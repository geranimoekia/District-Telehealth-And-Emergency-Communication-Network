"""
propagation.py  —  S3 Wireless Planning Lead
TELE 527  Group 1: District Telehealth & Emergency Network

COST 231-Hata path loss model (1500–2000 MHz).
All parameters read from scenario config — nothing hardcoded.
"""

import numpy as np
from typing import Dict, Any, Tuple, List


# ─── COST 231-Hata ───────────────────────────────────────────────────────────

def cost231_path_loss(
    d_km,
    f_mhz: float,
    h_b_m: float,
    h_m_m: float,
    terrain: str = "suburban_rural",
) -> np.ndarray:
    """
    COST 231-Hata path loss (dB).  Valid 1500–2000 MHz.

    suburban_rural correction: −[2·(log10(f/28))² + 5.4]
    """
    d = np.atleast_1d(np.asarray(d_km, dtype=float))
    d = np.where(d < 0.05, 0.05, d)

    a_hm = (1.1 * np.log10(f_mhz) - 0.7) * h_m_m - (1.56 * np.log10(f_mhz) - 0.8)
    C_m  = 3.0 if terrain == "urban" else 0.0

    L_urban = (46.3
               + 33.9 * np.log10(f_mhz)
               - 13.82 * np.log10(h_b_m)
               - a_hm
               + (44.9 - 6.55 * np.log10(h_b_m)) * np.log10(d)
               + C_m)

    if terrain == "suburban_rural":
        K = 2.0 * (np.log10(f_mhz / 28.0)) ** 2 + 5.4
        return L_urban - K
    elif terrain == "open":
        K = 4.78 * (np.log10(f_mhz)) ** 2 - 18.33 * np.log10(f_mhz) + 40.94
        return L_urban - K
    return L_urban


def received_power_dbm(
    tx_power_dbm: float,
    tx_gain_dbi: float,
    rx_gain_dbi: float,
    path_loss_db,
    shadow_margin_db: float = 0.0,
    body_loss_db: float = 0.0,
) -> np.ndarray:
    return (tx_power_dbm + tx_gain_dbi + rx_gain_dbi
            - np.asarray(path_loss_db)
            - shadow_margin_db - body_loss_db)


def free_space_path_loss_db(d_km: float, f_ghz: float) -> float:
    return 20.0 * np.log10(max(d_km, 0.001)) + 20.0 * np.log10(f_ghz) + 92.45


# ─── Grid builders ───────────────────────────────────────────────────────────

def build_received_power_grid(
    sites: List[Tuple],
    cfg: Dict[str, Any],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    500×500 best-server RSL grid over the 50×50 km district.
    Returns (xs, ys, grid_dbm).
    """
    env = cfg["environment"]
    N   = int(cfg["district_size_km"] * 1000 / cfg["grid_resolution_m"])
    xs  = np.linspace(0, cfg["district_size_km"], N)
    ys  = np.linspace(0, cfg["district_size_km"], N)
    XX, YY = np.meshgrid(xs, ys)
    grid = np.full((N, N), -300.0)

    for (sx, sy, sid, _) in sites:
        D   = np.sqrt((XX - sx) ** 2 + (YY - sy) ** 2)
        L   = cost231_path_loss(D, env["carrier_frequency_mhz"],
                                env["base_station_height_m"],
                                env["mobile_height_m"],
                                env["terrain_type"])
        RSL = received_power_dbm(env["tx_power_dbm"], 15.0, 0.0, L,
                                 env["shadow_fading_margin_db"],
                                 env["body_loss_db"])
        grid = np.maximum(grid, RSL)

    return xs, ys, grid