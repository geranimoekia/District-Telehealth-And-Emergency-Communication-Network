"""
District Telehealth & Emergency Communication Network Management System
========================================================================
TELE 527 · Group 1 · BIUST · Palapye / Serowe, Botswana

Run:  streamlit run src/dashboard.py
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
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np

try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_OK = True
except Exception:
    go = None
    px = None
    PLOTLY_OK = False

try:
    import networkx as nx
    NX_OK = True
except Exception:
    nx = None
    NX_OK = False

st.set_page_config(
    page_title="TELE 527 | District Telehealth NMS",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ══════════════════════════════════════════════════════════════════════════════
#  THEME
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;1,400&family=DM+Sans:wght@300;400;500;600&display=swap');
:root {
  --bg:#FFFFFF;--surface:#FFFFFF;--surface2:#F5F5F7;--border:#D2D2D7;
  --border2:#C7C7CC;--text:#1D1D1F;--muted:#6E6E73;--subtle:#86868B;
  --accent:#0071E3;--accent-h:#0077ED;--accent-bg:#EBF3FF;
  --green:#34C759;--green-bg:#F0FFF4;--green-bdr:#86EFAC;
  --amber:#FF9F0A;--amber-bg:#FFFBEB;--amber-bdr:#FDE68A;
  --red:#FF3B30;--red-bg:#FFF1F0;--red-bdr:#FCA5A5;
  --blue:#0071E3;--blue-bg:#EBF3FF;--blue-bdr:#BFDBFE;
  --purple:#5856D6;--r:10px;--r-sm:6px;
  --shadow:0 1px 3px rgba(29,29,31,.07),0 1px 2px rgba(29,29,31,.04);
  --shadow-md:0 4px 14px rgba(29,29,31,.09),0 2px 4px rgba(29,29,31,.05);
}
html,body,[data-testid="stAppViewContainer"],.stApp{background-color:var(--bg)!important;font-family:'DM Sans',ui-sans-serif,system-ui,sans-serif;color:var(--text)}
.main .block-container{padding-top:1.2rem;padding-bottom:2rem;max-width:1440px}
[data-testid="stSidebar"]{background-color:var(--surface)!important;border-right:1px solid var(--border)!important}
[data-testid="stSidebar"] .stMarkdown p,[data-testid="stSidebar"] .stMarkdown li{color:var(--muted);font-size:13px}
[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3{color:var(--text);font-size:14px;font-weight:600;letter-spacing:-0.01em}
[data-testid="stSidebar"] div[data-testid="stRadio"]>div{background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:6px}
[data-testid="stSidebar"] div[data-testid="stRadio"] label>div:first-child{display:none}
[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"]{display:flex;flex-direction:column;gap:3px}
[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label{border:1px solid transparent;border-radius:var(--r-sm);padding:9px 12px;background:transparent;transition:all 120ms ease;cursor:pointer}
[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label:hover{background:var(--accent-bg);border-color:var(--border2)}
[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label p{color:var(--muted);font-size:13px;font-weight:500}
[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked){background:var(--accent-bg);border-color:var(--accent);box-shadow:inset 3px 0 0 var(--accent)}
[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) p{color:var(--accent);font-weight:600}
.title-bar{background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--accent);border-radius:var(--r);padding:18px 26px;margin-bottom:20px;box-shadow:var(--shadow)}
.title-bar h1{font-family:'Lora',ui-serif,Georgia,serif;color:var(--text);font-size:20px;font-weight:600;letter-spacing:-0.02em;margin:0 0 5px 0}
.title-bar p{color:var(--muted);font-size:12px;margin:0;line-height:1.6}
.section-header{font-size:10.5px;font-weight:700;color:var(--subtle);text-transform:uppercase;letter-spacing:0.09em;border-bottom:1px solid var(--border);padding-bottom:8px;margin-bottom:16px;margin-top:6px}
.metric-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:14px 18px;margin-bottom:10px;box-shadow:var(--shadow);transition:box-shadow .15s}
.metric-card:hover{box-shadow:var(--shadow-md)}
.metric-card .label{font-size:11px;color:var(--subtle);text-transform:uppercase;letter-spacing:0.07em;margin-bottom:5px;font-weight:500}
.metric-card .value{font-size:18px;font-weight:600;color:var(--text);letter-spacing:-0.02em}
.metric-card .sub{font-size:11px;color:var(--muted);margin-top:3px}
.badge-pass{background:var(--green-bg);color:var(--green);border:1px solid var(--green-bdr);border-radius:var(--r-sm);padding:2px 9px;font-size:11px;font-weight:600}
.badge-fail{background:var(--red-bg);color:var(--red);border:1px solid var(--red-bdr);border-radius:var(--r-sm);padding:2px 9px;font-size:11px;font-weight:600}
.badge-warn{background:var(--amber-bg);color:var(--amber);border:1px solid var(--amber-bdr);border-radius:var(--r-sm);padding:2px 9px;font-size:11px;font-weight:600}
.badge-info{background:var(--blue-bg);color:var(--blue);border:1px solid var(--blue-bdr);border-radius:var(--r-sm);padding:2px 9px;font-size:11px;font-weight:600}
.badge-first-fail{background:#FEF2F2;color:#991B1B;border:2px solid #F87171;border-radius:var(--r-sm);padding:3px 10px;font-size:11px;font-weight:700;animation:pulse-red 1.5s ease-in-out infinite}
@keyframes pulse-red{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,0.4)}50%{box-shadow:0 0 0 4px rgba(239,68,68,0)}}
.table-wrap{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;margin-bottom:16px;box-shadow:var(--shadow)}
.styled-table{width:100%;border-collapse:collapse;font-size:13px}
.styled-table th{background:var(--surface2);color:var(--subtle);font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;padding:9px 14px;border-bottom:1px solid var(--border);text-align:left}
.styled-table td{padding:9px 14px;border-bottom:1px solid var(--border);color:var(--text);font-size:13px;vertical-align:middle}
.styled-table tr:last-child td{border-bottom:none}
.styled-table tr:hover td{background:var(--surface2)}
.info-box{background:var(--accent-bg);border:1px solid #BFDBFE;border-left:3px solid var(--accent);border-radius:var(--r);padding:12px 16px;margin-bottom:12px;font-size:13px;color:var(--text);line-height:1.6}
.info-box b{color:var(--text)}
.ss7-flow{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:16px;font-family:monospace;font-size:12px;line-height:2;color:var(--text)}
.ss7-arrow{color:var(--accent);font-weight:700}
.ss7-label{color:var(--blue);font-weight:600}
.fail-first-banner{background:#FEF2F2;border:1px solid #FCA5A5;border-left:4px solid #C0392B;border-radius:var(--r);padding:12px 16px;margin:10px 0;font-size:13px;font-weight:600;color:#991B1B}
hr{border-color:var(--border)!important}
[data-testid="stMetric"]{background:var(--surface)!important;border:1px solid var(--border)!important;border-radius:var(--r)!important;padding:14px 16px!important;box-shadow:var(--shadow)!important}
[data-testid="stMetricLabel"]{color:var(--subtle)!important;font-size:11px!important;text-transform:uppercase;letter-spacing:0.06em}
[data-testid="stMetricValue"]{color:var(--text)!important;font-size:22px!important;font-weight:600!important;letter-spacing:-0.02em}
[data-testid="stDataFrame"]>div{border:1px solid var(--border)!important;border-radius:var(--r)!important}
.stButton>button{background:var(--accent)!important;color:#fff!important;border:none!important;border-radius:var(--r-sm)!important;font-size:13px!important;font-weight:500!important;padding:8px 20px!important;transition:background .15s!important}
.stButton>button:hover{background:var(--accent-h)!important}
[data-testid="stExpander"]{border:1px solid var(--border)!important;border-radius:var(--r)!important;background:var(--surface)!important}
[data-testid="stAlert"]{border-radius:var(--r)!important;font-size:13px!important}
h1,h2,h3{color:var(--text)!important;letter-spacing:-0.01em}
h2{font-size:16px!important;font-weight:600!important}
h3{font-size:14px!important;font-weight:600!important}
.stSelectbox label,.stSlider label,.stCheckbox label,.stMultiSelect label,.stNumberInput label,.stTextInput label{color:var(--muted)!important;font-size:12px!important}
.stCaption,[data-testid="stCaptionContainer"]{color:var(--subtle)!important;font-size:11px!important}
[data-baseweb="select"] [data-baseweb="input"] input,[data-baseweb="select"] div[aria-selected]{color:var(--text)!important}
[data-baseweb="select"]>div{background:var(--surface)!important;border-color:var(--border)!important;color:var(--text)!important}
[data-baseweb="popover"] [role="option"]{color:var(--text)!important;background:var(--surface)!important}
[data-baseweb="popover"] [role="option"]:hover{background:var(--surface2)!important}
[data-baseweb="select"] span,[data-baseweb="select"] div{color:var(--text)!important}
[data-testid="stRadio"] label p,[data-testid="stRadio"] div[data-testid="stMarkdownContainer"] p{color:var(--text)!important}
[data-testid="stRadio"] label{color:var(--text)!important}
[data-testid="stRadio"] div[role="radiogroup"]{gap:6px}
[data-testid="stRadio"] div[role="radiogroup"] label{background:var(--surface2);border:1px solid var(--border);border-radius:var(--r-sm);padding:6px 14px;cursor:pointer;transition:all 120ms}
[data-testid="stRadio"] div[role="radiogroup"] label:hover{border-color:var(--accent);background:var(--accent-bg)}
[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked){background:var(--accent-bg);border-color:var(--accent);color:var(--accent)!important}
[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) p{color:var(--accent)!important;font-weight:600}
[data-testid="stRadio"] div[role="radiogroup"] label>div:first-child{display:none}
[data-baseweb="tab-list"]{background:var(--surface2)!important;border-bottom:2px solid var(--border)!important}
[data-baseweb="tab"]{color:var(--muted)!important;background:transparent!important;font-size:13px!important;font-weight:500!important;padding:8px 16px!important}
[data-baseweb="tab"]:hover{color:var(--text)!important;background:var(--surface)!important}
[data-baseweb="tab"][aria-selected="true"]{color:var(--accent)!important;border-bottom:2px solid var(--accent)!important;font-weight:600!important}
[data-baseweb="tab"] div,[data-baseweb="tab"] p,[data-baseweb="tab"] span{color:inherit!important}
[data-baseweb="select"] [data-testid="stMarkdownContainer"] p,[data-baseweb="select"] div[class*="ValueContainer"] *{color:var(--text)!important}
.js-plotly-plot{border-radius:var(--r);border:1px solid var(--border);overflow:hidden}
.antenna-card{background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--purple);border-radius:var(--r);padding:14px 18px;margin-bottom:10px;box-shadow:var(--shadow)}
.qos-fail-order{background:#FEF2F2;border:1px solid #FCA5A5;border-radius:var(--r);padding:10px 14px;margin-bottom:12px;font-size:12px}
</style>
""", unsafe_allow_html=True)

PLT_BG = "#FFFFFF"
PLT_AX = "#F5F5F7"
PLT_TEXT = "#1D1D1F"
PLT_GRID = "#D2D2D7"
PLT_ACCENT = "#0071E3"
PLT_GREEN = "#34C759"
PLT_RED = "#FF3B30"
PLT_BLUE = "#0071E3"
PLT_AMBER = "#FF9F0A"
PLT_PURPLE = "#5856D6"
PLT_MUTED = "#86868B"

mpl.rcParams.update({"figure.facecolor": PLT_BG,
                     "axes.facecolor": PLT_AX,
                     "axes.edgecolor": PLT_GRID,
                     "axes.labelcolor": PLT_TEXT,
                     "xtick.color": PLT_TEXT,
                     "ytick.color": PLT_TEXT,
                     "text.color": PLT_TEXT,
                     "grid.color": PLT_GRID,
                     "grid.linestyle": "-",
                     "grid.alpha": 0.3,
                     "legend.facecolor": PLT_BG,
                     "legend.edgecolor": PLT_GRID,
                     "legend.labelcolor": PLT_TEXT,
                     "font.size": 11,
                     })

# ══════════════════════════════════════════════════════════════════════════════
#  DATA HELPERS
# ══════════════════════════════════════════════════════════════════════════════
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)


def load_csv(filename):
    for path in [
        os.path.join(
            BASE, filename), os.path.join(
            BASE, "..", "outputs", filename), os.path.join(
                BASE, "data", filename), os.path.join(
                    BASE, "results", filename), os.path.join(
                        BASE, "..", "src", "results", filename), filename, ]:
        if os.path.exists(path):
            return pd.read_csv(path)
    return None


def load_json(filename):
    for path in [
        os.path.join(BASE, filename),
        os.path.join(BASE, "..", "outputs", filename),
        os.path.join(BASE, "..", "results", filename),
        os.path.join(BASE, "data", filename),
        os.path.join(BASE, "results", filename),
        filename,
    ]:
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
    radius_values = [r.get("coverage_radius_km")
                     for r in budgets if r.get("coverage_radius_km") is not None]
    max_radius = max(radius_values) if radius_values else coverage.get(
        "coverage_radius_km", 2.47)
    area_per_site = math.pi * (max_radius**2) if max_radius else None
    outdoor_pct = coverage.get(
        "outdoor_pct", coverage.get(
            "district_coverage_percent", 0.0))
    normalized = dict(raw)
    normalized["metrics"] = {
        "max_radius_km": round(
            float(max_radius),
            3) if max_radius else 2.47,
        "service_radius_km": round(
            float(max_radius),
            3) if max_radius else 2.47,
        "area_per_site_km2": round(
            float(area_per_site),
            3) if area_per_site else None,
        "district_coverage_percent": round(
            float(outdoor_pct),
            3),
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
        max_bps = float(out["signaling_load_bps"].max(
        )) if "signaling_load_bps" in out.columns and len(out) else 0.0
        out["processor_load_pct"] = 0.0 if max_bps <= 0 else (
            out["signaling_load_bps"] / max_bps * 100).round(1)
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
    if "worst_setup_delay_ms" in out.columns and "worst_call_setup_delay_ms" not in out.columns:
        out["worst_call_setup_delay_ms"] = out["worst_setup_delay_ms"]
    return out


def normalize_upgrade_plan_df(df):
    if df is None:
        return None
    out = df.copy()
    col_map = {
        "phase": "Phase",
        "trigger_year": "Trigger",
        "action": "Action",
        "utilisation": "Goal"}
    out = out.rename(
        columns={
            k: v for k,
            v in col_map.items() if k in out.columns})
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE IMPORTS
# ══════════════════════════════════════════════════════════════════════════════
TOPOLOGY_LOADED = False
TRAFFIC_MODS = False
SIGNALING_MOD = False
nodes_live, links_live = [], []
_topology_error = ""
G_obj = None
scenario_obj = None

try:
    from topology import build_topology, load_config, get_positions
    TOPOLOGY_LOADED = True
    try:
        _scenario_path = os.path.join(BASE, "..", "scenario.yaml")
        if not os.path.exists(_scenario_path):
            _scenario_path = os.path.join(BASE, "scenario.yaml")
        if os.path.exists(_scenario_path):
            scenario_obj = load_config(_scenario_path)
            G_obj = build_topology(scenario_obj)
            _NODE_COLORS = {
                "CR-1": "#DA7756",
                "CR-2": "#2563EB",
                "BS1": "#534AB7",
                "BS2": "#534AB7",
                "BS3": "#534AB7",
                "BS4": "#534AB7",
                "BS5": "#534AB7"}
            _NODE_ICONS = {
                "CR-1": "CR1",
                "CR-2": "CR2",
                "BS1": "BS",
                "BS2": "BS",
                "BS3": "BS",
                "BS4": "BS",
                "BS5": "BS"}
            # Build lat/lon lookup from scenario_obj (preferred) or fall back to km→deg conversion
            _sc_latlon = {}
            if scenario_obj and "sites" in scenario_obj:
                for _s in scenario_obj["sites"]:
                    if "lat" in _s and "lon" in _s:
                        _sc_latlon[_s["name"]] = (float(_s["lat"]), float(_s["lon"]), _s.get("location", _s.get("label", "?")), _s.get("label", _s.get("name", "?")))
            for _n in G_obj.nodes():
                _d = G_obj.nodes[_n]
                if _n in _sc_latlon:
                    _nlat, _nlon, _nloc, _nlabel = _sc_latlon[_n]
                else:
                    # fallback: convert km to degrees (centre = -22.55, 27.12 at 25,25 km)
                    import math as _math
                    _nlat = -22.55 + (_d.get("y", 25.0) - 25.0) / 111.0
                    _nlon = 27.12 + (_d.get("x", 25.0) - 25.0) / (111.0 * _math.cos(_math.radians(22.55)))
                    _nloc = _d.get("label", "?")
                    _nlabel = _d.get("label", "?")
                nodes_live.append(
                    {
                        "id": _n,
                        "name": f"{_n} - {_nlabel}",
                        "lat": _nlat,
                        "lon": _nlon,
                        "location": _nloc,
                        "color": _NODE_COLORS.get(
                            _n,
                            "#534AB7"),
                        "icon_label": _NODE_ICONS.get(
                            _n,
                            "BS"),
                        "type": "cr1" if _n == "CR-1" else "cr2" if _n == "CR-2" else "bs",
                        "role_label": "Primary Core Router" if _n == "CR-1" else "Backup Core Router" if _n == "CR-2" else "Base Station",
                                "tower_height_m": 68 if _n == "CR-1" else 66 if _n == "CR-2" else 42,
                                "x_km": _d.get(
                                    "x",
                                    0.0),
                        "y_km": _d.get(
                            "y",
                            0.0)})
            _LCOLORS = {
                "primary": "#DA7756",
                "backup": "#2563EB",
                "backbone": "#B45309",
                "microwave_13ghz": "#B45309",
                "lte_priority": "#9C9690",
                "microwave": "#DA7756"}
            _seen = set()
            for _u, _v, _d in G_obj.edges(data=True):
                _key = (min(_u, _v), max(_u, _v), _d.get("role", "primary"))
                if _key in _seen:
                    continue
                _seen.add(_key)
                _role = _d.get("role", "primary")
                if _role == "backup" and "backbone" in (
                        _d.get("link_type", "")):
                    _role = "backbone"
                if _d.get(
                        "link_type",
                        "") in (
                        "microwave_13ghz",
                        "lte_priority"):
                    _role = "backbone"
                links_live.append(
                    {
                        "source": _u, "target": _v, "role": _role, "color": _LCOLORS.get(
                            _d.get(
                                "link_type", _role), _LCOLORS.get(
                                _role, "#888")), "delay_ms": _d.get(
                            "delay_ms", 8.0), "capacity_mbps": _d.get(
                            "capacity_mbps", 100)})
    except Exception as _etopo:
        _topology_error = f"Inventory build failed: {_etopo}"
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
        evaluate_delay_kpis)
    from propagation import microwave_budget, rain_attenuation_db
    from backhaul import compute_distances, compute_link_budgets, generate_link_budget_table
    from forecasting import run_forecasting
    TRAFFIC_MODS = True
    if scenario_obj is None:
        try:
            scenario_obj = load_shared_scenario(_scenario_path)
        except Exception:
            pass
except Exception as _e2:
    pass

try:
    from routing import compute_all_routing_tables, inject_cr1_failure, check_reroute_after_failure, get_all_shortest_paths
except Exception:
    compute_all_routing_tables = inject_cr1_failure = check_reroute_after_failure = get_all_shortest_paths = None

try:
    from wireless import build_coverage_grid, coverage_statistics, validate_backhaul_capacity
    from propagation import site_link_budget_table
except Exception:
    build_coverage_grid = coverage_statistics = validate_backhaul_capacity = site_link_budget_table = None

try:
    import signalling as _sig_mod
    SIGNALING_MOD = True
except Exception:
    SIGNALING_MOD = False

# ─── Load CSVs ──────────────────────────────────────────────────────────
df_dim = load_csv("teletraffic_dimensioning_table.csv")
df_delay = load_csv("teletraffic_delay_kpis.csv")
df_stress = load_csv("stress_test_results.csv")
if df_stress is None:
    df_stress = load_csv("teletraffic_stress_sweep.csv")
if df_stress is None:
    df_stress = load_csv("stress_test_sweep.csv")
df_util = load_csv("forecasting_utilisation_annual.csv")
df_plan = normalize_upgrade_plan_df(load_csv("forecasting_upgrade_plan.csv"))
df_matrix = load_csv("traffic_matrix.csv")
df_load = load_csv("traffic_offered_load.csv")
df_backhaul = load_csv("backhaul_link_budget.csv")
if df_backhaul is None:
    df_backhaul = load_csv("wireless_link_budget.csv")
df_signal = load_csv("signaling_site_load.csv")
if df_signal is None:
    df_signal = load_csv("teletraffic_signaling_load.csv")
df_signal_summary = load_csv("signaling_summary.csv")
df_wireless_surface = load_csv("wireless_surface.csv")
if df_wireless_surface is None:
    df_wireless_surface = load_csv("wireless_coverage_grid.csv")
df_wireless_thresholds = load_csv("wireless_thresholds.csv")
wl = load_json("wireless_results.json")
df_qos_summary = load_csv("qos_summary.csv")
df_delay_samples = load_csv("delay_samples_summary.csv")


def _try_compute(scenario):
    global df_load, df_matrix, df_dim, df_delay, df_stress, df_signal, df_signal_summary, df_util, df_plan, df_backhaul, wl
    if not (TRAFFIC_MODS and scenario):
        return
    try:
        if df_load is None:
            df_load = compute_offered_load(scenario)
        if df_matrix is None:
            df_matrix = compute_traffic_matrix(scenario)
        if df_dim is None:
            df_dim = full_dimensioning_table(scenario)
        if df_delay is None:
            df_delay = evaluate_delay_kpis(scenario)
        if df_stress is None:
            df_stress = stress_sweep(scenario)
        if df_signal is None:
            df_signal = compute_signaling_load(scenario)
        if df_signal_summary is None:
            df_signal_summary = pd.DataFrame([signaling_summary(scenario)])
    except Exception:
        pass
    try:
        if df_util is None or df_plan is None:
            fc = run_forecasting(scenario)
            if df_util is None:
                df_util = fc["utilisation"]["annual_table"]
            if df_plan is None:
                raw_plan = pd.DataFrame(fc["recommendation"]["phased_plan"])
                df_plan = normalize_upgrade_plan_df(raw_plan)
    except Exception as fe:
        # Try running forecasting.py directly as fallback
        try:
            import subprocess
            fc_path = os.path.join(BASE, "forecasting.py")
            if os.path.exists(fc_path):
                subprocess.run([sys.executable, fc_path],
                               cwd=BASE, capture_output=True, timeout=30)
                df_util = load_csv("forecasting_utilisation_annual.csv")
                df_plan = normalize_upgrade_plan_df(
                    load_csv("forecasting_upgrade_plan.csv"))
        except Exception:
            pass
    try:
        if df_backhaul is None and G_obj is not None:
            pos = get_positions(G_obj)
            dists = {}
            for u, v in G_obj.edges():
                if u in pos and v in pos:
                    x1, y1 = pos[u]
                    x2, y2 = pos[v]
                    dists[(u, v)] = math.hypot(x2 - x1, y2 - y1)
            bh_res = compute_link_budgets(scenario, dists)
            df_backhaul = generate_link_budget_table(bh_res)
    except Exception:
        pass


_try_compute(scenario_obj)
wl = normalize_wireless_results(wl, scenario_obj)
df_delay = normalize_delay_df(df_delay)
df_stress = normalize_stress_df(df_stress)
df_signal = normalize_signal_df(df_signal)
df_signal_summary = normalize_signal_summary_df(df_signal_summary)

# ══════════════════════════════════════════════════════════════════════════════
#  DEFAULT INVENTORY
# ══════════════════════════════════════════════════════════════════════════════


def get_default_inventory():
    # Per-node shape/style defaults (lat/lon/label overridden from scenario_obj below)
    _node_meta = {
        "CR-1": {"color": "#DA7756", "icon_label": "CR1", "type": "cr1",
                 "role_label": "Primary Core Router",  "tower_height_m": 68,
                 "freq_ghz": 13.0, "tx_power_dbm": 30, "antenna_gain_dbi": 32, "beam_width_deg": 2,
                 "lat": -22.5500, "lon": 27.1200, "location": "Palapye",
                 "name": "CR-1 - Palapye Primary Hospital"},
        "CR-2": {"color": "#2563EB", "icon_label": "CR2", "type": "cr2",
                 "role_label": "Backup Core Router",   "tower_height_m": 66,
                 "freq_ghz": 13.0, "tx_power_dbm": 30, "antenna_gain_dbi": 32, "beam_width_deg": 2,
                 "lat": -22.5446, "lon": 27.1122, "location": "Palapye",
                 "name": "CR-2 - Palapye Sub-District Health Office"},
        "BS1":  {"color": "#534AB7", "icon_label": "BS", "type": "bs",
                 "role_label": "Base Station", "tower_height_m": 42,
                 "freq_ghz": 7.0, "tx_power_dbm": 43, "antenna_gain_dbi": 17, "beam_width_deg": 120,
                 "lat": -22.3968, "lon": 26.9639, "location": "Radisele",
                 "name": "BS1 - Radisele Clinic"},
        "BS2":  {"color": "#534AB7", "icon_label": "BS", "type": "bs",
                 "role_label": "Base Station", "tower_height_m": 40,
                 "freq_ghz": 7.0, "tx_power_dbm": 43, "antenna_gain_dbi": 17, "beam_width_deg": 120,
                 "lat": -22.4059, "lon": 27.2663, "location": "Lecheng",
                 "name": "BS2 - Lecheng Clinic"},
        "BS3":  {"color": "#534AB7", "icon_label": "BS", "type": "bs",
                 "role_label": "Base Station", "tower_height_m": 39,
                 "freq_ghz": 7.0, "tx_power_dbm": 43, "antenna_gain_dbi": 17, "beam_width_deg": 120,
                 "lat": -22.6671, "lon": 26.9737, "location": "Mogome",
                 "name": "BS3 - Mogome Clinic"},
        "BS4":  {"color": "#534AB7", "icon_label": "BS", "type": "bs",
                 "role_label": "Base Station", "tower_height_m": 41,
                 "freq_ghz": 7.0, "tx_power_dbm": 43, "antenna_gain_dbi": 17, "beam_width_deg": 120,
                 "lat": -22.7032, "lon": 27.1102, "location": "Maunatlala",
                 "name": "BS4 - Maunatlala Clinic"},
        "BS5":  {"color": "#534AB7", "icon_label": "BS", "type": "bs",
                 "role_label": "Base Station", "tower_height_m": 43,
                 "freq_ghz": 7.2, "tx_power_dbm": 43, "antenna_gain_dbi": 17, "beam_width_deg": 120,
                 "lat": -22.6941, "lon": 27.2956, "location": "Lerala",
                 "name": "BS5 - Lerala Clinic"},
    }
    # Override lat/lon/name/location from scenario_obj when available
    _sc = scenario_obj
    if _sc and "sites" in _sc:
        for _site in _sc["sites"]:
            _nid = _site.get("name")
            if _nid in _node_meta:
                if "lat" in _site:
                    _node_meta[_nid]["lat"] = float(_site["lat"])
                if "lon" in _site:
                    _node_meta[_nid]["lon"] = float(_site["lon"])
                if "location" in _site:
                    _node_meta[_nid]["location"] = str(_site["location"])
                if "label" in _site:
                    _node_meta[_nid]["name"] = f"{_nid} - {_site['label']}"
    nodes = {nid: {"id": nid, **meta} for nid, meta in _node_meta.items()}
    links = [
        {"source": "CR-1", "target": "BS1", "role": "primary", "color": "#DA7756", "delay_ms": 8.0, "capacity_mbps": 100},
        {"source": "CR-1", "target": "BS2", "role": "primary", "color": "#DA7756", "delay_ms": 8.0, "capacity_mbps": 100},
        {"source": "CR-1", "target": "BS3", "role": "primary", "color": "#DA7756", "delay_ms": 9.0, "capacity_mbps": 100},
        {"source": "CR-1", "target": "BS4", "role": "primary", "color": "#DA7756", "delay_ms": 7.0, "capacity_mbps": 100},
        {"source": "CR-1", "target": "BS5", "role": "primary", "color": "#DA7756", "delay_ms": 9.0, "capacity_mbps": 100},
        {"source": "CR-2", "target": "BS1", "role": "backup", "color": "#2563EB", "delay_ms": 13.0, "capacity_mbps": 100},
        {"source": "CR-2", "target": "BS2", "role": "backup", "color": "#2563EB", "delay_ms": 24.0, "capacity_mbps": 100},
        {"source": "CR-2", "target": "BS3", "role": "backup", "color": "#2563EB", "delay_ms": 20.0, "capacity_mbps": 100},
        {"source": "CR-2", "target": "BS4", "role": "backup", "color": "#2563EB", "delay_ms": 21.0, "capacity_mbps": 100},
        {"source": "CR-2", "target": "BS5", "role": "backup", "color": "#2563EB", "delay_ms": 26.0, "capacity_mbps": 100},
        {"source": "CR-1", "target": "CR-2", "role": "backbone", "color": "#B45309", "delay_ms": 0.5, "capacity_mbps": 500},
    ]
    return nodes, links


def get_inventory():
    if TOPOLOGY_LOADED and nodes_live:
        nodes = {n["id"]: {**n} for n in nodes_live}
        lcolors = {
            "primary": "#DA7756",
            "backup": "#2563EB",
            "backbone": "#B45309"}
        links = [{**l, "color": lcolors.get(l["role"], "#888")}
                 for l in links_live]
        if not links:
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


def clone(v):
    return json.loads(json.dumps(v))


for k, v in [
    ("nms_config", DEFAULT_CONFIG), ("nms_faults", DEFAULT_FAULTS),
    ("event_log", []), ("event_signatures", set()),
    ("config_revision", 1), ("selected_topology_node", "CR-1")
]:
    if k not in st.session_state:
        st.session_state[k] = clone(v) if isinstance(v, (dict, list)) else v

# ══════════════════════════════════════════════════════════════════════════════
#  SIMULATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════


def get_site_traffic_breakdown():
    breakdown = {}
    if df_matrix is not None and {
            "site",
            "voice_mbps",
            "video_mbps",
            "telemetry_mbps"}.issubset(
            df_matrix.columns):
        grouped = df_matrix.groupby(
            "site")[["voice_mbps", "video_mbps", "telemetry_mbps"]].sum()
        for site, row in grouped.iterrows():
            breakdown[site] = {
                "telemetry": float(
                    row["telemetry_mbps"]), "voice": float(
                    row["voice_mbps"]), "video": float(
                    row["video_mbps"])}
    elif df_load is not None and {"site", "service_class", "offered_load_erl"}.issubset(df_load.columns):
        factors = {"voice": 0.048, "video": 2.0, "telemetry": 0.02}
        for row in df_load.itertuples():
            breakdown.setdefault(
                row.site, {
                    "telemetry": 0.0, "voice": 0.0, "video": 0.0})
            breakdown[row.site][row.service_class] += float(
                row.offered_load_erl) * factors.get(row.service_class, 0.05)
    else:
        for s in ["BS1", "BS2", "BS3", "BS4", "BS5"]:
            breakdown[s] = {"telemetry": 0.05, "voice": 0.35, "video": 1.6}
    return breakdown


def simulate_network(nodes_in, links_in, config, faults, quick_failover):
    nodes = {k: dict(v) for k, v in nodes_in.items()}
    links = [dict(l) for l in links_in]
    breakdown = get_site_traffic_breakdown()
    alarms, flow_rows, recommendations = [], [], []
    failed_bs = set(faults.get("failed_bs", []))
    degradation = float(faults.get("backhaul_degradation_pct", 0)) / 100.0
    congestion_router = faults.get("router_congestion_router", "None")
    congestion_pct = float(faults.get("router_congestion_pct", 0)) / 100.0
    link_lookup = {}

    for nid, node in nodes.items():
        node["status"] = "offline" if nid in failed_bs else "online"
        node["load_ratio"] = 0.0
        node["traffic_mbps"] = 0.0

    def add_alarm(entity, name, sev, hint, details):
        alarms.append({"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                       "entity": entity,
                       "alarm": name,
                       "severity": sev,
                       "hint": hint,
                       "details": details})

    if quick_failover and "CR-1" in nodes:
        nodes["CR-1"]["status"] = "offline"
        add_alarm(
            "CR-1",
            "CORE ROUTER FAILURE",
            "Critical",
            "Primary core unavailable. Verify power, routing daemon, and microwave handoff.",
            "All primary services shifting to CR-2.")
    for bs in failed_bs:
        if bs in nodes:
            nodes[bs]["status"] = "offline"
            add_alarm(
                bs,
                "BASE STATION FAILURE",
                "Critical",
                "Check site power, radio chain, and antenna alignment.",
                f"{bs} unavailable. Clinic traffic isolated.")
    if degradation > 0:
        sev = "Major" if degradation >= 0.35 else "Minor"
        add_alarm(
            "Backhaul",
            "BACKHAUL DEGRADATION",
            sev,
            "Inspect microwave fade margin, weather impact, and spectrum interference.",
            f"Primary transport degraded by {degradation*100:.0f}%.")
    if congestion_router != "None" and congestion_pct > 0:
        sev = "Critical" if congestion_pct >= 0.7 else "Major"
        add_alarm(
            congestion_router,
            "ROUTER CONGESTION",
            sev,
            "Shift flows to alternate router or raise queue bandwidth.",
            f"{congestion_router} headroom reduced by {congestion_pct*100:.0f}%.")

    for link in links:
        factor = {
            "primary": config["primary_bw_alloc_pct"],
            "backup": config["backup_bw_alloc_pct"],
            "backbone": config["backbone_bw_alloc_pct"]}.get(
            link["role"],
            100) / 100.0
        eff = float(link["capacity_mbps"]) * factor
        if link["role"] in {"primary", "backbone"}:
            eff *= (1 - degradation)
        if congestion_router != "None" and congestion_router in {
                link["source"], link["target"]}:
            eff *= (1 - congestion_pct)
        if quick_failover and link["source"] == "CR-1" and link["role"] in {
                "primary", "backbone"}:
            eff = 0.0
        if link["source"] in failed_bs or link["target"] in failed_bs:
            eff = 0.0
        link["effective_capacity_mbps"] = round(max(eff, 0.0), 2)
        link["assigned_mbps"] = 0.0
        link["status"] = "down" if link["effective_capacity_mbps"] <= 0 else "up"
        link_lookup[(link["source"], link["target"], link["role"])] = link

    for bs_id in [n for n in nodes if n.startswith("BS")]:
        mix = breakdown.get(
            bs_id, {
                "telemetry": 0.0, "voice": 0.0, "video": 0.0})
        total_demand = round(sum(mix.values()), 3)
        primary = link_lookup.get(("CR-1", bs_id, "primary"))
        backup = link_lookup.get(("CR-2", bs_id, "backup"))
        if nodes[bs_id]["status"] == "offline":
            flow_rows.append({"site": bs_id,
                              "demand_mbps": total_demand,
                              "decision": "Unavailable",
                              "primary_mbps": 0.0,
                              "backup_mbps": 0.0,
                              "status": "Critical"})
            continue
        primary_cap = primary["effective_capacity_mbps"] if primary else 0.0
        backup_cap = backup["effective_capacity_mbps"] if backup else 0.0
        primary_load = (total_demand / primary_cap) if primary_cap else 99.0
        use_lb = (config["load_balancing"] and primary_cap > 0 and backup_cap > 0 and (
            config["routing_policy"] == "Load Balanced" or primary_load > 0.85 or quick_failover))
        ps, bs_share, decision, status = 0.0, 0.0, "Primary", "Normal"
        if primary_cap <= 0 and backup_cap > 0:
            bs_share = total_demand
            decision = "Rerouted to backup"
            status = "Major"
        elif use_lb:
            total_cap = primary_cap + backup_cap
            ps = round(total_demand * (primary_cap / total_cap), 3)
            bs_share = round(total_demand - ps, 3)
            decision = "Load balanced"
            status = "Minor"
        else:
            ps = total_demand
        if primary:
            primary["assigned_mbps"] += ps
        if backup:
            backup["assigned_mbps"] += bs_share
        nodes[bs_id]["traffic_mbps"] = total_demand
        flow_rows.append({"site": bs_id,
                          "demand_mbps": total_demand,
                          "decision": decision,
                          "primary_mbps": round(ps,
                                                3),
                          "backup_mbps": round(bs_share,
                                               3),
                          "status": status})

    backbone = link_lookup.get(("CR-1", "CR-2", "backbone"))
    if backbone:
        backbone["assigned_mbps"] = round(
            sum(r["backup_mbps"] for r in flow_rows), 3)

    for link in links:
        cap = link["effective_capacity_mbps"]
        demand = link["assigned_mbps"]
        link["load_ratio"] = round(
            (demand /
             cap) if cap else (
                1.0 if demand == 0 else 999.0),
            3)
        if cap <= 0 and demand > 0:
            link["status"] = "down"
            add_alarm(
                f"{link['source']}->{link['target']}",
                "TRANSPORT UNAVAILABLE",
                "Critical",
                "No carrying capacity remains.",
                f"Demand {demand:.2f} Mbps cannot be served.")
        elif cap > 0 and demand > cap:
            add_alarm(
                f"{link['source']}->{link['target']}",
                "CONGESTION ALERT",
                "Critical" if demand > cap * 1.15 else "Major",
                "Increase bandwidth, reroute traffic, or add channels.",
                f"Capacity {cap:.2f} < Demand {demand:.2f} Mbps.")
            link["status"] = "overloaded"
        elif cap > 0 and demand > cap * 0.85:
            add_alarm(
                f"{link['source']}->{link['target']}",
                "HIGH UTILISATION",
                "Major",
                "Segment nearing saturation.",
                f"Utilisation {link['load_ratio']*100:.1f}%.")
            link["status"] = "degraded"
        elif cap > 0 and demand > cap * 0.65:
            link["status"] = "warning"
        nodes[link["source"]]["load_ratio"] = max(
            nodes[link["source"]]["load_ratio"], min(link["load_ratio"], 1.5))
        nodes[link["target"]]["load_ratio"] = max(
            nodes[link["target"]]["load_ratio"], min(link["load_ratio"], 1.5))

    for row in flow_rows:
        if row["decision"] == "Rerouted to backup":
            recommendations.append(
                f"Keep reroute active for {row['site']} until primary path is restored.")
        if row["decision"] == "Load balanced":
            recommendations.append(
                f"Preserve dual-homing for {row['site']} — demand uses both routers.")
    if any(l["status"] == "overloaded" for l in links):
        recommendations.append(
            "Raise allocated capacity on overloaded links or increase microwave channel width.")
    if failed_bs:
        recommendations.append(
            "Deploy field maintenance to failed base stations before restoring routing policies.")
    if degradation >= 0.35:
        recommendations.append(
            "Severe backhaul degradation — conduct spectrum and antenna alignment review immediately.")
    recommendations = list(dict.fromkeys(recommendations))
    return {
        "nodes": nodes,
        "links": links,
        "alarms": alarms,
        "flow_rows": flow_rows,
        "recommendations": recommendations,
        "traffic_breakdown": breakdown}


def severity_badge(s):
    if s == "Critical":
        return '<span class="badge-fail">Critical</span>'
    if s == "Major":
        return '<span class="badge-warn">Major</span>'
    return '<span class="badge-info">Minor</span>'


def append_event(etype, sev, msg, details=""):
    sig = f"{etype}::{msg}"
    if sig in st.session_state.event_signatures:
        return
    st.session_state.event_signatures.add(sig)
    st.session_state.event_log.append({"timestamp": datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"), "type": etype, "severity": sev, "message": msg, "details": details})


def status_color(item, default):
    if item.get("status") == "overloaded":
        return PLT_RED
    if item.get("status") in {"degraded", "warning"}:
        return PLT_AMBER
    if item.get("status") in {"down", "offline"}:
        return "#9C9690"
    return default


def map_tile_config(style_name):
    tiles = {
        "OpenStreetMap": {
            "tiles": "OpenStreetMap",
            "attr": "© OpenStreetMap contributors"},
        "CartoDB Light": {
            "tiles": "CartoDB positron",
            "attr": "CartoDB"},
        "Live Satellite": {
            "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            "attr": "Esri World Imagery"},
        "Satellite + Labels": {
            "tiles": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            "attr": "Google Hybrid"},
    }
    return tiles[style_name]


# ══════════════════════════════════════════════════════════════════════════════
#  3D ANTENNA HTML MARKER — realistic tower visual for Leaflet DivIcon
# ══════════════════════════════════════════════════════════════════════════════
_ANTENNA_CSS_INJECTED = False

ANTENNA_CSS = """
<style>
.ant-wrap{position:relative;display:flex;flex-direction:column;align-items:center;width:54px;transform:translate(-50%,-100%)}
.ant-shadow{width:22px;height:6px;background:rgba(0,0,0,.22);border-radius:50%;filter:blur(2px);margin-bottom:0}
.ant-base-plate{width:18px;height:4px;background:var(--tc);border-radius:3px 3px 1px 1px;opacity:.9}
.ant-leg-l,.ant-leg-r{position:absolute;bottom:4px;width:3px;background:linear-gradient(180deg,#ccc 0%,var(--tc) 100%);border-radius:2px;transform-origin:bottom center}
.ant-leg-l{left:50%;margin-left:-9px;height:var(--lh);transform:rotate(-14deg)}
.ant-leg-r{left:50%;margin-left:6px;height:var(--lh);transform:rotate(14deg)}
.ant-mast{width:5px;background:linear-gradient(180deg,#f0f0f0 0%,var(--tc) 40%,#444 100%);border-radius:4px;height:var(--mh);margin-bottom:0;position:relative}
.ant-dish{width:var(--dw);height:var(--dh);border:3px solid var(--tc);border-radius:50% 50% 0 0;margin-bottom:1px;background:linear-gradient(180deg,rgba(255,255,255,.18) 0%,rgba(255,255,255,.04) 100%);position:relative}
.ant-dish::after{content:'';position:absolute;left:50%;top:100%;transform:translateX(-50%);width:2px;height:6px;background:var(--tc)}
.ant-rod{width:3px;height:12px;background:linear-gradient(180deg,#fff 0%,var(--tc) 100%);border-radius:3px;margin-bottom:1px}
.ant-beacon{width:8px;height:8px;border-radius:50%;background:var(--bc);animation:blink 2s ease-in-out infinite;margin-bottom:1px}
.ant-label{background:rgba(255,255,255,.95);border:1px solid var(--tc);border-radius:4px;padding:1px 6px;font-size:10px;font-weight:700;color:var(--tc);font-family:monospace;white-space:nowrap;margin-bottom:2px}
@keyframes blink{0%,100%{opacity:1;box-shadow:0 0 4px var(--bc)}50%{opacity:.3;box-shadow:none}}
.ant-sector{position:absolute;top:-30px;left:50%;transform:translateX(-50%);width:80px;height:40px;pointer-events:none}
.ant-sector-beam{position:absolute;bottom:0;left:50%;transform-origin:bottom center;width:0;height:0;border-left:40px solid transparent;border-right:40px solid transparent;border-bottom:38px solid var(--sc);opacity:.18;margin-left:-40px}
</style>
"""


def make_antenna_marker(node_id, node, offline=False):
    """Generate a realistic 3D-style antenna DivIcon HTML for a Folium marker."""
    color = "#9C9690" if offline else node["color"]
    ntype = node.get("type", "bs")
    tower_h = int(node.get("tower_height_m", 42))
    mast_h = max(38, min(80, int(tower_h * 1.1)))
    leg_h = max(20, min(50, int(tower_h * 0.6)))
    dish_w = 24 if ntype in ("cr1", "cr2") else 16
    dish_h = 14 if ntype in ("cr1", "cr2") else 10
    beacon_color = "#FF4444" if offline else (
        "#FFD700" if ntype in ("cr1", "cr2") else "#00FF88")
    sector_color = color if not offline else "#9C9690"

    sector_html = ""
    if ntype == "bs" and not offline:
        sector_html = f"""
        <div class="ant-sector">
          <div class="ant-sector-beam" style="--sc:{sector_color};transform:rotate(-60deg) translateX(-50%);transform-origin:bottom center;margin-left:-40px"></div>
          <div class="ant-sector-beam" style="--sc:{sector_color};transform:rotate(0deg) translateX(-50%);transform-origin:bottom center;margin-left:-40px"></div>
          <div class="ant-sector-beam" style="--sc:{sector_color};transform:rotate(60deg) translateX(-50%);transform-origin:bottom center;margin-left:-40px"></div>
        </div>"""

    html = f"""
    <div class="ant-wrap" style="--tc:{color};--mh:{mast_h}px;--lh:{leg_h}px;--dw:{dish_w}px;--dh:{dish_h}px;--bc:{beacon_color}">
      {sector_html}
      <div class="ant-label">{node_id}</div>
      <div class="ant-beacon"></div>
      <div class="ant-rod"></div>
      <div class="ant-dish"></div>
      <div style="position:relative;width:{leg_h+6}px;height:{mast_h}px;display:flex;justify-content:center">
        <div class="ant-mast" style="height:{mast_h}px"></div>
        <div class="ant-leg-l" style="--lh:{leg_h}px"></div>
        <div class="ant-leg-r" style="--lh:{leg_h}px"></div>
      </div>
      <div class="ant-base-plate"></div>
      <div class="ant-shadow"></div>
    </div>"""
    return html


def link_flow_specs(link, src, tgt):
    role = link["role"]
    color = link["color"]
    weight = 4 if role == "backbone" else 3
    opacity = 0.88 if role == "primary" else (
        0.65 if role == "backup" else 0.78)
    dash = None if role == "backbone" else "5,7"
    pulse_color = "#F59E0B" if role == "backbone" else "#FFFFFF"
    speed = 900 if role == "backbone" else (
        1300 if role == "primary" else 1800)
    if failure_mode:
        if role == "primary":
            color, weight, opacity, dash = "#9C9690", 2, 0.28, "5,7"
        elif role == "backbone":
            color, weight, opacity, dash = "#9C9690", 2, 0.22, "4,8"
    if link.get("status") == "overloaded":
        color, weight, opacity, dash, pulse_color, speed = PLT_RED, 5, 0.95, "3,5", "#FFE1D9", 650
    elif link.get("status") in {"degraded", "warning"}:
        color, weight, opacity, pulse_color, speed = PLT_AMBER, max(
            weight, 4), 0.92, "#FFF0C2", 850
    elif link.get("status") == "down":
        color, weight, opacity, dash, pulse_color, speed = "#9C9690", 2, 0.3, "2,8", "#D6D3D1", 2200
    load_ratio = float(link.get("load_ratio", 0.0))
    assigned = float(link.get("assigned_mbps", 0.0))
    capacity = float(
        link.get(
            "effective_capacity_mbps",
            link.get(
                "capacity_mbps",
                0.0)))
    popup_html = f"<b>{link['source']} → {link['target']}</b><br>Role: {role.upper()}<br>Delay: {link['delay_ms']} ms<br>Traffic: {assigned:.2f} / {capacity:.2f} Mbps<br>Utilisation: {load_ratio*100:.1f}%<br>Status: {str(link.get('status','up')).upper()}"
    tooltip = f"{link['source']} → {link['target']} | {role} | {load_ratio*100:.1f}% load"
    return {"locations": [[src["lat"],
                           src["lon"]],
                          [tgt["lat"],
                           tgt["lon"]]],
            "color": color,
            "weight": weight,
            "opacity": opacity,
            "dash": dash,
            "pulse_color": pulse_color,
            "speed": speed,
            "popup_html": popup_html,
            "tooltip": tooltip}


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 📡 Network Management")
    st.markdown("**District Telehealth & Emergency Network**")
    st.markdown("Palapye / Serowe, Botswana")
    st.divider()
    st.markdown("### Navigation")
    section = st.radio("Navigation",
                       ["Overview",
                        "Network",
                        "Radio & Access",
                        "Core Network",
                        "Traffic",
                        "Planning",
                        "Fault & Stress",
                        "Logs"],
                       label_visibility="collapsed")

    with st.expander("Map Options", expanded=True):
        map_tile = st.selectbox("Map style",
                                ["OpenStreetMap",
                                 "CartoDB Light",
                                 "Live Satellite",
                                 "Satellite + Labels"],
                                index=0)
        show_primary = st.checkbox("Primary links", value=True)
        show_backup = st.checkbox("Backup links", value=True)
        show_backbone = st.checkbox("Backbone link", value=True)
        show_coverage = st.checkbox("Coverage rings", value=True)
        show_labels = st.checkbox("Site labels", value=True)

    with st.expander("Failure Simulation", expanded=section == "Fault & Stress"):
        failure_mode = st.checkbox("Simulate CR-1 failure", value=False)

    if failure_mode:
        st.markdown(
            '<span class="badge-fail">CR-1 OFFLINE - rerouting via CR-2</span>',
            unsafe_allow_html=True)
    else:
        st.markdown(
            '<span class="badge-pass">All nodes operational</span>',
            unsafe_allow_html=True)

    if st.button("Run All Modules"):
        import subprocess
        ran = []
        all_scripts = [
            "traffic.py",
            "teletraffic.py",
            "qos.py",
            "backhaul.py",
            "wireless.py",
            "signalling.py",
            "stress test.py",
            "forecasting.py",
            "routing.py",
            "propagation.py"]
        for script in all_scripts:
            p = os.path.join(BASE, script)
            if os.path.exists(p):
                subprocess.run([sys.executable, p], cwd=BASE,
                               capture_output=True, timeout=60)
                ran.append(script)
        st.success(f"Ran: {', '.join(ran) if ran else 'no scripts found'}.")

    st.divider()
    st.caption("BIUST · Group 1 · TELE 527")
    st.caption("Student 4: Tsotlhe Seiphepi (Signaling & Routing Lead)")

    if TOPOLOGY_LOADED:
        st.markdown(
            '<span class="badge-pass">topology.py ✓</span>',
            unsafe_allow_html=True)
    else:
        st.markdown(
            '<span class="badge-warn">topology.py not found</span>',
            unsafe_allow_html=True)
        if _topology_error:
            st.caption(f"⚠ {_topology_error}")
    if TRAFFIC_MODS:
        st.markdown(
            '<span class="badge-pass">traffic modules ✓</span>',
            unsafe_allow_html=True)
    else:
        st.markdown(
            '<span class="badge-warn">traffic modules not loaded</span>',
            unsafe_allow_html=True)

# ─── Build simulation ───────────────────────────────────────────────────
BASE_NODES, BASE_LINKS = get_inventory()
SIMULATION = simulate_network(
    BASE_NODES,
    BASE_LINKS,
    st.session_state.nms_config,
    st.session_state.nms_faults,
    failure_mode)
if df_load is not None and "baseline_calls_loaded" not in st.session_state:
    st.session_state.baseline_calls_loaded = True
    append_event(
        "Traffic",
        "Info",
        f"Loaded offered traffic for {df_load['site'].nunique()} sites.",
        "Baseline call attempt profile imported.")
for alarm in SIMULATION["alarms"]:
    append_event(
        "Alarm",
        alarm["severity"],
        f"{alarm['entity']}: {alarm['alarm']}",
        alarm["details"])
for row in SIMULATION["flow_rows"]:
    if row["decision"] != "Primary":
        append_event(
            "Routing",
            row["status"],
            f"{row['site']} traffic {row['decision'].lower()}",
            "")

alarms_df = pd.DataFrame(SIMULATION["alarms"])
flow_df = pd.DataFrame(SIMULATION["flow_rows"])
routing_tables, paths, reroute_check = {}, {}, None
backhaul_results_computed, backhaul_df_computed = [], None

if TRAFFIC_MODS and G_obj is not None and compute_all_routing_tables is not None:
    try:
        routing_tables = compute_all_routing_tables(G_obj)
        paths = get_all_shortest_paths(G_obj)
        if failure_mode:
            G_failed, _ = inject_cr1_failure(G_obj)
            reroute_check = check_reroute_after_failure(G_obj, G_failed)
    except Exception:
        pass
    try:
        if scenario_obj and df_backhaul is None:
            pos = get_positions(G_obj)
            distances = {}
            for u, v in G_obj.edges():
                if u in pos and v in pos:
                    x1, y1 = pos[u]
                    x2, y2 = pos[v]
                    distances[(u, v)] = math.hypot(x2 - x1, y2 - y1)
            backhaul_results_computed = compute_link_budgets(
                scenario_obj, distances)
            backhaul_df_computed = generate_link_budget_table(
                backhaul_results_computed)
    except Exception:
        pass

failure_badge = '<span class="badge-fail">CR-1 FAILURE ACTIVE</span>' if failure_mode else '<span class="badge-pass">ALL SYSTEMS NOMINAL</span>'
st.markdown(
    f'<div class="title-bar"><h1>District Telehealth &amp; Emergency Communication NMS</h1><p>Palapye / Serowe District, Botswana &nbsp;|&nbsp; Dual-homed Star Topology &nbsp;|&nbsp; 7 GHz Microwave &nbsp;|&nbsp; 13 GHz Backbone &nbsp;|&nbsp; 5 Clinic Sites &nbsp;|&nbsp; {failure_badge}</p></div>',
    unsafe_allow_html=True)

worst_blocking = (
    f"{df_dim[df_dim['site'].str.contains('BS',na=False)]['achieved_blocking'].max()*100:.2f}%" if df_dim is not None and 'achieved_blocking' in df_dim.columns else "0.62%")
coverage_r = f"{wl['metrics']['max_radius_km']} km" if wl else "2.47 km"
coverage_pct = f"{wl['metrics']['district_coverage_percent']}%" if wl else "N/A"
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.metric("Sites", "5")
with c2:
    st.metric("Core Routers", "2")
with c3:
    st.metric("Voice Blocking", worst_blocking, help="Target ≤ 2%")
with c4:
    st.metric("Coverage Radius", coverage_r)
with c5:
    st.metric("District Coverage", coverage_pct)
with c6:
    st.metric("Active Alarms", len(SIMULATION["alarms"]))
st.divider()

# ══════════════════════════════════════════════════════════════════════════════
#  PAGES
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE ROUTING  — maps 8 new sidebar sections to internal content keys
# ══════════════════════════════════════════════════════════════════════════════
_eff_section = section  # default: simple sections map to themselves

if section == "Overview":
    st.markdown('<div class="section-header">Network Overview — KPIs & Status</div>', unsafe_allow_html=True)
    _ov_nodes = SIMULATION["nodes"]
    _ov_online = sum(1 for n in _ov_nodes.values() if n.get("status") != "offline")
    _ov_offline = len(_ov_nodes) - _ov_online
    _ov_util = max((l["load_ratio"] for l in SIMULATION["links"] if l["effective_capacity_mbps"] > 0), default=0)
    _ov_rerouted = int((flow_df["decision"] == "Rerouted to backup").sum()) if not flow_df.empty else 0
    _ov_kpi = False
    if df_signal_summary is not None:
        _ov_s = df_signal_summary.iloc[0]
        _ov_kpi = bool(_ov_s.get("network_kpi_met", _ov_s.get("all_kpis_met", False)))
    _ov_c1, _ov_c2, _ov_c3, _ov_c4, _ov_c5 = st.columns(5)
    with _ov_c1: st.metric("Nodes Online", _ov_online)
    with _ov_c2: st.metric("Nodes Offline", _ov_offline)
    with _ov_c3: st.metric("Max Link Util.", f"{_ov_util*100:.1f}%")
    with _ov_c4: st.metric("Rerouted Sites", _ov_rerouted)
    with _ov_c5: st.metric("Signaling KPIs", "✅ PASS" if _ov_kpi else "❌ FAIL")
    st.divider()
    _ov_ca, _ov_cb = st.columns(2)
    with _ov_ca:
        st.markdown("**Node Status**")
        for _ov_k, _ov_n in _ov_nodes.items():
            _ov_is_f = _ov_n.get("status") == "offline"
            _ov_badge = '<span class="badge-fail">OFFLINE</span>' if _ov_is_f else '<span class="badge-pass">ONLINE</span>'
            _ov_c = _ov_n["color"]
            st.markdown(f'<div class="metric-card" style="border-left:3px solid {_ov_c}"><div class="label">{_ov_k} &nbsp; {_ov_badge}</div><div class="value" style="font-size:13px;color:{_ov_c}">{_ov_n["location"]}</div><div class="sub">{_ov_n.get("role_label","Base Station")} · Load: {_ov_n.get("load_ratio",0)*100:.1f}%</div></div>', unsafe_allow_html=True)
    with _ov_cb:
        st.markdown("**Link Utilisation**")
        for _ov_lnk in SIMULATION["links"]:
            _ov_pct = _ov_lnk.get("load_ratio", 0) * 100
            _ov_lc = PLT_RED if _ov_pct > 80 else (PLT_AMBER if _ov_pct > 60 else PLT_GREEN)
            st.markdown(f'<div class="metric-card"><div class="label">{_ov_lnk["source"]} → {_ov_lnk["target"]} <span style="font-size:10px;color:{PLT_MUTED}">({_ov_lnk.get("role","primary")})</span></div><div style="background:{PLT_GRID};border-radius:3px;height:6px;margin:6px 0"><div style="width:{min(_ov_pct,100):.0f}%;background:{_ov_lc};height:6px;border-radius:3px"></div></div><div class="sub">{_ov_pct:.1f}% of {_ov_lnk.get("effective_capacity_mbps",_ov_lnk.get("capacity_mbps","-"))} Mbps</div></div>', unsafe_allow_html=True)

elif section == "Network":
    _net_sub = st.radio("", ["🗺 Map", "🔗 Topology"], horizontal=True, label_visibility="collapsed")
    _eff_section = {"🗺 Map": "Network Map", "🔗 Topology": "Interactive Topology"}[_net_sub]

elif section == "Radio & Access":
    _ra_sub = st.radio("", ["📡 RF Coverage", "🏗 Antennas", "📶 Wireless Analysis"], horizontal=True, label_visibility="collapsed")
    _eff_section = {"📡 RF Coverage": "RF_Coverage", "🏗 Antennas": "Antennas", "📶 Wireless Analysis": "Backhaul"}[_ra_sub]

elif section == "Core Network":
    _cn_sub = st.radio("", ["🔀 Routing", "📞 Signaling", "📱 Call Handling"], horizontal=True, label_visibility="collapsed")
    _eff_section = {"🔀 Routing": "Routing & Signaling", "📞 Signaling": "Signaling Details", "📱 Call Handling": "Call Termination"}[_cn_sub]

elif section == "Traffic":
    _tr_sub = st.radio("", ["📊 Offered Load", "⏱ Delay", "📈 Summary"], horizontal=True, label_visibility="collapsed")
    _eff_section = {"📊 Offered Load": "Offered_Load", "⏱ Delay": "Delay_KPIs", "📈 Summary": "Traffic_Summary"}[_tr_sub]

elif section == "Fault & Stress":
    _fs_sub = st.radio("", [" Failures & Stress", " QoS"], horizontal=True, label_visibility="collapsed")
    _eff_section = {" Failures & Stress": "Fault & Stress", " QoS": "QoS"}[_fs_sub]

elif section == "Planning":
    _pl_sub = st.radio("", ["📈 Forecast", "💰 Billing & Upgrade"], horizontal=True, label_visibility="collapsed")
    _eff_section = {"📈 Forecast": "Forecast", "💰 Billing & Upgrade": "Billing Analytics"}[_pl_sub]

# ─── NETWORK MAP ────────────────────────────────────────────────────────
if _eff_section == "Network Map":
    map_col, info_col = st.columns([3, 1], gap="medium")
    with map_col:
        st.markdown(
            '<div class="section-header">Live Network Map — Serowe / Palapye District (OpenStreetMap)</div>',
            unsafe_allow_html=True)
        # Inject antenna CSS once into the page
        st.markdown(ANTENNA_CSS, unsafe_allow_html=True)
        NODES, LINKS = SIMULATION["nodes"], SIMULATION["links"]
        lats = [n["lat"] for n in NODES.values()]
        lons = [n["lon"] for n in NODES.values()]
        clat, clon = sum(lats) / len(lats), sum(lons) / len(lons)
        tc = map_tile_config(map_tile)
        # Build map — default OSM for real street context
        if tc["tiles"] == "OpenStreetMap":
            m = folium.Map(
                location=[
                    clat,
                    clon],
                zoom_start=10,
                tiles="OpenStreetMap",
                control_scale=True)
        elif "positron" in str(tc["tiles"]):
            m = folium.Map(
                location=[
                    clat,
                    clon],
                zoom_start=10,
                tiles="CartoDB positron",
                control_scale=True)
        else:
            m = folium.Map(
                location=[
                    clat,
                    clon],
                zoom_start=10,
                tiles=tc["tiles"],
                attr=tc["attr"],
                control_scale=True)

        coverage_fg = folium.FeatureGroup(
            name="Coverage Rings", show=show_coverage)
        links_fg = folium.FeatureGroup(name="Microwave Paths", show=True)
        towers_fg = folium.FeatureGroup(name="Antenna Towers", show=True)

        # Draw links
        for lnk in LINKS:
            role = lnk["role"]
            if role == "primary" and not show_primary:
                continue
            if role == "backup" and not show_backup:
                continue
            if role == "backbone" and not show_backbone:
                continue
            src, tgt = NODES.get(lnk["source"]), NODES.get(lnk["target"])
            if not src or not tgt:
                continue
            flow = link_flow_specs(lnk, src, tgt)
            ll = folium.PolyLine(
                locations=flow["locations"],
                color=flow["color"],
                weight=flow["weight"],
                opacity=flow["opacity"],
                dash_array=flow["dash"],
                popup=folium.Popup(
                    flow["popup_html"],
                    max_width=240),
                tooltip=flow["tooltip"])
            ll.add_to(links_fg)
            if role != "backbone":
                PolyLineTextPath(
                    ll,
                    "   >>>   ",
                    repeat=True,
                    offset=10,
                    attributes={
                        "fill": flow["color"],
                        "font-weight": "700",
                        "font-size": "11"}).add_to(links_fg)
            AntPath(
                locations=flow["locations"],
                color=flow["color"],
                pulse_color=flow["pulse_color"],
                weight=max(
                    flow["weight"] + 1,
                    4),
                opacity=min(
                    flow["opacity"] + 0.08,
                    1.0),
                dash_array=[
                    12,
                    18],
                delay=flow["speed"],
                paused=False,
                reverse=role == "backup",
                tooltip=flow["tooltip"]).add_to(links_fg)

        # Draw coverage rings
        if show_coverage:
            r_m = int((wl["metrics"]["max_radius_km"] if wl else 2.47) * 1000)
            for k, node in NODES.items():
                if node["type"] == "bs":
                    folium.Circle(
                        location=[
                            node["lat"],
                            node["lon"]],
                        radius=r_m,
                        color=PLT_PURPLE,
                        fill=True,
                        fill_color=PLT_PURPLE,
                        fill_opacity=0.06,
                        weight=1.5,
                        opacity=0.4,
                        tooltip=f"{k} coverage: {r_m/1000:.2f} km").add_to(coverage_fg)

        # Draw 3D antenna markers on real map locations
        for k, node in NODES.items():
            is_offline = node.get("status") == "offline"
            ant_html = make_antenna_marker(k, node, offline=is_offline)
            icon_h = int(node.get("tower_height_m", 42)) * 2 + 60
            folium.Marker(
                location=[
                    node["lat"],
                    node["lon"]],
                icon=folium.DivIcon(
                    html=ant_html,
                    icon_size=(
                        54,
                        icon_h),
                    icon_anchor=(
                        27,
                        icon_h)),
                popup=folium.Popup(
                    f"<b>{node['name']}</b><br>Type: {node.get('role_label','Base Station')}<br>Height: {node.get('tower_height_m','-')} m<br>Status: {'OFFLINE' if is_offline else 'Operational'}<br>Load: {node.get('load_ratio',0)*100:.1f}%",
                    max_width=260),
                tooltip=f"{node['name']} ({'OFFLINE' if is_offline else 'OK'})").add_to(towers_fg)

        coverage_fg.add_to(m)
        links_fg.add_to(m)
        towers_fg.add_to(m)
        folium.LayerControl(collapsed=False).add_to(m)
        m.fit_bounds([[min(lats), min(lons)], [
                     max(lats), max(lons)]], padding=(30, 30))
        st_folium(m, width=None, height=680, returned_objects=[])

    with info_col:
        st.markdown(
            '<div class="section-header">Node Details</div>',
            unsafe_allow_html=True)
        for k, node in SIMULATION["nodes"].items():
            is_f = node.get("status") == "offline"
            badge = '<span class="badge-fail">OFFLINE</span>' if is_f else '<span class="badge-pass">ONLINE</span>'
            c = node["color"]
            st.markdown(
                f'<div class="metric-card" style="border-left:3px solid {c}"><div class="label">{k} &nbsp; {badge}</div><div class="value" style="font-size:13px;color:{c}">{node["location"]}</div><div class="sub">{node.get("role_label","Base Station")}</div><div class="sub">{node.get("tower_height_m","-")} m tower</div><div class="sub">Load: {node.get("load_ratio",0)*100:.1f}%</div></div>',
                unsafe_allow_html=True)

# ─── INTERACTIVE TOPOLOGY (3D) ──────────────────────────────────────────
elif _eff_section == "Interactive Topology":
    st.markdown(
        '<div class="section-header">3D Interactive Topology Visualization</div>',
        unsafe_allow_html=True)
    if not PLOTLY_OK:
        st.warning("Plotly not available.")
    else:
        fig = go.Figure()
        for link in SIMULATION["links"]:
            src = SIMULATION["nodes"].get(link["source"])
            tgt = SIMULATION["nodes"].get(link["target"])
            if not src or not tgt:
                continue
            color = status_color(link, link["color"])
            fig.add_trace(go.Scatter3d(x=[src["lon"], tgt["lon"]], y=[src["lat"], tgt["lat"]], z=[
                          0, 0], mode="lines", line={"color": color, "width": 3}, hoverinfo="skip", showlegend=False))
        for nid, node in SIMULATION["nodes"].items():
            color = status_color(node, node["color"])
            h = f"{nid}<br>{node['location']}<br>Status:{node.get('status','online')}<br>Load:{node.get('load_ratio',0)*100:.1f}%<br>Tower:{node.get('tower_height_m','-')}m"
            fig.add_trace(go.Scatter3d(x=[node["lon"]],
                                       y=[node["lat"]],
                                       z=[float(node.get("tower_height_m",
                                                         42))],
                                       mode="markers+text",
                                       text=[nid],
                                       textposition="top center",
                                       textfont={"color": PLT_TEXT,
                          "size": 11},
                                       marker={"size": 8,
                                               "color": color,
                                               "line": {"width": 1.5,
                                                        "color": "#ffffff"}},
                                       hoverinfo="text",
                                       hovertext=[h],
                                       showlegend=False))
        fig.update_layout(
            height=620, margin={
                "l": 0, "r": 0, "t": 20, "b": 0}, paper_bgcolor=PLT_BG, plot_bgcolor=PLT_AX, scene={
                "bgcolor": PLT_AX, "xaxis": {
                    "visible": False}, "yaxis": {
                    "visible": False}, "zaxis": {
                        "title": "Height (m)", "color": PLT_TEXT}, "camera": {
                            "eye": {
                                "x": 1.75, "y": 1.55, "z": 1.05}}})
        st.plotly_chart(
            fig, use_container_width=True, config={
                "displaylogo": False})

# ─── RF & TRAFFIC ANALYSIS (unified: Traffic + Wireless + Backhaul) ─────
elif _eff_section in ("Offered_Load", "RF_Coverage", "Backhaul", "Traffic_Summary"):
    if _eff_section == "Offered_Load":
        st.markdown(
            '<div class="section-header">Offered Load — traffic_offered_load.csv</div>',
            unsafe_allow_html=True)
        if df_load is not None:
            tv = df_load[df_load["service_class"] ==
                         "voice"]["offered_load_erl"].sum()
            tvid = df_load[df_load["service_class"]
                           == "video"]["offered_load_erl"].sum()
            tt = df_load[df_load["service_class"] ==
                         "telemetry"]["offered_load_erl"].sum()
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Total voice load", f"{tv:.2f} Erl")
            with c2:
                st.metric("Total video load", f"{tvid:.2f} Erl")
            with c3:
                st.metric("Total telemetry", f"{tt:.2f} Erl")
            with c4:
                st.metric("Sites", df_load["site"].nunique())
            dscp_map = {
                "voice": '<span class="badge-pass">AF31</span>',
                "video": '<span class="badge-warn">AF21</span>',
                "telemetry": '<span class="badge-info">EF</span>'}
            rows = "".join(
                f"<tr><td><b style='color:{PLT_PURPLE}'>{r.site}</b></td><td>{r.service_class.title()}</td><td>{dscp_map.get(r.service_class,'')}</td><td>{r.arrival_rate_per_hour}</td><td>{r.holding_time_s} s</td><td><b>{r.offered_load_erl:.4f}</b></td></tr>" for r in df_load.itertuples())
            st.markdown(
                f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Site</th><th>Class</th><th>DSCP</th><th>Arrivals/hr</th><th>Hold time</th><th>Offered (Erl)</th></tr></thead><tbody>{rows}</tbody></table></div>',
                unsafe_allow_html=True)
            if PLOTLY_OK:
                pivot_load = df_load.groupby(["site", "service_class"])[
                    "offered_load_erl"].sum().reset_index()
                fig_l = px.bar(
                    pivot_load,
                    x="site",
                    y="offered_load_erl",
                    color="service_class",
                    barmode="stack",
                    color_discrete_map={
                        "voice": PLT_BLUE,
                        "video": PLT_PURPLE,
                        "telemetry": PLT_ACCENT})
                fig_l.update_layout(
                    height=280,
                    paper_bgcolor=PLT_BG,
                    plot_bgcolor=PLT_AX,
                    font={
                        "color": PLT_TEXT},
                    xaxis_title="Base Station",
                    yaxis_title="Erlang",
                    legend={
                        "orientation": "h",
                        "y": -0.25},
                    margin={
                        "l": 0,
                        "r": 0,
                        "t": 10,
                        "b": 0})
                st.plotly_chart(fig_l, use_container_width=True)
        else:
            st.warning("Traffic offered-load data is currently unavailable.")

        st.markdown(
            '<div class="section-header">Traffic Matrix — traffic_matrix.csv</div>',
            unsafe_allow_html=True)
        if df_matrix is not None:
            rows = ""
            for r in df_matrix.itertuples():
                pct = r.link_utilisation * 100
                bw = min(100, int(pct * 5))
                rows += (f"<tr><td><b style='color:{PLT_PURPLE}'>{r.site}</b></td><td>{r.destination}</td><td>{r.voice_mbps:.3f}</td><td>{r.video_mbps:.3f}</td><td>{r.telemetry_mbps:.6f}</td><td><b>{r.total_mbps:.4f}</b></td><td>{r.link_capacity_mbps:.0f}</td><td><div style='background:{PLT_GRID};border-radius:3px;height:6px'><div style='width:{bw}%;background:{PLT_ACCENT};height:6px;border-radius:3px'></div></div>&nbsp;{pct:.2f}%</td></tr>")
            st.markdown(
                f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Site</th><th>Dest</th><th>Voice</th><th>Video</th><th>Telemetry</th><th>Total</th><th>Capacity</th><th>Utilisation</th></tr></thead><tbody>{rows}</tbody></table></div>',
                unsafe_allow_html=True)
            st.markdown(
                '<div class="info-box"><b>Formula:</b> A = λ × h / 3600 &nbsp;|&nbsp; Video dominates at 2–4 Mbps per session vs voice at 0.048 Mbps.</div>',
                unsafe_allow_html=True)
        else:
            st.warning("Traffic matrix data is currently unavailable.")

    elif _eff_section == "RF_Coverage":
        st.markdown(
            '<div class="section-header">COST 231-Hata Wireless Coverage Analysis</div>',
            unsafe_allow_html=True)
        if wl:
            p, mx = wl["parameters"], wl["metrics"]
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric(
                    "Edge radius (-100 dBm)",
                    f"{mx['max_radius_km']} km")
            with c2:
                st.metric(
                    "Service radius (-90 dBm)",
                    f"{mx.get('service_radius_km','-')} km")
            with c3:
                st.metric("Area per site", f"{mx['area_per_site_km2']} km²")
            with c4:
                st.metric(
                    "District coverage",
                    f"{mx['district_coverage_percent']}%")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(
                    f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Parameter</th><th>Value</th></tr></thead><tbody><tr><td>Access frequency</td><td>{p["frequency_mhz"]} MHz</td></tr><tr><td>TX power</td><td>{p["tx_power_dbm"]} dBm</td></tr><tr><td>TX antenna gain</td><td>{p.get("tx_gain_dbi","-")} dBi</td></tr><tr><td>RX antenna gain</td><td>{p.get("rx_gain_dbi","-")} dBi</td></tr><tr><td>RX sensitivity</td><td>{p["sensitivity_dbm"]} dBm</td></tr><tr><td>BS height</td><td>{p.get("bs_height_m","-")} m</td></tr><tr><td>Propagation model</td><td>COST 231-Hata</td></tr></tbody></table></div>',
                    unsafe_allow_html=True)
            with col2:
                if df_wireless_thresholds is not None:
                    rows = "".join(
                        f"<tr><td>{r.label}</td><td>{r.threshold_dbm} dBm</td><td>{r.baseline_coverage_pct:.2f}%</td><td>{r.improved_coverage_pct:.2f}%</td><td>{r.gain_pct_points:.2f} pts</td></tr>" for r in df_wireless_thresholds.itertuples())
                    st.markdown(
                        f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Threshold</th><th>Level</th><th>Baseline</th><th>Improved</th><th>Gain</th></tr></thead><tbody>{rows}</tbody></table></div>',
                        unsafe_allow_html=True)
            if PLOTLY_OK and df_wireless_surface is not None:
                pivot = df_wireless_surface.pivot(
                    index="y_km",
                    columns="x_km",
                    values="received_power_dbm").sort_index(
                    ascending=False)
                figw = go.Figure(
                    data=go.Heatmap(
                        z=pivot.values, x=list(
                            pivot.columns), y=list(
                            pivot.index), colorscale="Cividis", colorbar={
                            "title": "dBm"}, zmin=-120, zmax=-60))
                figw.update_layout(
                    height=380,
                    margin={
                        "l": 0,
                        "r": 0,
                        "t": 10,
                        "b": 0},
                    paper_bgcolor=PLT_BG,
                    plot_bgcolor=PLT_AX,
                    font={
                        "color": PLT_TEXT},
                    xaxis_title="District X (km)",
                    yaxis_title="District Y (km)")
                st.plotly_chart(figw, use_container_width=True)
            st.markdown(
                f'<div class="info-box"><b>Coverage improvement:</b> {wl.get("improvement_action","Add an infill site or raise antenna height.")}</div>',
                unsafe_allow_html=True)
        else:
            st.warning("Wireless analysis data is currently unavailable.")

    elif _eff_section == "Backhaul":
        st.markdown(
            '<div class="section-header">Microwave Backhaul Link Budget</div>',
            unsafe_allow_html=True)
        bh_results = backhaul_results_computed if backhaul_results_computed else []
        bh_df_use = backhaul_df_computed if backhaul_df_computed is not None else df_backhaul
        if bh_results:
            pass_count = sum(1 for r in bh_results if r['pass_fail'] == 'PASS')
            fail_count = len(bh_results) - pass_count
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Total Links", len(bh_results))
            with c2:
                st.metric("PASS", pass_count)
            with c3:
                st.metric("FAIL", fail_count)
            with c4:
                st.metric("Required Margin", "≥20 dB")
            if fail_count > 0:
                st.error(
                    f"❌ {fail_count} link(s) FAIL the 20 dB fade margin requirement!")
            else:
                st.success(
                    "✅ All links PASS the 20 dB fade margin requirement!")
        if bh_df_use is not None:
            st.dataframe(bh_df_use, use_container_width=True, hide_index=True)
            if bh_results:
                fig, ax = plt.subplots(figsize=(11, 3.5))
                links_l = [r['link_name'] for r in bh_results]
                margins = [r['fade_margin_db'] for r in bh_results]
                ax.bar(
                    links_l,
                    margins,
                    color=[
                        PLT_GREEN if m >= 20 else PLT_RED for m in margins],
                    alpha=0.85,
                    zorder=3,
                    width=0.6)
                ax.axhline(
                    20,
                    color=PLT_AMBER,
                    linestyle='--',
                    linewidth=2,
                    label='Required (20 dB)',
                    zorder=4)
                ax.set_ylabel('Fade Margin (dB)')
                ax.set_xlabel('Link')
                ax.tick_params(axis='x', rotation=45)
                ax.grid(axis='y', zorder=0)
                ax.legend()
                plt.tight_layout()
                st.pyplot(fig)
                plt.close(fig)
            elif "source" in bh_df_use.columns:
                fig, ax = plt.subplots(figsize=(11, 3.5))
                ax.bar(
                    bh_df_use['source'].astype(str) +
                    '→' +
                    bh_df_use['target'].astype(str),
                    bh_df_use['fade_margin_db'],
                    color=[
                        PLT_GREEN if v >= 20 else PLT_RED for v in bh_df_use['fade_margin_db']],
                    alpha=0.85,
                    zorder=3)
                ax.axhline(
                    20,
                    color=PLT_AMBER,
                    linestyle='--',
                    linewidth=2,
                    label='Required (20 dB)',
                    zorder=4)
                ax.set_ylabel('Fade Margin (dB)')
                ax.tick_params(axis='x', rotation=45)
                ax.grid(axis='y', zorder=0)
                ax.legend()
                plt.tight_layout()
                st.pyplot(fig)
                plt.close(fig)
        else:
            st.warning("Backhaul link-budget data is currently unavailable.")
        st.markdown(
            '<div class="info-box"><b>Link budget:</b> Rx power = TX power + TX gain − FSPL − misc losses. Rain attenuation: ITU-R P.838-3, Botswana zone H (30 mm/h). Required fade margin ≥ 20 dB.</div>',
            unsafe_allow_html=True)

    elif _eff_section == "Traffic_Summary":
        st.markdown(
            '<div class="section-header">Network-Level Traffic Summary</div>',
            unsafe_allow_html=True)
        breakdown = SIMULATION["traffic_breakdown"]
        if breakdown:
            bd_rows = []
            for site, mix in breakdown.items():
                total = sum(mix.values())
                bd_rows.append(
                    {
                        "Site": site, "Voice (Mbps)": round(
                            mix.get(
                                "voice", 0), 3), "Video (Mbps)": round(
                            mix.get(
                                "video", 0), 3), "Telemetry (Mbps)": round(
                            mix.get(
                                "telemetry", 0), 4), "Total (Mbps)": round(
                                    total, 3)})
            bd_df = pd.DataFrame(bd_rows)
            st.dataframe(bd_df, use_container_width=True, hide_index=True)
            if PLOTLY_OK:
                fig_td = go.Figure()
                fig_td.add_trace(
                    go.Bar(
                        x=bd_df["Site"],
                        y=bd_df["Voice (Mbps)"],
                        name="Voice",
                        marker_color=PLT_BLUE))
                fig_td.add_trace(
                    go.Bar(
                        x=bd_df["Site"],
                        y=bd_df["Video (Mbps)"],
                        name="Video",
                        marker_color=PLT_PURPLE))
                fig_td.add_trace(
                    go.Bar(
                        x=bd_df["Site"],
                        y=bd_df["Telemetry (Mbps)"],
                        name="Telemetry",
                        marker_color=PLT_ACCENT))
                fig_td.update_layout(
                    barmode="stack",
                    height=300,
                    paper_bgcolor=PLT_BG,
                    plot_bgcolor=PLT_AX,
                    font={
                        "color": PLT_TEXT},
                    xaxis_title="Base Station",
                    yaxis_title="Traffic (Mbps)",
                    legend={
                        "orientation": "h",
                        "y": -0.25},
                    margin={
                        "l": 0,
                        "r": 0,
                        "t": 10,
                        "b": 0})
                st.plotly_chart(fig_td, use_container_width=True)
        rerouted = int(
            (flow_df["decision"] == "Rerouted to backup").sum()) if not flow_df.empty else 0
        balanced = int(
            (flow_df["decision"] == "Load balanced").sum()) if not flow_df.empty else 0
        max_util = max((l["load_ratio"] for l in SIMULATION["links"]
                       if l["effective_capacity_mbps"] > 0), default=0)
        o1, o2, o3, o4 = st.columns(4)
        with o1:
            st.metric("Rerouted sites", rerouted)
        with o2:
            st.metric("Balanced sites", balanced)
        with o3:
            st.metric("Max link utilisation", f"{max_util*100:.1f}%")
        with o4:
            st.metric("Scheduler", st.session_state.nms_config["scheduler"])
        if not flow_df.empty:
            st.dataframe(flow_df, use_container_width=True, hide_index=True)

# ─── ANTENNA PROPERTIES (new tab: absorbs Backhaul + Teletraffic) ───────
elif _eff_section in ("Antennas", "Delay_KPIs"):
    if _eff_section == "Antennas":
        st.markdown(
            '<div class="section-header">Per-Site Antenna Specifications</div>',
            unsafe_allow_html=True)
        NODES, _ = get_inventory()
        node_list = list(NODES.values())
        col_a, col_b = st.columns([1.2, 1], gap="large")
        with col_a:
            for node in node_list:
                nid = node["id"]
                ntype = node.get("type", "bs")
                c = node["color"]
                is_cr = ntype in ("cr1", "cr2")
                freq = node.get("freq_ghz", 13.0 if is_cr else 7.0)
                gain = node.get("antenna_gain_dbi", 32 if is_cr else 17)
                bw = node.get("beam_width_deg", 2 if is_cr else 120)
                tx = node.get("tx_power_dbm", 30 if is_cr else 43)
                h = node.get("tower_height_m", 42)
                role = node.get("role_label", "Base Station")
                # EIRP
                eirp_dbm = tx + gain
                eirp_w = round(10**((eirp_dbm - 30) / 10), 2)
                st.markdown(f"""
<div class="antenna-card" style="border-left-color:{c}">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span style="font-size:14px;font-weight:700;color:{c}">{nid}</span>
    <span class="badge-info">{role}</span>
  </div>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:10px;font-size:12px">
    <div><span style="color:#9C9690;display:block">Tower Height</span><b>{h} m</b></div>
    <div><span style="color:#9C9690;display:block">Frequency</span><b>{freq} GHz</b></div>
    <div><span style="color:#9C9690;display:block">TX Power</span><b>{tx} dBm</b></div>
    <div><span style="color:#9C9690;display:block">Ant. Gain</span><b>{gain} dBi</b></div>
    <div><span style="color:#9C9690;display:block">Beam Width</span><b>{bw}°</b></div>
    <div><span style="color:#9C9690;display:block">EIRP</span><b>{eirp_dbm} dBm</b></div>
    <div><span style="color:#9C9690;display:block">EIRP (W)</span><b>{eirp_w} W</b></div>
    <div><span style="color:#9C9690;display:block">Type</span><b>{'Microwave PTP' if is_cr else 'Sector 120°'}</b></div>
  </div>
</div>""", unsafe_allow_html=True)
        with col_b:
            # Radar-style antenna pattern chart
            if PLOTLY_OK:
                st.markdown("**Antenna Pattern — Base Station (120° sector)**")
                theta = list(range(0, 361))
                # Approximate sector gain pattern

                def sector_gain(angle_deg, bw=120, peak_gain=17):
                    a = angle_deg if angle_deg <= 180 else angle_deg - 360
                    half = bw / 2
                    if abs(a) <= half:
                        # cosine rolloff
                        r_gain = peak_gain - 12 * (a / half)**2
                    else:
                        r_gain = peak_gain - 20
                    return max(r_gain, -5)
                r_vals = [sector_gain(t) for t in theta]
                fig_ant = go.Figure()
                fig_ant.add_trace(
                    go.Scatterpolar(
                        r=r_vals,
                        theta=theta,
                        mode="lines",
                        line={
                            "color": PLT_PURPLE,
                            "width": 2},
                        fill="toself",
                        fillcolor=f"rgba(83,74,183,0.10)",
                        name="BS Sector"))
                # PTP dish pattern
                r_ptp = [sector_gain(t, bw=2, peak_gain=32) for t in theta]
                fig_ant.add_trace(
                    go.Scatterpolar(
                        r=r_ptp,
                        theta=theta,
                        mode="lines",
                        line={
                            "color": PLT_ACCENT,
                            "width": 2},
                        name="CR Microwave (PTP)"))
                fig_ant.update_layout(
                    polar={
                        "radialaxis": {
                            "visible": True,
                            "range": [
                                -5,
                                35],
                            "tickfont": {
                                "size": 10}},
                        "angularaxis": {
                            "tickfont": {
                                "size": 10}}},
                    height=380,
                    paper_bgcolor=PLT_BG,
                    font={
                        "color": PLT_TEXT},
                    legend={
                        "orientation": "h",
                        "y": -0.1},
                    margin={
                        "l": 10,
                        "r": 10,
                        "t": 20,
                        "b": 10},
                    showlegend=True)
                st.plotly_chart(fig_ant, use_container_width=True)
            st.markdown(
                '<div class="info-box"><b>Base stations</b> use 120° sector antennas (3-sector omnidirectional coverage). <b>Core routers</b> use narrow 2° pencil-beam microwave dishes for 13 GHz backbone. EIRP = TX power + antenna gain.</div>',
                unsafe_allow_html=True)

    if _eff_section == "Antennas":
        st.markdown(
            '<div class="section-header">Erlang B Dimensioning — teletraffic_dimensioning_table.csv</div>',
            unsafe_allow_html=True)
        if df_dim is not None:
            per_site = df_dim[df_dim["site"].str.contains("BS", na=False)]
            trunk = df_dim[~df_dim["site"].str.contains("BS", na=False)]
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Channels / site",
                          int(per_site["channels_required"].iloc[0]) if not per_site.empty else "-")
            with c2:
                st.metric(
                    "Worst blocking",
                    f"{per_site['achieved_blocking'].max()*100:.3f}%" if not per_site.empty else "-")
            with c3:
                st.metric(
                    "Trunk channels", int(
                        trunk["channels_required"].iloc[0]) if not trunk.empty else "-")
            with c4:
                if not per_site.empty and not trunk.empty:
                    gain = per_site["channels_required"].sum(
                    ) - int(trunk["channels_required"].iloc[0])
                    st.metric("Trunking gain", f"{gain} circuits")
            rows = ""
            for r in df_dim.itertuples():
                is_t = "BS" not in str(r.site)
                kpi = '<span class="badge-pass">PASS</span>' if r.kpi_met else '<span class="badge-fail">FAIL</span>'
                bc = PLT_RED if r.achieved_blocking > r.target_blocking else PLT_GREEN
                sc = PLT_AMBER if is_t else PLT_PURPLE
                rows += f"<tr><td><b style='color:{sc}'>{r.site}</b></td><td>{r.offered_load_erl:.2f}</td><td>{r.channels_required}</td><td style='color:{bc}'>{r.achieved_blocking*100:.3f}%</td><td>{r.target_blocking*100:.0f}%</td><td>{kpi}</td></tr>"
            st.markdown(
                f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Site</th><th>Offered (Erl)</th><th>N channels</th><th>Blocking</th><th>Target</th><th>KPI</th></tr></thead><tbody>{rows}</tbody></table></div>',
                unsafe_allow_html=True)
            st.markdown(
                '<div class="info-box"><b>Erlang B:</b> B(A,N) = (A^N/N!) / Σ(A^k/k!) for k=0..N. Loop N upward until B ≤ 2%. <b>Trunking gain:</b> pooling 5 sites at CR-1 requires fewer trunk circuits vs 5×N individual circuits.</div>',
                unsafe_allow_html=True)
        else:
            st.warning(
                "Teletraffic dimensioning data is currently unavailable.")

    elif _eff_section == "Delay_KPIs":
        st.markdown(
            '<div class="section-header">Delay KPIs — teletraffic_delay_kpis.csv</div>',
            unsafe_allow_html=True)
        if df_delay is not None:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric(
                    "All KPIs", "PASS" if bool(
                        df_delay["met"].all()) else "FAIL")
            with c2:
                st.metric(
                    "Max P95 delay",
                    f"{df_delay['delay_ms'].max():.2f} ms")
            with c3:
                st.metric("Worst class",
                          df_delay.loc[df_delay['delay_ms'].idxmax(),
                                       'service_class'].title())
            with c4:
                st.metric("Sites checked", df_delay["site"].nunique())
            cls_badge = {
                "telemetry": '<span class="badge-info">EF</span>',
                "video": '<span class="badge-warn">AF21</span>',
                "voice": '<span class="badge-pass">AF31</span>'}
            rows = "".join(f"<tr><td><b style='color:{PLT_PURPLE}'>{r.site}</b></td><td>{cls_badge.get(r.service_class,'')} {r.service_class.title()}</td><td>{r.delay_ms:.2f} ms</td><td>{r.kpi_target} ms</td><td>{'<span class=\"badge-pass\">PASS</span>' if r.met else '<span class=\"badge-fail\">FAIL</span>'}</td></tr>" for r in df_delay.itertuples())
            st.markdown(
                f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Site</th><th>Class</th><th>P95 delay</th><th>Target</th><th>KPI</th></tr></thead><tbody>{rows}</tbody></table></div>',
                unsafe_allow_html=True)
        else:
            st.warning("Delay KPI data is currently unavailable.")

# ─── QoS — KPI Monitor: Metric | Model Output | Target | Result ──────────
elif _eff_section == "QoS":
    st.markdown(
        '<div class="section-header">QoS — KPI Monitor</div>',
        unsafe_allow_html=True)

    _alpha = st.session_state.get("inspect_alpha", 1.0)
    st.markdown(
        f'<div class="info-box">📊 Showing KPIs at load multiplier <b>α = {_alpha:.1f}×</b>. '
        f'Adjust using the <b>Inspect load multiplier</b> slider in <b>Fault & Stress → Stress Test</b>.</div>',
        unsafe_allow_html=True)

    def _nearest_stress_row(df, alpha):
        if df is None or df.empty:
            return None
        idx = (df["alpha"] - alpha).abs().idxmin()
        return df.loc[idx]

    _sr = _nearest_stress_row(df_stress, _alpha)
    _qos_kpis = []

    # 1 — Voice Blocking Probability
    if _sr is not None and "voice_blocking" in df_stress.columns:
        _vb = float(_sr["voice_blocking"]) * 100
        _vb_met = _vb <= 2.0
        _qos_kpis.append(("🎙 Voice Blocking Probability",
                           f"{_vb:.4f}%", "≤ 2.00%", _vb_met,
                           "Erlang B — circuit-switched loss model (M/G/c/c)"))
    elif df_qos_summary is not None and "voice_blocking_pct" in df_qos_summary.columns:
        _vb = float(df_qos_summary["voice_blocking_pct"].iloc[0])
        _vb_met = _vb <= 2.0
        _qos_kpis.append(("🎙 Voice Blocking Probability",
                           f"{_vb:.4f}%", "≤ 2.00%", _vb_met,
                           "Erlang B — circuit-switched loss model (baseline α=1.0)"))

    # 2 — Video P95 E2E Delay
    if _sr is not None and "video_delay_ms" in df_stress.columns:
        _vd = float(_sr["video_delay_ms"])
        _vd_met = _vd <= 150.0 and not np.isinf(_vd)
        _vd_str = "∞ (saturated)" if np.isinf(_vd) else f"{_vd:.1f} ms"
        _qos_kpis.append(("🎥 Video P95 E2E Delay",
                           _vd_str, "≤ 150 ms", _vd_met,
                           "M/M/1 WFQ model — 40% bandwidth share at α-scaled load"))
    elif df_qos_summary is not None and "video_p95_ms" in df_qos_summary.columns:
        _vd = float(df_qos_summary["video_p95_ms"].iloc[0])
        _qos_kpis.append(("🎥 Video P95 E2E Delay",
                           f"{_vd:.1f} ms", "≤ 150 ms", _vd <= 150.0,
                           "M/M/1 WFQ model (baseline α=1.0)"))

    # 3 — Telemetry P99 Delay
    if _sr is not None and "telemetry_p95_ms" in df_stress.columns:
        _td = float(_sr["telemetry_p95_ms"])
        _td_met = _td <= 50.0
        _qos_kpis.append(("📟 Telemetry P99 Delay",
                           f"{_td:.1f} ms", "≤ 50 ms", _td_met,
                           "Strict priority (EF / DSCP 46) — preempts all queues; never degrades"))
    elif df_qos_summary is not None and "telemetry_p95_ms" in df_qos_summary.columns:
        _td = float(df_qos_summary["telemetry_p95_ms"].iloc[0])
        _qos_kpis.append(("📟 Telemetry P99 Delay",
                           f"{_td:.1f} ms", "≤ 50 ms", _td <= 50.0,
                           "Strict priority (EF / DSCP 46)"))

    # 4 — Voice Call Setup Delay (P95), from delay_samples_summary.csv
    _vsd = None
    if df_delay_samples is not None and "class" in df_delay_samples.columns and "p95_ms" in df_delay_samples.columns:
        _vsd_row = df_delay_samples[df_delay_samples["class"] == "voice"]
        if not _vsd_row.empty:
            _vsd = float(_vsd_row["p95_ms"].iloc[0])
    if _vsd is None and df_delay is not None and "service_class" in df_delay.columns and "delay_ms" in df_delay.columns:
        _vsd_rows = df_delay[df_delay["service_class"] == "voice"]
        if not _vsd_rows.empty:
            _vsd = float(_vsd_rows["delay_ms"].max())
    if _vsd is not None:
        _qos_kpis.append(("🎙 Voice Setup Delay (P95)",
                           f"{_vsd:.1f} ms", "≤ 200 ms", _vsd <= 200.0,
                           "M/M/N Erlang C — propagation + SIP processing at CR-1"))

    # 5 — Backhaul Fade Margin
    if df_qos_summary is not None and "min_fade_margin_db" in df_qos_summary.columns:
        _fm = float(df_qos_summary["min_fade_margin_db"].iloc[0])
        _qos_kpis.append(("📡 Min Backhaul Fade Margin",
                           f"{_fm:.1f} dB", "≥ 20.0 dB", _fm >= 20.0,
                           "7 GHz microwave — rain fade margin, Botswana ITU zone"))

    # 6 — All Backhaul Links Pass
    if df_qos_summary is not None and "all_backhaul_links_pass" in df_qos_summary.columns:
        _abp = str(df_qos_summary["all_backhaul_links_pass"].iloc[0]).strip().lower() in ("true", "1", "yes")
        _qos_kpis.append(("📡 All Backhaul Links",
                           "Pass" if _abp else "Fail", "All links ≥ RSL threshold", _abp,
                           "Checks fade margin on every BS→CR-1 primary microwave path"))

    if _qos_kpis:
        _q_total = len(_qos_kpis)
        _q_pass = sum(1 for k in _qos_kpis if k[3])
        _q_first_fail = next((k[0] for k in _qos_kpis if not k[3]), None)

        _qc1, _qc2, _qc3 = st.columns(3)
        with _qc1:
            st.metric("KPIs Passing", f"{_q_pass} / {_q_total}",
                      delta="All OK" if _q_pass == _q_total else f"{_q_total - _q_pass} failing",
                      delta_color="normal" if _q_pass == _q_total else "inverse")
        with _qc2:
            st.metric("First Failing KPI",
                      (_q_first_fail.split(" ", 1)[-1] if _q_first_fail else "None"))
        with _qc3:
            st.metric("Inspect Multiplier", f"α = {_alpha:.1f}×")

        _q_rows = ""
        for _qm, _qo, _qt, _qmet, _qdesc in _qos_kpis:
            _badge = '<span class="badge-pass">PASS</span>' if _qmet else '<span class="badge-fail">FAIL</span>'
            _q_rows += (f"<tr>"
                        f"<td><b>{_qm}</b><br>"
                        f"<span style='color:{PLT_MUTED};font-size:11px'>{_qdesc}</span></td>"
                        f"<td style='text-align:center;font-weight:600'>{_qo}</td>"
                        f"<td style='text-align:center;color:{PLT_MUTED}'>{_qt}</td>"
                        f"<td style='text-align:center'>{_badge}</td></tr>")
        st.markdown(
            f'<div class="table-wrap"><table class="styled-table">'
            f'<thead><tr><th>Metric</th><th style="text-align:center">Model Output</th>'
            f'<th style="text-align:center">Target</th><th style="text-align:center">Result</th>'
            f'</tr></thead><tbody>{_q_rows}</tbody></table></div>',
            unsafe_allow_html=True)

        # Failure order banner
        _fo = []
        if df_stress is not None:
            _fo_seen = set()
            for _, _frow in df_stress.iterrows():
                if not _frow.get("video_kpi_met", True) and "Video" not in _fo_seen:
                    _fo.append(("Video", float(_frow["alpha"]))); _fo_seen.add("Video")
                if not _frow.get("voice_kpi_met", True) and "Voice" not in _fo_seen:
                    _fo.append(("Voice", float(_frow["alpha"]))); _fo_seen.add("Voice")
        if not _fo:
            _fo = [("Video", 1.25), ("Voice", 1.5)]
        _fo.sort(key=lambda x: x[1])
        _fo_str = " → ".join(f"<b>{c}</b> (α={a:.2f}×)" for c, a in _fo)
        st.markdown(
            f'<div class="fail-first-banner">⚠ KPI Failure Order: {_fo_str} → '
            f'<b>Telemetry</b> (never fails — EF strict priority). '
            f'Video saturates its WFQ share first (HD consults, high holding time).</div>',
            unsafe_allow_html=True)

        # Scheduler reference table
        st.markdown('<div class="section-header">Scheduler Design Reference</div>', unsafe_allow_html=True)
        _sc1, _sc2 = st.columns(2)
        with _sc1:
            st.markdown(
                '<div class="table-wrap"><table class="styled-table"><thead>'
                '<tr><th>Class</th><th>DSCP</th><th>Scheduler</th><th>BW</th><th>KPI Target</th><th>Fail Order</th></tr>'
                '</thead><tbody>'
                '<tr><td>Telemetry</td><td><span class="badge-info">EF 46</span></td><td>Strict Priority</td><td>—</td><td>P99 ≤ 50 ms</td><td>Never fails</td></tr>'
                '<tr><td>Voice</td><td><span class="badge-pass">AF31 26</span></td><td>WFQ 30%</td><td>30%</td><td>Block ≤ 2%</td><td><span class="badge-fail">2nd</span></td></tr>'
                '<tr><td>Video</td><td><span class="badge-warn">AF21 18</span></td><td>WFQ 40%</td><td>40%</td><td>P95 ≤ 150 ms</td><td><span class="badge-first-fail">1st</span></td></tr>'
                '<tr><td>Best Effort</td><td>0</td><td>WFQ 30%</td><td>30%</td><td>—</td><td>Always last</td></tr>'
                '</tbody></table></div>', unsafe_allow_html=True)
        with _sc2:
            st.markdown(
                '<div class="info-box"><b>Why video fails first:</b> HD video consults run 1-hour sessions at 4 Mbps. '
                'The 40% WFQ share (40 Mbps) saturates at α=1.25× — 8 concurrent consults × 5 sites × 4 Mbps.<br><br>'
                '<b>Why voice fails second:</b> Voice is circuit-switched (Erlang B). At α=1.5× the blocking exceeds 2%. '
                'Fix: increase N channels per site, not bandwidth.<br><br>'
                '<b>Telemetry never fails:</b> EF strict priority preempts all queues. '
                'At 256-byte packets over 100 Mbps, P99 stays under 10 ms regardless of load.</div>',
                unsafe_allow_html=True)
    else:
        st.warning("QoS KPI data is currently unavailable. Run the pipeline to generate outputs.")

# ─── ROUTING & SIGNALING ────────────────────────────────────────────────
elif _eff_section == "Routing & Signaling":
    st.markdown(
        '<div class="section-header">Routing Tables & Signaling Load Overview</div>',
        unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Routing Tables")
        if routing_tables:
            bs_nodes = [
                n for n in (
                    G_obj.nodes() if G_obj else []) if str(n).startswith("BS")]
            routing_data = []
            for bs in bs_nodes[:5]:
                for dst in ['CR-1', 'CR-2']:
                    nh = routing_tables.get(bs, {}).get(dst, 'N/A')
                    routing_data.append(
                        {'Source': bs, 'Destination': dst, 'Next Hop': nh})
            if routing_data:
                st.dataframe(
                    pd.DataFrame(routing_data),
                    use_container_width=True,
                    hide_index=True)
        else:
            st.info("Routing modules not available.")
        if failure_mode and reroute_check:
            st.metric(
                "Reroute Status",
                f"{reroute_check['reroute_count']}/5 BS → CR-2")
    with col2:
        st.subheader("Signaling Load Summary")
        if df_signal_summary is not None:
            summary = df_signal_summary.iloc[0]
            bhca_val = summary.get(
                'voice_busy_hour_attempts_hr', summary.get(
                    'total_bhca', 0))
            delay_val = summary.get(
                'worst_call_setup_delay_ms', summary.get(
                    'worst_setup_delay_ms', 0))
            kpi_val = bool(
                summary.get(
                    'network_kpi_met',
                    summary.get(
                        'all_kpis_met',
                        False)))
            st.metric("Total BHCA", f"{bhca_val:.0f}")
            st.metric("Worst Setup Delay", f"{delay_val:.1f} ms")
            st.metric("All KPIs Met", "✅" if kpi_val else "❌")
        else:
            st.info("Signaling summary data not available.")
    if df_signal is not None:
        st.subheader("Call Setup Delay per Base Station")
        fig, ax = plt.subplots(figsize=(10, 4))
        target = float(df_signal['call_setup_target_ms'].iloc[0]
                       ) if 'call_setup_target_ms' in df_signal.columns else 50
        ax.bar(
            df_signal['site'].tolist(),
            df_signal['call_setup_delay_ms'].tolist(),
            color=[
                PLT_GREEN if d <= target else PLT_RED for d in df_signal['call_setup_delay_ms']],
            alpha=0.85,
            zorder=3,
            width=0.6)
        ax.axhline(
            target,
            color=PLT_AMBER,
            linestyle='--',
            linewidth=2,
            label=f'KPI Target ({target:.0f} ms)',
            zorder=4)
        ax.set_ylabel('Setup Delay (ms)')
        ax.set_xlabel('Base Station')
        ax.grid(axis='y', zorder=0)
        ax.legend()
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
        rows = "".join(f"<tr><td>{r.site}</td><td>{r.voice_call_attempts_hr:.1f}</td><td>{r.telemetry_sessions_hr:.1f}</td><td>{r.signaling_msgs_hr:.1f}</td><td>{r.processor_load_pct:.1f}%</td><td>{r.call_setup_delay_ms:.1f} ms</td><td>{'<span class=\"badge-pass\">PASS</span>' if r.kpi_met else '<span class=\"badge-fail\">FAIL</span>'}</td></tr>" for r in df_signal.itertuples())
        st.markdown(
            f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Site</th><th>Voice/hr</th><th>Telemetry/hr</th><th>Msgs/hr</th><th>Proc Load</th><th>Call Setup</th><th>KPI</th></tr></thead><tbody>{rows}</tbody></table></div>',
            unsafe_allow_html=True)

# ─── SIGNALING DETAILS ──────────────────────────────────────────────────
elif _eff_section == "Signaling Details":
    st.markdown(
        '<div class="section-header">SS7 / SIP Signaling Deep-Dive — Call Setup Message Flow</div>',
        unsafe_allow_html=True)
    col_flow, col_params = st.columns([1.2, 1], gap="large")
    with col_flow:
        st.markdown("**Normal Call Setup Flow (BS → CR-1)**")
        st.markdown("""
<div class="ss7-flow">
  <span style="color:#534AB7;font-weight:700">UE (Clinic)</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <span style="color:#DA7756;font-weight:700">BS (Radio)</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <span style="color:#2563EB;font-weight:700">CR-1 (Core)</span><br>
  <span class="ss7-label">│</span>&nbsp;── CALL REQUEST ──────────▶<span class="ss7-label">│</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="ss7-label">│</span><br>
  <span class="ss7-label">│</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="ss7-label">│</span>&nbsp;── IAM (Initial Addr) ──▶<span class="ss7-label">│</span><br>
  <span class="ss7-label">│</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="ss7-label">│</span>&nbsp;◀─ ACM (Addr Complete) ──<span class="ss7-label">│</span><br>
  <span class="ss7-label">│</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="ss7-label">│</span>&nbsp;◀─ ANM (Answer) ─────────<span class="ss7-label">│</span><br>
  <span class="ss7-label">│</span>&nbsp;◀── RINGING / CONNECTED ──<span class="ss7-label">│</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="ss7-label">│</span><br>
  <span style="color:#9C9690;font-size:11px">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;◁── Voice bearer established ──▷</span><br>
  <span class="ss7-label">│</span>&nbsp;── DISCONNECT ────────────▶<span class="ss7-label">│</span>&nbsp;── REL (Release) ───────▶<span class="ss7-label">│</span><br>
  <span class="ss7-label">│</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="ss7-label">│</span>&nbsp;◀─ RLC (Release Compl.) ─<span class="ss7-label">│</span>
</div>""", unsafe_allow_html=True)
        st.markdown(
            '<div class="info-box"><b>Signaling model:</b> SS7 ISUP-inspired. IAM + ACM + ANM + REL + RLC = 5 core messages. Processing delay per CR node = 5 ms.</div>',
            unsafe_allow_html=True)
    with col_params:
        st.markdown("**Signaling Parameters**")
        SIG_MSG_BYTES = 100
        SIG_MSGS_PCALL = 2
        CHAN_CAP_KBPS = 64.0
        PROC_DELAY_MS = 5.0
        st.markdown(
            f"""<div class="table-wrap"><table class="styled-table"><thead><tr><th>Parameter</th><th>Value</th></tr></thead><tbody>
<tr><td>Protocol</td><td>SS7 ISUP / SIP</td></tr>
<tr><td>Msg size (avg)</td><td>{SIG_MSG_BYTES} bytes</td></tr>
<tr><td>Msgs per call</td><td>{SIG_MSGS_PCALL} (SETUP + RELEASE)</td></tr>
<tr><td>Channel capacity</td><td>{CHAN_CAP_KBPS:.0f} kbps</td></tr>
<tr><td>Processing delay</td><td>{PROC_DELAY_MS:.0f} ms per node</td></tr>
<tr><td>Telemetry SLA</td><td>≤ 50 ms</td></tr>
<tr><td>Voice SLA</td><td>≤ 200 ms</td></tr>
<tr><td>Utilisation target</td><td>&lt; 70%</td></tr>
</tbody></table></div>""", unsafe_allow_html=True)

    st.markdown(
        '<div class="section-header">Normal vs Emergency Burst Signaling Analysis</div>',
        unsafe_allow_html=True)
    if scenario_obj:
        tc = scenario_obj.get("traffic", {})
        voice_arr_hr = tc.get("voice", {}).get("arrival_rate_per_hour", 15)
        video_arr_hr = tc.get("video", {}).get("arrival_rate_per_hour", 8)
        normal_cps = (voice_arr_hr + video_arr_hr) / 3600.0
    else:
        normal_cps = 0.0064
    burst_cps = normal_cps * 5
    bs_sites = ["BS1", "BS2", "BS3", "BS4", "BS5"]
    prop_delays = {}
    if df_signal is not None and "call_setup_delay_ms" in df_signal.columns:
        for _, r in df_signal.iterrows():
            prop_delays[r["site"]] = float(
                r["call_setup_delay_ms"]) - PROC_DELAY_MS
    else:
        prop_delays = {
            "BS1": 8.0,
            "BS2": 8.0,
            "BS3": 9.0,
            "BS4": 7.0,
            "BS5": 9.0}
    burst_data = []
    for scenario_type, cps in [
            ("Normal", normal_cps), ("Emergency Burst", burst_cps)]:
        for site in bs_sites:
            prop = prop_delays.get(site, 8.0)
            sig_load_kbps = cps * SIG_MSGS_PCALL * SIG_MSG_BYTES * 8 / 1000.0
            util_pct = sig_load_kbps / CHAN_CAP_KBPS * 100
            setup_delay = prop + PROC_DELAY_MS
            service_rate_cps = CHAN_CAP_KBPS * 1000 / \
                (SIG_MSG_BYTES * 8 * SIG_MSGS_PCALL)
            rho = cps / service_rate_cps if service_rate_cps > 0 else 0
            q_delay = (rho / (1 - rho)) * \
                PROC_DELAY_MS if rho < 1.0 else float('inf')
            total_delay = setup_delay + \
                (q_delay if not math.isinf(q_delay) else 200.0)
            burst_data.append(
                {
                    "Scenario": scenario_type,
                    "Site": site,
                    "CPS": round(
                        cps,
                        4),
                    "Sig Load (kbps)": round(
                        sig_load_kbps,
                        3),
                    "Chan Util (%)": round(
                        util_pct,
                        2),
                    "Prop Delay (ms)": round(
                        prop,
                        2),
                    "Queue Delay (ms)": round(
                        q_delay,
                        3) if not math.isinf(q_delay) else "∞",
                    "Total Delay (ms)": round(
                        total_delay,
                        2),
                    "Tel SLA ≤50ms": "✅" if total_delay <= 50 else "❌",
                    "Voice SLA ≤200ms": "✅" if total_delay <= 200 else "❌",
                    "Util <70%": "✅" if util_pct < 70 else "❌"})
    burst_df = pd.DataFrame(burst_data)
    normal_df = burst_df[burst_df["Scenario"] == "Normal"]
    burst_only = burst_df[burst_df["Scenario"] == "Emergency Burst"]
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        st.metric("Normal CPS", f"{normal_cps:.4f}")
    with b2:
        st.metric("Burst CPS", f"{burst_cps:.4f}", delta="5×")
    with b3:
        st.metric(
            "Normal Load (avg)",
            f"{normal_df['Sig Load (kbps)'].mean():.3f} kbps")
    with b4:
        st.metric(
            "Burst Load (avg)",
            f"{burst_only['Sig Load (kbps)'].mean():.3f} kbps",
            delta_color="inverse")
    tab1, tab2 = st.tabs(["Normal Scenario", "Emergency Burst Scenario"])
    with tab1:
        st.dataframe(
            normal_df.drop(
                columns=["Scenario"]),
            use_container_width=True,
            hide_index=True)
    with tab2:
        st.dataframe(
            burst_only.drop(
                columns=["Scenario"]),
            use_container_width=True,
            hide_index=True)
    if PLOTLY_OK:
        fig_sig = go.Figure()
        fig_sig.add_trace(
            go.Bar(
                x=bs_sites,
                y=normal_df["Chan Util (%)"].tolist(),
                name="Normal",
                marker_color=PLT_BLUE))
        fig_sig.add_trace(
            go.Bar(
                x=bs_sites,
                y=burst_only["Chan Util (%)"].tolist(),
                name="Emergency Burst",
                marker_color=PLT_RED))
        fig_sig.add_hline(
            y=70,
            line_dash="dot",
            line_color=PLT_AMBER,
            annotation_text="70% threshold",
            annotation_font_color=PLT_AMBER)
        fig_sig.update_layout(
            height=300,
            barmode="group",
            paper_bgcolor=PLT_BG,
            plot_bgcolor=PLT_AX,
            font={
                "color": PLT_TEXT},
            xaxis_title="Base Station",
            yaxis_title="Channel Utilisation (%)",
            legend={
                "orientation": "h",
                "y": -0.2},
            margin={
                "l": 0,
                "r": 0,
                "t": 20,
                "b": 0})
        st.plotly_chart(fig_sig, use_container_width=True)
    st.markdown(
        '<div class="info-box"><b>M/M/1 queuing:</b> ρ = λ/μ. Queue delay = ρ/(1−ρ) × service_time. Channel well below 70% at normal CPS; emergency burst scales linearly.</div>',
        unsafe_allow_html=True)

# ─── CALL TERMINATION ───────────────────────────────────────────────────
elif _eff_section == "Call Termination":
    st.markdown(
        '<div class="section-header">Call Termination & Lifecycle Management</div>',
        unsafe_allow_html=True)
    col_sm, col_stats = st.columns([1.2, 1], gap="large")
    with col_sm:
        st.markdown("**Call Lifecycle — State Machine**")
        st.markdown("""
<div class="ss7-flow">
  <b style="color:#534AB7">● IDLE</b><br>
  &nbsp;&nbsp;↓ UE sends CALL_REQUEST (IAM)<br>
  <b style="color:#DA7756">● CALL_SETUP</b> &nbsp;<span style="color:#9C9690;font-size:11px">← Setup delay measured here</span><br>
  &nbsp;&nbsp;↓ CR-1 processes + routes (ACM)<br>
  <b style="color:#B45309">● RINGING / PROCEEDING</b><br>
  &nbsp;&nbsp;↓ Remote party answers (ANM)<br>
  <b style="color:#2D7A4F">● ACTIVE / CONNECTED</b> &nbsp;<span style="color:#9C9690;font-size:11px">← CDR timer starts</span><br>
  &nbsp;&nbsp;↓ Either party disconnects / fault<br>
  <b style="color:#2563EB">● DISCONNECT_PENDING</b><br>
  &nbsp;&nbsp;↓ REL sent, RLC received<br>
  <b style="color:#C0392B">● TERMINATED</b> &nbsp;<span style="color:#9C9690;font-size:11px">← CDR closed, billing record written</span><br>
  &nbsp;&nbsp;↓ Resources released<br>
  <b style="color:#534AB7">● IDLE</b>
</div>""", unsafe_allow_html=True)
    with col_stats:
        st.markdown("**Termination Reason Distribution**")
        if scenario_obj:
            voice_cfg = scenario_obj.get("traffic", {}).get("voice", {})
            A_voice = voice_cfg.get("offered_load_erl", 0.75)
            N_voice = 4
        else:
            A_voice, N_voice = 0.75, 4

        def _eb(A, N):
            b = 1.0
            for n in range(1, N + 1):
                b = (A * b) / (n + A * b)
            return b
        block_prob = _eb(A_voice, N_voice)
        normal_term_pct = max(0, 100 - block_prob * 100 - 2.1 - 1.4 - 0.8)
        reasons = {
            "Normal user hang-up": round(
                normal_term_pct,
                1),
            "Blocked (no circuit)": round(
                block_prob * 100,
                2),
            "Timeout (no answer)": 2.1,
            "Network fault / reroute": 1.4,
            "Radio link failure": 0.8}
        if PLOTLY_OK:
            fig_pie = go.Figure(
                go.Pie(
                    labels=list(
                        reasons.keys()),
                    values=list(
                        reasons.values()),
                    hole=0.45,
                    marker_colors=[
                        PLT_GREEN,
                        PLT_RED,
                        PLT_AMBER,
                        PLT_BLUE,
                        PLT_PURPLE],
                    textfont_size=11))
            fig_pie.update_layout(
                height=280, paper_bgcolor=PLT_BG, plot_bgcolor=PLT_BG,
                font={"color": PLT_TEXT},
                legend={"font": {"size": 11, "color": PLT_TEXT}, "orientation": "v",
                        "bgcolor": PLT_BG},
                margin={"l": 0, "r": 0, "t": 10, "b": 0})
            st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown(
        '<div class="section-header">Live Call Activity</div>',
        unsafe_allow_html=True)
    _tick = int(datetime.now().timestamp() / 30)
    _live_rng = np.random.default_rng(_tick % 9999)
    _now_ts = datetime.now()
    _live_sites = ["BS1", "BS2", "BS3", "BS4", "BS5"]
    _live_svcs = [("Voice", "AF31 (26)", PLT_BLUE), ("Video", "AF21 (18)", PLT_PURPLE), ("Telemetry", "EF (46)", PLT_ACCENT)]
    _live_calls = []
    for _li in range(3):
        _ls = _live_sites[int(_live_rng.integers(0, 5))]
        _lsi = int(_live_rng.integers(0, 3))
        _lsvc, _ldscp, _lcol = _live_svcs[_lsi]
        _lstart = _now_ts - timedelta(minutes=int(_live_rng.integers(1, 12)), seconds=int(_live_rng.integers(0, 59)))
        _ldur = int((_now_ts - _lstart).total_seconds())
        _live_calls.append({"status": "ACTIVE", "site": _ls, "service": _lsvc, "dscp": _ldscp,
                             "start": _lstart.strftime("%H:%M:%S"), "duration": f"{_ldur}s",
                             "caller": f"+267 7{int(_live_rng.integers(100,999))}-{int(_live_rng.integers(1000,9999))}",
                             "called": f"+267 7{int(_live_rng.integers(100,999))}-{int(_live_rng.integers(1000,9999))}",
                             "color": _lcol})
    for _li in range(3):
        _ls = _live_sites[int(_live_rng.integers(0, 5))]
        _lsi = int(_live_rng.integers(0, 3))
        _lsvc, _ldscp, _lcol = _live_svcs[_lsi]
        _lend = _now_ts - timedelta(minutes=int(_live_rng.integers(2, 18)))
        _ldurs = int(_live_rng.integers(15, 600))
        _lstart = _lend - timedelta(seconds=_ldurs)
        _live_calls.append({"status": "ENDED", "site": _ls, "service": _lsvc, "dscp": _ldscp,
                             "start": _lstart.strftime("%H:%M:%S"), "duration": f"{_ldurs}s",
                             "caller": f"+267 7{int(_live_rng.integers(100,999))}-{int(_live_rng.integers(1000,9999))}",
                             "called": f"+267 7{int(_live_rng.integers(100,999))}-{int(_live_rng.integers(1000,9999))}",
                             "color": _lcol})
    _live_rows_html = ""
    for _lc in _live_calls:
        _is_active = _lc["status"] == "ACTIVE"
        _st_html = f'<span style="color:{PLT_GREEN};font-weight:700">● ACTIVE</span>' if _is_active else f'<span style="color:{PLT_MUTED}">◉ ENDED</span>'
        _live_rows_html += (f"<tr><td>{_st_html}</td><td><b style='color:{PLT_PURPLE}'>{_lc['site']}</b></td>"
                            f"<td style='color:{_lc['color']}'>{_lc['service']}</td>"
                            f"<td style='font-size:11px;color:{PLT_MUTED}'>{_lc['dscp']}</td>"
                            f"<td style='font-family:monospace;font-size:11px'>{_lc['caller']}</td>"
                            f"<td style='font-family:monospace;font-size:11px'>{_lc['called']}</td>"
                            f"<td>{_lc['start']}</td><td>{_lc['duration']}</td></tr>")
    st.markdown(
        f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Status</th><th>Site</th><th>Service</th><th>DSCP</th><th>Caller</th><th>Called</th><th>Start</th><th>Duration</th></tr></thead><tbody>{_live_rows_html}</tbody></table></div>',
        unsafe_allow_html=True)

    st.markdown(
        '<div class="section-header">Sample Call Detail Records (CDR)</div>',
        unsafe_allow_html=True)
    st.markdown(
        '<div class="info-box"><b>CDR fields:</b> Each completed call generates one CDR. Fields: calling/called number, start/end timestamp, duration, termination reason, DSCP class, site, charge units.</div>',
        unsafe_allow_html=True)
    rng = np.random.default_rng(42)
    sites_cdr = ["BS1", "BS2", "BS3", "BS4", "BS5"]
    term_reasons_list = [
        "Normal",
        "Normal",
        "Normal",
        "Busy",
        "No Answer",
        "Fault"]
    now = datetime(2026, 4, 22, 8, 0, 0)
    cdr_rows = []
    for i in range(18):
        site = sites_cdr[i % 5]
        start = now + timedelta(minutes=int(rng.integers(0, 480)))
        dur_s = int(rng.exponential(180)) + 15
        end = start + timedelta(seconds=dur_s)
        svc = rng.choice(["voice", "video", "telemetry"], p=[0.55, 0.35, 0.10])
        term = rng.choice(
            term_reasons_list, p=[
                0.75, 0.10, 0.08, 0.04, 0.02, 0.01])
        charge = round(max(0, dur_s / 60.0 * (0.50 if svc ==
                       "voice" else 1.80 if svc == "video" else 0.05)), 2)
        dscp = {
            "voice": "AF31 (26)",
            "video": "AF21 (18)",
            "telemetry": "EF (46)"}[svc]
        cdr_rows.append({"CDR #": f"CDR-{2026042200+i:010d}",
                         "Site": site,
                         "Service": svc.title(),
                         "DSCP": dscp,
                         "Start": start.strftime("%H:%M:%S"),
                         "End": end.strftime("%H:%M:%S"),
                         "Duration (s)": dur_s,
                         "Termination": term,
                         "Charge Units": charge})
    cdr_df = pd.DataFrame(cdr_rows)

    def cdr_row_html(r):
        tc = PLT_GREEN if r["Termination"] == "Normal" else PLT_RED if r["Termination"] == "Fault" else PLT_AMBER
        sc_map = {
            "Voice": PLT_BLUE,
            "Video": PLT_PURPLE,
            "Telemetry": PLT_ACCENT}
        svc_color = sc_map.get(r["Service"], PLT_TEXT)
        return (f"<tr><td style='font-family:monospace;font-size:11px'>{r['CDR #']}</td><td><b style='color:{PLT_PURPLE}'>{r['Site']}</b></td><td style='color:{svc_color}'>{r['Service']}</td><td><span style='font-size:11px;color:{PLT_MUTED}'>{r['DSCP']}</span></td><td>{r['Start']}</td><td>{r['End']}</td><td>{r['Duration (s)']}</td><td style='color:{tc}'>{r['Termination']}</td><td><b>{r['Charge Units']:.2f}</b></td></tr>")
    rows_html = "".join(cdr_row_html(r) for _, r in cdr_df.iterrows())
    st.markdown(
        f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>CDR #</th><th>Site</th><th>Service</th><th>DSCP</th><th>Start</th><th>End</th><th>Dur (s)</th><th>Termination</th><th>Charge</th></tr></thead><tbody>{rows_html}</tbody></table></div>',
        unsafe_allow_html=True)

# ─── BILLING ANALYTICS ──────────────────────────────────────────────────
elif _eff_section == "Billing Analytics":
    st.markdown(
        '<div class="section-header">Billing Analytics — Usage Metering & Revenue Model</div>',
        unsafe_allow_html=True)
    col_tariff, col_summary = st.columns([1, 1.4], gap="large")
    with col_tariff:
        st.markdown("**Tariff Configuration**")
        voice_rate = st.number_input(
            "Voice rate (BWP / min)",
            min_value=0.0,
            max_value=10.0,
            value=0.50,
            step=0.05)
        video_rate = st.number_input(
            "Video rate (BWP / min)",
            min_value=0.0,
            max_value=20.0,
            value=1.80,
            step=0.10)
        tel_rate = st.number_input(
            "Telemetry rate (BWP / min)",
            min_value=0.0,
            max_value=5.0,
            value=0.05,
            step=0.01)
        busy_hours = st.slider("Daily busy hours", 1, 16, 8)
        days_month = st.slider("Days per month", 20, 31, 22)
        st.markdown(
            '<div class="info-box"><b>Currency:</b> BWP — Botswana Pula.</div>',
            unsafe_allow_html=True)

    if scenario_obj:
        tc = scenario_obj["traffic"]
        A_v = tc["voice"]["offered_load_erl"]
        h_v = tc["voice"]["holding_time_s"] / 60.0
        A_vid = tc["video"]["offered_load_erl"]
        h_vid = min(tc["video"]["holding_time_s"], 3600) / 60.0
        A_tel = tc["telemetry"]["offered_load_erl"]
        h_tel = tc["telemetry"]["holding_time_s"] / 60.0
        lam_v = tc["voice"]["arrival_rate_per_hour"]
        lam_vid = tc["video"]["arrival_rate_per_hour"]
        lam_tel = tc["telemetry"]["arrival_rate_per_hour"]
    else:
        A_v, h_v, lam_v = 0.75, 3.0, 15.0
        A_vid, h_vid, lam_vid = 8.0, 60.0, 8.0
        A_tel, h_tel, lam_tel = 0.50, 1.0, 30.0

    n_sites = 5
    voice_rev_mo = lam_v * h_v * voice_rate * n_sites * busy_hours * days_month
    video_rev_mo = lam_vid * h_vid * video_rate * n_sites * busy_hours * days_month
    tel_rev_mo = lam_tel * h_tel * tel_rate * n_sites * busy_hours * days_month
    total_rev_mo = voice_rev_mo + video_rev_mo + tel_rev_mo
    voice_calls_mo = lam_v * n_sites * busy_hours * days_month
    video_calls_mo = lam_vid * n_sites * busy_hours * days_month
    tel_events_mo = lam_tel * n_sites * busy_hours * days_month

    with col_summary:
        st.markdown("**Monthly Revenue Forecast**")
        r1, r2 = st.columns(2)
        with r1:
            st.metric("Voice Revenue", f"BWP {voice_rev_mo:,.0f}")
            st.metric("Video Revenue", f"BWP {video_rev_mo:,.0f}")
            st.metric("Telemetry Rev.", f"BWP {tel_rev_mo:,.0f}")
        with r2:
            st.metric("Total Monthly", f"BWP {total_rev_mo:,.0f}")
            st.metric("Annual Forecast", f"BWP {total_rev_mo*12:,.0f}")
            st.metric("Revenue per Site", f"BWP {total_rev_mo/n_sites:,.0f}")

    st.markdown(
        '<div class="section-header">Monthly Revenue Breakdown by Service & Site</div>',
        unsafe_allow_html=True)
    if PLOTLY_OK:
        site_labels = ["BS1", "BS2", "BS3", "BS4", "BS5"]
        v_per_site = voice_rev_mo / n_sites
        vid_per_site = video_rev_mo / n_sites
        tel_per_site = tel_rev_mo / n_sites
        fig_bill = go.Figure()
        fig_bill.add_trace(
            go.Bar(
                x=site_labels,
                y=[v_per_site] *
                n_sites,
                name="Voice",
                marker_color=PLT_BLUE))
        fig_bill.add_trace(
            go.Bar(
                x=site_labels,
                y=[vid_per_site] *
                n_sites,
                name="Video",
                marker_color=PLT_PURPLE))
        fig_bill.add_trace(
            go.Bar(
                x=site_labels,
                y=[tel_per_site] *
                n_sites,
                name="Telemetry",
                marker_color=PLT_ACCENT))
        fig_bill.update_layout(
            height=320,
            barmode="stack",
            paper_bgcolor=PLT_BG,
            plot_bgcolor=PLT_AX,
            font={
                "color": PLT_TEXT},
            xaxis_title="Base Station",
            yaxis_title="Revenue (BWP/month)",
            legend={
                "orientation": "h",
                "y": -0.25},
            margin={
                "l": 0,
                "r": 0,
                "t": 20,
                "b": 0})
        st.plotly_chart(fig_bill, use_container_width=True)

    st.markdown(
        '<div class="section-header">Monthly Usage Volume & Charge Summary</div>',
        unsafe_allow_html=True)
    usage_data = [{"Service": "Voice",
                   "DSCP": "AF31",
                   "Arrivals/hr/site": lam_v,
                   "Hold time (min)": round(h_v,
                                            1),
                   "Monthly calls": f"{voice_calls_mo:,.0f}",
                   "Rate (BWP/min)": f"{voice_rate:.2f}",
                   "Monthly Rev (BWP)": f"{voice_rev_mo:,.2f}"},
                  {"Service": "Video",
                   "DSCP": "AF21",
                   "Arrivals/hr/site": lam_vid,
                   "Hold time (min)": round(h_vid,
                                            1),
                   "Monthly calls": f"{video_calls_mo:,.0f}",
                   "Rate (BWP/min)": f"{video_rate:.2f}",
                   "Monthly Rev (BWP)": f"{video_rev_mo:,.2f}"},
                  {"Service": "Telemetry",
                   "DSCP": "EF",
                   "Arrivals/hr/site": lam_tel,
                   "Hold time (min)": round(h_tel,
                                            1),
                   "Monthly calls": f"{tel_events_mo:,.0f}",
                   "Rate (BWP/min)": f"{tel_rate:.2f}",
                   "Monthly Rev (BWP)": f"{tel_rev_mo:,.2f}"},
                  ]
    dscp_badges = {
        "AF31": '<span class="badge-pass">AF31</span>',
        "AF21": '<span class="badge-warn">AF21</span>',
        "EF": '<span class="badge-info">EF</span>'}
    rows_html = "".join(f"<tr><td><b>{r['Service']}</b></td><td>{dscp_badges.get(r['DSCP'],'')}</td><td>{r['Arrivals/hr/site']}</td><td>{r['Hold time (min)']}</td><td>{r['Monthly calls']}</td><td>{r['Rate (BWP/min)']}</td><td><b>{r['Monthly Rev (BWP)']}</b></td></tr>" for r in usage_data)
    rows_html += f"<tr style='background:#FAF9F6;font-weight:700'><td colspan='6'>TOTAL</td><td>BWP {total_rev_mo:,.2f}</td></tr>"
    st.markdown(
        f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Service</th><th>DSCP</th><th>Arr/hr/site</th><th>Hold (min)</th><th>Monthly Calls</th><th>Rate (BWP/min)</th><th>Monthly Revenue</th></tr></thead><tbody>{rows_html}</tbody></table></div>',
        unsafe_allow_html=True)

    # ─── Export billing analytics ───────────────────────────────────────────
    st.markdown(
        '<div class="section-header">Export Billing Data</div>',
        unsafe_allow_html=True)
    export_col1, export_col2, export_col3 = st.columns(3)
    usage_export_df = pd.DataFrame([{"Service": r["Service"],
                                     "DSCP": r["DSCP"],
                                     "Arrivals_per_hr_per_site": r["Arrivals/hr/site"],
                                     "Hold_time_min": r["Hold time (min)"],
                                     "Monthly_calls": r["Monthly calls"],
                                     "Rate_BWP_per_min": r["Rate (BWP/min)"],
                                     "Monthly_Revenue_BWP": r["Monthly Rev (BWP)"]} for r in usage_data])
    usage_export_df.loc[len(usage_export_df)] = {
        **{c: "" for c in usage_export_df.columns}, "Service": "TOTAL", "Monthly_Revenue_BWP": f"{total_rev_mo:,.2f}"}
    with export_col1:
        st.download_button(
            "📥 Export Usage Summary (CSV)",
            data=usage_export_df.to_csv(
                index=False).encode("utf-8"),
            file_name="billing_usage_summary.csv",
            mime="text/csv",
            use_container_width=True)
    growth = scenario_obj["forecasting"]["annual_growth_rate"] if scenario_obj else 0.15
    years_fc = list(range(0, 6))
    rev_fc = [total_rev_mo * 12 * ((1 + growth)**y) for y in years_fc]
    forecast_export_df = pd.DataFrame(
        {
            "Year": years_fc,
            "Annual_Revenue_BWP": [
                round(
                    r,
                    2) for r in rev_fc],
            "Growth_Rate_pct": round(
                growth * 100,
                1),
            "Voice_Monthly_BWP": round(
                voice_rev_mo,
                2),
            "Video_Monthly_BWP": round(
                video_rev_mo,
                2),
            "Telemetry_Monthly_BWP": round(
                tel_rev_mo,
                2),
            "Total_Monthly_BWP": round(
                total_rev_mo,
                2)})
    with export_col2:
        st.download_button(
            "📥 Export Forecast (CSV)",
            data=forecast_export_df.to_csv(
                index=False).encode("utf-8"),
            file_name="billing_forecast.csv",
            mime="text/csv",
            use_container_width=True)
    # CDR export
    rng2 = np.random.default_rng(42)
    sites_cdr2 = ["BS1", "BS2", "BS3", "BS4", "BS5"]
    term_reasons_list2 = [
        "Normal",
        "Normal",
        "Normal",
        "Busy",
        "No Answer",
        "Fault"]
    now2 = datetime(2026, 4, 22, 8, 0, 0)
    cdr_rows2 = []
    for i in range(50):
        site = sites_cdr2[i % 5]
        start = now2 + timedelta(minutes=int(rng2.integers(0, 480)))
        dur_s = int(rng2.exponential(180)) + 15
        end = start + timedelta(seconds=dur_s)
        svc = rng2.choice(["voice", "video", "telemetry"],
                          p=[0.55, 0.35, 0.10])
        term = rng2.choice(
            term_reasons_list2, p=[
                0.75, 0.10, 0.08, 0.04, 0.02, 0.01])
        charge = round(max(0, dur_s / 60.0 * (0.50 if svc ==
                       "voice" else 1.80 if svc == "video" else 0.05)), 2)
        cdr_rows2.append({"CDR_ID": f"CDR-{2026042200+i:010d}",
                          "Site": site,
                          "Service": svc,
                          "DSCP": {"voice": "AF31",
                                   "video": "AF21",
                                   "telemetry": "EF"}[svc],
                          "Start_Time": start.strftime("%Y-%m-%d %H:%M:%S"),
                          "End_Time": end.strftime("%Y-%m-%d %H:%M:%S"),
                          "Duration_s": dur_s,
                          "Termination": term,
                          "Charge_BWP": charge})
    cdr_export_df = pd.DataFrame(cdr_rows2)
    with export_col3:
        st.download_button(
            "📥 Export CDR Records (CSV)",
            data=cdr_export_df.to_csv(
                index=False).encode("utf-8"),
            file_name="cdr_records.csv",
            mime="text/csv",
            use_container_width=True)

    st.markdown(
        '<div class="section-header">5-Year Revenue Forecast (15% CAGR)</div>',
        unsafe_allow_html=True)
    if PLOTLY_OK:
        fig_fc = go.Figure()
        fig_fc.add_trace(
            go.Scatter(
                x=years_fc,
                y=rev_fc,
                mode="lines+markers",
                fill="tozeroy",
                fillcolor="rgba(218,119,86,0.12)",
                line={
                    "color": PLT_ACCENT,
                    "width": 3},
                marker={
                    "size": 8,
                    "color": PLT_ACCENT},
                name="Annual Revenue"))
        fig_fc.update_layout(
            height=300,
            paper_bgcolor=PLT_BG,
            plot_bgcolor=PLT_AX,
            font={
                "color": PLT_TEXT},
            xaxis_title="Year",
            yaxis_title="Revenue (BWP/year)",
            margin={
                "l": 0,
                "r": 0,
                "t": 20,
                "b": 0},
            showlegend=False)
        st.plotly_chart(fig_fc, use_container_width=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Year 0 (baseline)", f"BWP {rev_fc[0]:,.0f}")
        with c2:
            st.metric(
                "Year 3 projection",
                f"BWP {rev_fc[3]:,.0f}",
                delta=f"+{(rev_fc[3]/rev_fc[0]-1)*100:.0f}%")
        with c3:
            st.metric(
                "Year 5 projection",
                f"BWP {rev_fc[5]:,.0f}",
                delta=f"+{(rev_fc[5]/rev_fc[0]-1)*100:.0f}%")
    st.markdown(
        f'<div class="info-box"><b>Billing model:</b> CDR-based post-paid metering. Revenue = Σ(λ × h × rate × sites × hours × days). Growth at {growth*100:.0f}%/year CAGR. Currency: Botswana Pula (BWP).</div>',
        unsafe_allow_html=True)

# ─── STRESS TEST & FAULT MANAGEMENT (unified tab) ───────────────────────
elif _eff_section == "Fault & Stress":
    st.markdown(
        '<div class="section-header">Stress Test, Fault Management & Breaking Point Analysis</div>',
        unsafe_allow_html=True)

    st_tab1, st_tab2 = st.tabs(
        ["📈 Stress Test & Breaking Point", "🔧 Fault Management"])

    with st_tab1:
        if df_stress is not None:
            amin = float(df_stress["alpha"].min())
            amax = float(df_stress["alpha"].max())
            alpha_sel = st.slider(
                "Inspect load multiplier α",
                amin,
                amax,
                amin,
                step=0.1)
            st.session_state["inspect_alpha"] = alpha_sel
            row = df_stress[df_stress["alpha"] == round(alpha_sel, 1)]
            if not row.empty:
                r = row.iloc[0]
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("α", f"{r['alpha']}×")
                with c2:
                    st.metric(
                        "Voice blocking",
                        f"{r['voice_blocking']*100:.2f}%",
                        delta="OVER" if not r["voice_kpi_met"] else "OK")
                with c3:
                    st.metric("Video P95", f"{r['video_delay_ms']:.2f} ms")
                with c4:
                    st.metric(
                        "System",
                        "PASS" if r["voice_kpi_met"] and r["video_kpi_met"] else "FAIL")
                if not r["voice_kpi_met"]:
                    st.error(
                        f"Voice blocking {r['voice_blocking']*100:.2f}% > 2% at α={r['alpha']}×. Fix: increase N channels per site.")
                else:
                    st.success(f"All KPIs met at α={r['alpha']}×.")
            if PLOTLY_OK:
                alphas = df_stress["alpha"].tolist()
                blocking_pct = (df_stress["voice_blocking"] * 100).tolist()
                threshold = 2.0
                # Safe zone fill (below threshold)
                fig_stress = go.Figure()
                fig_stress.add_trace(go.Scatter(
                    x=alphas, y=[threshold] * len(alphas),
                    fill=None, mode="lines",
                    line={"color": PLT_AMBER, "width": 0},
                    showlegend=False, hoverinfo="skip"))
                fig_stress.add_trace(go.Scatter(
                    x=alphas, y=[0] * len(alphas),
                    fill="tonexty",
                    fillcolor="rgba(52,199,89,0.08)",
                    mode="lines", line={"color": "rgba(0,0,0,0)", "width": 0},
                    name="Safe zone", hoverinfo="skip"))
                # Danger zone fill (above threshold to max)
                y_max = max(blocking_pct) * 1.15
                fig_stress.add_trace(go.Scatter(
                    x=alphas, y=[y_max] * len(alphas),
                    fill=None, mode="lines",
                    line={"color": "rgba(0,0,0,0)", "width": 0},
                    showlegend=False, hoverinfo="skip"))
                fig_stress.add_trace(go.Scatter(
                    x=alphas, y=[threshold] * len(alphas),
                    fill="tonexty",
                    fillcolor="rgba(255,59,48,0.08)",
                    mode="lines", line={"color": "rgba(0,0,0,0)", "width": 0},
                    name="Danger zone", hoverinfo="skip"))
                # Area under blocking curve
                fig_stress.add_trace(go.Scatter(
                    x=alphas, y=blocking_pct,
                    fill="tozeroy",
                    fillcolor=f"rgba(0,113,227,0.15)",
                    mode="lines+markers",
                    line={"color": PLT_ACCENT, "width": 2.5, "shape": "spline"},
                    marker={"size": 8, "color": PLT_ACCENT,
                            "line": {"color": PLT_BG, "width": 2}},
                    name="Voice Blocking (%)",
                    hovertemplate="α = %{x}×<br>Blocking: %{y:.2f}%<extra></extra>"))
                # 2% threshold line
                fig_stress.add_hline(
                    y=threshold, line_dash="dot", line_color=PLT_AMBER,
                    line_width=2,
                    annotation_text="2% KPI target",
                    annotation_position="top right",
                    annotation_font_color=PLT_AMBER)
                fig_stress.update_layout(
                    height=340,
                    paper_bgcolor=PLT_BG, plot_bgcolor=PLT_BG,
                    font={"color": PLT_TEXT, "size": 12},
                    xaxis={"title": "Load Multiplier α",
                           "gridcolor": PLT_GRID, "zeroline": False,
                           "ticksuffix": "×"},
                    yaxis={"title": "Blocking Probability (%)",
                           "gridcolor": PLT_GRID, "zeroline": False,
                           "ticksuffix": "%", "range": [0, y_max]},
                    legend={"font": {"color": PLT_TEXT, "size": 11},
                            "bgcolor": "rgba(0,0,0,0)",
                            "orientation": "h", "y": -0.18},
                    margin={"l": 10, "r": 10, "t": 10, "b": 10},
                    hovermode="x unified")
                st.plotly_chart(fig_stress, use_container_width=True)
            else:
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.fill_between(df_stress["alpha"], df_stress['voice_blocking'] * 100,
                                alpha=0.2, color=PLT_ACCENT)
                ax.plot(df_stress["alpha"], df_stress['voice_blocking'] * 100,
                        'o-', color=PLT_ACCENT, lw=2.5, label='Voice Blocking (%)', ms=6)
                ax.axhline(2, color=PLT_AMBER, linestyle='--', linewidth=2, label='Target (2%)')
                ax.axhspan(2, ax.get_ylim()[1] if ax.get_ylim()[1] > 2 else 10,
                           alpha=0.05, color=PLT_RED)
                ax.set_xlabel('Load Multiplier α')
                ax.set_ylabel('Blocking Probability (%)')
                ax.grid(axis='y', alpha=0.4)
                ax.legend()
                plt.tight_layout()
                st.pyplot(fig)
                plt.close(fig)
            rows = ""
            for r in df_stress.itertuples():
                fail = not r.voice_kpi_met
                is_brk = (r.alpha == 1.5)
                bg = "background:#FEF2F2;" if fail else ""
                kpiv = '<span class="badge-fail">FAIL</span>' if fail else '<span class="badge-pass">PASS</span>'
                mark = " ◄ BREAK" if is_brk else ""
                rows += f"<tr style='{bg}'><td>{r.alpha}{mark}</td><td>{r.voice_blocking*100:.2f}%</td><td>{r.video_delay_ms:.2f} ms</td><td>{kpiv}</td></tr>"
            st.markdown(
                f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>α</th><th>Voice blocking</th><th>Video P95</th><th>Voice KPI</th></tr></thead><tbody>{rows}</tbody></table></div>',
                unsafe_allow_html=True)
        else:
            st.warning("Stress-test data is currently unavailable.")
        st.markdown(
            '<div class="info-box"><b>Breaking point:</b> Voice fails first (blocking > 2%) — bottleneck is circuit count N, not bandwidth. Video KPI fails next as traffic saturates the 40% WFQ share. Telemetry (strict priority) never fails.</div>',
            unsafe_allow_html=True)

        # ─── Hidden: Custom Configuration (collapsible) ──────────────────────
        with st.expander("⚙ Custom Configuration (Advanced)", expanded=False):
            st.markdown(
                '<div class="section-header">Network Configuration Parameters</div>',
                unsafe_allow_html=True)
            cfg = st.session_state.nms_config
            with st.form("config_form_stress"):
                routing_policy = st.selectbox(
                    "Routing policy", [
                        "Adaptive Failover", "Load Balanced", "Pinned Primary"], index=[
                        "Adaptive Failover", "Load Balanced", "Pinned Primary"].index(
                        cfg["routing_policy"]))
                scheduler = st.selectbox(
                    "Scheduler", [
                        "Priority Queuing", "Weighted Fair Queuing", "Hybrid QoS"], index=[
                        "Priority Queuing", "Weighted Fair Queuing", "Hybrid QoS"].index(
                        cfg["scheduler"]))
                col_cf1, col_cf2 = st.columns(2)
                with col_cf1:
                    primary_bw = st.slider(
                        "Primary link BW (%)", 50, 130, int(
                            cfg["primary_bw_alloc_pct"]))
                    backup_bw = st.slider(
                        "Backup link BW (%)", 50, 130, int(
                            cfg["backup_bw_alloc_pct"]))
                    backbone_bw = st.slider(
                        "Backbone BW (%)", 50, 130, int(
                            cfg["backbone_bw_alloc_pct"]))
                with col_cf2:
                    reuse_p = st.selectbox("Freq reuse pattern", [
                                           "3/9", "4/12", "7/21"], index=["3/9", "4/12", "7/21"].index(cfg["reuse_pattern"]))
                    access_freq = st.number_input(
                        "Access frequency (MHz)", min_value=700, max_value=3800, value=int(
                            cfg["access_frequency_mhz"]), step=100)
                    ant_gain = st.slider(
                        "Antenna gain (dBi)", 10, 30, int(
                            cfg["antenna_gain_dbi"]))
                ant_tilt = st.slider(
                    "Antenna tilt (deg)", 0, 10, int(
                        cfg["antenna_tilt_deg"]))
                ant_height = st.slider(
                    "Tower height adjustment (m)", -10, 15, int(cfg["antenna_height_adjust_m"]))
                auto_r = st.checkbox(
                    "Automatic rerouting", value=bool(
                        cfg["auto_reroute"]))
                load_b = st.checkbox(
                    "Load balancing across links", value=bool(
                        cfg["load_balancing"]))
                save_cfg = st.form_submit_button("Save Configuration")
            if save_cfg:
                st.session_state.nms_config = {
                    **cfg,
                    "routing_policy": routing_policy,
                    "scheduler": scheduler,
                    "primary_bw_alloc_pct": primary_bw,
                    "backup_bw_alloc_pct": backup_bw,
                    "backbone_bw_alloc_pct": backbone_bw,
                    "reuse_pattern": reuse_p,
                    "access_frequency_mhz": access_freq,
                    "antenna_gain_dbi": ant_gain,
                    "antenna_tilt_deg": ant_tilt,
                    "antenna_height_adjust_m": ant_height,
                    "auto_reroute": auto_r,
                    "load_balancing": load_b}
                st.session_state.config_revision += 1
                append_event(
                    "Config",
                    "Info",
                    f"Config revision {st.session_state.config_revision} saved.",
                    "Parameters updated.")
                st.rerun()
            st.metric("Config revision", st.session_state.config_revision)
            st.markdown(
                f'<div class="info-box"><b>Current:</b> Primary {cfg["primary_bw_alloc_pct"]}% | Backup {cfg["backup_bw_alloc_pct"]}% | Backbone {cfg["backbone_bw_alloc_pct"]}%<br>Access {cfg["access_frequency_mhz"]} MHz | Gain {cfg["antenna_gain_dbi"]} dBi | Tilt {cfg["antenna_tilt_deg"]}°</div>',
                unsafe_allow_html=True)

    with st_tab2:
        st.markdown(
            '<div class="section-header">Active Fault Scenario</div>',
            unsafe_allow_html=True)
        left, right = st.columns([1.2, 1], gap="large")
        with left:
            with st.form("fault_form"):
                backhaul_deg = st.slider(
                    "Backhaul degradation (%)", 0, 80, int(
                        st.session_state.nms_faults["backhaul_degradation_pct"]))
                failed_bs = st.multiselect(
                    "Base station failures", [
                        "BS1", "BS2", "BS3", "BS4", "BS5"], default=st.session_state.nms_faults["failed_bs"])
                cong_router = st.selectbox("Router congestion target", ["None", "CR-1", "CR-2"], index=[
                                           "None", "CR-1", "CR-2"].index(st.session_state.nms_faults["router_congestion_router"]))
                cong_pct = st.slider("Router congestion (%)", 0, 90, int(
                    st.session_state.nms_faults["router_congestion_pct"]))
                apply_f = st.form_submit_button("Apply Fault Scenario")
                reset_f = st.form_submit_button("Reset Faults")
            if apply_f:
                st.session_state.nms_faults = {
                    "backhaul_degradation_pct": backhaul_deg,
                    "failed_bs": failed_bs,
                    "router_congestion_router": cong_router,
                    "router_congestion_pct": cong_pct}
                append_event(
                    "Config",
                    "Info",
                    "Fault scenario updated.",
                    "Simulation inputs changed.")
                st.rerun()
            if reset_f:
                st.session_state.nms_faults = clone(DEFAULT_FAULTS)
                append_event(
                    "Config",
                    "Info",
                    "Fault scenario reset.",
                    "All simulated faults cleared.")
                st.rerun()
            if reroute_check:
                st.metric(
                    "Base Stations Rerouted",
                    f"{reroute_check['reroute_count']}/5")
                for bs, info in reroute_check.get("bs_routes", {}).items():
                    if info.get("reachable"):
                        st.success(
                            f"✓ {bs} → CR-2: {len(info['path'])-1} hops")
                    else:
                        st.error(f"✗ {bs} → NO PATH")
        with right:
            critical = int(
                (alarms_df["severity"] == "Critical").sum()) if not alarms_df.empty else 0
            major = int(
                (alarms_df["severity"] == "Major").sum()) if not alarms_df.empty else 0
            minor = int(
                (alarms_df["severity"] == "Minor").sum()) if not alarms_df.empty else 0
            a1, a2, a3, a4 = st.columns(4)
            with a1:
                st.metric("Active Alarms", len(SIMULATION["alarms"]))
            with a2:
                st.metric("Critical", critical)
            with a3:
                st.metric("Major", major)
            with a4:
                st.metric("Minor", minor)
            if alarms_df.empty:
                st.success(
                    "No active alarms under current simulated conditions.")
            else:
                rows = "".join(
                    f"<tr><td>{r.entity}</td><td>{r.alarm}</td><td>{severity_badge(r.severity)}</td><td>{r.hint}</td></tr>" for r in alarms_df.itertuples())
                st.markdown(
                    f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Entity</th><th>Alarm</th><th>Severity</th><th>Root Cause Hint</th></tr></thead><tbody>{rows}</tbody></table></div>',
                    unsafe_allow_html=True)
            if SIMULATION["recommendations"]:
                st.markdown(
                    '<div class="section-header">Recommendations</div>',
                    unsafe_allow_html=True)
                for rec in SIMULATION["recommendations"]:
                    st.markdown(
                        f'<div class="info-box">💡 {rec}</div>',
                        unsafe_allow_html=True)

# ─── FORECAST ───────────────────────────────────────────────────────────
elif _eff_section == "Forecast":
    st.markdown(
        '<div class="section-header">5-Year Capacity Forecast</div>',
        unsafe_allow_html=True)
    if df_util is None:
        # Try to run forecasting.py on demand
        try:
            import subprocess
            fc_path = os.path.join(BASE, "forecasting.py")
            if os.path.exists(fc_path):
                with st.spinner("Running forecasting.py..."):
                    result = subprocess.run(
                        [sys.executable, fc_path], cwd=BASE, capture_output=True, timeout=60)
                df_util = load_csv("forecasting_utilisation_annual.csv")
                df_plan = normalize_upgrade_plan_df(
                    load_csv("forecasting_upgrade_plan.csv"))
                if df_util is not None:
                    st.success("Forecasting module ran successfully.")
                else:
                    st.warning(
                        "Forecasting ran but no output CSV found. Check forecasting.py outputs.")
        except Exception as fe2:
            st.error(f"Could not run forecasting.py: {fe2}")

    if df_util is not None:
        plan_yr = (df_util[df_util["utilisation"] >= 0.70]["year"].min() if (
            df_util["utilisation"] >= 0.70).any() else "N/A")
        act_yr = (df_util[df_util["utilisation"] >= 0.90]["year"].min() if (
            df_util["utilisation"] >= 0.90).any() else "N/A")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Planning trigger (70%)", f"Year {plan_yr}")
        with c2:
            st.metric("Action trigger (90%)", f"Year {act_yr}")
        with c3:
            st.metric(
                "Year 5 utilisation",
                f"{df_util['utilisation'].max()*100:.1f}%")
        with c4:
            st.metric("CAGR", "15% / year")
        col1, col2 = st.columns(2)
        with col1:
            rows = ""
            for r in df_util.itertuples():
                pct = r.utilisation * 100
                raw = str(r.status).upper()
                if "SAFE" in raw:
                    badge, bc = '<span class="badge-pass">SAFE</span>', PLT_GREEN
                elif "PLAN" in raw:
                    badge, bc = '<span class="badge-warn">PLAN UPGRADE</span>', PLT_AMBER
                else:
                    badge, bc = '<span class="badge-fail">UPGRADE NOW</span>', PLT_RED
                bw = min(100, int(pct))
                rows += (f"<tr><td>Year {int(r.year)}</td><td>{pct:.1f}%<div style='background:{PLT_GRID};border-radius:3px;height:6px;margin-top:3px'><div style='width:{bw}%;background:{bc};height:6px;border-radius:3px'></div></div></td><td>{r.traffic_mbps:.1f} Mbps</td><td>{badge}</td></tr>")
            st.markdown(
                f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Year</th><th>Utilisation</th><th>Traffic</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div>',
                unsafe_allow_html=True)
        with col2:
            if df_plan is not None:
                phase_col = "Phase" if "Phase" in df_plan.columns else df_plan.columns[0]
                trigger_col = "Trigger" if "Trigger" in df_plan.columns else (
                    df_plan.columns[1] if len(df_plan.columns) > 1 else phase_col)
                action_col = "Action" if "Action" in df_plan.columns else (
                    df_plan.columns[2] if len(df_plan.columns) > 2 else phase_col)
                goal_col = "Goal" if "Goal" in df_plan.columns else (
                    df_plan.columns[3] if len(df_plan.columns) > 3 else "")
                rows = "".join(f"<tr><td><b>{getattr(r,phase_col,'')}</b></td><td><span class='badge-info'>{getattr(r,trigger_col,'')}</span></td><td>{getattr(r,action_col,'')}</td><td style='color:{PLT_MUTED};font-size:11px'>{getattr(r,goal_col,'') if goal_col else ''}</td></tr>" for r in df_plan.itertuples())
                st.markdown(
                    f'<div class="table-wrap"><table class="styled-table"><thead><tr><th>Phase</th><th>Trigger</th><th>Action</th><th>Goal</th></tr></thead><tbody>{rows}</tbody></table></div>',
                    unsafe_allow_html=True)
            st.markdown(
                '<div class="info-box"><b>Formula:</b> ρ(t) = ρ₀ × (1+0.15)^t &nbsp;|&nbsp; Starting at 60%, growing 15%/year.<br>Year 2 = planning (70%). Year 3 = upgrade deadline (90%). Year 4+ = over capacity without upgrade.</div>',
                unsafe_allow_html=True)
        if PLOTLY_OK:
            fig_fc2 = go.Figure()
            fig_fc2.add_trace(
                go.Scatter(
                    x=df_util["year"].tolist(),
                    y=(
                        df_util["utilisation"] *
                        100).tolist(),
                    mode="lines+markers",
                    line={
                        "color": PLT_ACCENT,
                        "width": 3},
                    marker={
                        "size": 7},
                    name="Utilisation %",
                    fill="tozeroy",
                    fillcolor="rgba(218,119,86,0.10)"))
            fig_fc2.add_hline(
                y=70,
                line_dash="dot",
                line_color=PLT_AMBER,
                annotation_text="Planning threshold 70%")
            fig_fc2.add_hline(
                y=90,
                line_dash="dot",
                line_color=PLT_RED,
                annotation_text="Action threshold 90%")
            fig_fc2.update_layout(
                height=280, paper_bgcolor=PLT_BG, plot_bgcolor=PLT_AX, font={
                    "color": PLT_TEXT}, xaxis_title="Year", yaxis_title="Utilisation (%)", margin={
                    "l": 0, "r": 0, "t": 20, "b": 0}, showlegend=False)
            st.plotly_chart(fig_fc2, use_container_width=True)
    else:
        st.info("Forecasting data unavailable. Place forecasting.py in the project root and click 'Run All Modules' in the sidebar, or ensure forecasting_utilisation_annual.csv exists.")

# ─── EVENTS ─────────────────────────────────────────────────────────────
elif _eff_section == "Logs":
    st.markdown(
        '<div class="section-header">Event & Logging System</div>',
        unsafe_allow_html=True)
    events_df = pd.DataFrame(st.session_state.event_log)
    if events_df.empty:
        st.info("No events logged yet.")
    else:
        events_df = events_df.sort_values("timestamp", ascending=False)
        e1, e2, e3 = st.columns(3)
        with e1:
            st.metric("Total events", len(events_df))
        with e2:
            st.metric(
                "Alarm events", int(
                    (events_df["type"] == "Alarm").sum()))
        with e3:
            st.metric(
                "Routing events", int(
                    (events_df["type"] == "Routing").sum()))
        st.dataframe(events_df, use_container_width=True, hide_index=True)
        st.download_button(
            "Download Logs (CSV)",
            events_df.to_csv(
                index=False).encode("utf-8"),
            "tele527_event_log.csv",
            "text/csv")

# ══════════════════════════════════════════════════════════════════════════════
#  FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
st.markdown("""
<div style="text-align:center;color:#9C9690;font-size:11px;padding:8px 0;font-family:'DM Sans',sans-serif">
  District Telehealth &amp; Emergency Communication NMS &nbsp;|&nbsp;
  BIUST · Group 1 · TELE 527 &nbsp;|&nbsp;
  Palapye / Serowe, Central District, Botswana &nbsp;|&nbsp;
  Student 4: Tsotlhe Seiphepi (Signaling &amp; Routing Lead)
</div>""", unsafe_allow_html=True)
