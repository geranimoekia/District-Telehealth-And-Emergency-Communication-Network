"""
dashboard.py
============
Student 3 — Wireless Planning Lead | TELE 527 Group 1

Streamlit dashboard with ALL required outputs including:
  • Coverage & propagation results (exact screenshot fields)
  • Per-link usage (Student 4 requirement)
  • Erlang B blocking probability (Student 4 requirement)
  • Call setup metrics: setup delay, primary/backup link usage,
    calls per link (Student 4 requirement)
  • Grade of Service (GoS)
  • Backhaul capacity with rain attenuation
  • Frequency reuse & sectorization
  • Stress testing & breaking point

Run:  streamlit run dashboard.py
"""

import os
import sys
import math
import json
import copy

import numpy as np
import pandas as pd
import yaml
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

sys.path.insert(0, os.path.dirname(__file__))

from traffic     import load_scenario, compute_traffic_matrix, compute_trunk_demand, stress_bandwidth_sweep
from teletraffic import (run_teletraffic, compute_signaling_load, signaling_summary,
                          stress_sweep, find_breaking_point, erlang_b, dimension_channels,
                          erlang_b_curve, blocking_vs_load)
from propagation import (cost231_hata, site_link_budget_table, microwave_budget,
                          rain_attenuation_db, _coverage_radius)
from wireless    import (build_coverage_grid, coverage_statistics, validate_backhaul_capacity,
                          frequency_reuse_cluster, sectorization_analysis, grade_of_service,
                          plot_reuse_pattern)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TELE 527 | Wireless Planning — Student 3",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #0d1117; }
[data-testid="stSidebar"]          { background: #161b22; }
.stTabs [data-baseweb="tab-list"]  { background: #161b22; border-radius: 8px; }
.stTabs [data-baseweb="tab"]       { color: #8b949e; font-weight: 600; }
.stTabs [aria-selected="true"]     { color: #58a6ff !important; border-bottom: 2px solid #58a6ff; }
div[data-testid="metric-container"] { background: #161b22; border-radius: 8px;
                                       border: 1px solid #30363d; padding: 12px; }
.stDataFrame { background: #161b22; }
h1,h2,h3 { color: #e6edf3; }
p, li     { color: #8b949e; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar: global controls ───────────────────────────────────────────────────
st.sidebar.title("⚙️ Scenario Controls")
st.sidebar.markdown("---")

SCENARIO_PATH = os.path.join(os.path.dirname(__file__), "scenario.yaml")
sc = load_scenario(SCENARIO_PATH)

alpha       = st.sidebar.slider("Load multiplier α", 1.0, 5.0, 1.0, 0.5)
grid_res    = st.sidebar.select_slider("Grid resolution", [60, 80, 100, 120], value=80)
reuse_N     = st.sidebar.selectbox("Reuse factor N", [1, 3, 4, 7, 12], index=2)
sectors     = st.sidebar.radio("Sectors / site", [1, 3, 6], index=1, horizontal=True)
fail_link   = st.sidebar.selectbox("Inject failure", ["None"] + [
    s["name"] for s in sc["sites"] if s["type"] == "base_station"])

st.sidebar.markdown("---")
rerun = st.sidebar.button("▶ Re-run scenario", type="primary", use_container_width=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("📡 Wireless Planning Dashboard")
st.caption(f"**Student 3 — Wireless Planning Lead** | Group 1 | TELE 527 | BIUST 2026  |  α = {alpha:.1f}")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "🗺️ Coverage & Propagation",
    "📶 Link Quality & Backhaul",
    "📊 Erlang B & GoS",
    "📞 Call Setup & Signaling",
    "🔁 Reuse & Sectorization",
    "⚡ Stress Test & Breaking Point",
])


# =============================================================================
# ── Cached computations ───────────────────────────────────────────────────────
# =============================================================================

@st.cache_data(show_spinner=False)
def _get_grid(grid_res, alpha_val):
    """Build coverage grid — cached."""
    env  = sc["environment"]
    f, hb, hm = env["carrier_frequency_mhz"], env["base_station_height_m"], env["mobile_height_m"]
    ptx  = env["tx_power_dbm"]
    eirp = ptx + 17.0 - 2.0
    size = env["district_size_km"]
    xs   = np.linspace(0, size, grid_res)
    ys   = np.linspace(0, size, grid_res)
    grid = np.full((grid_res, grid_res), -150.0)
    bs_sites = [(s["x_km"], s["y_km"]) for s in sc["sites"] if s["type"] == "base_station"]
    for (sx, sy) in bs_sites:
        for j, y in enumerate(ys):
            for i, x in enumerate(xs):
                d   = max(math.hypot(x-sx, y-sy), 0.05)
                pl  = cost231_hata(d, f, hb, hm, 0.0)
                prx = eirp - pl
                if prx > grid[j, i]:
                    grid[j, i] = prx
    return xs, ys, grid


@st.cache_data(show_spinner=False)
def _get_traffic(alpha_val):
    return compute_traffic_matrix(sc, alpha_val)


@st.cache_data(show_spinner=False)
def _get_teletraffic(alpha_val):
    return run_teletraffic(sc, alpha_val)


# =============================================================================
# TAB 1 — Coverage & Propagation (screenshot fields)
# =============================================================================

with tabs[0]:
    st.header("Coverage & Propagation Results")
    st.markdown("> **Student 3 → Student 4 interface** — these fields feed directly into the routing module.")

    with st.spinner("Computing coverage grid…"):
        xs, ys, grid = _get_grid(grid_res, alpha)

    env    = sc["environment"]
    thr_od = env["coverage_threshold_outdoor_dbm"]
    thr_in = env["coverage_threshold_indoor_dbm"]
    cov    = {
        "outdoor_pct": round(100*float(np.sum(grid >= thr_od))/grid.size, 1),
        "indoor_pct":  round(100*float(np.sum(grid >= thr_in))/grid.size, 1),
    }

    # KPI metrics row
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Outdoor Coverage", f"{cov['outdoor_pct']}%",
              f"threshold {thr_od} dBm")
    c2.metric("Indoor Coverage",  f"{cov['indoor_pct']}%",
              f"threshold {thr_in} dBm")
    c3.metric("Max Rx Power",     f"{grid.max():.1f} dBm")
    c4.metric("Min Rx Power",     f"{grid.min():.1f} dBm")
    c5.metric("Coverage Radius",  f"{_coverage_radius(sc):.2f} km")

    # Heatmap
    col_map, col_lb = st.columns([2, 1])
    with col_map:
        fig, ax = plt.subplots(figsize=(8, 7))
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#0d1117")
        norm = mcolors.Normalize(vmin=-130, vmax=-50)
        pcm  = ax.pcolormesh(xs, ys, grid, cmap="RdYlGn", norm=norm, shading="auto")
        cbar = fig.colorbar(pcm, ax=ax, pad=0.02, shrink=0.85)
        cbar.set_label("Received power (dBm)", color="white", fontsize=9)
        cbar.ax.yaxis.set_tick_params(color="white")
        plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")
        for thr, ls, col, lbl in [
            (thr_od, "--", "white", f"{thr_od} dBm outdoor"),
            (thr_in, ":",  "cyan",  f"{thr_in} dBm indoor"),
        ]:
            try:
                cs = ax.contour(xs, ys, grid, levels=[thr],
                                colors=[col], linewidths=2, linestyles=ls)
                ax.clabel(cs, fmt=f"{thr} dBm", fontsize=8, colors=[col])
            except Exception:
                pass

        # Site markers + backhaul lines
        cr1 = next(s for s in sc["sites"] if s["name"] == "CR-1")
        cr2 = next(s for s in sc["sites"] if s["name"] == "CR-2")
        for bs in [s for s in sc["sites"] if s["type"] == "base_station"]:
            colour = "#E74C3C" if bs["name"] == fail_link else "white"
            ax.plot(bs["x_km"], bs["y_km"], "^", color=colour, markersize=11,
                    markeredgecolor="black", markeredgewidth=1.3, zorder=6)
            ax.annotate(bs["name"], (bs["x_km"], bs["y_km"]),
                        xytext=(3, 7), textcoords="offset points",
                        fontsize=8, color=colour, fontweight="bold")
            if bs["name"] != fail_link:
                ax.plot([cr1["x_km"], bs["x_km"]], [cr1["y_km"], bs["y_km"]],
                        "w-", alpha=0.25, lw=1)
                ax.plot([cr2["x_km"], bs["x_km"]], [cr2["y_km"], bs["y_km"]],
                        color="cyan", alpha=0.12, lw=0.8, ls="--")
        ax.plot(cr1["x_km"], cr1["y_km"], "s", color="gold", markersize=12,
                markeredgecolor="black", zorder=6)
        ax.annotate("CR-1", (cr1["x_km"], cr1["y_km"]),
                    xytext=(4, 8), textcoords="offset points",
                    fontsize=8, color="gold", fontweight="bold")
        ax.plot(cr2["x_km"], cr2["y_km"], "s", color="gold", markersize=12,
                markeredgecolor="black", zorder=6)
        ax.annotate("CR-2", (cr2["x_km"], cr2["y_km"]),
                    xytext=(4, 8), textcoords="offset points",
                    fontsize=8, color="gold", fontweight="bold")
        ax.plot([cr1["x_km"], cr2["x_km"]], [cr1["y_km"], cr2["y_km"]],
                color="gold", lw=2, alpha=0.8)

        ax.set_xlabel("East–West (km)", color="white")
        ax.set_ylabel("North–South (km)", color="white")
        ax.tick_params(colors="white")
        for sp in ax.spines.values():
            sp.set_edgecolor("#444")
        ax.set_title("COST 231 Hata @ 1800 MHz — Best-Server Rx Power",
                     color="white", fontsize=11)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    with col_lb:
        # ── EXACT SCREENSHOT TABLE: coverage_propagation results ──────────────
        st.subheader("Coverage & propagation results")
        st.caption("**Student 3 — Wireless lead**")

        lb_table = site_link_budget_table(sc)
        lb_df    = pd.DataFrame(lb_table)

        # Rename columns to match screenshot exactly
        lb_df_display = lb_df.rename(columns={
            "site_id":             "site_id",
            "received_signal_dbm": "received_signal_dbm",
            "path_loss_db":        "path_loss_db",
            "link_margin_db":      "link_margin_db",
            "coverage_radius_km":  "coverage_radius_km",
            "link_quality":        "link_quality",
        })

        def _colour_quality(val):
            colours = {"good": "color: #2ECC71", "marginal": "color: #F39C12", "poor": "color: #E74C3C"}
            return colours.get(val, "")

        styled = lb_df_display.style.applymap(_colour_quality, subset=["link_quality"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # CSV export button (screenshot shows CSV badge)
        csv_str = lb_df.to_csv(index=False)
        st.download_button("⬇ Download CSV", csv_str,
                           "coverage_propagation.csv", "text/csv",
                           use_container_width=True)

        # Threshold justification
        st.markdown("""
        **Threshold justification**
        - **−90 dBm outdoor**: Minimum RSRP per 3GPP TS 36.213 for LTE
          connected mode in suburban-rural terrain
        - **−80 dBm indoor**: Adds 10 dB indoor penetration loss margin
          (concrete/brick building, scenario config)
        """)


# =============================================================================
# TAB 2 — Link Quality & Backhaul Capacity
# =============================================================================

with tabs[1]:
    st.header("Link Quality & Backhaul Capacity")

    with st.spinner("Validating backhaul links…"):
        traffic_df  = _get_traffic(alpha)
        bh_results  = validate_backhaul_capacity(sc, traffic_df, alpha)
        bh_df       = pd.DataFrame(bh_results)

    # Summary metrics
    good_ct = sum(1 for r in bh_results if r["link_status"] == "good")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Links: Good",     good_ct)
    c2.metric("Links: Marginal", sum(1 for r in bh_results if r["link_status"] == "marginal"))
    c3.metric("Links: Poor",     sum(1 for r in bh_results if r["link_status"] == "poor"))
    c4.metric("Peak utilisation",f"{max(r['link_utilisation'] for r in bh_results)*100:.2f}%")

    st.markdown("---")

    # Primary vs backup link usage chart — Student 4 requirement
    col_chart, col_table = st.columns([2, 1])
    with col_chart:
        st.subheader("Per-Link Usage (Primary vs Backup)")
        sites   = [r["site"] for r in bh_results]
        demand  = [r["demand_mbps"] for r in bh_results]
        cap     = [r["capacity_mbps"] for r in bh_results]
        colours = ["#2ECC71" if r["link_status"] == "good"
                   else "#F39C12" if r["link_status"] == "marginal"
                   else "#E74C3C" for r in bh_results]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
        fig.patch.set_facecolor("#0d1117")
        x = np.arange(len(sites))

        for ax in (ax1, ax2):
            ax.set_facecolor("#0d1117")
            ax.tick_params(colors="white")
            for sp in ax.spines.values():
                sp.set_edgecolor("#444")

        ax1.bar(x, demand, color=colours, width=0.5)
        ax1.bar(x, cap, width=0.5, color="none", edgecolor="#444", ls="--", lw=1.5)
        for i, (d, c) in enumerate(zip(demand, cap)):
            ax1.text(i, d + 0.05, f"{d:.2f}", ha="center", fontsize=8, color="white")
        ax1.set_xticks(x); ax1.set_xticklabels(sites, color="white")
        ax1.set_ylabel("Mbps", color="white")
        ax1.set_title(f"Demand vs Capacity (α={alpha})", color="white")

        util_pct = [r["link_utilisation"]*100 for r in bh_results]
        safe_zone= sc["qos"]["utilisation_zones"]["safe"] * 100
        col2 = ["#2ECC71" if u < safe_zone else "#F39C12" if u < 90 else "#E74C3C"
                 for u in util_pct]
        ax2.bar(x, util_pct, color=col2, width=0.5)
        ax2.axhline(safe_zone, color="orange", ls="--", lw=1.5, label=f"Safe ({safe_zone:.0f}%)")
        ax2.axhline(90, color="red", ls=":", lw=1.5, label="Action (90%)")
        for i, u in enumerate(util_pct):
            ax2.text(i, u + 0.2, f"{u:.1f}%", ha="center", fontsize=8, color="white")
        ax2.set_xticks(x); ax2.set_xticklabels(sites, color="white")
        ax2.set_ylabel("Utilisation (%)", color="white")
        ax2.set_title("Link Utilisation", color="white")
        ax2.set_ylim(0, 110)
        ax2.legend(fontsize=8, facecolor="#161b22", labelcolor="white")
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    with col_table:
        st.subheader("Link Status")
        disp = bh_df[["site", "primary_dist_km", "primary_margin_db",
                       "rain_attenuation_db", "margin_after_rain_db",
                       "calls_routed_primary", "calls_routed_backup",
                       "link_status"]].copy()
        disp.columns = ["Site","Dist (km)","Margin (dB)","Rain (dB)",
                         "Net Margin","Primary calls","Backup calls","Status"]

        def _st(val):
            return {"good": "color:#2ECC71", "marginal": "color:#F39C12",
                    "poor": "color:#E74C3C"}.get(val, "")
        st.dataframe(disp.style.applymap(_st, subset=["Status"]),
                     use_container_width=True, hide_index=True)

    # Rain attenuation section
    st.markdown("---")
    st.subheader("🌧️ Rain Attenuation — Botswana Zone H (ITU-R P.838-3)")
    rain_rows = []
    bh_cfg = sc["backhaul"]
    for r in bh_results:
        rain = r["rain_attenuation_db"]
        rain_rows.append({
            "Site": r["site"],
            "Distance (km)": r["primary_dist_km"],
            "Rain att. (dB)": rain,
            "Margin w/o rain (dB)": r["primary_margin_db"],
            "Net margin (dB)": r["margin_after_rain_db"],
            "Status after rain": "✅ OK" if r["margin_after_rain_db"] > 0 else "❌ FAIL",
        })
    st.dataframe(pd.DataFrame(rain_rows), use_container_width=True, hide_index=True)

    # Backbone 13 GHz budget
    st.markdown("---")
    st.subheader("13 GHz Backbone — CR-1 ↔ CR-2")
    cr1 = next(s for s in sc["sites"] if s["name"] == "CR-1")
    cr2 = next(s for s in sc["sites"] if s["name"] == "CR-2")
    d_bb = math.hypot(cr1["x_km"]-cr2["x_km"], cr1["y_km"]-cr2["y_km"])
    bb   = sc["backbone_13ghz"]
    mw_bb= microwave_budget(bb["frequency_ghz"], d_bb, bb)
    rain_bb = rain_attenuation_db(d_bb, bb["frequency_ghz"])
    b1,b2,b3,b4 = st.columns(4)
    b1.metric("FSPL",        f"{mw_bb['fspl_db']:.1f} dB")
    b2.metric("Rx Power",    f"{mw_bb['rx_power_dbm']:.1f} dBm")
    b3.metric("Link Margin", f"{mw_bb['link_margin_db']:.1f} dB",
              delta=f"{mw_bb['link_margin_db']-bb['min_fade_margin_db']:+.1f} vs req")
    b4.metric("Status",      mw_bb["status"])
    st.info(f"Rain attenuation at {bb['frequency_ghz']} GHz, {d_bb:.1f} km: **{rain_bb} dB** — "
            f"net margin after rain: **{mw_bb['link_margin_db']-rain_bb:.1f} dB**")


# =============================================================================
# TAB 3 — Erlang B & Grade of Service
# =============================================================================

with tabs[2]:
    st.header("Erlang B Analysis & Grade of Service")

    with st.spinner("Computing GoS…"):
        tt  = _get_teletraffic(alpha)
        gos = grade_of_service(sc, tt, alpha)

    # GoS summary
    tc = sc["traffic"]
    st.subheader("Grade of Service (GoS) — per site")
    col_gos, col_erl = st.columns([1, 2])

    with col_gos:
        gos_df = pd.DataFrame(gos["per_site"])
        gos_display = gos_df[["site","voice_offered_erl","voice_channels_N",
                               "voice_blocking","video_blocking","gos_target","gos_met"]].copy()
        gos_display.columns = ["Site","Voice A (Erl)","N circuits",
                                "Voice B","Video B","Target B","GoS met"]

        def _met(val):
            return "color:#2ECC71" if val else "color:#E74C3C"
        st.dataframe(gos_display.style.applymap(_met, subset=["GoS met"]),
                     use_container_width=True, hide_index=True)

        all_ok = gos["all_gos_met"]
        if all_ok:
            st.success(f"✅ All sites meet GoS target B ≤ {gos['gos_target']:.1%}")
        else:
            st.error(f"❌ GoS violated — worst site: {gos['worst_site']} "
                     f"(B={gos['worst_blocking']:.4%})")

        # Network-level GoS targets (Student 4 requirement)
        st.markdown("""
        **Network-Level GoS Targets**
        | Traffic class | GoS target |
        |---|---|
        | Voice (primary links) | B ≤ 2% (Erlang B) |
        | Voice (high-priority) | B ≤ 0.5–1% |
        | Video sessions | B ≤ 2% |
        | Telemetry | N/A (connectionless) |
        """)

    with col_erl:
        # Erlang B curves — blocking vs N circuits
        st.subheader("Erlang B Curves (blocking vs circuits)")
        A_voice = tc["voice"]["offered_load_erl"] * alpha
        A_video = tc["video"]["offered_load_erl"] * alpha
        A_tel   = tc["telemetry"]["offered_load_erl"] * alpha

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
        fig.patch.set_facecolor("#0d1117")
        for ax in (ax1, ax2):
            ax.set_facecolor("#0d1117")
            ax.tick_params(colors="white")
            for sp in ax.spines.values(): sp.set_edgecolor("#444")

        N_range = range(0, 16)

        for A, label, col in [
            (A_voice, f"Voice (A={A_voice:.2f} Erl)", "#3498DB"),
            (A_video, f"Video (A={A_video:.2f} Erl)", "#E74C3C"),
            (A_tel,   f"Telemetry (A={A_tel:.2f} Erl)", "#2ECC71"),
        ]:
            y = [erlang_b(A, n) for n in N_range]
            ax1.semilogy(list(N_range), y, "-o", color=col, label=label, markersize=4, lw=2)

        ax1.axhline(tc["voice"]["kpi_blocking_prob"], color="orange", ls="--",
                    lw=1.5, label=f"Target B={tc['voice']['kpi_blocking_prob']:.1%}")
        ax1.set_xlabel("Number of circuits N", color="white")
        ax1.set_ylabel("Blocking probability B", color="white")
        ax1.set_title(f"Erlang B Curves (α={alpha})", color="white")
        ax1.legend(fontsize=8, facecolor="#161b22", labelcolor="white")
        ax1.grid(True, alpha=0.2)

        # Blocking vs load for fixed N=4
        N_fixed = 4
        A_range = np.linspace(0.1, 5.0, 200)
        B_range = [erlang_b(A, N_fixed) for A in A_range]
        ax2.semilogy(A_range, B_range, "#3498DB", lw=2)
        ax2.axvline(A_voice, color="#3498DB", ls="--", lw=1.5,
                    label=f"Voice load ({A_voice:.2f} Erl)")
        ax2.axhline(tc["voice"]["kpi_blocking_prob"], color="orange", ls="--",
                    lw=1.5, label=f"Target B={tc['voice']['kpi_blocking_prob']:.1%}")
        ax2.fill_between(A_range, tc["voice"]["kpi_blocking_prob"],
                         [max(b, 1e-10) for b in B_range],
                         where=[b > tc["voice"]["kpi_blocking_prob"] for b in B_range],
                         alpha=0.2, color="#E74C3C")
        ax2.set_xlabel("Offered load A (Erlang)", color="white")
        ax2.set_ylabel("Blocking probability B", color="white")
        ax2.set_title(f"Blocking vs Load  (N={N_fixed} circuits)", color="white")
        ax2.legend(fontsize=8, facecolor="#161b22", labelcolor="white")
        ax2.grid(True, alpha=0.2)
        ax2.set_ylim(1e-8, 1.5)

        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    # Dimensioning table from Student 2
    st.markdown("---")
    st.subheader("Voice Channel Dimensioning Table")
    st.dataframe(tt["dimensioning_table"], use_container_width=True, hide_index=True)


# =============================================================================
# TAB 4 — Call Setup & Signaling (Student 4 requirement)
# =============================================================================

with tabs[3]:
    st.header("Call Setup Metrics & Signaling")
    st.markdown("> **Student 4 data feed** — setup delay, link usage, BHCA, signaling load.")

    sig_df  = compute_signaling_load(sc, alpha)
    sig_sum = signaling_summary(sc, alpha)

    # ── Call Setup Delay ──────────────────────────────────────────────────────
    st.subheader("📊 Setup Delay (ms) — time from call attempt to connection")
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Min setup delay", f"{sig_df['call_setup_delay_ms'].min():.1f} ms")
    col_m2.metric("Max setup delay", f"{sig_df['call_setup_delay_ms'].max():.1f} ms",
                   delta=f"vs {sig_df['kpi_target_ms'].iloc[0]} ms KPI",
                   delta_color="inverse")
    col_m3.metric("Total BHCA",     f"{sig_sum['total_bhca']:.0f}")
    col_m4.metric("All KPIs met",   "✅ Yes" if sig_sum["all_kpis_met"] else "❌ No")

    # Setup delay chart
    fig, ax = plt.subplots(figsize=(10, 3))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")
    sites  = sig_df["site"].tolist()
    delays = sig_df["call_setup_delay_ms"].tolist()
    target = sig_df["kpi_target_ms"].iloc[0]
    colours= ["#2ECC71" if d <= target else "#E74C3C" for d in delays]
    ax.bar(sites, delays, color=colours, width=0.5)
    ax.axhline(target, color="orange", ls="--", lw=2, label=f"KPI target {target} ms")
    for i, d in enumerate(delays):
        ax.text(i, d + 0.3, f"{d:.0f} ms", ha="center", fontsize=9, color="white")
    ax.tick_params(colors="white")
    ax.set_ylabel("Setup delay (ms)", color="white")
    ax.set_title("Call Setup Delay per BS (Propagation + Processing)", color="white")
    ax.legend(fontsize=9, facecolor="#161b22", labelcolor="white")
    for sp in ax.spines.values(): sp.set_edgecolor("#444")
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    st.markdown("---")

    # ── Link Usage / Selection  (primary vs backup) ───────────────────────────
    st.subheader("🔀 Link Usage / Selection — Primary vs Backup")

    bh_results = validate_backhaul_capacity(sc, _get_traffic(alpha), alpha)
    link_rows  = []
    for r in bh_results:
        prim_ok = r["primary_status"] == "PASS"
        link_rows.append({
            "BS Site":             r["site"],
            "Primary link":        r["primary_link"],
            "Primary margin (dB)": r["primary_margin_db"],
            "Primary status":      r["primary_status"],
            "Backup link":         r["backup_link"],
            "Backup margin (dB)":  r["backup_margin_db"],
            "Backup status":       r["backup_status"],
            "Active link":         "Primary" if prim_ok else "Backup",
            "Calls via primary":   "All" if prim_ok else "0",
            "Calls via backup":    "0"  if prim_ok else "All",
        })
    link_df = pd.DataFrame(link_rows)

    def _link_col(val):
        if val == "PASS":    return "color:#2ECC71"
        if val == "FAIL":    return "color:#E74C3C"
        if val == "Primary": return "color:#58a6ff"
        if val == "Backup":  return "color:#F39C12"
        return ""
    st.dataframe(
        link_df.style.applymap(_link_col, subset=["Primary status","Backup status","Active link"]),
        use_container_width=True, hide_index=True
    )

    # Failure injection effect
    if fail_link != "None":
        st.warning(f"⚠️ Failure injected on {fail_link}: all {fail_link} calls rerouted to backup link.")
        affected = next((r for r in bh_results if r["site"] == fail_link), None)
        if affected:
            bk = affected["backup_margin_db"]
            st.info(f"Backup link margin: **{bk:.1f} dB** — "
                    f"{'✅ sufficient' if bk >= sc['backhaul']['min_fade_margin_db'] else '❌ insufficient'}")

    st.markdown("---")

    # ── Signaling full table ───────────────────────────────────────────────────
    st.subheader("Signaling Load per BS")
    sig_display = sig_df.copy()
    sig_display.columns = ["Site","BHCA","Sig msgs/hr","Sig load (bps)",
                            "Setup delay (ms)","KPI target (ms)","KPI met"]
    def _kpi(val):
        return "color:#2ECC71" if val else "color:#E74C3C"
    st.dataframe(sig_display.style.applymap(_kpi, subset=["KPI met"]),
                 use_container_width=True, hide_index=True)

    # Number of calls routed per link
    st.markdown("---")
    st.subheader("Number of Calls Routed per Link")
    call_rows = []
    for r in bh_results:
        A_voice = sc["traffic"]["voice"]["offered_load_erl"] * alpha
        A_video = sc["traffic"]["video"]["offered_load_erl"] * alpha
        expected_calls = (A_voice + A_video)  # concurrent active sessions = Erlang value
        call_rows.append({
            "BS Site":                    r["site"],
            "Arrival rate (voice/hr)":    sc["traffic"]["voice"]["arrival_rate_per_hour"] * alpha,
            "Arrival rate (video/hr)":    sc["traffic"]["video"]["arrival_rate_per_hour"] * alpha,
            "Expected concurrent calls":  round(expected_calls, 2),
            "Calls on primary link":      round(expected_calls, 2) if r["primary_status"] == "PASS" else 0,
            "Calls on backup link":       0 if r["primary_status"] == "PASS" else round(expected_calls, 2),
        })
    st.dataframe(pd.DataFrame(call_rows), use_container_width=True, hide_index=True)

    # Delay KPIs from Student 2
    st.markdown("---")
    st.subheader("P95 Delay KPIs (from Student 2 teletraffic)")
    tt = _get_teletraffic(alpha)
    st.dataframe(tt["delay_kpis"], use_container_width=True, hide_index=True)


# =============================================================================
# TAB 5 — Frequency Reuse & Sectorization
# =============================================================================

with tabs[4]:
    st.header("Frequency Reuse & Sectorization")

    reuse = frequency_reuse_cluster(reuse_N, 20, 5)
    sect  = sectorization_analysis(reuse_N, sectors, 20, 5)

    col_m, col_fig = st.columns([1, 2])
    with col_m:
        st.subheader("Reuse Metrics")
        m1,m2,m3,m4 = st.columns(2)
        m1.metric("Cluster N",         reuse["reuse_factor"])
        m2.metric("D/R ratio",          reuse["D_R_ratio"])
        m3.metric("Channels/cell",       reuse["channels_per_cell"])
        m4.metric("Approx SIR (dB)",     reuse["approx_SIR_dB"])

        st.metric("Spectral efficiency", f"{reuse['spectral_efficiency']:.2f}")

        st.markdown("---")
        st.subheader("Sectorization")
        s1,s2 = st.columns(2)
        s1.metric("Sectors/site", sectors)
        s2.metric("Capacity gain", f"×{sect['capacity_gain_x']:.1f}")
        st.info(f"**{sectors}-sector** config at N={reuse_N} "
                f"gives **×{sect['capacity_gain_x']:.1f}** capacity vs omni. "
                f"SIR ≈ {sect['sectorized']['approx_SIR_dB']:.1f} dB.")

        st.markdown("""
        **Engineering tradeoff**
        | Factor | 3-sector | Omni |
        |---|---|---|
        | Capacity gain | ×3–4 | ×1 |
        | Interference | Lower | Higher |
        | Cost | +2 antennas/site | Baseline |
        | Handover complexity | Higher | Lower |
        """)

    with col_fig:
        st.subheader(f"Hexagonal Reuse Pattern — N={reuse_N}")
        fig = plot_reuse_pattern(reuse_N)
        st.pyplot(fig)
        plt.close(fig)


# =============================================================================
# TAB 6 — Stress Test & Breaking Point
# =============================================================================

with tabs[5]:
    st.header("Stress Testing & Breaking Point Analysis")

    with st.spinner("Running stress sweep…"):
        sweep = stress_sweep(sc)
        bp    = find_breaking_point(sc)
        bw_sweep = stress_bandwidth_sweep(sc)

    # Breaking point banner
    bp_alpha = float(bp["first_failure_alpha"])
    if alpha >= bp_alpha:
        st.error(f"🔴 **BREAKING POINT REACHED** at α={bp_alpha:.1f} "
                 f"— {bp['first_failure_kpi']} exceeded target")
    else:
        st.success(f"✅ Operating safely at α={alpha:.1f} — "
                   f"breaking point is α={bp_alpha:.1f}")

    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Breaking point α",    f"{bp_alpha:.1f}")
    m2.metric("First KPI failed",    bp["first_failure_kpi"])
    m3.metric("KPI value at break",  f"{float(bp['first_failure_value']):.4f}")
    m4.metric("KPI target",          bp["first_failure_target"])

    st.info(bp["bottleneck_description"])
    st.markdown("---")

    col_voice, col_bw = st.columns(2)
    with col_voice:
        st.subheader("Voice Blocking vs Load Multiplier")
        fig, ax = plt.subplots(figsize=(7, 4))
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#0d1117")
        ax.semilogy(sweep["load_multiplier"], sweep["voice_blocking"],
                    "o-", color="#3498DB", lw=2, markersize=5)
        ax.axhline(sc["traffic"]["voice"]["kpi_blocking_prob"],
                   color="orange", ls="--", lw=2, label="2% KPI target")
        ax.axvline(bp_alpha, color="#E74C3C", ls="-.", lw=2,
                   label=f"Breaking point α={bp_alpha:.1f}")
        ax.set_xlabel("Load multiplier α", color="white")
        ax.set_ylabel("Blocking probability", color="white")
        ax.set_title("Voice Blocking vs Load", color="white")
        ax.legend(fontsize=9, facecolor="#161b22", labelcolor="white")
        ax.tick_params(colors="white")
        ax.grid(True, alpha=0.2)
        for sp in ax.spines.values(): sp.set_edgecolor("#444")
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    with col_bw:
        st.subheader("Bandwidth Demand vs Load")
        fig, ax = plt.subplots(figsize=(7, 4))
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#0d1117")
        ax.stackplot(bw_sweep["load_multiplier"],
                     bw_sweep["telemetry_mbps"] * 5,   # ×5 sites
                     bw_sweep["voice_mbps"] * 5,
                     bw_sweep["video_mbps"] * 5,
                     labels=["Telemetry ×5", "Voice ×5", "Video ×5"],
                     colors=["#2ECC71", "#3498DB", "#E74C3C"], alpha=0.75)
        ax.axhline(100, color="orange", ls="--", lw=2, label="100 Mbps link cap")
        ax.set_xlabel("Load multiplier α", color="white")
        ax.set_ylabel("Aggregate demand (Mbps)", color="white")
        ax.set_title("Traffic Demand Breakdown", color="white")
        ax.legend(fontsize=9, facecolor="#161b22", labelcolor="white")
        ax.tick_params(colors="white")
        ax.grid(True, alpha=0.2)
        for sp in ax.spines.values(): sp.set_edgecolor("#444")
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    # Full sweep table
    st.markdown("---")
    st.subheader("Full Stress Sweep Table")
    sweep_disp = sweep.copy()
    def _kpi_row(val):
        return "color:#E74C3C" if val == False else "color:#2ECC71"
    st.dataframe(
        sweep_disp.style.applymap(_kpi_row, subset=["voice_kpi_met","telemetry_kpi_met",
                                                      "video_kpi_met","all_kpis_met"]),
        use_container_width=True, hide_index=True
    )

    # Coverage deep-dive at break point
    st.markdown("---")
    st.subheader("Coverage Sensitivity at Breaking Point")
    st.markdown(f"""
    At **α={bp_alpha:.1f}** (breaking point):
    - Voice blocking: **{float(bp['first_failure_value']):.2%}** > target {bp['first_failure_target']:.1%}
    - Required additional channels per site: **1** (N=4→5)
    - Voice offered load at failure: **{bp['n_baseline']} circuits** insufficient
    - **Recommended action**: Upgrade from N=4 to N=5 circuits per site to restore GoS
    """)

"""
dashboard.py
------------
Streamlit dashboard for TELE 527 Group 1 - District Telehealth Network.

Tabs:
  1. Network Overview       - sites, links, offered load table
  2. QoS Performance        - dimensioning, delay KPIs, Erlang curves
  3. Coverage & Power       - placeholder for Student 3 (wireless/propagation)
  4. Microwave Backhaul     - placeholder for Student 4 (backhaul module)
  5. Forecasting            - utilisation growth, Erlang forecast, upgrade plan
  6. Stress & Comparison    - baseline vs stress vs failure KPI comparison

Run with:
    streamlit run dashboard.py

Student 2 responsibility - Traffic and Teletraffic Lead
TELE 527 | Group 1 | BIUST | 2026
"""

import os
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# -----------------------------------------------------------------------
# Page configuration
# -----------------------------------------------------------------------

st.set_page_config(
    page_title="TELE 527 | Group 1 | District Telehealth Network",
    page_icon="📡",
    layout="wide",
)

# -----------------------------------------------------------------------
# Load scenario (cached so it only reads the file once per session)
# -----------------------------------------------------------------------

@st.cache_data
def load_scenario_cached(path: str) -> dict:
    from traffic import load_scenario
    return load_scenario(path)


SCENARIO_PATH = os.path.join(os.path.dirname(__file__), "..", "scenario.yaml")
sc = load_scenario_cached(SCENARIO_PATH)

# -----------------------------------------------------------------------
# Sidebar — interactive controls
# -----------------------------------------------------------------------

st.sidebar.title("Simulation Controls")
st.sidebar.markdown("---")

alpha = st.sidebar.slider(
    "Load multiplier  α",
    min_value=1.0,
    max_value=5.0,
    value=1.0,
    step=0.5,
    help="1.0 = normal busy-hour load. Increase to stress-test the network.",
)

reuse_factor = st.sidebar.selectbox(
    "Frequency reuse factor  K",
    options=[1, 3, 4, 7, 9, 12],
    index=2,
    help="Used by the wireless coverage module (Student 3).",
)

enable_failure = st.sidebar.checkbox(
    "Inject backhaul failure (BS1 → CR-1)",
    value=False,
    help="Removes the primary BS1–CR-1 link and forces traffic via CR-2 backup.",
)

st.sidebar.markdown("---")
rerun = st.sidebar.button("Re-run scenario", type="primary")

st.sidebar.markdown(
    "**Scenario:** District telehealth & emergency network  \n"
    "**Sites:** 5 BS + 2 core routers  \n"
    "**Traffic classes:** Telemetry · Voice · Video  \n"
    "**Backhaul:** 100 Mbps microwave per link"
)

# -----------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------

st.title("TELE 527 — District Telehealth & Emergency Network")
st.caption(
    f"Group 1 | BIUST | 2026  ·  "
    f"Load multiplier α = **{alpha}**  ·  "
    f"Reuse factor K = **{reuse_factor}**  ·  "
    f"Backhaul failure = **{'ON' if enable_failure else 'OFF'}**"
)

# -----------------------------------------------------------------------
# Compute results for current alpha
# -----------------------------------------------------------------------

@st.cache_data
def get_teletraffic(alpha: float):
    from teletraffic import run_teletraffic
    sc_ = load_scenario_cached(SCENARIO_PATH)
    return run_teletraffic(sc_, alpha)


@st.cache_data
def get_traffic_matrix(alpha: float):
    from traffic import compute_traffic_matrix, compute_offered_load
    sc_ = load_scenario_cached(SCENARIO_PATH)
    return compute_traffic_matrix(sc_, alpha), compute_offered_load(sc_, alpha)


@st.cache_data
def get_forecasting():
    from forecasting import run_forecasting
    sc_ = load_scenario_cached(SCENARIO_PATH)
    return run_forecasting(sc_)


tt      = get_teletraffic(alpha)
matrix, offered = get_traffic_matrix(alpha)
fc_data = get_forecasting()

# -----------------------------------------------------------------------
# Tabs
# -----------------------------------------------------------------------

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📍 Network Overview",
    "📊 QoS Performance",
    "📡 Coverage & Power",
    "🔗 Microwave Backhaul",
    "📈 Forecasting",
    "⚡ Stress & Comparison",
])


# ===================================================================
# TAB 1 — Network Overview
# ===================================================================

with tab1:
    st.subheader("Network Topology")

    col_sites, col_links = st.columns(2)

    with col_sites:
        st.markdown("**Sites**")
        sites_df = pd.DataFrame([
            {"Name": s["name"], "Label": s["label"], "Type": s["type"],
             "x (km)": s["x_km"], "y (km)": s["y_km"]}
            for s in sc["sites"]
        ])
        st.dataframe(sites_df, use_container_width=True, hide_index=True)

    with col_links:
        st.markdown("**Links summary**")
        links_df = pd.DataFrame([
            {"From": l["from"], "To": l["to"],
             "Cap (Mbps)": l["capacity_mbps"],
             "Delay (ms)": l["delay_ms"],
             "Type": l["type"], "Role": l["role"]}
            for l in sc["links"]
        ])
        # Remove duplicates (show unique from-to pairs)
        links_summary = (
            links_df.groupby(["From", "To", "Type", "Role"])
            .first().reset_index()
        )
        st.dataframe(links_summary, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader(f"Offered Load per Site  (α = {alpha})")
    st.dataframe(
        offered.pivot(index="site", columns="service_class", values="offered_load_erl")
               .round(4),
        use_container_width=True,
    )

    st.subheader(f"Traffic Demand per Backhaul Link  (α = {alpha})")
    st.dataframe(matrix, use_container_width=True, hide_index=True)

    # Traffic matrix bar chart
    from plots import fig_traffic_matrix_bar
    st.pyplot(fig_traffic_matrix_bar(sc, alpha), use_container_width=True)


# ===================================================================
# TAB 2 — QoS Performance
# ===================================================================

with tab2:
    st.subheader(f"Voice Channel Dimensioning  (α = {alpha})")
    dim_df = tt["dimensioning_table"].copy()
    dim_df["achieved_blocking_%"] = (dim_df["achieved_blocking"] * 100).round(4)
    st.dataframe(
        dim_df[["site", "offered_load_erl", "channels_required",
                "achieved_blocking_%", "kpi_met"]],
        use_container_width=True,
        hide_index=True,
    )

    trunk = tt["trunk"]
    st.info(
        f"**Backhaul trunk** (all 5 sites):  "
        f"A = {trunk['offered_load_erl']} Erl  →  "
        f"N = {trunk['channels_required']} circuits  →  "
        f"B = {trunk['achieved_blocking']*100:.4f}%  "
        f"({'✅ KPI met' if trunk['kpi_met'] else '❌ KPI FAILED'})  |  "
        f"Trunking gain = **{trunk['trunking_gain_channels']} circuits saved**"
    )

    st.markdown("---")
    st.subheader(f"P95 Delay KPIs  (α = {alpha})")
    delay_df = tt["delay_kpis"].copy()
    delay_df["rho_%"] = (delay_df["rho"] * 100).round(4)
    st.dataframe(
        delay_df[["site", "service_class", "offered_load_erl",
                  "rho_%", "p95_delay_ms", "kpi_target_ms", "kpi_met"]],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    col_eb, col_bvl = st.columns(2)

    with col_eb:
        st.markdown("**Erlang B curve — all classes**")
        from plots import fig_erlang_b_curve
        st.pyplot(fig_erlang_b_curve(sc), use_container_width=True)

    with col_bvl:
        st.markdown("**Voice blocking vs offered load  (fixed N_baseline)**")
        from plots import fig_blocking_vs_load
        st.pyplot(fig_blocking_vs_load(sc), use_container_width=True)

    st.markdown("**P95 delay vs load multiplier**")
    from plots import fig_p95_delay_vs_alpha
    st.pyplot(fig_p95_delay_vs_alpha(sc), use_container_width=True)


# ===================================================================
# TAB 3 — Coverage & Power  (Student 3 placeholder)
# ===================================================================

with tab3:
    st.subheader("Coverage & Received Power")
    st.warning(
        "⚠️  This tab is owned by **Student 3 (Wireless Planning Lead)**.  \n"
        "Plug in the outputs of `propagation.py` and `wireless.py` here.  \n\n"
        "**Expected inputs from Student 2 already available:**  \n"
        "- `compute_offered_load(sc, alpha)` — traffic demand per site  \n"
        "- `dimension_voice_per_site(sc, alpha)['channels_required']` — channel count  \n"
        "- Reuse factor K selected in the sidebar"
    )
    st.markdown("**Scenario radio environment parameters:**")
    env_df = pd.DataFrame(
        [{"Parameter": k, "Value": v} for k, v in sc["environment"].items()]
    )
    st.dataframe(env_df, use_container_width=True, hide_index=True)


# ===================================================================
# TAB 4 — Microwave Backhaul  (Student 4 placeholder)
# ===================================================================

with tab4:
    st.subheader("Microwave Backhaul Link Budget")
    st.warning(
        "⚠️  This tab is owned by **Student 4 (Signaling & Routing Lead)**.  \n"
        "Plug in the outputs of `backhaul.py` here."
    )
    st.markdown("**Scenario backhaul parameters:**")
    bh_df = pd.DataFrame(
        [{"Parameter": k, "Value": v} for k, v in sc["backhaul"].items()]
    )
    st.dataframe(bh_df, use_container_width=True, hide_index=True)

    st.markdown("**Link distances and delays (from topology):**")
    link_detail = pd.DataFrame([
        {"Link": f"{l['from']} → {l['to']}",
         "Capacity (Mbps)": l["capacity_mbps"],
         "Delay (ms)": l["delay_ms"],
         "Type": l["type"],
         "Role": l["role"]}
        for l in sc["links"]
        if l["type"] == "microwave" and l["role"] == "primary"
        and l["from"] != "CR-2"
    ])
    st.dataframe(link_detail, use_container_width=True, hide_index=True)


# ===================================================================
# TAB 5 — Forecasting
# ===================================================================

with tab5:
    st.subheader("Traffic Forecast and Upgrade Triggers")

    rec = fc_data["recommendation"]
    st.success(f"**Recommendation:**  {rec['full_text']}")

    col_t1, col_t2, col_t3 = st.columns(3)
    col_t1.metric("Planning trigger  (70%)", f"Year {rec['t_plan']:.1f}")
    col_t2.metric("Action trigger  (90%)",   f"Year {rec['t_act']:.1f}")
    col_t3.metric(
        "Voice channel upgrade",
        f"Year {rec['site_upgrade_year']}" if rec["site_upgrade_year"] else "Not needed",
    )

    st.markdown("---")
    col_f1, col_f2 = st.columns(2)

    with col_f1:
        st.markdown("**Link utilisation forecast**")
        from plots import fig_utilisation_forecast
        st.pyplot(fig_utilisation_forecast(sc), use_container_width=True)

    with col_f2:
        st.markdown("**Voice Erlang and blocking forecast**")
        from plots import fig_erlang_forecast
        st.pyplot(fig_erlang_forecast(sc), use_container_width=True)

    st.markdown("---")
    st.markdown("**Annual utilisation table**")
    st.dataframe(
        fc_data["utilisation"]["annual_table"],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("**Voice channel forecast table**")
    st.dataframe(fc_data["erlang"], use_container_width=True, hide_index=True)

    st.markdown("**Phased upgrade plan**")
    phases_df = pd.DataFrame(rec["phased_plan"])
    st.dataframe(phases_df, use_container_width=True, hide_index=True)


# ===================================================================
# TAB 6 — Stress & Comparison
# ===================================================================

with tab6:
    st.subheader("Breaking Point Study — Baseline vs Stress vs Failure")

    bp = tt["breaking_point"]
    if "first_failure_alpha" in bp:
        st.error(
            f"**First KPI failure** at α = **{bp['first_failure_alpha']}**  |  "
            f"KPI: `{bp['first_failure_kpi']}`  |  "
            f"Value: {bp['first_failure_value']:.4f}  "
            f"(target: {bp['first_failure_target']})  |  "
            f"Baseline circuits: N = {bp['n_baseline']}"
        )
    else:
        st.success(bp["bottleneck_description"])

    st.markdown("---")
    st.markdown("**Full stress sweep table**")
    sweep_df = tt["stress_sweep"].copy()
    sweep_df["voice_blocking_%"] = (sweep_df["voice_blocking"] * 100).round(4)
    st.dataframe(
        sweep_df[[
            "load_multiplier", "voice_offered_erl", "n_baseline",
            "voice_blocking_%", "voice_kpi_met",
            "telemetry_p95_ms", "telemetry_kpi_met",
            "video_p95_ms",     "video_kpi_met",
            "all_kpis_met",
        ]],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("**Stress sweep charts**")
    from plots import fig_stress_sweep
    st.pyplot(fig_stress_sweep(sc), use_container_width=True)

    st.markdown("---")
    st.subheader("Failure Scenario Comparison")

    if enable_failure:
        st.warning(
            "Backhaul failure injected: BS1 → CR-1 primary link removed.  \n"
            "Traffic reroutes via BS1 → CR-2 (backup, delay = 13 ms vs 8 ms primary).  \n\n"
            "**Routing module (Student 4) will show:**  \n"
            "- Reroute count  \n"
            "- Delay increase on BS1 path (+5 ms propagation overhead)  \n"
            "- Any capacity reduction on the backup link"
        )
        # Show the delay impact from the scenario backup link
        backup_delay = next(
            l["delay_ms"] for l in sc["links"]
            if l["from"] == "BS1" and l["to"] == "CR-2" and l["role"] == "backup"
        )
        primary_delay = next(
            l["delay_ms"] for l in sc["links"]
            if l["from"] == "BS1" and l["to"] == "CR-1" and l["role"] == "primary"
        )
        st.metric(
            "BS1 propagation delay",
            f"{backup_delay} ms  (via CR-2 backup)",
            delta=f"+{backup_delay - primary_delay} ms vs primary",
            delta_color="inverse",
        )
    else:
        st.info("Enable **'Inject backhaul failure'** in the sidebar to see the failure comparison.")
