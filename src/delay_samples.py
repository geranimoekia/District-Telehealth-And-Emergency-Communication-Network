"""
delay_samples.py
----------------
Per-packet / per-session delay sample generator for TELE 527 Group 1.

The analytical M/M/1 P95 values in teletraffic.py are sufficient for KPI
PASS/FAIL checks, but the spec requires two plots that need distributions,
not scalars (§4.5):

  - CDF of telemetry delay, with P99 marker and the 50 ms target line
  - Histogram of video session delay, with P95 marker and the 150 ms line

This module generates synthetic delay samples per class per site by drawing
from the M/M/1 sojourn-time distribution (packetised) and adding the link's
propagation delay from scenario.yaml.

Packetised M/M/1 model
----------------------
Each traffic class is modelled as an M/M/1 queue with:
    - service rate  mu = (effective link capacity bps) / (packet size bits)
                    = packets per second the link can serve
    - arrival rate  lambda = packet arrival rate per second
    - utilisation   rho = lambda / mu

For a stable queue (rho < 1) the sojourn time W is exponentially
distributed:
    W ~ Exponential(rate = mu * (1 - rho))
    E[W] = 1 / (mu * (1 - rho)) seconds

This is the standard textbook packet-M/M/1 result, which produces queuing
delays that grow meaningfully as rho approaches 1 (matching what the report
reader expects to see on the CDF and histogram).

Telemetry packets use the configured packet size; video "packets" are
approximated as standard 1500-byte Ethernet frames carrying the video
stream bits.

Public API
----------
  sample_telemetry_delays(scenario, n_samples, alpha=1.0)  -> np.ndarray (ms)
  sample_video_delays    (scenario, n_samples, alpha=1.0)  -> np.ndarray (ms)
  build_delay_samples    (scenario, n_samples=20_000,
                          alpha=1.0)                       -> dict of arrays
  delay_sample_summary   (scenario, n_samples=20_000)      -> pd.DataFrame

Student 2 responsibility - Traffic and Teletraffic Lead
TELE 527 | Group 1 | BIUST | 2026
"""

import os
import numpy as np
import pandas as pd
import yaml


# -----------------------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------------------

def load_scenario(path: str = "scenario.yaml") -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _base_stations(scenario: dict) -> list:
    return [s["name"] for s in scenario["sites"] if s["type"] == "base_station"]


def _site_prop_delay_ms(scenario: dict, site_name: str) -> float:
    for link in scenario["links"]:
        if (
            link["from"] == site_name
            and link["to"] == "CR-1"
            and link.get("role") == "primary"
        ):
            return float(link["delay_ms"])
    return 8.0


def _rng(scenario: dict, stream_offset: int = 0) -> np.random.Generator:
    """
    Deterministic RNG seeded from scenario.simulation.random_seed + offset.
    Different offsets give independent streams for different classes.
    """
    seed = int(scenario["simulation"]["random_seed"]) + int(stream_offset)
    return np.random.default_rng(seed)


# -----------------------------------------------------------------------
# Core sampler  -  packetised M/M/1
# -----------------------------------------------------------------------

def _mm1_sojourn_samples_ms(
    lambda_pps: float,
    mu_pps: float,
    n_samples: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Draw n_samples from the M/M/1 sojourn-time distribution in MILLISECONDS.

    Parameters
    ----------
    lambda_pps : float
        Packet arrival rate (packets/second).
    mu_pps : float
        Service rate (packets/second) = link_capacity_bps / packet_size_bits.
    n_samples : int
    rng : np.random.Generator

    For a stable M/M/1:
        W ~ Exponential(rate = mu - lambda)   [rate in per-second units]
        E[W] = 1 / (mu - lambda)   seconds

    If the queue is unstable (rho >= 1), returns an array of +inf.
    """
    if mu_pps <= 0 or lambda_pps >= mu_pps:
        return np.full(n_samples, np.inf)
    rate_per_s = mu_pps - lambda_pps               # per second
    samples_s  = rng.exponential(scale=1.0 / rate_per_s, size=n_samples)
    return samples_s * 1000.0


# -----------------------------------------------------------------------
# Telemetry samples (strict priority, full link)
# -----------------------------------------------------------------------

def sample_telemetry_delays(
    scenario: dict,
    n_samples: int = 20_000,
    alpha: float = 1.0,
) -> np.ndarray:
    """
    Draw per-packet telemetry end-to-end delay samples (ms), aggregated
    across all base station sites.

    Each BS contributes an equal share of the samples, with its own
    propagation delay added.

    Model (packetised M/M/1)
    ------------------------
    * Packet arrival rate     λ = arrival_rate_per_hour * alpha / 3600
    * Packet service rate     μ = link_bps / (packet_size_bytes * 8)
    * Link effective capacity = full 100 Mbps (strict priority / DSCP 46)
    * End-to-end delay        = M/M/1 sojourn + site propagation

    Returns
    -------
    np.ndarray of shape (n_samples,)
    """
    tel       = scenario["traffic"]["telemetry"]
    link_bps  = 100e6
    pkt_bits  = tel["packet_size_bytes"] * 8
    sites     = _base_stations(scenario)

    lam_pps   = tel["arrival_rate_per_hour"] * alpha / 3600.0
    mu_pps    = link_bps / pkt_bits if pkt_bits > 0 else 0.0

    per_site  = max(1, n_samples // len(sites))
    rng       = _rng(scenario, stream_offset=101)

    chunks = []
    for site in sites:
        prop_ms = _site_prop_delay_ms(scenario, site)
        sojourn = _mm1_sojourn_samples_ms(lam_pps, mu_pps, per_site, rng)
        chunks.append(sojourn + prop_ms)

    return np.concatenate(chunks)


# -----------------------------------------------------------------------
# Video samples (WFQ weight 0.40)
# -----------------------------------------------------------------------

def sample_video_delays(
    scenario: dict,
    n_samples: int = 20_000,
    alpha: float = 1.0,
) -> np.ndarray:
    """
    Draw per-packet video end-to-end delay samples (ms), aggregated across
    all base station sites.

    Model (packetised M/M/1)
    ------------------------
    * Video stream carried as 1500-byte Ethernet frames.
    * Aggregate arrival rate (bps)  = offered_load_erl * bitrate_mbps * 1e6
    * Packet arrival rate (pps)     = aggregate_bps / (1500 * 8)
    * Effective link for video      = 0.40 * link_capacity (WFQ weight)
    * Packet service rate (pps)     = wfq_bps / (1500 * 8)
    * End-to-end delay              = M/M/1 sojourn + site propagation

    Returns
    -------
    np.ndarray of shape (n_samples,)
    """
    vid        = scenario["traffic"]["video"]
    link_bps   = 100e6
    wfq_bps    = 0.40 * link_bps               # WFQ effective rate for video
    pkt_bits   = 1500 * 8                       # standard Ethernet MTU
    sites      = _base_stations(scenario)

    A_vid      = vid["offered_load_erl"] * alpha
    arr_bps    = A_vid * vid["bitrate_mbps"] * 1e6
    lam_pps    = arr_bps / pkt_bits
    mu_pps     = wfq_bps / pkt_bits

    per_site   = max(1, n_samples // len(sites))
    rng        = _rng(scenario, stream_offset=202)

    chunks = []
    for site in sites:
        prop_ms = _site_prop_delay_ms(scenario, site)
        sojourn = _mm1_sojourn_samples_ms(lam_pps, mu_pps, per_site, rng)
        chunks.append(sojourn + prop_ms)

    return np.concatenate(chunks)


# -----------------------------------------------------------------------
# Bundle both classes + summary stats
# -----------------------------------------------------------------------

def build_delay_samples(
    scenario: dict,
    n_samples: int = 20_000,
    alpha: float = 1.0,
) -> dict:
    """
    Generate delay samples for both telemetry and video in a single call.

    Returns
    -------
    dict with keys:
        telemetry_ms : np.ndarray
        video_ms     : np.ndarray
        n_samples    : int   (actual length after per-site rounding)
        alpha        : float
    """
    tel = sample_telemetry_delays(scenario, n_samples, alpha)
    vid = sample_video_delays    (scenario, n_samples, alpha)
    return {
        "telemetry_ms": tel,
        "video_ms":     vid,
        "n_samples":    int(len(tel)),
        "alpha":        alpha,
    }


def delay_sample_summary(
    scenario: dict,
    n_samples: int = 20_000,
    alpha: float = 1.0,
) -> pd.DataFrame:
    """
    Compute percentiles and PASS/FAIL vs the spec KPIs from the samples.

    Returns
    -------
    pd.DataFrame
        Columns: class, samples, mean_ms, p50_ms, p95_ms, p99_ms,
                 kpi_target_ms, kpi_percentile, kpi_met
    """
    bundle = build_delay_samples(scenario, n_samples, alpha)

    tel_target = scenario["traffic"]["telemetry"]["kpi_delay_p95_ms"]  # 50 ms target
    vid_target = scenario["traffic"]["video"]["kpi_delay_p95_ms"]      # 150 ms target

    def _stats(arr, name, target, pctile):
        mean_ms = float(np.mean(arr))
        p50     = float(np.percentile(arr, 50))
        p95     = float(np.percentile(arr, 95))
        p99     = float(np.percentile(arr, 99))
        kpi_val = p99 if pctile == 99 else p95
        return {
            "class":          name,
            "samples":        len(arr),
            "mean_ms":        round(mean_ms, 3),
            "p50_ms":         round(p50, 3),
            "p95_ms":         round(p95, 3),
            "p99_ms":         round(p99, 3),
            "kpi_target_ms":  target,
            "kpi_percentile": f"P{pctile}",
            "kpi_met":        bool(kpi_val <= target),
        }

    rows = [
        # Telemetry KPI in the spec is phrased as "P95 / P99 < 50 ms" —
        # we evaluate against the tighter P99 target.
        _stats(bundle["telemetry_ms"], "telemetry", tel_target, 99),
        _stats(bundle["video_ms"],     "video",     vid_target, 95),
    ]
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------
# Standalone demo
# -----------------------------------------------------------------------

if __name__ == "__main__":
    scenario_path = os.path.join(os.path.dirname(__file__), "..", "scenario.yaml")
    sc = load_scenario(scenario_path)

    print("=" * 65)
    print("DELAY SAMPLE SUMMARY  (α = 1.0, 20 000 samples per class)")
    print("=" * 65)
    summary = delay_sample_summary(sc, n_samples=20_000, alpha=1.0)
    print(summary.to_string(index=False))

    # Export full sample arrays (for plots.py to consume)
    out_dir = os.path.join(os.path.dirname(__file__), "..", "outputs")
    os.makedirs(out_dir, exist_ok=True)

    bundle = build_delay_samples(sc, n_samples=20_000, alpha=1.0)
    pd.DataFrame({"telemetry_delay_ms": bundle["telemetry_ms"]}).to_csv(
        os.path.join(out_dir, "delay_samples_telemetry.csv"), index=False
    )
    pd.DataFrame({"video_delay_ms": bundle["video_ms"]}).to_csv(
        os.path.join(out_dir, "delay_samples_video.csv"), index=False
    )
    summary.to_csv(
        os.path.join(out_dir, "delay_samples_summary.csv"), index=False
    )

    print("\nCSV files saved to outputs/:")
    for name in [
        "delay_samples_telemetry.csv",
        "delay_samples_video.csv",
        "delay_samples_summary.csv",
    ]:
        print(f"  {name}")