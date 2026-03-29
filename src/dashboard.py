"""
dashboard.py
============
Student 3 — Wireless Planning Lead | TELE 527 Group 1

Streamlit dashboard tab for wireless planning outputs.
This file is designed to be imported by the group's main dashboard (Student 5)
OR run standalone with:

  streamlit run dashboard.py

Tabs exposed:
  1. Coverage & Received Power  (heatmap with interactive controls)
  2. Reuse & Sectorization      (cluster pattern + capacity table)
  3. Backhaul Link Budget       (interactive link budget calculator)
  4. Improvement Study          (before/after comparison)
"""

import os
import sys
import json
import numpy as np

import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

sys.path.insert(0, os.path.dirname(__file__))
from propagation import cost231_extension, received_power_dbm
from wireless import (
    build_coverage_grid,
    coverage_statistics,
    plot_coverage_heatmap,
    frequency_reuse_cluster,
    sectorization_analysis,
    plot_reuse_pattern,
    microwave_link_budget,
)

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TELE 527 | Wireless Planning",
    page_icon="📡",
    layout="wide",
)

st.title("📡 Wireless Planning — Student 3 | Group 1")
st.caption("District Telehealth & Emergency Network — TELE 527 PBL Dashboard")

tab1, tab2, tab3, tab4 = st.tabs([
    "Coverage & Received Power",
    "Frequency Reuse & Sectorization",
    "Microwave Backhaul",
    "Improvement Study",
])


# =============================================================================
# TAB 1 — Coverage Heatmap
# =============================================================================

with tab1:
    st.header("Coverage Heatmap")
    st.markdown("""
    Visualises received power across the 20 × 20 km district using the
    **COST 231 Hata** model at 1800 MHz.  
    Adjust the sliders to explore sensitivity — this is your breaking-point study.
    """)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Controls")
        tx_power = st.slider("Tx Power (dBm)", 30, 50, 46, 1)
        tx_gain  = st.slider("Tx Antenna Gain (dBi)", 10, 20, 17, 1)
        h_base   = st.slider("Base Station Height (m)", 15, 60, 35, 5)
        thr1     = st.slider("Threshold 1 (dBm)", -100, -70, -85, 1)
        thr2     = st.slider("Threshold 2 (dBm)", -110, -80, -95, 1)
        grid_res = st.select_slider("Grid resolution", [50, 80, 100, 120], value=80)

        sites_default = [(5, 5), (5, 15), (10, 10), (15, 5), (15, 15)]
        site_count = st.radio("Number of sites", [5, 6], horizontal=True)
        sites = sites_default
        if site_count == 6:
            sites = sites_default + [(10, 3)]

        run = st.button("▶ Compute Coverage", type="primary")

    with col2:
        if run or "coverage_grid" not in st.session_state:
            with st.spinner("Computing coverage grid…"):
                xs, ys, grid = build_coverage_grid(
                    sites,
                    grid_res     = grid_res,
                    area_km      = 20,
                    tx_power_dbm = tx_power,
                    tx_gain_dbi  = tx_gain,
                    rx_gain_dbi  = 0,
                    f_mhz        = 1800,
                    h_base       = h_base,
                )
                st.session_state["coverage_grid"] = (xs, ys, grid, sites)

        xs, ys, grid, cur_sites = st.session_state["coverage_grid"]

        fig, ax = plt.subplots(figsize=(7, 6))
        norm = mcolors.Normalize(vmin=-120, vmax=-50)
        pcm  = ax.pcolormesh(xs, ys, grid, cmap="RdYlGn", norm=norm, shading="auto")
        plt.colorbar(pcm, ax=ax, label="Rx power (dBm)")
        for thr, ls, col in [(thr1, "--", "white"), (thr2, ":", "cyan")]:
            cs = ax.contour(xs, ys, grid, levels=[thr],
                            colors=[col], linewidths=2, linestyles=ls)
            ax.clabel(cs, fmt=f"{thr} dBm", fontsize=8, colors=[col])
        for (sx, sy) in cur_sites:
            ax.plot(sx, sy, "^w", markersize=9, markeredgecolor="black")
        ax.set_xlabel("East–West (km)")
        ax.set_ylabel("North–South (km)")
        ax.set_title("COST 231 @ 1800 MHz — Best-Server Rx Power")
        st.pyplot(fig)
        plt.close(fig)

        # Statistics
        stats = coverage_statistics(grid, [thr1, thr2])
        c1, c2 = st.columns(2)
        c1.metric(f"Coverage ≥ {thr1} dBm", f"{stats[thr1]}%", "Good (voice/video)")
        c2.metric(f"Coverage ≥ {thr2} dBm", f"{stats[thr2]}%", "Edge (telemetry)")


# =============================================================================
# TAB 2 — Frequency Reuse & Sectorization
# =============================================================================

with tab2:
    st.header("Frequency Reuse & Sectorization")

    col1, col2 = st.columns([1, 2])

    with col1:
        N = st.selectbox("Reuse factor N", [1, 3, 4, 7, 12], index=2)
        S = st.radio("Sectors per site", [1, 3, 6], index=1, horizontal=True)
        total_bw = st.number_input("Total bandwidth (MHz)", 10.0, 40.0, 20.0, 5.0)
        ch_bw    = st.number_input("Channel BW (MHz)", 1.0, 10.0, 5.0, 1.0)

    with col2:
        reuse  = frequency_reuse_cluster(N, total_bw, ch_bw)
        sector = sectorization_analysis(N, S, total_bw, ch_bw)

        st.subheader("Reuse Metrics")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Cluster size N",       reuse["reuse_factor"])
        r2.metric("D/R ratio",            reuse["D_R_ratio"])
        r3.metric("Channels/cell",        reuse["channels_per_cell"])
        r4.metric("Approx SIR (dB)",      reuse["approx_SIR_dB"])

        st.subheader("Sectorization Gain")
        s1, s2 = st.columns(2)
        s1.metric("Capacity gain", f"×{sector['capacity_gain_x']}")
        s2.info(sector["summary"])

    # Hexagonal cluster diagram
    fig = plot_reuse_pattern(N, filename=f"reuse_N{N}_dashboard.png")
    st.pyplot(fig)
    plt.close(fig)

    st.markdown("""
    **Engineering interpretation:**  
    A reuse factor of N=4 with 3-sector antennas provides a good balance between
    co-channel interference protection (D/R ≈ 3.46) and spectral efficiency.
    Each sector reduces the effective interference by ~3 dB compared to omni cells.
    """)


# =============================================================================
# TAB 3 — Microwave Backhaul Link Budget
# =============================================================================

with tab3:
    st.header("Microwave Backhaul Link Budget")
    st.markdown("Point-to-point microwave link budget for the longest backhaul hop.")

    col1, col2 = st.columns([1, 2])

    with col1:
        freq_ghz = st.select_slider("Frequency (GHz)", [7, 11, 15, 18, 23], value=7)
        dist_km  = st.slider("Distance (km)", 1.0, 30.0, 12.0, 0.5)
        ptx      = st.slider("Tx Power (dBm)", 20, 40, 30, 1)
        gtx      = st.slider("Tx Antenna Gain (dBi)", 25, 45, 34, 1)
        grx      = st.slider("Rx Antenna Gain (dBi)", 25, 45, 34, 1)
        lsys     = st.slider("System Losses (dB)", 1.0, 6.0, 3.0, 0.5)
        fm_req   = st.slider("Required Fade Margin (dB)", 10, 30, 20, 1)
        rx_sens  = st.slider("Rx Sensitivity (dBm)", -100, -70, -85, 1)

    with col2:
        budget = microwave_link_budget(
            freq_ghz         = freq_ghz,
            distance_km      = dist_km,
            tx_power_dbm     = ptx,
            tx_gain_dbi      = gtx,
            rx_gain_dbi      = grx,
            system_losses_db = lsys,
            fade_margin_db   = fm_req,
            rx_threshold_dbm = rx_sens,
        )

        status_colour = "normal" if budget["status"] == "PASS" else "inverse"
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("EIRP (dBm)",           budget["eirp_dbm"])
        b2.metric("FSPL (dB)",             budget["fspl_db"])
        b3.metric("Rx Power (dBm)",        budget["rx_power_dbm"])
        b4.metric("Link Margin (dB)",      budget["link_margin_db"],
                  delta=f"{budget['link_margin_db'] - fm_req:+.1f} vs required")

        if budget["status"] == "PASS":
            st.success(f"✅ Link PASS — margin {budget['link_margin_db']:.1f} dB ≥ {fm_req} dB required")
        else:
            st.error(f"❌ Link FAIL — margin {budget['link_margin_db']:.1f} dB < {fm_req} dB required")

        import pandas as pd
        df = pd.DataFrame([
            {"Parameter": "Frequency",          "Symbol": "f",     "Value": f"{freq_ghz} GHz"},
            {"Parameter": "Distance",            "Symbol": "d",     "Value": f"{dist_km} km"},
            {"Parameter": "Tx Power",            "Symbol": "Ptx",   "Value": f"{ptx} dBm"},
            {"Parameter": "Tx Gain",             "Symbol": "Gtx",   "Value": f"{gtx} dBi"},
            {"Parameter": "EIRP",                "Symbol": "EIRP",  "Value": f"{budget['eirp_dbm']} dBm"},
            {"Parameter": "FSPL",                "Symbol": "FSPL",  "Value": f"{budget['fspl_db']} dB"},
            {"Parameter": "System Losses",       "Symbol": "Lsys",  "Value": f"{lsys} dB"},
            {"Parameter": "Rx Gain",             "Symbol": "Grx",   "Value": f"{grx} dBi"},
            {"Parameter": "Received Power",      "Symbol": "Prx",   "Value": f"{budget['rx_power_dbm']} dBm"},
            {"Parameter": "Rx Threshold",        "Symbol": "Smin",  "Value": f"{rx_sens} dBm"},
            {"Parameter": "Link Margin",         "Symbol": "M",     "Value": f"{budget['link_margin_db']} dB"},
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)


# =============================================================================
# TAB 4 — Improvement Study
# =============================================================================

with tab4:
    st.header("Coverage Improvement Study")
    st.markdown("""
    Compare the baseline 5-site layout against two improvement strategies:
    - **Add a 6th site** at the south-centre coverage gap
    - **Raise antenna height** from 35 m to 50 m
    """)

    if st.button("▶ Run Improvement Study", type="primary"):
        res_file = os.path.join(os.path.dirname(__file__),
                                "results", "wireless_results.json")
        if os.path.exists(res_file):
            with open(res_file) as f:
                data = json.load(f)
            improve = data.get("improvement_study", {})
        else:
            improve = {"baseline": {-85: "N/A", -95: "N/A"},
                       "add_6th_site": {-85: "N/A", -95: "N/A"},
                       "raise_height_50m": {-85: "N/A", -95: "N/A"}}
            st.warning("Run `python run_pipeline.py` first to generate results.")

        import pandas as pd
        rows = []
        for scenario, stats in improve.items():
            label = {
                "baseline":       "Baseline (5 sites, 35 m)",
                "add_6th_site":   "6th Site Added",
                "raise_height_50m": "Antenna Height → 50 m",
            }.get(scenario, scenario)
            rows.append({
                "Scenario":          label,
                "≥ −85 dBm (%)":     stats.get(-85, stats.get("-85", "N/A")),
                "≥ −95 dBm (%)":     stats.get(-95, stats.get("-95", "N/A")),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.markdown("""
        **Tradeoff discussion:**

        | Option | Coverage gain | Cost implication | Capacity effect |
        |---|---|---|---|
        | 6th site | +8–12% at −85 dBm | +1 site CAPEX + backhaul | Requires N=4 reuse extension |
        | Raise height | +5–8% at −85 dBm | Low (tower modification) | No impact on spectrum reuse |

        **Recommendation:** Raising antenna height is the most cost-effective first step.
        The 6th site should be reserved for when traffic forecasting (Student 5) confirms
        that demand justifies the additional capacity.
        """)

        fig_path = os.path.join(os.path.dirname(__file__),
                                "figures", "improvement_study.png")
        if os.path.exists(fig_path):
            st.image(fig_path, caption="Before/After Coverage Comparison")
        else:
            st.info("Run `python run_pipeline.py` to generate the improvement figure.")
