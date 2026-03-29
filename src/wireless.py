"""
wireless.py
===========
Student 3 — Wireless Planning Lead | TELE 527 Group 1

Core wireless planning module.  Builds coverage grids, evaluates frequency
reuse, and analyses sectorization effects for the District Telehealth scenario.

Exposes:
  build_coverage_grid()      — 2-D received-power grid across the district
  coverage_statistics()      — percentage area above each RSSI threshold
  plot_coverage_heatmap()    — required heatmap figure with contour overlays
  plot_path_loss_curves()    — model comparison plot for methodology section
  frequency_reuse_cluster()  — cluster size and D/R ratio table
  sectorization_analysis()   — omni vs 3-sector capacity/gain comparison
  plot_reuse_pattern()       — hexagonal cluster visualisation
  improvement_study()        — before/after: adding a 6th site or raising antenna
"""

import os
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")          # non-interactive backend — safe for scripts
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

from propagation import (
    cost231_extension,
    received_power_dbm,
    free_space_loss,
    okumura_hata_urban,
)

# ── output directory ──────────────────────────────────────────────────────────
FIG_DIR = os.path.join(os.path.dirname(__file__), "figures")
RES_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(FIG_DIR, exist_ok=True)
os.makedirs(RES_DIR, exist_ok=True)


# =============================================================================
# 1.  Coverage grid
# =============================================================================

def build_coverage_grid(sites,
                        grid_res: int   = 150,
                        area_km:  float = 20.0,
                        tx_power_dbm:   float = 46,
                        tx_gain_dbi:    float = 17,
                        rx_gain_dbi:    float = 0,
                        f_mhz:          float = 1800,
                        h_base:         float = 35,
                        h_mobile:       float = 1.5,
                        system_losses:  float = 2.0) -> tuple:
    """
    Build a 2-D grid of best-server received power across the district area.

    Parameters
    ----------
    sites         : list of (x_km, y_km) tuples
    grid_res      : number of sample points per axis
    area_km       : side length of square coverage area in km
    tx_power_dbm  : base-station transmit power (dBm)
    tx_gain_dbi   : transmit antenna gain (dBi)
    rx_gain_dbi   : receive antenna gain (dBi)
    f_mhz         : carrier frequency (MHz)
    h_base        : base-station antenna height (m)
    h_mobile      : mobile/CPE height (m)
    system_losses : miscellaneous system losses (dB)

    Returns
    -------
    xs, ys : 1-D coordinate arrays (km)
    grid   : 2-D array of best-server Rx power (dBm), shape (grid_res, grid_res)
    """
    xs = np.linspace(0, area_km, grid_res)
    ys = np.linspace(0, area_km, grid_res)

    # initialise to a very low floor
    grid = np.full((grid_res, grid_res), -150.0)

    for (sx, sy) in sites:
        for j, y in enumerate(ys):
            for i, x in enumerate(xs):
                d = float(np.sqrt((x - sx) ** 2 + (y - sy) ** 2))
                d = max(d, 0.05)            # minimum 50 m to avoid singularity
                pl = cost231_extension(d, f_mhz, h_base, h_mobile)
                rp = received_power_dbm(tx_power_dbm, tx_gain_dbi,
                                        rx_gain_dbi, pl, system_losses)
                if rp > grid[j, i]:
                    grid[j, i] = rp
    return xs, ys, grid


def coverage_statistics(grid: np.ndarray,
                        thresholds_dbm: list = (-85, -95)) -> dict:
    """
    Compute percentage of grid cells above each RSSI threshold.

    Returns
    -------
    dict  { threshold_dbm: coverage_pct }
    """
    total = grid.size
    stats = {}
    for thr in thresholds_dbm:
        count = float(np.sum(grid >= thr))
        stats[int(thr)] = round(100.0 * count / total, 1)
    return stats


# =============================================================================
# 2.  Coverage heatmap plot (required deliverable)
# =============================================================================

def plot_coverage_heatmap(xs, ys, grid,
                          sites,
                          site_names=None,
                          thresholds_dbm=(-85, -95),
                          title: str = "Coverage Heatmap — COST 231 @ 1800 MHz",
                          filename: str = "coverage_heatmap.png") -> plt.Figure:
    """
    Produces the required coverage heatmap with:
    • Colour-coded received-power surface (green = good, red = weak)
    • Dashed contour at −85 dBm  (good coverage threshold)
    • Dotted contour at −95 dBm  (edge coverage threshold)
    • Base-station site markers
    • Colour bar and labelled axes
    """
    fig, ax = plt.subplots(figsize=(8, 7))

    # colour map: red (weak) → yellow → green (good)
    cmap = plt.cm.RdYlGn
    norm = mcolors.Normalize(vmin=-120, vmax=-50)
    pcm  = ax.pcolormesh(xs, ys, grid, cmap=cmap, norm=norm, shading="auto")
    cbar = fig.colorbar(pcm, ax=ax, pad=0.02)
    cbar.set_label("Received power (dBm)", fontsize=10)

    # threshold contours
    styles   = ["--", ":"]
    colours  = ["white", "cyan"]
    for thr, ls, col in zip(thresholds_dbm, styles, colours):
        cs = ax.contour(xs, ys, grid, levels=[thr],
                        colors=[col], linewidths=2, linestyles=ls)
        ax.clabel(cs, fmt=f"{thr} dBm", fontsize=8, colors=[col])

    # site markers
    names = site_names or [f"S{i+1}" for i in range(len(sites))]
    for (sx, sy), name in zip(sites, names):
        ax.plot(sx, sy, "^", color="white", markersize=10,
                markeredgecolor="black", markeredgewidth=1.2, zorder=5)
        ax.annotate(name, (sx, sy), textcoords="offset points",
                    xytext=(4, 6), fontsize=7, color="white",
                    fontweight="bold")

    # legend
    legend_elements = [
        Line2D([0], [0], color="white",  linestyle="--", lw=2, label="−85 dBm (good)"),
        Line2D([0], [0], color="cyan",   linestyle=":",  lw=2, label="−95 dBm (edge)"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor="white",
               markersize=9, markeredgecolor="black", label="Base station"),
    ]
    ax.legend(handles=legend_elements, loc="upper left",
              fontsize=8, framealpha=0.7, facecolor="#222222", labelcolor="white")

    ax.set_xlabel("East–West distance (km)", fontsize=10)
    ax.set_ylabel("North–South distance (km)", fontsize=10)
    ax.set_title(title, fontsize=11, pad=10)
    ax.set_xlim(0, xs[-1])
    ax.set_ylim(0, ys[-1])

    plt.tight_layout()
    path = os.path.join(FIG_DIR, filename)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    print(f"[wireless] Saved: {path}")
    return fig


# =============================================================================
# 3.  Path-loss comparison plot (methodology section)
# =============================================================================

def plot_path_loss_curves(f_mhz: float = 1800,
                          h_base: float = 35,
                          filename: str = "path_loss_curves.png") -> plt.Figure:
    """
    Comparison of FSPL, Okumura-Hata urban, and COST 231 models.
    Justifies choice of COST 231 for the district scenario.
    """
    distances = np.linspace(0.1, 20, 300)

    fspl = [free_space_loss(d, f_mhz) for d in distances]
    oh   = [okumura_hata_urban(d, f_mhz, h_base) for d in distances]
    c231 = [cost231_extension(d, f_mhz, h_base) for d in distances]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(distances, fspl, "b--",  lw=1.5, label="Free-space (FSPL)")
    ax.plot(distances, oh,   "g-",   lw=1.8, label="Okumura-Hata Urban")
    ax.plot(distances, c231, "r-",   lw=2.2, label="COST 231 (selected)")
    ax.axhline(-50 + 46 + 17,  color="gray", linestyle=":", lw=1)   # Tx EIRP reference
    ax.axvline(10, color="orange", linestyle="--", lw=1, label="10 km reference")

    ax.set_xlabel("Distance (km)", fontsize=10)
    ax.set_ylabel("Path loss (dB)", fontsize=10)
    ax.set_title(f"Path Loss Model Comparison — {f_mhz} MHz, h_base={h_base} m",
                 fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.invert_yaxis()
    plt.tight_layout()
    path = os.path.join(FIG_DIR, filename)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    print(f"[wireless] Saved: {path}")
    return fig


# =============================================================================
# 4.  Frequency reuse
# =============================================================================

def frequency_reuse_cluster(reuse_factor: int = 4,
                             total_bandwidth_mhz: float = 20,
                             channel_bw_mhz: float = 5) -> dict:
    """
    Frequency reuse analysis.

    Parameters
    ----------
    reuse_factor        : cluster size N (number of cells per cluster)
    total_bandwidth_mhz : total spectrum available (MHz)
    channel_bw_mhz      : per-cell channel bandwidth (MHz)

    Returns
    -------
    dict with engineering quantities
    """
    D_over_R  = float(np.sqrt(3 * reuse_factor))
    channels_per_cell = total_bandwidth_mhz / reuse_factor / channel_bw_mhz
    sir_db    = 10 * np.log10((D_over_R ** 2.0) / 6)   # approx SIR for omni

    return {
        "reuse_factor":      reuse_factor,
        "D_R_ratio":         round(D_over_R, 3),
        "channels_per_cell": round(channels_per_cell, 1),
        "approx_SIR_dB":     round(sir_db, 1),
        "spectral_efficiency": round(1 / reuse_factor, 3),
        "note": (f"N={reuse_factor}: D/R={D_over_R:.2f}, "
                 f"{channels_per_cell:.0f} channels/cell, "
                 f"SIR≈{sir_db:.1f} dB"),
    }


def sectorization_analysis(reuse_factor: int = 4,
                           sectors: int = 3,
                           total_bandwidth_mhz: float = 20,
                           channel_bw_mhz: float = 5) -> dict:
    """
    Compare omnidirectional vs K-sector antenna configuration.

    With S sectors per site:
      • Effective reuse factor improves by factor S (more spatial reuse)
      • Each sector sees 1/S of the interference sources compared to omni
      • Capacity per site scales with S (more channels reused per km²)
    """
    omni  = frequency_reuse_cluster(reuse_factor, total_bandwidth_mhz, channel_bw_mhz)
    # With sectorization, effective cluster size can be reduced
    # because each sector already provides directional isolation
    effective_N = max(1, reuse_factor // sectors) if sectors > 1 else reuse_factor
    sector_data = frequency_reuse_cluster(effective_N, total_bandwidth_mhz, channel_bw_mhz)

    capacity_gain = sectors * sector_data["channels_per_cell"] / omni["channels_per_cell"]

    return {
        "omni":            omni,
        "sectorized":      sector_data,
        "num_sectors":     sectors,
        "capacity_gain_x": round(capacity_gain, 2),
        "summary": (f"{sectors}-sector config gives ×{capacity_gain:.1f} capacity "
                    f"vs omni at N={reuse_factor}"),
    }


# =============================================================================
# 5.  Reuse pattern visualisation
# =============================================================================

def plot_reuse_pattern(reuse_factor: int = 4,
                       filename: str = "reuse_pattern.png") -> plt.Figure:
    """
    Draws a hexagonal frequency-reuse cluster pattern.
    Each colour represents a different frequency assignment group.
    """
    fig, ax = plt.subplots(figsize=(8, 7))

    # generate a grid of hexagon centres
    colours = plt.cm.Set1.colors[:reuse_factor]
    hex_r   = 1.0    # normalised cell radius

    freq_idx = 0
    cell_labels = []
    for row in range(-3, 4):
        for col in range(-4, 5):
            cx = col * 1.5 * hex_r
            cy = row * np.sqrt(3) * hex_r + (col % 2) * np.sqrt(3) / 2 * hex_r
            colour = colours[freq_idx % reuse_factor]
            hex_patch = mpatches.RegularPolygon(
                (cx, cy), numVertices=6, radius=hex_r * 0.95,
                orientation=0, facecolor=colour, edgecolor="white",
                linewidth=1.5, alpha=0.8)
            ax.add_patch(hex_patch)
            ax.text(cx, cy, f"f{freq_idx % reuse_factor + 1}",
                    ha="center", va="center", fontsize=8,
                    fontweight="bold", color="white")
            cell_labels.append(freq_idx % reuse_factor + 1)
            freq_idx += 1

    ax.set_xlim(-6, 6)
    ax.set_ylim(-6, 6)
    ax.set_aspect("equal")
    ax.axis("off")

    # legend
    legend_patches = [
        mpatches.Patch(color=colours[i], label=f"Frequency group f{i+1}")
        for i in range(reuse_factor)
    ]
    ax.legend(handles=legend_patches, loc="upper right", fontsize=9,
              title=f"N={reuse_factor} Reuse Pattern")
    ax.set_title(f"Frequency Reuse Pattern — Cluster Size N = {reuse_factor}",
                 fontsize=12, pad=12)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"[wireless] Saved: {path}")
    return fig


# =============================================================================
# 6.  Improvement study (before / after)
# =============================================================================

def improvement_study(base_sites: list,
                      scenario_cfg: dict,
                      filename_prefix: str = "improvement") -> dict:
    """
    Compares baseline 5-site layout against two improvements:
      A) Adding a 6th site at the district's coverage black-spot
      B) Raising antenna height from 35 m to 50 m

    Returns coverage statistics for each scenario.
    """
    thresholds = scenario_cfg.get("thresholds", [-85, -95])
    kwargs = dict(
        grid_res      = scenario_cfg.get("grid_res", 100),
        area_km       = scenario_cfg.get("area_km", 20),
        tx_power_dbm  = scenario_cfg.get("tx_power_dbm", 46),
        tx_gain_dbi   = scenario_cfg.get("tx_gain_dbi", 17),
        rx_gain_dbi   = scenario_cfg.get("rx_gain_dbi", 0),
        f_mhz         = scenario_cfg.get("f_mhz", 1800),
        h_base        = scenario_cfg.get("h_base", 35),
        h_mobile      = scenario_cfg.get("h_mobile", 1.5),
        system_losses = scenario_cfg.get("system_losses", 2.0),
    )

    results = {}

    # --- Baseline ---
    xs, ys, g0 = build_coverage_grid(base_sites, **kwargs)
    results["baseline"] = coverage_statistics(g0, thresholds)

    # --- Improvement A: 6th site at coverage centroid black-spot ---
    extra_site  = [(10.0, 3.0)]      # south-centre gap in the 5-site layout
    sites_6     = base_sites + extra_site
    _, _, g_6   = build_coverage_grid(sites_6, **kwargs)
    results["add_6th_site"] = coverage_statistics(g_6, thresholds)

    # --- Improvement B: raise antenna height to 50 m ---
    kw_tall = {**kwargs, "h_base": 50}
    _, _, g_tall = build_coverage_grid(base_sites, **kw_tall)
    results["raise_height_50m"] = coverage_statistics(g_tall, thresholds)

    # --- Side-by-side plot ---
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True)
    titles   = ["Baseline (5 sites, 35 m)", "6th Site Added", "Antenna Raised to 50 m"]
    grids    = [g0, g_6, g_tall]
    all_sites= [base_sites, sites_6, base_sites]
    cmap     = plt.cm.RdYlGn
    norm     = mcolors.Normalize(vmin=-120, vmax=-50)

    for ax, g, ttl, slist in zip(axes, grids, titles, all_sites):
        pcm = ax.pcolormesh(xs, ys, g, cmap=cmap, norm=norm, shading="auto")
        for thr, ls, col in zip(thresholds, ["--", ":"], ["white", "cyan"]):
            cs = ax.contour(xs, ys, g, levels=[thr],
                            colors=[col], linewidths=1.8, linestyles=ls)
            ax.clabel(cs, fmt=f"{thr}", fontsize=7, colors=[col])
        for (sx, sy) in slist:
            ax.plot(sx, sy, "^", color="white", markersize=8,
                    markeredgecolor="black", markeredgewidth=1)
        ax.set_title(ttl, fontsize=10, pad=6)
        ax.set_xlabel("East–West (km)", fontsize=9)
    axes[0].set_ylabel("North–South (km)", fontsize=9)
    fig.colorbar(pcm, ax=axes[-1], label="Rx power (dBm)", pad=0.02)
    fig.suptitle("Coverage Improvement Study", fontsize=13, y=1.01)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, f"{filename_prefix}_study.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"[wireless] Saved: {path}")
    plt.close(fig)

    return results


# =============================================================================
# 7.  Microwave backhaul link budget
# =============================================================================

def microwave_link_budget(freq_ghz:        float = 7.0,
                          distance_km:     float = 12.0,
                          tx_power_dbm:    float = 30.0,
                          tx_gain_dbi:     float = 34.0,
                          rx_gain_dbi:     float = 34.0,
                          system_losses_db:float = 3.0,
                          fade_margin_db:  float = 20.0,
                          rx_threshold_dbm:float = -85.0,
                          filename:        str   = "link_budget.png") -> dict:
    """
    Full microwave point-to-point link budget calculation.
    Outputs a results dict and a formatted table figure.

    FSPL formula: 92.45 + 20·log10(f_GHz) + 20·log10(d_km)
    """
    fspl_db = 92.45 + 20 * np.log10(freq_ghz) + 20 * np.log10(distance_km)
    eirp_dbm = tx_power_dbm + tx_gain_dbi
    rx_power_dbm = eirp_dbm + rx_gain_dbi - fspl_db - system_losses_db
    link_margin_db = rx_power_dbm - rx_threshold_dbm
    available_fade = link_margin_db            # fade margin available
    status = "PASS" if link_margin_db >= fade_margin_db else "FAIL"

    budget = {
        "freq_ghz":           freq_ghz,
        "distance_km":        distance_km,
        "tx_power_dbm":       tx_power_dbm,
        "tx_gain_dbi":        tx_gain_dbi,
        "rx_gain_dbi":        rx_gain_dbi,
        "eirp_dbm":           round(eirp_dbm, 1),
        "fspl_db":            round(fspl_db, 1),
        "system_losses_db":   system_losses_db,
        "rx_power_dbm":       round(rx_power_dbm, 1),
        "rx_threshold_dbm":   rx_threshold_dbm,
        "link_margin_db":     round(link_margin_db, 1),
        "required_fade_margin": fade_margin_db,
        "status":             status,
    }

    # ── plot table ──────────────────────────────────────────────────────────
    rows = [
        ["Parameter",                "Symbol",    "Value",                    "Unit",  ""],
        ["Frequency",                "f",         f"{freq_ghz:.1f}",          "GHz",   ""],
        ["Link distance",            "d",         f"{distance_km:.1f}",       "km",    ""],
        ["Transmit power",           "Ptx",       f"{tx_power_dbm:.1f}",      "dBm",   ""],
        ["Tx antenna gain",          "Gtx",       f"{tx_gain_dbi:.1f}",       "dBi",   ""],
        ["EIRP",                     "EIRP",      f"{eirp_dbm:.1f}",          "dBm",   ""],
        ["Free-space path loss",     "FSPL",      f"{fspl_db:.1f}",           "dB",    ""],
        ["System losses",            "Lsys",      f"{system_losses_db:.1f}",  "dB",    ""],
        ["Rx antenna gain",          "Grx",       f"{rx_gain_dbi:.1f}",       "dBi",   ""],
        ["Received power",           "Prx",       f"{rx_power_dbm:.1f}",      "dBm",   ""],
        ["Rx threshold",             "Smin",      f"{rx_threshold_dbm:.1f}",  "dBm",   ""],
        ["Link margin",              "M",         f"{link_margin_db:.1f}",    "dB",    ""],
        ["Required fade margin",     "Mreq",      f"{fade_margin_db:.1f}",    "dB",    ""],
        ["Link status",              "—",         status,                     "—",     status],
    ]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axis("off")
    tbl = ax.table(
        cellText  = [[r[0], r[1], r[2], r[3]] for r in rows[1:]],
        colLabels = rows[0][:4],
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.5)

    # colour header and status row
    header_colour = "#2C3E50"
    for j in range(4):
        tbl[0, j].set_facecolor(header_colour)
        tbl[0, j].set_text_props(color="white", fontweight="bold")

    # colour pass/fail row
    for j in range(4):
        tbl[len(rows) - 1, j].set_facecolor(
            "#27AE60" if status == "PASS" else "#E74C3C")
        tbl[len(rows) - 1, j].set_text_props(color="white", fontweight="bold")

    ax.set_title("Microwave Backhaul Link Budget — 7 GHz, 12 km hop",
                 fontsize=11, pad=12)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, filename)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    print(f"[wireless] Saved: {path}")
    plt.close(fig)

    return budget


# =============================================================================
# 8.  JSON export (numpy-safe)
# =============================================================================

class _NumpySafeEncoder(json.JSONEncoder):
    """Converts numpy scalars to native Python types before JSON serialisation."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def export_results(data: dict, filename: str = "wireless_results.json") -> str:
    """Serialise results dict to JSON, handling numpy types correctly."""
    path = os.path.join(RES_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, cls=_NumpySafeEncoder)
    print(f"[wireless] Exported: {path}")
    return path
