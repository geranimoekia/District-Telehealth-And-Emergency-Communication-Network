"""
TELE 527 — District Telehealth & Emergency Network
Live QoS Dashboard — Student 5 (Thebe Ratsatsi)
=======================================================
Install:  pip install streamlit plotly pandas folium streamlit-folium
Run:      streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json, os, time, math
from datetime import datetime
import folium
from folium import plugins
from streamlit_folium import st_folium

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="TELE 527 | QoS Dashboard",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA = os.path.join(os.path.dirname(__file__), "data")

# ─────────────────────────────────────────────
# REAL BOTSWANA COORDINATES — Palapye District
# Spread across ~50 km area centred on Palapye
# ─────────────────────────────────────────────
NODES = {
    "CR-1": {
        "label": "District Hospital (Palapye)",
        "lat": -22.5694, "lon": 27.1258,
        "role": "Primary core router",
        "type": "core_primary",
    },
    "CR-2": {
        "label": "District Health Office (Palapye)",
        "lat": -22.5820, "lon": 27.1100,
        "role": "Backup core router — failover",
        "type": "core_backup",
    },
    "BS1": {
        "label": "Clinic North-West (Mookane)",
        "lat": -22.3900, "lon": 26.9200,
        "role": "Access site — primary → CR-1",
        "type": "bs",
        "delay_primary_ms": 8,  "delay_backup_ms": 13,
        "link_margin_db": 39.5, "blocking_pct": 0.62,
        "setup_delay_ms": 13,   "rx_dbm": -45.5,
    },
    "BS2": {
        "label": "Clinic North-East (Serowe area)",
        "lat": -22.3700, "lon": 27.3500,
        "role": "Access site — primary → CR-1",
        "type": "bs",
        "delay_primary_ms": 8,  "delay_backup_ms": 24,
        "link_margin_db": 39.5, "blocking_pct": 0.62,
        "setup_delay_ms": 13,   "rx_dbm": -45.5,
    },
    "BS3": {
        "label": "Clinic South-West (Tswolofelo)",
        "lat": -22.7600, "lon": 26.9400,
        "role": "Access site — primary → CR-1",
        "type": "bs",
        "delay_primary_ms": 9,  "delay_backup_ms": 20,
        "link_margin_db": 39.5, "blocking_pct": 0.62,
        "setup_delay_ms": 14,   "rx_dbm": -45.5,
    },
    "BS4": {
        "label": "Clinic South (Molalatau)",
        "lat": -22.7900, "lon": 27.1258,
        "role": "Access site — primary → CR-1",
        "type": "bs",
        "delay_primary_ms": 7,  "delay_backup_ms": 21,
        "link_margin_db": 42.0, "blocking_pct": 0.62,
        "setup_delay_ms": 12,   "rx_dbm": -43.0,
    },
    "BS5": {
        "label": "Clinic South-East (Lerala)",
        "lat": -22.7700, "lon": 27.3600,
        "role": "Access site — primary → CR-1",
        "type": "bs",
        "delay_primary_ms": 9,  "delay_backup_ms": 26,
        "link_margin_db": 39.5, "blocking_pct": 0.62,
        "setup_delay_ms": 14,   "rx_dbm": -45.5,
    },
}

LINKS_PRIMARY  = [("BS1","CR-1"),("BS2","CR-1"),("BS3","CR-1"),("BS4","CR-1"),("BS5","CR-1")]
LINKS_BACKUP   = [("BS1","CR-2"),("BS2","CR-2"),("BS3","CR-2"),("BS4","CR-2"),("BS5","CR-2")]

C = {"blue":"#4f6ef7","purple":"#8b5cf6","green":"#059669",
     "amber":"#d97706","red":"#dc2626","gray":"#9ca3af"}

# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_csv(name):
    path = os.path.join(DATA, name)
    return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()

@st.cache_data(ttl=30)
def load_json(name):
    path = os.path.join(DATA, name)
    with open(path) as f: return json.load(f)
    return {}

delay_kpis  = load_csv("teletraffic_delay_kpis.csv")
dim_table   = load_csv("teletraffic_dimensioning_table.csv")
sig_load    = load_csv("teletraffic_signaling_load.csv")
stress      = load_csv("teletraffic_stress_sweep.csv")
erlang_c    = load_csv("teletraffic_erlang_curves.csv")
trunk_sum   = load_csv("teletraffic_trunk_summary.csv")
util_annual = load_csv("forecasting_utilisation_annual.csv")
upgrade_plan= load_csv("forecasting_upgrade_plan.csv")
erl_site    = load_csv("forecasting_erlang_per_site.csv")
erl_trunk   = load_csv("forecasting_trunk_erlang.csv")
traffic_mx  = load_csv("traffic_matrix.csv")
bw_sweep    = load_csv("traffic_stress_bandwidth_sweep.csv")
wireless    = load_json("wireless_results.json")

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📡 TELE 527")
    st.markdown("**District Telehealth Network**  \nGroup 1 · BIUST")
    st.divider()

    page = st.radio("Navigate", [
        "🏠 Overview",
        "🗺️ Network Map",
        "📊 QoS Metrics",
        "🔥 Stress & Demo",
        "📈 Forecast & Upgrades",
        "📡 Wireless & Backhaul",
        "🔀 Routing & Signaling (S4)",
    ])

    st.divider()
    auto_refresh = st.toggle("🔄 Auto-refresh (30 s)", value=False)
    if st.button("Refresh now"):
        st.cache_data.clear()
        st.rerun()

    if "S4" in page:
        st.divider()
        st.markdown("### 📂 Student 4 files")
        s4_routing = st.file_uploader("routing_table.csv",      type="csv")
        s4_signal  = st.file_uploader("signaling_model.json",   type="json")
        s4_failure = st.file_uploader("failure_scenarios.csv",  type="csv")
    else:
        s4_routing = s4_signal = s4_failure = None

    st.divider()
    st.caption(f"⏱ {datetime.now().strftime('%H:%M:%S')}")
    st.caption("Student 5 — Thebe Ratsatsi")

if auto_refresh:
    time.sleep(30)
    st.rerun()

# ═══════════════════════════════════════════════════════════════
# PAGE: OVERVIEW
# ═══════════════════════════════════════════════════════════════
if page == "🏠 Overview":
    st.title("📡 District Telehealth & Emergency Network — QoS Dashboard")
    st.caption(f"TELE 527 · Group 1 · Student 5  |  {datetime.now().strftime('%A %d %B %Y, %H:%M:%S')}")

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Sites",          "5",     "BS1–BS5 clinics")
    c2.metric("Core routers",   "2",     "CR-1 primary · CR-2 backup")
    c3.metric("Telemetry P95",  "8 ms",  "Target 50 ms ✅")
    c4.metric("Voice blocking", "0.62%", "Target < 2% ✅")
    c5.metric("Video P95",      "8 ms",  "Target 150 ms ✅")
    c6.metric("Stress break",   "1.5×",  "Voice fails first ⚠️")

    st.divider()
    col1,col2,col3 = st.columns(3)
    specs = [("Telemetry P95 Delay",8,50,"ms"),
             ("Voice Blocking Prob.",0.62,2.0,"%"),
             ("Video P95 Delay",8,150,"ms")]
    for col,(title,val,tgt,unit) in zip([col1,col2,col3],specs):
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=val,
            title={"text":title,"font":{"size":13}},
            gauge={"axis":{"range":[0,tgt],"tickfont":{"size":9}},
                   "bar":{"color":C["green"],"thickness":0.25},
                   "steps":[{"range":[0,tgt*0.6],"color":"#d1fae5"},
                             {"range":[tgt*0.6,tgt*0.85],"color":"#fef3c7"},
                             {"range":[tgt*0.85,tgt],"color":"#fee2e2"}],
                   "threshold":{"line":{"color":C["red"],"width":3},"thickness":0.8,"value":tgt}},
            number={"suffix":f" {unit}","font":{"size":22}}))
        fig.update_layout(height=210,margin=dict(t=50,b=0,l=20,r=20))
        col.plotly_chart(fig,use_container_width=True)
        col.success(f"✅ PASS — target {tgt} {unit}")

    st.divider()
    col1,col2 = st.columns(2)
    with col1:
        st.subheader("QoS headroom radar")
        cats = ["Telemetry delay","Voice blocking","Video delay",
                "Signaling delay","Link margin","Util headroom"]
        vals = [16,31,5,28,74,40]
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=vals+[vals[0]],theta=cats+[cats[0]],
            fill='toself',fillcolor='rgba(79,110,247,0.12)',
            line=dict(color=C["blue"],width=2.5),name="% of target used"))
        fig.add_trace(go.Scatterpolar(r=[100]*7,theta=cats+[cats[0]],
            line=dict(color=C["red"],width=1,dash="dot"),
            fillcolor='rgba(0,0,0,0)',name="100% = at limit"))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True,range=[0,110])),
            showlegend=True,height=330,margin=dict(t=20,b=10),
            legend=dict(orientation="h",y=-0.08))
        st.plotly_chart(fig,use_container_width=True)

    with col2:
        st.subheader("5-year utilisation forecast")
        years = util_annual["year"].tolist()
        utils = (util_annual["utilisation"]*100).round(1).tolist()
        pt_c  = [C["green"] if u<70 else (C["amber"] if u<90 else C["red"]) for u in utils]
        fig = go.Figure()
        fig.add_traces([
            go.Scatter(x=years,y=utils,mode='lines+markers',
                line=dict(color=C["blue"],width=2.5),
                marker=dict(color=pt_c,size=11,line=dict(color="#fff",width=2)),
                name="Utilisation %"),
            go.Scatter(x=years,y=[70]*len(years),mode='lines',
                line=dict(color=C["amber"],dash="dash",width=1.5),name="Plan 70%"),
            go.Scatter(x=years,y=[90]*len(years),mode='lines',
                line=dict(color=C["red"],dash="dash",width=1.5),name="Upgrade 90%"),
            go.Scatter(x=years,y=[100]*len(years),mode='lines',
                line=dict(color=C["gray"],dash="dot",width=1),name="Capacity"),
        ])
        fig.update_layout(height=330,yaxis=dict(title="%",range=[0,135]),
            xaxis=dict(title="Year",tickvals=years),
            legend=dict(orientation="h",y=-0.2,font=dict(size=11)),
            margin=dict(t=10,b=10),hovermode="x unified")
        st.plotly_chart(fig,use_container_width=True)

    st.subheader("Upgrade timeline")
    uc1,uc2,uc3,uc4 = st.columns(4)
    upgrades = [
        ("Year 1.1","Plan","Begin procurement for backhaul upgrade","#fef3c7","#92400e"),
        ("Year 2.0","Expand","Trunk circuits 9 → 10 (Erlang KPI)","#dbeafe","#1e40af"),
        ("Year 2.9","Upgrade","Backhaul 100 → 200 Mbps","#fee2e2","#991b1b"),
        ("Year 3.0","Expand","Per-site circuits 4 → 5","#dbeafe","#1e40af"),
    ]
    for col,(yr,phase,action,bg,tc) in zip([uc1,uc2,uc3,uc4],upgrades):
        col.markdown(f"""<div style='background:{bg};border-radius:10px;padding:14px 16px;'>
            <div style='font-size:18px;font-weight:700;color:{tc};'>{yr}</div>
            <div style='font-size:12px;font-weight:600;color:{tc};margin:3px 0 5px;'>{phase}</div>
            <div style='font-size:12px;color:{tc};'>{action}</div>
            </div>""",unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# PAGE: NETWORK MAP
# ═══════════════════════════════════════════════════════════════
elif page == "🗺️ Network Map":
    st.title("🗺️ Network Map — Palapye District, Botswana")
    st.caption("Live Google Maps · Click any marker for full site details · Use layer controls to toggle links")

    col1,col2,col3,col4 = st.columns(4)
    show_primary  = col1.checkbox("Primary links (solid blue)",  value=True)
    show_backup   = col2.checkbox("Backup links (dashed purple)", value=True)
    show_coverage = col3.checkbox("Coverage radius (2.16 km)",   value=False)
    map_tile      = col4.selectbox("Map style",
        ["OpenStreetMap","CartoDB positron","CartoDB dark_matter","Stamen Terrain"])

    center_lat = sum(n["lat"] for n in NODES.values())/len(NODES)
    center_lon = sum(n["lon"] for n in NODES.values())/len(NODES)

    m = folium.Map(location=[center_lat,center_lon],zoom_start=9,
                   tiles=map_tile,control_scale=True)

    # Feature groups
    lg_pri  = folium.FeatureGroup(name="Primary links  (CR-1)", show=show_primary)
    lg_bkp  = folium.FeatureGroup(name="Backup links   (CR-2)", show=show_backup)
    lg_bb   = folium.FeatureGroup(name="Backbone CR-1↔CR-2",   show=True)
    lg_bs   = folium.FeatureGroup(name="Base stations (clinics)",show=True)
    lg_cr   = folium.FeatureGroup(name="Core routers",          show=True)
    lg_cov  = folium.FeatureGroup(name="Coverage radius",       show=show_coverage)

    # Backbone
    n1,n2 = NODES["CR-1"],NODES["CR-2"]
    folium.PolyLine([[n1["lat"],n1["lon"]],[n2["lat"],n2["lon"]]],
        color="#f59e0b",weight=4,dash_array="8 6",opacity=0.95,
        tooltip="Backbone CR-1↔CR-2 | 13 GHz microwave | 500 Mbps | 0.5 ms").add_to(lg_bb)

    # Primary links
    for src,dst in LINKS_PRIMARY:
        a,b = NODES[src],NODES[dst]
        folium.PolyLine([[a["lat"],a["lon"]],[b["lat"],b["lon"]]],
            color="#4f6ef7",weight=2.5,opacity=0.8,
            tooltip=f"{src}→{dst} | 7 GHz | 100 Mbps | {a.get('delay_primary_ms','?')} ms").add_to(lg_pri)

    # Backup links
    for src,dst in LINKS_BACKUP:
        a,b = NODES[src],NODES[dst]
        folium.PolyLine([[a["lat"],a["lon"]],[b["lat"],b["lon"]]],
            color="#8b5cf6",weight=1.5,dash_array="6 8",opacity=0.6,
            tooltip=f"{src}→{dst} (backup) | {a.get('delay_backup_ms','?')} ms").add_to(lg_bkp)

    # Coverage circles
    for nid,n in NODES.items():
        if n["type"]=="bs":
            folium.Circle(location=[n["lat"],n["lon"]],radius=2163,
                color="#059669",fill=True,fill_opacity=0.07,weight=1.5,opacity=0.45,
                tooltip=f"{nid} coverage: 2.16 km").add_to(lg_cov)

    # Core router markers
    for nid,n in NODES.items():
        if n["type"] in ("core_primary","core_backup"):
            ic = "blue" if n["type"]=="core_primary" else "purple"
            pop = f"""<div style='font-family:sans-serif;min-width:230px;'>
              <div style='font-size:15px;font-weight:700;color:{"#1e40af" if ic=="blue" else "#5b21b6"};margin-bottom:6px;'>🖥️ {nid}</div>
              <div style='font-size:13px;font-weight:600;'>{n['label']}</div>
              <div style='font-size:11px;color:#6b7280;margin:4px 0 8px;'>{n['role']}</div>
              <table style='font-size:12px;width:100%;'>
                <tr><td style='color:#6b7280;'>Latitude</td><td style='text-align:right;'>{n['lat']:.4f}°</td></tr>
                <tr><td style='color:#6b7280;'>Longitude</td><td style='text-align:right;'>{n['lon']:.4f}°</td></tr>
                <tr><td style='color:#6b7280;'>Backbone link</td>
                    <td style='text-align:right;'>{'500 Mbps · 0.5 ms' if nid=='CR-1' else 'LTE backup · 45 ms'}</td></tr>
              </table></div>"""
            folium.Marker([n["lat"],n["lon"]],
                popup=folium.Popup(pop,max_width=260),
                tooltip=f"{'🔵' if ic=='blue' else '🟣'} {nid} — {n['label']}  (click for details)",
                icon=folium.Icon(color=ic,icon="server",prefix="fa")).add_to(lg_cr)

    # Base station markers
    for nid,n in NODES.items():
        if n["type"]=="bs":
            pop = f"""<div style='font-family:sans-serif;min-width:250px;'>
              <div style='font-size:15px;font-weight:700;color:#065f46;margin-bottom:6px;'>📡 {nid}</div>
              <div style='font-size:13px;font-weight:600;'>{n['label']}</div>
              <div style='font-size:11px;color:#6b7280;margin:4px 0 10px;'>{n['role']}</div>
              <table style='font-size:12px;width:100%;border-collapse:collapse;'>
                <tr style='background:#f0fdf4;'><td colspan='2' style='padding:4px 6px;font-weight:600;color:#065f46;'>📍 Location</td></tr>
                <tr><td style='padding:3px 6px;color:#6b7280;'>Latitude</td><td style='text-align:right;'>{n['lat']:.4f}°</td></tr>
                <tr><td style='padding:3px 6px;color:#6b7280;'>Longitude</td><td style='text-align:right;'>{n['lon']:.4f}°</td></tr>
                <tr style='background:#eff6ff;'><td colspan='2' style='padding:4px 6px;font-weight:600;color:#1e40af;'>📶 Backhaul link</td></tr>
                <tr><td style='padding:3px 6px;color:#6b7280;'>Primary delay</td><td style='text-align:right;'>{n.get("delay_primary_ms","?")} ms → CR-1</td></tr>
                <tr><td style='padding:3px 6px;color:#6b7280;'>Backup delay</td><td style='text-align:right;'>{n.get("delay_backup_ms","?")} ms → CR-2</td></tr>
                <tr><td style='padding:3px 6px;color:#6b7280;'>Link margin</td><td style='text-align:right;'>{n.get("link_margin_db","?")} dB</td></tr>
                <tr><td style='padding:3px 6px;color:#6b7280;'>RX signal</td><td style='text-align:right;'>{n.get("rx_dbm","?")} dBm</td></tr>
                <tr><td style='padding:3px 6px;color:#6b7280;'>Utilisation</td><td style='text-align:right;'>2.1%</td></tr>
                <tr style='background:#f0fdf4;'><td colspan='2' style='padding:4px 6px;font-weight:600;color:#065f46;'>📊 QoS status</td></tr>
                <tr><td style='padding:3px 6px;color:#6b7280;'>Voice blocking</td>
                    <td style='text-align:right;color:#059669;font-weight:600;'>{n.get("blocking_pct","?")}% ✅</td></tr>
                <tr><td style='padding:3px 6px;color:#6b7280;'>Setup delay</td>
                    <td style='text-align:right;color:#059669;font-weight:600;'>{n.get("setup_delay_ms","?")} ms ✅</td></tr>
                <tr><td style='padding:3px 6px;color:#6b7280;'>Telemetry P95</td>
                    <td style='text-align:right;color:#059669;font-weight:600;'>≤ 9 ms ✅</td></tr>
                <tr><td style='padding:3px 6px;color:#6b7280;'>Video P95</td>
                    <td style='text-align:right;color:#059669;font-weight:600;'>≤ 9 ms ✅</td></tr>
              </table></div>"""
            folium.Marker([n["lat"],n["lon"]],
                popup=folium.Popup(pop,max_width=280),
                tooltip=f"📡 {nid} — {n['label']}  (click for QoS details)",
                icon=folium.Icon(color="green",icon="signal",prefix="fa")).add_to(lg_bs)

    for lg in [lg_pri,lg_bkp,lg_bb,lg_bs,lg_cr,lg_cov]:
        lg.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    plugins.Fullscreen().add_to(m)
    plugins.MiniMap(toggle_display=True,zoom_level_offset=-5).add_to(m)
    plugins.MousePosition(position="bottomleft").add_to(m)

    map_data = st_folium(m, width="100%", height=560,
                         returned_objects=["last_object_clicked"])

    # ── Click detail panel ──
    if map_data and map_data.get("last_object_clicked"):
        clk = map_data["last_object_clicked"]
        clat,clon = clk.get("lat"),clk.get("lng")
        if clat and clon:
            nearest = min(NODES.items(),
                key=lambda kv:(kv[1]["lat"]-clat)**2+(kv[1]["lon"]-clon)**2)
            nid,nd = nearest
            st.divider()
            st.subheader(f"📍 {nid} — {nd['label']}")
            if nd["type"]=="bs":
                r1,r2,r3,r4,r5,r6 = st.columns(6)
                r1.metric("Latitude",        f"{nd['lat']:.4f}°")
                r2.metric("Longitude",       f"{nd['lon']:.4f}°")
                r3.metric("Primary delay",   f"{nd.get('delay_primary_ms','?')} ms")
                r4.metric("Backup delay",    f"{nd.get('delay_backup_ms','?')} ms")
                r5.metric("Voice blocking",  f"{nd.get('blocking_pct','?')}%","✅ < 2%")
                r6.metric("Setup delay",     f"{nd.get('setup_delay_ms','?')} ms","✅ < 50ms")
            else:
                r1,r2,r3 = st.columns(3)
                r1.metric("Latitude",  f"{nd['lat']:.4f}°")
                r2.metric("Longitude", f"{nd['lon']:.4f}°")
                r3.metric("Role",      nd["role"])

    st.divider()
    st.subheader("Node coordinates table")
    rows=[]
    for nid,n in NODES.items():
        rows.append({"Node":nid,"Label":n["label"],
            "Latitude":f"{n['lat']:.4f}°","Longitude":f"{n['lon']:.4f}°",
            "Type":n["type"],
            "Primary delay":f"{n.get('delay_primary_ms','—')} ms" if n["type"]=="bs" else "—",
            "Backup delay": f"{n.get('delay_backup_ms','—')} ms"  if n["type"]=="bs" else "—",
            "Link margin":  f"{n.get('link_margin_db','—')} dB"   if n["type"]=="bs" else "—"})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)


# ═══════════════════════════════════════════════════════════════
# PAGE: QOS METRICS
# ═══════════════════════════════════════════════════════════════
elif page == "📊 QoS Metrics":
    st.title("📊 QoS Metrics — Per Site")
    st.success("✅ All QoS targets are met across all 5 sites under baseline load.")

    tab1,tab2,tab3 = st.tabs(["Delay KPIs","Voice Blocking (Erlang B)","Signaling KPIs"])

    with tab1:
        col1,col2 = st.columns(2)
        with col1:
            d = delay_kpis[["site","service_class","p95_delay_ms","kpi_target_ms","kpi_met"]].copy()
            d.columns=["Site","Service","P95 (ms)","Target (ms)","Pass?"]
            d["Pass?"]=d["Pass?"].map({True:"✅ PASS",False:"❌ FAIL"})
            st.dataframe(d,use_container_width=True,hide_index=True)
        with col2:
            fig=go.Figure()
            for svc,clr in [("telemetry",C["blue"]),("video",C["purple"])]:
                df=delay_kpis[delay_kpis["service_class"]==svc]
                fig.add_trace(go.Bar(name=svc.capitalize(),x=df["site"],y=df["p95_delay_ms"],
                    marker_color=clr,text=df["p95_delay_ms"].astype(str)+" ms",textposition="outside"))
            fig.add_hline(y=50, line_dash="dash",line_color=C["amber"],annotation_text="Tel 50ms")
            fig.add_hline(y=150,line_dash="dash",line_color=C["red"],  annotation_text="Vid 150ms")
            fig.update_layout(barmode="group",height=320,yaxis=dict(title="P95 (ms)",range=[0,180]),
                legend=dict(orientation="h",y=1.05),margin=dict(t=10))
            st.plotly_chart(fig,use_container_width=True)

    with tab2:
        col1,col2 = st.columns(2)
        dim_bs=dim_table[dim_table["site"].str.startswith("BS")].copy()
        with col1:
            d2=dim_bs[["site","offered_load_erl","channels_required","achieved_blocking","target_blocking","kpi_met"]].copy()
            d2["achieved_blocking"]=(d2["achieved_blocking"]*100).round(3).astype(str)+"%"
            d2["target_blocking"]=(d2["target_blocking"]*100).astype(str)+"%"
            d2["kpi_met"]=d2["kpi_met"].map({True:"✅",False:"❌"})
            d2.columns=["Site","Offered (Erl)","Circuits","Blocking","Target","Pass?"]
            st.dataframe(d2,use_container_width=True,hide_index=True)
            tn=trunk_sum.iloc[0]
            st.metric("Trunk blocking",f"{tn['achieved_blocking']*100:.3f}%","✅ < 2% · 9 circuits · saves 11")
        with col2:
            fig=go.Figure(go.Bar(x=dim_bs["site"],y=dim_bs["achieved_blocking"]*100,
                marker_color=C["green"],
                text=[f"{v*100:.3f}%" for v in dim_bs["achieved_blocking"]],
                textposition="outside"))
            fig.add_hline(y=2.0,line_dash="dash",line_color=C["red"],annotation_text="KPI 2%")
            fig.update_layout(height=300,yaxis=dict(title="Blocking (%)",range=[0,3]),margin=dict(t=10))
            st.plotly_chart(fig,use_container_width=True)

        st.subheader("Erlang B curves")
        svc=st.selectbox("Traffic class",erlang_c["service_class"].unique())
        df_e=erlang_c[erlang_c["service_class"]==svc]
        fig=go.Figure(go.Scatter(x=df_e["circuits_N"],y=df_e["blocking_prob"]*100,
            mode="lines+markers",line=dict(color=C["blue"],width=2),
            hovertemplate="N=%{x} → blocking=%{y:.5f}%<extra></extra>"))
        fig.add_hline(y=2,line_dash="dash",line_color=C["red"],annotation_text="KPI 2%")
        fig.update_layout(height=280,xaxis_title="Circuits (N)",yaxis_title="Blocking (%)",yaxis_type="log")
        st.plotly_chart(fig,use_container_width=True)

    with tab3:
        col1,col2=st.columns(2)
        with col1:
            d3=sig_load.copy()
            d3["kpi_met"]=d3["kpi_met"].map({True:"✅ PASS",False:"❌ FAIL"})
            d3.columns=["Site","BHCA","Msgs/hr","Load (bps)","Setup delay (ms)","Target (ms)","Pass?"]
            st.dataframe(d3,use_container_width=True,hide_index=True)
            st.caption("Total BHCA: 115 · Total signaling: 51.1 bps · Worst setup: 14 ms @ BS3/BS5")
        with col2:
            fig=go.Figure(go.Bar(x=sig_load["site"],y=sig_load["call_setup_delay_ms"],
                marker_color=C["blue"],
                text=sig_load["call_setup_delay_ms"].astype(str)+" ms",textposition="outside"))
            fig.add_hline(y=50,line_dash="dash",line_color=C["red"],annotation_text="Target 50ms")
            fig.update_layout(height=300,yaxis=dict(title="Setup delay (ms)",range=[0,65]),margin=dict(t=10))
            st.plotly_chart(fig,use_container_width=True)


# ═══════════════════════════════════════════════════════════════
# PAGE: STRESS & DEMO
# ═══════════════════════════════════════════════════════════════
elif page == "🔥 Stress & Demo":
    st.title("🔥 Stress Analysis & Demo Scenario")
    st.warning("⚠️ Voice blocking fails at **1.5× load** — this is your demo degradation scenario.")

    alpha = st.slider("Load multiplier (α)",1.0,5.0,1.0,0.5)
    row = stress[stress["load_multiplier"]==alpha]
    if not row.empty:
        r=row.iloc[0]
        vb=r["voice_blocking"]*100
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Voice offered",f"{r['voice_offered_erl']:.3f} Erl")
        c2.metric("Voice blocking",f"{vb:.2f}%",
            "❌ FAIL — exceeds 2%" if not r["voice_kpi_met"] else "✅ PASS",
            delta_color="inverse")
        c3.metric("Telemetry P95",f"{r['telemetry_p95_ms']} ms",
            "✅ PASS" if r["telemetry_kpi_met"] else "❌ FAIL")
        c4.metric("Video P95",f"{r['video_p95_ms']} ms",
            "✅ PASS" if r["video_kpi_met"] else "❌ FAIL")

    st.divider()
    col1,col2=st.columns([3,2])
    with col1:
        st.subheader("Stress sweep — all KPIs")
        fig=make_subplots(specs=[[{"secondary_y":True}]])
        fig.add_trace(go.Scatter(x=stress["load_multiplier"],y=stress["voice_blocking"]*100,
            name="Voice blocking (%)",line=dict(color=C["red"],width=2.5),
            fill='tozeroy',fillcolor='rgba(220,38,38,0.08)'),secondary_y=False)
        fig.add_trace(go.Scatter(x=stress["load_multiplier"],y=stress["telemetry_p95_ms"],
            name="Telemetry P95 (ms)",line=dict(color=C["blue"],dash="dash",width=2)),secondary_y=True)
        fig.add_trace(go.Scatter(x=stress["load_multiplier"],y=stress["video_p95_ms"],
            name="Video P95 (ms)",line=dict(color=C["purple"],dash="dash",width=2)),secondary_y=True)
        fig.add_hline(y=2.0,line_dash="dot",line_color=C["amber"],
            annotation_text="Voice KPI limit 2%",secondary_y=False)
        fig.add_vline(x=1.5,line_dash="dot",line_color=C["red"],
            annotation_text="Break point α=1.5")
        fig.update_yaxes(title_text="Voice blocking (%)",secondary_y=False)
        fig.update_yaxes(title_text="Delay (ms)",range=[0,60],secondary_y=True)
        fig.update_layout(height=360,hovermode="x unified",xaxis_title="Load multiplier (α)",
            legend=dict(orientation="h",y=-0.2),margin=dict(t=10))
        st.plotly_chart(fig,use_container_width=True)

    with col2:
        st.subheader("Pass/fail table")
        d=stress[["load_multiplier","voice_blocking","voice_kpi_met",
                   "telemetry_kpi_met","video_kpi_met","all_kpis_met"]].copy()
        d["voice_blocking"]=(d["voice_blocking"]*100).round(2).astype(str)+"%"
        for c in ["voice_kpi_met","telemetry_kpi_met","video_kpi_met","all_kpis_met"]:
            d[c]=d[c].map({True:"✅",False:"❌"})
        d.columns=["α","Voice blk","Voice","Tel","Vid","All"]
        st.dataframe(d,use_container_width=True,hide_index=True,height=330)
        st.error("**Break point: α = 1.5×**  \nVoice 2.18% > 2% target  \nFix: N 4 → 5 circuits")


# ═══════════════════════════════════════════════════════════════
# PAGE: FORECAST & UPGRADES
# ═══════════════════════════════════════════════════════════════
elif page == "📈 Forecast & Upgrades":
    st.title("📈 Traffic Forecast & Upgrade Plan")

    col1,col2=st.columns(2)
    with col1:
        st.subheader("Utilisation forecast — 5 years")
        years=util_annual["year"].tolist()
        utils=(util_annual["utilisation"]*100).round(1).tolist()
        pt_c=[C["green"] if u<70 else (C["amber"] if u<90 else C["red"]) for u in utils]
        fig=go.Figure()
        fig.add_traces([
            go.Scatter(x=years,y=utils,mode='lines+markers',
                line=dict(color=C["blue"],width=2.5),
                marker=dict(color=pt_c,size=12,line=dict(color="#fff",width=2)),
                name="Utilisation"),
            go.Scatter(x=years,y=[70]*len(years),mode='lines',
                line=dict(color=C["amber"],dash="dash",width=1.5),name="Plan 70%"),
            go.Scatter(x=years,y=[90]*len(years),mode='lines',
                line=dict(color=C["red"],dash="dash",width=1.5),name="Upgrade 90%"),
            go.Scatter(x=years,y=[100]*len(years),mode='lines',
                line=dict(color=C["gray"],dash="dot",width=1),name="Capacity"),
        ])
        fig.update_layout(height=320,yaxis=dict(title="%",range=[0,135]),
            xaxis=dict(title="Year",tickvals=years),
            legend=dict(orientation="h",y=-0.2),margin=dict(t=10),hovermode="x unified")
        st.plotly_chart(fig,use_container_width=True)

        d=util_annual.copy()
        d["utilisation"]=(d["utilisation"]*100).round(1).astype(str)+"%"
        d["traffic_mbps"]=d["traffic_mbps"].round(1).astype(str)+" Mbps"
        d.columns=["Year","Utilisation","Traffic","Status"]
        st.dataframe(d,use_container_width=True,hide_index=True)

    with col2:
        st.subheader("Upgrade plan")
        for _,row in upgrade_plan.iterrows():
            bg="#fee2e2" if "Action" in str(row["phase"]) else ("#fef3c7" if "Planning" in str(row["phase"]) else "#dbeafe")
            tc="#991b1b" if "Action" in str(row["phase"]) else ("#92400e" if "Planning" in str(row["phase"]) else "#1e40af")
            st.markdown(f"""<div style='background:{bg};border-radius:10px;padding:14px 16px;margin-bottom:10px;'>
              <div style='font-size:18px;font-weight:700;color:{tc};'>Year {row['trigger_year']}</div>
              <div style='font-size:12px;font-weight:600;color:{tc};margin:3px 0 5px;'>{row['phase']}</div>
              <div style='font-size:12px;color:{tc};'>{row['action']}</div>
              </div>""",unsafe_allow_html=True)

    st.divider()
    col1,col2=st.columns(2)
    with col1:
        st.subheader("Voice blocking — per site forecast")
        clrs=[C["green"] if m else C["red"] for m in erl_site["blocking_kpi_met"]]
        fig=go.Figure(go.Bar(x=erl_site["year"],y=erl_site["blocking_prob"]*100,
            marker_color=clrs,text=(erl_site["blocking_prob"]*100).round(2).astype(str)+"%",
            textposition="outside"))
        fig.add_hline(y=2,line_dash="dash",line_color=C["red"],annotation_text="KPI 2%")
        fig.update_layout(height=280,xaxis_title="Year",yaxis_title="Blocking (%)",yaxis=dict(range=[0,7]))
        st.plotly_chart(fig,use_container_width=True)

    with col2:
        st.subheader("Voice blocking — trunk forecast")
        clrs=[C["green"] if m else C["red"] for m in erl_trunk["kpi_met"]]
        fig=go.Figure(go.Bar(x=erl_trunk["year"],y=erl_trunk["blocking_prob"]*100,
            marker_color=clrs,text=(erl_trunk["blocking_prob"]*100).round(2).astype(str)+"%",
            textposition="outside"))
        fig.add_hline(y=2,line_dash="dash",line_color=C["red"],annotation_text="KPI 2%")
        fig.update_layout(height=280,xaxis_title="Year",yaxis_title="Blocking (%)",yaxis=dict(range=[0,18]))
        st.plotly_chart(fig,use_container_width=True)


# ═══════════════════════════════════════════════════════════════
# PAGE: WIRELESS & BACKHAUL
# ═══════════════════════════════════════════════════════════════
elif page == "📡 Wireless & Backhaul":
    st.title("📡 Wireless & Backhaul Analysis")
    st.success("✅ All backhaul links pass primary and backup link budgets including rain attenuation margin.")

    bh=wireless.get("backhaul",[])
    df_bh=pd.DataFrame(bh)

    c1,c2,c3,c4=st.columns(4)
    c1.metric("All primary links","PASS ✅")
    c2.metric("All backup links", "PASS ✅")
    c3.metric("Best primary margin","42.0 dB (BS4)")
    c4.metric("Worst after rain",   "33.2 dB (adequate)")

    st.subheader("Backhaul link budget")
    disp=df_bh[["site","primary_rx_dbm","primary_margin_db","rain_attenuation_db",
                 "margin_after_rain_db","backup_margin_db","link_utilisation","link_status"]].copy()
    disp["link_utilisation"]=(disp["link_utilisation"]*100).round(2).astype(str)+"%"
    disp["link_status"]=disp["link_status"].map(lambda x:"✅ Good" if x=="good" else x)
    disp.columns=["Site","Primary RX (dBm)","Primary Margin (dB)","Rain Atten (dB)",
                   "Margin after rain (dB)","Backup Margin (dB)","Utilisation","Status"]
    st.dataframe(disp,use_container_width=True,hide_index=True)

    col1,col2=st.columns(2)
    with col1:
        fig=go.Figure()
        sites=df_bh["site"].tolist()
        fig.add_trace(go.Bar(name="Primary margin",    x=sites,y=df_bh["primary_margin_db"],  marker_color=C["blue"]))
        fig.add_trace(go.Bar(name="Backup margin",     x=sites,y=df_bh["backup_margin_db"],   marker_color=C["purple"]))
        fig.add_trace(go.Bar(name="After rain margin", x=sites,y=df_bh["margin_after_rain_db"],marker_color=C["green"]))
        fig.update_layout(barmode="group",height=300,yaxis_title="Margin (dB)",
            legend=dict(orientation="h",y=1.05),margin=dict(t=10))
        st.plotly_chart(fig,use_container_width=True)

    with col2:
        cov=wireless.get("site_link_budgets",[])
        if cov:
            df_c=pd.DataFrame(cov)
            st.dataframe(df_c[["site_id","received_signal_dbm","path_loss_db",
                                "link_margin_db","coverage_radius_km","link_quality"]]
                .rename(columns={"site_id":"Site","received_signal_dbm":"RX (dBm)",
                                  "path_loss_db":"Path loss","link_margin_db":"Margin (dB)",
                                  "coverage_radius_km":"Radius (km)","link_quality":"Quality"}),
                use_container_width=True,hide_index=True)
        rc1,rc2,rc3=st.columns(3)
        rc1.metric("Reuse factor (omni)","4")
        rc2.metric("Channels/cell (sect.)","4.0")
        rc3.metric("Capacity gain","12×")


# ═══════════════════════════════════════════════════════════════
# PAGE: ROUTING & SIGNALING (STUDENT 4)
# ═══════════════════════════════════════════════════════════════
elif page == "🔀 Routing & Signaling (S4)":
    st.title("🔀 Routing & Signaling — Student 4 Integration")

    files_uploaded = any([s4_routing, s4_signal, s4_failure])

    if files_uploaded:
        if s4_routing:
            df_r=pd.read_csv(s4_routing)
            st.success("✅ routing_table.csv loaded")
            st.subheader("Routing table")
            st.dataframe(df_r,use_container_width=True,hide_index=True)
            if "end_to_end_delay_ms" in df_r.columns:
                fig=go.Figure(go.Bar(x=df_r.get("path_id",df_r.index),y=df_r["end_to_end_delay_ms"],
                    marker_color=C["blue"],text=df_r["end_to_end_delay_ms"].astype(str)+" ms",textposition="outside"))
                fig.add_hline(y=50,line_dash="dash",line_color=C["red"],annotation_text="Telemetry target 50ms")
                fig.update_layout(height=260,yaxis_title="End-to-end delay (ms)",margin=dict(t=10))
                st.plotly_chart(fig,use_container_width=True)
            if "utilisation_pct" in df_r.columns:
                fig2=go.Figure(go.Bar(x=df_r.get("path_id",df_r.index),y=df_r["utilisation_pct"],
                    marker_color=C["purple"],text=df_r["utilisation_pct"].astype(str)+"%",textposition="outside"))
                fig2.add_hline(y=70,line_dash="dash",line_color=C["amber"],annotation_text="Plan 70%")
                fig2.add_hline(y=90,line_dash="dash",line_color=C["red"],annotation_text="Upgrade 90%")
                fig2.update_layout(height=260,yaxis_title="Link utilisation (%)",margin=dict(t=10))
                st.plotly_chart(fig2,use_container_width=True)

        if s4_signal:
            ds=json.load(s4_signal)
            st.success("✅ signaling_model.json loaded")
            c1,c2,c3,c4=st.columns(4)
            c1.metric("Call setup delay",   f"{ds.get('call_setup_delay_ms','—')} ms")
            c2.metric("Signaling load/node",f"{ds.get('signaling_load_per_node','—')}")
            c3.metric("Reroute delay",      f"{ds.get('failure_reroute_delay_ms','—')} ms")
            c4.metric("Degraded paths",     str(len(ds.get("degraded_backhaul_paths",[]))))
            if ds.get("degraded_backhaul_paths"):
                st.warning(f"⚠️ Degraded paths: {', '.join(ds['degraded_backhaul_paths'])}")

        if s4_failure:
            df_f=pd.read_csv(s4_failure)
            st.success("✅ failure_scenarios.csv loaded")
            st.subheader("Failure & rerouting scenarios")
            st.dataframe(df_f,use_container_width=True,hide_index=True)

    else:
        st.info("📂 Upload Student 4 files in the sidebar to populate this section.")
        st.divider()

        tab1,tab2,tab3=st.tabs(["routing_table.csv","signaling_model.json","failure_scenarios.csv"])
        with tab1:
            st.markdown("**Required columns — use these exact names:**")
            ex=pd.DataFrame({
                "path_id":             ["P01","P02","P03","P04","P05"],
                "source":              ["BS1","BS2","BS3","BS4","BS5"],
                "destination":         ["CR-1","CR-1","CR-1","CR-1","CR-1"],
                "hops":                [2,3,2,2,3],
                "end_to_end_delay_ms": [18,34,22,20,28],
                "utilisation_pct":     [62,74,55,48,70],
                "backup_path_id":      ["P01B","P02B","P03B","P04B","P05B"],
            })
            st.dataframe(ex,use_container_width=True,hide_index=True)
            st.caption("⚠️ Use BS1–BS5 and CR-1/CR-2 exactly to match site IDs across the project.")

        with tab2:
            st.code(json.dumps({
                "call_setup_delay_ms": 120,
                "signaling_load_per_node": 0.08,
                "failure_reroute_delay_ms": 340,
                "degraded_backhaul_paths": ["P02","P03"]
            },indent=2),language="json")

        with tab3:
            ex2=pd.DataFrame({
                "scenario":              ["CR-1 primary fail","BS2 link fail","Backbone fail"],
                "failed_component":      ["CR-1","BS2→CR-1","CR-1↔CR-2"],
                "reroute_path":          ["all→CR-2","BS2→CR-2","LTE bearer"],
                "reroute_delay_ms":      [340,24,45],
                "voice_blocking_impact": ["increase","none","increase"],
                "kpis_still_met":        [True,True,False],
            })
            st.dataframe(ex2,use_container_width=True,hide_index=True)

        st.divider()
        st.subheader("Preview — what this page shows once Student 4 files are uploaded")
        pc1,pc2,pc3=st.columns(3)
        pc1.markdown("**Routing analysis:**\n- End-to-end delay per path vs KPI\n- Link utilisation with trigger lines\n- Hop count per site")
        pc2.markdown("**Signaling model:**\n- Setup delay vs 50ms KPI\n- Signaling load per node\n- Reroute delay under failure")
        pc3.markdown("**Failure scenarios:**\n- Before/after KPI per scenario\n- Degraded path map\n- Voice & delay impact")

        st.divider()
        st.subheader("Signaling cross-check from Student 2 (already available)")
        d3=sig_load.copy()
        d3["kpi_met"]=d3["kpi_met"].map({True:"✅ PASS",False:"❌ FAIL"})
        d3.columns=["Site","BHCA","Msgs/hr","Load (bps)","Setup delay (ms)","Target (ms)","Pass?"]
        st.dataframe(d3,use_container_width=True,hide_index=True)
        st.caption("Student 4 will add routing paths, reroute logic, and failure scenarios to complete this section.")

"""
District Telehealth & Emergency Communication Network — Streamlit Dashboard
TELE 527 — Telecommunications Network and Infrastructures
Group 1 — Botswana International University of Science and Technology (BIUST)
"""

import streamlit as st
import yaml
import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from topology import load_config, build_topology, get_positions, draw_topology
except ImportError as e:
    st.warning(f"Could not import modules: {e}")

# Page configuration
st.set_page_config(
    page_title="District Telehealth Network",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏥 District Telehealth & Emergency Communication Network")
st.markdown("""
**TELE 527** — Telecommunications Network and Infrastructures  
Group 1 PBL Laboratory, BIUST
""")

# Load scenario configuration
@st.cache_data
def load_scenario():
    scenario_path = Path(__file__).parent / "scenario.yaml"
    return load_config(str(scenario_path))

try:
    scenario = load_scenario()
except FileNotFoundError:
    st.error("scenario.yaml not found. Please ensure the scenario file is in the project root.")
    st.stop()

# Sidebar navigation
st.sidebar.header("📊 Navigation")
page = st.sidebar.radio("Select Page", [
    "Dashboard Overview",
    "Network Topology",
    "Scenario Configuration",
    "Simulation Results",
    "About"
])

# Page: Dashboard Overview
if page == "Dashboard Overview":
    st.header("Dashboard Overview")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Sites", len(scenario['sites']))
    with col2:
        st.metric("Total Links", len(scenario['links']))
    with col3:
        st.metric("Load Multiplier Steps", len(scenario['simulation']['load_multiplier_steps']))
    
    st.subheader("Key Project Parameters")
    params = {
        "Random Seed": scenario['simulation']['random_seed'],
        "Growth Rate": f"{scenario['simulation']['growth_rate']*100:.1f}%",
        "Forecast Horizon": f"{scenario['simulation']['forecast_horizon_years']} years",
        "Load Multiplier Range": f"{scenario['simulation']['load_multiplier_range']}"
    }
    
    for key, value in params.items():
        st.write(f"**{key}:** {value}")

# Page: Network Topology
elif page == "Network Topology":
    st.header("Network Topology")
    st.markdown("""
    ### Topology 5 — North–South Dual-Core Architecture
    
    - **CR-1** (District Hospital) — primary core router, north position
    - **CR-2** (District Health Office) — secondary core router, south position
    - **BS1–BS5** — five community health clinics, dual-homed to both CR-1 and CR-2
    """)
    
    # Build NetworkX graph from scenario
    G = build_topology(scenario)
    pos = get_positions(G)
    
    # Visualization
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Draw network
    # Core routers in green, base stations in blue
    core_nodes = [n for n in G.nodes if G.nodes[n]['type'] == 'core_router']
    bs_nodes = [n for n in G.nodes if G.nodes[n]['type'] == 'base_station']
    
    nx.draw_networkx_nodes(G, pos, nodelist=core_nodes, 
                           node_color='#22c55e', node_size=1500, 
                           node_shape='o',
                           label='Core Router', ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=bs_nodes, 
                           node_color='#3b82f6', node_size=1000, 
                           node_shape='s',
                           label='Base Station', ax=ax)
    
    nx.draw_networkx_edges(G, pos, ax=ax, 
                          edge_color='gray', arrows=True, 
                          arrowsize=20, arrowstyle='->', 
                          width=2, alpha=0.6)
    
    nx.draw_networkx_labels(G, pos, font_size=9, font_weight='bold', ax=ax)
    
    ax.set_title("District Network Topology", fontsize=14, fontweight='bold')
    ax.set_xlabel("X Coordinate (km)")
    ax.set_ylabel("Y Coordinate (km)")
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    
    st.pyplot(fig)
    
    # Sites table
    st.subheader("Sites")
    sites_df = pd.DataFrame(scenario['sites'])
    st.dataframe(sites_df, use_container_width=True)
    
    # Links table
    st.subheader("Links")
    links_df = pd.DataFrame(scenario['links'])
    st.dataframe(links_df, use_container_width=True)

# Page: Scenario Configuration
elif page == "Scenario Configuration":
    st.header("Scenario Configuration")
    st.markdown("View the complete scenario.yaml configuration:")
    
    # Display YAML as formatted code
    st.code(yaml.dump(scenario, default_flow_style=False), language='yaml')

# Page: Simulation Results
elif page == "Simulation Results":
    st.header("Simulation Results")
    st.info("📊 Run simulation using main.py to generate results. Use this page to visualize outcomes.")
    
    st.subheader("Traffic Classes and KPI Targets")
    traffic_classes = {
        "Class": ["Telemetry", "Voice", "Video"],
        "Model": ["M/M/N Queue", "M/M/N/0 (Erlang B)", "M/M/N Queue"],
        "KPI Target": ["P95 delay ≤ 50 ms", "Blocking ≤ 2%", "P95 delay ≤ 150 ms"],
        "DSCP": ["EF (46)", "AF31 (26)", "AF21 (18)"],
        "Priority": ["Strict Priority Queue", "WFQ 30%", "WFQ 40%"]
    }
    
    st.dataframe(pd.DataFrame(traffic_classes), use_container_width=True)

# Page: About
elif page == "About":
    st.header("About This Project")
    
    st.subheader("📋 Project Overview")
    st.markdown("""
    This repository contains the complete Python simulation pipeline for the **District Telehealth 
    and Emergency Communication Network** — a cost-constrained district network designed to guarantee 
    performance for critical healthcare services during peak load and partial backhaul degradation.
    
    ### Core Engineering Question
    > *How do we design and validate a cost-constrained district network that guarantees performance 
    > for critical services during peak load and partial backhaul degradation?*
    """)
    
    st.subheader("👥 Group Members")
    members = {
        "Student": ["Atlang Zambezi", "Pako Kgosintwa", "Goitse Pihelo", "Tsotlhe Seiphepi", "Thebe Ratsatsi"],
        "Role": [
            "Network Architect",
            "Traffic & Teletraffic Lead",
            "Wireless Planning Lead",
            "Signaling & Routing Lead",
            "QoS & Data Networks Lead"
        ]
    }
    st.dataframe(pd.DataFrame(members), use_container_width=True)
    
    st.subheader("🎓 Course Information")
    st.write("**TELE 527** — Telecommunications Network and Infrastructures")
    st.write("**Program:** Python-Based Problem Based Learning (PBL) Laboratory")
    st.write("**Institution:** Botswana International University of Science and Technology (BIUST)")
    st.write("**Department:** Electrical, Computer and Telecommunications Engineering")
    st.write("**Semester:** 2, 2026")
    
    st.subheader("🔗 Repository Structure")
    st.code("""
tele527-pbl-group1/
├── scenario.yaml           # Configuration file
├── main.py                 # Main simulation entry point
├── app.py                  # This Streamlit dashboard
├── requirements.txt        # Python dependencies
├── src/                    # Source modules
├── figures/                # Generated plots
├── tests/                  # Test suite
└── report/                 # LaTeX report
    """, language='text')

st.sidebar.markdown("---")
st.sidebar.markdown("""
**Supervisors:**  
Prof. Abid Yahya  
Eng. Robin Tau
""")
st.sidebar.markdown("Semester 2, 2026")
