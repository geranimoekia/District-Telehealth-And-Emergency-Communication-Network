"""
delay_samples.py
----------------
Per-packet / per-session delay sample generator for TELE 527 Group 1.

The analytical M/M/1 P95 values in teletraffic.py are sufficient for KPI
PASS/FAIL checks, but the spec requires plots that need distributions,
not scalars (§4.5):

  - CDF of telemetry delay, with P99 marker and the 50 ms target line
  - Histogram of video session delay, with P95 marker and the 150 ms line
  - Histogram of voice call setup delay (post-dial delay via M/M/N model)

This module generates synthetic delay samples per class per site by drawing
from the appropriate queuing distribution and adding the link propagation
delay from scenario.yaml.

Models used
-----------
Telemetry  — Packetised M/M/1:
    lambda (pps) = arrival_rate_per_hour / 3600 / packet_size_bits
    mu     (pps) = link_bps / packet_size_bits    (strict priority → full link)
    W ~ Exponential(mu - lambda)

Video      — Packetised M/M/1 on WFQ share:
    Same as telemetry but mu uses 0.40 * link_bps (WFQ weight for video)
    Packets approximated as 1500-byte Ethernet frames.

Voice      — M/M/N (Erlang C) call setup delay:
    Voice is a circuit-switched loss system (Erlang B blocks calls when
    all N* circuits are busy). For calls that are NOT blocked, the setup
    delay is the one-way signalling round-trip: propagation to CR-1
    plus a fixed SIP processing time. We model this as a constant
    (propagation + processing) because accepted calls seize a circuit
    immediately. The Erlang C waiting time is included for completeness
    to show the expected queue wait if the system were a delay system
    (M/M/N) rather than a loss system — this is the conservative upper
    bound on voice setup delay.

Public API
----------
  sample_telemetry_delays(scenario, n_samples, alpha=1.0)  -> np.ndarray (ms)
  sample_video_delays    (scenario, n_samples, alpha=1.0)  -> np.ndarray (ms)
  sample_voice_delays    (scenario, n_samples, alpha=1.0)  -> np.ndarray (ms)
  build_delay_samples    (scenario, n_samples=20_000,
                          alpha=1.0)                       -> dict of arrays
  delay_sample_summary   (scenario, n_samples=20_000)      -> pd.DataFrame

Student 2 responsibility - Traffic and Teletraffic Lead
TELE 527 | Group 1 | BIUST | 2026
"""

import os
import math
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
    seed = int(scenario["simulation"]["random_seed"]) + int(stream_offset)
    return np.random.default_rng(seed)


# -----------------------------------------------------------------------
# Core sampler — packetised M/M/1
# -----------------------------------------------------------------------

def _mm1_sojourn_samples_ms(
    lambda_pps: float,
    mu_pps: float,
    n_samples: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Draw n_samples from the M/M/1 sojourn-time distribution (milliseconds).
    Returns array of +inf if the queue is unstable (rho >= 1).
    """
    if mu_pps <= 0 or lambda_pps >= mu_pps:
        return np.full(n_samples, np.inf)
    rate_per_s = mu_pps - lambda_pps
    return rng.exponential(scale=1.0 / rate_per_s, size=n_samples) * 1000.0


# -----------------------------------------------------------------------
# Telemetry samples (strict priority, full link)
# -----------------------------------------------------------------------

def sample_telemetry_delays(
    scenario: dict,
    n_samples: int = 20_000,
    alpha: float = 1.0,
) -> np.ndarray:
    """
    Packetised M/M/1 telemetry delay samples (ms) across all BS sites.

    Effective link = 100 Mbps (strict priority / DSCP 46).
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
    Packetised M/M/1 video delay samples (ms) across all BS sites.

    Effective link = 0.40 × 100 Mbps (WFQ weight for video).
    Video stream carried as 1500-byte Ethernet frames.
    """
    vid        = scenario["traffic"]["video"]
    link_bps   = 100e6
    wfq_bps    = 0.40 * link_bps
    pkt_bits   = 1500 * 8
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
# Voice samples — call setup delay (M/M/N Erlang C waiting time)
# -----------------------------------------------------------------------

def sample_voice_delays(
    scenario: dict,
    n_samples: int = 20_000,
    alpha: float = 1.0,
) -> np.ndarray:
    """
    Voice call setup delay samples (ms) across all BS sites.

    Voice is a circuit-switched loss system (Erlang B). Calls that
    are NOT blocked seize a circuit immediately; their setup delay is:

        setup_delay = propagation_ms (one-way BS→CR-1) + processing_ms

    where processing_ms is the SIP signalling round-trip processing
    time at CR-1 (fixed at 5 ms, consistent with teletraffic.py).

    To show the queuing component, we also model the M/M/N Erlang C
    conditional waiting time for calls that would have to wait if this
    were a delay system (conservative upper bound). The distribution of
    the conditional wait time W | W > 0 for M/M/N is:

        W | W > 0  ~  Exponential(rate = N*mu - lambda)

    where N is the dimensioned circuit count and mu = 1/holding_time_s.

    We draw samples from a mixture:
        - proportion (1 - C(A, N))  → wait = 0  (immediate service)
        - proportion C(A, N)        → wait ~ Exp(N*mu - lambda)

    Then add propagation + processing delay.

    Parameters
    ----------
    scenario : dict
    n_samples : int
    alpha : float

    Returns
    -------
    np.ndarray  (ms), shape (n_samples,)
    """
    from teletraffic import erlang_c, dimension_channels

    vox       = scenario["traffic"]["voice"]
    A0        = vox["offered_load_erl"]
    target_B  = vox["kpi_blocking_prob"]
    h         = vox["holding_time_s"]
    sites     = _base_stations(scenario)

    PROC_MS   = 5.0    # SIP processing at CR-1 (ms)

    A         = A0 * alpha
    N         = dimension_channels(A, target_B)
    mu        = 1.0 / h                     # completions per second per circuit
    lam       = A / h                       # arrivals per second = A * mu

    # Erlang C probability of waiting (M/M/N delay system)
    C         = erlang_c(A, N)

    # Rate parameter for conditional waiting time distribution
    # N*mu - lambda must be > 0 for stability
    rate_wait = max(N * mu - lam, 1e-9)    # per second

    per_site  = max(1, n_samples // len(sites))
    rng       = _rng(scenario, stream_offset=303)

    chunks = []
    for site in sites:
        prop_ms = _site_prop_delay_ms(scenario, site)

        # Bernoulli draw: does this call have to wait?
        has_wait = rng.random(per_site) < C
        n_wait   = int(has_wait.sum())
        n_no_wait = per_site - n_wait

        # Waiting calls: exponential wait + prop + proc
        wait_ms = np.zeros(per_site)
        if n_wait > 0:
            wait_ms[has_wait] = (
                rng.exponential(scale=1.0 / rate_wait, size=n_wait) * 1000.0
            )

        setup_delay = wait_ms + prop_ms + PROC_MS
        chunks.append(setup_delay)

    return np.concatenate(chunks)


# -----------------------------------------------------------------------
# Bundle all three classes
# -----------------------------------------------------------------------

def build_delay_samples(
    scenario: dict,
    n_samples: int = 20_000,
    alpha: float = 1.0,
) -> dict:
    """
    Generate delay samples for telemetry, video, and voice.

    Returns
    -------
    dict with keys: telemetry_ms, video_ms, voice_ms, n_samples, alpha
    """
    tel = sample_telemetry_delays(scenario, n_samples, alpha)
    vid = sample_video_delays    (scenario, n_samples, alpha)
    vox = sample_voice_delays    (scenario, n_samples, alpha)
    return {
        "telemetry_ms": tel,
        "video_ms":     vid,
        "voice_ms":     vox,
        "n_samples":    int(len(tel)),
        "alpha":        alpha,
    }


def delay_sample_summary(
    scenario: dict,
    n_samples: int = 20_000,
    alpha: float = 1.0,
) -> pd.DataFrame:
    """
    Compute percentile statistics and KPI PASS/FAIL for all three classes.

    Returns
    -------
    pd.DataFrame
        Columns: class, samples, mean_ms, p50_ms, p95_ms, p99_ms,
                 kpi_target_ms, kpi_percentile, kpi_met
    """
    bundle = build_delay_samples(scenario, n_samples, alpha)

    tel_target = scenario["traffic"]["telemetry"]["kpi_delay_p95_ms"]  # 50 ms
    vid_target = scenario["traffic"]["video"]["kpi_delay_p95_ms"]       # 150 ms
    # Voice KPI: blocking probability (not delay). For the delay summary we
    # report setup delay statistics without a hard KPI target — use 150 ms
    # as a reference (same as video, conservative for voice setup).
    vox_ref    = 150.0

    def _stats(arr, name, target, pctile):
        finite = arr[np.isfinite(arr)]
        if len(finite) == 0:
            return {
                "class": name, "samples": len(arr),
                "mean_ms": np.inf, "p50_ms": np.inf,
                "p95_ms": np.inf, "p99_ms": np.inf,
                "kpi_target_ms": target,
                "kpi_percentile": f"P{pctile}", "kpi_met": False,
            }
        mean_ms = float(np.mean(finite))
        p50     = float(np.percentile(finite, 50))
        p95     = float(np.percentile(finite, 95))
        p99     = float(np.percentile(finite, 99))
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
        _stats(bundle["telemetry_ms"], "telemetry", tel_target, 99),
        _stats(bundle["video_ms"],     "video",     vid_target, 95),
        _stats(bundle["voice_ms"],     "voice",     vox_ref,    95),
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

    # Export
    out_dir = os.path.join(os.path.dirname(__file__), "..", "outputs")
    os.makedirs(out_dir, exist_ok=True)

    bundle = build_delay_samples(sc, n_samples=20_000, alpha=1.0)
    pd.DataFrame({"telemetry_delay_ms": bundle["telemetry_ms"]}).to_csv(
        os.path.join(out_dir, "delay_samples_telemetry.csv"), index=False
    )
    pd.DataFrame({"video_delay_ms": bundle["video_ms"]}).to_csv(
        os.path.join(out_dir, "delay_samples_video.csv"), index=False
    )
    pd.DataFrame({"voice_setup_delay_ms": bundle["voice_ms"]}).to_csv(
        os.path.join(out_dir, "delay_samples_voice.csv"), index=False
    )
    summary.to_csv(
        os.path.join(out_dir, "delay_samples_summary.csv"), index=False
    )

    print("\nCSV files saved to outputs/:")
    for name in [
        "delay_samples_telemetry.csv",
        "delay_samples_video.csv",
        "delay_samples_voice.csv",
        "delay_samples_summary.csv",
    ]:
        print(f"  {name}")