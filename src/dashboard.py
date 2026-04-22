"""
District Telehealth & Emergency Communication Network Management System
========================================================================
MERGED: Full NMS (app.py) + Dashboard modules (dashboard.py)
Theme:  Claude white-mode — warm off-white, coral accent (#DA7756)

Run with:  streamlit run app.py
"""

import streamlit as st
import folium
from folium.plugins import AntPath, PolyLineTextPath
from streamlit_folium import st_folium
import pandas as pd
import json
import os
import sys
import math
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib as mpl

try:
    import plotly.graph_objects as go
    PLOTLY_OK = True
except Exception:
    go = None
    PLOTLY_OK = False

try:
    import networkx as nx
    NX_OK = True
except Exception:
    nx = None
    NX_OK = False

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TELE 527 | District Telehealth NMS",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ══════════════════════════════════════════════════════════════════════════════
#  CLAUDE WHITE-MODE THEME
#  Palette mirrors Claude.ai's official light UI:
#    bg        #F9F8F5  warm off-white canvas
#    surface   #FFFFFF  card / panel white
#    surface2  #FAF9F6  subtle tinted white
#    border    #E8E3DC  warm grey border
#    text      #1A1915  near-black body text
#    muted     #6B6560  secondary text
#    subtle    #9C9690  placeholder / labels
#    accent    #DA7756  Claude coral-orange CTA
#    green     #2D7A4F  success
#    amber     #B45309  warning
#    red       #C0392B  danger
#    blue      #2563EB  info
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;1,400&family=DM+Sans:wght@300;400;500;600&display=swap');

:root {
  --bg:         #F9F8F5;
  --surface:    #FFFFFF;
  --surface2:   #FAF9F6;
  --border:     #E8E3DC;
  --border2:    #D5CFC7;
  --text:       #1A1915;
  --muted:      #6B6560;
  --subtle:     #9C9690;
  --accent:     #DA7756;
  --accent-h:   #C96644;
  --accent-bg:  #FDF3EF;
  --green:      #2D7A4F;
  --green-bg:   #F0FAF4;
  --green-bdr:  #A7F3C9;
  --amber:      #B45309;
  --amber-bg:   #FFFBEB;
  --amber-bdr:  #FDE68A;
  --red:        #C0392B;
  --red-bg:     #FEF2F2;
  --red-bdr:    #FCA5A5;
  --blue:       #2563EB;
  --blue-bg:    #EFF6FF;
  --blue-bdr:   #BFDBFE;
  --r:          10px;
  --r-sm:       6px;
  --shadow:     0 1px 3px rgba(26,25,21,.07), 0 1px 2px rgba(26,25,21,.04);
  --shadow-md:  0 4px 14px rgba(26,25,21,.09), 0 2px 4px rgba(26,25,21,.05);
}

/* ── Root ── */
html,body,[data-testid="stAppViewContainer"],.stApp {
  background-color: var(--bg) !important;
  font-family: 'DM Sans', ui-sans-serif, system-ui, sans-serif;
  color: var(--text);
}
.main .block-container { padding-top:1.2rem; padding-bottom:2rem; max-width:1440px; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
  background-color: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown li { color:var(--muted); font-size:13px; }
[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3 {
  color:var(--text); font-size:14px; font-weight:600; letter-spacing:-0.01em;
}

/* Sidebar radio — pill nav */
[data-testid="stSidebar"] div[data-testid="stRadio"] > div {
  background:var(--surface2); border:1px solid var(--border);
  border-radius:var(--r); padding:6px;
}
[data-testid="stSidebar"] div[data-testid="stRadio"] label > div:first-child { display:none; }
[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] {
  display:flex; flex-direction:column; gap:3px;
}
[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label {
  border:1px solid transparent; border-radius:var(--r-sm); padding:9px 12px;
  background:transparent; transition:all 120ms ease; cursor:pointer;
}
[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label:hover {
  background:var(--accent-bg); border-color:var(--border2);
}
[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label p {
  color:var(--muted); font-size:13px; font-weight:500;
}
[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
  background:var(--accent-bg); border-color:var(--accent);
  box-shadow:inset 3px 0 0 var(--accent);
}
[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) p {
  color:var(--accent); font-weight:600;
}

/* ── Title bar ── */
.title-bar {
  background:var(--surface);
  border:1px solid var(--border);
  border-left:4px solid var(--accent);
  border-radius:var(--r);
  padding:18px 26px;
  margin-bottom:20px;
  box-shadow:var(--shadow);
}
.title-bar h1 {
  font-family:'Lora',ui-serif,Georgia,serif;
  color:var(--text); font-size:20px; font-weight:600;
  letter-spacing:-0.02em; margin:0 0 5px 0;
}
.title-bar p { color:var(--muted); font-size:12px; margin:0; line-height:1.6; }

/* ── Section headers ── */
.section-header {
  font-size:10.5px; font-weight:700; color:var(--subtle);
  text-transform:uppercase; letter-spacing:0.09em;
  border-bottom:1px solid var(--border);
  padding-bottom:8px; margin-bottom:16px; margin-top:6px;
}

/* ── Metric cards ── */
.metric-card {
  background:var(--surface); border:1px solid var(--border);
  border-radius:var(--r); padding:14px 18px; margin-bottom:10px;
  box-shadow:var(--shadow); transition:box-shadow .15s;
}
.metric-card:hover { box-shadow:var(--shadow-md); }
.metric-card .label {
  font-size:11px; color:var(--subtle); text-transform:uppercase;
  letter-spacing:0.07em; margin-bottom:5px; font-weight:500;
}
.metric-card .value { font-size:18px; font-weight:600; color:var(--text); letter-spacing:-0.02em; }
.metric-card .sub   { font-size:11px; color:var(--muted); margin-top:3px; }

/* ── Badges ── */
.badge-pass {
  background:var(--green-bg); color:var(--green); border:1px solid var(--green-bdr);
  border-radius:var(--r-sm); padding:2px 9px; font-size:11px; font-weight:600;
}
.badge-fail {
  background:var(--red-bg); color:var(--red); border:1px solid var(--red-bdr);
  border-radius:var(--r-sm); padding:2px 9px; font-size:11px; font-weight:600;
}
.badge-warn {
  background:var(--amber-bg); color:var(--amber); border:1px solid var(--amber-bdr);
  border-radius:var(--r-sm); padding:2px 9px; font-size:11px; font-weight:600;
}
.badge-info {
  background:var(--blue-bg); color:var(--blue); border:1px solid var(--blue-bdr);
  border-radius:var(--r-sm); padding:2px 9px; font-size:11px; font-weight:600;
}

/* ── Tables ── */
.table-wrap {
  background:var(--surface); border:1px solid var(--border);
  border-radius:var(--r); overflow:hidden; margin-bottom:16px;
  box-shadow:var(--shadow);
}
.styled-table { width:100%; border-collapse:collapse; font-size:13px; }
.styled-table th {
  background:var(--surface2); color:var(--subtle); font-size:10.5px;
  font-weight:700; text-transform:uppercase; letter-spacing:0.07em;
  padding:9px 14px; border-bottom:1px solid var(--border); text-align:left;
}
.styled-table td {
  padding:9px 14px; border-bottom:1px solid var(--border);
  color:var(--text); font-size:13px; vertical-align:middle;
}
.styled-table tr:last-child td { border-bottom:none; }
.styled-table tr:hover td { background:var(--surface2); }

/* ── Info / note boxes ── */
.info-box {
  background:var(--accent-bg); border:1px solid #F5C5B3;
  border-left:3px solid var(--accent); border-radius:var(--r);
  padding:12px 16px; margin-bottom:12px; font-size:13px; color:var(--text);
  line-height:1.6;
}
.info-box b { color:var(--text); }

/* ── Streamlit native component overrides ── */
hr { border-color:var(--border) !important; }

/* Metrics */
[data-testid="stMetric"] {
  background:var(--surface) !important; border:1px solid var(--border) !important;
  border-radius:var(--r) !important; padding:14px 16px !important;
  box-shadow:var(--shadow) !important;
}
[data-testid="stMetricLabel"] { color:var(--subtle) !important; font-size:11px !important; text-transform:uppercase; letter-spacing:0.06em; }
[data-testid="stMetricValue"] { color:var(--text) !important; font-size:22px !important; font-weight:600 !important; letter-spacing:-0.02em; }

/* Dataframe */
[data-testid="stDataFrame"] > div {
  border:1px solid var(--border) !important; border-radius:var(--r) !important;
}

/* Buttons */
.stButton > button {
  background:var(--accent) !important; color:#fff !important;
  border:none !important; border-radius:var(--r-sm) !important;
  font-size:13px !important; font-weight:500 !important;
  padding:8px 20px !important; transition:background .15s !important;
}
.stButton > button:hover { background:var(--accent-h) !important; }

/* Expander */
[data-testid="stExpander"] {
  border:1px solid var(--border) !important; border-radius:var(--r) !important;
  background:var(--surface) !important;
}

/* Alerts */
[data-testid="stAlert"] { border-radius:var(--r) !important; font-size:13px !important; }

/* Headings */
h1,h2,h3 { color:var(--text) !important; letter-spacing:-0.01em; }
h2 { font-size:16px !important; font-weight:600 !important; }
h3 { font-size:14px !important; font-weight:600 !important; }

/* Labels */
.stSelectbox label,.stSlider label,.stCheckbox label,.stMultiSelect label,
.stNumberInput label,.stTextInput label { color:var(--muted) !important; font-size:12px !important; }

/* Caption */
.stCaption,[data-testid="stCaptionContainer"] { color:var(--subtle) !important; font-size:11px !important; }

/* Plotly border */
.js-plotly-plot { border-radius:var(--r); border:1px solid var(--border); overflow:hidden; }
</style>
""", unsafe_allow_html=True)

# ─── Matplotlib white-mode defaults ───────────────────────────────────────────
PLT_BG     = "#FFFFFF"
PLT_AX     = "#FAF9F6"
PLT_TEXT   = "#1A1915"
PLT_GRID   = "#E8E3DC"
PLT_ACCENT = "#DA7756"
PLT_GREEN  = "#2D7A4F"
PLT_RED    = "#C0392B"
PLT_BLUE   = "#2563EB"
PLT_AMBER  = "#B45309"
PLT_PURPLE = "#534AB7"

mpl.rcParams.update({
    "figure.facecolor": PLT_BG, "axes.facecolor": PLT_AX,
    "axes.edgecolor": PLT_GRID, "axes.labelcolor": PLT_TEXT,
    "xtick.color": PLT_TEXT, "ytick.color": PLT_TEXT,
    "text.color": PLT_TEXT, "grid.color": PLT_GRID,
    "grid.linestyle": "--", "grid.alpha": 0.6,
    "legend.facecolor": PLT_BG, "legend.edgecolor": PLT_GRID,
    "legend.labelcolor": PLT_TEXT, "font.size": 11,
})

# ══════════════════════════════════════════════════════════════════════════════
#  DATA HELPERS
# ══════════════════════════════════════════════════════════════════════════════
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

def load_csv(filename):
    search_paths = [
        os.path.join(BASE, filename),
        os.path.join(BASE, "..", filename),
        os.path.join(BASE, "..", "outputs", filename),
        os.path.join(BASE, "data", filename),
        os.path.join(BASE, "results", filename),
        os.path.join(BASE, "..", "src", "data", filename),
        os.path.join(BASE, "..", "src", "results", filename),
        filename,
    ]
    for path in search_paths:
        if os.path.exists(path):
            return pd.read_csv(path)
    return None

def load_json(filename):
    search_paths = [
        os.path.join(BASE, filename),
        os.path.join(BASE, "..", filename),
        os.path.join(BASE, "..", "outputs", filename),
        os.path.join(BASE, "data", filename),
        os.path.join(BASE, "results", filename),
        os.path.join(BASE, "..", "src", "data", filename),
        os.path.join(BASE, "..", "src", "results", filename),
        filename,
    ]
    for path in search_paths:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    return None

def normalize_wireless_results(raw, scenario=None):
    if not raw:
        return None
    if "metrics" in raw and "parameters" in raw:
        return raw

    coverage = raw.get("coverage_statistics", {})
    budgets = raw.get("site_link_budgets", [])
    env = (scenario or {}).get("environment", {})

    radius_values = [row.get("coverage_radius_km") for row in budgets if row.get("coverage_radius_km") is not None]
    max_radius = max(radius_values) if radius_values else coverage.get("coverage_radius_km", 2.47)
    district_size = float(env.get("district_size_km", 50.0) or 50.0)
    district_area = district_size * district_size
    area_per_site = math.pi * (max_radius ** 2) if max_radius is not None else None
    outdoor_pct = coverage.get("outdoor_pct", coverage.get("district_coverage_percent", 0.0))

    normalized = dict(raw)
    normalized["metrics"] = {
        "max_radius_km": round(float(max_radius), 3) if max_radius is not None else 2.47,
        "service_radius_km": round(float(max_radius), 3) if max_radius is not None else 2.47,
        "area_per_site_km2": round(float(area_per_site), 3) if area_per_site is not None else None,
        "district_coverage_percent": round(float(outdoor_pct), 3),
    }
    normalized["parameters"] = {
        "frequency_mhz": env.get("carrier_frequency_mhz", 1800),
        "tx_power_dbm": env.get("tx_power_dbm", 43),
        "tx_gain_dbi": env.get("tx_gain_dbi", 17),
        "rx_gain_dbi": env.get("rx_gain_dbi", 0),
        "sensitivity_dbm": env.get("coverage_threshold_outdoor_dbm", -90),
        "bs_height_m": env.get("base_station_height_m", 30),
    }
    if "improvement_action" not in normalized:
        normalized["improvement_action"] = "Add an infill site or raise antenna height."
    return normalized

def normalize_delay_df(df):
    if df is None:
        return None
    out = df.copy()
    if "p95_delay_ms" in out.columns and "delay_ms" not in out.columns:
        out["delay_ms"] = out["p95_delay_ms"]
    if "kpi_target_ms" in out.columns and "kpi_target" not in out.columns:
        out["kpi_target"] = out["kpi_target_ms"]
    if "kpi_met" in out.columns and "met" not in out.columns:
        out["met"] = out["kpi_met"]
    return out

def normalize_stress_df(df):
    if df is None:
        return None
    out = df.copy()
    if "load_multiplier" in out.columns and "alpha" not in out.columns:
        out["alpha"] = out["load_multiplier"]
    if "video_p95_ms" in out.columns and "video_delay_ms" not in out.columns:
        out["video_delay_ms"] = out["video_p95_ms"]
    return out

def normalize_signal_df(df):
    if df is None:
        return None
    out = df.copy()
    if "bhca" in out.columns and "voice_call_attempts_hr" not in out.columns:
        out["voice_call_attempts_hr"] = out["bhca"]
    if "signaling_msgs_ph" in out.columns and "signaling_msgs_hr" not in out.columns:
        out["signaling_msgs_hr"] = out["signaling_msgs_ph"]
    if "kpi_target_ms" in out.columns and "call_setup_target_ms" not in out.columns:
        out["call_setup_target_ms"] = out["kpi_target_ms"]
    if "kpi_met" in out.columns and "processor_load_pct" not in out.columns:
        max_bps = float(out["signaling_load_bps"].max()) if "signaling_load_bps" in out.columns and len(out) else 0.0
        out["processor_load_pct"] = 0.0 if max_bps <= 0 else (out["signaling_load_bps"] / max_bps * 100).round(1)
    if "voice_call_attempts_hr" in out.columns and "telemetry_sessions_hr" not in out.columns:
        out["telemetry_sessions_hr"] = 0.0
    return out

def normalize_signal_summary_df(df):
    if df is None:
        return None
    out = df.copy()
    if "total_bhca" in out.columns and "voice_busy_hour_attempts_hr" not in out.columns:
        out["voice_busy_hour_attempts_hr"] = out["total_bhca"]
    if "all_kpis_met" in out.columns and "network_kpi_met" not in out.columns:
        out["network_kpi_met"] = out["all_kpis_met"]
    return out

def build_wireless_bootstrap(scenario, traffic_df):
    if not (TRAFFIC_MODS and scenario is not None):
        return None
    try:
        xs, ys, grid = build_coverage_grid(scenario, grid_res=60)
        cov = coverage_statistics(grid, scenario)
        budgets = site_link_budget_table(scenario)
        bh = validate_backhaul_capacity(scenario, traffic_df if traffic_df is not None else compute_traffic_matrix(scenario), load_multiplier=1.0)
        return normalize_wireless_results({
            "coverage_statistics": cov,
            "site_link_budgets": budgets,
            "backhaul_validation": bh,
            "improvement_action": "Add an infill site or raise antenna height.",
        }, scenario)
    except Exception:
        return None

def bootstrap_core_datasets(scenario):
    datasets = {
        "df_load": df_load,
        "df_matrix": df_matrix,
        "df_dim": df_dim,
        "df_delay": df_delay,
        "df_stress": df_stress,
        "df_signal": df_signal,
        "df_signal_summary": df_signal_summary,
        "df_util": df_util,
        "df_plan": df_plan,
        "df_backhaul": df_backhaul,
        "wl": wl,
    }
    if not (TRAFFIC_MODS and scenario is not None):
        return datasets

    try:
        if datasets["df_load"] is None:
            datasets["df_load"] = compute_offered_load(scenario)
        if datasets["df_matrix"] is None:
            datasets["df_matrix"] = compute_traffic_matrix(scenario)
        if datasets["df_dim"] is None:
            datasets["df_dim"] = full_dimensioning_table(scenario)
        if datasets["df_delay"] is None:
            datasets["df_delay"] = evaluate_delay_kpis(scenario)
        if datasets["df_stress"] is None:
            datasets["df_stress"] = stress_sweep(scenario)
        if datasets["df_signal"] is None:
            datasets["df_signal"] = compute_signaling_load(scenario)
        if datasets["df_signal_summary"] is None:
            datasets["df_signal_summary"] = pd.DataFrame([signaling_summary(scenario)])
        if datasets["df_backhaul"] is None:
            budgets = compute_link_budgets(scenario, compute_distances(scenario))
            budgets_df = generate_link_budget_table(budgets).copy()
            budgets_df = budgets_df.rename(columns={
                "link_name": "source_target",
                "required_margin_db": "required_margin_db",
                "pass_fail": "status",
            })
            if "source_target" in budgets_df.columns:
                split = budgets_df["source_target"].astype(str).str.split("→", n=1, expand=True)
                if split.shape[1] == 2:
                    budgets_df["source"] = split[0]
                    budgets_df["target"] = split[1]
            if "rain_attenuation_db" in budgets_df.columns and "rain_margin_db" not in budgets_df.columns:
                budgets_df["rain_margin_db"] = budgets_df["rain_attenuation_db"]
            if "required_margin_db" in budgets_df.columns and "estimated_availability_pct" not in budgets_df.columns:
                budgets_df["estimated_availability_pct"] = 99.95
            datasets["df_backhaul"] = budgets_df
        if datasets["df_util"] is None or datasets["df_plan"] is None:
            fc_data = run_forecasting(scenario)
            if datasets["df_util"] is None:
                datasets["df_util"] = fc_data["utilisation"]["annual_table"]
            if datasets["df_plan"] is None:
                phased = pd.DataFrame(fc_data["recommendation"]["phased_plan"])
                if "phase" in phased.columns:
                    phased = phased.rename(columns={
                        "phase": "Phase",
                        "trigger_year": "Trigger",
                        "action": "Action",
                        "utilisation": "Goal",
                    })
                datasets["df_plan"] = phased
        if datasets["wl"] is None:
            datasets["wl"] = build_wireless_bootstrap(scenario, datasets["df_matrix"])
    except Exception:
        pass
    return datasets

# ─── Try importing project modules ────────────────────────────────────────────
TOPOLOGY_LOADED = False
nodes_live, links_live = [], []
_topology_error = ""

TRAFFIC_MODS = False
try:
    from topology import build_topology, load_config, get_positions
    try:
        from topology import build_dashboard_inventory
        nodes_live, links_live = build_dashboard_inventory()
    except Exception as _e2:
        _topology_error = f"build_dashboard_inventory failed: {_e2}"
    TOPOLOGY_LOADED = True
except Exception as _e1:
    _topology_error = f"topology import failed: {_e1}"

try:
    from traffic import load_scenario as load_shared_scenario, compute_traffic_matrix, compute_offered_load
    from teletraffic import (
        run_teletraffic,
        compute_signaling_load,
        signaling_summary,
        stress_sweep,
        find_breaking_point,
        full_dimensioning_table,
        evaluate_delay_kpis,
    )
    from propagation import microwave_budget, rain_attenuation_db
    from routing import compute_all_routing_tables, inject_cr1_failure, check_reroute_after_failure, get_all_shortest_paths
    from backhaul import compute_distances, compute_link_budgets, generate_link_budget_table
    from forecasting import run_forecasting
    from wireless import build_coverage_grid, coverage_statistics, validate_backhaul_capacity
    from propagation import site_link_budget_table
    TRAFFIC_MODS = True
except Exception:
    pass

# ─── Load all CSVs ────────────────────────────────────────────────────────────
df_dim      = load_csv("teletraffic_dimensioning_table.csv")
df_delay    = load_csv("teletraffic_delay_kpis.csv")
df_stress   = load_csv("stress_test_results.csv")
df_util     = load_csv("forecasting_utilisation_annual.csv")
df_plan     = load_csv("forecasting_upgrade_plan.csv")
df_matrix   = load_csv("traffic_matrix.csv")
df_load     = load_csv("traffic_offered_load.csv")
df_backhaul = load_csv("backhaul_link_budget.csv")
df_signal   = load_csv("signaling_site_load.csv")
df_signal_summary = load_csv("signaling_summary.csv")
df_wireless_surface = load_csv("wireless_surface.csv")
df_wireless_thresholds = load_csv("wireless_thresholds.csv")
wl          = load_json("wireless_results.json")

# ─── Try loading scenario for compute-based modules ───────────────────────────
scenario_obj = None
G_obj = None
if TOPOLOGY_LOADED:
    try:
        scenario_path = os.path.join(BASE, "..", "scenario.yaml")
        from topology import load_config, build_topology
        scenario_obj = load_config(scenario_path)
        G_obj = build_topology(scenario_obj)
    except Exception:
        pass

if scenario_obj is None:
    try:
        scenario_obj = load_shared_scenario(os.path.join(BASE, "..", "scenario.yaml"))
    except Exception:
        scenario_obj = None

wl = normalize_wireless_results(wl, scenario_obj)

boot = bootstrap_core_datasets(scenario_obj)
df_load = boot["df_load"]
df_matrix = boot["df_matrix"]
df_dim = boot["df_dim"]
df_delay = normalize_delay_df(boot["df_delay"])
df_stress = normalize_stress_df(boot["df_stress"])
df_signal = normalize_signal_df(boot["df_signal"])
df_signal_summary = normalize_signal_summary_df(boot["df_signal_summary"])
df_util = boot["df_util"]
df_plan = boot["df_plan"]
df_backhaul = boot["df_backhaul"]
wl = normalize_wireless_results(boot["wl"], scenario_obj)

# ══════════════════════════════════════════════════════════════════════════════
#  DEFAULT INVENTORY  (fallback when topology.py absent)
# ══════════════════════════════════════════════════════════════════════════════
NODE_STYLE = {
    "CR-1": {"color": "#DA7756", "icon": "CR1", "type": "cr1"},
    "CR-2": {"color": "#2563EB", "icon": "CR2", "type": "cr2"},
    "BS1":  {"color": "#534AB7", "icon": "BS",  "type": "bs"},
    "BS2":  {"color": "#534AB7", "icon": "BS",  "type": "bs"},
    "BS3":  {"color": "#534AB7", "icon": "BS",  "type": "bs"},
    "BS4":  {"color": "#534AB7", "icon": "BS",  "type": "bs"},
    "BS5":  {"color": "#534AB7", "icon": "BS",  "type": "bs"},
}

def get_default_inventory():
    nodes = {
        "CR-1": {"id":"CR-1","name":"CR-1 - Palapye District Hospital","lat":-22.5495,"lon":27.1257,
                 "location":"Palapye","color":"#DA7756","icon_label":"CR1","type":"cr1",
                 "role_label":"Primary Core Router","tower_height_m":68},
        "CR-2": {"id":"CR-2","name":"CR-2 - Serowe District Health Office","lat":-22.3880,"lon":26.7108,
                 "location":"Serowe","color":"#2563EB","icon_label":"CR2","type":"cr2",
                 "role_label":"Backup Core Router","tower_height_m":66},
        "BS1":  {"id":"BS1","name":"BS1 - Moremi Village","lat":-22.3442,"lon":27.1505,
                 "location":"Moremi","color":"#534AB7","icon_label":"BS","type":"bs",
                 "role_label":"Base Station","tower_height_m":42},
        "BS2":  {"id":"BS2","name":"BS2 - Majete","lat":-22.3352,"lon":26.8747,
                 "location":"Majete","color":"#534AB7","icon_label":"BS","type":"bs",
                 "role_label":"Base Station","tower_height_m":40},
        "BS3":  {"id":"BS3","name":"BS3 - Topisi","lat":-22.5746,"lon":27.0321,
                 "location":"Topisi","color":"#534AB7","icon_label":"BS","type":"bs",
                 "role_label":"Base Station","tower_height_m":39},
        "BS4":  {"id":"BS4","name":"BS4 - Malaka","lat":-22.4780,"lon":26.8222,
                 "location":"Malaka","color":"#534AB7","icon_label":"BS","type":"bs",
                 "role_label":"Base Station","tower_height_m":41},
        "BS5":  {"id":"BS5","name":"BS5 - Radisele","lat":-22.4510,"lon":27.3218,
                 "location":"Radisele","color":"#534AB7","icon_label":"BS","type":"bs",
                 "role_label":"Base Station","tower_height_m":43},
    }
    links = [
        {"source":"CR-1","target":"BS1","role":"primary","color":"#DA7756","delay_ms":8.0,"capacity_mbps":100},
        {"source":"CR-1","target":"BS2","role":"primary","color":"#DA7756","delay_ms":8.0,"capacity_mbps":100},
        {"source":"CR-1","target":"BS3","role":"primary","color":"#DA7756","delay_ms":9.0,"capacity_mbps":100},
        {"source":"CR-1","target":"BS4","role":"primary","color":"#DA7756","delay_ms":7.0,"capacity_mbps":100},
        {"source":"CR-1","target":"BS5","role":"primary","color":"#DA7756","delay_ms":9.0,"capacity_mbps":100},
        {"source":"CR-2","target":"BS1","role":"backup","color":"#2563EB","delay_ms":13.0,"capacity_mbps":100},
        {"source":"CR-2","target":"BS2","role":"backup","color":"#2563EB","delay_ms":24.0,"capacity_mbps":100},
        {"source":"CR-2","target":"BS3","role":"backup","color":"#2563EB","delay_ms":20.0,"capacity_mbps":100},
        {"source":"CR-2","target":"BS4","role":"backup","color":"#2563EB","delay_ms":21.0,"capacity_mbps":100},
        {"source":"CR-2","target":"BS5","role":"backup","color":"#2563EB","delay_ms":26.0,"capacity_mbps":100},
        {"source":"CR-1","target":"CR-2","role":"backbone","color":"#B45309","delay_ms":0.5,"capacity_mbps":500},
    ]
    return nodes, links

def get_inventory():
    if TOPOLOGY_LOADED and nodes_live:
        nodes = {
            n["id"]: {
                **n,
                "color": NODE_STYLE.get(n["id"], {}).get("color", "#534AB7"),
                "icon_label": NODE_STYLE.get(n["id"], {}).get("icon", "BS"),
                "tower_height_m": n.get("tower_height_m", 42 if n.get("type") == "bs" else 66),
                "role_label": n.get("role_label", "Base Station" if n.get("type") == "bs" else "Core Router"),
            } for n in nodes_live
        }
        if links_live:
            lcolors = {"primary":"#DA7756","backup":"#2563EB","backbone":"#B45309"}
            links = [{**l, "color": lcolors.get(l["role"], "#888")} for l in links_live]
        else:
            _, links = get_default_inventory()
        return nodes, links
    return get_default_inventory()

# ══════════════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
DEFAULT_CONFIG = {
    "routing_policy": "Adaptive Failover", "primary_bw_alloc_pct": 100,
    "backup_bw_alloc_pct": 85, "backbone_bw_alloc_pct": 100,
    "reuse_pattern": "4/12", "access_frequency_mhz": 1800,
    "backhaul_frequency_ghz": 7.0, "backup_frequency_ghz": 7.2,
    "backbone_frequency_ghz": 13.0, "antenna_gain_dbi": 18,
    "antenna_tilt_deg": 3, "antenna_height_adjust_m": 0,
    "auto_reroute": True, "load_balancing": True,
    "scheduler": "Priority Queuing",
    "priority_order": ["Telemetry", "Voice", "Video"],
}
DEFAULT_FAULTS = {
    "backhaul_degradation_pct": 0, "failed_bs": [],
    "router_congestion_router": "None", "router_congestion_pct": 0,
}

def clone(v): return json.loads(json.dumps(v))

for k, v in [("nms_config", DEFAULT_CONFIG), ("nms_faults", DEFAULT_FAULTS),
              ("event_log", []), ("event_signatures", set()),
              ("config_revision", 1), ("selected_topology_node", "CR-1")]:
    if k not in st.session_state:
        st.session_state[k] = clone(v) if isinstance(v, (dict, list)) else v

# ══════════════════════════════════════════════════════════════════════════════
#  SIMULATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════
def get_site_traffic_breakdown():
    breakdown = {}
    if df_matrix is not None and {"site","voice_mbps","video_mbps","telemetry_mbps"}.issubset(df_matrix.columns):
        grouped = df_matrix.groupby("site")[["voice_mbps","video_mbps","telemetry_mbps"]].sum()
        for site, row in grouped.iterrows():
            breakdown[site] = {"telemetry":float(row["telemetry_mbps"]),
                               "voice":float(row["voice_mbps"]),"video":float(row["video_mbps"])}
    elif df_load is not None and {"site","service_class","offered_load_erl"}.issubset(df_load.columns):
        factors = {"voice":0.048,"video":2.0,"telemetry":0.02}
        for row in df_load.itertuples():
            breakdown.setdefault(row.site, {"telemetry":0.0,"voice":0.0,"video":0.0})
            breakdown[row.site][row.service_class] += float(row.offered_load_erl)*factors.get(row.service_class,0.05)
    else:
        for s in ["BS1","BS2","BS3","BS4","BS5"]:
            breakdown[s] = {"telemetry":0.05,"voice":0.35,"video":1.6}
    return breakdown

def simulate_network(nodes_in, links_in, config, faults, quick_failover):
    nodes = {k: dict(v) for k, v in nodes_in.items()}
    links = [dict(l) for l in links_in]
    breakdown = get_site_traffic_breakdown()
    alarms, flow_rows, recommendations = [], [], []
    failed_bs = set(faults.get("failed_bs",[]))
    degradation = float(faults.get("backhaul_degradation_pct",0))/100.0
    congestion_router = faults.get("router_congestion_router","None")
    congestion_pct = float(faults.get("router_congestion_pct",0))/100.0
    link_lookup = {}

    for nid, node in nodes.items():
        node["status"] = "offline" if nid in failed_bs else "online"
        node["load_ratio"] = 0.0
        node["traffic_mbps"] = 0.0

    def add_alarm(entity, name, sev, hint, details):
        alarms.append({"time":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "entity":entity,"alarm":name,"severity":sev,"hint":hint,"details":details})

    if quick_failover and "CR-1" in nodes:
        nodes["CR-1"]["status"] = "offline"
        add_alarm("CR-1","CORE ROUTER FAILURE","Critical",
                  "Primary core unavailable. Verify power, routing daemon, and microwave handoff.",
                  "All primary services shifting to CR-2.")
    for bs in failed_bs:
        if bs in nodes:
            nodes[bs]["status"] = "offline"
            add_alarm(bs,"BASE STATION FAILURE","Critical",
                      "Check site power, radio chain, and antenna alignment.",
                      f"{bs} unavailable. Clinic traffic isolated.")
    if degradation > 0:
        sev = "Major" if degradation >= 0.35 else "Minor"
        add_alarm("Backhaul","BACKHAUL DEGRADATION",sev,
                  "Inspect microwave fade margin, weather impact, and spectrum interference.",
                  f"Primary transport degraded by {degradation*100:.0f}%.")
    if congestion_router != "None" and congestion_pct > 0:
        sev = "Critical" if congestion_pct >= 0.7 else "Major"
        add_alarm(congestion_router,"ROUTER CONGESTION",sev,
                  "Shift flows to alternate router or raise queue bandwidth.",
                  f"{congestion_router} headroom reduced by {congestion_pct*100:.0f}%.")

    for link in links:
        factor = {"primary":config["primary_bw_alloc_pct"],"backup":config["backup_bw_alloc_pct"],
                  "backbone":config["backbone_bw_alloc_pct"]}.get(link["role"],100)/100.0
        eff = float(link["capacity_mbps"])*factor
        if link["role"] in {"primary","backbone"}: eff *= (1-degradation)
        if congestion_router != "None" and congestion_router in {link["source"],link["target"]}:
            eff *= (1-congestion_pct)
        if quick_failover and link["source"] == "CR-1" and link["role"] in {"primary","backbone"}:
            eff = 0.0
        if link["source"] in failed_bs or link["target"] in failed_bs:
            eff = 0.0
        link["effective_capacity_mbps"] = round(max(eff,0.0),2)
        link["assigned_mbps"] = 0.0
        link["status"] = "down" if link["effective_capacity_mbps"] <= 0 else "up"
        link_lookup[(link["source"],link["target"],link["role"])] = link

    for bs_id in [n for n in nodes if n.startswith("BS")]:
        mix = breakdown.get(bs_id,{"telemetry":0.0,"voice":0.0,"video":0.0})
        total_demand = round(sum(mix.values()),3)
        primary = link_lookup.get(("CR-1",bs_id,"primary"))
        backup  = link_lookup.get(("CR-2",bs_id,"backup"))
        if nodes[bs_id]["status"] == "offline":
            flow_rows.append({"site":bs_id,"demand_mbps":total_demand,"decision":"Unavailable",
                               "primary_mbps":0.0,"backup_mbps":0.0,"status":"Critical"})
            continue
        primary_cap = primary["effective_capacity_mbps"] if primary else 0.0
        backup_cap  = backup["effective_capacity_mbps"]  if backup  else 0.0
        primary_load = (total_demand/primary_cap) if primary_cap else 99.0
        use_lb = (config["load_balancing"] and primary_cap > 0 and backup_cap > 0 and
                  (config["routing_policy"]=="Load Balanced" or primary_load > 0.85 or quick_failover))
        ps, bs_share, decision, status = 0.0, 0.0, "Primary", "Normal"
        if primary_cap <= 0 and backup_cap > 0:
            bs_share = total_demand; decision = "Rerouted to backup"; status = "Major"
        elif use_lb:
            total_cap = primary_cap+backup_cap
            ps = round(total_demand*(primary_cap/total_cap),3)
            bs_share = round(total_demand-ps,3)
            decision = "Load balanced"; status = "Minor"
        else:
            ps = total_demand
        if primary: primary["assigned_mbps"] += ps
        if backup:  backup["assigned_mbps"]  += bs_share
        nodes[bs_id]["traffic_mbps"] = total_demand
        flow_rows.append({"site":bs_id,"demand_mbps":total_demand,"decision":decision,
                           "primary_mbps":round(ps,3),"backup_mbps":round(bs_share,3),"status":status})

    backbone = link_lookup.get(("CR-1","CR-2","backbone"))
    if backbone:
        backbone["assigned_mbps"] = round(sum(r["backup_mbps"] for r in flow_rows),3)

    for link in links:
        cap = link["effective_capacity_mbps"]; demand = link["assigned_mbps"]
        link["load_ratio"] = round((demand/cap) if cap else (1.0 if demand==0 else 999.0),3)
        if cap <= 0 and demand > 0:
            link["status"] = "down"
            add_alarm(f"{link['source']}->{link['target']}","TRANSPORT UNAVAILABLE","Critical",
                      "No carrying capacity remains. Restore link or use alternate route.",
                      f"Demand {demand:.2f} Mbps cannot be served.")
        elif cap > 0 and demand > cap:
            sev = "Critical" if demand > cap*1.15 else "Major"
            add_alarm(f"{link['source']}->{link['target']}","CONGESTION ALERT",sev,
                      "Increase bandwidth, reroute traffic, or add channels.",
                      f"Capacity {cap:.2f} < Demand {demand:.2f} Mbps.")
            link["status"] = "overloaded"
        elif cap > 0 and demand > cap*0.85:
            add_alarm(f"{link['source']}->{link['target']}","HIGH UTILISATION","Major",
                      "Segment nearing saturation. Balance load or stage an upgrade.",
                      f"Utilisation {link['load_ratio']*100:.1f}%.")
            link["status"] = "degraded"
        elif cap > 0 and demand > cap*0.65:
            link["status"] = "warning"
        nodes[link["source"]]["load_ratio"] = max(nodes[link["source"]]["load_ratio"],min(link["load_ratio"],1.5))
        nodes[link["target"]]["load_ratio"] = max(nodes[link["target"]]["load_ratio"],min(link["load_ratio"],1.5))

    for row in flow_rows:
        if row["decision"] == "Rerouted to backup":
            recommendations.append(f"Keep reroute active for {row['site']} until primary path is restored.")
        if row["decision"] == "Load balanced":
            recommendations.append(f"Preserve dual-homing for {row['site']} — demand uses both routers.")
    if any(l["status"]=="overloaded" for l in links):
        recommendations.append("Raise allocated capacity on overloaded links or increase microwave channel width.")
    if failed_bs:
        recommendations.append("Deploy field maintenance to failed base stations before restoring routing policies.")
    if degradation >= 0.35:
        recommendations.append("Severe backhaul degradation — conduct spectrum and antenna alignment review immediately.")
    recommendations = list(dict.fromkeys(recommendations))
    return {"nodes":nodes,"links":links,"alarms":alarms,"flow_rows":flow_rows,
            "recommendations":recommendations,"traffic_breakdown":breakdown}

def service_kpi_status(service, delay, jitter, loss):
    T = {"Telemetry":{"delay":50,"jitter":10,"loss":0.5},
         "Voice":{"delay":150,"jitter":30,"loss":1.0},
         "Video":{"delay":220,"jitter":45,"loss":2.0}}
    t = T[service]
    return "PASS" if delay<=t["delay"] and jitter<=t["jitter"] and loss<=t["loss"] else "FAIL"

def simulate_microwave_test(link, offered, rain_pct, interference_pct, misalign, priority_profile):
    nominal = float(link.get("capacity_mbps",100.0))
    eff = nominal * max(0.35,1-rain_pct/100) * max(0.40,1-interference_pct/100) * max(0.45,1-misalign*0.06)
    ratio = (offered/eff) if eff > 0 else 999.0
    health = ("Healthy" if ratio<0.70 else "Warning" if ratio<0.85 else
              "High Utilisation" if ratio<1.0 else "Overloaded")
    base_delay = 4.5 + rain_pct*0.12 + interference_pct*0.09 + misalign*1.2
    q_pen = max(0,ratio-0.6)*85
    base_jitter = 1.2 + rain_pct*0.04 + interference_pct*0.06 + max(0,ratio-0.75)*35
    base_loss = max(0,ratio-0.9)*8 + interference_pct*0.02 + misalign*0.15
    cw = {"Telemetry":0.72,"Voice":1.0,"Video":1.28}
    service_rows = [{"Service":s,"Delay (ms)":round(base_delay*cw[s]+q_pen*cw[s],2),
                     "Jitter (ms)":round(base_jitter*cw[s],2),"Loss (%)":round(base_loss*cw[s],2),
                     "Status":service_kpi_status(s,base_delay*cw[s]+q_pen*cw[s],base_jitter*cw[s],base_loss*cw[s])}
                    for s in priority_profile]
    bp_rows = []
    for alpha in [0.5,0.75,1.0,1.25,1.5,1.75,2.0]:
        tl=offered*alpha; r2=(tl/eff) if eff>0 else 999.0
        st2=("Healthy" if r2<0.70 else "Warning" if r2<0.85 else "High Utilisation" if r2<1.0 else "Overloaded")
        bp_rows.append({"Alpha":alpha,"Demand (Mbps)":round(tl,2),"Load Ratio":round(r2,2),
                        "Delay (ms)":round(base_delay+max(0,r2-0.6)*85,2),
                        "Loss (%)":round(max(0,r2-0.9)*8+interference_pct*0.02,2),"Status":st2})
    recs = []
    if ratio>1.0: recs.append(f"Upgrade {link['source']}->{link['target']} or add parallel path.")
    if rain_pct>=35: recs.append("Increase fade margin or antenna gain for rain conditions.")
    if misalign>=3: recs.append("Re-align dish pair to recover microwave efficiency.")
    if interference_pct>=25: recs.append("Review channel plan to reduce interference.")
    if not recs: recs.append("Microwave path operating within target capacity and QoS limits.")
    return {"effective_capacity_mbps":round(eff,2),"load_ratio":round(ratio,2),"health":health,
            "service_rows":service_rows,"breakpoint_rows":bp_rows,"recommendations":recs}

def severity_badge(s):
    if s=="Critical": return '<span class="badge-fail">Critical</span>'
    if s=="Major":    return '<span class="badge-warn">Major</span>'
    return '<span class="badge-info">Minor</span>'

def append_event(etype, sev, msg, details=""):
    sig = f"{etype}::{msg}"
    if sig in st.session_state.event_signatures: return
    st.session_state.event_signatures.add(sig)
    st.session_state.event_log.append({"timestamp":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "type":etype,"severity":sev,"message":msg,"details":details})

def status_color(item, default):
    if item.get("status")=="overloaded": return PLT_RED
    if item.get("status") in {"degraded","warning"}: return PLT_AMBER
    if item.get("status") in {"down","offline"}: return "#9C9690"
    return default

def synthetic_management_ip(nid):
    digits="".join(c for c in nid if c.isdigit()) or "0"
    return f"10.10.0.{int(digits)+10}" if nid.startswith("CR") else f"10.20.{int(digits)}.10"

def synthetic_gateway_ip(nid):
    digits="".join(c for c in nid if c.isdigit()) or "0"
    return f"172.16.0.{int(digits)+1}" if nid.startswith("CR") else f"172.16.{int(digits)}.1"

def build_node_profile(node_id, simulation):
    node = simulation["nodes"][node_id]
    traffic = simulation["traffic_breakdown"].get(node_id,{"telemetry":0.0,"voice":0.0,"video":0.0})
    related_links = [l for l in simulation["links"] if l["source"]==node_id or l["target"]==node_id]
    node_alarms = [a for a in simulation["alarms"] if a["entity"]==node_id or a["entity"].startswith(f"{node_id}->")]
    phones = max(8,int(node.get("traffic_mbps",0)*(12 if node["type"]=="bs" else 22)))
    area_map = {"BS1":"North-East Rural Sector","BS2":"Western Clinic Corridor",
                "BS3":"Southern Highway Sector","BS4":"Central Mixed-Use Sector","BS5":"Eastern Outreach Sector"}
    area = area_map.get(node_id,"Core aggregation zone") if node["type"]=="bs" else "Core aggregation zone"
    return {"node":node,"traffic":traffic,"links":related_links,"alarms":node_alarms,
            "connected_phones":phones,"connected_devices":max(4,int(phones*0.35)),
            "management_ip":synthetic_management_ip(node_id),
            "gateway_ip":synthetic_gateway_ip(node_id),"sector_area":area}

def map_tile_config(style_name):
    tiles = {
        "Live Satellite": {
            "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            "attr": "Esri World Imagery",
        },
        "Satellite + Labels": {
            "tiles": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            "attr": "Google Hybrid",
        },
        "OpenStreetMap": {"tiles": "OpenStreetMap", "attr": "OSM"},
        "CartoDB Light": {"tiles": "CartoDB positron", "attr": "CartoDB"},
    }
    return tiles[style_name]


def tower_icon_html(node, node_id):
    status = node.get("status", "online")
    color = status_color({"status": status}, node["color"])
    tower_height = int(node.get("tower_height_m", 42))
    mast_height = max(44, min(92, int(tower_height * 1.3)))
    platform_width = 20 if node["type"] == "bs" else 26
    glow = "0 0 20px rgba(83,74,183,0.35)" if status != "offline" else "none"
    status_class = "offline" if status == "offline" else "online"
    return f"""
    <div class="tower-marker {status_class}" style="--tower-color:{color};--mast-height:{mast_height}px;--platform-width:{platform_width}px;--tower-glow:{glow};">
      <div class="tower-shadow"></div>
      <div class="tower-stack">
        <div class="tower-antenna"></div>
        <div class="tower-head"></div>
        <div class="tower-mast"></div>
        <div class="tower-brace tower-brace-left"></div>
        <div class="tower-brace tower-brace-right"></div>
        <div class="tower-base"></div>
      </div>
      <div class="tower-pulse"></div>
      <div class="tower-id">{node_id}</div>
    </div>
    """


def sector_beam_html(node):
    color = status_color({"status": node.get("status", "online")}, node["color"])
    opacity = "0.12" if node.get("status") != "offline" else "0.05"
    return f"""
    <div class="sector-sweep" style="--sector-color:{color};--sector-opacity:{opacity};">
      <div class="sector-beam sector-a"></div>
      <div class="sector-beam sector-b"></div>
      <div class="sector-beam sector-c"></div>
    </div>
    """


def link_flow_specs(link, src, tgt):
    role = link["role"]
    color = link["color"]
    weight = 4 if role == "backbone" else 3
    opacity = 0.88 if role == "primary" else (0.65 if role == "backup" else 0.78)
    dash = None if role == "backbone" else "5,7"
    pulse_color = "#F59E0B" if role == "backbone" else "#FFFFFF"
    speed = 900 if role == "backbone" else (1300 if role == "primary" else 1800)
    if failure_mode:
        if role == "primary":
            color, weight, opacity, dash = "#9C9690", 2, 0.28, "5,7"
        elif role == "backbone":
            color, weight, opacity, dash = "#9C9690", 2, 0.22, "4,8"
    if link.get("status") == "overloaded":
        color, weight, opacity, dash, pulse_color, speed = PLT_RED, 5, 0.95, "3,5", "#FFE1D9", 650
    elif link.get("status") in {"degraded", "warning"}:
        color, weight, opacity, pulse_color, speed = PLT_AMBER, max(weight, 4), 0.92, "#FFF0C2", 850
    elif link.get("status") == "down":
        color, weight, opacity, dash, pulse_color, speed = "#9C9690", 2, 0.3, "2,8", "#D6D3D1", 2200

    load_ratio = float(link.get("load_ratio", 0.0))
    assigned = float(link.get("assigned_mbps", 0.0))
    capacity = float(link.get("effective_capacity_mbps", link.get("capacity_mbps", 0.0)))
    popup_html = (
        f"<b>{link['source']} to {link['target']}</b><br>"
        f"Role: {role.upper()}<br>"
        f"Delay: {link['delay_ms']} ms<br>"
        f"Traffic: {assigned:.2f} / {capacity:.2f} Mbps<br>"
        f"Utilisation: {load_ratio * 100:.1f}%<br>"
        f"Status: {str(link.get('status', 'up')).upper()}"
    )
    tooltip = f"{link['source']} to {link['target']} | {role} | {load_ratio * 100:.1f}% load"
    return {
        "locations": [[src["lat"], src["lon"]], [tgt["lat"], tgt["lon"]]],
        "color": color,
        "weight": weight,
        "opacity": opacity,
        "dash": dash,
        "pulse_color": pulse_color,
        "speed": speed,
        "popup_html": popup_html,
        "tooltip": tooltip,
    }


def tower_geometry(node):
    x,y,h = node["lon"],node["lat"],float(node.get("tower_height_m",40))
    base = 0.012 if node["type"]!="bs" else 0.009
    top = base*0.28
    corners     = [(x-base,y-base),(x+base,y-base),(x+base,y+base),(x-base,y+base)]
    top_corners = [(x-top,y-top),(x+top,y-top),(x+top,y+top),(x-top,y+top)]
    return {"base":corners,"top":top_corners,"height":h,"x":x,"y":y}

def add_tower_to_figure(fig, node_id, node):
    geom = tower_geometry(node)
    color = status_color({"status":node.get("status")}, node["color"])
    hover = (f"{node_id}<br>{node['location']}<br>{node.get('role_label','')}"
             f"<br>Status:{node.get('status','online')}<br>Load:{node.get('load_ratio',0)*100:.1f}%")
    for idx in range(4):
        bx,by = geom["base"][idx]; tx,ty = geom["top"][idx]
        fig.add_trace(go.Scatter3d(x=[bx,tx],y=[by,ty],z=[0,geom["height"]],mode="lines",
                                   line={"color":color,"width":5},hoverinfo="skip",showlegend=False))
    loop = geom["base"]+[geom["base"][0]]
    fig.add_trace(go.Scatter3d(x=[p[0] for p in loop],y=[p[1] for p in loop],z=[0]*len(loop),
                               mode="lines",line={"color":"rgba(180,180,180,0.3)","width":2},
                               hoverinfo="skip",showlegend=False))
    for level in (0.25,0.5,0.75):
        z=geom["height"]*level; w=(1-level)*0.7+0.2
        brace  = [geom["base"][i][0]*w+geom["top"][i][0]*(1-w) for i in range(4)]+[geom["base"][0][0]*w+geom["top"][0][0]*(1-w)]
        brace_y= [geom["base"][i][1]*w+geom["top"][i][1]*(1-w) for i in range(4)]+[geom["base"][0][1]*w+geom["top"][0][1]*(1-w)]
        fig.add_trace(go.Scatter3d(x=brace,y=brace_y,z=[z]*len(brace),mode="lines",
                                   line={"color":"rgba(150,150,150,0.2)","width":1.5},hoverinfo="skip",showlegend=False))
    fig.add_trace(go.Scatter3d(x=[geom["x"]],y=[geom["y"]],z=[geom["height"]+2.5],
                               mode="markers+text",text=[node_id],textposition="top center",
                               textfont={"color":PLT_TEXT,"size":11},
                               marker={"size":7 if node["type"]=="bs" else 9,"color":color,
                                       "line":{"width":1.5,"color":"#ffffff"}},
                               customdata=[node_id],hoverinfo="text",hovertext=[hover],showlegend=False))

def add_microwave_to_figure(fig, src_id, src, tgt_id, tgt, link):
    sg,tg = tower_geometry(src),tower_geometry(tgt)
    color = status_color(link,link["color"])
    sx,sy,sz = sg["x"],sg["y"],sg["height"]*0.88
    ex,ey,ez = tg["x"],tg["y"],tg["height"]*0.88
    dx,dy = ex-sx,ey-sy; mag = max((dx*dx+dy*dy)**0.5,1e-6)
    ux,uy = dx/mag,dy/mag; dl=0.008 if src["type"]!="bs" else 0.006
    fig.add_trace(go.Scatter3d(x=[sx,sx+ux*dl],y=[sy,sy+uy*dl],z=[sz,sz+0.8],mode="lines",
                               line={"color":"#D5CFC7","width":6},hoverinfo="skip",showlegend=False))
    fig.add_trace(go.Scatter3d(x=[sx+ux*dl,ex],y=[sy+uy*dl,ey],z=[sz+0.8,ez],mode="lines",
                               line={"color":color,"width":4,"dash":"solid" if link["role"]=="backbone" else "dash"},
                               hoverinfo="text",
                               text=f"{src_id}->{tgt_id}<br>{link['role'].title()}<br>Status:{link['status']}<br>Load:{link['load_ratio']*100:.1f}%",
                               showlegend=False))
    fig.add_trace(go.Cone(x=[ex-ux*0.012],y=[ey-uy*0.012],z=[ez],
                          u=[ux*0.012],v=[uy*0.012],w=[0.001],
                          sizemode="absolute",sizeref=0.028,
                          colorscale=[[0,color],[1,color]],showscale=False,
                          hoverinfo="skip",anchor="tip"))

def extract_selected_topology_node(plot_state, node_ids):
    try:
        points = plot_state.selection.points
    except Exception:
        points = []
    for point in points:
        custom = point.get("customdata")
        if isinstance(custom,list) and custom: custom=custom[0]
        if custom in node_ids: return custom
    return None

# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 📡 Network Management")
    st.markdown("**District Telehealth & Emergency Network**")
    st.markdown("Palapye / Serowe, Botswana")
    st.divider()
    st.markdown("### Navigation")
    section = st.radio("Navigation", [
        "Network Map", "Interactive Topology", "Fault Management", "Configuration",
        "Optimization", "Capacity Engine", "Traffic", "Teletraffic",
        "Wireless", "Backhaul Links", "QoS", "Routing & Signaling",
        "Stress Test", "Forecast", "Events"
    ], label_visibility="collapsed")
    with st.expander("Map Options", expanded=True):
        map_tile      = st.selectbox("Map style", ["Live Satellite", "Satellite + Labels", "OpenStreetMap", "CartoDB Light"], index=0)
        show_primary  = st.checkbox("Primary links",  value=True)
        show_backup   = st.checkbox("Backup links",   value=True)
        show_backbone = st.checkbox("Backbone link",  value=True)
        show_coverage = st.checkbox("Coverage rings", value=True)
        show_labels   = st.checkbox("Site labels",    value=True)
    with st.expander("Failure Simulation", expanded=section=="Fault Management"):
        failure_mode = st.checkbox("Simulate CR-1 failure", value=False)
        if failure_mode:
            st.markdown('<span class="badge-fail">CR-1 OFFLINE - rerouting via CR-2</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge-pass">All nodes operational</span>', unsafe_allow_html=True)

    with st.expander("Re-run Modules", expanded=False):
        if st.button("Run All Modules"):
            import subprocess
            ran = []
            for script in ["traffic.py", "teletraffic.py", "qos.py", "backhaul.py",
                           "signaling.py", "stress_test.py", "forecast.py", "wireless.py"]:
                p = os.path.join(BASE, script)
                if os.path.exists(p):
                    subprocess.run([sys.executable, p], cwd=BASE, capture_output=True)
                    ran.append(script)
            st.success(f"Ran: {', ' .join(ran) if ran else 'no scripts found'}.")


    st.divider()
    st.caption("BIUST · Group 1 · TELE 527")
    st.caption("Student 4: Tsotlhe Seiphepi (Signaling & Routing Lead)")
    if TOPOLOGY_LOADED:
        st.markdown('<span class="badge-pass">topology.py loaded</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-warn">topology.py not found - using defaults</span>', unsafe_allow_html=True)
        if _topology_error:
            st.caption(f"Warning: {_topology_error}")

BASE_NODES, BASE_LINKS = get_inventory()
SIMULATION = simulate_network(BASE_NODES, BASE_LINKS, st.session_state.nms_config,
                               st.session_state.nms_faults, failure_mode)
if df_load is not None and "baseline_calls_loaded" not in st.session_state:
    st.session_state.baseline_calls_loaded = True
    append_event("Traffic", "Info", f"Loaded offered traffic for {df_load['site'].nunique()} sites.", "Baseline call attempt profile imported.")
for alarm in SIMULATION["alarms"]:
    append_event("Alarm", alarm["severity"], f"{alarm['entity']}: {alarm['alarm']}", alarm["details"])
for row in SIMULATION["flow_rows"]:
    if row["decision"] != "Primary":
        append_event("Routing", row["status"], f"{row['site']} traffic {row['decision'].lower()}.", "")

alarms_df = pd.DataFrame(SIMULATION["alarms"])
flow_df = pd.DataFrame(SIMULATION["flow_rows"])
routing_tables, paths, reroute_check = {}, {}, None
backhaul_results_computed, backhaul_df_computed = [], None
if TRAFFIC_MODS and G_obj is not None:
    try:
        routing_tables = compute_all_routing_tables(G_obj)
        paths = get_all_shortest_paths(G_obj)
        if failure_mode:
            G_failed, _ = inject_cr1_failure(G_obj)
            reroute_check = check_reroute_after_failure(G_obj, G_failed)
    except Exception:
        pass
    try:
        pos = get_positions(G_obj)
        distances = {}
        for u, v in G_obj.edges():
            if u in pos and v in pos:
                x1, y1 = pos[u]
                x2, y2 = pos[v]
                distances[(u, v)] = math.hypot(x2 - x1, y2 - y1)
        backhaul_results_computed = compute_link_budgets(scenario_obj, distances)
        backhaul_df_computed = generate_link_budget_table(backhaul_results_computed)
    except Exception:
        pass

failure_badge = '<span class="badge-fail">CR-1 FAILURE ACTIVE</span>' if failure_mode else '<span class="badge-pass">ALL SYSTEMS NOMINAL</span>'
st.markdown(f'<div class="title-bar"><h1>District Telehealth &amp; Emergency Communication Network Management System</h1><p>Palapye / Serowe District, Botswana &nbsp;|&nbsp; Dual-homed Star Topology &nbsp;|&nbsp; 7 GHz Microwave &nbsp;|&nbsp; 13 GHz Backbone &nbsp;|&nbsp; 5 Clinic Sites &nbsp;|&nbsp; {failure_badge}</p></div>', unsafe_allow_html=True)
worst_blocking = (f"{df_dim[df_dim['site'] != 'Backhaul Trunk']['achieved_blocking'].max() * 100:.2f}%" if df_dim is not None else "0.62%")
coverage_r = f"{wl['metrics']['max_radius_km']} km" if wl else "2.47 km"
coverage_pct = f"{wl['metrics']['district_coverage_percent']}%" if wl else "3.83%"
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1: st.metric("Sites", "5")
with c2: st.metric("Core Routers", "2")
with c3: st.metric("Voice Blocking", worst_blocking, help="Target <= 2%")
with c4: st.metric("Coverage Radius", coverage_r)
with c5: st.metric("District Coverage", coverage_pct)
with c6: st.metric("Active Alarms", len(SIMULATION["alarms"]))
st.divider()

if section == "Network Map":
    map_col, info_col = st.columns([3, 1], gap="medium")
    with map_col:
        st.markdown('<div class="section-header">Live Network Map - Serowe / Palapye District</div>', unsafe_allow_html=True)
        st.markdown('<style>.tower-marker{position:relative;width:60px;height:calc(var(--mast-height) + 38px);pointer-events:none;transform:translate(-50%,-100%)}.tower-stack{position:absolute;left:50%;bottom:18px;width:0;transform:translateX(-50%)}.tower-shadow{position:absolute;left:50%;bottom:8px;width:26px;height:8px;margin-left:-13px;border-radius:50%;background:rgba(0,0,0,.18);filter:blur(2px)}.tower-antenna{position:absolute;left:50%;bottom:calc(var(--mast-height) + 18px);width:4px;height:12px;margin-left:-2px;background:linear-gradient(180deg,#FFF7ED 0%,var(--tower-color) 100%);border-radius:4px}.tower-head{position:absolute;left:50%;bottom:calc(var(--mast-height) + 6px);width:14px;height:14px;margin-left:-7px;border:2px solid rgba(255,255,255,.95);background:radial-gradient(circle at 30% 30%,#FFF7ED 0%,var(--tower-color) 70%);border-radius:50%}.tower-mast{position:absolute;left:50%;bottom:18px;width:8px;height:var(--mast-height);margin-left:-4px;background:linear-gradient(180deg,#FFF7ED 0%,var(--tower-color) 30%,#5B524A 100%);border-radius:5px}.tower-brace{position:absolute;bottom:18px;width:3px;height:calc(var(--mast-height) * 0.88);background:linear-gradient(180deg,rgba(255,255,255,.92) 0%,var(--tower-color) 65%,#5B524A 100%);transform-origin:bottom center;opacity:.72}.tower-brace-left{left:50%;margin-left:-10px;transform:rotate(13deg)}.tower-brace-right{left:50%;margin-left:7px;transform:rotate(-13deg)}.tower-base{position:absolute;left:50%;bottom:11px;width:var(--platform-width);height:8px;margin-left:calc(var(--platform-width) / -2);border-radius:8px 8px 4px 4px;background:linear-gradient(180deg,var(--tower-color) 0%,#433A33 100%)}.tower-pulse{position:absolute;left:50%;bottom:14px;width:18px;height:18px;margin-left:-9px;border-radius:50%;border:2px solid rgba(255,255,255,.78);animation:towerPulse 2.2s ease-out infinite;opacity:.72}.tower-id{position:absolute;left:50%;bottom:calc(var(--mast-height) + 28px);transform:translateX(-50%);padding:1px 7px;border-radius:999px;background:rgba(255,255,255,.95);color:#1A1915;border:1px solid rgba(26,25,21,.08);font-family:monospace;font-size:11px;font-weight:700;white-space:nowrap}.sector-sweep{position:relative;width:170px;height:170px;transform:translate(-50%,-50%);pointer-events:none}.sector-beam{position:absolute;left:50%;top:50%;width:96px;height:96px;margin-left:-48px;margin-top:-48px;border-radius:50% 50% 0 0;background:radial-gradient(circle at 50% 100%,rgba(255,255,255,0.0) 0%,rgba(83,74,183,0.30) 58%,rgba(255,255,255,0.0) 100%);clip-path:polygon(50% 50%,7% 0%,93% 0%);opacity:var(--sector-opacity);transform-origin:50% 100%;animation:sectorSweep 6s ease-in-out infinite}.sector-a{transform:rotate(0deg) scale(1.45)}.sector-b{transform:rotate(120deg) scale(1.4);animation-delay:-2s}.sector-c{transform:rotate(240deg) scale(1.35);animation-delay:-4s}@keyframes towerPulse{0%{transform:scale(.55);opacity:.8}100%{transform:scale(2.6);opacity:0}}@keyframes sectorSweep{0%,100%{opacity:calc(var(--sector-opacity) * 0.6)}50%{opacity:var(--sector-opacity)}}</style>', unsafe_allow_html=True)
        NODES, LINKS = SIMULATION["nodes"], SIMULATION["links"]
        lats = [n["lat"] for n in NODES.values()]
        lons = [n["lon"] for n in NODES.values()]
        clat, clon = sum(lats) / len(lats), sum(lons) / len(lons)
        tc = map_tile_config(map_tile)
        if tc["tiles"] == "OpenStreetMap":
            m = folium.Map(location=[clat, clon], zoom_start=10, tiles="OpenStreetMap", control_scale=True)
        elif "positron" in tc["tiles"]:
            m = folium.Map(location=[clat, clon], zoom_start=10, tiles="CartoDB positron", control_scale=True)
        else:
            m = folium.Map(location=[clat, clon], zoom_start=10, tiles=tc["tiles"], attr=tc["attr"], control_scale=True)
        coverage_fg = folium.FeatureGroup(name="Coverage Rings", show=show_coverage)
        links_fg = folium.FeatureGroup(name="Microwave Paths", show=True)
        towers_fg = folium.FeatureGroup(name="Tower Overlay", show=True)
        for lnk in LINKS:
            role = lnk["role"]
            if role == "primary" and not show_primary:
                continue
            if role == "backup" and not show_backup:
                continue
            if role == "backbone" and not show_backbone:
                continue
            src, tgt = NODES[lnk["source"]], NODES[lnk["target"]]
            flow = link_flow_specs(lnk, src, tgt)
            ll = folium.PolyLine(locations=flow["locations"], color=flow["color"], weight=flow["weight"], opacity=flow["opacity"], dash_array=flow["dash"], popup=folium.Popup(flow["popup_html"], max_width=240), tooltip=flow["tooltip"])
            ll.add_to(links_fg)
            if role != "backbone":
                PolyLineTextPath(ll, "   >>>   ", repeat=True, offset=10, attributes={"fill": flow["color"], "font-weight": "700", "font-size": "11"}).add_to(links_fg)
            AntPath(locations=flow["locations"], color=flow["color"], pulse_color=flow["pulse_color"], weight=max(flow["weight"] + 1, 4), opacity=min(flow["opacity"] + 0.08, 1.0), dash_array=[12, 18], delay=flow["speed"], paused=False, reverse=role == "backup", tooltip=flow["tooltip"]).add_to(links_fg)
        if show_coverage:
            r_m = int((wl["metrics"]["max_radius_km"] if wl else 2.47) * 1000)
            for k, node in NODES.items():
                if node["type"] == "bs":
                    folium.Circle(location=[node["lat"], node["lon"]], radius=r_m, color=PLT_PURPLE, fill=True, fill_color=PLT_PURPLE, fill_opacity=0.06, weight=1.5, opacity=0.4, tooltip=f"{k} coverage: {r_m / 1000:.2f} km").add_to(coverage_fg)
        for k, node in NODES.items():
            is_f = node.get("status") == "offline"
            nc = "#9C9690" if is_f else node["color"]
            if node["type"] == "bs":
                folium.Marker(location=[node["lat"], node["lon"]], icon=folium.DivIcon(html=sector_beam_html(node), icon_size=(170, 170), icon_anchor=(85, 85)), tooltip=f"{k} sector footprint").add_to(towers_fg)
            folium.Marker(location=[node["lat"], node["lon"]], icon=folium.DivIcon(html=tower_icon_html(node, k), icon_size=(60, 120), icon_anchor=(30, 92)), popup=folium.Popup(f"<b>{node['name']}</b><br>Location: {node['location']}<br>Role: {node.get('role_label', '')}<br>Tower: {node.get('tower_height_m', '-')} m<br>Status: {'OFFLINE' if is_f else 'Operational'}", max_width=240), tooltip=f"{node['name']} ({'OFFLINE' if is_f else 'OK'})").add_to(towers_fg)
            if show_labels:
                folium.Marker(location=[node["lat"] + 0.018, node["lon"]], icon=folium.DivIcon(html=f"<div style='background:#fff;border:1px solid {nc};border-radius:4px;padding:2px 7px;white-space:nowrap;font-family:monospace;font-size:11px;font-weight:600;color:{nc};box-shadow:0 1px 4px rgba(0,0,0,.1)'>{k} - {node['location']}</div>", icon_size=(160, 22), icon_anchor=(80, 11))).add_to(towers_fg)
        coverage_fg.add_to(m)
        links_fg.add_to(m)
        towers_fg.add_to(m)
        folium.LayerControl(collapsed=False).add_to(m)
        m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]], padding=(30, 30))
        st.markdown('<div class="info-box"><b>Map realism:</b> Base stations now show three animated sector beams around each tower, and packet paths stay anchored to the live map while you pan and zoom.</div>', unsafe_allow_html=True)
        st_folium(m, width=None, height=660, returned_objects=[])
    with info_col:
        st.markdown('<div class="section-header">Node Details</div>', unsafe_allow_html=True)
        for k, node in SIMULATION["nodes"].items():
            is_f = node.get("status") == "offline"
            badge = '<span class="badge-fail">OFFLINE</span>' if is_f else '<span class="badge-pass">ONLINE</span>'
            c = node["color"]
            st.markdown(f'<div class="metric-card" style="border-left:3px solid {c}"><div class="label">{k} &nbsp; {badge}</div><div class="value" style="font-size:13px;color:{c}">{node["location"]}</div><div class="sub">{node.get("role_label", "Base Station")}</div><div class="sub">{node.get("tower_height_m", "-")} m tower</div></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# INTERACTIVE TOPOLOGY (3D)
# ─────────────────────────────────────────────────────────────────────────────
elif section == "Interactive Topology":
    st.markdown('<div class="section-header">3D Interactive Topology Visualization</div>', unsafe_allow_html=True)
    if not PLOTLY_OK:
        st.warning("Plotly not available. Cannot render 3D topology.")
    else:
        topo_col, detail_col = st.columns([1.8,1], gap="large")
        node_ids = list(SIMULATION["nodes"].keys())
        fig = go.Figure()
        for link in SIMULATION["links"]:
            src = SIMULATION["nodes"][link["source"]]; tgt = SIMULATION["nodes"][link["target"]]
            fig.add_trace(go.Scatter3d(x=[src["lon"],tgt["lon"]],y=[src["lat"],tgt["lat"]],z=[0,0],
                                       mode="lines",line={"color":"rgba(200,200,200,0.15)","width":2,"dash":"dot"},
                                       hoverinfo="skip",showlegend=False))
        for nid, node in SIMULATION["nodes"].items():
            add_tower_to_figure(fig, nid, node)
        for link in SIMULATION["links"]:
            add_microwave_to_figure(fig, link["source"], SIMULATION["nodes"][link["source"]],
                                    link["target"], SIMULATION["nodes"][link["target"]], link)
        fig.update_layout(
            height=680, margin={"l":0,"r":0,"t":20,"b":0},
            paper_bgcolor=PLT_BG, plot_bgcolor=PLT_BG,
            scene={
                "bgcolor":PLT_AX,
                "xaxis":{"visible":False,"showbackground":True,"backgroundcolor":PLT_AX,"gridcolor":PLT_GRID},
                "yaxis":{"visible":False,"showbackground":True,"backgroundcolor":PLT_AX,"gridcolor":PLT_GRID},
                "zaxis":{"title":"Tower Height","color":PLT_TEXT,"showbackground":True,"backgroundcolor":PLT_AX,"gridcolor":PLT_GRID},
                "camera":{"eye":{"x":1.75,"y":1.55,"z":1.05}},
                "aspectmode":"manual","aspectratio":{"x":1.18,"y":1.0,"z":0.72},
            }
        )
        with topo_col:
            st.markdown('<div class="info-box"><b>How to use:</b> Click a tower to inspect it. Microwave dishes point toward peer towers; beam colour shows transport health. Cones show communication direction.</div>', unsafe_allow_html=True)
            plot_state = st.plotly_chart(fig, use_container_width=True, key="topo3d",
                                          on_select="rerun", selection_mode="points", config={"displaylogo":False})
            sel = extract_selected_topology_node(plot_state, set(node_ids))
            if sel: st.session_state.selected_topology_node = sel

        sel_node = st.session_state.selected_topology_node if st.session_state.selected_topology_node in node_ids else node_ids[0]
        profile = build_node_profile(sel_node, SIMULATION)
        with detail_col:
            st.markdown('<div class="section-header">Node Inspection</div>', unsafe_allow_html=True)
            sel_node = st.selectbox("Selected node", node_ids, index=node_ids.index(sel_node), key="topo_sel")
            if sel_node != st.session_state.selected_topology_node:
                st.session_state.selected_topology_node = sel_node
            profile = build_node_profile(st.session_state.selected_topology_node, SIMULATION)
            pn = profile["node"]
            d1,d2 = st.columns(2)
            with d1: st.metric("Tower load", f"{pn['load_ratio']*100:.1f}%")
            with d2: st.metric("Traffic", f"{pn.get('traffic_mbps',0):.2f} Mbps")
            st.markdown(f"""
            <div class="metric-card" style="border-left:3px solid {pn['color']}">
              <div class="label">{sel_node} · {pn['location']}</div>
              <div class="value" style="font-size:15px;color:{pn['color']}">{pn.get('role_label','Network Node')}</div>
              <div class="sub">Sector: {profile['sector_area']}</div>
              <div class="sub">Status: {pn['status'].title()}</div>
              <div class="sub">Tower: {pn.get('tower_height_m','-')} m</div>
            </div>""", unsafe_allow_html=True)
            i1,i2 = st.columns(2)
            with i1: st.metric("Connected phones", profile["connected_phones"])
            with i2: st.metric("IP devices", profile["connected_devices"])
            st.markdown(f"""<div class="table-wrap"><table class="styled-table">
              <thead><tr><th>Attribute</th><th>Value</th></tr></thead><tbody>
              <tr><td>Management IP</td><td>{profile['management_ip']}</td></tr>
              <tr><td>Gateway IP</td><td>{profile['gateway_ip']}</td></tr>
              <tr><td>Telemetry</td><td>{profile['traffic']['telemetry']:.3f} Mbps</td></tr>
              <tr><td>Voice</td><td>{profile['traffic']['voice']:.3f} Mbps</td></tr>
              <tr><td>Video</td><td>{profile['traffic']['video']:.3f} Mbps</td></tr>
              </tbody></table></div>""", unsafe_allow_html=True)
            link_rows = "".join(
                f"<tr><td>{l['source']}->{l['target']}</td><td>{l['status']}</td><td>{l['assigned_mbps']:.2f}/{l['effective_capacity_mbps']:.2f} Mbps</td></tr>"
                for l in profile["links"])
            st.markdown(f"""<div class="table-wrap"><table class="styled-table">
              <thead><tr><th>Link</th><th>Status</th><th>Load</th></tr></thead>
              <tbody>{link_rows}</tbody></table></div>""", unsafe_allow_html=True)
            if profile["alarms"]:
                st.markdown("".join(f'<p>{severity_badge(a["severity"])} {a["alarm"]}</p>' for a in profile["alarms"]), unsafe_allow_html=True)
            else:
                st.success("No active alarms on this node.")

        # Microwave load test
        st.markdown('<div class="section-header">Microwave Load Test & Capacity Validation</div>', unsafe_allow_html=True)
        mw_links = [l for l in SIMULATION["links"] if l["role"] in {"primary","backup","backbone"}]
        mw_labels = [f"{l['source']} -> {l['target']} ({l['role']})" for l in mw_links]
        chosen_label = st.selectbox("Microwave path", mw_labels)
        chosen_link = mw_links[mw_labels.index(chosen_label)]
        t1,t2 = st.columns([1.05,1],gap="large")
        with t1:
            offered = st.slider("Offered traffic (Mbps)",5.0,max(50.0,float(chosen_link["capacity_mbps"])*2),
                                min(float(chosen_link["capacity_mbps"])*0.75,80.0),step=1.0)
            rain_pct = st.slider("Rain fade (%)",0,60,10)
            int_pct  = st.slider("Interference (%)",0,50,8)
            mis_deg  = st.slider("Dish misalignment (deg)",0,8,1)
            prio = st.multiselect("Priority order",["Telemetry","Voice","Video"],default=["Telemetry","Voice","Video"])
            if len(prio)!=3: prio=["Telemetry","Voice","Video"]
            mwr = simulate_microwave_test(chosen_link,offered,rain_pct,int_pct,mis_deg,prio)
        with t2:
            m1,m2,m3,m4=st.columns(4)
            with m1: st.metric("Nominal cap",f"{chosen_link['capacity_mbps']:.0f} Mbps")
            with m2: st.metric("Effective cap",f"{mwr['effective_capacity_mbps']:.2f} Mbps")
            with m3: st.metric("Load ratio",f"{mwr['load_ratio']:.2f}x")
            with m4: st.metric("Health",mwr["health"])
            st.dataframe(pd.DataFrame(mwr["service_rows"]),use_container_width=True,hide_index=True)
            rec_rows="".join(f"<tr><td>{i+1}</td><td>{t}</td></tr>" for i,t in enumerate(mwr["recommendations"]))
            st.markdown(f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>#</th><th>Recommendation</th></tr></thead><tbody>{rec_rows}</tbody></table></div>', unsafe_allow_html=True)
        if PLOTLY_OK:
            bpdf=pd.DataFrame(mwr["breakpoint_rows"])
            figmw=go.Figure()
            figmw.add_trace(go.Scatter(x=bpdf["Demand (Mbps)"],y=bpdf["Load Ratio"],
                                       mode="lines+markers",name="Load ratio",
                                       line={"color":PLT_ACCENT,"width":3},marker={"color":PLT_ACCENT}))
            for y,col,label in [(0.70,PLT_BLUE,"Healthy/Warning"),(0.85,PLT_AMBER,"Warning/High"),(1.00,PLT_RED,"Capacity limit")]:
                figmw.add_hline(y=y,line_dash="dot",line_color=col,annotation_text=label,annotation_font_color=col)
            figmw.update_layout(height=320,margin={"l":0,"r":0,"t":20,"b":0},
                                paper_bgcolor=PLT_BG,plot_bgcolor=PLT_AX,font={"color":PLT_TEXT},
                                xaxis={"title":"Demand (Mbps)","gridcolor":PLT_GRID},
                                yaxis={"title":"Load Ratio","gridcolor":PLT_GRID},showlegend=False)
            st.plotly_chart(figmw,use_container_width=True)
        st.dataframe(pd.DataFrame(mwr["breakpoint_rows"]),use_container_width=True,hide_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# FAULT MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
elif section == "Fault Management":
    st.markdown('<div class="section-header">Fault Management System</div>', unsafe_allow_html=True)
    left, right = st.columns([1.2,1], gap="large")
    with left:
        with st.form("fault_form"):
            backhaul_deg = st.slider("Backhaul degradation (%)",0,80,int(st.session_state.nms_faults["backhaul_degradation_pct"]))
            failed_bs    = st.multiselect("Base station failures",["BS1","BS2","BS3","BS4","BS5"],default=st.session_state.nms_faults["failed_bs"])
            cong_router  = st.selectbox("Router congestion target",["None","CR-1","CR-2"],index=["None","CR-1","CR-2"].index(st.session_state.nms_faults["router_congestion_router"]))
            cong_pct     = st.slider("Router congestion (%)",0,90,int(st.session_state.nms_faults["router_congestion_pct"]))
            apply_f = st.form_submit_button("Apply Fault Scenario")
            reset_f = st.form_submit_button("Reset Faults")
        if apply_f:
            st.session_state.nms_faults = {"backhaul_degradation_pct":backhaul_deg,"failed_bs":failed_bs,
                                            "router_congestion_router":cong_router,"router_congestion_pct":cong_pct}
            append_event("Config","Info","Fault scenario updated.","Simulation inputs changed.")
            st.rerun()
        if reset_f:
            st.session_state.nms_faults = clone(DEFAULT_FAULTS)
            append_event("Config","Info","Fault scenario reset.","All simulated faults cleared.")
            st.rerun()
        st.markdown('<div class="info-box"><b>Alarm logic:</b> Engine raises alarms for backhaul degradation, base station outages, router congestion, and any case where effective link capacity falls below demand.</div>', unsafe_allow_html=True)
        if reroute_check:
            st.metric("Base Stations Rerouted", f"{reroute_check['reroute_count']}/5")
            for bs, info in reroute_check.get("bs_routes",{}).items():
                if info.get("reachable"):
                    st.success(f"✓ {bs} → CR-2: {len(info['path'])-1} hops")
                else:
                    st.error(f"✗ {bs} → NO PATH")
    with right:
        critical = int((alarms_df["severity"]=="Critical").sum()) if not alarms_df.empty else 0
        major    = int((alarms_df["severity"]=="Major").sum())    if not alarms_df.empty else 0
        minor    = int((alarms_df["severity"]=="Minor").sum())    if not alarms_df.empty else 0
        a1,a2,a3,a4=st.columns(4)
        with a1: st.metric("Active Alarms",len(SIMULATION["alarms"]))
        with a2: st.metric("Critical",critical)
        with a3: st.metric("Major",major)
        with a4: st.metric("Minor",minor)
        if alarms_df.empty:
            st.success("No active alarms under current simulated conditions.")
        else:
            rows="".join(
                f"<tr><td>{r.entity}</td><td>{r.alarm}</td><td>{severity_badge(r.severity)}</td><td>{r.hint}</td></tr>"
                for r in alarms_df.itertuples())
            st.markdown(f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Entity</th><th>Alarm</th><th>Severity</th><th>Root Cause Hint</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
elif section == "Configuration":
    st.markdown('<div class="section-header">Configuration Management</div>', unsafe_allow_html=True)
    cfg = st.session_state.nms_config
    c_left, c_right = st.columns([1.2,1], gap="large")
    with c_left:
        with st.form("config_form"):
            routing_policy = st.selectbox("Routing policy",["Adaptive Failover","Load Balanced","Pinned Primary"],
                                          index=["Adaptive Failover","Load Balanced","Pinned Primary"].index(cfg["routing_policy"]))
            scheduler = st.selectbox("Scheduler",["Priority Queuing","Weighted Fair Queuing","Hybrid QoS"],
                                     index=["Priority Queuing","Weighted Fair Queuing","Hybrid QoS"].index(cfg["scheduler"]))
            primary_bw  = st.slider("Primary link BW allocation (%)",50,130,int(cfg["primary_bw_alloc_pct"]))
            backup_bw   = st.slider("Backup link BW allocation (%)",50,130,int(cfg["backup_bw_alloc_pct"]))
            backbone_bw = st.slider("Backbone BW allocation (%)",50,130,int(cfg["backbone_bw_alloc_pct"]))
            reuse_p     = st.selectbox("Frequency reuse pattern",["3/9","4/12","7/21"],
                                       index=["3/9","4/12","7/21"].index(cfg["reuse_pattern"]))
            access_freq = st.number_input("Access frequency (MHz)",min_value=700,max_value=3800,
                                          value=int(cfg["access_frequency_mhz"]),step=100)
            ant_gain    = st.slider("Antenna gain (dBi)",10,30,int(cfg["antenna_gain_dbi"]))
            ant_tilt    = st.slider("Antenna tilt (deg)",0,10,int(cfg["antenna_tilt_deg"]))
            ant_height  = st.slider("Tower height adjustment (m)",-10,15,int(cfg["antenna_height_adjust_m"]))
            auto_r      = st.checkbox("Automatic rerouting",value=bool(cfg["auto_reroute"]))
            load_b      = st.checkbox("Load balancing across links",value=bool(cfg["load_balancing"]))
            save_cfg = st.form_submit_button("Save Configuration")
        if save_cfg:
            st.session_state.nms_config = {**cfg,"routing_policy":routing_policy,"scheduler":scheduler,
                "primary_bw_alloc_pct":primary_bw,"backup_bw_alloc_pct":backup_bw,
                "backbone_bw_alloc_pct":backbone_bw,"reuse_pattern":reuse_p,
                "access_frequency_mhz":access_freq,"antenna_gain_dbi":ant_gain,
                "antenna_tilt_deg":ant_tilt,"antenna_height_adjust_m":ant_height,
                "auto_reroute":auto_r,"load_balancing":load_b}
            st.session_state.config_revision += 1
            append_event("Config","Info",f"Config revision {st.session_state.config_revision} saved.","Parameters updated.")
            st.rerun()
    with c_right:
        st.metric("Config revision", st.session_state.config_revision)
        st.metric("Routing policy", cfg["routing_policy"])
        st.metric("Scheduler", cfg["scheduler"])
        st.metric("Reuse pattern", cfg["reuse_pattern"])
        st.markdown(f'<div class="info-box"><b>Current posture:</b> Primary {cfg["primary_bw_alloc_pct"]}% | Backup {cfg["backup_bw_alloc_pct"]}% | Backbone {cfg["backbone_bw_alloc_pct"]}%<br>Access {cfg["access_frequency_mhz"]} MHz | Gain {cfg["antenna_gain_dbi"]} dBi | Tilt {cfg["antenna_tilt_deg"]} deg</div>', unsafe_allow_html=True)
        if st.button("Preview Config JSON"):
            st.json(cfg)

# ─────────────────────────────────────────────────────────────────────────────
# OPTIMIZATION
# ─────────────────────────────────────────────────────────────────────────────
elif section == "Optimization":
    st.markdown('<div class="section-header">Traffic Engineering & Optimization Engine</div>', unsafe_allow_html=True)
    rerouted = int((flow_df["decision"]=="Rerouted to backup").sum()) if not flow_df.empty else 0
    balanced = int((flow_df["decision"]=="Load balanced").sum())      if not flow_df.empty else 0
    max_util = max((l["load_ratio"] for l in SIMULATION["links"] if l["effective_capacity_mbps"]>0),default=0)
    o1,o2,o3,o4=st.columns(4)
    with o1: st.metric("Rerouted sites",rerouted)
    with o2: st.metric("Balanced sites",balanced)
    with o3: st.metric("Max link utilisation",f"{max_util*100:.1f}%")
    with o4: st.metric("Scheduler",st.session_state.nms_config["scheduler"])
    if not flow_df.empty:
        st.dataframe(flow_df,use_container_width=True,hide_index=True)
    st.markdown('<div class="info-box"><b>Priority scheduling:</b> Telemetry (patient vitals) is highest priority using Expedited Forwarding. Voice and video share remaining bandwidth via Weighted Fair Queuing. Best-effort traffic only gets leftover bandwidth.</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CAPACITY ENGINE
# ─────────────────────────────────────────────────────────────────────────────
elif section == "Capacity Engine":
    st.markdown('<div class="section-header">Capacity & Upgrade Recommendation Engine</div>', unsafe_allow_html=True)
    recs = []
    for link in SIMULATION["links"]:
        if link["status"]=="overloaded":
            recs.append({"priority":"Immediate","action":f"Upgrade link {link['source']}-{link['target']}",
                         "reason":f"Demand {link['assigned_mbps']:.2f} Mbps exceeds effective capacity {link['effective_capacity_mbps']:.2f} Mbps."})
    if df_dim is not None and df_dim["achieved_blocking"].max()>0.02:
        recs.append({"priority":"Near Term","action":"Increase voice channels","reason":"Additional channels needed to reduce Erlang B blocking below 2%."})
    if wl and wl["metrics"]["district_coverage_percent"]<5:
        recs.append({"priority":"Planned","action":"Add base station in weakest sector","reason":"Coverage remains spot-focused with limited geographic resilience."})
    if df_util is not None and (df_util["utilisation"]>=0.70).any():
        trigger_yr = int(df_util[df_util["utilisation"]>=0.70]["year"].min())
        recs.append({"priority":"Planned","action":f"Upgrade backbone before Year {trigger_yr}","reason":"Forecast utilisation crosses 70% planning threshold."})
    recs.extend({"priority":"Operational","action":t,"reason":"Generated by optimization engine."} for t in SIMULATION["recommendations"])
    if recs:
        st.dataframe(pd.DataFrame(recs).drop_duplicates(),use_container_width=True,hide_index=True)
    else:
        st.success("No upgrade actions currently required.")

# ─────────────────────────────────────────────────────────────────────────────
# TRAFFIC
# ─────────────────────────────────────────────────────────────────────────────
elif section == "Traffic":
    st.markdown('<div class="section-header">Offered Load — traffic_offered_load.csv</div>', unsafe_allow_html=True)
    if df_load is not None:
        tv=df_load[df_load["service_class"]=="voice"]["offered_load_erl"].sum()
        tvid=df_load[df_load["service_class"]=="video"]["offered_load_erl"].sum()
        tt=df_load[df_load["service_class"]=="telemetry"]["offered_load_erl"].sum()
        c1,c2,c3,c4=st.columns(4)
        with c1: st.metric("Total voice load",f"{tv:.2f} Erl")
        with c2: st.metric("Total video load",f"{tvid:.2f} Erl")
        with c3: st.metric("Total telemetry",f"{tt:.2f} Erl")
        with c4: st.metric("Sites",df_load["site"].nunique())
        dscp_map={"voice":'<span class="badge-pass">AF31</span>',
                  "video":'<span class="badge-warn">AF21</span>',
                  "telemetry":'<span class="badge-info">EF</span>'}
        rows="".join(
            f"<tr><td><b style='color:{PLT_PURPLE}'>{r.site}</b></td><td>{r.service_class.title()}</td>"
            f"<td>{dscp_map.get(r.service_class,'')}</td><td>{r.arrival_rate_per_hour}</td>"
            f"<td>{r.holding_time_s} s</td><td><b>{r.offered_load_erl:.4f}</b></td></tr>"
            for r in df_load.itertuples())
        st.markdown(f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Site</th><th>Class</th><th>DSCP</th><th>Arrivals/hr</th><th>Hold time</th><th>Offered (Erl)</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
    else:
        st.warning("Traffic offered-load data is currently unavailable.")
    st.markdown('<div class="section-header">Traffic Matrix — traffic_matrix.csv</div>', unsafe_allow_html=True)
    if df_matrix is not None:
        rows=""
        for r in df_matrix.itertuples():
            pct=r.link_utilisation*100; bw=min(100,int(pct*5))
            rows+=(f"<tr><td><b style='color:{PLT_PURPLE}'>{r.site}</b></td><td>{r.destination}</td>"
                   f"<td>{r.voice_mbps:.3f}</td><td>{r.video_mbps:.3f}</td>"
                   f"<td>{r.telemetry_mbps:.6f}</td><td><b>{r.total_mbps:.4f}</b></td>"
                   f"<td>{r.link_capacity_mbps:.0f}</td>"
                   f"<td><div style='background:{PLT_GRID};border-radius:3px;height:6px'>"
                   f"<div style='width:{bw}%;background:{PLT_ACCENT};height:6px;border-radius:3px'></div>"
                   f"</div>&nbsp;{pct:.2f}%</td></tr>")
        st.markdown(f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Site</th><th>Dest</th><th>Voice</th><th>Video</th><th>Telemetry</th><th>Total</th><th>Capacity</th><th>Utilisation</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
        st.markdown('<div class="info-box"><b>Formula:</b> A = λ × h / 3600 &nbsp;|&nbsp; λ = arrivals/hour, h = holding time (s). Video dominates at 2.0 Mbps vs voice at 0.048 Mbps.</div>', unsafe_allow_html=True)
    else:
        st.warning("Traffic matrix data is currently unavailable.")

# ─────────────────────────────────────────────────────────────────────────────
# TELETRAFFIC
# ─────────────────────────────────────────────────────────────────────────────
elif section == "Teletraffic":
    st.markdown('<div class="section-header">Erlang B Dimensioning — teletraffic_dimensioning_table.csv</div>', unsafe_allow_html=True)
    if df_dim is not None:
        per_site=df_dim[df_dim["site"]!="Backhaul Trunk"]
        trunk=df_dim[df_dim["site"]=="Backhaul Trunk"]
        c1,c2,c3,c4=st.columns(4)
        with c1: st.metric("Channels / site",int(per_site["channels_required"].iloc[0]))
        with c2: st.metric("Worst blocking",f"{per_site['achieved_blocking'].max()*100:.3f}%")
        with c3: st.metric("Trunk channels",int(trunk["channels_required"].iloc[0]) if not trunk.empty else "-")
        with c4:
            gain=per_site["channels_required"].sum()-(int(trunk["channels_required"].iloc[0]) if not trunk.empty else 0)
            st.metric("Trunking gain",f"{gain} circuits")
        rows=""
        for r in df_dim.itertuples():
            is_t=r.site=="Backhaul Trunk"
            kpi='<span class="badge-pass">PASS</span>' if r.kpi_met else '<span class="badge-fail">FAIL</span>'
            bc=PLT_RED if r.achieved_blocking>r.target_blocking else PLT_GREEN
            sc=PLT_AMBER if is_t else PLT_PURPLE
            rows+=f"<tr><td><b style='color:{sc}'>{r.site}</b></td><td>{r.offered_load_erl:.2f}</td><td>{r.channels_required}</td><td style='color:{bc}'>{r.achieved_blocking*100:.3f}%</td><td>{r.target_blocking*100:.0f}%</td><td>{kpi}</td></tr>"
        st.markdown(f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Site</th><th>Offered (Erl)</th><th>N channels</th><th>Blocking</th><th>Target</th><th>KPI</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
        st.markdown('<div class="info-box"><b>Erlang B:</b> B(A,N) = (A^N/N!) / Σ(A^k/k!) for k=0..N. Loop N upward until B ≤ 2%. <b>Trunking gain:</b> pooling 5 sites at CR-1 needs 9 trunk circuits instead of 5×4=20 individual circuits — saving 11 circuits.</div>', unsafe_allow_html=True)
    else:
        st.warning("Teletraffic dimensioning data is currently unavailable.")
    st.markdown('<div class="section-header">Delay KPIs — teletraffic_delay_kpis.csv</div>', unsafe_allow_html=True)
    if df_delay is not None:
        c1,c2,c3,c4=st.columns(4)
        with c1: st.metric("All KPIs","PASS" if bool(df_delay["met"].all()) else "FAIL")
        with c2: st.metric("Max P95 delay",f"{df_delay['delay_ms'].max():.2f} ms")
        with c3: st.metric("Worst class",df_delay.loc[df_delay['delay_ms'].idxmax(),'service_class'].title())
        with c4: st.metric("Sites checked",df_delay["site"].nunique())
        cls_badge={"telemetry":'<span class="badge-info">EF</span>',
                   "video":'<span class="badge-warn">AF21</span>',
                   "voice":'<span class="badge-pass">AF31</span>'}
        def _delay_row_html(r):
            kpi_badge = (
                '<span class="badge-pass">PASS</span>'
                if r.met
                else '<span class="badge-fail">FAIL</span>'
            )
            return (
                f"<tr><td><b style='color:{PLT_PURPLE}'>{r.site}</b></td>"
                f"<td>{cls_badge.get(r.service_class,'')} {r.service_class.title()}</td>"
                f"<td>{r.delay_ms:.2f} ms</td><td>{r.kpi_target} ms</td>"
                f"<td>{kpi_badge}</td></tr>"
            )

        rows = "".join(_delay_row_html(r) for r in df_delay.itertuples())
        st.markdown(f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Site</th><th>Class</th><th>P95 delay</th><th>Target</th><th>KPI</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# WIRELESS
# ─────────────────────────────────────────────────────────────────────────────
elif section == "Wireless":
    st.markdown('<div class="section-header">COST 231-Hata Wireless Analysis — wireless_results.json</div>', unsafe_allow_html=True)
    if wl:
        p,mx = wl["parameters"],wl["metrics"]
        c1,c2,c3,c4=st.columns(4)
        with c1: st.metric("Edge radius (-100 dBm)",f"{mx['max_radius_km']} km")
        with c2: st.metric("Service radius (-90 dBm)",f"{mx.get('service_radius_km','-')} km")
        with c3: st.metric("Area per site",f"{mx['area_per_site_km2']} km²")
        with c4: st.metric("District coverage",f"{mx['district_coverage_percent']}%")
        col1,col2=st.columns(2)
        with col1:
            st.markdown(f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Parameter</th><th>Value</th></tr></thead><tbody>'
                        f"<tr><td>Access frequency</td><td>{p['frequency_mhz']} MHz</td></tr>"
                        f"<tr><td>TX power</td><td>{p['tx_power_dbm']} dBm</td></tr>"
                        f"<tr><td>TX antenna gain</td><td>{p.get('tx_gain_dbi','-')} dBi</td></tr>"
                        f"<tr><td>RX antenna gain</td><td>{p.get('rx_gain_dbi','-')} dBi</td></tr>"
                        f"<tr><td>RX sensitivity</td><td>{p['sensitivity_dbm']} dBm</td></tr>"
                        f"<tr><td>BS height</td><td>{p.get('bs_height_m','-')} m</td></tr>"
                        "<tr><td>Propagation model</td><td>COST 231-Hata</td></tr>"
                        "</tbody></table></div>", unsafe_allow_html=True)
        with col2:
            if df_wireless_thresholds is not None:
                rows="".join(
                    f"<tr><td>{r.label}</td><td>{r.threshold_dbm} dBm</td>"
                    f"<td>{r.baseline_coverage_pct:.2f}%</td><td>{r.improved_coverage_pct:.2f}%</td>"
                    f"<td>{r.gain_pct_points:.2f} pts</td></tr>"
                    for r in df_wireless_thresholds.itertuples())
                st.markdown(f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Threshold</th><th>Level</th><th>Baseline</th><th>Improved</th><th>Gain</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
            else:
                st.info("wireless_thresholds.csv not found.")
        if PLOTLY_OK and df_wireless_surface is not None:
            pivot=df_wireless_surface.pivot(index="y_km",columns="x_km",values="received_power_dbm").sort_index(ascending=False)
            figw=go.Figure(data=go.Heatmap(z=pivot.values,x=list(pivot.columns),y=list(pivot.index),
                                            colorscale="Cividis",colorbar={"title":"dBm"},zmin=-120,zmax=-60))
            figw.update_layout(height=360,margin={"l":0,"r":0,"t":10,"b":0},
                               paper_bgcolor=PLT_BG,plot_bgcolor=PLT_AX,font={"color":PLT_TEXT},
                               xaxis_title="District X (km)",yaxis_title="District Y (km)")
            st.plotly_chart(figw,use_container_width=True)
        st.markdown(f'<div class="info-box"><b>Coverage deep-dive:</b> Two received-power thresholds compared with improvement scenario for cost-vs-coverage tradeoff analysis. Recommended action: {wl.get("improvement_action","Add an infill site or raise antenna height.")}</div>', unsafe_allow_html=True)
    else:
        st.warning("Wireless analysis data is currently unavailable.")

# ─────────────────────────────────────────────────────────────────────────────
# BACKHAUL LINKS
# ─────────────────────────────────────────────────────────────────────────────
elif section == "Backhaul Links":
    st.markdown('<div class="section-header">Microwave Backhaul Link Budget</div>', unsafe_allow_html=True)

    # Prefer computed results from modules, fallback to CSV
    if backhaul_df_computed is not None and len(backhaul_results_computed) > 0:
        pass_count = sum(1 for r in backhaul_results_computed if r['pass_fail']=='PASS')
        fail_count = len(backhaul_results_computed)-pass_count
        c1,c2,c3,c4=st.columns(4)
        with c1: st.metric("Total Links",len(backhaul_results_computed))
        with c2: st.metric("PASS",pass_count,delta=f"{pass_count/len(backhaul_results_computed)*100:.0f}%")
        with c3: st.metric("FAIL",fail_count,delta_color="inverse" if fail_count>0 else "off")
        with c4: st.metric("Required Margin","≥20 dB")
        if fail_count>0: st.error(f"❌ {fail_count} link(s) FAIL the 20 dB fade margin requirement!")
        else:            st.success("✅ All links PASS the 20 dB fade margin requirement!")
        display_df=backhaul_df_computed.copy()
        display_df.columns=['Link','Type','Role','Freq(GHz)','Dist(km)','FSPL(dB)','Rain(dB)','Rx Power(dBm)','Margin(dB)','Req(dB)','Status','Cap(Mbps)']
        def color_status(val):
            return f'color:{PLT_GREEN};font-weight:600' if val=='PASS' else f'color:{PLT_RED};font-weight:600'
        st.dataframe(display_df.style.applymap(color_status,subset=['Status']),use_container_width=True,hide_index=True)
        fig,ax=plt.subplots(figsize=(12,4))
        links_l=[r['link_name'] for r in backhaul_results_computed]
        margins=[r['fade_margin_db'] for r in backhaul_results_computed]
        bars_c=[PLT_GREEN if m>=20 else PLT_RED for m in margins]
        ax.bar(links_l,margins,color=bars_c,alpha=0.85,zorder=3,width=0.6)
        ax.axhline(20,color=PLT_AMBER,linestyle='--',linewidth=2,label='Required (20 dB)',zorder=4)
        ax.set_ylabel('Fade Margin (dB)'); ax.set_xlabel('Link')
        ax.tick_params(axis='x',rotation=45); ax.grid(axis='y',zorder=0); ax.legend()
        plt.tight_layout(); st.pyplot(fig); plt.close(fig)

    elif df_backhaul is not None:
        c1,c2,c3,c4=st.columns(4)
        with c1: st.metric("Links assessed",len(df_backhaul))
        with c2: st.metric("Worst fade margin",f"{df_backhaul['fade_margin_db'].min():.1f} dB")
        with c3: st.metric("Worst Rx power",f"{df_backhaul['rx_power_dbm'].min():.1f} dBm")
        with c4: st.metric("PASS links",int((df_backhaul["status"]=="PASS").sum()))
        def _backhaul_row_html(r):
            badge_html = (
                '<span class="badge-pass">PASS</span>'
                if r.status == "PASS"
                else '<span class="badge-warn">WATCH</span>'
            )
            return (
                f"<tr><td>{r.source}???{r.target}</td><td>{r.role.title()}</td><td>{r.frequency_ghz:.1f} GHz</td>"
                f"<td>{r.distance_km:.2f} km</td><td>{r.rx_power_dbm:.2f} dBm</td>"
                f"<td>{r.fade_margin_db:.2f} dB</td><td>{r.rain_margin_db:.1f} dB</td>"
                f"<td>{r.estimated_availability_pct:.3f}%</td>"
                f"<td>{badge_html}</td></tr>"
            )

        rows = "".join(_backhaul_row_html(r) for r in df_backhaul.itertuples())
        st.markdown(f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Path</th><th>Role</th><th>Freq</th><th>Distance</th><th>Rx</th><th>Fade Margin</th><th>Rain Margin</th><th>Availability</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
        # Bar chart from CSV
        fig,ax=plt.subplots(figsize=(12,4))
        ax.bar(df_backhaul['source'].astype(str)+'→'+df_backhaul['target'].astype(str),
               df_backhaul['fade_margin_db'],
               color=[PLT_GREEN if v>=20 else PLT_RED for v in df_backhaul['fade_margin_db']],alpha=0.85,zorder=3)
        ax.axhline(20,color=PLT_AMBER,linestyle='--',linewidth=2,label='Required (20 dB)',zorder=4)
        ax.set_ylabel('Fade Margin (dB)'); ax.tick_params(axis='x',rotation=45); ax.grid(axis='y',zorder=0); ax.legend()
        plt.tight_layout(); st.pyplot(fig); plt.close(fig)
    else:
        st.warning("Backhaul link-budget data is currently unavailable.")
    st.markdown('<div class="info-box"><b>Computed link budget:</b> received power derived from TX power, antenna gains, free-space path loss, and misc losses. Fade margin and rain margin confirm each microwave span is robust for emergency traffic.</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# QoS
# ─────────────────────────────────────────────────────────────────────────────
elif section == "QoS":
    st.markdown('<div class="section-header">QoS — Delay KPIs & Scheduler Design</div>', unsafe_allow_html=True)
    if df_delay is not None:
        all_pass=bool(df_delay["met"].all())
        c1,c2,c3,c4=st.columns(4)
        with c1: st.metric("All KPIs","PASS" if all_pass else "FAIL")
        with c2: st.metric("Max P95 delay",f"{df_delay['delay_ms'].max():.2f} ms")
        with c3: st.metric("Worst class",df_delay.loc[df_delay['delay_ms'].idxmax(),'service_class'].title())
        with c4: st.metric("Sites checked",df_delay["site"].nunique())
        col1,col2=st.columns(2)
        with col1:
            cls_badge={"telemetry":'<span class="badge-info">EF</span>',
                       "video":'<span class="badge-warn">AF21</span>',
                       "voice":'<span class="badge-pass">AF31</span>'}
            def _delay_row_html_lower(r):
                kpi_badge = (
                    '<span class="badge-pass">PASS</span>'
                    if r.met
                    else '<span class="badge-fail">FAIL</span>'
                )
                return (
                    f"<tr><td><b style='color:{PLT_PURPLE}'>{r.site}</b></td>"
                    f"<td>{cls_badge.get(r.service_class,'')} {r.service_class.title()}</td>"
                    f"<td>{r.delay_ms:.2f} ms</td><td>{r.kpi_target} ms</td>"
                    f"<td>{kpi_badge}</td></tr>"
                )

            rows = "".join(_delay_row_html_lower(r) for r in df_delay.itertuples())
            st.markdown(f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Site</th><th>Class</th><th>P95 delay</th><th>Target</th><th>KPI</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Class</th><th>DSCP</th><th>Scheduler</th><th>BW</th><th>KPI</th></tr></thead><tbody>'
                        '<tr><td>Telemetry</td><td><span class="badge-info">EF 46</span></td><td>Strict Priority</td><td>—</td><td>P95 ≤ 50 ms</td></tr>'
                        '<tr><td>Voice</td><td><span class="badge-pass">AF31 26</span></td><td>WFQ 30%</td><td>30%</td><td>Block ≤ 2%</td></tr>'
                        '<tr><td>Video</td><td><span class="badge-warn">AF21 18</span></td><td>WFQ 40%</td><td>40%</td><td>P95 ≤ 150 ms</td></tr>'
                        '<tr><td>Best effort</td><td>0</td><td>WFQ 30%</td><td>30%</td><td>—</td></tr>'
                        '</tbody></table></div>', unsafe_allow_html=True)
            st.markdown('<div class="info-box"><b>How it works:</b> Telemetry (patient vitals) uses Expedited Forwarding — jumps the queue every time. Voice and video share remaining bandwidth via Weighted Fair Queuing. Best-effort only gets leftover bandwidth.</div>', unsafe_allow_html=True)
    else:
        st.warning("QoS delay KPI data is currently unavailable.")

# ─────────────────────────────────────────────────────────────────────────────
# ROUTING & SIGNALING
# ─────────────────────────────────────────────────────────────────────────────
elif section == "Routing & Signaling":
    st.markdown('<div class="section-header">Routing Tables & Signaling Analysis</div>', unsafe_allow_html=True)
    col1,col2=st.columns(2)
    with col1:
        st.subheader("Routing Tables")
        if routing_tables:
            bs_nodes=[n for n in (G_obj.nodes() if G_obj else []) if str(n).startswith("BS")]
            routing_data=[]
            for bs in bs_nodes[:5]:
                for dst in ['CR-1','CR-2']:
                    nh=routing_tables.get(bs,{}).get(dst,'N/A')
                    routing_data.append({'Source':bs,'Destination':dst,'Next Hop':nh})
            if routing_data:
                st.dataframe(pd.DataFrame(routing_data),use_container_width=True,hide_index=True)
            else:
                st.info("No routing data computed.")
        else:
            st.info("Routing modules not available. Ensure topology.py and routing.py are present.")
        if failure_mode and reroute_check:
            st.metric("Reroute Status",f"{reroute_check['reroute_count']}/5 BS → CR-2")

    with col2:
        st.subheader("Signaling Load & Call Setup")
        if df_signal is not None and df_signal_summary is not None:
            summary=df_signal_summary.iloc[0]
            st.metric("Total BHCA",f"{summary['voice_busy_hour_attempts_hr']:.0f}")
            st.metric("Worst Setup Delay",f"{summary['worst_call_setup_delay_ms']:.1f} ms")
            st.metric("All KPIs Met","✅" if bool(summary["network_kpi_met"]) else "❌")
        elif TRAFFIC_MODS and scenario_obj:
            try:
                sig_sum=signaling_summary(scenario_obj,1.0)
                st.metric("Total BHCA",f"{sig_sum['total_bhca']:.0f}")
                st.metric("Worst Setup Delay",f"{sig_sum['worst_setup_delay_ms']:.1f} ms")
                st.metric("All KPIs Met","✅" if sig_sum['all_kpis_met'] else "❌")
            except Exception:
                st.info("Signaling data not available.")
        else:
            st.info("Signaling data is currently unavailable.")

    # Call setup delay chart
    if df_signal is not None:
        st.subheader("Call Setup Delay per Base Station")
        fig,ax=plt.subplots(figsize=(10,4))
        sites_s=df_signal['site'].tolist(); delays=df_signal['call_setup_delay_ms'].tolist()
        target=df_signal['call_setup_target_ms'].iloc[0] if 'call_setup_target_ms' in df_signal.columns else 200
        bar_c=[PLT_GREEN if d<=target else PLT_RED for d in delays]
        ax.bar(sites_s,delays,color=bar_c,alpha=0.85,zorder=3,width=0.6)
        ax.axhline(target,color=PLT_AMBER,linestyle='--',linewidth=2,label=f'KPI Target ({target} ms)',zorder=4)
        ax.set_ylabel('Setup Delay (ms)'); ax.set_xlabel('Base Station')
        ax.grid(axis='y',zorder=0); ax.legend(); plt.tight_layout()
        st.pyplot(fig); plt.close(fig)

    # Normal vs Burst
    st.subheader("Normal vs Emergency Burst Signaling")
    normal_cps=5.0; burst_cps=25.0
    normal_load=(normal_cps*10*100*8)/1000; burst_load=(burst_cps*10*100*8)/1000
    channel_cap=64.0
    c1,c2,c3,c4=st.columns(4)
    with c1: st.metric("Normal CPS",f"{normal_cps} calls/sec")
    with c2: st.metric("Burst CPS",f"{burst_cps} calls/sec",delta="5×")
    with c3: st.metric("Normal Load",f"{normal_load:.2f} kbps",delta=f"{normal_load/channel_cap*100:.0f}%")
    with c4: st.metric("Burst Load",f"{burst_load:.2f} kbps",delta=f"{burst_load/channel_cap*100:.0f}%",delta_color="inverse")

    if df_signal is not None:
        def _signal_row_html(r):
            kpi_badge = (
                '<span class="badge-pass">PASS</span>'
                if r.kpi_met
                else '<span class="badge-fail">FAIL</span>'
            )
            return (
                f"<tr><td>{r.site}</td><td>{r.voice_call_attempts_hr:.1f}</td><td>{r.telemetry_sessions_hr:.1f}</td>"
                f"<td>{r.signaling_msgs_hr:.1f}</td><td>{r.processor_load_pct:.1f}%</td>"
                f"<td>{r.call_setup_delay_ms:.1f} ms</td>"
                f"<td>{kpi_badge}</td></tr>"
            )

        rows = "".join(_signal_row_html(r) for r in df_signal.itertuples())
        st.markdown(f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Site</th><th>Voice/hr</th><th>Telemetry/hr</th><th>Msgs/hr</th><th>Proc Load</th><th>Call Setup</th><th>KPI</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# STRESS TEST
# ─────────────────────────────────────────────────────────────────────────────
elif section == "Stress Test":
    st.markdown('<div class="section-header">Load Stress Sweep — stress_test_results.csv</div>', unsafe_allow_html=True)
    if df_stress is not None:
        amin=float(df_stress["alpha"].min()); amax=float(df_stress["alpha"].max())
        alpha_sel=st.slider("Inspect load multiplier α",amin,amax,amin,step=0.1)
        row=df_stress[df_stress["alpha"]==round(alpha_sel,1)]
        if not row.empty:
            r=row.iloc[0]
            c1,c2,c3,c4=st.columns(4)
            with c1: st.metric("α",f"{r['alpha']}×")
            with c2: st.metric("Voice blocking",f"{r['voice_blocking']*100:.2f}%",delta="OVER" if not r["voice_kpi_met"] else "OK")
            with c3: st.metric("Video P95",f"{r['video_delay_ms']:.2f} ms")
            with c4: st.metric("System","PASS" if r["voice_kpi_met"] and r["video_kpi_met"] else "FAIL")
            if not r["voice_kpi_met"]:
                st.error(f"Voice blocking {r['voice_blocking']*100:.2f}% > 2% at α={r['alpha']}×. Fix: increase N from 4 to 5 channels per site.")
            else:
                st.success(f"All KPIs met at α={r['alpha']}×.")

        fig,ax=plt.subplots(figsize=(10,4))
        ax.plot(df_stress['load_multiplier'] if 'load_multiplier' in df_stress.columns else df_stress['alpha'],
                df_stress['voice_blocking']*100,'o-',color=PLT_ACCENT,lw=2.5,label='Voice Blocking (%)',ms=6)
        ax.axhline(2,color=PLT_AMBER,linestyle='--',linewidth=2,label='Target (2%)')
        ax.set_xlabel('Load Multiplier α'); ax.set_ylabel('Blocking Probability (%)')
        ax.grid(axis='y'); ax.legend(); plt.tight_layout()
        st.pyplot(fig); plt.close(fig)

        rows=""
        for r in df_stress.itertuples():
            fail=not r.voice_kpi_met; is_brk=(r.alpha==1.5)
            bg="background:#FEF2F2;" if fail else ""
            kpiv='<span class="badge-fail">FAIL</span>' if fail else '<span class="badge-pass">PASS</span>'
            mark=" ◄ BREAK" if is_brk else ""
            rows+=f"<tr style='{bg}'><td>{r.alpha}??{mark}</td><td>{r.voice_blocking*100:.2f}%</td><td>{r.video_delay_ms:.2f} ms</td><td>{kpiv}</td><td>{kpiv}</td></tr>"
        st.markdown(f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>α</th><th>Voice blocking</th><th>Video P95</th><th>Voice KPI</th><th>All KPIs</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
        st.markdown('<div class="info-box"><b>Breaking point α=1.5</b> — voice fails first (blocking 2.18% > 2%). Telemetry and video never fail because link utilisation is only ~2%. The bottleneck is always the number of voice circuits (N=4), not bandwidth. Fix: N=5 per site pushes the breaking point beyond α=2.0.</div>', unsafe_allow_html=True)
    elif TRAFFIC_MODS and scenario_obj:
        st.info("Generating stress sweep from modules...")
        try:
            sweep=stress_sweep(scenario_obj); bp=find_breaking_point(scenario_obj)
            c1,c2,c3=st.columns(3)
            with c1: st.metric("Breaking Point α",f"{bp.get('first_failure_alpha','N/A')}")
            with c2: st.metric("First KPI Failed",bp.get('first_failure_kpi','None'))
            with c3: st.metric("Status at α=1.0","✅ PASS" if sweep.iloc[0]['all_kpis_met'] else "❌ FAIL")
            st.dataframe(sweep,use_container_width=True,hide_index=True)
        except Exception as e:
            st.warning(f"Stress sweep computation failed: {e}")
    else:
        st.warning("Stress-test data is currently unavailable.")

# ─────────────────────────────────────────────────────────────────────────────
# FORECAST
# ─────────────────────────────────────────────────────────────────────────────
elif section == "Forecast":
    st.markdown('<div class="section-header">5-Year Capacity Forecast — forecasting_utilisation_annual.csv</div>', unsafe_allow_html=True)
    if df_util is not None:
        plan_yr=(df_util[df_util["utilisation"]>=0.70]["year"].min() if (df_util["utilisation"]>=0.70).any() else "N/A")
        act_yr =(df_util[df_util["utilisation"]>=0.90]["year"].min() if (df_util["utilisation"]>=0.90).any() else "N/A")
        c1,c2,c3,c4=st.columns(4)
        with c1: st.metric("Planning trigger (70%)",f"Year {plan_yr}")
        with c2: st.metric("Action trigger (90%)",f"Year {act_yr}")
        with c3: st.metric("Year 5 utilisation",f"{df_util['utilisation'].max()*100:.1f}%")
        with c4: st.metric("CAGR","15% / year")
        col1,col2=st.columns(2)
        with col1:
            rows=""
            for r in df_util.itertuples():
                pct=r.utilisation*100; raw=str(r.status).upper()
                if "SAFE" in raw:    badge,bc='<span class="badge-pass">SAFE</span>',PLT_GREEN
                elif "PLAN" in raw:  badge,bc='<span class="badge-warn">PLAN UPGRADE</span>',PLT_AMBER
                else:                badge,bc='<span class="badge-fail">UPGRADE NOW</span>',PLT_RED
                bw=min(100,int(pct))
                rows+=(f"<tr><td>Year {int(r.year)}</td>"
                       f"<td>{pct:.1f}%<div style='background:{PLT_GRID};border-radius:3px;height:6px;margin-top:3px'>"
                       f"<div style='width:{bw}%;background:{bc};height:6px;border-radius:3px'></div></div></td>"
                       f"<td>{r.traffic_mbps:.1f} Mbps</td><td>{badge}</td></tr>")
            st.markdown(f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Year</th><th>Utilisation</th><th>Traffic</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
        with col2:
            if df_plan is not None:
                rows="".join(
                    f"<tr><td><b>{r.Phase}</b></td><td><span class='badge-info'>{r.Trigger}</span></td><td>{r.Action}</td><td style='color:{PLT_MUTED};font-size:11px'>{r.Goal}</td></tr>"
                    for r in df_plan.itertuples())
                st.markdown(f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Phase</th><th>Trigger</th><th>Action</th><th>Goal</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
            st.markdown('<div class="info-box"><b>Formula:</b> ρ(t) = ρ₀ × (1+0.15)^t &nbsp;|&nbsp; Starting at 60%, growing 15%/year.<br>Year 2 = planning (70%). Year 3 = upgrade deadline (90%). Year 4+ = over capacity without upgrade.</div>', unsafe_allow_html=True)
    else:
        st.warning("Forecasting data is currently unavailable.")

# ─────────────────────────────────────────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────────────────────────────────────────
elif section == "Events":
    st.markdown('<div class="section-header">Event & Logging System</div>', unsafe_allow_html=True)
    events_df=pd.DataFrame(st.session_state.event_log)
    if events_df.empty:
        st.info("No events logged yet.")
    else:
        events_df=events_df.sort_values("timestamp",ascending=False)
        e1,e2,e3=st.columns(3)
        with e1: st.metric("Total events",len(events_df))
        with e2: st.metric("Alarm events",int((events_df["type"]=="Alarm").sum()))
        with e3: st.metric("Routing events",int((events_df["type"]=="Routing").sum()))
        st.dataframe(events_df,use_container_width=True,hide_index=True)
        st.download_button("Download Logs (CSV)",events_df.to_csv(index=False).encode("utf-8"),"tele527_event_log.csv","text/csv")

# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════
st.divider()
st.markdown("""
<div style="text-align:center;color:#9C9690;font-size:11px;padding:8px 0;font-family:'DM Sans',sans-serif">
  District Telehealth &amp; Emergency Communication Network Management System &nbsp;|&nbsp;
  BIUST · Group 1 · TELE 527 &nbsp;|&nbsp;
  Palapye / Serowe, Central District, Botswana &nbsp;|&nbsp;
  Student 4: Tsotlhe Seiphepi (Signaling &amp; Routing Lead)
</div>""", unsafe_allow_html=True)
