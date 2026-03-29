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
