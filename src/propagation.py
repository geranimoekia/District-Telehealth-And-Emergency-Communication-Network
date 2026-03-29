"""
propagation.py
==============
Student 3 — Wireless Planning Lead | TELE 527 Group 1

Propagation models aligned with scenario.yaml:
  - District size: 50 km
  - Carrier: 1800 MHz
  - TX power: 43 dBm
  - Terrain: suburban_rural  → COST 231 Hata with cm=0
  - Shadow fading margin: 8 dB
  - Body loss: 3 dB
  - Indoor penetration loss: 10 dB
"""

import numpy as np


# ---------------------------------------------------------------------------
# COST 231 Hata — primary model
# ---------------------------------------------------------------------------

def cost231_hata(d_km: float,
                 f_mhz: float = 1800,
                 h_base: float = 30,
                 h_mobile: float = 1.5,
                 cm: float = 0.0) -> float:
    """
    COST 231 extension to Okumura-Hata. Valid 1500–2000 MHz.
    cm = 0 dB for medium/small cities (district scenario).
    cm = 3 dB for metropolitan centres.
    """
    d_km = max(float(d_km), 0.05)
    a_hm = (1.1 * np.log10(f_mhz) - 0.7) * h_mobile \
         - (1.56 * np.log10(f_mhz) - 0.8)
    L = (46.3 + 33.9 * np.log10(f_mhz)
         - 13.82 * np.log10(h_base)
         - a_hm
         + (44.9 - 6.55 * np.log10(h_base)) * np.log10(d_km)
         + cm)
    return float(L)


def free_space_loss(d_km: float, f_mhz: float = 1800) -> float:
    d_km = max(float(d_km), 0.05)
    return 20 * np.log10(d_km) + 20 * np.log10(f_mhz) + 32.45


def okumura_hata_urban(d_km: float, f_mhz: float = 1800,
                       h_base: float = 30, h_mobile: float = 1.5) -> float:
    d_km = max(float(d_km), 0.05)
    a_hm = (1.1 * np.log10(f_mhz) - 0.7) * h_mobile \
         - (1.56 * np.log10(f_mhz) - 0.8)
    return float(69.55 + 26.16 * np.log10(f_mhz)
                 - 13.82 * np.log10(h_base) - a_hm
                 + (44.9 - 6.55 * np.log10(h_base)) * np.log10(d_km))


# ---------------------------------------------------------------------------
# Full link budget computation
# ---------------------------------------------------------------------------

def compute_link_budget(d_km: float, scenario: dict) -> dict:
    """
    Full downlink budget using scenario.yaml environment parameters.

    Returns dict with all link budget line items.
    """
    env = scenario["environment"]
    f   = env["carrier_frequency_mhz"]
    hb  = env["base_station_height_m"]
    hm  = env["mobile_height_m"]
    ptx = env["tx_power_dbm"]
    sfm = env["shadow_fading_margin_db"]
    bl  = env["body_loss_db"]
    ipl = env["indoor_penetration_loss_db"]

    # Gains — sector antenna 17 dBi TX, 0 dBi RX (UE)
    tx_gain_dbi = 17.0
    rx_gain_dbi = 0.0
    feeder_loss  = 2.0   # cable + connector

    pl     = cost231_hata(d_km, f, hb, hm, cm=0.0)
    eirp   = ptx + tx_gain_dbi - feeder_loss
    prx    = eirp + rx_gain_dbi - pl
    margin = prx - env["coverage_threshold_outdoor_dbm"] - sfm - bl

    return {
        "distance_km":         round(d_km, 3),
        "path_loss_db":        round(pl, 2),
        "tx_power_dbm":        ptx,
        "tx_gain_dbi":         tx_gain_dbi,
        "feeder_loss_db":      feeder_loss,
        "eirp_dbm":            round(eirp, 2),
        "rx_gain_dbi":         rx_gain_dbi,
        "received_signal_dbm": round(prx, 2),
        "shadow_fading_margin":sfm,
        "body_loss_db":        bl,
        "threshold_outdoor_dbm": env["coverage_threshold_outdoor_dbm"],
        "threshold_indoor_dbm":  env["coverage_threshold_indoor_dbm"],
        "link_margin_db":      round(margin, 2),
        "coverage_radius_km":  round(_coverage_radius(scenario), 3),
        "link_quality":        _quality(margin),
    }


def _quality(margin_db: float) -> str:
    if margin_db >= 10:
        return "good"
    if margin_db >= 3:
        return "marginal"
    return "poor"


def _coverage_radius(scenario: dict) -> float:
    """Binary-search for the distance where received power = outdoor threshold."""
    env     = scenario["environment"]
    f       = env["carrier_frequency_mhz"]
    hb      = env["base_station_height_m"]
    hm      = env["mobile_height_m"]
    ptx     = env["tx_power_dbm"]
    tx_gain = 17.0
    feeder  = 2.0
    eirp    = ptx + tx_gain - feeder
    thr     = env["coverage_threshold_outdoor_dbm"] + env["shadow_fading_margin_db"]

    lo, hi = 0.05, 60.0
    for _ in range(60):
        mid = (lo + hi) / 2
        prx = eirp - cost231_hata(mid, f, hb, hm)
        if prx > thr:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ---------------------------------------------------------------------------
# Per-site link budget table (Student 4 interface + screenshot requirement)
# ---------------------------------------------------------------------------

def site_link_budget_table(scenario: dict) -> list[dict]:
    """
    Returns one row per BS site with the required fields from the screenshot:
      site_id, received_signal_dbm, path_loss_db, link_margin_db,
      coverage_radius_km, link_quality
    """
    import math
    sites  = scenario["sites"]
    bs_list = [s for s in sites if s["type"] == "base_station"]
    cr1     = next(s for s in sites if s["name"] == "CR-1")

    rows = []
    for bs in bs_list:
        d = math.hypot(bs["x_km"] - cr1["x_km"], bs["y_km"] - cr1["y_km"])
        lb = compute_link_budget(d, scenario)
        rows.append({
            "site_id":             bs["name"],
            "received_signal_dbm": lb["received_signal_dbm"],
            "path_loss_db":        lb["path_loss_db"],
            "link_margin_db":      lb["link_margin_db"],
            "coverage_radius_km":  lb["coverage_radius_km"],
            "link_quality":        lb["link_quality"],
        })
    return rows


# ---------------------------------------------------------------------------
# Microwave backhaul link budget (7 GHz BS→CR-1 and 13 GHz backbone)
# ---------------------------------------------------------------------------

def microwave_budget(freq_ghz: float, dist_km: float, cfg: dict) -> dict:
    """Compute point-to-point MW link budget from a config dict."""
    fspl   = 92.45 + 20*np.log10(freq_ghz) + 20*np.log10(dist_km)
    eirp   = cfg["tx_power_dbm"] + cfg["tx_antenna_gain_dbi"] - cfg["misc_losses_db"]
    prx    = eirp + cfg["rx_antenna_gain_dbi"] - fspl
    margin = prx - cfg["receiver_threshold_dbm"]
    status = "PASS" if margin >= cfg["min_fade_margin_db"] else "FAIL"
    capacity_mbps = _mw_capacity(freq_ghz, margin)
    return {
        "frequency_ghz":    freq_ghz,
        "distance_km":      dist_km,
        "fspl_db":          round(fspl, 1),
        "eirp_dbm":         round(eirp, 1),
        "rx_power_dbm":     round(prx, 1),
        "link_margin_db":   round(margin, 1),
        "required_margin":  cfg["min_fade_margin_db"],
        "status":           status,
        "capacity_mbps":    capacity_mbps,
    }


def _mw_capacity(freq_ghz: float, margin_db: float) -> int:
    """Rough capacity estimate based on modulation achievable at margin."""
    if margin_db >= 30:
        return 100 if freq_ghz < 10 else 400
    if margin_db >= 20:
        return 50  if freq_ghz < 10 else 200
    if margin_db >= 10:
        return 20  if freq_ghz < 10 else 100
    return 10


# ---------------------------------------------------------------------------
# Rainfall attenuation (ITU-R P.838-3) — Botswana zone H
# ---------------------------------------------------------------------------

def rain_attenuation_db(d_km: float, freq_ghz: float,
                         rain_rate_mm_h: float = 30.0) -> float:
    """
    ITU-R P.838-3 specific attenuation, zone H (30 mm/h typical peak).
    gamma_R = k * R^alpha  [dB/km]
    """
    # Coefficients for horizontal polarisation at common frequencies
    _table = {
        7:  (0.00301, 1.332),
        13: (0.0168,  1.217),
        15: (0.0335,  1.128),
        18: (0.0688,  1.061),
        23: (0.148,   1.000),
    }
    # Linear interpolation to nearest
    freqs = sorted(_table.keys())
    f0 = min(freqs, key=lambda x: abs(x - freq_ghz))
    k, alpha = _table[f0]
    gamma = k * (rain_rate_mm_h ** alpha)
    return round(gamma * d_km, 2)
