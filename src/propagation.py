"""
propagation.py
==============
Student 3 — Wireless Planning Lead | TELE 527 Group 1

Implements the Okumura-Hata path loss model for urban/suburban macro cells
at 1800 MHz, as required by the District Telehealth scenario.

Reference:
  Hata, M. (1980). Empirical formula for propagation loss in land mobile radio
  services. IEEE Trans. Vehicular Technology, 29(3), 317–325.

Usage:
  from propagation import okumura_hata_urban, received_power_dbm, free_space_loss
"""

import numpy as np


# ---------------------------------------------------------------------------
# Core propagation functions
# ---------------------------------------------------------------------------

def okumura_hata_urban(d_km: float,
                       f_mhz: float = 1800,
                       h_base: float = 35,
                       h_mobile: float = 1.5) -> float:
    """
    Okumura-Hata path loss — urban large city correction.

    Valid range: 150–1500 MHz (extended to 1800 MHz with COST 231 correction)
    Distance   : 1–20 km
    h_base     : 30–200 m
    h_mobile   : 1–10 m

    Parameters
    ----------
    d_km     : link distance in km (clipped to 0.05 km minimum to avoid -inf)
    f_mhz    : carrier frequency in MHz
    h_base   : base-station antenna height in metres
    h_mobile : mobile/CPE antenna height in metres

    Returns
    -------
    Path loss in dB (positive value)
    """
    d_km = max(float(d_km), 0.05)   # guard against zero distance

    # Mobile-station height correction factor (large city, f ≥ 300 MHz)
    a_hm = (1.1 * np.log10(f_mhz) - 0.7) * h_mobile \
           - (1.56 * np.log10(f_mhz) - 0.8)

    # Okumura-Hata urban median path loss
    L = (69.55
         + 26.16 * np.log10(f_mhz)
         - 13.82 * np.log10(h_base)
         - a_hm
         + (44.9 - 6.55 * np.log10(h_base)) * np.log10(d_km))
    return float(L)


def okumura_hata_suburban(d_km: float,
                          f_mhz: float = 1800,
                          h_base: float = 35,
                          h_mobile: float = 1.5) -> float:
    """
    Okumura-Hata suburban path loss correction.
    Reduces urban path loss for open/quasi-open areas typical of a district.
    """
    L_urban = okumura_hata_urban(d_km, f_mhz, h_base, h_mobile)
    K = 2 * (np.log10(f_mhz / 28)) ** 2 + 5.4
    return float(L_urban - K)


def cost231_extension(d_km: float,
                      f_mhz: float = 1800,
                      h_base: float = 35,
                      h_mobile: float = 1.5,
                      cm: float = 0) -> float:
    """
    COST 231 Hata model — extends Okumura-Hata to 1500–2000 MHz.

    cm = 0 dB  for medium/small cities (district towns)
    cm = 3 dB  for metropolitan centres

    Reference:
      COST Action 231 (1999). Digital mobile radio towards future generation
      systems. European Commission.
    """
    d_km = max(float(d_km), 0.05)
    a_hm = (1.1 * np.log10(f_mhz) - 0.7) * h_mobile \
           - (1.56 * np.log10(f_mhz) - 0.8)

    L = (46.3
         + 33.9 * np.log10(f_mhz)
         - 13.82 * np.log10(h_base)
         - a_hm
         + (44.9 - 6.55 * np.log10(h_base)) * np.log10(d_km)
         + cm)
    return float(L)


def free_space_loss(d_km: float, f_mhz: float = 1800) -> float:
    """
    Free-space path loss (FSPL) for reference comparison.

    FSPL (dB) = 20*log10(d) + 20*log10(f) + 32.45
    """
    d_km = max(float(d_km), 0.05)
    return 20 * np.log10(d_km) + 20 * np.log10(f_mhz) + 32.45


def received_power_dbm(tx_power_dbm: float,
                       tx_gain_dbi: float,
                       rx_gain_dbi: float,
                       path_loss_db: float,
                       system_losses_db: float = 2.0) -> float:
    """
    Link budget received power.

    Prx = Ptx + Gtx + Grx − PL − Lsys

    Parameters
    ----------
    tx_power_dbm    : transmit power in dBm
    tx_gain_dbi     : transmit antenna gain in dBi
    rx_gain_dbi     : receive antenna gain in dBi
    path_loss_db    : path loss (positive, in dB)
    system_losses_db: feeder, connector, body losses (default 2 dB)

    Returns
    -------
    Received power in dBm
    """
    return tx_power_dbm + tx_gain_dbi + rx_gain_dbi \
           - path_loss_db - system_losses_db


# ---------------------------------------------------------------------------
# Path loss distance sweep — used for link budget tables
# ---------------------------------------------------------------------------

def path_loss_vs_distance(distances_km: list,
                          f_mhz: float = 1800,
                          h_base: float = 35,
                          h_mobile: float = 1.5,
                          model: str = "cost231") -> dict:
    """
    Compute path loss at a list of distances.

    Parameters
    ----------
    distances_km : list of distances in km
    model        : "okumura_hata" | "suburban" | "cost231" | "fspl"

    Returns
    -------
    dict with 'distances' and 'path_loss' lists
    """
    fn_map = {
        "okumura_hata": okumura_hata_urban,
        "suburban":     okumura_hata_suburban,
        "cost231":      cost231_extension,
        "fspl":         free_space_loss,
    }
    fn = fn_map.get(model, cost231_extension)
    losses = [fn(d, f_mhz, h_base, h_mobile) if model not in ("fspl",)
              else free_space_loss(d, f_mhz)
              for d in distances_km]
    return {"distances_km": distances_km, "path_loss_db": losses}


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Propagation Model Self-Test ===\n")
    test_distances = [0.5, 1, 2, 5, 10, 15, 20]
    print(f"{'Distance (km)':<16} {'FSPL (dB)':<12} {'OH Urban (dB)':<16} {'COST231 (dB)':<14}")
    print("-" * 60)
    for d in test_distances:
        fspl = free_space_loss(d)
        oh   = okumura_hata_urban(d)
        c231 = cost231_extension(d)
        print(f"{d:<16.1f} {fspl:<12.1f} {oh:<16.1f} {c231:<14.1f}")

    print("\nReceived power at 5 km:")
    pl = cost231_extension(5)
    rp = received_power_dbm(46, 17, 0, pl)
    print(f"  Path loss : {pl:.1f} dB")
    print(f"  Rx power  : {rp:.1f} dBm")
    print(f"  {'PASS' if rp > -95 else 'FAIL'} — threshold −95 dBm")
