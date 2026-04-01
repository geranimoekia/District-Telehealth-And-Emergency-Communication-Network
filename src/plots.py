"""
plots.py
--------
Report-quality figure generation for TELE 527 Group 1.

All figures are generated from scenario.yaml + module outputs.
Each function returns a matplotlib Figure object so it works both
standalone (savefig) and inside Streamlit (st.pyplot).

Figures produced:
  1. erlang_b_curve          - blocking vs circuits N for all three classes
  2. blocking_vs_load        - blocking vs offered load for fixed N_baseline
  3. p95_delay_vs_alpha      - P95 delay vs load multiplier for tel and video
  4. traffic_matrix_bar      - Mbps per site per class (stacked bar)
  5. utilisation_forecast    - link utilisation growth with trigger lines
  6. erlang_forecast         - voice blocking growth with KPI line
  7. stress_sweep_summary    - KPI pass/fail across all load multiplier steps

Student 2 responsibility - Traffic and Teletraffic Lead
TELE 527 | Group 1 | BIUST | 2026
"""

import math
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import yaml
import os

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

# Colour palette consistent across all figures
COLOURS = {
    "telemetry": "#2196F3",  # blue
    "voice":     "#4CAF50",  # green
    "video":     "#FF9800",  # orange
    "trunk":     "#9C27B0",  # purple
    "plan":      "#FF9800",  # orange dashed
    "act":       "#F44336",  # red dashed
}


def load_scenario(path: str = "scenario.yaml") -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# -----------------------------------------------------------------------
# Figure 1 — Erlang B curve
# -----------------------------------------------------------------------

def fig_erlang_b_curve(scenario: dict) -> plt.Figure:
    """
    Blocking probability vs number of circuits N for each traffic class.
    Marks the dimensioned operating point for each class.
    """
    from src.teletraffic import erlang_b, dimension_channels

    traffic_cfg = scenario["traffic"]
    classes = {
        "telemetry": traffic_cfg["telemetry"]["offered_load_erl"],
        "voice":     traffic_cfg["voice"]["offered_load_erl"],
        "video":     traffic_cfg["video"]["offered_load_erl"],
    }
    target_B = traffic_cfg["voice"]["kpi_blocking_prob"]
    N_max    = 15

    fig, ax = plt.subplots(figsize=(7, 4.5))

    for svc, A in classes.items():
        N_vals = list(range(1, N_max + 1))
        B_vals = [erlang_b(A, N) for N in N_vals]
        ax.semilogy(N_vals, B_vals, marker="o", markersize=4,
                    color=COLOURS[svc], label=f"{svc.capitalize()}  (A={A} Erl)")

        # Mark dimensioned operating point
        N_dim = dimension_channels(A, target_B)
        B_dim = erlang_b(A, N_dim)
        ax.semilogy(N_dim, B_dim, marker="*", markersize=12,
                    color=COLOURS[svc], zorder=5)

    # KPI target line
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


# -----------------------------------------------------------------------
# Figure 2 — Blocking vs offered load (fixed baseline N)
# -----------------------------------------------------------------------

def fig_blocking_vs_load(scenario: dict) -> plt.Figure:
    """
    Blocking probability vs offered load for the baseline circuit count N.
    Shows the operating point and KPI boundary.
    """
    from src.teletraffic import erlang_b, dimension_channels

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

    # Mark stress multiplier points
    for alpha, marker in [(1.5, "^"), (2.0, "s"), (3.0, "D")]:
        A_stress = A0 * alpha
        B_stress = erlang_b(A_stress, N_base)
        ax.semilogy(A_stress, B_stress, marker=marker, markersize=8,
                    color="red", zorder=5, label=f"α = {alpha}  →  B = {B_stress*100:.1f}%")

    ax.set_xlabel("Offered traffic  A  (Erlang)")
    ax.set_ylabel("Blocking probability  B(A, N)")
    ax.set_title(f"Voice Blocking vs Offered Load\n"
                 f"(Fixed baseline N = {N_base} circuits per site)")
    ax.legend(loc="lower right")
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------
# Figure 3 — P95 delay vs load multiplier
# -----------------------------------------------------------------------

def fig_p95_delay_vs_alpha(scenario: dict) -> plt.Figure:
    """
    P95 one-way delay vs load multiplier α for telemetry and video.
    Shows KPI targets as horizontal dashed lines.
    """
    from src.teletraffic import evaluate_delay_kpis

    alphas     = scenario["simulation"]["load_multiplier_steps"]
    tel_target = scenario["traffic"]["telemetry"]["kpi_delay_p95_ms"]
    vid_target = scenario["traffic"]["video"]["kpi_delay_p95_ms"]

    tel_p95_all = []
    vid_p95_all = []

    for alpha in alphas:
        df  = evaluate_delay_kpis(scenario, alpha)
        tel = df[df["service_class"] == "telemetry"]["p95_delay_ms"].max()
        vid = df[df["service_class"] == "video"]["p95_delay_ms"].max()
        tel_p95_all.append(tel)
        vid_p95_all.append(vid)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(alphas, tel_p95_all, marker="o", color=COLOURS["telemetry"],
            label="Telemetry P95 delay (worst site)")
    ax.plot(alphas, vid_p95_all, marker="s", color=COLOURS["video"],
            label="Video P95 delay (worst site)")
    ax.axhline(tel_target, color=COLOURS["telemetry"], linestyle="--", linewidth=1.2,
               label=f"Telemetry KPI target  {tel_target} ms")
    ax.axhline(vid_target, color=COLOURS["video"], linestyle="--", linewidth=1.2,
               label=f"Video KPI target  {vid_target} ms")

    ax.set_xlabel("Load multiplier  α")
    ax.set_ylabel("P95 one-way delay  (ms)")
    ax.set_title("P95 Delay vs Load Multiplier\n"
                 "(Propagation delay + M/M/1 queuing delay)")
    ax.legend(loc="upper left")
    ax.set_xlim(min(alphas) - 0.1, max(alphas) + 0.1)
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------
# Figure 4 — Traffic matrix stacked bar
# -----------------------------------------------------------------------

def fig_traffic_matrix_bar(scenario: dict, load_multiplier: float = 1.0) -> plt.Figure:
    """
    Stacked bar chart of traffic demand (Mbps) per BS site per service class.
    """
    from src.traffic import compute_traffic_matrix

    matrix = compute_traffic_matrix(scenario, load_multiplier)
    sites  = matrix["site"].tolist()
    x      = np.arange(len(sites))
    width  = 0.55

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars_tel = ax.bar(x, matrix["telemetry_mbps"], width, color=COLOURS["telemetry"],
                      label="Telemetry")
    bars_vox = ax.bar(x, matrix["voice_mbps"],     width,
                      bottom=matrix["telemetry_mbps"],
                      color=COLOURS["voice"], label="Voice")
    bars_vid = ax.bar(x, matrix["video_mbps"],     width,
                      bottom=matrix["telemetry_mbps"] + matrix["voice_mbps"],
                      color=COLOURS["video"], label="Video")

    # Link capacity: at normal load bars are ~2 Mbps vs 100 Mbps capacity.
    # A reference line at 100 Mbps would make bars invisible on the chart.
    # Instead, annotate peak utilisation above each bar.
    link_cap = 100.0
    for i, row in matrix.iterrows():
        ax.text(i, row["total_mbps"] + 0.02,
                f"{row['link_utilisation']*100:.1f}%",
                ha="center", va="bottom", fontsize=8, color="black")

    ax.set_xticks(x)
    ax.set_xticklabels(sites)
    ax.set_xlabel("Base station site")
    ax.set_ylabel("Traffic demand  (Mbps)")
    ax.set_title(f"Per-Site Traffic Demand by Service Class\n(α = {load_multiplier:.1f})")
    ax.legend(loc="upper right")
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------
# Figure 5 — Utilisation forecast
# -----------------------------------------------------------------------

def fig_utilisation_forecast(scenario: dict) -> plt.Figure:
    """
    Link utilisation growth forecast with planning and action trigger lines.
    """
    from forecasting import forecast_utilisation

    fc     = forecast_utilisation(scenario)
    curve  = fc["curve"]
    annual = fc["annual_table"]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(curve["year"], curve["utilisation"] * 100,
            color="#1976D2", label="Forecast utilisation")
    ax.scatter(annual["year"], annual["utilisation"] * 100,
               color="#1976D2", s=40, zorder=5)

    ax.axhline(fc["planning_trigger"] * 100, color=COLOURS["plan"],
               linestyle="--", linewidth=1.4,
               label=f"Planning trigger  {fc['planning_trigger']*100:.0f}%  "
                     f"(year {fc['t_plan']:.1f})")
    ax.axhline(fc["action_trigger"] * 100, color=COLOURS["act"],
               linestyle="--", linewidth=1.4,
               label=f"Action trigger  {fc['action_trigger']*100:.0f}%  "
                     f"(year {fc['t_act']:.1f})")

    # Vertical lines at crossover points
    ax.axvline(fc["t_plan"], color=COLOURS["plan"], linestyle=":", linewidth=1.0)
    ax.axvline(fc["t_act"],  color=COLOURS["act"],  linestyle=":", linewidth=1.0)

    ax.set_xlabel("Years from baseline")
    ax.set_ylabel("Link utilisation  (%)")
    ax.set_title(f"Backhaul Link Utilisation Forecast\n"
                 f"(U₀ = {fc['initial_utilisation']*100:.0f}%,  "
                 f"r = {fc['growth_rate']*100:.0f}% per year)")
    ax.set_xlim(0, fc["horizon_years"])
    max_pct = fc["annual_table"]["utilisation"].max() * 100
    ax.set_ylim(0, max(115, math.ceil(max_pct / 10) * 10 + 5))
    ax.legend(loc="upper left")
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------
# Figure 6 — Erlang (voice blocking) forecast
# -----------------------------------------------------------------------

def fig_erlang_forecast(scenario: dict) -> plt.Figure:
    """
    Voice offered load and blocking probability growth over the forecast horizon.
    Two y-axes: left = Erlang load, right = blocking probability.
    """
    from forecasting import forecast_erlang

    df       = forecast_erlang(scenario)
    target_B = scenario["traffic"]["voice"]["kpi_blocking_prob"]

    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    ax2 = ax1.twinx()

    line1, = ax1.plot(df["year"], df["offered_load_erl"], marker="o",
                      color=COLOURS["voice"], label="Offered load (Erl)")
    line2, = ax2.semilogy(df["year"], df["blocking_prob"], marker="s",
                          color="#E91E63", label="Blocking probability")
    kpi_line = ax2.axhline(target_B, color="red", linestyle="--", linewidth=1.2,
                           label=f"KPI target  {target_B*100:.0f}%")

    # Mark first failure year
    fail = df[df["upgrade_needed"]]
    upgrade_line = None
    if not fail.empty:
        yr = fail["year"].iloc[0]
        upgrade_line = ax2.axvline(yr, color="red", linestyle=":", linewidth=1.2,
                                   label=f"Upgrade needed (year {yr})")

    ax1.set_xlabel("Years from baseline")
    ax1.set_ylabel("Offered voice load  (Erlang)", color=COLOURS["voice"])
    ax2.set_ylabel("Blocking probability", color="#E91E63")
    ax1.set_title("Voice Traffic Growth and Blocking Probability Forecast")
    ax1.set_xlim(0, scenario["forecasting"]["horizon_years"])

    lines  = [line1, line2, kpi_line]
    labels = [l.get_label() for l in lines]
    if upgrade_line is not None:
        lines.append(upgrade_line)
        labels.append(upgrade_line.get_label())
    ax1.legend(lines, labels, loc="upper left")
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------
# Figure 7 — Stress sweep KPI summary
# -----------------------------------------------------------------------

def fig_stress_sweep(scenario: dict) -> plt.Figure:
    """
    Combined stress sweep showing voice blocking and P95 delays
    against their KPI targets across load multipliers.
    """
    from src.teletraffic import stress_sweep

    sweep      = stress_sweep(scenario)
    alphas     = sweep["load_multiplier"].tolist()
    voice_B    = sweep["voice_blocking"].tolist()
    tel_p95    = sweep["telemetry_p95_ms"].tolist()
    vid_p95    = sweep["video_p95_ms"].tolist()

    target_B   = scenario["traffic"]["voice"]["kpi_blocking_prob"]
    tel_target = scenario["traffic"]["telemetry"]["kpi_delay_p95_ms"]
    vid_target = scenario["traffic"]["video"]["kpi_delay_p95_ms"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))

    # Left panel: voice blocking
    ax1.semilogy(alphas, voice_B, marker="o", color=COLOURS["voice"],
                 label="Voice blocking  B(A, N_base)")
    ax1.axhline(target_B, color="red", linestyle="--", linewidth=1.2,
                label=f"KPI target  {target_B*100:.0f}%")
    ax1.set_xlabel("Load multiplier  α")
    ax1.set_ylabel("Blocking probability")
    ax1.set_title("Voice Blocking — Breaking Point Study")
    ax1.legend()

    # Right panel: P95 delays
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

    fig.suptitle("Stress Sweep: KPI Performance vs Load Multiplier  (Fixed Baseline Capacity)",
                 fontsize=11, fontweight="bold")
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------
# Save all figures to disk (for LaTeX report)
# -----------------------------------------------------------------------

def save_all_figures(scenario: dict, output_dir: str = "figures") -> list:
    """
    Generate and save all report figures as PNG files.

    Parameters
    ----------
    scenario : dict
        Loaded scenario YAML.
    output_dir : str
        Directory to save figures. Created if it does not exist.

    Returns
    -------
    list of str
        Paths to saved figure files.
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    figure_fns = [
        ("fig_erlang_b_curve.png",       fig_erlang_b_curve),
        ("fig_blocking_vs_load.png",     fig_blocking_vs_load),
        ("fig_p95_delay_vs_alpha.png",   fig_p95_delay_vs_alpha),
        ("fig_traffic_matrix_bar.png",   fig_traffic_matrix_bar),
        ("fig_utilisation_forecast.png", fig_utilisation_forecast),
        ("fig_erlang_forecast.png",      fig_erlang_forecast),
        ("fig_stress_sweep.png",         fig_stress_sweep),
    ]

    saved = []
    for fname, fn in figure_fns:
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
    path = os.path.join(os.path.dirname(__file__), "..", "scenario.yaml")
    sc   = load_scenario(path)

    print("Generating all report figures...")
    out_dir = os.path.join(os.path.dirname(__file__), "figures")
    saved   = save_all_figures(sc, out_dir)
    print(f"\nDone. {len(saved)} figures saved to: {out_dir}")
    plt.show()