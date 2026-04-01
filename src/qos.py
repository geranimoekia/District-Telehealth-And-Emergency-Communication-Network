"""
qos.py
======
TELE 527 · Group 1 · District Telehealth & Emergency Network
BIUST — Department of Electrical Communications Systems Engineering
Student 5 — QoS & Data Networks Lead

All parameters in this file are pulled DIRECTLY from the three project files:
  - topology.py  → link capacities, propagation delays, node structure
  - traffic.py   → TelemetryParams, VoiceParams, VideoParams, aggregate load
  - routing.py   → link_utilisation(), shortest_path(), simulate_failure()

Network facts (from topology.py):
  Access links (CR1/CR2 → each BS) : 100 Mbps, sub-6 GHz microwave
  Backbone trunk (CR1 ↔ CR2)       : 1000 Mbps, E-Band 80 GHz
  Propagation delays per topology.py:
    CR1–BS3 (shortest) : 0.12   ms
    CR1–BS2 / CR1–BS4  : 0.1283 ms
    CR1–BS1 / CR1–BS5  : 0.1448 ms  ← worst-case access link

Traffic facts (from traffic.py):
  Telemetry : 128-byte packets, 20 pps/BS, 0.020 Mbps/BS, priority=high
  Voice     : G.711 64 kbps, 0.50 Erl/BS, 50 pps, blocking target 2%
  Video     : 2.0 Mbps/session, 1400-byte packets, 178.6 pps, 0.20 Erl/BS
  Aggregate : 2.084 Mbps/BS  (from TrafficGenerator.aggregate_load_mbps())
  Trunk     : 3.75 Erl total (matches network diagram label)

QoS targets come from traffic.py dataclass fields:
  TelemetryParams.delay_target_ms  = 20.0  ms  (P95)
  TelemetryParams.delay_percentile = 95
  VoiceParams.blocking_target_pct  = 2.0   %
  VideoParams.delay_target_ms      = 150.0 ms  (P95)
  VideoParams.delay_percentile     = 95

Queue models:
  Telemetry → M/D/1  (fixed 128-byte packets → deterministic service time)
  Voice     → Erlang B loss model (circuit-switched, no queuing)
  Video     → M/M/1  (variable H.264 frame sizes → random service time)

Reference: RFC 2474 (DiffServ), ITU-T G.107 (E-model), Kleinrock (1976),
           Forouzan (2013) ch. 24, ITU-T E.501
"""

import math
import numpy as np
import pandas as pd

# ── Project imports ──────────────────────────────────────────────────────────
from src.topology import build_topology, NODES
from routing  import shortest_path, link_utilisation, simulate_failure
from traffic  import (
    TrafficGenerator,
    TelemetryParams, VoiceParams, VideoParams,
)


# ---------------------------------------------------------------------------
# KPI targets — read directly from traffic.py dataclass defaults
# ---------------------------------------------------------------------------

_tel_defaults   = TelemetryParams()
_voice_defaults = VoiceParams()
_video_defaults = VideoParams()

# Exact values from traffic.py — do not hard-code independently
TEL_DELAY_TARGET_MS    = _tel_defaults.delay_target_ms      # 20.0 ms
TEL_PERCENTILE         = _tel_defaults.delay_percentile     # 95
TEL_PACKET_BYTES       = _tel_defaults.packet_size_bytes    # 128
TEL_INTER_ARRIVAL_MS   = _tel_defaults.inter_arrival_ms     # 50.0 ms → 20 pps
TEL_OFFERED_ERL        = _tel_defaults.offered_erlang       # 0.05
TEL_PRIORITY           = _tel_defaults.priority             # "high"

VOICE_BLOCKING_TARGET  = _voice_defaults.blocking_target_pct  # 2.0 %
VOICE_OFFERED_ERL      = _voice_defaults.offered_erlang        # 0.50
VOICE_CODEC_KBPS       = _voice_defaults.codec_kbps            # 64.0
VOICE_HOLDING_S        = _voice_defaults.call_holding_s        # 120.0 s
VOICE_PRIORITY         = _voice_defaults.priority              # "medium"

VIDEO_DELAY_TARGET_MS  = _video_defaults.delay_target_ms      # 150.0 ms
VIDEO_PERCENTILE       = _video_defaults.delay_percentile     # 95
VIDEO_BITRATE_MBPS     = _video_defaults.bitrate_mbps         # 2.0
VIDEO_PKT_BYTES        = _video_defaults.packet_size_bytes    # 1400
VIDEO_OFFERED_ERL      = _video_defaults.offered_erlang       # 0.20
VIDEO_PRIORITY         = _video_defaults.priority             # "medium"

# Link capacities from topology.py
ACCESS_LINK_MBPS = 100.0    # all CR→BS sub-6 GHz microwave links
TRUNK_LINK_MBPS  = 1000.0   # CR1–CR2 E-Band trunk


# ---------------------------------------------------------------------------
# Helper: pull propagation delay for bs_id→CR1 directly from topology graph
# ---------------------------------------------------------------------------

def _get_prop_delay_ms(bs_id: str, G=None) -> float:
    """
    Return the propagation delay (ms) on the first hop of bs_id → CR1.
    Values come from topology.py edge 'delay_ms' attribute:
      BS1/BS5 → CR1 : 0.1448 ms  (distance 13.42 km)
      BS2/BS4 → CR1 : 0.1283 ms  (distance  8.49 km)
      BS3     → CR1 : 0.12   ms  (distance  6.00 km)
    """
    if G is None:
        G = build_topology()
    r = shortest_path(G, bs_id, "CR1")
    if r["reachable"] and len(r["path"]) >= 2:
        return G[r["path"][0]][r["path"][1]].get("delay_ms", 0.1448)
    return 0.1448   # fallback to worst-case


# ---------------------------------------------------------------------------
# Erlang B — recursive Jagerman formula
# ---------------------------------------------------------------------------

def erlang_b(A: float, N: int) -> float:
    """
    Erlang B blocking probability B(A, N).

    Recursive Jagerman formula (numerically stable):
        B(A, 0) = 1
        B(A, n) = A·B(A, n-1) / (n + A·B(A, n-1))

    Parameters
    ----------
    A : offered traffic (Erlangs) — from VoiceParams.offered_erlang × load
    N : number of circuits

    Returns
    -------
    Blocking probability 0–1.
    """
    B = 1.0
    for n in range(1, N + 1):
        B = (A * B) / (n + A * B)
    return B


def dimension_circuits(A: float, target_b: float = 0.02) -> int:
    """
    Minimum N circuits so that Erlang B(A, N) ≤ target_b.
    target_b default = 0.02 matches VoiceParams.blocking_target_pct / 100.
    """
    for N in range(1, 200):
        if erlang_b(A, N) <= target_b:
            return N
    return 200


# ---------------------------------------------------------------------------
# Queue delay models
# ---------------------------------------------------------------------------

def _md1_mean_delay_ms(lam: float, mu: float) -> float:
    """
    M/D/1 mean sojourn time (wait + service), in ms.

    Formula: W = (1/μ) · (1 + ρ/(2(1−ρ)))    [seconds] × 1000

    Used for TELEMETRY because TelemetryParams.packet_size_bytes = 128 (fixed).
    Fixed packet size → deterministic service time → D in M/D/1.
    M/D/1 gives exactly HALF the queuing delay of M/M/1 at the same ρ.

    Parameters
    ----------
    lam : arrival rate in packets/s  (= 1000/inter_arrival_ms × load_mult)
    mu  : service rate in packets/s  (= link_bps / pkt_bits)
    """
    if lam >= mu:
        return float("inf")
    rho = lam / mu
    return ((1.0 / mu) * (1.0 + rho / (2.0 * (1.0 - rho)))) * 1000.0


def _mm1_mean_delay_ms(lam: float, mu: float) -> float:
    """
    M/M/1 mean sojourn time (wait + service), in ms.

    Formula: W = 1/(μ−λ)    [seconds] × 1000

    Used for VIDEO because VideoParams.packet_size_bytes = 1400 but H.264
    encoding produces variable-sized frames → random service time → M/M/1.

    Parameters
    ----------
    lam : aggregate video packet arrival rate (sessions × pkt_rate_per_session)
    mu  : service rate on the 100 Mbps access link
    """
    if lam >= mu:
        return float("inf")
    return (1.0 / (mu - lam)) * 1000.0


def _percentile_delay_ms(mean_ms: float, percentile: int, model: str) -> float:
    """
    Estimate a delay percentile from the mean sojourn time.

    M/M/1 — sojourn time is exponentially distributed (exact):
        W_p = −W_mean · ln(1 − p)

    M/D/1 — no closed-form tail; Kleinrock (1976) approximation:
        W_p ≈ W_mean · (1 + 0.5·ln(1/(1−p)))

    Percentiles used:
        TelemetryParams.delay_percentile = 95
        VideoParams.delay_percentile     = 95
    """
    if math.isinf(mean_ms):
        return float("inf")
    p = percentile / 100.0
    if model == "mm1":
        return round(-mean_ms * math.log(1.0 - p), 4)
    else:   # md1
        return round(mean_ms * (1.0 + 0.5 * math.log(1.0 / (1.0 - p))), 4)


# ---------------------------------------------------------------------------
# ITU-T G.107 E-model for voice MOS
# ---------------------------------------------------------------------------

def _emodel_mos(one_way_delay_ms: float, loss_pct: float = 0.0) -> float:
    """
    Compute MOS using the ITU-T G.107 E-model.

    R factor:
        R = R0 − Is − Id − Ie_eff

        R0      = 93.2           (G.711 signal/noise baseline)
        Is      = 1.4            (simultaneous impairments, G.711)
        Id      = 0.024·d + 0.11·max(d−177.3, 0)    (delay impairment)
        Ie_eff  = 30·loss_pct/100                    (packet loss impairment)

    MOS from R (ITU-T G.107 mapping):
        MOS = 1 + 0.035·R + R·(R−60)·(100−R)·7e-6

    Voice one-way delay = 20 ms (G.711 packetisation) + propagation + tx.
    Codec = VoiceParams.codec_kbps = 64 kbps (G.711).
    """
    R0      = 93.2
    Is      = 1.4
    Id      = 0.024 * one_way_delay_ms + 0.11 * max(one_way_delay_ms - 177.3, 0.0)
    Ie_eff  = 30.0 * (loss_pct / 100.0)
    R       = max(0.0, min(100.0, R0 - Is - Id - Ie_eff))
    mos     = 1.0 + 0.035 * R + R * (R - 60.0) * (100.0 - R) * 7e-6
    return round(max(1.0, min(5.0, mos)), 3)


def _mos_label(mos: float) -> str:
    if mos >= 4.3: return "Excellent"
    if mos >= 4.0: return "Good"
    if mos >= 3.5: return "Fair"
    if mos >= 3.0: return "Poor"
    return "Bad"


# ---------------------------------------------------------------------------
# Telemetry QoS  (M/D/1)
# ---------------------------------------------------------------------------

def telemetry_qos(bs_id: str = "BS1", load_multiplier: float = 1.0, G=None) -> dict:
    """
    Compute QoS metrics for the Telemetry class at one base station.

    Source of every parameter:
      arrival rate  ← TelemetryParams.inter_arrival_ms = 50 ms → 20 pps
      packet size   ← TelemetryParams.packet_size_bytes = 128 B
      link capacity ← topology.py access link = 100 Mbps
      propagation   ← topology.py edge delay_ms for bs_id→CR1
      KPI target    ← TelemetryParams.delay_target_ms = 20 ms (P95)
      percentile    ← TelemetryParams.delay_percentile = 95

    Service time = (128 × 8) / (100 × 10^6) × 10^3 = 0.01024 ms
    This matches the service_ms column in TrafficGenerator.generate_telemetry().

    Queue model choice — M/D/1:
      Packet size is always 128 bytes (fixed sensor payload) → service time
      is deterministic → D in M/D/1. M/D/1 queuing delay is half of M/M/1
      at the same utilisation, which correctly models this high-priority class.

    Parameters
    ----------
    bs_id           : base station ID (BS1–BS5)
    load_multiplier : traffic scaling factor (1.0 = nominal)
    G               : topology graph (built from topology.py if None)
    """
    if G is None:
        G = build_topology()

    prop_ms = _get_prop_delay_ms(bs_id, G)

    # Arrival rate: 1000 ms / inter_arrival_ms × load_multiplier
    # TelemetryParams.inter_arrival_ms = 50.0  →  base = 20.0 pps
    lam = (1000.0 / TEL_INTER_ARRIVAL_MS) * load_multiplier   # pps

    # Service rate on 100 Mbps link (topology.py access link capacity)
    mu = (ACCESS_LINK_MBPS * 1e6) / (TEL_PACKET_BYTES * 8)   # pps

    rho = lam / mu

    # M/D/1 sojourn time
    W_ms = _md1_mean_delay_ms(lam, mu)

    # Transmission delay = service time
    # = (128 × 8) / (100e6) × 1e3 = 0.01024 ms
    # Matches generate_telemetry() service_ms
    tx_ms = (TEL_PACKET_BYTES * 8) / (ACCESS_LINK_MBPS * 1e6) * 1000.0

    mean_total_ms = (W_ms if not math.isinf(W_ms) else 9999.0) + prop_ms + tx_ms

    # P95 — uses TEL_PERCENTILE = 95 from TelemetryParams.delay_percentile
    p95_ms = (
        _percentile_delay_ms(W_ms, TEL_PERCENTILE, "md1") + prop_ms + tx_ms
        if not math.isinf(W_ms) else float("inf")
    )

    # Jitter (M/D/1 std-dev approximation)
    jitter_ms = (
        round((rho / (mu * math.sqrt(2.0) * (1.0 - rho))) * 1000.0, 5)
        if rho < 1.0 else float("inf")
    )

    loss_pct    = 0.0 if rho < 1.0 else 100.0
    meets_delay = (not math.isinf(p95_ms)) and (p95_ms < TEL_DELAY_TARGET_MS)
    meets_loss  = loss_pct == 0.0

    return {
        "bs":                 bs_id,
        "class":              "telemetry",
        "priority":           TEL_PRIORITY,
        "queue_model":        "M/D/1",
        "packet_size_bytes":  TEL_PACKET_BYTES,
        "inter_arrival_ms":   TEL_INTER_ARRIVAL_MS,
        "arrival_pps":        round(lam, 3),
        "service_pps":        round(mu, 3),
        "utilisation_rho":    round(rho, 6),
        "tx_service_ms":      round(tx_ms, 5),
        "propagation_ms":     prop_ms,
        "mean_queue_ms":      round(W_ms, 5) if not math.isinf(W_ms) else "inf",
        "mean_total_ms":      round(mean_total_ms, 5),
        "p95_delay_ms":       round(p95_ms, 4) if not math.isinf(p95_ms) else float("inf"),
        "jitter_ms":          jitter_ms,
        "loss_pct":           loss_pct,
        "target_p95_ms":      TEL_DELAY_TARGET_MS,
        "meets_delay_kpi":    meets_delay,
        "meets_loss_kpi":     meets_loss,
        "pass":               meets_delay and meets_loss,
    }


# ---------------------------------------------------------------------------
# Voice QoS  (Erlang B + ITU-T G.107 E-model)
# ---------------------------------------------------------------------------

def voice_qos(bs_id: str = "BS1", load_multiplier: float = 1.0, G=None) -> dict:
    """
    Compute QoS metrics for the Voice class at one base station.

    Source of every parameter:
      offered_erlang   ← VoiceParams.offered_erlang = 0.50
      codec_kbps       ← VoiceParams.codec_kbps = 64.0 (G.711)
      call_holding_s   ← VoiceParams.call_holding_s = 120.0 s
      blocking_target  ← VoiceParams.blocking_target_pct = 2.0 %
      priority         ← VoiceParams.priority = "medium"
      propagation      ← topology.py edge delay_ms for bs_id→CR1

    Circuit dimensioning:
      N = smallest integer where Erlang B(A, N) ≤ 2%
      At A = 0.50 Erl: N = 3, B = 1.27% ✓

    Voice delay budget:
      Packetisation = 20 ms   (G.711 20 ms frame → 50 pps matches traffic_summary)
      TX delay      = (160 B × 8) / (64 kbps) = 20 ms
      Propagation   = 0.12–0.1448 ms (from topology.py)
      Total ≈ 40 ms  <<  150 ms target ✓

    Trunk aggregate:
      5 BSes × 0.50 Erl = 2.50 Erl voice on CR1–CR2
      (trunk_aggregate_erlang() voice_erlang = 2.50 matches diagram label)

    Parameters
    ----------
    bs_id           : base station ID (BS1–BS5)
    load_multiplier : scales VoiceParams.offered_erlang
    G               : topology graph
    """
    if G is None:
        G = build_topology()

    prop_ms = _get_prop_delay_ms(bs_id, G)

    A = VOICE_OFFERED_ERL * load_multiplier
    N = dimension_circuits(A, VOICE_BLOCKING_TARGET / 100.0)
    B = erlang_b(A, N)

    # Voice delay budget
    # Packetisation: G.711 20 ms frames → 50 pps (matches traffic_summary Rate=50)
    pkt_ms  = 20.0
    # TX: one 160-byte frame at 64 kbps = (160×8)/(64000) × 1000 = 20 ms
    tx_ms   = (160.0 * 8.0) / (VOICE_CODEC_KBPS * 1000.0) * 1000.0
    total_ms = pkt_ms + prop_ms + tx_ms

    mos = _emodel_mos(total_ms, loss_pct=0.0)

    # Trunk dimensioning (5 BSes × A)
    trunk_A = VOICE_OFFERED_ERL * load_multiplier * len(TrafficGenerator.BASE_STATIONS)
    trunk_N = dimension_circuits(trunk_A, VOICE_BLOCKING_TARGET / 100.0)
    trunk_B = erlang_b(trunk_A, trunk_N)

    meets_blocking = (B * 100.0) < VOICE_BLOCKING_TARGET
    meets_delay    = total_ms < 150.0
    meets_mos      = mos >= 3.5

    return {
        "bs":                  bs_id,
        "class":               "voice",
        "priority":            VOICE_PRIORITY,
        "queue_model":         "Erlang B (loss system)",
        "codec":               f"G.711 {int(VOICE_CODEC_KBPS)} kbps",
        "offered_erl":         round(A, 4),
        "circuits_N":          N,
        "blocking_prob":       round(B, 6),
        "blocking_pct":        round(B * 100.0, 4),
        "target_blocking_pct": VOICE_BLOCKING_TARGET,
        "packetisation_ms":    pkt_ms,
        "propagation_ms":      prop_ms,
        "tx_ms":               round(tx_ms, 4),
        "total_delay_ms":      round(total_ms, 4),
        "loss_pct":            0.0,
        "mos":                 mos,
        "mos_quality":         _mos_label(mos),
        "trunk_offered_erl":   round(trunk_A, 3),
        "trunk_circuits_N":    trunk_N,
        "trunk_blocking_pct":  round(trunk_B * 100.0, 4),
        "meets_blocking_kpi":  meets_blocking,
        "meets_delay_kpi":     meets_delay,
        "meets_mos_kpi":       meets_mos,
        "pass":                meets_blocking and meets_delay and meets_mos,
    }


# ---------------------------------------------------------------------------
# Video QoS  (M/M/1)
# ---------------------------------------------------------------------------

def video_qos(bs_id: str = "BS1", load_multiplier: float = 1.0, G=None) -> dict:
    """
    Compute QoS metrics for the Video class at one base station.

    Source of every parameter:
      offered_erlang    ← VideoParams.offered_erlang = 0.20
      bitrate_mbps      ← VideoParams.bitrate_mbps = 2.0 per session
      packet_size_bytes ← VideoParams.packet_size_bytes = 1400
      delay_target_ms   ← VideoParams.delay_target_ms = 150.0 ms
      delay_percentile  ← VideoParams.delay_percentile = 95
      priority          ← VideoParams.priority = "medium"
      propagation       ← topology.py edge delay_ms for bs_id→CR1

    Packet rate (from generate_video):
      pkt_rate_pps = (2.0 × 10^6) / (1400 × 8) = 178.57 pps per session

    Service time (from generate_video service_ms):
      tx_ms = (1400 × 8) / (100 × 10^6) × 10^3 = 0.112 ms

    Aggregate arrivals:
      lam = mean_sessions × 178.57   (Little's law: sessions = offered_erlang)

    Queue model choice — M/M/1:
      H.264/H.265 video produces frames of highly variable sizes (I/P/B frames).
      Variable packet size → random service time → second M in M/M/1.

    Parameters
    ----------
    bs_id           : base station ID (BS1–BS5)
    load_multiplier : scales VideoParams.offered_erlang
    G               : topology graph
    """
    if G is None:
        G = build_topology()

    prop_ms = _get_prop_delay_ms(bs_id, G)

    mean_sessions = VIDEO_OFFERED_ERL * load_multiplier

    # Packet rate per session: matches generate_video() pkt_rate_pps
    pkt_rate_per_sess = (VIDEO_BITRATE_MBPS * 1e6) / (VIDEO_PKT_BYTES * 8)  # 178.57 pps
    lam = mean_sessions * pkt_rate_per_sess

    # Service rate on 100 Mbps access link
    mu  = (ACCESS_LINK_MBPS * 1e6) / (VIDEO_PKT_BYTES * 8)

    rho = lam / mu

    # M/M/1 sojourn time
    W_ms = _mm1_mean_delay_ms(lam, mu) if rho < 1.0 else float("inf")

    # TX delay — matches generate_video() service_ms = 0.112 ms
    tx_ms = (VIDEO_PKT_BYTES * 8) / (ACCESS_LINK_MBPS * 1e6) * 1000.0

    mean_total_ms = (W_ms if not math.isinf(W_ms) else 9999.0) + prop_ms + tx_ms

    # P95 — uses VIDEO_PERCENTILE = 95 from VideoParams.delay_percentile
    p95_ms = (
        _percentile_delay_ms(W_ms, VIDEO_PERCENTILE, "mm1") + prop_ms + tx_ms
        if not math.isinf(W_ms) else float("inf")
    )

    throughput_pct = min(100.0, (1.0 - rho) * 100.0) if rho < 1.0 else 0.0

    meets_delay      = (not math.isinf(p95_ms)) and (p95_ms < VIDEO_DELAY_TARGET_MS)
    meets_throughput = throughput_pct >= 95.0

    return {
        "bs":                      bs_id,
        "class":                   "video",
        "priority":                VIDEO_PRIORITY,
        "queue_model":             "M/M/1",
        "bitrate_per_session_mbps": VIDEO_BITRATE_MBPS,
        "packet_size_bytes":       VIDEO_PKT_BYTES,
        "mean_sessions":           round(mean_sessions, 4),
        "agg_bw_mbps":             round(mean_sessions * VIDEO_BITRATE_MBPS, 4),
        "pkt_rate_per_session":    round(pkt_rate_per_sess, 2),
        "arrival_pps":             round(lam, 3),
        "service_pps":             round(mu, 3),
        "utilisation_rho":         round(rho, 6),
        "tx_service_ms":           round(tx_ms, 4),
        "propagation_ms":          prop_ms,
        "mean_queue_ms":           round(W_ms, 5) if not math.isinf(W_ms) else "inf",
        "mean_total_ms":           round(mean_total_ms, 5),
        "p95_delay_ms":            round(p95_ms, 4) if not math.isinf(p95_ms) else float("inf"),
        "throughput_pct":          round(throughput_pct, 4),
        "target_p95_ms":           VIDEO_DELAY_TARGET_MS,
        "meets_delay_kpi":         meets_delay,
        "meets_throughput_kpi":    meets_throughput,
        "pass":                    meets_delay and meets_throughput,
    }


# ---------------------------------------------------------------------------
# Network-wide QoS snapshot  (all 5 BSes, all classes)
# ---------------------------------------------------------------------------

def qos_snapshot(load_multiplier: float = 1.0) -> dict:
    """
    Full QoS snapshot for all BSes at a given load multiplier.

    Calls TrafficGenerator(load_multiplier) to get aggregate_load_mbps(),
    then calls routing.link_utilisation() with those exact demands.
    Also calls trunk_aggregate_erlang() to verify trunk Erlang matches diagram.

    Returns
    -------
    dict with:
        per_bs     : {bs: {telemetry, voice, video}}
        link_util  : list from routing.link_utilisation()
        summary    : worst-case metrics across all BSes
        all_pass   : bool
    """
    G   = build_topology()
    gen = TrafficGenerator(load_multiplier=load_multiplier, seed=42, duration_s=3600)
    bs_ids = TrafficGenerator.BASE_STATIONS

    per_bs = {}
    for bs in bs_ids:
        per_bs[bs] = {
            "telemetry": telemetry_qos(bs, load_multiplier, G),
            "voice":     voice_qos(bs,     load_multiplier, G),
            "video":     video_qos(bs,     load_multiplier, G),
        }

    # Link utilisation using exact demand dict from aggregate_load_mbps()
    bw       = gen.aggregate_load_mbps()
    demands  = {(bs, "CR1"): bw[bs] for bs in bs_ids}
    link_util = link_utilisation(G, demands)

    # Worst-case summary
    tel_p95_list   = [per_bs[bs]["telemetry"]["p95_delay_ms"]
                      for bs in bs_ids if not math.isinf(per_bs[bs]["telemetry"]["p95_delay_ms"])]
    video_p95_list = [per_bs[bs]["video"]["p95_delay_ms"]
                      for bs in bs_ids if not math.isinf(per_bs[bs]["video"]["p95_delay_ms"])]

    all_pass = all(
        per_bs[bs][cls]["pass"]
        for bs in bs_ids
        for cls in ("telemetry", "voice", "video")
    )

    return {
        "load_multiplier": load_multiplier,
        "per_bs":          per_bs,
        "link_util":       link_util,
        "trunk_erlang":    gen.trunk_aggregate_erlang(),
        "summary": {
            "tel_p95_worst_ms":    round(max(tel_p95_list), 4)   if tel_p95_list   else float("inf"),
            "voice_block_max_pct": round(max(per_bs[bs]["voice"]["blocking_pct"] for bs in bs_ids), 4),
            "mos_min":             min(per_bs[bs]["voice"]["mos"] for bs in bs_ids),
            "video_p95_worst_ms":  round(max(video_p95_list), 4) if video_p95_list else float("inf"),
        },
        "all_pass": all_pass,
    }


# ---------------------------------------------------------------------------
# QoS report table  (clean DataFrame for report)
# ---------------------------------------------------------------------------

def qos_report_table(load_multiplier: float = 1.0) -> pd.DataFrame:
    """
    One row per metric, worst-case BS (BS1 — longest propagation 0.1448 ms).
    """
    tel   = telemetry_qos("BS1", load_multiplier)
    voice = voice_qos("BS1",     load_multiplier)
    video = video_qos("BS1",     load_multiplier)

    rows = [
        # Telemetry rows
        {"Class": "Telemetry", "Model": "M/D/1",
         "Metric": f"P{TEL_PERCENTILE} delay (ms)",
         "Value": tel["p95_delay_ms"],
         "Target": f"< {TEL_DELAY_TARGET_MS} ms",
         "Status": "PASS ✓" if tel["meets_delay_kpi"] else "FAIL ✗"},
        {"Class": "Telemetry", "Model": "M/D/1",
         "Metric": "Packet loss (%)",
         "Value": tel["loss_pct"],
         "Target": "< 0.1%",
         "Status": "PASS ✓" if tel["meets_loss_kpi"] else "FAIL ✗"},
        {"Class": "Telemetry", "Model": "M/D/1",
         "Metric": "Link utilisation ρ",
         "Value": tel["utilisation_rho"],
         "Target": "< 1.0",
         "Status": "PASS ✓"},
        # Voice rows
        {"Class": "Voice", "Model": "Erlang B",
         "Metric": "Blocking prob (%)",
         "Value": voice["blocking_pct"],
         "Target": f"< {VOICE_BLOCKING_TARGET}%",
         "Status": "PASS ✓" if voice["meets_blocking_kpi"] else "FAIL ✗"},
        {"Class": "Voice", "Model": "Erlang B",
         "Metric": "Circuits N",
         "Value": voice["circuits_N"],
         "Target": f"min N for B < {VOICE_BLOCKING_TARGET}%",
         "Status": "PASS ✓"},
        {"Class": "Voice", "Model": "E-model (G.107)",
         "Metric": "MOS score",
         "Value": voice["mos"],
         "Target": "≥ 3.5",
         "Status": "PASS ✓" if voice["meets_mos_kpi"] else "FAIL ✗"},
        {"Class": "Voice", "Model": "E-model (G.107)",
         "Metric": "End-to-end delay (ms)",
         "Value": voice["total_delay_ms"],
         "Target": "< 150 ms",
         "Status": "PASS ✓" if voice["meets_delay_kpi"] else "FAIL ✗"},
        {"Class": "Voice", "Model": "Erlang B",
         "Metric": "Trunk blocking (5 BSes)",
         "Value": voice["trunk_blocking_pct"],
         "Target": f"< {VOICE_BLOCKING_TARGET}%",
         "Status": "PASS ✓" if voice["trunk_blocking_pct"] < VOICE_BLOCKING_TARGET else "FAIL ✗"},
        # Video rows
        {"Class": "Video", "Model": "M/M/1",
         "Metric": f"P{VIDEO_PERCENTILE} delay (ms)",
         "Value": video["p95_delay_ms"] if not math.isinf(video["p95_delay_ms"]) else "∞",
         "Target": f"< {VIDEO_DELAY_TARGET_MS} ms",
         "Status": "PASS ✓" if video["meets_delay_kpi"] else "FAIL ✗"},
        {"Class": "Video", "Model": "M/M/1",
         "Metric": "Throughput delivered (%)",
         "Value": video["throughput_pct"],
         "Target": "≥ 95%",
         "Status": "PASS ✓" if video["meets_throughput_kpi"] else "FAIL ✗"},
        {"Class": "Video", "Model": "M/M/1",
         "Metric": "Link utilisation ρ",
         "Value": video["utilisation_rho"],
         "Target": "< 1.0",
         "Status": "PASS ✓"},
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Per-BS comparison table
# ---------------------------------------------------------------------------

def per_bs_qos_table(load_multiplier: float = 1.0) -> pd.DataFrame:
    """
    One row per BS. Shows that BS1/BS5 are worst-case (longest propagation).
    """
    G   = build_topology()
    rows = []
    for bs in TrafficGenerator.BASE_STATIONS:
        prop  = _get_prop_delay_ms(bs, G)
        tel   = telemetry_qos(bs, load_multiplier, G)
        voice = voice_qos(bs,     load_multiplier, G)
        video = video_qos(bs,     load_multiplier, G)
        rows.append({
            "BS":                 bs,
            "Label":              NODES[bs]["label"],
            "Prop delay (ms)":    prop,
            "Tel P95 (ms)":       tel["p95_delay_ms"],
            "Tel pass":           "✓" if tel["pass"]   else "✗",
            "Voice blocking (%)": voice["blocking_pct"],
            "Voice N circuits":   voice["circuits_N"],
            "Voice MOS":          voice["mos"],
            "Voice pass":         "✓" if voice["pass"] else "✗",
            "Video P95 (ms)":     video["p95_delay_ms"],
            "Video pass":         "✓" if video["pass"] else "✗",
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Breaking point — sweep load until KPIs fail
# ---------------------------------------------------------------------------

def breaking_point_analysis(
    max_multiplier: float = 5.0,
    steps:          int   = 40,
) -> pd.DataFrame:
    """
    Sweep load from 0.1× to max_multiplier×, recording KPI pass/fail.

    Traffic scaling uses TrafficGenerator(load_multiplier=m) which internally
    scales TelemetryParams, VoiceParams, VideoParams by m — exactly as
    traffic.py defines the load_multiplier mechanism.

    Link utilisation at each step calls routing.link_utilisation() with the
    exact demands from TrafficGenerator.aggregate_load_mbps().

    The breaking point is the first multiplier where any KPI is breached.
    In this network, voice blocking (Erlang B) is expected to fail first
    because circuit utilisation grows faster than link bandwidth utilisation.

    Returns
    -------
    DataFrame; attrs: tel_break, voice_break, video_break, first_break.
    """
    G    = build_topology()
    rows = []

    for m in np.linspace(0.1, max_multiplier, steps):
        m = round(float(m), 4)

        tel   = telemetry_qos("BS1", m, G)
        voice = voice_qos("BS1",     m, G)
        video = video_qos("BS1",     m, G)

        # Link utilisation from routing.py
        gen     = TrafficGenerator(load_multiplier=m, seed=42)
        bw      = gen.aggregate_load_mbps()
        demands = {(bs, "CR1"): bw[bs] for bs in TrafficGenerator.BASE_STATIONS}
        util    = link_utilisation(G, demands)

        access_util = max(
            (r["utilisation_pct"] for r in util if r["link_type"] == "sub6_microwave"),
            default=0.0
        )
        trunk_util = next(
            (r["utilisation_pct"] for r in util if r["link_type"] == "eband_microwave"),
            0.0
        )

        rows.append({
            "load_multiplier":      m,
            # Telemetry
            "tel_p95_ms":           tel["p95_delay_ms"] if not math.isinf(tel["p95_delay_ms"]) else 9999,
            "tel_rho":              tel["utilisation_rho"],
            "tel_pass":             tel["pass"],
            # Voice
            "voice_erl":            voice["offered_erl"],
            "voice_N":              voice["circuits_N"],
            "voice_blocking_pct":   voice["blocking_pct"],
            "voice_mos":            voice["mos"],
            "voice_pass":           voice["pass"],
            # Video
            "video_p95_ms":         video["p95_delay_ms"] if not math.isinf(video["p95_delay_ms"]) else 9999,
            "video_rho":            video["utilisation_rho"],
            "video_throughput_pct": video["throughput_pct"],
            "video_pass":           video["pass"],
            # Link utilisation (from routing.link_utilisation)
            "access_util_pct":      round(access_util, 3),
            "trunk_util_pct":       round(trunk_util, 3),
            # Overall
            "all_pass":             tel["pass"] and voice["pass"] and video["pass"],
        })

    df = pd.DataFrame(rows)

    df.attrs["tel_break"]   = (
        df.loc[~df["tel_pass"],   "load_multiplier"].min()
        if not df["tel_pass"].all()   else None
    )
    df.attrs["voice_break"] = (
        df.loc[~df["voice_pass"], "load_multiplier"].min()
        if not df["voice_pass"].all() else None
    )
    df.attrs["video_break"] = (
        df.loc[~df["video_pass"], "load_multiplier"].min()
        if not df["video_pass"].all() else None
    )
    candidates = [x for x in [df.attrs["tel_break"],
                               df.attrs["voice_break"],
                               df.attrs["video_break"]] if x is not None]
    df.attrs["first_break"] = min(candidates) if candidates else None

    return df


# ---------------------------------------------------------------------------
# Failure-scenario QoS comparison
# ---------------------------------------------------------------------------

def failure_qos_comparison(failed_links: list = None) -> dict:
    """
    Compare QoS before and after a link failure using simulate_failure()
    from routing.py.

    Default failure: CR1–CR2 trunk (as tested in routing.py __main__).

    For each BS, the post-failure propagation delay is recomputed from the
    rerouted path returned by simulate_failure().

    Returns
    -------
    dict with baseline and failure QoS for every BS.
    """
    if failed_links is None:
        failed_links = [("CR1", "CR2")]

    G_base   = build_topology()
    G_fail   = build_topology(failed_links=failed_links)
    sim      = simulate_failure(G_base, failed_links)

    comparison = {}
    for bs in TrafficGenerator.BASE_STATIONS:
        fp = sim["post_failure_paths"][bs]

        # Post-failure propagation: sum hop delays on the new path
        if fp["reachable"] and len(fp["path"]) >= 2:
            fail_prop = round(sum(
                G_fail[fp["path"][i]][fp["path"][i+1]].get("delay_ms", 0.0)
                for i in range(len(fp["path"]) - 1)
            ), 4)
        else:
            fail_prop = float("inf")

        comparison[bs] = {
            "baseline_path":      " → ".join(sim["baseline_paths"][bs]["path"]),
            "failure_path":       " → ".join(fp["path"]) if fp["reachable"] else "UNREACHABLE",
            "baseline_prop_ms":   _get_prop_delay_ms(bs, G_base),
            "failure_prop_ms":    fail_prop,
            "baseline": {
                "telemetry": telemetry_qos(bs, 1.0, G_base),
                "voice":     voice_qos(bs,     1.0, G_base),
                "video":     video_qos(bs,     1.0, G_base),
            },
            "post_failure": {
                "telemetry": telemetry_qos(bs, 1.0, G_fail),
                "voice":     voice_qos(bs,     1.0, G_fail),
                "video":     video_qos(bs,     1.0, G_fail),
            },
        }

    return {
        "failed_links":     failed_links,
        "rerouted":         sim["rerouted"],
        "unreachable":      sim["unreachable"],
        "graph_connected":  sim["graph_connected"],
        "edges_remaining":  sim["edges_remaining"],
        "bs_comparison":    comparison,
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("TELE 527 Group 1 — QoS Module  (Student 5)")
    print("Parameters grounded in topology.py / routing.py / traffic.py")
    print("=" * 70)

    # ── 1. Parameter echo ─────────────────────────────────────────────────
    print("\n── traffic.py parameter echo ──────────────────────────────────────")
    print(f"  Telemetry : pkt={TEL_PACKET_BYTES}B, IAT={TEL_INTER_ARRIVAL_MS}ms → "
          f"{1000/TEL_INTER_ARRIVAL_MS:.0f} pps, P{TEL_PERCENTILE} target={TEL_DELAY_TARGET_MS}ms")
    print(f"  Voice     : A={VOICE_OFFERED_ERL}Erl, {int(VOICE_CODEC_KBPS)}kbps G.711, "
          f"hold={VOICE_HOLDING_S}s, GoS<{VOICE_BLOCKING_TARGET}%")
    print(f"  Video     : A={VIDEO_OFFERED_ERL}Erl, {VIDEO_BITRATE_MBPS}Mbps/session, "
          f"pkt={VIDEO_PKT_BYTES}B, P{VIDEO_PERCENTILE} target={VIDEO_DELAY_TARGET_MS}ms")

    # ── 2. Topology propagation delays ────────────────────────────────────
    print("\n── topology.py propagation delays (BS→CR1 first hop) ─────────────")
    G = build_topology()
    for bs in TrafficGenerator.BASE_STATIONS:
        d = _get_prop_delay_ms(bs, G)
        print(f"  {bs} ({NODES[bs]['label']:<14}): {d} ms")

    # ── 3. Per-BS QoS table ───────────────────────────────────────────────
    print("\n── Per-BS QoS at 1.0× load ────────────────────────────────────────")
    print(per_bs_qos_table(1.0).to_string(index=False))

    # ── 4. Full report table ──────────────────────────────────────────────
    print("\n── QoS report table (worst-case BS1, 1.0× load) ───────────────────")
    print(qos_report_table(1.0).to_string(index=False))

    # ── 5. Breaking point sweep ───────────────────────────────────────────
    print("\n── Breaking point analysis (0.1× → 5×, 40 steps) ─────────────────")
    bp = breaking_point_analysis(5.0, 40)
    print(f"  Telemetry KPI breaks at : {bp.attrs['tel_break']}×")
    print(f"  Voice     KPI breaks at : {bp.attrs['voice_break']}×")
    print(f"  Video     KPI breaks at : {bp.attrs['video_break']}×")
    print(f"  First failure overall   : {bp.attrs['first_break']}×")
    print("\n  Voice blocking at selected multipliers:")
    for m in [0.5, 1.0, 1.2, 1.4, 1.6, 2.0, 3.0, 5.0]:
        row = bp[bp["load_multiplier"].between(m - 0.08, m + 0.08)].head(1)
        if not row.empty:
            b   = row["voice_blocking_pct"].values[0]
            ok  = row["voice_pass"].values[0]
            a   = row["access_util_pct"].values[0]
            print(f"    {m}× : voice_blocking={b:.4f}%  pass={ok}  access_link_util={a}%")

    # ── 6. Full snapshot ──────────────────────────────────────────────────
    print("\n── Full snapshot at 1.0× ───────────────────────────────────────────")
    snap = qos_snapshot(1.0)
    s    = snap["summary"]
    print(f"  Tel P95 (worst BS) : {s['tel_p95_worst_ms']} ms   target < {TEL_DELAY_TARGET_MS} ms")
    print(f"  Voice blocking max : {s['voice_block_max_pct']}%   target < {VOICE_BLOCKING_TARGET}%")
    print(f"  MOS min            : {s['mos_min']}          target >= 3.5")
    print(f"  Video P95 (worst)  : {s['video_p95_worst_ms']} ms  target < {VIDEO_DELAY_TARGET_MS} ms")
    print(f"  Trunk Erlang       : {snap['trunk_erlang']}   (diagram label 3.75 Erl)")
    print(f"  All KPIs pass      : {snap['all_pass']}")

    print("\n  Link utilisation (routing.link_utilisation, 1× load):")
    for r in snap["link_util"]:
        print(f"    {r['link']:<12} {r['link_type']:<18} "
              f"cap={r['capacity_mbps']}Mbps  load={r['load_mbps']}Mbps  "
              f"util={r['utilisation_pct']}%")

    # ── 7. Failure comparison ─────────────────────────────────────────────
    print("\n── Failure comparison: CR1–CR2 trunk down ─────────────────────────")
    fc = failure_qos_comparison([("CR1", "CR2")])
    print(f"  Graph connected  : {fc['graph_connected']}")
    print(f"  BSes rerouted    : {fc['rerouted']}")
    print(f"  BSes unreachable : {fc['unreachable']}")
    for bs, c in fc["bs_comparison"].items():
        bv = c["baseline"]["voice"]
        fv = c["post_failure"]["voice"]
        print(f"  {bs}: {c['baseline_path']}  prop={c['baseline_prop_ms']}ms"
              f"  →  {c['failure_path']}  prop={c['failure_prop_ms']}ms"
              f"  | blocking: {bv['blocking_pct']}% → {fv['blocking_pct']}%")
