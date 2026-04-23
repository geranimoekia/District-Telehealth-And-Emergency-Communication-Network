"""
qos.py
------
QoS KPI aggregation stage for the TELE 527 integration pipeline.

This stage reuses the teletraffic and backhaul analyses to produce a concise
summary of the report KPIs expected by the master pipeline.
"""

from pathlib import Path
import sys

import pandas as pd

from teletraffic import (
    dimension_voice_per_site,
    evaluate_delay_kpis,
    load_scenario,
)
from backhaul import check_all_links_pass, compute_link_budgets, compute_distances


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run(scenario: dict | None = None) -> dict:
    """Compute the top-level QoS KPIs consumed by the pipeline."""
    if scenario is None:
        scenario = load_scenario(str(Path(__file__).resolve().parent.parent / "scenario.yaml"))

    delay_df = evaluate_delay_kpis(scenario)
    voice_df = dimension_voice_per_site(scenario)
    backhaul_rows = compute_link_budgets(scenario, compute_distances(scenario))
    backhaul_check = check_all_links_pass(backhaul_rows)

    telemetry_p95 = float(
        delay_df.loc[delay_df["service_class"] == "telemetry", "p95_delay_ms"].max()
    )
    video_p95 = float(
        delay_df.loc[delay_df["service_class"] == "video", "p95_delay_ms"].max()
    )
    voice_blocking_pct = float(voice_df["achieved_blocking"].max()) * 100.0
    min_fade_margin_db = float(min(row["fade_margin_db"] for row in backhaul_rows))

    summary = {
        "telemetry_p95_ms": round(telemetry_p95, 2),
        "voice_blocking_pct": round(voice_blocking_pct, 4),
        "video_p95_ms": round(video_p95, 2),
        "min_fade_margin_db": round(min_fade_margin_db, 2),
        "all_backhaul_links_pass": bool(backhaul_check["all_pass"]),
    }

    output_dir = Path(__file__).resolve().parent.parent / "outputs"
    output_dir.mkdir(exist_ok=True)
    pd.DataFrame([summary]).to_csv(output_dir / "qos_summary.csv", index=False)

    print("=" * 70)
    print("QOS KPI SUMMARY")
    print("=" * 70)
    for key, value in summary.items():
        print(f"  {key:24s}: {value}")
    print(f"\nSaved: {output_dir / 'qos_summary.csv'}")

    return summary


if __name__ == "__main__":
    run()
