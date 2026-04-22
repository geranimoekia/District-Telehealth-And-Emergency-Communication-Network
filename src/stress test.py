"""
stress_test.py
--------------
Breaking point study for TELE 527 Group 1 - District Telehealth Network.

This module is the standalone entry point for the breaking point deliverable
(O-07 / spec §4.3 / Project Manual §11.1).

It answers two questions required by the specification:

  1. At what load multiplier alpha does each KPI first fail?
  2. Do the KPIs fail in the expected order (video FIRST, telemetry LAST)?

The computational heavy-lifting is delegated to teletraffic.stress_sweep()
which runs the full Erlang B + M/M/1 analysis at each alpha in
scenario.simulation.load_multiplier_steps with FIXED baseline capacity
(dimensioned at alpha = 1.0).

Public API
----------
  per_class_breaking_point(scenario) -> dict
        alpha_fail_voice / video / telemetry  + raw sweep DataFrame
  test_failure_order(scenario)       -> None
        Assertion: alpha_fail_video <= alpha_fail_voice <= alpha_fail_telemetry
  breaking_point_report(scenario)    -> dict
        Formatted summary + sweep table for the report

Student 2 responsibility - Traffic and Teletraffic Lead
TELE 527 | Group 1 | BIUST | 2026
"""

import math
import os
import numpy as np
import pandas as pd
import yaml


# -----------------------------------------------------------------------
# Scenario loader (mirrors traffic.py / teletraffic.py for standalone use)
# -----------------------------------------------------------------------

def load_scenario(path: str = "scenario.yaml") -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# -----------------------------------------------------------------------
# Per-class alpha at first failure
# -----------------------------------------------------------------------

def _first_fail_alpha(sweep: pd.DataFrame, kpi_col: str) -> float:
    """
    Return the smallest alpha for which the KPI boolean column is False.
    Returns +inf if the KPI never fails within the swept range.
    """
    failing = sweep[~sweep[kpi_col]]
    if failing.empty:
        return float("inf")
    return float(failing["load_multiplier"].iloc[0])


def per_class_breaking_point(scenario: dict) -> dict:
    """
    Run the stress sweep (delegated to teletraffic.stress_sweep) and extract
    the first-failure alpha per traffic class, plus the overall first
    failure.

    Returns
    -------
    dict with keys:
        sweep                : pd.DataFrame   full sweep table
        alpha_fail_voice     : float          first alpha where voice blocking > 2%
        alpha_fail_video     : float          first alpha where video P95 > 150 ms
        alpha_fail_telemetry : float          first alpha where tel P95 > 50 ms
        first_failing_class  : str            'voice' | 'video' | 'telemetry'
        first_failing_alpha  : float
        failure_order        : list[str]      classes ordered by fail alpha asc
        all_kpis_met_alphas  : list[float]    alphas where all KPIs still pass
    """
    from teletraffic import stress_sweep

    sweep = stress_sweep(scenario)

    a_voice = _first_fail_alpha(sweep, "voice_kpi_met")
    a_video = _first_fail_alpha(sweep, "video_kpi_met")
    a_tel   = _first_fail_alpha(sweep, "telemetry_kpi_met")

    per_class = {
        "voice":     a_voice,
        "video":     a_video,
        "telemetry": a_tel,
    }
    # Sort ascending by failure alpha (lowest = first to fail)
    failure_order = sorted(per_class, key=lambda k: per_class[k])

    first_class = failure_order[0]
    first_alpha = per_class[first_class]

    safe_alphas = sweep.loc[sweep["all_kpis_met"], "load_multiplier"].tolist()

    return {
        "sweep":                sweep,
        "alpha_fail_voice":     a_voice,
        "alpha_fail_video":     a_video,
        "alpha_fail_telemetry": a_tel,
        "first_failing_class":  first_class,
        "first_failing_alpha":  first_alpha,
        "failure_order":        failure_order,
        "all_kpis_met_alphas":  safe_alphas,
    }


# -----------------------------------------------------------------------
# Required assertion (spec §4.4)
# -----------------------------------------------------------------------

def test_failure_order(scenario: dict) -> None:
    """
    Verify the spec-mandated failure ordering:
        video fails first → voice next → telemetry last.

    Rationale: telemetry runs at strict priority (DSCP 46 / EF), voice uses
    WFQ weight 0.30 of the link, and video uses WFQ weight 0.40. Video has
    the highest arrival rate in Mbps relative to its WFQ share, so its P95
    delay crosses the 150 ms target before voice blocking crosses 2%, and
    telemetry — protected by strict priority — is the last to fail.

    Formal assertion:
        alpha_fail_video    <= alpha_fail_voice
        alpha_fail_voice    <= alpha_fail_telemetry
    """
    bp = per_class_breaking_point(scenario)

    a_video = bp["alpha_fail_video"]
    a_voice = bp["alpha_fail_voice"]
    a_tel   = bp["alpha_fail_telemetry"]

    assert a_video <= a_voice, (
        f"Video must fail before voice. Got alpha_fail_video = {a_video}, "
        f"alpha_fail_voice = {a_voice}."
    )
    assert a_voice <= a_tel, (
        f"Voice must fail before telemetry. Got alpha_fail_voice = {a_voice}, "
        f"alpha_fail_telemetry = {a_tel}."
    )
    # Combined form per spec checklist
    assert a_tel > a_video, (
        f"Telemetry must survive longer than video. "
        f"alpha_fail_telemetry = {a_tel}, alpha_fail_video = {a_video}."
    )


# -----------------------------------------------------------------------
# Report-ready summary
# -----------------------------------------------------------------------

def breaking_point_report(scenario: dict) -> dict:
    """
    Build a report-ready breaking point analysis combining the per-class
    failure alphas, the safe operating envelope, and a plain-text
    bottleneck description.

    Returns
    -------
    dict with keys:
        sweep, alpha_fail_voice, alpha_fail_video, alpha_fail_telemetry,
        first_failing_class, first_failing_alpha, failure_order,
        n_baseline, bottleneck_description, ordered_summary,
        per_alpha_worst_class
    """
    from teletraffic import find_breaking_point, _baseline_channel_count

    bp     = per_class_breaking_point(scenario)
    fp     = find_breaking_point(scenario)
    N_base = _baseline_channel_count(scenario)

    def _fmt_alpha(a):
        return f"{a:.2f}" if math.isfinite(a) else ">5.0 (never fails)"

    ordered = " → ".join(
        f"{cls} (α={_fmt_alpha(bp[f'alpha_fail_{cls}'])})"
        for cls in bp["failure_order"]
    )

    # Build a per-alpha worst-class summary (Requirement 4)
    sweep = bp["sweep"]
    per_alpha = []
    for _, row in sweep.iterrows():
        if not row["video_kpi_met"]:
            worst = "video (P95 delay saturated — WFQ backhaul bottleneck)"
        elif not row["voice_kpi_met"]:
            worst = "voice (blocking > 2% — circuit pool exhausted)"
        elif not row["telemetry_kpi_met"]:
            worst = "telemetry (P95 delay — strict-priority link saturated)"
        else:
            worst = "none (all KPIs pass)"
        per_alpha.append({
            "alpha":              row["load_multiplier"],
            "worst_class":        worst,
            "all_kpis_met":       row["all_kpis_met"],
        })

    desc = fp["bottleneck_description"]

    return {
        "sweep":                  bp["sweep"],
        "alpha_fail_voice":       bp["alpha_fail_voice"],
        "alpha_fail_video":       bp["alpha_fail_video"],
        "alpha_fail_telemetry":   bp["alpha_fail_telemetry"],
        "first_failing_class":    bp["first_failing_class"],
        "first_failing_alpha":    bp["first_failing_alpha"],
        "failure_order":          bp["failure_order"],
        "n_baseline":             N_base,
        "bottleneck_description": desc,
        "ordered_summary":        ordered,
        "per_alpha_worst_class":  per_alpha,
    }


# -----------------------------------------------------------------------
# Standalone demo (runnable:  python stress_test.py)
# -----------------------------------------------------------------------

if __name__ == "__main__":
    scenario_path = os.path.join(os.path.dirname(__file__), "..", "scenario.yaml")
    sc = load_scenario(scenario_path)

    print("=" * 70)
    print("BREAKING POINT STRESS SWEEP")
    print("=" * 70)
    rep = breaking_point_report(sc)
    print(rep["sweep"].to_string(index=False))

    print("\n" + "=" * 70)
    print("REQUIREMENT 1 & 2 — First failing KPI and exact alpha")
    print("=" * 70)
    print(f"  First failing class  : {rep['first_failing_class']}")
    print(f"  First failing alpha  : {rep['first_failing_alpha']}")
    print(f"  alpha_fail_video     : {rep['alpha_fail_video']}")
    print(f"  alpha_fail_voice     : {rep['alpha_fail_voice']}")
    print(f"  alpha_fail_telemetry : {rep['alpha_fail_telemetry']}")

    print("\n" + "=" * 70)
    print("REQUIREMENT 3 — First bottleneck (link / resource)")
    print("=" * 70)
    print(f"  {rep['bottleneck_description']}")

    print("\n" + "=" * 70)
    print("REQUIREMENT 4 — Worst class at each alpha step")
    print("=" * 70)
    for row in rep["per_alpha_worst_class"]:
        status = "ALL PASS" if row["all_kpis_met"] else "KPI FAIL"
        print(f"  alpha={row['alpha']:.2f}  [{status}]  worst: {row['worst_class']}")

    print("\n" + "=" * 70)
    print("CRITICAL REQUIREMENT — failure order (video → voice → telemetry)")
    print("=" * 70)
    print(f"  {rep['ordered_summary']}")
    try:
        test_failure_order(sc)
        print("  [PASS] Telemetry is last — QoS scheduler correctly configured.")
    except AssertionError as e:
        print(f"  [FAIL] {e}")

    # --- CSV export --------------------------------------------------
    out_dir = os.path.join(os.path.dirname(__file__), "..", "outputs")
    os.makedirs(out_dir, exist_ok=True)

    rep["sweep"].to_csv(
        os.path.join(out_dir, "stress_test_sweep.csv"), index=False
    )
    pd.DataFrame([{
        "alpha_fail_voice":     rep["alpha_fail_voice"],
        "alpha_fail_video":     rep["alpha_fail_video"],
        "alpha_fail_telemetry": rep["alpha_fail_telemetry"],
        "first_failing_class":  rep["first_failing_class"],
        "first_failing_alpha":  rep["first_failing_alpha"],
        "n_baseline":           rep["n_baseline"],
        "bottleneck":           rep["bottleneck_description"],
    }]).to_csv(
        os.path.join(out_dir, "stress_test_per_class_failure.csv"), index=False
    )
    pd.DataFrame(rep["per_alpha_worst_class"]).to_csv(
        os.path.join(out_dir, "stress_test_worst_class_per_alpha.csv"), index=False
    )
    print("\nCSV files saved to outputs/:")
    for name in [
        "stress_test_sweep.csv",
        "stress_test_per_class_failure.csv",
        "stress_test_worst_class_per_alpha.csv",
    ]:
        print(f"  {name}")