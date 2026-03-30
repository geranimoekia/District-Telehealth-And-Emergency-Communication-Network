import dash
from dash import html, dcc, Input, Output, State
import plotly.graph_objects as go
import random
import time
from collections import deque

# ── DMS helper
def dms(d, m, s, direction):
    dd = d + m/60 + s/3600
    return -dd if direction in ("S","W") else dd

# ── Network topology
SITES = [
    {"name":"CR-1","label":"District Hospital",      "lat":dms(22,59,59.19,"S"),"lon":dms(23,59,42.31,"E"),"channels":8,"tier":1,"type":"controller"},
    {"name":"CR-2","label":"District Health Office", "lat":dms(22,58,21.89,"S"),"lon":dms(23,56,45.85,"E"),"channels":8,"tier":1,"type":"controller"},
    {"name":"BS1", "label":"Clinic North-West",      "lat":dms(22,51,52.70,"S"),"lon":dms(23,49,42.34,"E"),"channels":4,"tier":2,"type":"bs"},
    {"name":"BS2", "label":"Clinic North-East",      "lat":dms(22,51,52.70,"S"),"lon":dms(24, 9,42.28,"E"),"channels":4,"tier":2,"type":"bs"},
    {"name":"BS3", "label":"Clinic South-West",      "lat":dms(23, 8, 5.68,"S"),"lon":dms(23,49,42.34,"E"),"channels":4,"tier":2,"type":"bs"},
    {"name":"BS4", "label":"Clinic South",           "lat":dms(23, 9,10.54,"S"),"lon":dms(23,59,42.31,"E"),"channels":4,"tier":2,"type":"bs"},
    {"name":"BS5", "label":"Clinic South-East",      "lat":dms(23, 8, 5.68,"S"),"lon":dms(24, 9,42.28,"E"),"channels":4,"tier":2,"type":"bs"},
]

LINKS = [
    {"source":"CR-1","target":"CR-2","type":"Fiber",     "capacity":16},
    {"source":"CR-1","target":"BS1", "type":"Microwave", "capacity":4},
    {"source":"CR-1","target":"BS2", "type":"Microwave", "capacity":4},
    {"source":"CR-2","target":"BS3", "type":"Microwave", "capacity":4},
    {"source":"CR-2","target":"BS4", "type":"Fiber",     "capacity":4},
    {"source":"CR-2","target":"BS5", "type":"Microwave", "capacity":4},
    {"source":"BS1", "target":"BS2", "type":"Microwave", "capacity":2},
    {"source":"BS3", "target":"BS4", "type":"Microwave", "capacity":2},
    {"source":"BS4", "target":"BS5", "type":"Microwave", "capacity":2},
]

SITE_MAP  = {s["name"]: s for s in SITES}
LINK_MAP  = {(lk["source"],lk["target"]): lk for lk in LINKS}
LINK_MAP.update({(lk["target"],lk["source"]): lk for lk in LINKS})

# ── Routing tables (tier-based)
# Tier-1 (Controllers) are primary routes; Tier-2 BSs route via nearest controller
# OSPF-style: lowest-hop, prefer Fiber > Microwave
ROUTES = {
    # BS→Controller assignments
    "BS1": ["CR-1","CR-2"],
    "BS2": ["CR-1","CR-2"],
    "BS3": ["CR-2","CR-1"],
    "BS4": ["CR-2","CR-1"],
    "BS5": ["CR-2","CR-1"],
    "CR-1":["CR-2"],
    "CR-2":["CR-1"],
}

# ── State
for s in SITES:
    s["in_use"]   = 0
    s["calls"]    = 0
    s["blocked"]  = 0
    s["handovers"]= 0

for lk in LINKS:
    lk["active_flows"] = 0

# Active calls: {call_id: {site, route_path, tick_started}}
active_calls = {}
call_counter  = [0]
event_log     = deque(maxlen=60)
active_packet = {"path": [], "progress": 0, "visible": False}  # animated packet

TICK = [0]

# ── Signalling engine
SIGNAL_EVENTS = ["SETUP","RELEASE","HANDOVER","OVERFLOW_REROUTE","BLOCKED"]
MSG_TYPES      = ["IAM","ACM","ANM","REL","RLC","HO_REQ","HO_CMD","HO_CPL"]

def pick_route(src_name, exclude=None):
    candidates = ROUTES.get(src_name, [])
    for c in candidates:
        ctrl = SITE_MAP[c]
        if ctrl["in_use"] < ctrl["channels"] and c != exclude:
            return c
    return None

def run_signalling_tick():
    TICK[0] += 1
    events = []

    # 1. Random new call attempt (40% chance)
    if random.random() < 0.40:
        bs = random.choice([s for s in SITES if s["type"]=="bs"])
        if bs["in_use"] < bs["channels"]:
            route = pick_route(bs["name"])
            if route and SITE_MAP[route]["in_use"] < SITE_MAP[route]["channels"]:
                bs["in_use"]  += 1
                bs["calls"]   += 1
                SITE_MAP[route]["in_use"] += 1
                cid = f"C{call_counter[0]:04d}"
                call_counter[0] += 1
                path = [bs["name"], route]
                active_calls[cid] = {"site": bs["name"], "ctrl": route, "path": path, "tick": TICK[0]}
                msg = random.choice(["IAM","ACM","ANM"])
                events.append({
                    "tick": TICK[0], "type":"SETUP", "site": bs["name"],
                    "route": route, "path": path, "call": cid, "msg": msg,
                    "detail": f"▶ SETUP {cid} | {bs['name']}→{route} | {msg} | {'FIBER' if LINK_MAP.get((bs['name'],route),{}).get('type')=='Fiber' else 'MICROWAVE'}"
                })
                active_packet["path"]     = path
                active_packet["progress"] = 0
                active_packet["visible"]  = True
            else:
                # Try overflow reroute
                alt = pick_route(bs["name"])
                if alt:
                    bs["in_use"] += 1
                    SITE_MAP[alt]["in_use"] += 1
                    cid = f"C{call_counter[0]:04d}"; call_counter[0] += 1
                    path = [bs["name"], alt]
                    active_calls[cid] = {"site":bs["name"],"ctrl":alt,"path":path,"tick":TICK[0]}
                    events.append({
                        "tick":TICK[0],"type":"OVERFLOW_REROUTE","site":bs["name"],
                        "route":alt,"path":path,"call":cid,"msg":"IAM",
                        "detail":f"⚡ REROUTE {cid} | {bs['name']}→{alt} | OSPF OVERFLOW"
                    })
                else:
                    bs["blocked"] += 1
                    events.append({
                        "tick":TICK[0],"type":"BLOCKED","site":bs["name"],
                        "route":None,"path":[],"call":None,"msg":"REL",
                        "detail":f"✖ BLOCKED | {bs['name']} | GOS EXCEEDED | REL sent"
                    })
        else:
            bs["blocked"] += 1
            events.append({
                "tick":TICK[0],"type":"BLOCKED","site":bs["name"],
                "route":None,"path":[],"call":None,"msg":"REL",
                "detail":f"✖ BLOCKED | {bs['name']} | NO CHANNELS | REL"
            })

    # 2. Random release (30% chance if calls exist)
    if active_calls and random.random() < 0.30:
        cid = random.choice(list(active_calls.keys()))
        call = active_calls.pop(cid)
        SITE_MAP[call["site"]]["in_use"] = max(0, SITE_MAP[call["site"]]["in_use"]-1)
        SITE_MAP[call["ctrl"]]["in_use"] = max(0, SITE_MAP[call["ctrl"]]["in_use"]-1)
        events.append({
            "tick":TICK[0],"type":"RELEASE","site":call["site"],
            "route":call["ctrl"],"path":call["path"][::-1],"call":cid,"msg":"RLC",
            "detail":f"◀ RELEASE {cid} | {call['site']}←{call['ctrl']} | RLC | ch freed"
        })

    # 3. Random handover (15% chance if calls exist)
    if active_calls and random.random() < 0.15:
        cid = random.choice(list(active_calls.keys()))
        call = active_calls[cid]
        old_bs = SITE_MAP[call["site"]]
        # pick neighbour BS
        neighbours = [s for s in SITES if s["type"]=="bs" and s["name"]!=call["site"] and s["in_use"]<s["channels"]]
        if neighbours:
            new_bs = random.choice(neighbours)
            old_bs["in_use"]  = max(0, old_bs["in_use"]-1)
            old_bs["handovers"] += 1
            new_bs["in_use"]  += 1
            new_bs["handovers"]+= 1
            old_name = call["site"]
            call["site"] = new_bs["name"]
            call["path"] = [new_bs["name"], call["ctrl"]]
            active_calls[cid] = call
            events.append({
                "tick":TICK[0],"type":"HANDOVER","site":new_bs["name"],
                "route":call["ctrl"],"path":[old_name, new_bs["name"]],"call":cid,"msg":"HO_CPL",
                "detail":f"↔ HANDOVER {cid} | {old_name}→{new_bs['name']} | HO_CPL | ctrl={call['ctrl']}"
            })
            active_packet["path"]    = [old_name, new_bs["name"]]
            active_packet["progress"]= 0
            active_packet["visible"] = True

    for e in events:
        event_log.appendleft(e)

    return events

# ── Color helpers
def usage_color(ratio):
    if ratio == 0:   return "#00e5ff"
    if ratio < 0.50: return "#00ff88"
    if ratio < 0.80: return "#ffd600"
    if ratio < 1.00: return "#ff6d00"
    return "#ff1744"

def event_color(etype):
    return {"SETUP":"#00ff88","RELEASE":"#4a90d9","HANDOVER":"#ffd600",
            "BLOCKED":"#ff1744","OVERFLOW_REROUTE":"#ff6d00"}.get(etype,"#aaa")

def link_color(lk):
    if lk["type"] == "Fiber": return "#00e5ff"
    return "#4a90d9"

# ── Map builder
def make_figure(active_event=None):
    fig = go.Figure()

    # 1. Draw all links (base layer)
    for lk in LINKS:
        src = SITE_MAP[lk["source"]]
        tgt = SITE_MAP[lk["target"]]
        fig.add_trace(go.Scattermapbox(
            lat=[src["lat"], tgt["lat"], None],
            lon=[src["lon"], tgt["lon"], None],
            mode="lines",
            line=dict(width=3 if lk["type"]=="Fiber" else 1.5, color=link_color(lk)),
            opacity=0.45, hoverinfo="skip", showlegend=False
        ))

    # 2. Highlight active route path
    if active_event and active_event.get("path") and len(active_event["path"]) >= 2:
        path = active_event["path"]
        etype = active_event["type"]
        for i in range(len(path)-1):
            a, b = SITE_MAP[path[i]], SITE_MAP[path[i+1]]
            fig.add_trace(go.Scattermapbox(
                lat=[a["lat"], b["lat"], None],
                lon=[a["lon"], b["lon"], None],
                mode="lines",
                line=dict(width=5, color=event_color(etype)),
                opacity=0.9, hoverinfo="skip", showlegend=False
            ))

        # 3. Animated "packet" marker at midpoint
        if active_packet["visible"] and len(path) >= 2:
            p = active_packet["progress"]  # 0..1
            a, b = SITE_MAP[path[0]], SITE_MAP[path[1]]
            mid_lat = a["lat"] + (b["lat"]-a["lat"]) * p
            mid_lon = a["lon"] + (b["lon"]-a["lon"]) * p
            fig.add_trace(go.Scattermapbox(
                lat=[mid_lat], lon=[mid_lon],
                mode="markers",
                marker=dict(size=14, color=event_color(etype), opacity=1.0, symbol="circle"),
                hoverinfo="skip", showlegend=False
            ))

    # 4. Draw sites
    for s in SITES:
        ratio = s["in_use"] / s["channels"]
        is_ctrl = s["type"] == "controller"
        size = 26 if is_ctrl else 18
        color = usage_color(ratio)

        # Pulse effect: highlight if recently active
        if active_event and s["name"] in (active_event.get("path") or []):
            size += 8

        fig.add_trace(go.Scattermapbox(
            lat=[s["lat"]], lon=[s["lon"]],
            mode="markers+text",
            marker=dict(size=size, color=color, opacity=0.92, symbol="circle"),
            text=[s["name"]],
            textposition="top right",
            textfont=dict(color="white", size=10),
            hovertemplate=(
                f"<b>{s['name']} — {s['label']}</b><br>"
                f"Tier: {'1 (Controller)' if is_ctrl else '2 (Base Station)'}<br>"
                f"Channels: {s['in_use']}/{s['channels']}<br>"
                f"Calls: {s['calls']} | Blocked: {s['blocked']} | HO: {s['handovers']}"
                "<extra></extra>"
            ),
            showlegend=False
        ))

    center_lat = sum(s["lat"] for s in SITES)/len(SITES)
    center_lon = sum(s["lon"] for s in SITES)/len(SITES)

    fig.update_layout(
        mapbox=dict(style="open-street-map", center=dict(lat=center_lat, lon=center_lon), zoom=8),
        margin=dict(l=0,r=0,t=0,b=0),
        height=520,
        paper_bgcolor="#020a17",
    )
    return fig

# ── Sidebar builder
def make_sidebar():
    items = []
    # Tier 1
    items.append(html.Div("TIER 1 — CONTROLLERS", style={"color":"#00e5ff","fontSize":"10px","letterSpacing":"2px","marginBottom":"8px","marginTop":"4px"}))
    for s in [x for x in SITES if x["type"]=="controller"]:
        items.append(site_card(s))
    # Tier 2
    items.append(html.Div("TIER 2 — BASE STATIONS", style={"color":"#4a90d9","fontSize":"10px","letterSpacing":"2px","marginBottom":"8px","marginTop":"14px"}))
    for s in [x for x in SITES if x["type"]=="bs"]:
        items.append(site_card(s))
    return items

def site_card(s):
    ratio = s["in_use"]/s["channels"]
    pct   = ratio*100
    bc    = "#ff1744" if pct>=100 else "#ff6d00" if pct>=80 else "#ffd600" if pct>=50 else "#00ff88"
    return html.Div(style={"marginBottom":"10px","padding":"8px","background":"#060d1a","border":"1px solid #0a2840","borderRadius":"3px"}, children=[
        html.Div([
            html.Span(s["name"], style={"fontSize":"11px","fontWeight":"bold","color":"white"}),
            html.Span(f"{s['in_use']}/{s['channels']}", style={"fontSize":"10px","color":bc}),
        ], style={"display":"flex","justifyContent":"space-between","marginBottom":"4px"}),
        html.Div(s["label"], style={"fontSize":"9px","color":"#4a8aaa","marginBottom":"4px"}),
        html.Div(style={"height":"3px","background":"#111","borderRadius":"2px"}, children=[
            html.Div(style={"height":"100%","width":f"{pct}%","background":bc,"borderRadius":"2px"})
        ]),
        html.Div([
            html.Span(f"▶{s['calls']}", style={"fontSize":"9px","color":"#00ff88","marginRight":"8px"}),
            html.Span(f"✖{s['blocked']}", style={"fontSize":"9px","color":"#ff1744","marginRight":"8px"}),
            html.Span(f"↔{s['handovers']}", style={"fontSize":"9px","color":"#ffd600"}),
        ], style={"marginTop":"4px"}),
    ])

# ── GOS panel
def make_gos_panel():
    total_ch  = sum(s["channels"] for s in SITES)
    used_ch   = sum(s["in_use"]   for s in SITES)
    total_calls = sum(s["calls"]   for s in SITES)
    total_blocked=sum(s["blocked"] for s in SITES)
    total_ho   = sum(s["handovers"]for s in SITES)
    gos = (total_blocked/max(1,total_calls+total_blocked))*100
    active_count = len(active_calls)

    def stat(label, val, color="#00e5ff"):
        return html.Div(style={"display":"flex","justifyContent":"space-between","marginBottom":"6px"}, children=[
            html.Span(label, style={"fontSize":"10px","color":"#4a8aaa"}),
            html.Span(val,   style={"fontSize":"11px","color":color,"fontWeight":"bold"}),
        ])

    return [
        html.Div("GOS & NETWORK STATS", style={"color":"#ffd600","fontSize":"10px","letterSpacing":"2px","marginBottom":"10px"}),
        stat("Active Calls",    str(active_count),           "#00ff88"),
        stat("Total Setups",    str(total_calls),            "#00e5ff"),
        stat("Blocked",         str(total_blocked),          "#ff1744"),
        stat("Handovers",       str(total_ho),               "#ffd600"),
        stat("Channel Util.",   f"{used_ch}/{total_ch} ({100*used_ch//max(1,total_ch)}%)", "#ff6d00"),
        stat("Grade of Service",f"{gos:.1f}%",               "#ff1744" if gos>5 else "#00ff88"),
        # GOS bar
        html.Div(style={"height":"4px","background":"#111","borderRadius":"2px","marginTop":"4px"}, children=[
            html.Div(style={"height":"100%","width":f"{min(gos,100):.1f}%","background":"#ff1744","borderRadius":"2px"})
        ]),
    ]

# ── Event log builder
def make_log():
    rows = []
    for e in list(event_log)[:18]:
        color = event_color(e["type"])
        rows.append(html.Div(e["detail"], style={"color":color,"fontSize":"10px","marginBottom":"2px","fontFamily":"monospace","whiteSpace":"nowrap","overflow":"hidden"}))
    return rows

# ── App
app = dash.Dash(__name__)
app.title = "Tier Routing & Signalling Monitor"

app.layout = html.Div(style={
    "backgroundColor":"#020a17","color":"white",
    "fontFamily":"'Courier New', monospace","padding":"16px","minHeight":"100vh"
}, children=[
    # Header
    html.Div(style={"borderBottom":"1px solid #0a2840","paddingBottom":"10px","marginBottom":"14px","display":"flex","justifyContent":"space-between","alignItems":"center"}, children=[
        html.Div([
            html.H2("TIER ROUTING & SIGNALLING MONITOR", style={"color":"#00e5ff","margin":"0","fontSize":"16px","letterSpacing":"3px"}),
            html.Div("Palapye District — PSTN/GSM Hybrid Control Plane  |  OSPF Tier Routing  |  Live Simulation",
                     style={"color":"#4a8aaa","fontSize":"10px","marginTop":"3px"}),
        ]),
        html.Div(id="tick-counter", style={"color":"#4a8aaa","fontSize":"10px"}),
    ]),

    html.Div(style={"display":"flex","gap":"14px"}, children=[

        # ── Left sidebar: channel meters
        html.Div(style={"width":"200px","flexShrink":"0"}, children=[
            html.Div(id="sidebar", style={"overflowY":"auto","maxHeight":"600px"}),
        ]),

        # ── Center: map
        html.Div(style={"flex":"1","minWidth":"0"}, children=[
            dcc.Graph(id="map-graph", config={"displayModeBar":False}),

            # Event log
            html.Div(style={"marginTop":"10px","background":"#000","border":"1px solid #0a2840","padding":"8px","height":"160px","overflowY":"auto"}, children=[
                html.Div("◈ SIGNALLING EVENT LOG", style={"color":"#00e5ff","fontSize":"10px","letterSpacing":"2px","marginBottom":"6px"}),
                html.Div(id="event-log"),
            ]),
        ]),

        # ── Right: GOS + legend
        html.Div(style={"width":"200px","flexShrink":"0"}, children=[
            html.Div(id="gos-panel", style={"background":"#060d1a","border":"1px solid #0a2840","padding":"12px","marginBottom":"14px"}),

            # Legend
            html.Div(style={"background":"#060d1a","border":"1px solid #0a2840","padding":"12px"}, children=[
                html.Div("LEGEND", style={"color":"#4a8aaa","fontSize":"10px","letterSpacing":"2px","marginBottom":"8px"}),
                *[html.Div([
                    html.Span("●", style={"color":c,"marginRight":"6px"}),
                    html.Span(label, style={"fontSize":"10px","color":"#ccc"}),
                ], style={"marginBottom":"4px"}) for c,label in [
                    ("#00e5ff","Idle (0%)"),
                    ("#00ff88","Low (<50%)"),
                    ("#ffd600","Medium (50-79%)"),
                    ("#ff6d00","High (80-99%)"),
                    ("#ff1744","Full / Blocked"),
                ]],
                html.Div(style={"borderTop":"1px solid #0a2840","marginTop":"8px","paddingTop":"8px"}),
                *[html.Div([
                    html.Span("—", style={"color":c,"marginRight":"6px","fontWeight":"bold"}),
                    html.Span(label, style={"fontSize":"10px","color":"#ccc"}),
                ], style={"marginBottom":"4px"}) for c,label in [
                    ("#00e5ff","Fiber link"),
                    ("#4a90d9","Microwave link"),
                    ("#00ff88","Active SETUP route"),
                    ("#ff1744","BLOCKED / RELEASE"),
                    ("#ffd600","HANDOVER path"),
                ]],
            ]),
        ]),
    ]),

    dcc.Interval(id="heartbeat", interval=1800, n_intervals=0),
    dcc.Store(id="last-event", data={}),
])


@app.callback(
    [Output("map-graph","figure"),
     Output("sidebar","children"),
     Output("gos-panel","children"),
     Output("event-log","children"),
     Output("tick-counter","children"),
     Output("last-event","data")],
    Input("heartbeat","n_intervals"),
)
def update(n):
    events = run_signalling_tick()

    # Advance packet animation
    if active_packet["visible"]:
        active_packet["progress"] += 0.35
        if active_packet["progress"] >= 1.0:
            active_packet["visible"]  = False
            active_packet["progress"] = 0.0

    latest = events[0] if events else None
    fig = make_figure(active_event=latest)

    tick_str = f"TICK {TICK[0]:04d}  |  ACTIVE CALLS: {len(active_calls):02d}"

    return (
        fig,
        make_sidebar(),
        make_gos_panel(),
        make_log(),
        tick_str,
        latest or {}
    )


if __name__ == "__main__":
    app.run(debug=False, port=8050)