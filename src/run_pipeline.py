"""
run_pipeline.py
===============
Student 3 — Wireless Planning Lead | TELE 527 Group 1

Master execution script.  Run this once to produce ALL required deliverables:

  Step 1 — Load scenario YAML config
  Step 2 — Propagation model self-test & path-loss curves
  Step 3 — Build 5-site coverage grid
  Step 4 — Coverage statistics at two thresholds
  Step 5 — Coverage heatmap figure
  Step 6 — Frequency reuse analysis + cluster visualisation
  Step 7 — Sectorization analysis (omni vs 3-sector)
  Step 8 — Improvement study (before/after)
  Step 9 — Microwave backhaul link budget
  Step 10 — Export all results to JSON

Usage:
  python run_pipeline.py

All figures saved to  ./figures/
All results saved to  ./results/
"""

import os
import sys
import yaml
import json

# ── ensure local modules are importable ──────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from propagation import (
    cost231_extension, received_power_dbm, path_loss_vs_distance
)
from wireless import (
    build_coverage_grid,
    coverage_statistics,
    plot_coverage_heatmap,
    plot_path_loss_curves,
    frequency_reuse_cluster,
    sectorization_analysis,
    plot_reuse_pattern,
    improvement_study,
    microwave_link_budget,
    export_results,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCENARIO_FILE = os.path.join(os.path.dirname(__file__), "scenario.yaml")


# =============================================================================
# Helper: pretty-print a dict as a table
# =============================================================================

def _print_table(title: str, data: dict, indent: int = 2):
    pad = " " * indent
    print(f"\n  ┌─ {title}")
    for k, v in data.items():
        print(f"  {pad}{k:<30}: {v}")
    print()


# =============================================================================
# STEP 1 — Load config
# =============================================================================

def step1_load_config() -> dict:
    print("\n" + "═" * 60)
    print("  STEP 1 — Loading scenario configuration")
    print("═" * 60)
    with open(SCENARIO_FILE) as f:
        cfg = yaml.safe_load(f)
    print(f"  Scenario : {cfg['scenario']['name']}")
    print(f"  Group    : {cfg['scenario']['group']}")
    print(f"  Role     : {cfg['scenario']['student_role']}")
    return cfg


# =============================================================================
# STEP 2 — Path-loss model curves
# =============================================================================

def step2_path_loss_curves(cfg: dict):
    print("\n" + "═" * 60)
    print("  STEP 2 — Path-loss model comparison")
    print("═" * 60)
    wl = cfg["wireless"]
    plot_path_loss_curves(
        f_mhz  = wl["frequency_mhz"],
        h_base = wl["antenna"]["base_height_m"],
    )

    # quick sanity check at key distances
    print("  Path-loss spot checks (COST 231):")
    for d in [1, 2, 5, 10, 15]:
        pl = cost231_extension(d, wl["frequency_mhz"],
                               wl["antenna"]["base_height_m"])
        rp = received_power_dbm(wl["antenna"]["tx_power_dbm"],
                                wl["antenna"]["tx_gain_dbi"],
                                wl["antenna"]["rx_gain_dbi"],
                                pl)
        flag = "✓" if rp > -95 else "✗"
        print(f"    {d:>4} km  PL={pl:.1f} dB  Prx={rp:.1f} dBm  {flag}")


# =============================================================================
# STEP 3 & 4 — Coverage grid + statistics
# =============================================================================

def step3_coverage_grid(cfg: dict) -> tuple:
    print("\n" + "═" * 60)
    print("  STEP 3 — Building 5-site coverage grid (may take ~20 s)")
    print("═" * 60)
    wl  = cfg["wireless"]
    ant = wl["antenna"]

    sites = [(s["x"], s["y"]) for s in wl["sites"]]
    names = [s["name"] for s in wl["sites"]]

    xs, ys, grid = build_coverage_grid(
        sites,
        grid_res      = wl["grid_resolution"],
        area_km       = wl["area_km"],
        tx_power_dbm  = ant["tx_power_dbm"],
        tx_gain_dbi   = ant["tx_gain_dbi"],
        rx_gain_dbi   = ant["rx_gain_dbi"],
        f_mhz         = wl["frequency_mhz"],
        h_base        = ant["base_height_m"],
        h_mobile      = ant["mobile_height_m"],
    )
    print(f"  Grid shape : {grid.shape}  |  Max Prx: {grid.max():.1f} dBm  |  Min Prx: {grid.min():.1f} dBm")
    return xs, ys, grid, sites, names


def step4_coverage_stats(grid, thresholds: list) -> dict:
    print("\n" + "═" * 60)
    print("  STEP 4 — Coverage statistics")
    print("═" * 60)
    stats = coverage_statistics(grid, thresholds)
    for thr, pct in stats.items():
        label = "Good (voice/video)" if thr == -85 else "Edge (telemetry)"
        print(f"    Coverage ≥ {thr} dBm  [{label}]  :  {pct:.1f}%")
    return stats


# =============================================================================
# STEP 5 — Heatmap figure
# =============================================================================

def step5_heatmap(xs, ys, grid, sites, names, thresholds, cfg: dict):
    print("\n" + "═" * 60)
    print("  STEP 5 — Generating coverage heatmap")
    print("═" * 60)
    plot_coverage_heatmap(
        xs, ys, grid,
        sites          = sites,
        site_names     = names,
        thresholds_dbm = thresholds,
    )
    print("  Threshold justification:")
    print("    −85 dBm → LTE Reference Signal Received Power (RSRP) target")
    print("             for reliable voice + video (3GPP TS 36.213)")
    print("    −95 dBm → Minimum RSRP for telemetry / LPWAN-grade link")


# =============================================================================
# STEP 6 — Frequency reuse
# =============================================================================

def step6_reuse(cfg: dict) -> dict:
    print("\n" + "═" * 60)
    print("  STEP 6 — Frequency reuse analysis")
    print("═" * 60)
    N = cfg["wireless"]["reuse"]["factor"]
    reuse = frequency_reuse_cluster(N)
    _print_table(f"Reuse N={N}", reuse)
    plot_reuse_pattern(N)
    return reuse


# =============================================================================
# STEP 7 — Sectorization
# =============================================================================

def step7_sectorization(cfg: dict) -> dict:
    print("\n" + "═" * 60)
    print("  STEP 7 — Sectorization analysis (omni vs 3-sector)")
    print("═" * 60)
    N = cfg["wireless"]["reuse"]["factor"]
    S = cfg["wireless"]["reuse"]["sectors"]
    result = sectorization_analysis(N, S)
    print(f"  Omni config:      {result['omni']['note']}")
    print(f"  Sectorized ({S}S):  {result['sectorized']['note']}")
    print(f"  Capacity gain  :  ×{result['capacity_gain_x']}")
    print(f"  Summary        :  {result['summary']}")
    return result


# =============================================================================
# STEP 8 — Improvement study
# =============================================================================

def step8_improvement(xs, ys, grid, sites, cfg: dict) -> dict:
    print("\n" + "═" * 60)
    print("  STEP 8 — Coverage improvement study (before / after)")
    print("═" * 60)
    wl  = cfg["wireless"]
    ant = wl["antenna"]
    scenario_cfg = {
        "grid_res":      min(wl["grid_resolution"], 100),  # smaller for speed
        "area_km":       wl["area_km"],
        "tx_power_dbm":  ant["tx_power_dbm"],
        "tx_gain_dbi":   ant["tx_gain_dbi"],
        "rx_gain_dbi":   ant["rx_gain_dbi"],
        "f_mhz":         wl["frequency_mhz"],
        "h_base":        ant["base_height_m"],
        "h_mobile":      ant["mobile_height_m"],
        "system_losses": 2.0,
        "thresholds":    wl["coverage_thresholds_dbm"],
    }
    results = improvement_study(sites, scenario_cfg)
    print("\n  Coverage results summary:")
    for scenario, stats in results.items():
        print(f"    {scenario:<25}  →  {stats}")
    return results


# =============================================================================
# STEP 9 — Backhaul link budget
# =============================================================================

def step9_link_budget(cfg: dict) -> dict:
    print("\n" + "═" * 60)
    print("  STEP 9 — Microwave backhaul link budget")
    print("═" * 60)
    bh = cfg["backhaul"]
    budget = microwave_link_budget(
        freq_ghz         = bh["frequency_ghz"],
        distance_km      = bh["distance_km"],
        tx_power_dbm     = bh["tx_power_dbm"],
        tx_gain_dbi      = bh["tx_antenna_gain_dbi"],
        rx_gain_dbi      = bh["rx_antenna_gain_dbi"],
        system_losses_db = bh["system_losses_db"],
        fade_margin_db   = bh["fade_margin_db"],
        rx_threshold_dbm = bh["rx_sensitivity_dbm"],
    )
    _print_table("Link Budget Result", budget)
    return budget


# =============================================================================
# STEP 10 — Export all results
# =============================================================================

def step10_export(all_results: dict):
    print("\n" + "═" * 60)
    print("  STEP 10 — Exporting results to JSON")
    print("═" * 60)
    export_results(all_results, "wireless_results.json")
    print("  Done. All figures in ./figures/  |  Results in ./results/")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("\n" + "█" * 60)
    print("  TELE 527 — Wireless Planning Pipeline")
    print("  Student 3 | Group 1 | District Telehealth Network")
    print("█" * 60)

    cfg = step1_load_config()
    wl  = cfg["wireless"]
    thresholds = wl["coverage_thresholds_dbm"]

    step2_path_loss_curves(cfg)

    xs, ys, grid, sites, names = step3_coverage_grid(cfg)
    cov_stats   = step4_coverage_stats(grid, thresholds)
    step5_heatmap(xs, ys, grid, sites, names, thresholds, cfg)
    reuse_data  = step6_reuse(cfg)
    sector_data = step7_sectorization(cfg)
    improve     = step8_improvement(xs, ys, grid, sites, cfg)
    budget      = step9_link_budget(cfg)

    # Consolidate and export
    all_results = {
        "coverage_statistics":  cov_stats,
        "frequency_reuse":      reuse_data,
        "sectorization":        sector_data,
        "improvement_study":    improve,
        "backhaul_link_budget": budget,
    }
    step10_export(all_results)

    print("\n" + "█" * 60)
    print("  PIPELINE COMPLETE — All deliverables generated.")
    print("█" * 60 + "\n")
