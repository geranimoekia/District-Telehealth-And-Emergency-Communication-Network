"""
wireless.py
===========
Student 3 — Wireless Planning Lead | TELE 527 Group 1

Full wireless planning module that:
  1. Reads scenario.yaml (shared with Student 2)
  2. Consumes Student 2's traffic outputs for backhaul capacity validation
  3. Produces all required outputs including Student 4's interface fields
  4. Generates figures for the Streamlit dashboard

Outputs provided to Student 4 (Signaling & Routing Lead):
  - Per-link usage (primary vs backup, Mbps and % utilisation)
  - Erlang B blocking probability per site
  - Call arrival rates per BS
  - Call setup delay per site
  - Grade of Service (GoS)
  - Link quality classification (good / marginal / poor)
"""

import os
import math
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

from propagation import (
    cost231_hata, free_space_loss, okumura_hata_urban,
    compute_link_budget, site_link_budget_table,
    microwave_budget, rain_attenuation_db, _coverage_radius,
)

FIG_DIR = os.path.join(os.path.dirname(__file__), "figures")
RES_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(FIG_DIR, exist_ok=True)
os.makedirs(RES_DIR, exist_ok=True)


# ============================================================
# 1.  Coverage grid  (50 km district, scenario-driven)
# ============================================================

def build_coverage_grid(scenario: dict,
                        load_multiplier: float = 1.0,
                        grid_res: int = 120) -> tuple:
    """
    2-D best-server received-power grid across the 50 km district.
    Uses COST 231 Hata with scenario.yaml parameters.
    """
    env  = scenario["environment"]
    f    = env["carrier_frequency_mhz"]
    hb   = env["base_station_height_m"]
    hm   = env["mobile_height_m"]
    ptx  = env["tx_power_dbm"]
    sfm  = env["shadow_fading_margin_db"]
    tx_gain = 17.0
    feeder  = 2.0
    eirp    = ptx + tx_gain - feeder

    size = env["district_size_km"]
    xs   = np.linspace(0, size, grid_res)
    ys   = np.linspace(0, size, grid_res)
    grid = np.full((grid_res, grid_res), -150.0)

    bs_sites = [(s["x_km"], s["y_km"])
                for s in scenario["sites"] if s["type"] == "base_station"]

    for (sx, sy) in bs_sites:
        for j, y in enumerate(ys):
            for i, x in enumerate(xs):
                d   = max(math.hypot(x - sx, y - sy), 0.05)
                pl  = cost231_hata(d, f, hb, hm, cm=0.0)
                prx = eirp - pl
                if prx > grid[j, i]:
                    grid[j, i] = prx

    return xs, ys, grid


def coverage_statistics(grid: np.ndarray, scenario: dict) -> dict:
    env    = scenario["environment"]
    thr_od = env["coverage_threshold_outdoor_dbm"]
    thr_in = env["coverage_threshold_indoor_dbm"]
    total  = grid.size
    return {
        "outdoor_pct": round(100 * float(np.sum(grid >= thr_od)) / total, 1),
        "indoor_pct":  round(100 * float(np.sum(grid >= thr_in)) / total, 1),
        "threshold_outdoor_dbm": thr_od,
        "threshold_indoor_dbm":  thr_in,
        "max_rx_dbm":  round(float(grid.max()), 1),
        "min_rx_dbm":  round(float(grid.min()), 1),
        "median_rx_dbm": round(float(np.median(grid)), 1),
    }


# ============================================================
# 2.  Coverage heatmap figure
# ============================================================

def plot_coverage_heatmap(xs, ys, grid, scenario: dict,
                          title="Coverage Heatmap — COST 231 @ 1800 MHz",
                          filename="coverage_heatmap.png") -> plt.Figure:
    env     = scenario["environment"]
    thr_od  = env["coverage_threshold_outdoor_dbm"]
    thr_in  = env["coverage_threshold_indoor_dbm"]
    bs_list = [s for s in scenario["sites"] if s["type"] == "base_station"]
    cr_list = [s for s in scenario["sites"] if s["type"] == "core_router"]

    fig, ax = plt.subplots(figsize=(9, 8))
    norm = mcolors.Normalize(vmin=-130, vmax=-50)
    pcm  = ax.pcolormesh(xs, ys, grid, cmap="RdYlGn", norm=norm, shading="auto")
    cbar = fig.colorbar(pcm, ax=ax, pad=0.02, shrink=0.85)
    cbar.set_label("Received power (dBm)", fontsize=10)

    # Threshold contours
    for thr, ls, col, lbl in [
        (thr_od, "--", "white", f"{thr_od} dBm (outdoor)"),
        (thr_in, ":",  "cyan",  f"{thr_in} dBm (indoor)"),
    ]:
        try:
            cs = ax.contour(xs, ys, grid, levels=[thr],
                            colors=[col], linewidths=2, linestyles=ls)
            ax.clabel(cs, fmt=f"{thr} dBm", fontsize=8, colors=[col])
        except Exception:
            pass

    # BS markers
    for bs in bs_list:
        ax.plot(bs["x_km"], bs["y_km"], "^", color="white", markersize=11,
                markeredgecolor="black", markeredgewidth=1.3, zorder=6)
        ax.annotate(bs["name"], (bs["x_km"], bs["y_km"]),
                    xytext=(3, 7), textcoords="offset points",
                    fontsize=8, color="white", fontweight="bold")

    # Core router markers
    for cr in cr_list:
        ax.plot(cr["x_km"], cr["y_km"], "s", color="gold", markersize=11,
                markeredgecolor="black", markeredgewidth=1.3, zorder=6)
        ax.annotate(cr["name"], (cr["x_km"], cr["y_km"]),
                    xytext=(3, 7), textcoords="offset points",
                    fontsize=8, color="gold", fontweight="bold")

    # Draw backhaul links
    cr1 = next(s for s in scenario["sites"] if s["name"] == "CR-1")
    cr2 = next(s for s in scenario["sites"] if s["name"] == "CR-2")
    for bs in bs_list:
        ax.plot([cr1["x_km"], bs["x_km"]], [cr1["y_km"], bs["y_km"]],
                color="white", alpha=0.3, lw=1, linestyle="-")
        ax.plot([cr2["x_km"], bs["x_km"]], [cr2["y_km"], bs["y_km"]],
                color="cyan", alpha=0.15, lw=0.8, linestyle="--")
    ax.plot([cr1["x_km"], cr2["x_km"]], [cr1["y_km"], cr2["y_km"]],
            color="gold", lw=2, linestyle="-", alpha=0.7)

    legend_elements = [
        Line2D([0], [0], color="white",  ls="--", lw=2, label=f"{thr_od} dBm outdoor"),
        Line2D([0], [0], color="cyan",   ls=":",  lw=2, label=f"{thr_in} dBm indoor"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor="white",
               markersize=9, markeredgecolor="black", label="Base station"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="gold",
               markersize=9, markeredgecolor="black", label="Core router"),
        Line2D([0], [0], color="gold", lw=2, label="13 GHz backbone"),
    ]
    ax.legend(handles=legend_elements, loc="upper left",
              fontsize=8, framealpha=0.75, facecolor="#1a1a2e", labelcolor="white")

    ax.set_xlabel("East–West distance (km)", fontsize=10)
    ax.set_ylabel("North–South distance (km)", fontsize=10)
    ax.set_title(title, fontsize=12, pad=10)
    ax.set_xlim(0, xs[-1])
    ax.set_ylim(0, ys[-1])
    plt.tight_layout()
    path = os.path.join(FIG_DIR, filename)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    print(f"[wireless] Saved: {path}")
    return fig


# ============================================================
# 3.  Path-loss comparison
# ============================================================

def plot_path_loss_curves(scenario: dict,
                          filename="path_loss_curves.png") -> plt.Figure:
    env = scenario["environment"]
    f   = env["carrier_frequency_mhz"]
    hb  = env["base_station_height_m"]
    hm  = env["mobile_height_m"]
    ptx = env["tx_power_dbm"]
    tx_gain = 17.0
    feeder  = 2.0
    eirp    = ptx + tx_gain - feeder

    distances = np.linspace(0.1, 30, 400)
    fspl = [free_space_loss(d, f) for d in distances]
    oh   = [okumura_hata_urban(d, f, hb, hm) for d in distances]
    c231 = [cost231_hata(d, f, hb, hm, 0) for d in distances]

    # Received power curves
    prx_c231 = [eirp - pl for pl in c231]
    thr_od   = env["coverage_threshold_outdoor_dbm"]
    thr_in   = env["coverage_threshold_indoor_dbm"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Left: path loss
    ax1.plot(distances, fspl, "b--", lw=1.5, label="FSPL")
    ax1.plot(distances, oh,   "g-",  lw=1.8, label="Okumura-Hata Urban")
    ax1.plot(distances, c231, "r-",  lw=2.5, label="COST 231 (selected)", zorder=5)
    ax1.set_xlabel("Distance (km)", fontsize=10)
    ax1.set_ylabel("Path loss (dB)", fontsize=10)
    ax1.set_title(f"Path Loss Models @ {f} MHz, h_base={hb} m", fontsize=10)
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.invert_yaxis()

    # Right: received power + thresholds
    ax2.plot(distances, prx_c231, "r-", lw=2.5, label="Rx Power (COST 231)")
    ax2.axhline(thr_od, color="orange", ls="--", lw=1.8,
                label=f"Outdoor threshold ({thr_od} dBm)")
    ax2.axhline(thr_in, color="cyan", ls=":", lw=1.8,
                label=f"Indoor threshold ({thr_in} dBm)")

    # Coverage radius
    r_cov = _coverage_radius(scenario)
    ax2.axvline(r_cov, color="green", ls="-.", lw=1.5,
                label=f"Coverage radius ({r_cov:.1f} km)")
    ax2.fill_between(distances, thr_od, prx_c231,
                     where=[p > thr_od for p in prx_c231],
                     alpha=0.15, color="green")
    ax2.set_xlabel("Distance (km)", fontsize=10)
    ax2.set_ylabel("Received power (dBm)", fontsize=10)
    ax2.set_title("Received Power vs Distance", fontsize=10)
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)

    plt.suptitle("Propagation Analysis — District Telehealth Network", fontsize=12)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, filename)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    print(f"[wireless] Saved: {path}")
    return fig


# ============================================================
# 4.  Frequency reuse
# ============================================================

def frequency_reuse_cluster(N: int = 4,
                             total_bw_mhz: float = 20,
                             ch_bw_mhz: float = 5) -> dict:
    D_over_R   = float(np.sqrt(3 * N))
    ch_per_cell = total_bw_mhz / N / ch_bw_mhz
    sir_db      = 10 * np.log10((D_over_R ** 2) / 6)
    return {
        "reuse_factor":      N,
        "D_R_ratio":         round(D_over_R, 3),
        "channels_per_cell": round(ch_per_cell, 1),
        "approx_SIR_dB":     round(sir_db, 1),
        "spectral_efficiency": round(1 / N, 3),
    }


def sectorization_analysis(N: int = 4, sectors: int = 3,
                            total_bw: float = 20, ch_bw: float = 5) -> dict:
    omni   = frequency_reuse_cluster(N, total_bw, ch_bw)
    eff_N  = max(1, N // sectors)
    sect   = frequency_reuse_cluster(eff_N, total_bw, ch_bw)
    gain   = sectors * sect["channels_per_cell"] / max(omni["channels_per_cell"], 0.01)
    return {
        "omni":           omni,
        "sectorized":     sect,
        "sectors":        sectors,
        "capacity_gain_x": round(gain, 2),
    }


def plot_reuse_pattern(N: int = 4, filename="reuse_pattern.png") -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 7))
    colours = plt.cm.Set1.colors[:max(N, 1)]
    hex_r   = 1.0
    freq_idx = 0
    for row in range(-3, 4):
        for col in range(-4, 5):
            cx = col * 1.5 * hex_r
            cy = row * np.sqrt(3) * hex_r + (col % 2) * np.sqrt(3) / 2 * hex_r
            colour = colours[freq_idx % N]
            p = mpatches.RegularPolygon((cx, cy), numVertices=6, radius=hex_r * 0.95,
                                         orientation=0, facecolor=colour,
                                         edgecolor="white", linewidth=1.5, alpha=0.8)
            ax.add_patch(p)
            ax.text(cx, cy, f"f{freq_idx % N + 1}", ha="center", va="center",
                    fontsize=8, fontweight="bold", color="white")
            freq_idx += 1
    ax.set_xlim(-6, 6); ax.set_ylim(-6, 6)
    ax.set_aspect("equal"); ax.axis("off")
    patches = [mpatches.Patch(color=colours[i], label=f"Freq group f{i+1}")
               for i in range(N)]
    ax.legend(handles=patches, loc="upper right", fontsize=9,
              title=f"N={N} Reuse Pattern")
    ax.set_title(f"Frequency Reuse — Cluster Size N={N}", fontsize=12, pad=12)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"[wireless] Saved: {path}")
    return fig


# ============================================================
# 5.  Backhaul capacity validation  (Student 2 outputs consumed here)
# ============================================================

def validate_backhaul_capacity(scenario: dict,
                                traffic_matrix,
                                load_multiplier: float = 1.0) -> list[dict]:
    """
    Cross-checks each BS→CR-1 link against:
      a) Microwave link budget  (7 GHz, scenario backhaul cfg)
      b) Traffic demand from Student 2's traffic matrix
      c) Rain attenuation in Botswana (zone H, 30 mm/h)

    Returns one row per link.
    """
    import math
    bh_cfg = scenario["backhaul"]
    sites  = scenario["sites"]
    bs_list= [s for s in sites if s["type"] == "base_station"]
    cr1    = next(s for s in sites if s["name"] == "CR-1")
    cr2    = next(s for s in sites if s["name"] == "CR-2")

    results = []
    for bs in bs_list:
        d_primary = math.hypot(bs["x_km"] - cr1["x_km"], bs["y_km"] - cr1["y_km"])
        d_backup  = math.hypot(bs["x_km"] - cr2["x_km"], bs["y_km"] - cr2["y_km"])

        # Microwave budget — primary
        mw_primary = microwave_budget(bh_cfg["frequency_ghz"], d_primary, bh_cfg)
        mw_backup  = microwave_budget(bh_cfg["frequency_ghz"], d_backup,  bh_cfg)

        # Rain attenuation
        rain_db    = rain_attenuation_db(d_primary, bh_cfg["frequency_ghz"])

        # Traffic demand from Student 2
        row = traffic_matrix[traffic_matrix["site"] == bs["name"]].iloc[0] \
              if len(traffic_matrix[traffic_matrix["site"] == bs["name"]]) > 0 \
              else None

        demand_mbps  = float(row["total_mbps"]) if row is not None else 0.0
        cap_mbps     = mw_primary["capacity_mbps"]
        utilisation  = demand_mbps / cap_mbps if cap_mbps > 0 else 0.0
        link_status  = _link_status(mw_primary["link_margin_db"],
                                     mw_primary["required_margin"], rain_db)

        results.append({
            "site":                  bs["name"],
            "primary_dist_km":       round(d_primary, 2),
            "backup_dist_km":        round(d_backup, 2),
            "primary_rx_dbm":        mw_primary["rx_power_dbm"],
            "primary_margin_db":     mw_primary["link_margin_db"],
            "primary_status":        mw_primary["status"],
            "backup_rx_dbm":         mw_backup["rx_power_dbm"],
            "backup_margin_db":      mw_backup["link_margin_db"],
            "backup_status":         mw_backup["status"],
            "rain_attenuation_db":   rain_db,
            "margin_after_rain_db":  round(mw_primary["link_margin_db"] - rain_db, 1),
            "demand_mbps":           round(demand_mbps * load_multiplier, 4),
            "capacity_mbps":         cap_mbps,
            "link_utilisation":      round(utilisation * load_multiplier, 6),
            "link_status":           link_status,
            # Student 4 fields
            "primary_link":          f"{bs['name']}→CR-1",
            "backup_link":           f"{bs['name']}→CR-2",
            "calls_routed_primary":  1 if mw_primary["status"] == "PASS" else 0,
            "calls_routed_backup":   0 if mw_primary["status"] == "PASS" else 1,
        })
    return results


def _link_status(margin_db: float, req: float, rain_db: float) -> str:
    net = margin_db - rain_db
    if net >= req:
        return "good"
    if margin_db >= req:
        return "marginal"
    return "poor"


# ============================================================
# 6.  Per-link usage plot  (Student 4 requirement)
# ============================================================

def plot_link_usage(backhaul_results: list[dict],
                    scenario: dict,
                    load_multiplier: float = 1.0,
                    filename="link_usage.png") -> plt.Figure:
    """
    Bar chart showing primary vs backup link utilisation per site,
    overlaid with capacity limit.  Required by Student 4.
    """
    sites     = [r["site"] for r in backhaul_results]
    demand    = [r["demand_mbps"] for r in backhaul_results]
    capacity  = [r["capacity_mbps"] for r in backhaul_results]
    colours   = ["#2ECC71" if r["link_status"] == "good"
                 else "#F39C12" if r["link_status"] == "marginal"
                 else "#E74C3C" for r in backhaul_results]

    x = np.arange(len(sites))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Left: demand vs capacity
    bars = ax1.bar(x, demand, color=colours, width=0.5, label="Demand (Mbps)")
    ax1.bar(x, capacity, width=0.5, bottom=0, color="none",
            edgecolor="white", linewidth=1.5, linestyle="--", label="Capacity (Mbps)")
    ax1.axhline(scenario["qos"]["utilisation_zones"]["safe"] * 100,
                color="orange", ls="--", lw=1.2, label="Safe zone 70%")
    for bar, val in zip(bars, demand):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                 f"{val:.2f}", ha="center", va="bottom", fontsize=8, color="white")
    ax1.set_xticks(x); ax1.set_xticklabels(sites)
    ax1.set_ylabel("Bandwidth (Mbps)"); ax1.set_title(f"Per-Link Demand vs Capacity (α={load_multiplier})")
    ax1.legend(fontsize=8); ax1.set_facecolor("#0d1117")

    # Right: utilisation %
    util_pct = [r["link_utilisation"] * 100 for r in backhaul_results]
    col2 = ["#2ECC71" if u < 70 else "#F39C12" if u < 90 else "#E74C3C"
            for u in util_pct]
    ax2.bar(x, util_pct, color=col2, width=0.5)
    ax2.axhline(70, color="orange", ls="--", lw=1.5, label="Safe (70%)")
    ax2.axhline(90, color="red",    ls=":",  lw=1.5, label="Action (90%)")
    for i, u in enumerate(util_pct):
        ax2.text(i, u + 0.3, f"{u:.1f}%", ha="center", va="bottom",
                 fontsize=8, color="white")
    ax2.set_xticks(x); ax2.set_xticklabels(sites)
    ax2.set_ylabel("Utilisation (%)"); ax2.set_ylim(0, 105)
    ax2.set_title("Link Utilisation per BS")
    ax2.legend(fontsize=8); ax2.set_facecolor("#0d1117")

    for ax in (ax1, ax2):
        ax.tick_params(colors="white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")
        ax.yaxis.label.set_color("white")
        ax.xaxis.label.set_color("white")
        ax.title.set_color("white")

    fig.patch.set_facecolor("#0d1117")
    plt.suptitle("Backhaul Link Usage — Primary Links (BS → CR-1)",
                 color="white", fontsize=12)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, filename)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    print(f"[wireless] Saved: {path}")
    return fig


# ============================================================
# 7.  Grade of Service summary
# ============================================================

def grade_of_service(scenario: dict,
                     teletraffic_results: dict,
                     load_multiplier: float = 1.0) -> dict:
    """
    Compute GoS metrics for output to Student 4.

    Returns:
        voice_blocking_prob  — Erlang B result per site
        video_blocking_prob  — Erlang B for video sessions
        gos_target           — from scenario
        gos_met              — bool
        worst_site           — BS with highest blocking
    """
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from src.teletraffic import erlang_b, dimension_channels

    tc = scenario["traffic"]
    target_B = tc["voice"]["kpi_blocking_prob"]

    sites = [s["name"] for s in scenario["sites"] if s["type"] == "base_station"]
    gos_rows = []
    for site in sites:
        A_voice = tc["voice"]["offered_load_erl"] * load_multiplier
        A_video = tc["video"]["offered_load_erl"] * load_multiplier
        N_voice = dimension_channels(A_voice, target_B)
        N_video = dimension_channels(A_video, target_B)
        B_voice = erlang_b(A_voice, N_voice)
        B_video = erlang_b(A_video, N_video)

        # Primary vs backup — link selection based on margin
        gos_rows.append({
            "site":              site,
            "voice_offered_erl": round(A_voice, 4),
            "voice_channels_N":  N_voice,
            "voice_blocking":    round(B_voice, 6),
            "video_offered_erl": round(A_video, 4),
            "video_channels_N":  N_video,
            "video_blocking":    round(B_video, 6),
            "gos_target":        target_B,
            "gos_met":           bool(B_voice <= target_B and B_video <= target_B),
            "link_preference":   "primary",
        })

    worst = max(gos_rows, key=lambda r: r["voice_blocking"])
    return {
        "per_site":      gos_rows,
        "gos_target":    target_B,
        "worst_site":    worst["site"],
        "worst_blocking":round(worst["voice_blocking"], 6),
        "all_gos_met":   all(r["gos_met"] for r in gos_rows),
    }


# ============================================================
# 8.  Improvement study
# ============================================================

def improvement_study(scenario: dict) -> dict:
    """
    Before/after: baseline 5 sites vs adding BS6 at south gap.
    Also tests raising antenna to 40 m.
    Uses lower grid resolution for speed.
    """
    import copy

    def run(sc):
        xs, ys, g = build_coverage_grid(sc, grid_res=80)
        return xs, ys, g, coverage_statistics(g, sc)

    xs, ys, g0, s0 = run(scenario)

    # Add BS6
    sc6 = copy.deepcopy(scenario)
    sc6["sites"].append({
        "name": "BS6", "label": "Extra Site South",
        "type": "base_station",
        "x_km": 25.0, "y_km": 2.0,
    })
    xs, ys, g6, s6 = run(sc6)

    # Raise antenna
    sc_h = copy.deepcopy(scenario)
    sc_h["environment"]["base_station_height_m"] = 40.0
    xs, ys, gh, sh = run(sc_h)

    results = {
        "baseline":       s0,
        "add_6th_site":   s6,
        "raise_height_40m": sh,
    }

    # Plot
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True)
    titles = ["Baseline (5 sites, 30 m)", "6th Site Added", "Antenna → 40 m"]
    grids  = [g0, g6, gh]
    env    = scenario["environment"]
    thr_od = env["coverage_threshold_outdoor_dbm"]
    thr_in = env["coverage_threshold_indoor_dbm"]
    norm   = mcolors.Normalize(vmin=-130, vmax=-50)

    for ax, g, ttl in zip(axes, grids, titles):
        ax.pcolormesh(xs, ys, g, cmap="RdYlGn", norm=norm, shading="auto")
        for thr, ls, col in [(thr_od, "--", "white"), (thr_in, ":", "cyan")]:
            try:
                cs = ax.contour(xs, ys, g, levels=[thr],
                                colors=[col], lw=1.8, linestyles=ls)
                ax.clabel(cs, fmt=f"{thr}", fontsize=7, colors=[col])
            except Exception:
                pass
        for bs in [s for s in scenario["sites"] if s["type"] == "base_station"]:
            ax.plot(bs["x_km"], bs["y_km"], "^w", markersize=8,
                    markeredgecolor="black")
        ax.set_title(ttl, fontsize=10)
        ax.set_xlabel("East–West (km)", fontsize=9)
    axes[0].set_ylabel("North–South (km)", fontsize=9)

    pcm = axes[-1].pcolormesh(xs, ys, grids[-1], cmap="RdYlGn", norm=norm, shading="auto")
    fig.colorbar(pcm, ax=axes[-1], label="Rx power (dBm)", pad=0.02)
    fig.suptitle("Coverage Improvement Study", fontsize=13)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, "improvement_study.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"[wireless] Saved: {path}")
    plt.close(fig)

    return results


# ============================================================
# 9.  Backbone + backhaul link budget figures
# ============================================================

def plot_backhaul_link_budget(scenario: dict,
                               filename="backhaul_link_budget.png") -> plt.Figure:
    """
    Table figure with both 7 GHz (BS links) and 13 GHz (backbone) budgets.
    Includes rain attenuation for Botswana zone H.
    """
    import math
    bh  = scenario["backhaul"]
    bb  = scenario["backbone_13ghz"]
    sites = scenario["sites"]
    cr1   = next(s for s in sites if s["name"] == "CR-1")
    cr2   = next(s for s in sites if s["name"] == "CR-2")

    # Representative longest BS link
    bs5 = next(s for s in sites if s["name"] == "BS5")
    d_bs = math.hypot(bs5["x_km"] - cr1["x_km"], bs5["y_km"] - cr1["y_km"])
    d_bb = math.hypot(cr1["x_km"] - cr2["x_km"], cr1["y_km"] - cr2["y_km"])

    mw_bs = microwave_budget(bh["frequency_ghz"], d_bs, bh)
    mw_bb = microwave_budget(bb["frequency_ghz"], d_bb, bb)
    rain_bs = rain_attenuation_db(d_bs, bh["frequency_ghz"])
    rain_bb = rain_attenuation_db(d_bb, bb["frequency_ghz"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    for ax, mw, rain, title in [
        (ax1, mw_bs, rain_bs, f"BS Link (7 GHz, {d_bs:.1f} km) — BS5→CR-1"),
        (ax2, mw_bb, rain_bb, f"Backbone (13 GHz, {d_bb:.1f} km) — CR-1↔CR-2"),
    ]:
        rows = [
            ["Frequency",            f"{mw['frequency_ghz']:.0f} GHz"],
            ["Distance",             f"{mw['distance_km']:.1f} km"],
            ["FSPL",                 f"{mw['fspl_db']:.1f} dB"],
            ["EIRP",                 f"{mw['eirp_dbm']:.1f} dBm"],
            ["Rx Power",             f"{mw['rx_power_dbm']:.1f} dBm"],
            ["Link Margin",          f"{mw['link_margin_db']:.1f} dB"],
            ["Required Margin",      f"{mw['required_margin']:.0f} dB"],
            ["Rain Att. (30 mm/h)",  f"{rain:.2f} dB"],
            ["Net Margin (rain)",    f"{mw['link_margin_db']-rain:.1f} dB"],
            ["Capacity",             f"{mw['capacity_mbps']} Mbps"],
            ["Status",               mw["status"]],
        ]
        ax.axis("off")
        tbl = ax.table(cellText=rows, colLabels=["Parameter", "Value"],
                       loc="center", cellLoc="center")
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(10)
        tbl.scale(1, 1.7)
        # Style header
        for j in range(2):
            tbl[0, j].set_facecolor("#2C3E50")
            tbl[0, j].set_text_props(color="white", fontweight="bold")
        # Colour status row
        status_row = len(rows)
        for j in range(2):
            colour = "#27AE60" if mw["status"] == "PASS" else "#E74C3C"
            tbl[status_row, j].set_facecolor(colour)
            tbl[status_row, j].set_text_props(color="white", fontweight="bold")
        ax.set_title(title, fontsize=10, pad=10)

    plt.suptitle("Microwave Backhaul Link Budget — District Telehealth Network",
                 fontsize=12, y=1.02)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, filename)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    print(f"[wireless] Saved: {path}")
    return fig


# ============================================================
# 10. JSON export (numpy-safe)
# ============================================================

class _Safe(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):   return int(obj)
        if isinstance(obj, (np.floating,)):  return float(obj)
        if isinstance(obj, (np.bool_,)):     return bool(obj)
        if isinstance(obj, np.ndarray):      return obj.tolist()
        return super().default(obj)

def export_results(data: dict, filename="wireless_results.json") -> str:
    path = os.path.join(RES_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, cls=_Safe)
    print(f"[wireless] Exported: {path}")
    return path
