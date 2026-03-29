"""
traffic.py
----------
Traffic generation module for TELE 527 Group 1 - District Telehealth Network.

Generates synthetic packet flows and voice/video call arrivals for three
service classes: telemetry, voice, and video.

All parameters are read from scenario.yaml so changing the scenario file
automatically propagates to all traffic outputs.

Supports:
  - Poisson arrival process per class per site
  - Exponential holding times
  - Load multiplier (alpha) for stress testing
  - Per-link bandwidth demand matrix for routing/QoS modules
  - Link utilisation summary

Student 2 responsibility - Traffic and Teletraffic Lead
TELE 527 | Group 1 | BIUST | 2026
"""

import math
import numpy as np
import pandas as pd
import yaml
from pathlib import Path
from typing import Optional


# -----------------------------------------------------------------------
# Scenario loader
# -----------------------------------------------------------------------

def load_scenario(path: str = "scenario.yaml") -> dict:
    """
    Load the shared scenario YAML file.

    Parameters
    ----------
    path : str
        Path to scenario.yaml relative to the working directory.

    Returns
    -------
    dict
        Full scenario configuration.
    """
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# -----------------------------------------------------------------------
# Helper: propagation delay lookup per BS
# -----------------------------------------------------------------------

def _site_prop_delay_ms(scenario: dict, site_name: str) -> float:
    """
    Return the one-way propagation delay (ms) on the primary link
    from a base station to CR-1.

    Falls back to 8.0 ms if the link is not found.
    """
    for link in scenario["links"]:
        if link["from"] == site_name and link["to"] == "CR-1" and link.get("role") == "primary":
            return float(link["delay_ms"])
    return 8.0


def _base_stations(scenario: dict) -> list[str]:
    """Return names of all base station sites."""
    return [s["name"] for s in scenario["sites"] if s["type"] == "base_station"]


# -----------------------------------------------------------------------
# Offered load (theoretical)
# -----------------------------------------------------------------------

def compute_offered_load(
    scenario: dict,
    load_multiplier: float = 1.0,
) -> pd.DataFrame:
    """
    Compute theoretical offered load (Erlang) per site per service class.

    Uses the formula:  A = lambda * h
    where lambda is the arrival rate (calls/s) and h is the mean holding time (s).

    Parameters
    ----------
    scenario : dict
        Loaded scenario YAML.
    load_multiplier : float
        Alpha multiplier for stress testing. 1.0 = normal load.

    Returns
    -------
    pd.DataFrame
        Columns: site, service_class, arrival_rate_per_hour,
                 holding_time_s, offered_load_erl
    """
    traffic_cfg = scenario["traffic"]
    sites = _base_stations(scenario)

    rows = []
    for site in sites:
        for svc, cfg in [
            ("telemetry", traffic_cfg["telemetry"]),
            ("voice",     traffic_cfg["voice"]),
            ("video",     traffic_cfg["video"]),
        ]:
            lam_h = cfg["arrival_rate_per_hour"] * load_multiplier
            h     = cfg["holding_time_s"]
            A     = cfg["offered_load_erl"] * load_multiplier  # same as lam_h * h / 3600
            rows.append({
                "site":                  site,
                "service_class":         svc,
                "arrival_rate_per_hour": round(lam_h, 4),
                "holding_time_s":        h,
                "offered_load_erl":      round(A, 4),
            })

    return pd.DataFrame(rows)


# -----------------------------------------------------------------------
# Traffic matrix (bandwidth demand per link)
# -----------------------------------------------------------------------

def compute_traffic_matrix(
    scenario: dict,
    load_multiplier: float = 1.0,
) -> pd.DataFrame:
    """
    Compute per-link traffic demand in Mbps from each BS to CR-1.

    Method
    ------
    * Telemetry:  aggregate_bps = lambda_ps * packet_size_bits
    * Voice:      aggregate_bps = A * bitrate_bps
    * Video:      aggregate_bps = A * bitrate_bps

    The offered load A gives the expected number of simultaneously active
    sessions (Little's Law), each consuming their respective bitrate.

    Parameters
    ----------
    scenario : dict
        Loaded scenario YAML.
    load_multiplier : float
        Alpha multiplier.

    Returns
    -------
    pd.DataFrame
        Columns: site, destination, telemetry_mbps, voice_mbps, video_mbps,
                 total_mbps, link_capacity_mbps, link_utilisation
    """
    traffic_cfg = scenario["traffic"]
    sites       = _base_stations(scenario)
    link_cap    = 100.0  # Mbps, all backhaul links in the scenario

    rows = []
    for site in sites:
        tel_cfg = traffic_cfg["telemetry"]
        vox_cfg = traffic_cfg["voice"]
        vid_cfg = traffic_cfg["video"]

        # Telemetry: packet rate * packet size
        lam_tel_ps = tel_cfg["arrival_rate_per_hour"] * load_multiplier / 3600.0
        tel_bps    = lam_tel_ps * tel_cfg["packet_size_bytes"] * 8          # <-- in bps
        tel_mbps   = tel_bps / 1e6

        # Voice: expected active calls * bitrate
        A_voice    = vox_cfg["offered_load_erl"] * load_multiplier
        voice_mbps = A_voice * vox_cfg["bitrate_kbps"] / 1000.0

        # Video: expected active sessions * bitrate
        A_video    = vid_cfg["offered_load_erl"] * load_multiplier
        video_mbps = A_video * vid_cfg["bitrate_mbps"]

        total_mbps  = tel_mbps + voice_mbps + video_mbps
        utilisation = total_mbps / link_cap

        rows.append({
            "site":               site,
            "destination":        "CR-1",
            "telemetry_mbps":     round(tel_mbps,   6),   # ← was 4 dp; micro-Mbps needs 6
            "voice_mbps":         round(voice_mbps,  4),
            "video_mbps":         round(video_mbps,  4),
            "total_mbps":         round(total_mbps,  4),
            "link_capacity_mbps": link_cap,
            "link_utilisation":   round(utilisation, 6),
        })
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------
# Aggregate backhaul trunk demand (all BS sites → CR-1)
# -----------------------------------------------------------------------

def compute_trunk_demand(
    scenario: dict,
    load_multiplier: float = 1.0,
) -> dict:
    """
    Compute aggregate bandwidth demand on the backhaul trunk (all 5 sites).

    Returns
    -------
    dict
        Keys: telemetry_mbps, voice_mbps, video_mbps, total_mbps,
              trunk_capacity_mbps, trunk_utilisation
    """
    matrix = compute_traffic_matrix(scenario, load_multiplier)
    link_cap = 100.0  # each site has its own 100 Mbps backhaul

    # Each site has an independent link → report per-site peak, not sum
    peak = matrix.loc[matrix["total_mbps"].idxmax()]
    return {
        "peak_site":            peak["site"],
        "telemetry_mbps":       round(matrix["telemetry_mbps"].sum(), 4),
        "voice_mbps":           round(matrix["voice_mbps"].sum(), 4),
        "video_mbps":           round(matrix["video_mbps"].sum(), 4),
        "aggregate_total_mbps": round(matrix["total_mbps"].sum(), 4),
        "per_site_peak_mbps":   round(peak["total_mbps"], 4),
        "link_capacity_mbps":   link_cap,
        "worst_link_utilisation": round(peak["link_utilisation"], 6),
    }


# -----------------------------------------------------------------------
# Poisson event generator
# -----------------------------------------------------------------------

def generate_traffic_events(
    scenario: dict,
    load_multiplier: float = 1.0,
    duration_hours: float = 1.0,
    rng: Optional[np.random.Generator] = None,
) -> pd.DataFrame:
    """
    Generate a synthetic event trace using Poisson arrivals and
    exponential holding times for each service class at each site.

    The inter-arrival time between consecutive calls follows
        IAT ~ Exp(1/lambda)
    and the session duration follows
        H   ~ Exp(1/mean_holding_time).

    Parameters
    ----------
    scenario : dict
        Loaded scenario YAML.
    load_multiplier : float
        Alpha multiplier (scales arrival rates, not holding times).
    duration_hours : float
        Simulation window in hours. Default = 1 busy hour.
    rng : np.random.Generator, optional
        Seeded RNG. Uses scenario random_seed if None.

    Returns
    -------
    pd.DataFrame
        One row per event. Columns:
        time_s, end_time_s, site, service_class, duration_s,
        packet_size_bytes, bitrate_bps, dscp
    """
    if rng is None:
        seed = scenario["simulation"]["random_seed"]
        rng  = np.random.default_rng(seed)

    traffic_cfg  = scenario["traffic"]
    sites        = _base_stations(scenario)
    duration_s   = duration_hours * 3600.0

    class_meta = {
        "telemetry": {
            "cfg":          traffic_cfg["telemetry"],
            "packet_bytes": traffic_cfg["telemetry"]["packet_size_bytes"],
            "bitrate_bps":  0.0,
            "dscp":         traffic_cfg["telemetry"]["dscp"],
        },
        "voice": {
            "cfg":          traffic_cfg["voice"],
            "packet_bytes": 0,
            "bitrate_bps":  traffic_cfg["voice"]["bitrate_kbps"] * 1000.0,
            "dscp":         traffic_cfg["voice"]["dscp"],
        },
        "video": {
            "cfg":          traffic_cfg["video"],
            "packet_bytes": 0,
            "bitrate_bps":  traffic_cfg["video"]["bitrate_mbps"] * 1e6,
            "dscp":         traffic_cfg["video"]["dscp"],
        },
    }

    events = []
    for site in sites:
        for svc, meta in class_meta.items():
            cfg = meta["cfg"]
            lam = cfg["arrival_rate_per_hour"] * load_multiplier / 3600.0  # arrivals/s
            mu  = 1.0 / cfg["holding_time_s"]                              # completions/s

            t = 0.0
            while True:
                iat = rng.exponential(1.0 / lam)
                t  += iat
                if t >= duration_s:
                    break
                hold = rng.exponential(1.0 / mu)
                events.append({
                    "time_s":           round(t, 4),
                    "end_time_s":       round(t + hold, 4),
                    "site":             site,
                    "service_class":    svc,
                    "duration_s":       round(hold, 4),
                    "packet_size_bytes": meta["packet_bytes"],
                    "bitrate_bps":      meta["bitrate_bps"],
                    "dscp":             meta["dscp"],
                })

    df = pd.DataFrame(events).sort_values("time_s").reset_index(drop=True)
    return df


# -----------------------------------------------------------------------
# Concurrent active sessions at each time step
# -----------------------------------------------------------------------

def compute_active_sessions(
    events: pd.DataFrame,
    resolution_s: float = 60.0,
) -> pd.DataFrame:
    """
    Count simultaneously active sessions per class per site over time.

    Scans a time grid with step = resolution_s and counts events where
    time_s <= t < end_time_s.

    Parameters
    ----------
    events : pd.DataFrame
        Output of generate_traffic_events().
    resolution_s : float
        Time step for the activity grid (seconds).

    Returns
    -------
    pd.DataFrame
        Columns: time_s, site, service_class, active_sessions
    """
    t_max  = events["end_time_s"].max()
    times  = np.arange(0, t_max, resolution_s)
    rows   = []

    for t in times:
        active = events[(events["time_s"] <= t) & (events["end_time_s"] > t)]
        for (site, svc), grp in active.groupby(["site", "service_class"]):
            rows.append({
                "time_s":          t,
                "site":            site,
                "service_class":   svc,
                "active_sessions": len(grp),
            })

    return pd.DataFrame(rows)


# -----------------------------------------------------------------------
# Stress test bandwidth summary
# -----------------------------------------------------------------------

def stress_bandwidth_sweep(scenario: dict) -> pd.DataFrame:
    """
    Compute traffic matrix metrics at each load multiplier step.

    Useful for the Streamlit dashboard's stress comparison tab.

    Returns
    -------
    pd.DataFrame
        Columns: load_multiplier, worst_site, worst_link_utilisation,
                 total_mbps_all_sites, voice_mbps, video_mbps, telemetry_mbps
    """
    rows = []
    for alpha in scenario["simulation"]["load_multiplier_steps"]:
        trunk = compute_trunk_demand(scenario, alpha)
        rows.append({
            "load_multiplier":       alpha,
            "worst_site":            trunk["peak_site"],
            "worst_link_utilisation": trunk["worst_link_utilisation"],
            "total_mbps_all_sites":  trunk["aggregate_total_mbps"],
            "voice_mbps":            trunk["voice_mbps"],
            "video_mbps":            trunk["video_mbps"],
            "telemetry_mbps":        trunk["telemetry_mbps"],
        })
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------
# Standalone demo
# -----------------------------------------------------------------------

if __name__ == "__main__":
    import os

    scenario_path = os.path.join(os.path.dirname(__file__), "..", "scenario.yaml")
    sc = load_scenario(scenario_path)

    print("=" * 60)
    print("OFFERED LOAD (alpha = 1.0)")
    print("=" * 60)
    print(compute_offered_load(sc).to_string(index=False))

    print("\n" + "=" * 60)
    print("TRAFFIC MATRIX (alpha = 1.0)")
    print("=" * 60)
    print(compute_traffic_matrix(sc).to_string(index=False))

    print("\n" + "=" * 60)
    print("TRUNK DEMAND SUMMARY")
    print("=" * 60)
    for k, v in compute_trunk_demand(sc).items():
        print(f"  {k:30s}: {v}")

    print("\n" + "=" * 60)
    print("STRESS BANDWIDTH SWEEP")
    print("=" * 60)
    print(stress_bandwidth_sweep(sc).to_string(index=False))

    print("\n" + "=" * 60)
    print("POISSON EVENT TRACE (first 10 events)")
    print("=" * 60)
    events = generate_traffic_events(sc, load_multiplier=1.0, duration_hours=1.0)
    print(events.head(10).to_string(index=False))
    print(f"\nTotal events generated: {len(events)}")