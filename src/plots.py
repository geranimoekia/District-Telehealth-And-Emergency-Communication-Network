"""
plots.py
--------
Report-quality figure generation for TELE 527 Group 1.

All figures are generated from scenario.yaml + module outputs.
Each function returns a matplotlib Figure object so it works both
standalone (savefig) and inside Streamlit (st.pyplot).

Figures produced
----------------
  --- Teletraffic / Erlang ---
  1.  fig_erlang_b_curve         - blocking probability vs circuits N (all classes)
  2.  fig_blocking_vs_load       - blocking vs offered load at fixed baseline N
  3.  fig_p95_delay_vs_alpha     - P95 delay vs load multiplier (tel + video)
  4.  fig_stress_sweep           - voice blocking + delay KPIs across stress sweep

  --- Traffic ---
  5.  fig_traffic_matrix_bar     - Mbps per site per class (stacked bar)

  --- Delay distributions ---
  6.  fig_telemetry_delay_cdf    - CDF of telemetry delay, P99 vs 50 ms KPI
  7.  fig_video_delay_histogram  - histogram of video delay, P95 vs 150 ms KPI

  --- Forecasting ---
  8.  fig_forecast_per_class     - 36-month per-class Mbps + utilisation triggers
  9.  fig_erlang_forecast        - voice blocking growth with KPI line
  10. fig_strategy_comparison    - upgrade strategy bar chart (cost per month)

Student 2 responsibility - Traffic and Teletraffic Lead
TELE 527 | Group 1 | BIUST | 2026
"""

import math
import os
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import yaml

matplotlib.rcParams.update({
    "font.size":        10,
    "axes.titlesize":   11,
    "axes.labelsize":   10,
    "legend.fontsize":  9,
    "xtick.labelsize":  9,
    "ytick.labelsize":  9,
    "figure.dpi":       120,
    "axes.grid":        True,
    "grid.alpha":       0.35,
    "lines.linewidth":  1.8,
})

# Colour palette — consistent across every figure
COLOURS = {
    "telemetry": "#2196F3",   # blue
    "voice":     "#4CAF50",   # green
    "video":     "#FF9800",   # orange
    "trunk":     "#9C27B0",   # purple
    "plan":      "#FF9800",   # orange dashed  (planning trigger)
    "act":       "#F44336",   # red dashed     (action trigger)
    "target":    "#D32F2F",   # red solid      (KPI target lines)
}


def load_scenario(path: str = "scenario.yaml") -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1 — TELETRAFFIC / ERLANG FIGURES
# ═══════════════════════════════════════════════════════════════════════════

def fig_erlang_b_curve(scenario: dict) -> plt.Figure:
    """
    Figure 1 — Blocking probability vs number of circuits N for each class.
    Stars mark the dimensioned operating point; red dashed line = KPI target.
    """
    from teletraffic import erlang_b, dimension_channels

    traffic_cfg = scenario["traffic"]
    classes = {
        "telemetry": traffic_cfg["telemetry"]["offered_load_erl"],
        "voice":     traffic_cfg["voice"]["offered_load_erl"],
        "video":     traffic_cfg["video"]["offered_load_erl"],
    }
    target_B = traffic_cfg["voice"]["kpi_blocking_prob"]
    N_max    = 20

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for svc, A in classes.items():
        N_vals = list(range(1, N_max + 1))
        B_vals = [erlang_b(A, N) for N in N_vals]
        ax.semilogy(N_vals, B_vals, marker="o", markersize=4,
                    color=COLOURS[svc],
                    label=f"{svc.capitalize()}  (A = {A} Erl)")
        N_dim = dimension_channels(A, target_B)
        B_dim = erlang_b(A, N_dim)
        ax.semilogy(N_dim, B_dim, marker="*", markersize=12,
                    color=COLOURS[svc], zorder=5)

    ax.axhline(target_B, color="red", linestyle="--", linewidth=1.2,
               label=f"KPI target  B = {target_B*100:.0f}%")
    ax.set_xlabel("Number of circuits  N")
    ax.set_ylabel("Blocking probability  B(A, N)")
    ax.set_title("Erlang B — Blocking Probability vs Circuit Count\n"
                 "(★ marks dimensioned operating point)")
    ax.legend(loc="upper right")
    ax.set_xlim(1, N_max)
    ax.set_ylim(1e-6, 1.1)
    fig.tight_layout()
    return fig


def fig_blocking_vs_load(scenario: dict) -> plt.Figure:
    """
    Figure 2 — Voice blocking probability vs offered load at fixed N_baseline.
    Marks the normal operating point and several stress multipliers.
    """
    from teletraffic import erlang_b, dimension_channels

    cfg      = scenario["traffic"]["voice"]
    A0       = cfg["offered_load_erl"]
    target_B = cfg["kpi_blocking_prob"]
    N_base   = dimension_channels(A0, target_B)

    A_vals = np.linspace(0.01, N_base * 1.5, 300)
    B_vals = [erlang_b(A, N_base) for A in A_vals]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.semilogy(A_vals, B_vals, color=COLOURS["voice"],
                label=f"Erlang B  (N = {N_base} circuits)")
    ax.axhline(target_B, color="red", linestyle="--", linewidth=1.2,
               label=f"KPI target  B = {target_B*100:.0f}%")
    ax.axvline(A0, color="gray", linestyle=":", linewidth=1.2,
               label=f"Normal load  A = {A0} Erl (α = 1.0)")

    for alpha, marker in [(1.25, "^"), (1.5, "s"), (2.0, "D")]:
        A_s = A0 * alpha
        B_s = erlang_b(A_s, N_base)
        ax.semilogy(A_s, B_s, marker=marker, markersize=8,
                    color="red", zorder=5,
                    label=f"α = {alpha}  →  B = {B_s*100:.1f}%")

    ax.set_xlabel("Offered traffic  A  (Erlang)")
    ax.set_ylabel("Blocking probability  B(A, N)")
    ax.set_title(f"Voice Blocking vs Offered Load\n"
                 f"(Fixed baseline N = {N_base} circuits per site)")
    ax.legend(loc="lower right")
    fig.tight_layout()
    return fig


def fig_p95_delay_vs_alpha(scenario: dict) -> plt.Figure:
    """
    Figure 3 — P95 one-way delay vs load multiplier α for telemetry and video.
    KPI target lines show at what point each class fails.
    """
    from teletraffic import evaluate_delay_kpis

    alphas     = scenario["simulation"]["load_multiplier_steps"]
    tel_target = scenario["traffic"]["telemetry"]["kpi_delay_p95_ms"]
    vid_target = scenario["traffic"]["video"]["kpi_delay_p95_ms"]

    tel_vals, vid_vals = [], []
    for alpha in alphas:
        df = evaluate_delay_kpis(scenario, alpha)
        tel_vals.append(df[df["service_class"] == "telemetry"]["p95_delay_ms"].max())
        vid_vals.append(df[df["service_class"] == "video"]["p95_delay_ms"].max())

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(alphas, tel_vals, marker="o", color=COLOURS["telemetry"],
            label="Telemetry P95 delay (worst site)")
    ax.plot(alphas, vid_vals, marker="s", color=COLOURS["video"],
            label="Video P95 delay (worst site)")
    ax.axhline(tel_target, color=COLOURS["telemetry"], linestyle="--",
               linewidth=1.2, label=f"Telemetry KPI  {tel_target} ms")
    ax.axhline(vid_target, color=COLOURS["video"], linestyle="--",
               linewidth=1.2, label=f"Video KPI  {vid_target} ms")
    ax.set_xlabel("Load multiplier  α")
    ax.set_ylabel("P95 one-way delay  (ms)")
    ax.set_title("P95 Delay vs Load Multiplier\n"
                 "(Propagation + M/M/1 packetised queuing delay)")
    ax.legend(loc="upper left")
    ax.set_xlim(min(alphas) - 0.1, max(alphas) + 0.1)
    fig.tight_layout()
    return fig


def fig_stress_sweep(scenario: dict) -> plt.Figure:
    """
    Figure 4 — Combined stress sweep: voice blocking (left) and P95 delays
    (right) plotted against load multiplier with their KPI targets.
    """
    from teletraffic import stress_sweep

    sweep      = stress_sweep(scenario)
    alphas     = sweep["load_multiplier"].tolist()
    voice_B    = sweep["voice_blocking"].tolist()
    tel_p95    = sweep["telemetry_p95_ms"].tolist()
    vid_p95    = sweep["video_p95_ms"].tolist()

    target_B   = scenario["traffic"]["voice"]["kpi_blocking_prob"]
    tel_target = scenario["traffic"]["telemetry"]["kpi_delay_p95_ms"]
    vid_target = scenario["traffic"]["video"]["kpi_delay_p95_ms"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))

    ax1.semilogy(alphas, voice_B, marker="o", color=COLOURS["voice"],
                 label="Voice blocking  B(A, N_base)")
    ax1.axhline(target_B, color="red", linestyle="--", linewidth=1.2,
                label=f"KPI target  {target_B*100:.0f}%")
    ax1.set_xlabel("Load multiplier  α")
    ax1.set_ylabel("Blocking probability")
    ax1.set_title("Voice Blocking — Breaking Point Study")
    ax1.legend()

    ax2.plot(alphas, tel_p95, marker="o", color=COLOURS["telemetry"],
             label="Telemetry P95")
    ax2.plot(alphas, vid_p95, marker="s", color=COLOURS["video"],
             label="Video P95")
    ax2.axhline(tel_target, color=COLOURS["telemetry"], linestyle="--",
                linewidth=1.2, label=f"Telemetry KPI  {tel_target} ms")
    ax2.axhline(vid_target, color=COLOURS["video"], linestyle="--",
                linewidth=1.2, label=f"Video KPI  {vid_target} ms")
    ax2.set_xlabel("Load multiplier  α")
    ax2.set_ylabel("P95 one-way delay  (ms)")
    ax2.set_title("Delay KPIs — Breaking Point Study")
    ax2.legend()

    fig.suptitle(
        "Stress Sweep: KPI Performance vs Load Multiplier  "
        "(Fixed Baseline Capacity)",
        fontsize=11, fontweight="bold",
    )
    fig.tight_layout()
    return fig


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2 — TRAFFIC FIGURE
# ═══════════════════════════════════════════════════════════════════════════

def fig_traffic_matrix_bar(scenario: dict, load_multiplier: float = 1.0) -> plt.Figure:
    """
    Figure 5 — Stacked bar chart of traffic demand (Mbps) per BS site and
    service class at the given load multiplier.
    """
    from traffic import compute_traffic_matrix

    matrix    = compute_traffic_matrix(scenario, load_multiplier)
    sites     = matrix["site"].tolist()
    x         = np.arange(len(sites))
    link_cap  = matrix["link_capacity_mbps"].iloc[0]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    tel_bars = ax.bar(x, matrix["telemetry_mbps"], color=COLOURS["telemetry"],
                      label="Telemetry")
    vox_bars = ax.bar(x, matrix["voice_mbps"], bottom=matrix["telemetry_mbps"],
                      color=COLOURS["voice"], label="Voice")
    vid_bars = ax.bar(x, matrix["video_mbps"],
                      bottom=matrix["telemetry_mbps"] + matrix["voice_mbps"],
                      color=COLOURS["video"], label="Video")

    ax.axhline(link_cap, color="red", linestyle="--", linewidth=1.2,
               label=f"Link capacity  {link_cap:.0f} Mbps")
    ax.set_xticks(x)
    ax.set_xticklabels(sites)
    ax.set_xlabel("Base station site")
    ax.set_ylabel("Traffic demand  (Mbps)")
    ax.set_title(f"Traffic Matrix — Per-Site Bandwidth Demand\n"
                 f"(α = {load_multiplier})")
    ax.legend(loc="upper right")
    fig.tight_layout()
    return fig


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3 — DELAY DISTRIBUTION FIGURES
# ═══════════════════════════════════════════════════════════════════════════

def fig_telemetry_delay_cdf(
    scenario: dict,
    n_samples: int = 20_000,
) -> plt.Figure:
    """
    Figure 6 — CDF of end-to-end telemetry delay aggregated over all BS
    sites (α = 1.0).

    Two-panel layout when the KPI target is far beyond the data range:
      top  — tight zoom showing the per-site propagation steps
      bot  — zoom out to include the 50 ms KPI line + safety margin
    """
    from delay_samples import sample_telemetry_delays

    tel_target = scenario["traffic"]["telemetry"]["kpi_delay_p95_ms"]

    samples = sample_telemetry_delays(scenario, n_samples=n_samples, alpha=1.0)
    samples = np.sort(samples[np.isfinite(samples)])
    cdf     = np.arange(1, len(samples) + 1) / len(samples)

    p95 = float(np.percentile(samples, 95))
    p99 = float(np.percentile(samples, 99))

    data_upper     = max(p99 * 1.15, samples[-1] * 1.02)
    use_two_panels = data_upper < tel_target * 0.5

    def _draw_cdf(ax, x_upper, show_kpi: bool):
        ax.plot(samples, cdf, color=COLOURS["telemetry"],
                label="Telemetry delay CDF")
        ax.axvline(p95, color="gray", linestyle=":", linewidth=1.2,
                   label=f"P95 = {p95:.1f} ms")
        ax.axvline(p99, color=COLOURS["telemetry"], linestyle="--",
                   linewidth=1.4, label=f"P99 = {p99:.1f} ms")
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
            gridspec_kw={"height_ratios": [3, 2]},
        )
        _draw_cdf(ax_top, data_upper, show_kpi=False)
        ax_top.set_title(
            "Telemetry Delay CDF — P99 vs 50 ms KPI\n"
            "(top: data detail  ·  bottom: zoom out to KPI line)"
        )
        ax_top.legend(loc="lower right", fontsize=8)

        _draw_cdf(ax_bot, tel_target * 1.5, show_kpi=True)
        ax_bot.set_xlabel("End-to-end delay (ms)")
        ax_bot.text(
            tel_target * 0.05, 0.15,
            f"Safety margin\nP99 → KPI\n= {tel_target - p99:.0f} ms",
            fontsize=8, color="#555", va="center",
        )
        ax_bot.legend(loc="lower right", fontsize=8)
    else:
        fig, ax = plt.subplots(figsize=(7.5, 4.5))
        _draw_cdf(ax, max(tel_target * 1.5, p99 * 1.1), show_kpi=True)
        ax.set_xlabel("End-to-end delay (ms)")
        ax.set_title(
            "Telemetry Delay CDF — P99 vs 50 ms KPI\n"
            "(aggregated over all 5 base stations, α = 1.0)"
        )
        ax.legend(loc="lower right")

    fig.tight_layout()
    return fig


def fig_video_delay_histogram(
    scenario: dict,
    n_samples: int = 20_000,
) -> plt.Figure:
    """
    Figure 7 — Histogram of per-session video delay aggregated over all BS
    sites (α = 1.0).

    Two-panel layout when the KPI target is far beyond the data range:
      top  — tight zoom showing the exponential M/M/1 tail
      bot  — zoom out to include the 150 ms KPI line + safety margin
    """
    from delay_samples import sample_video_delays

    vid_target = scenario["traffic"]["video"]["kpi_delay_p95_ms"]
    samples    = sample_video_delays(scenario, n_samples=n_samples, alpha=1.0)
    samples    = samples[np.isfinite(samples)]

    p95  = float(np.percentile(samples, 95))
    p99  = float(np.percentile(samples, 99))
    mean = float(np.mean(samples))

    data_upper     = max(p99 * 1.15, samples.max() * 1.02)
    use_two_panels = data_upper < vid_target * 0.5

    if use_two_panels:
        fig, (ax_top, ax_bot) = plt.subplots(
            2, 1, figsize=(7.5, 5.8),
            gridspec_kw={"height_ratios": [3, 1]},
        )
        ax_top.hist(samples[samples <= data_upper], bins=60,
                    color=COLOURS["video"], alpha=0.80, edgecolor="white",
                    label=f"Video session delay (n = {len(samples):,})")
        ax_top.axvline(mean, color="gray", linestyle=":", linewidth=1.2,
                       label=f"Mean = {mean:.1f} ms")
        ax_top.axvline(p95,  color=COLOURS["video"], linestyle="--",
                       linewidth=1.4, label=f"P95 = {p95:.1f} ms")
        ax_top.axvline(p99,  color=COLOURS["target"], linestyle=":",
                       linewidth=1.2, label=f"P99 = {p99:.1f} ms")
        ax_top.set_ylabel("Count")
        ax_top.set_xlim(0, data_upper)
        ax_top.set_title(
            "Video Session Delay Histogram — P95 vs 150 ms KPI\n"
            "(top: data detail  ·  bottom: zoom out to KPI line)"
        )
        ax_top.legend(loc="upper right", fontsize=8)

        ax_bot.hist(samples, bins=80, color=COLOURS["video"],
                    alpha=0.80, edgecolor="white")
        ax_bot.axvline(p95, color=COLOURS["video"], linestyle="--", linewidth=1.4)
        ax_bot.axvline(vid_target, color=COLOURS["target"], linestyle="--",
                       linewidth=1.6, label=f"KPI target = {vid_target} ms")
        ax_bot.set_xlim(0, vid_target * 1.35)
        ax_bot.set_xlabel("Session end-to-end delay (ms)")
        ax_bot.set_ylabel("Count")
        ax_bot.text(
            vid_target * 0.05, ax_bot.get_ylim()[1] * 0.55,
            f"Safety margin\nP95 → KPI\n= {vid_target - p95:.0f} ms",
            fontsize=8, color="#555", va="top",
        )
        ax_bot.legend(loc="upper right", fontsize=8)
    else:
        x_upper = max(vid_target * 1.4, p99 * 1.2)
        fig, ax = plt.subplots(figsize=(7.5, 4.5))
        ax.hist(samples[samples <= x_upper], bins=60,
                color=COLOURS["video"], alpha=0.80, edgecolor="white",
                label=f"Video session delay (n = {len(samples):,})")
        ax.axvline(mean, color="gray", linestyle=":", linewidth=1.2,
                   label=f"Mean = {mean:.1f} ms")
        ax.axvline(p95, color=COLOURS["video"], linestyle="--", linewidth=1.4,
                   label=f"P95 = {p95:.1f} ms")
        ax.axvline(vid_target, color=COLOURS["target"], linestyle="--",
                   linewidth=1.4, label=f"KPI target = {vid_target} ms")
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


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4 — FORECASTING FIGURES
# ═══════════════════════════════════════════════════════════════════════════

def fig_forecast_per_class(scenario: dict) -> plt.Figure:
    """
    Figure 8 — Two-panel 36-month forecast.
      Top   : stacked Mbps per class (aggregate, per-class CAGR)
      Bottom: worst-link utilisation with planning and action trigger lines
              annotated with trigger month and order-by month.
    """
    from forecasting import forecast_mbps_per_class, forecast_utilisation

    mbps = forecast_mbps_per_class(scenario)
    fc   = forecast_utilisation(scenario)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(8, 6), sharex=True,
        gridspec_kw={"height_ratios": [3, 2]},
    )

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
        "36-Month Per-Class Traffic Forecast\n"
        "(monthly CAGR applied; baseline α = 1.0)"
    )
    ax1.legend(loc="upper left")

    ax2.plot(fc["table"]["month"], fc["table"]["utilisation"] * 100,
             color=COLOURS["trunk"], linewidth=2.0,
             label=f"Utilisation — worst link ({fc['worst_site']})")
    ax2.axhline(fc["planning_trigger"] * 100, color=COLOURS["plan"],
                linestyle="--", linewidth=1.4,
                label=f"Planning trigger  {fc['planning_trigger']*100:.0f}%")
    ax2.axhline(fc["action_trigger"] * 100, color=COLOURS["act"],
                linestyle="--", linewidth=1.4,
                label=f"Action trigger    {fc['action_trigger']*100:.0f}%")

    if math.isfinite(fc["t_plan_months"]):
        ax2.axvline(fc["t_plan_months"], color=COLOURS["plan"],
                    linestyle=":", linewidth=1.0, alpha=0.8)
        ax2.annotate(
            f"t_plan = m{fc['t_plan_months']:.1f}\n"
            f"(order m{fc['order_plan_month']:.1f})",
            xy=(fc["t_plan_months"], fc["planning_trigger"] * 100),
            xytext=(8, 10), textcoords="offset points",
            fontsize=8, color=COLOURS["plan"],
        )
    if math.isfinite(fc["t_act_months"]):
        ax2.axvline(fc["t_act_months"], color=COLOURS["act"],
                    linestyle=":", linewidth=1.0, alpha=0.8)
        ax2.annotate(
            f"t_act = m{fc['t_act_months']:.1f}\n"
            f"(order m{fc['order_act_month']:.1f})",
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


def fig_erlang_forecast(scenario: dict) -> plt.Figure:
    """
    Figure 9 — Voice offered load and blocking probability growth over the
    36-month horizon. Dual y-axis: left = Erlang load, right = blocking.
    Marks the first month where channel upgrade is needed.
    """
    from forecasting import forecast_erlang

    df       = forecast_erlang(scenario)
    target_B = scenario["traffic"]["voice"]["kpi_blocking_prob"]
    horizon  = scenario.get("forecasting", {}).get("horizon_months", 36)

    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    ax2 = ax1.twinx()

    line1, = ax1.plot(df["month"], df["offered_load_erl"], marker="o",
                      color=COLOURS["voice"], label="Offered load (Erl)")
    line2, = ax2.semilogy(df["month"], df["blocking_prob"], marker="s",
                          color="#E91E63", label="Blocking probability")
    kpi_line = ax2.axhline(target_B, color="red", linestyle="--",
                           linewidth=1.2,
                           label=f"KPI target  {target_B*100:.0f}%")

    fail         = df[df["upgrade_needed"]]
    upgrade_line = None
    if not fail.empty:
        m = fail["month"].iloc[0]
        upgrade_line = ax2.axvline(m, color="red", linestyle=":",
                                   linewidth=1.2,
                                   label=f"Upgrade needed (month {m})")

    ax1.set_xlabel("Month from baseline")
    ax1.set_ylabel("Offered voice load  (Erlang)", color=COLOURS["voice"])
    ax2.set_ylabel("Blocking probability", color="#E91E63")
    ax1.set_title("Voice Traffic Growth and Blocking Probability Forecast\n"
                  "(36-month horizon, voice CAGR 10% / yr)")
    ax1.set_xlim(0, horizon)

    lines  = [line1, line2, kpi_line]
    labels = [l.get_label() for l in lines]
    if upgrade_line is not None:
        lines.append(upgrade_line)
        labels.append(upgrade_line.get_label())
    ax1.legend(lines, labels, loc="upper left")
    fig.tight_layout()
    return fig


def fig_strategy_comparison(scenario: dict) -> plt.Figure:
    """
    Figure 10 — Horizontal bar chart comparing upgrade strategies by cost
    per extended month. Colour-coded by rank (dark green = rank 1 best,
    red = rank 4 worst). Each bar is annotated with full cost details.
    """
    from forecasting import strategy_comparison, forecast_utilisation

    df      = strategy_comparison(scenario).copy()
    horizon = forecast_utilisation(scenario)["horizon_months"]

    df["cpm_plot"] = df["cost_per_month_kUSD"].replace(
        [np.inf, -np.inf], np.nan
    )
    max_finite = df["cpm_plot"].max(skipna=True)
    if pd.isna(max_finite) or max_finite <= 0:
        max_finite = 1.0
    df["cpm_plot"] = df["cpm_plot"].fillna(max_finite * 1.3)

    palette = {1: "#2E7D32", 2: "#66BB6A", 3: "#FB8C00", 4: "#C62828"}
    bar_colours = [palette.get(int(r), "#9E9E9E") for r in df["rank"]]

    def _ext_label(ext):
        if ext is None or not math.isfinite(ext):
            return f">{horizon} mo"
        return "0 mo (no extension)" if ext <= 0 else f"{ext:g} mo"

    def _cpm_label(cpm):
        return "n/a" if (cpm is None or not math.isfinite(cpm)) \
               else f"{cpm:g} kUSD/mo"

    fig, ax = plt.subplots(figsize=(8, 4.5))
    y = np.arange(len(df))
    ax.barh(y, df["cpm_plot"], color=bar_colours, edgecolor="white")

    for i, row in df.iterrows():
        label = (f"rank {int(row['rank'])}  •  "
                 f"{row['cost_kUSD']} kUSD / {_ext_label(row['extended_months'])}"
                 f"  =  {_cpm_label(row['cost_per_month_kUSD'])}")
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


# ═══════════════════════════════════════════════════════════════════════════
# SAVE ALL FIGURES
# ═══════════════════════════════════════════════════════════════════════════

def save_all_figures(scenario: dict, output_dir: str = "figures") -> list:
    """
    Generate and save all 10 report figures as PNG files.

    Returns a list of saved file paths.
    """
    os.makedirs(output_dir, exist_ok=True)

    figure_fns = [
        ("fig_erlang_b_curve.png",          fig_erlang_b_curve),
        ("fig_blocking_vs_load.png",         fig_blocking_vs_load),
        ("fig_p95_delay_vs_alpha.png",        fig_p95_delay_vs_alpha),
        ("fig_stress_sweep.png",              fig_stress_sweep),
        ("fig_traffic_matrix_bar.png",        fig_traffic_matrix_bar),
        ("fig_telemetry_delay_cdf.png",       fig_telemetry_delay_cdf),
        ("fig_video_delay_histogram.png",     fig_video_delay_histogram),
        ("fig_forecast_per_class.png",        fig_forecast_per_class),
        ("fig_erlang_forecast.png",           fig_erlang_forecast),
        ("fig_strategy_comparison.png",       fig_strategy_comparison),
    ]

    saved = []
    for fname, fn in figure_fns:
        print(f"  Generating {fname} ...", end=" ", flush=True)
        fig  = fn(scenario)
        path = os.path.join(output_dir, fname)
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        saved.append(path)
        print("done")

    return saved


# ═══════════════════════════════════════════════════════════════════════════
# STANDALONE ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    scenario_path = os.path.join(os.path.dirname(__file__), "..", "scenario.yaml")
    sc = load_scenario(scenario_path)

    print("Generating all 10 report figures...")
    out_dir = os.path.join(os.path.dirname(__file__), "figures")
    saved   = save_all_figures(sc, out_dir)

    print(f"\nDone. {len(saved)} figures saved to: {out_dir}")
    for p in saved:
        print(f"  {os.path.basename(p)}")