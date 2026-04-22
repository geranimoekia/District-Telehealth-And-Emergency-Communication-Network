"""
plots_extra.py
--------------
Additional report figures for TELE 527 Group 1, complementing plots.py.

These cover the three spec-required plots (§4.5) that were not yet in
plots.py:

  1. fig_telemetry_delay_cdf     - CDF of telemetry delay with P99 marker
                                   and the 50 ms target line
  2. fig_video_delay_histogram   - Histogram of video session delay with
                                   P95 marker and the 150 ms target line
  3. fig_forecast_per_class      - 36-month Mbps projection per class,
                                   with planning (70%) and action (90%)
                                   trigger lines
  4. fig_strategy_comparison     - Bar chart of upgrade strategies ranked
                                   by cost per extended month

All figures follow the same style/palette as plots.py.

Student 2 responsibility - Traffic and Teletraffic Lead
TELE 527 | Group 1 | BIUST | 2026
"""

import os
import math
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import yaml


matplotlib.rcParams.update({
    "font.size":       10,
    "axes.titlesize":  11,
    "axes.labelsize":  10,
    "legend.fontsize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "figure.dpi":      120,
    "axes.grid":       True,
    "grid.alpha":      0.35,
    "lines.linewidth": 1.8,
})

COLOURS = {
    "telemetry": "#2196F3",  # blue
    "voice":     "#4CAF50",  # green
    "video":     "#FF9800",  # orange
    "trunk":     "#9C27B0",  # purple
    "plan":      "#FF9800",  # orange dashed
    "act":       "#F44336",  # red dashed
    "target":    "#D32F2F",  # red solid
}


def load_scenario(path: str = "scenario.yaml") -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# -----------------------------------------------------------------------
# Figure 1 - Telemetry delay CDF (P99 < 50 ms)
# -----------------------------------------------------------------------

def fig_telemetry_delay_cdf(
    scenario: dict,
    n_samples: int = 20_000,
) -> plt.Figure:
    """
    CDF of end-to-end telemetry delay aggregated over all BS sites, with
    the P99 value and the 50 ms KPI target line marked.

    Uses a two-panel layout when the KPI target sits far beyond the data
    range: the top panel is tight around the observed samples, the bottom
    panel zooms out to include the KPI line.
    """
    from delay_samples import sample_telemetry_delays

    tel_target = scenario["traffic"]["telemetry"]["kpi_delay_p95_ms"]  # 50 ms

    samples = sample_telemetry_delays(scenario, n_samples=n_samples, alpha=1.0)
    samples = np.sort(samples[np.isfinite(samples)])
    cdf     = np.arange(1, len(samples) + 1) / len(samples)

    p95 = float(np.percentile(samples, 95))
    p99 = float(np.percentile(samples, 99))

    # Tight range for the observed data
    data_upper     = max(p99 * 1.15, samples[-1] * 1.02)
    use_two_panels = data_upper < tel_target * 0.5

    def _draw_cdf(ax, x_upper, show_kpi: bool):
        ax.plot(samples, cdf, color=COLOURS["telemetry"],
                label="Telemetry delay CDF")
        ax.axvline(p95, color="gray", linestyle=":", linewidth=1.2,
                   label=f"P95 = {p95:.1f} ms")
        ax.axvline(p99, color=COLOURS["telemetry"], linestyle="--", linewidth=1.4,
                   label=f"P99 = {p99:.1f} ms")
        if show_kpi:
            ax.axvline(tel_target, color=COLOURS["target"], linestyle="--",
                       linewidth=1.4, label=f"KPI target = {tel_target} ms")
        ax.axhline(0.95, color="gray", linestyle=":", linewidth=0.8, alpha=0.6)
        ax.axhline(0.99, color="gray", linestyle=":", linewidth=0.8, alpha=0.6)
        ax.set_xlim(0, x_upper)
        ax.set_ylim(0, 1.01)
        ax.set_ylabel("Cumulative probability")

    if use_two_panels:
        fig, (ax_top, ax_bot) = plt.subplots(
            2, 1, figsize=(7.5, 5.8),
            gridspec_kw={"height_ratios": [3, 2]}
        )
        _draw_cdf(ax_top, data_upper, show_kpi=False)
        ax_top.set_title(
            "Telemetry Delay CDF — P99 vs 50 ms KPI\n"
            "(top: data detail · bottom: zoom out to KPI line)"
        )
        ax_top.legend(loc="lower right", fontsize=8)

        _draw_cdf(ax_bot, tel_target * 1.5, show_kpi=True)
        ax_bot.set_xlabel("End-to-end delay (ms)")
        margin = tel_target - p99
        ax_bot.text(
            tel_target * 0.05, 0.15,
            f"Safety margin\nP99 → KPI\n= {margin:.0f} ms",
            fontsize=8, color="#555", va="center",
        )
        ax_bot.legend(loc="lower right", fontsize=8)
    else:
        x_upper = max(tel_target * 1.5, p99 * 1.1)
        fig, ax = plt.subplots(figsize=(7.5, 4.5))
        _draw_cdf(ax, x_upper, show_kpi=True)
        ax.set_xlabel("End-to-end delay (ms)")
        ax.set_title(
            "Telemetry Delay CDF — P99 vs 50 ms KPI\n"
            "(aggregated over all 5 base stations, α = 1.0)"
        )
        ax.legend(loc="lower right")

    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------
# Figure 2 - Video delay histogram (P95 < 150 ms)
# -----------------------------------------------------------------------

def fig_video_delay_histogram(
    scenario: dict,
    n_samples: int = 20_000,
) -> plt.Figure:
    """
    Histogram of per-session video delay with P95 and the 150 ms KPI target.

    Uses a two-panel layout when the KPI is far from the data: the top
    panel shows the data distribution tightly; the bottom panel zooms out
    to include the KPI line for context.
    """
    from delay_samples import sample_video_delays

    vid_target = scenario["traffic"]["video"]["kpi_delay_p95_ms"]   # 150 ms
    samples    = sample_video_delays(scenario, n_samples=n_samples, alpha=1.0)
    samples    = samples[np.isfinite(samples)]

    p95  = float(np.percentile(samples, 95))
    p99  = float(np.percentile(samples, 99))
    mean = float(np.mean(samples))

    # Tight x-range for the actual data
    data_upper = max(p99 * 1.15, samples.max() * 1.02)
    # If the KPI is far away, use two panels; otherwise one
    use_two_panels = data_upper < vid_target * 0.5

    if use_two_panels:
        fig, (ax_top, ax_bot) = plt.subplots(
            2, 1, figsize=(7.5, 5.8),
            gridspec_kw={"height_ratios": [3, 1]}
        )

        # --- Top panel: tight histogram zoom ---
        ax_top.hist(samples[samples <= data_upper], bins=60,
                    color=COLOURS["video"], alpha=0.80, edgecolor="white",
                    label=f"Video session delay (n = {len(samples):,})")
        ax_top.axvline(mean, color="gray", linestyle=":", linewidth=1.2,
                       label=f"Mean = {mean:.1f} ms")
        ax_top.axvline(p95,  color=COLOURS["video"], linestyle="--", linewidth=1.4,
                       label=f"P95 = {p95:.1f} ms")
        ax_top.axvline(p99,  color="#B71C1C", linestyle=":", linewidth=1.2,
                       label=f"P99 = {p99:.1f} ms")
        ax_top.set_xlim(0, data_upper)
        ax_top.set_ylabel("Count")
        ax_top.set_title(
            "Video Session Delay Histogram — P95 vs 150 ms KPI\n"
            "(top: data detail · bottom: zoom out to KPI line)"
        )
        ax_top.legend(loc="upper right", fontsize=8)

        # --- Bottom panel: full scale with KPI line ---
        ax_bot.hist(samples, bins=80,
                    color=COLOURS["video"], alpha=0.80, edgecolor="white")
        ax_bot.axvline(p95, color=COLOURS["video"], linestyle="--", linewidth=1.4)
        ax_bot.axvline(vid_target, color=COLOURS["target"], linestyle="--",
                       linewidth=1.6, label=f"KPI target = {vid_target} ms")
        ax_bot.set_xlim(0, vid_target * 1.35)
        ax_bot.set_xlabel("Session end-to-end delay (ms)")
        ax_bot.set_ylabel("Count")
        ax_bot.legend(loc="upper right", fontsize=8)
        # Annotate the safety margin
        margin = vid_target - p95
        ax_bot.text(
            vid_target * 0.05, ax_bot.get_ylim()[1] * 0.55,
            f"Safety margin\nP95 → KPI\n= {margin:.0f} ms",
            fontsize=8, color="#555", va="top",
        )
    else:
        # Single panel when the data spans a reasonable fraction of KPI
        x_upper = max(vid_target * 1.4, p99 * 1.2)
        shown   = samples[samples <= x_upper]

        fig, ax = plt.subplots(figsize=(7.5, 4.5))
        ax.hist(shown, bins=60, color=COLOURS["video"], alpha=0.80,
                edgecolor="white",
                label=f"Video session delay (n = {len(samples):,})")
        ax.axvline(mean,       color="gray", linestyle=":",  linewidth=1.2,
                   label=f"Mean = {mean:.1f} ms")
        ax.axvline(p95,        color=COLOURS["video"], linestyle="--", linewidth=1.4,
                   label=f"P95 = {p95:.1f} ms")
        ax.axvline(vid_target, color=COLOURS["target"], linestyle="--", linewidth=1.4,
                   label=f"KPI target = {vid_target} ms")
        ax.set_xlim(0, x_upper)
        ax.set_xlabel("Session end-to-end delay (ms)")
        ax.set_ylabel("Count")
        ax.set_title(
            "Video Session Delay Histogram — P95 vs 150 ms KPI\n"
            "(aggregated over all 5 base stations, α = 1.0)"
        )
        ax.legend(loc="upper right")

    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------
# Figure 3 - Per-class Mbps forecast (36 months, per-class CAGR)
# -----------------------------------------------------------------------

def fig_forecast_per_class(scenario: dict) -> plt.Figure:
    """
    Stacked time series of per-class Mbps (total) + worst-link utilisation
    with planning and action trigger lines, over the 36-month horizon.
    """
    from forecasting import forecast_mbps_per_class, forecast_utilisation

    mbps = forecast_mbps_per_class(scenario)
    fc   = forecast_utilisation(scenario)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(8, 6), sharex=True,
        gridspec_kw={"height_ratios": [3, 2]}
    )

    # --- Panel 1: stacked Mbps per class (aggregate over all sites) ---
    ax1.stackplot(
        mbps["month"],
        mbps["telemetry_mbps"],
        mbps["voice_mbps"],
        mbps["video_mbps"],
        labels=[
            f"Telemetry  ({fc['cagr']['telemetry']*100:.0f}% / yr)",
            f"Voice      ({fc['cagr']['voice']*100:.0f}% / yr)",
            f"Video      ({fc['cagr']['video']*100:.0f}% / yr)",
        ],
        colors=[COLOURS["telemetry"], COLOURS["voice"], COLOURS["video"]],
        alpha=0.85,
    )
    ax1.set_ylabel("Aggregate Mbps (all sites)")
    ax1.set_title(
        f"36-Month Per-Class Traffic Forecast\n"
        f"(monthly CAGR applied; baseline α = 1.0)"
    )
    ax1.legend(loc="upper left")

    # --- Panel 2: worst-link utilisation + trigger lines ---
    ax2.plot(fc["table"]["month"], fc["table"]["utilisation"] * 100,
             color=COLOURS["trunk"], linewidth=2.0,
             label=f"Utilisation — worst link ({fc['worst_site']})")

    ax2.axhline(fc["planning_trigger"] * 100, color=COLOURS["plan"],
                linestyle="--", linewidth=1.4,
                label=f"Planning trigger {fc['planning_trigger']*100:.0f}%")
    ax2.axhline(fc["action_trigger"] * 100, color=COLOURS["act"],
                linestyle="--", linewidth=1.4,
                label=f"Action trigger   {fc['action_trigger']*100:.0f}%")

    # Crossover markers + order-date annotations
    if math.isfinite(fc["t_plan_months"]):
        ax2.axvline(fc["t_plan_months"], color=COLOURS["plan"],
                    linestyle=":", linewidth=1.0, alpha=0.8)
        ax2.annotate(
            f"t_plan = m{fc['t_plan_months']:.1f}\n(order m{fc['order_plan_month']:.1f})",
            xy=(fc["t_plan_months"], fc["planning_trigger"] * 100),
            xytext=(8, 10), textcoords="offset points",
            fontsize=8, color=COLOURS["plan"],
        )
    if math.isfinite(fc["t_act_months"]):
        ax2.axvline(fc["t_act_months"], color=COLOURS["act"],
                    linestyle=":", linewidth=1.0, alpha=0.8)
        ax2.annotate(
            f"t_act = m{fc['t_act_months']:.1f}\n(order m{fc['order_act_month']:.1f})",
            xy=(fc["t_act_months"], fc["action_trigger"] * 100),
            xytext=(8, -28), textcoords="offset points",
            fontsize=8, color=COLOURS["act"],
        )

    ax2.set_xlabel("Month")
    ax2.set_ylabel("Link utilisation (%)")
    ax2.set_xlim(0, fc["horizon_months"])
    ax2.set_ylim(0, max(100, fc["table"]["utilisation"].max() * 100 * 1.1))
    ax2.legend(loc="lower right")

    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------
# Figure 4 - Upgrade strategy comparison
# -----------------------------------------------------------------------

def fig_strategy_comparison(scenario: dict) -> plt.Figure:
    """
    Horizontal bar chart comparing upgrade strategies by cost per extended
    month. Bars are coloured by rank (green = best, red = worst).
    """
    from forecasting import strategy_comparison, forecast_utilisation

    df      = strategy_comparison(scenario).copy()
    horizon = forecast_utilisation(scenario)["horizon_months"]

    # Replace inf with a plot-friendly number; keep originals for annotations
    df["cpm_plot"] = df["cost_per_month_kUSD"].replace(
        [np.inf, -np.inf], np.nan
    )
    max_finite = df["cpm_plot"].max(skipna=True)
    if pd.isna(max_finite) or max_finite <= 0:
        max_finite = 1.0
    df["cpm_plot"] = df["cpm_plot"].fillna(max_finite * 1.3)

    # Rank-based colour map: 1 = green, worst = red
    palette = {1: "#2E7D32", 2: "#66BB6A", 3: "#FB8C00", 4: "#C62828"}
    bar_colours = [palette.get(int(r), "#9E9E9E") for r in df["rank"]]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    y = np.arange(len(df))
    ax.barh(y, df["cpm_plot"], color=bar_colours, edgecolor="white")

    def _ext_label(ext):
        if ext is None:
            return "n/a"
        if not math.isfinite(ext):
            return f">{horizon} mo"
        if ext <= 0:
            return "0 mo (no extension)"
        return f"{ext:g} mo"

    def _cpm_label(cpm):
        if cpm is None or not math.isfinite(cpm):
            return "n/a"
        return f"{cpm:g} kUSD/mo"

    for i, row in df.iterrows():
        rank  = int(row["rank"])
        cost  = row["cost_kUSD"]
        ext_s = _ext_label(row["extended_months"])
        cpm_s = _cpm_label(row["cost_per_month_kUSD"])
        label = f"rank {rank}  •  {cost} kUSD / {ext_s}  =  {cpm_s}"
        ax.text(row["cpm_plot"] * 1.02, i, label, va="center", fontsize=8)

    ax.set_yticks(y)
    ax.set_yticklabels(df["strategy"], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Cost per extended month (kUSD)")
    ax.set_title(
        "Upgrade Strategy Comparison — Report Table 3\n"
        "(lower bars = better value; rank 1 = best)"
    )
    ax.set_xlim(0, max_finite * 1.9)
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------
# Save-all for report pipeline
# -----------------------------------------------------------------------

def save_all_extra_figures(scenario: dict, output_dir: str = "figures") -> list:
    """
    Generate and save the extra figures (CDF, histogram, per-class forecast,
    strategy comparison) as PNG files.
    """
    os.makedirs(output_dir, exist_ok=True)
    fns = [
        ("fig_telemetry_delay_cdf.png",   fig_telemetry_delay_cdf),
        ("fig_video_delay_histogram.png", fig_video_delay_histogram),
        ("fig_forecast_per_class.png",    fig_forecast_per_class),
        ("fig_strategy_comparison.png",   fig_strategy_comparison),
    ]
    saved = []
    for fname, fn in fns:
        fig  = fn(scenario)
        path = os.path.join(output_dir, fname)
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        saved.append(path)
        print(f"  Saved: {path}")
    return saved


# -----------------------------------------------------------------------
# Standalone demo
# -----------------------------------------------------------------------

if __name__ == "__main__":
    scenario_path = os.path.join(os.path.dirname(__file__), "..", "scenario.yaml")
    sc = load_scenario(scenario_path)

    print("Generating extra report figures...")
    out_dir = os.path.join(os.path.dirname(__file__), "figures")
    saved   = save_all_extra_figures(sc, out_dir)
    print(f"\nDone. {len(saved)} extra figures saved to: {out_dir}")