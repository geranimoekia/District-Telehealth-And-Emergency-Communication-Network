"""
teletraffic.py
--------------
Teletraffic engineering module for TELE 527 Group 1 - District Telehealth Network.

Implements:
  - Erlang B formula (exact recursive, numerically stable)
  - Erlang C formula (for delay systems, optional extension)
  - Voice channel dimensioning per site and for the backhaul trunk
  - M/M/1 delay model for telemetry and video KPI evaluation
  - Breaking point stress sweep (fixed baseline capacity, increasing alpha)
  - Erlang B curves and blocking-vs-load curves for the report

All inputs are read from scenario.yaml.

Design note on the M/M/1 delay model
-------------------------------------
Each BS-to-CR-1 microwave backhaul link (100 Mbps) is modelled as an M/M/1
queue. Traffic classes share the link via WFQ:
  - Telemetry: strict priority (SP) - served before voice and video
  - Voice:     WFQ weight 0.30 of remaining capacity
  - Video:     WFQ weight 0.40 of remaining capacity
Effective service capacity per class = WFQ_weight * link_capacity.
Total one-way delay = propagation delay (from scenario) + M/M/1 queuing delay.

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
# Scenario loader (mirrors traffic.py for standalone use)
# -----------------------------------------------------------------------

def load_scenario(path: str = "scenario.yaml") -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _base_stations(scenario: dict) -> list[str]:
    return [s["name"] for s in scenario["sites"] if s["type"] == "base_station"]


def _site_prop_delay_ms(scenario: dict, site_name: str) -> float:
    """One-way propagation delay on the primary BS → CR-1 link (ms)."""
    for link in scenario["links"]:
        if (
            link["from"] == site_name
            and link["to"] == "CR-1"
            and link.get("role") == "primary"
        ):
            return float(link["delay_ms"])
    return 8.0  # default fallback


# -----------------------------------------------------------------------
# Erlang B  (blocking probability, loss system)
# -----------------------------------------------------------------------

def erlang_b(A: float, N: int) -> float:
    """
    Erlang B blocking probability using the exact recursive formula.

    Recurrence (Jagerman 1974, numerically stable):
        B(A, 0) = 1
        B(A, n) = (A * B(A, n-1)) / (n + A * B(A, n-1))

    Parameters
    ----------
    A : float
        Offered traffic in Erlangs (A = lambda * h).
    N : int
        Number of circuits (channels).

    Returns
    -------
    float
        Blocking probability in [0, 1].
    """
    if A <= 0:
        return 0.0
    if N == 0:
        return 1.0
    b = 1.0
    for n in range(1, N + 1):
        b = (A * b) / (n + A * b)
    return b


# -----------------------------------------------------------------------
# Erlang C  (queuing probability, delay system - optional extension)
# -----------------------------------------------------------------------

def erlang_c(A: float, N: int) -> float:
    """
    Erlang C probability that an arriving call has to wait.

    C(A, N) = [A^N / (N! * (1 - A/N))] /
              [sum_{k=0}^{N-1} A^k/k! + A^N / (N! * (1 - A/N))]

    Uses the relationship:  C(A,N) = N * B(A,N) / (N - A * (1 - B(A,N)))
    Valid only when A < N (stable system).

    Parameters
    ----------
    A : float
        Offered traffic in Erlangs.
    N : int
        Number of servers.

    Returns
    -------
    float
        Probability of waiting. Returns 1.0 if A >= N (overloaded).
    """
    if A >= N:
        return 1.0
    b = erlang_b(A, N)
    return (N * b) / (N - A * (1.0 - b))


# -----------------------------------------------------------------------
# Channel dimensioning
# -----------------------------------------------------------------------

def dimension_channels(A: float, target_blocking: float) -> int:
    """
    Find the minimum number of circuits N so that erlang_b(A, N) <= target.

    Starts from ceil(A) and increments until the KPI is satisfied.

    Parameters
    ----------
    A : float
        Offered traffic in Erlangs.
    target_blocking : float
        Maximum acceptable blocking probability (e.g. 0.02 for 2%).

    Returns
    -------
    int
        Minimum number of circuits required.
    """
    if A <= 0:
        return 1
    N = max(1, math.ceil(A))
    while erlang_b(A, N) > target_blocking:
        N += 1
    return N


# -----------------------------------------------------------------------
# Erlang B curves (for report figures)
# -----------------------------------------------------------------------

def erlang_b_curve(A: float, N_max: int = 20) -> pd.DataFrame:
    """
    Blocking probability vs number of circuits for a fixed offered load A.

    Useful for plotting the dimensioning operating point on the Erlang B curve.

    Returns
    -------
    pd.DataFrame
        Columns: circuits_N, blocking_prob
    """
    return pd.DataFrame(
        [{"circuits_N": n, "blocking_prob": erlang_b(A, n)} for n in range(0, N_max + 1)]
    )


def blocking_vs_load(N: int, A_max: float = 10.0, steps: int = 200) -> pd.DataFrame:
    """
    Blocking probability vs offered load for a fixed circuit count N.

    Useful for showing where the baseline design sits on the Erlang curve
    and how blocking degrades as load grows.

    Returns
    -------
    pd.DataFrame
        Columns: offered_load_erl, blocking_prob
    """
    loads = np.linspace(0.01, A_max, steps)
    return pd.DataFrame(
        [{"offered_load_erl": round(A, 4), "blocking_prob": erlang_b(A, N)} for A in loads]
    )


# -----------------------------------------------------------------------
# Dimensioning tables
# -----------------------------------------------------------------------

def dimension_voice_per_site(
    scenario: dict,
    load_multiplier: float = 1.0,
) -> pd.DataFrame:
    """
    Dimension voice circuits for each base station site.

    The Erlang B model treats each BS-to-CR-1 backhaul as a loss system
    with N circuits serving A Erlangs of voice traffic.

    Returns
    -------
    pd.DataFrame
        Columns: site, offered_load_erl, channels_required,
                 achieved_blocking, target_blocking, kpi_met
    """
    cfg         = scenario["traffic"]["voice"]
    A_base      = cfg["offered_load_erl"]
    target_B    = cfg["kpi_blocking_prob"]
    sites       = _base_stations(scenario)

    rows = []
    for site in sites:
        A = A_base * load_multiplier
        N = dimension_channels(A, target_B)
        B = erlang_b(A, N)
        rows.append({
            "site":               site,
            "offered_load_erl":   round(A, 4),
            "channels_required":  N,
            "achieved_blocking":  round(B, 6),
            "target_blocking":    target_B,
            "kpi_met":            bool(B <= target_B),
        })
    return pd.DataFrame(rows)


def dimension_backhaul_trunk(
    scenario: dict,
    load_multiplier: float = 1.0,
) -> dict:
    """
    Dimension the voice backhaul trunk for aggregate traffic from all 5 sites.

    The trunk carries the combined voice Erlangs from all base stations.
    Trunking efficiency means fewer circuits are needed per Erlang compared
    to individual site dimensioning (the trunking gain principle).

    Returns
    -------
    dict with keys:
        offered_load_erl, channels_required, achieved_blocking,
        target_blocking, kpi_met, trunking_gain_channels
    """
    A_trunk  = scenario["traffic"]["backhaul_trunk_erl"] * load_multiplier
    target_B = scenario["traffic"]["voice"]["kpi_blocking_prob"]
    N        = dimension_channels(A_trunk, target_B)
    B        = erlang_b(A_trunk, N)

    # Trunking gain: channels saved vs. N_sites * N_per_site
    per_site_N = dimension_channels(
        scenario["traffic"]["voice"]["offered_load_erl"] * load_multiplier, target_B
    )
    n_sites    = len(_base_stations(scenario))
    trunking_gain = (n_sites * per_site_N) - N

    return {
        "offered_load_erl":        round(A_trunk, 4),
        "channels_required":       N,
        "achieved_blocking":       round(B, 6),
        "target_blocking":         target_B,
        "kpi_met":                 bool(B <= target_B),
        "trunking_gain_channels":  trunking_gain,
    }


def full_dimensioning_table(
    scenario: dict,
    load_multiplier: float = 1.0,
) -> pd.DataFrame:
    """
    Combined dimensioning table: per-site voice + aggregate backhaul trunk.

    Returns
    -------
    pd.DataFrame
        Same columns as dimension_voice_per_site, with a trunk summary row appended.
    """
    per_site = dimension_voice_per_site(scenario, load_multiplier)
    trunk    = dimension_backhaul_trunk(scenario, load_multiplier)
    trunk_row = pd.DataFrame([{
        "site":               "Backhaul trunk (5 sites aggregate)",
        "offered_load_erl":   trunk["offered_load_erl"],
        "channels_required":  trunk["channels_required"],
        "achieved_blocking":  trunk["achieved_blocking"],
        "target_blocking":    trunk["target_blocking"],
        "kpi_met":            trunk["kpi_met"],
    }])
    return pd.concat([per_site, trunk_row], ignore_index=True)


# -----------------------------------------------------------------------
# M/M/1 delay model
# -----------------------------------------------------------------------

def _mm1_p95_delay_ms(
    arrival_rate_bps: float,
    service_rate_bps: float,
    propagation_ms: float = 0.0,
    percentile: float = 0.95,
    packet_size_bits: float = 1500 * 8,
) -> float:
    """
    Compute the p-th percentile of the packetised M/M/1 sojourn time,
    then add propagation.

    Packetised M/M/1 rates
    ----------------------
        lambda (packets/s) = arrival_rate_bps / packet_size_bits
        mu     (packets/s) = service_rate_bps / packet_size_bits
        rho                 = lambda / mu  =  arrival_rate_bps / service_rate_bps

    M/M/1 sojourn time W has the mixed CDF
        P(W = 0)   = 1 - rho           (arrives to empty system)
        P(W <= t)  = 1 - rho * exp( -(mu - lambda) * t )   for t > 0

    Inverting the tail:
        if percentile <= 1 - rho : queuing = 0      (no waiting)
        else                     : t = -ln((1-p) / rho) / (mu - lambda)
    where (mu - lambda) is in packets/second, giving t in seconds.

    Total delay = propagation + queuing.

    Parameters
    ----------
    arrival_rate_bps : float
        Aggregate offered load in bits/s for this class.
    service_rate_bps : float
        Effective service capacity (WFQ-weighted) in bits/s.
    propagation_ms : float
        One-way link propagation delay (ms) from scenario.
    percentile : float
        Target percentile. Default 0.95 (P95).
    packet_size_bits : float
        Packet size used to convert bps to packets/s. Default: a standard
        1500-byte Ethernet MTU (12 000 bits), appropriate for voice/video
        streams and large-packet telemetry. For small sensor packets,
        pass the telemetry packet size explicitly.

    Returns
    -------
    float
        Total P-th percentile one-way delay in milliseconds.
        Returns inf if the queue is overloaded (rho >= 1).
    """
    if service_rate_bps <= 0 or packet_size_bits <= 0:
        return float("inf")

    rho = arrival_rate_bps / service_rate_bps
    if rho >= 1.0:
        return float("inf")

    # Convert bps to packets/s
    lambda_pps = arrival_rate_bps / packet_size_bits
    mu_pps     = service_rate_bps / packet_size_bits
    mu_minus_lambda_pps = mu_pps - lambda_pps      # per second

    if percentile <= (1.0 - rho):
        # The percentile falls inside the zero-delay mass
        queuing_ms = 0.0
    else:
        tail_prob  = 1.0 - percentile              # e.g. 0.05 for P95
        queuing_s  = -math.log(tail_prob / rho) / mu_minus_lambda_pps
        queuing_ms = queuing_s * 1000.0

    return round(propagation_ms + queuing_ms, 3)


def evaluate_delay_kpis(
    scenario: dict,
    load_multiplier: float = 1.0,
) -> pd.DataFrame:
    """
    Evaluate P95 delay KPIs for telemetry and video at each base station.

    Modelling assumptions
    ----------------------
    * Each BS-to-CR-1 backhaul is 100 Mbps.
    * Scheduler: WFQ with strict priority for telemetry (DSCP EF).
    * Telemetry (SP): effective capacity = full link (100 Mbps).
    * Voice:          WFQ weight 0.30 → 30 Mbps effective capacity.
    * Video:          WFQ weight 0.40 → 40 Mbps effective capacity.
    * Arrival rate in bps = offered_load_erl * bitrate_bps (expected active * bps per session).
    * Telemetry arrival rate in bps = lambda_ps * packet_size_bits.
    * Total delay = M/M/1 queuing P95 + link propagation delay (from scenario YAML).

    Parameters
    ----------
    scenario : dict
        Loaded scenario YAML.
    load_multiplier : float
        Alpha multiplier for stress testing.

    Returns
    -------
    pd.DataFrame
        Columns: site, service_class, offered_load_erl, arrival_rate_mbps,
                 rho, p95_delay_ms, kpi_target_ms, kpi_met
    """
    traffic_cfg  = scenario["traffic"]
    qos_cfg      = scenario["qos"]
    sites        = _base_stations(scenario)
    link_cap_bps = 100e6  # 100 Mbps

    # WFQ effective service rates (bits/s)
    wfq = {
        "telemetry": link_cap_bps,          # strict priority → full link
        "voice":     0.30 * link_cap_bps,   # 30% weight
        "video":     0.40 * link_cap_bps,   # 40% weight
    }

    rows = []
    for site in sites:
        prop_ms = _site_prop_delay_ms(scenario, site)

        # --- Telemetry ---
        tel           = traffic_cfg["telemetry"]
        tel_pkt_bits  = tel["packet_size_bytes"] * 8
        lam_tel_ps    = tel["arrival_rate_per_hour"] * load_multiplier / 3600.0
        tel_arr_bps   = lam_tel_ps * tel_pkt_bits
        tel_rho       = tel_arr_bps / wfq["telemetry"]
        tel_p95       = _mm1_p95_delay_ms(
            tel_arr_bps, wfq["telemetry"], prop_ms,
            packet_size_bits=tel_pkt_bits,
        )

        rows.append({
            "site":               site,
            "service_class":      "telemetry",
            "offered_load_erl":   round(tel["offered_load_erl"] * load_multiplier, 4),
            "arrival_rate_mbps":  round(tel_arr_bps / 1e6, 6),
            "effective_cap_mbps": wfq["telemetry"] / 1e6,
            "rho":                round(tel_rho, 6),
            "p95_delay_ms":       tel_p95,
            "kpi_target_ms":      tel["kpi_delay_p95_ms"],
            "kpi_met":            tel_p95 <= tel["kpi_delay_p95_ms"],
        })

        # --- Video ---
        # Video stream is carried as standard 1500-byte Ethernet frames
        vid            = traffic_cfg["video"]
        vid_pkt_bits   = 1500 * 8
        A_vid          = vid["offered_load_erl"] * load_multiplier
        vid_arr_bps    = A_vid * vid["bitrate_mbps"] * 1e6
        vid_rho        = vid_arr_bps / wfq["video"]
        vid_p95        = _mm1_p95_delay_ms(
            vid_arr_bps, wfq["video"], prop_ms,
            packet_size_bits=vid_pkt_bits,
        )

        rows.append({
            "site":               site,
            "service_class":      "video",
            "offered_load_erl":   round(A_vid, 4),
            "arrival_rate_mbps":  round(vid_arr_bps / 1e6, 4),
            "effective_cap_mbps": wfq["video"] / 1e6,
            "rho":                round(vid_rho, 6),
            "p95_delay_ms":       vid_p95,
            "kpi_target_ms":      vid["kpi_delay_p95_ms"],
            "kpi_met":            vid_p95 <= vid["kpi_delay_p95_ms"],
        })

    return pd.DataFrame(rows)


# -----------------------------------------------------------------------
# Stress sweep (breaking point study)
# -----------------------------------------------------------------------

def _baseline_channel_count(scenario: dict) -> int:
    """
    Dimension channels for alpha=1.0 (baseline deployed capacity).
    This is the fixed capacity the network is built for.
    """
    A_base   = scenario["traffic"]["voice"]["offered_load_erl"]
    target_B = scenario["traffic"]["voice"]["kpi_blocking_prob"]
    return dimension_channels(A_base, target_B)


def stress_sweep(scenario: dict) -> pd.DataFrame:
    """
    Breaking point study: sweep load multipliers with FIXED baseline capacity.

    The baseline channel count N is dimensioned at alpha=1.0 (normal load).
    As alpha increases, the offered load grows but N stays fixed, so
    blocking probability rises. This reveals when each KPI first fails.

    Outputs a row per load multiplier with worst-case metrics across all sites.

    Returns
    -------
    pd.DataFrame
        Columns: load_multiplier, voice_offered_erl, voice_blocking,
                 voice_kpi_met, telemetry_p95_ms, telemetry_kpi_met,
                 video_p95_ms, video_kpi_met, all_kpis_met
    """
    N_baseline   = _baseline_channel_count(scenario)
    voice_target = scenario["traffic"]["voice"]["kpi_blocking_prob"]
    tel_target   = scenario["traffic"]["telemetry"]["kpi_delay_p95_ms"]
    vid_target   = scenario["traffic"]["video"]["kpi_delay_p95_ms"]

    rows = []
    for alpha in scenario["simulation"]["load_multiplier_steps"]:
        # Voice blocking at fixed N_baseline
        A_voice       = scenario["traffic"]["voice"]["offered_load_erl"] * alpha
        voice_block   = erlang_b(A_voice, N_baseline)
        voice_kpi_met = bool(voice_block <= voice_target)

        # Delay KPIs (worst site across all BSs)
        delay_df      = evaluate_delay_kpis(scenario, alpha)
        tel_df        = delay_df[delay_df["service_class"] == "telemetry"]
        vid_df        = delay_df[delay_df["service_class"] == "video"]
        worst_tel     = tel_df["p95_delay_ms"].max()
        worst_vid     = vid_df["p95_delay_ms"].max()
        tel_kpi_met   = bool(worst_tel <= tel_target)
        vid_kpi_met   = bool(worst_vid <= vid_target)

        rows.append({
            "load_multiplier":   alpha,
            "voice_offered_erl": round(A_voice, 4),
            "n_baseline":        N_baseline,
            "voice_blocking":    round(voice_block, 6),
            "voice_kpi_met":     voice_kpi_met,
            "telemetry_p95_ms":  worst_tel,
            "telemetry_kpi_met": tel_kpi_met,
            "video_p95_ms":      worst_vid,
            "video_kpi_met":     vid_kpi_met,
            "all_kpis_met":      voice_kpi_met and tel_kpi_met and vid_kpi_met,
        })

    return pd.DataFrame(rows)


def find_breaking_point(scenario: dict) -> dict:
    """
    Identify which KPI fails first and at what load multiplier.

    Scans the stress sweep results and returns a structured summary
    suitable for the report's breaking point section (Section 11.1).

    Returns
    -------
    dict with keys:
        first_failure_alpha       - load multiplier at which first KPI fails
        first_failure_kpi         - which KPI failed first
        first_failure_value       - value of the failing metric
        first_failure_target      - its target
        n_baseline                - baseline circuit count used
        bottleneck_description    - plain-text summary for the report
    """
    sweep = stress_sweep(scenario)

    # Find first alpha where all_kpis_met is False
    failures = sweep[~sweep["all_kpis_met"]]
    if failures.empty:
        return {"bottleneck_description": "No KPI failure in the tested load range."}

    first_fail = failures.iloc[0]
    alpha      = first_fail["load_multiplier"]

    # Determine which KPI caused the failure
    kpi_name  = "unknown"
    kpi_value = None
    kpi_target = None

    if not first_fail["voice_kpi_met"]:
        kpi_name   = "voice_blocking_probability"
        kpi_value  = first_fail["voice_blocking"]
        kpi_target = scenario["traffic"]["voice"]["kpi_blocking_prob"]
    elif not first_fail["video_kpi_met"]:
        kpi_name   = "video_p95_delay_ms"
        kpi_value  = first_fail["video_p95_ms"]
        kpi_target = scenario["traffic"]["video"]["kpi_delay_p95_ms"]
    elif not first_fail["telemetry_kpi_met"]:
        kpi_name   = "telemetry_p95_delay_ms"
        kpi_value  = first_fail["telemetry_p95_ms"]
        kpi_target = scenario["traffic"]["telemetry"]["kpi_delay_p95_ms"]

    desc = (
        f"First KPI failure at load multiplier alpha={alpha:.1f}. "
        f"KPI '{kpi_name}' exceeded its target "
        f"(value={kpi_value:.4f}, target={kpi_target}). "
        f"Baseline channel count was N={first_fail['n_baseline']} per site. "
        f"Voice offered load at failure: {first_fail['voice_offered_erl']:.2f} Erlang."
    )

    return {
        "first_failure_alpha":    alpha,
        "first_failure_kpi":      kpi_name,
        "first_failure_value":    kpi_value,
        "first_failure_target":   kpi_target,
        "n_baseline":             int(first_fail["n_baseline"]),
        "bottleneck_description": desc,
    }


# -----------------------------------------------------------------------
# Erlang B curves for a range of offered loads (report figure data)
# -----------------------------------------------------------------------

def erlang_curves_for_report(scenario: dict) -> pd.DataFrame:
    """
    Generate Erlang B blocking probability curves for each service class
    at normal load (alpha=1.0), varying N from 1 to 20 circuits.

    Returns a long-format DataFrame suitable for matplotlib/plotly.

    Returns
    -------
    pd.DataFrame
        Columns: service_class, offered_load_erl, circuits_N, blocking_prob
    """
    traffic_cfg = scenario["traffic"]
    rows = []

    for svc, cfg in [
        ("telemetry", traffic_cfg["telemetry"]),
        ("voice",     traffic_cfg["voice"]),
        ("video",     traffic_cfg["video"]),
    ]:
        A = cfg["offered_load_erl"]
        for N in range(0, 21):
            rows.append({
                "service_class":    svc,
                "offered_load_erl": A,
                "circuits_N":       N,
                "blocking_prob":    erlang_b(A, N),
            })

    return pd.DataFrame(rows)


# -----------------------------------------------------------------------
# Dashboard entry point
# -----------------------------------------------------------------------

def run_teletraffic(
    scenario: dict,
    load_multiplier: float = 1.0,
) -> dict:
    """
    Run full teletraffic analysis for the Streamlit dashboard.

    Parameters
    ----------
    scenario : dict
        Loaded scenario YAML.
    load_multiplier : float
        Current load multiplier selected in the dashboard slider.

    Returns
    -------
    dict with keys:
        dimensioning_table : pd.DataFrame  - per-site + trunk voice dimensioning
        delay_kpis         : pd.DataFrame  - P95 delay results for tel and video
        trunk              : dict          - backhaul trunk summary
        stress_sweep       : pd.DataFrame  - full sweep (computed once at alpha=1 call)
        breaking_point     : dict          - first KPI failure analysis
        erlang_curves      : pd.DataFrame  - Erlang B curves for plotting
    """
    return {
        "dimensioning_table": full_dimensioning_table(scenario, load_multiplier),
        "delay_kpis":         evaluate_delay_kpis(scenario, load_multiplier),
        "trunk":              dimension_backhaul_trunk(scenario, load_multiplier),
        "stress_sweep":       stress_sweep(scenario),
        "breaking_point":     find_breaking_point(scenario),
        "erlang_curves":      erlang_curves_for_report(scenario),
    }


# -----------------------------------------------------------------------
# Signaling Load Model
# -----------------------------------------------------------------------

def compute_signaling_load(
    scenario: dict,
    load_multiplier: float = 1.0,
) -> pd.DataFrame:
    """
    Simplified signaling model for call setup delay and signaling load.

    Model assumptions (ITU-T Q.543 / simplified BHCA approach)
    -----------------------------------------------------------
    * Each call (voice or video) generates exactly 2 signaling messages:
      one SETUP and one RELEASE (minimum signaling exchange).
    * Telemetry uses no call signaling (connectionless sensor packets).
    * Signaling message size: 100 bytes (SIP INVITE / BYE simplified).
    * Call setup delay = one-way propagation + processing time.
      Processing time is modelled as a fixed 5 ms per message (typical
      SIP proxy on embedded hardware).
    * BHCA (Busy-Hour Call Attempts) = arrival_rate_per_hour per site.

    Outputs per site
    ----------------
    bhca              : Busy-Hour Call Attempts (voice + video combined)
    signaling_msgs_ph : Signaling messages per hour (2 per call attempt)
    signaling_load_bps: Aggregate signaling bandwidth in bps
    call_setup_delay_ms: One-way call setup delay (propagation + processing)
    kpi_delay_ms      : Target from scenario telemetry KPI (50 ms) used as
                        proxy — signaling must complete within 50 ms.
    kpi_met           : Whether call setup delay is within target.

    Returns
    -------
    pd.DataFrame
        Columns: site, bhca, signaling_msgs_ph, signaling_load_bps,
                 call_setup_delay_ms, kpi_target_ms, kpi_met
    """
    traffic_cfg  = scenario["traffic"]
    sites        = _base_stations(scenario)

    SIG_MSG_BYTES   = 100          # bytes per signaling message
    SIG_MSGS_PCALL  = 2            # SETUP + RELEASE
    PROC_DELAY_MS   = 5.0          # signaling processing time at CR-1 (ms)

    # Use the telemetry P95 delay as the signaling KPI proxy (tightest delay class)
    kpi_ms = traffic_cfg["telemetry"]["kpi_delay_p95_ms"]

    rows = []
    for site in sites:
        prop_ms = _site_prop_delay_ms(scenario, site)

        # BHCA: voice + video call attempts (telemetry is connectionless)
        voice_arr = traffic_cfg["voice"]["arrival_rate_per_hour"] * load_multiplier
        video_arr = traffic_cfg["video"]["arrival_rate_per_hour"] * load_multiplier
        bhca      = voice_arr + video_arr

        # Signaling message rate
        sig_msgs_ph  = bhca * SIG_MSGS_PCALL
        sig_msgs_ps  = sig_msgs_ph / 3600.0
        sig_load_bps = sig_msgs_ps * SIG_MSG_BYTES * 8  # bits/s

        # Call setup delay = propagation (one-way to CR-1) + processing
        setup_delay_ms = prop_ms + PROC_DELAY_MS

        rows.append({
            "site":                  site,
            "bhca":                  round(bhca, 2),
            "signaling_msgs_ph":     round(sig_msgs_ph, 1),
            "signaling_load_bps":    round(sig_load_bps, 4),
            "call_setup_delay_ms":   round(setup_delay_ms, 2),
            "kpi_target_ms":         kpi_ms,
            "kpi_met":               setup_delay_ms <= kpi_ms,
        })

    return pd.DataFrame(rows)


def signaling_summary(scenario: dict, load_multiplier: float = 1.0) -> dict:
    """
    Aggregate signaling load across all sites and report worst-case delay.

    Returns
    -------
    dict with keys:
        total_bhca, total_signaling_bps, worst_setup_delay_ms,
        worst_setup_site, all_kpis_met
    """
    df = compute_signaling_load(scenario, load_multiplier)
    return {
        "total_bhca":             round(df["bhca"].sum(), 2),
        "total_signaling_bps":    round(df["signaling_load_bps"].sum(), 4),
        "worst_setup_delay_ms":   df["call_setup_delay_ms"].max(),
        "worst_setup_site":       df.loc[df["call_setup_delay_ms"].idxmax(), "site"],
        "all_kpis_met":           bool(df["kpi_met"].all()),
    }


# -----------------------------------------------------------------------
# Standalone demo
# -----------------------------------------------------------------------

if __name__ == "__main__":
    import os

    scenario_path = os.path.join(os.path.dirname(__file__), "..", "scenario.yaml")
    sc = load_scenario(scenario_path)

    print("=" * 65)
    print("VOICE DIMENSIONING TABLE (alpha = 1.0)")
    print("=" * 65)
    print(full_dimensioning_table(sc).to_string(index=False))

    print("\n" + "=" * 65)
    print("BACKHAUL TRUNK SUMMARY")
    print("=" * 65)
    trunk = dimension_backhaul_trunk(sc)
    for k, v in trunk.items():
        print(f"  {k:30s}: {v}")

    print("\n" + "=" * 65)
    print("DELAY KPIs (alpha = 1.0)")
    print("=" * 65)
    print(evaluate_delay_kpis(sc).to_string(index=False))

    print("\n" + "=" * 65)
    print("BREAKING POINT STRESS SWEEP")
    print("=" * 65)
    sweep = stress_sweep(sc)
    print(sweep.to_string(index=False))

    print("\n" + "=" * 65)
    print("BREAKING POINT ANALYSIS")
    print("=" * 65)
    bp = find_breaking_point(sc)
    for k, v in bp.items():
        print(f"  {k:30s}: {v}")

    print("\n" + "=" * 65)
    print("ERLANG B  -  voice at A=0.75 Erl")
    print("=" * 65)
    curve = erlang_b_curve(0.75, N_max=10)
    print(curve.to_string(index=False))

    # ------------------------------------------------------------------
    # CSV export
    # ------------------------------------------------------------------
    out_dir = os.path.join(os.path.dirname(__file__), "..", "outputs")
    os.makedirs(out_dir, exist_ok=True)

    full_dimensioning_table(sc).to_csv(
        os.path.join(out_dir, "teletraffic_dimensioning_table.csv"), index=False
    )
    evaluate_delay_kpis(sc).to_csv(
        os.path.join(out_dir, "teletraffic_delay_kpis.csv"), index=False
    )
    stress_sweep(sc).to_csv(
        os.path.join(out_dir, "teletraffic_stress_sweep.csv"), index=False
    )
    erlang_curves_for_report(sc).to_csv(
        os.path.join(out_dir, "teletraffic_erlang_curves.csv"), index=False
    )
    compute_signaling_load(sc).to_csv(
        os.path.join(out_dir, "teletraffic_signaling_load.csv"), index=False
    )
    pd.DataFrame([dimension_backhaul_trunk(sc)]).to_csv(
        os.path.join(out_dir, "teletraffic_trunk_summary.csv"), index=False
    )

    print("\nCSV files saved to outputs/:")
    for name in [
        "teletraffic_dimensioning_table.csv",
        "teletraffic_delay_kpis.csv",
        "teletraffic_stress_sweep.csv",
        "teletraffic_erlang_curves.csv",
        "teletraffic_signaling_load.csv",
        "teletraffic_trunk_summary.csv",
    ]:
        print(f"  {name}")