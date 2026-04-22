"""
run_pipeline.py
===============
Student 3 — Wireless Planning Lead | TELE 527 Group 1

Full integrated pipeline. Reads Student 2 outputs and produces all
wireless planning deliverables.

Steps:
  1  Load scenario.yaml and Student 2 modules
  2  Compute traffic matrix from Student 2 (traffic.py)
  3  Run teletraffic analysis from Student 2 (teletraffic.py)
  4  Propagation model comparison + path loss curves
  5  Build 50 km coverage grid
  6  Coverage statistics (outdoor + indoor thresholds)
  7  Coverage heatmap figure
  8  Per-site link budget table (screenshot fields)
  9  Backhaul capacity validation (cross-checks Student 2 traffic)
 10  Frequency reuse + sectorization
 11  Grade of Service for Student 4
 12  Signaling summary
 13  Improvement study (before/after)
 14  Backhaul link budget table
 15  Export all results to JSON
"""

import os
import sys
import yaml
import json

SRC_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SRC_DIR, ".."))
for path in (PROJECT_ROOT, SRC_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
from traffic      import load_scenario, compute_traffic_matrix, compute_trunk_demand
from teletraffic  import (run_teletraffic, compute_signaling_load,
                           signaling_summary, stress_sweep, find_breaking_point)
from propagation  import site_link_budget_table
from src.wireless import (
    build_coverage_grid, coverage_statistics, plot_coverage_heatmap,
    plot_path_loss_curves, frequency_reuse_cluster, sectorization_analysis,
    plot_reuse_pattern, validate_backhaul_capacity, plot_link_usage,
    grade_of_service, improvement_study, plot_backhaul_link_budget,
    export_results,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def get_scenario_file_path() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    candidates = [
        os.path.join(here, "scenario.yaml"),
        os.path.join(here, "..", "scenario.yaml"),
        os.path.join(os.getcwd(), "scenario.yaml"),
    ]
    for candidate in candidates:
        candidate_abspath = os.path.abspath(candidate)
        if os.path.isfile(candidate_abspath):
            return candidate_abspath
    searched = "\n".join([os.path.abspath(c) for c in candidates])
    raise FileNotFoundError(
        "Unable to locate scenario.yaml. Searched:\n" + searched
    )

SCENARIO = get_scenario_file_path()


def _h(title):
    print("\n" + "═"*62)
    print(f"  {title}")
    print("═"*62)


def _kv(data: dict):
    for k, v in data.items():
        print(f"    {k:<35}: {v}")


if __name__ == "__main__":
    print("\n" + "█"*62)
    print("  TELE 527 — Wireless Planning Pipeline  |  Student 3")
    print("  Group 1 | District Telehealth & Emergency Network")
    print("█"*62)

    # ── 1. Config ──────────────────────────────────────────────
    _h("STEP 1 — Load scenario")
    sc = load_scenario(SCENARIO)
    print(f"  Sites: {[s['name'] for s in sc['sites']]}")
    print(f"  District: {sc['environment']['district_size_km']} km")
    print(f"  Frequency: {sc['environment']['carrier_frequency_mhz']} MHz")

    # ── 2. Student 2 traffic ───────────────────────────────────
    _h("STEP 2 — Student 2: Traffic matrix")
    traffic_df = compute_traffic_matrix(sc, load_multiplier=1.0)
    trunk      = compute_trunk_demand(sc)
    print(traffic_df.to_string(index=False))
    print(f"\n  Worst link utilisation: {trunk['worst_link_utilisation']*100:.4f}%")
    print(f"  Aggregate demand:       {trunk['aggregate_total_mbps']:.4f} Mbps")

    # ── 3. Student 2 teletraffic ───────────────────────────────
    _h("STEP 3 — Student 2: Teletraffic analysis")
    tt = run_teletraffic(sc, load_multiplier=1.0)
    print(tt["dimensioning_table"].to_string(index=False))
    print(f"\n  Breaking point: alpha={tt['breaking_point']['first_failure_alpha']:.1f}")
    print(f"  First KPI fail: {tt['breaking_point']['first_failure_kpi']}")

    # ── 4. Path-loss curves ────────────────────────────────────
    _h("STEP 4 — Propagation: Path-loss model comparison")
    plot_path_loss_curves(sc)

    # ── 5. Coverage grid ───────────────────────────────────────
    _h("STEP 5 — Build 50 km coverage grid (may take ~30 s)")
    xs, ys, grid = build_coverage_grid(sc, grid_res=120)
    print(f"  Grid: {grid.shape}  max={grid.max():.1f} dBm  min={grid.min():.1f} dBm")

    # ── 6. Coverage stats ──────────────────────────────────────
    _h("STEP 6 — Coverage statistics")
    cov_stats = coverage_statistics(grid, sc)
    _kv(cov_stats)

    # ── 7. Heatmap ─────────────────────────────────────────────
    _h("STEP 7 — Coverage heatmap")
    plot_coverage_heatmap(xs, ys, grid, sc)

    # ── 8. Per-site link budget (screenshot fields) ────────────
    _h("STEP 8 — Per-site link budget table (Student 3 → Student 4 interface)")
    lb_table = site_link_budget_table(sc)
    lb_df = pd.DataFrame(lb_table)
    print(lb_df.to_string(index=False))
    # Save as CSV (screenshot format)
    csv_path = os.path.join(os.path.dirname(__file__), "results", "coverage_propagation.csv")
    lb_df.to_csv(csv_path, index=False)
    print(f"\n  CSV exported: {csv_path}")

    # ── 9. Backhaul capacity validation ───────────────────────
    _h("STEP 9 — Backhaul capacity validation")
    bh_results = validate_backhaul_capacity(sc, traffic_df, load_multiplier=1.0)
    bh_df = pd.DataFrame(bh_results)
    print(bh_df[["site","primary_dist_km","primary_margin_db","primary_status",
                  "rain_attenuation_db","margin_after_rain_db",
                  "demand_mbps","link_utilisation","link_status"]].to_string(index=False))
    plot_link_usage(bh_results, sc, load_multiplier=1.0)

    # ── 10. Frequency reuse + sectorization ───────────────────
    _h("STEP 10 — Frequency reuse & sectorization")
    reuse = frequency_reuse_cluster(N=4, total_bw_mhz=20, ch_bw_mhz=5)
    sect  = sectorization_analysis(N=4, sectors=3, total_bw=20, ch_bw=5)
    _kv(reuse)
    print(f"  Capacity gain (3-sector): ×{sect['capacity_gain_x']}")
    plot_reuse_pattern(N=4)

    # ── 11. Grade of Service → Student 4 ──────────────────────
    _h("STEP 11 — Grade of Service (GoS) for Student 4")
    gos = grade_of_service(sc, tt, load_multiplier=1.0)
    print(pd.DataFrame(gos["per_site"]).to_string(index=False))
    print(f"\n  Worst site:    {gos['worst_site']}")
    print(f"  Worst blocking: {gos['worst_blocking']:.6f}")
    print(f"  GoS target:    {gos['gos_target']}")
    print(f"  All GoS met:   {gos['all_gos_met']}")

    # ── 12. Signaling summary → Student 4 ─────────────────────
    _h("STEP 12 — Call setup & signaling (Student 4 feed)")
    sig_df  = compute_signaling_load(sc, load_multiplier=1.0)
    sig_sum = signaling_summary(sc, load_multiplier=1.0)
    print(sig_df.to_string(index=False))
    print()
    _kv(sig_sum)

    # ── 13. Improvement study ──────────────────────────────────
    _h("STEP 13 — Coverage improvement study")
    improve = improvement_study(sc)
    for scenario_name, stats in improve.items():
        print(f"  {scenario_name:<25}: outdoor={stats['outdoor_pct']}%  indoor={stats['indoor_pct']}%")

    # ── 14. Backhaul link budget figures ──────────────────────
    _h("STEP 14 — Microwave backhaul link budget")
    plot_backhaul_link_budget(sc)

    # ── 15. Stress sweep (breaking point from Student 2) ──────
    _h("STEP 15 — Stress sweep & breaking point")
    sweep = stress_sweep(sc)
    print(sweep.to_string(index=False))
    bp    = find_breaking_point(sc)
    print(f"\n  Breaking point: alpha={bp['first_failure_alpha']:.1f}")
    print(f"  {bp['bottleneck_description']}")

    # ── Export everything ──────────────────────────────────────
    _h("STEP 16 — Export results JSON")
    all_results = {
        "coverage_statistics":  cov_stats,
        "site_link_budgets":    lb_table,
        "backhaul_validation":  bh_results,
        "frequency_reuse":      reuse,
        "sectorization":        sect,
        "grade_of_service":     gos,
        "signaling":            sig_sum,
        "improvement_study":    improve,
        "breaking_point":       {k: (float(v) if hasattr(v, 'item') else v)
                                 for k, v in bp.items()},
    }
    export_results(all_results)

    print("\n" + "█"*62)
    print("  PIPELINE COMPLETE — All 15 deliverables generated.")
    print(f"  Figures: ./figures/   Results: ./results/")
    print("█"*62 + "\n")
