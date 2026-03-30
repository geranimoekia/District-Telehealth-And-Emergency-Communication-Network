import dash
from dash import html, dcc, Input, Output
import plotly.graph_objects as go
import random
import time
from collections import deque

# ── DMS helper
def dms(d, m, s, direction):
    dd = d + m/60 + s/3600
    return -dd if direction in ("S","W") else dd

# ══════════════════════════════════════════════════════════════
# NETWORK TOPOLOGY  (mirrors your Fig 2.1 hierarchy)
# Tier 0 = SDN Controller (logical, top)
# Tier 1 = Core / Controllers  (CR-1, CR-2) — Static+MPLS
# Tier 2 = Base Stations / Clinics (BS1-BS5) — OSPF dynamic
# ══════════════════════════════════════════════════════════════
SITES = [
    # SS7 Point Codes are 3-part: Network-Cluster-Member
    {"name":"SDN", "label":"SDN Controller (Core)",      "lat":dms(22,50,0,"S"),  "lon":dms(23,59,42,"E"), "channels":99,"tier":0,"type":"sdn",        "pc":"1-1-1", "opc":"001-001-001"},
    {"name":"CR-1","label":"District Hospital (SSP/STP)","lat":dms(22,59,59,"S"), "lon":dms(23,59,42,"E"), "channels":8, "tier":1,"type":"controller",  "pc":"1-1-2", "opc":"001-001-002"},
    {"name":"CR-2","label":"District Health Office (SSP)","lat":dms(22,58,21,"S"),"lon":dms(23,56,45,"E"), "channels":8, "tier":1,"type":"controller",  "pc":"1-1-3", "opc":"001-001-003"},
    {"name":"BS1", "label":"Clinic North-West",           "lat":dms(22,51,52,"S"), "lon":dms(23,49,42,"E"), "channels":4, "tier":2,"type":"bs",          "pc":"2-1-1", "opc":"002-001-001"},
    {"name":"BS2", "label":"Clinic North-East",           "lat":dms(22,51,52,"S"), "lon":dms(24, 9,42,"E"), "channels":4, "tier":2,"type":"bs",          "pc":"2-1-2", "opc":"002-001-002"},
    {"name":"BS3", "label":"Clinic South-West",           "lat":dms(23, 8, 5,"S"), "lon":dms(23,49,42,"E"), "channels":4, "tier":2,"type":"bs",          "pc":"2-2-1", "opc":"002-002-001"},
    {"name":"BS4", "label":"Clinic South",                "lat":dms(23, 9,10,"S"), "lon":dms(23,59,42,"E"), "channels":4, "tier":2,"type":"bs",          "pc":"2-2-2", "opc":"002-002-002"},
    {"name":"BS5", "label":"Clinic South-East",           "lat":dms(23, 8, 5,"S"), "lon":dms(24, 9,42,"E"), "channels":4, "tier":2,"type":"bs",          "pc":"2-2-3", "opc":"002-002-003"},
]

# Link types map to your routing methodology sections
LINKS = [
    {"source":"SDN", "target":"CR-1","type":"OpenFlow",  "routing":"SDN",    "capacity":99, "cost":1},
    {"source":"SDN", "target":"CR-2","type":"OpenFlow",  "routing":"SDN",    "capacity":99, "cost":1},
    {"source":"CR-1","target":"CR-2","type":"Fiber",     "routing":"STATIC+MPLS","capacity":16,"cost":2},
    {"source":"CR-1","target":"BS1", "type":"Microwave", "routing":"OSPF",   "capacity":4,  "cost":5},
    {"source":"CR-1","target":"BS2", "type":"Microwave", "routing":"OSPF",   "capacity":4,  "cost":5},
    {"source":"CR-2","target":"BS3", "type":"Microwave", "routing":"OSPF",   "capacity":4,  "cost":5},
    {"source":"CR-2","target":"BS4", "type":"Fiber",     "routing":"STATIC+MPLS","capacity":4,"cost":3},
    {"source":"CR-2","target":"BS5", "type":"Microwave", "routing":"OSPF",   "capacity":4,  "cost":5},
    {"source":"BS1", "target":"BS2", "type":"Microwave", "routing":"OSPF",   "capacity":2,  "cost":8},
    {"source":"BS3", "target":"BS4", "type":"Microwave", "routing":"OSPF",   "capacity":2,  "cost":8},
    {"source":"BS4", "target":"BS5", "type":"Microwave", "routing":"OSPF",   "capacity":2,  "cost":8},
]

SITE_MAP = {s["name"]: s for s in SITES}
LINK_LOOKUP = {}
for lk in LINKS:
    LINK_LOOKUP[(lk["source"],lk["target"])] = lk
    LINK_LOOKUP[(lk["target"],lk["source"])] = lk

# ══════════════════════════════════════════════════════════════
# SS7 MESSAGE DEFINITIONS  (ISUP + TCAP/MAP)
# ══════════════════════════════════════════════════════════════
SS7_ISUP = {
    "IAM":  {"desc":"Initial Address Message",   "layer":"ISUP", "dir":"fwd", "color":"#00ff88"},
    "ACM":  {"desc":"Address Complete Message",  "layer":"ISUP", "dir":"bwd", "color":"#00e5ff"},
    "ANM":  {"desc":"Answer Message",            "layer":"ISUP", "dir":"bwd", "color":"#00e5ff"},
    "REL":  {"desc":"Release Message",           "layer":"ISUP", "dir":"fwd", "color":"#ff6d00"},
    "RLC":  {"desc":"Release Complete",          "layer":"ISUP", "dir":"bwd", "color":"#ff6d00"},
    "CPG":  {"desc":"Call Progress Message",     "layer":"ISUP", "dir":"bwd", "color":"#4a90d9"},
    "SUS":  {"desc":"Suspend",                   "layer":"ISUP", "dir":"fwd", "color":"#ffd600"},
    "RES":  {"desc":"Resume",                    "layer":"ISUP", "dir":"fwd", "color":"#ffd600"},
    "BLO":  {"desc":"Blocking (GOS exceeded)",   "layer":"ISUP", "dir":"fwd", "color":"#ff1744"},
    "UBL":  {"desc":"Unblocking",                "layer":"ISUP", "dir":"fwd", "color":"#00ff88"},
}
SS7_TCAP = {
    "TC-BEGIN":  {"desc":"TCAP Begin (MAP query)",    "layer":"TCAP/MAP","color":"#b388ff"},
    "TC-CONTINUE":{"desc":"TCAP Continue (in dialog)","layer":"TCAP/MAP","color":"#b388ff"},
    "TC-END":    {"desc":"TCAP End (MAP response)",   "layer":"TCAP/MAP","color":"#b388ff"},
    "MAP-SRI":   {"desc":"Send Routing Info",         "layer":"TCAP/MAP","color":"#ea80fc"},
    "MAP-PRN":   {"desc":"Provide Roaming Number",    "layer":"TCAP/MAP","color":"#ea80fc"},
    "MAP-UL":    {"desc":"Update Location",           "layer":"TCAP/MAP","color":"#ea80fc"},
}
ALL_SS7 = {**SS7_ISUP, **SS7_TCAP}

# Call sequence templates (ladder steps)
CALL_LADDER = ["IAM","ACM","ANM"]
RELEASE_LADDER = ["REL","RLC"]
HANDOVER_LADDER = ["TC-BEGIN","MAP-SRI","MAP-PRN","TC-END","IAM","ACM","ANM"]
EMERGENCY_LADDER = ["IAM","ACM","ANM"]  # pre-emption via SDN

# ══════════════════════════════════════════════════════════════
# ROUTING MODE  (Static vs OSPF/Dynamic — your sec 1.2.1/1.2.2)
# ══════════════════════════════════════════════════════════════
# Static table: fixed preferred controller per BS
STATIC_TABLE = {
    "BS1":"CR-1","BS2":"CR-1",
    "BS3":"CR-2","BS4":"CR-2","BS5":"CR-2",
}
# OSPF cost table (Dijkstra simplified — lower=better)
OSPF_COSTS = {
    ("BS1","CR-1"):5, ("BS1","CR-2"):7,
    ("BS2","CR-1"):5, ("BS2","CR-2"):7,
    ("BS3","CR-2"):5, ("BS3","CR-1"):7,
    ("BS4","CR-2"):3, ("BS4","CR-1"):5,  # fiber to CR-2
    ("BS5","CR-2"):5, ("BS5","CR-1"):7,
}

def pick_route(bs_name, mode="OSPF"):
    candidates = ["CR-1","CR-2"]
    if mode == "STATIC":
        preferred = STATIC_TABLE.get(bs_name,"CR-1")
        for c in [preferred] + [x for x in candidates if x!=preferred]:
            if SITE_MAP[c]["in_use"] < SITE_MAP[c]["channels"]:
                return c, "STATIC"
        return None, "STATIC"
    else:  # OSPF
        ranked = sorted(candidates, key=lambda c: OSPF_COSTS.get((bs_name,c),99))
        for c in ranked:
            if SITE_MAP[c]["in_use"] < SITE_MAP[c]["channels"]:
                return c, "OSPF"
        return None, "OSPF"

# ══════════════════════════════════════════════════════════════
# STATE
# ══════════════════════════════════════════════════════════════
for s in SITES:
    s["in_use"]=0; s["calls"]=0; s["blocked"]=0; s["handovers"]=0

active_calls   = {}
call_counter   = [0]
event_log      = deque(maxlen=80)
ladder_log     = deque(maxlen=12)   # MSC ladder entries
TICK           = [0]
ROUTE_MODE     = ["OSPF"]           # toggled by user
packet_anim    = {"path":[],"progress":0.0,"visible":False,"color":"#00ff88"}

# GOS tracking
gos_stats = {"total":0,"blocked":0,"handovers":0,"setups":0,"releases":0,"reroutes":0}

# ══════════════════════════════════════════════════════════════
# SIGNALLING ENGINE
# ══════════════════════════════════════════════════════════════
def make_ss7_decode(msg, src, dst, cic=None):
    info = ALL_SS7.get(msg,{})
    cic  = cic or random.randint(1,31)
    sls  = random.randint(0,15)
    src_pc = SITE_MAP.get(src,{}).get("pc","?")
    dst_pc = SITE_MAP.get(dst,{}).get("pc","?")
    return {
        "msg":msg,"layer":info.get("layer","ISUP"),
        "desc":info.get("desc",""),
        "opc":src_pc,"dpc":dst_pc,
        "cic":cic,"sls":sls,
        "src":src,"dst":dst,
    }

def run_tick():
    TICK[0] += 1
    events = []
    mode   = ROUTE_MODE[0]

    # 40% new call
    if random.random() < 0.40:
        bs = random.choice([s for s in SITES if s["type"]=="bs"])
        ctrl, rmode = pick_route(bs["name"], mode)
        gos_stats["total"] += 1

        if ctrl and bs["in_use"] < bs["channels"] and SITE_MAP[ctrl]["in_use"] < SITE_MAP[ctrl]["channels"]:
            bs["in_use"]+=1; bs["calls"]+=1
            SITE_MAP[ctrl]["in_use"]+=1
            cid  = f"C{call_counter[0]:04d}"; call_counter[0]+=1
            cic  = random.randint(1,31)
            path = [bs["name"],ctrl,"SDN"]
            active_calls[cid] = {"site":bs["name"],"ctrl":ctrl,"path":path,"cic":cic,"tick":TICK[0]}
            gos_stats["setups"]+=1

            # Build ISUP ladder
            for msg in CALL_LADDER:
                decode = make_ss7_decode(msg, bs["name"] if msg=="IAM" else ctrl, ctrl if msg=="IAM" else bs["name"], cic)
                ladder_log.appendleft({"step":msg,"from":decode["src"],"to":decode["dst"],"decode":decode,"type":"SETUP"})

            lk = LINK_LOOKUP.get((bs["name"],ctrl),{})
            ev = {
                "tick":TICK[0],"type":"SETUP","site":bs["name"],"route":ctrl,
                "path":[bs["name"],ctrl],"call":cid,"msg":"IAM","routing":rmode,
                "mpls_label": f"L{random.randint(100,999)}" if lk.get("routing","")=="STATIC+MPLS" else None,
                "detail": (f"▶ SETUP {cid} | {bs['name']}(OPC:{SITE_MAP[bs['name']]['pc']})→"
                           f"{ctrl}(DPC:{SITE_MAP[ctrl]['pc']}) | IAM CIC:{cic} | {rmode} | "
                           f"{'MPLS:L'+str(random.randint(100,999)) if lk.get('routing','')=='STATIC+MPLS' else 'IP-routed'}")
            }
            events.append(ev)
            packet_anim.update({"path":[bs["name"],ctrl],"progress":0.0,"visible":True,"color":"#00ff88"})

        else:
            # Try OSPF overflow reroute
            alt_ctrl = "CR-2" if STATIC_TABLE.get(bs["name"])=="CR-1" else "CR-1"
            if SITE_MAP[alt_ctrl]["in_use"] < SITE_MAP[alt_ctrl]["channels"] and bs["in_use"] < bs["channels"]:
                bs["in_use"]+=1; SITE_MAP[alt_ctrl]["in_use"]+=1
                cid=f"C{call_counter[0]:04d}"; call_counter[0]+=1
                cic=random.randint(1,31)
                active_calls[cid]={"site":bs["name"],"ctrl":alt_ctrl,"path":[bs["name"],alt_ctrl],"cic":cic,"tick":TICK[0]}
                gos_stats["reroutes"]+=1; gos_stats["setups"]+=1
                decode = make_ss7_decode("IAM", bs["name"], alt_ctrl, cic)
                ladder_log.appendleft({"step":"IAM","from":bs["name"],"to":alt_ctrl,"decode":decode,"type":"REROUTE"})
                events.append({"tick":TICK[0],"type":"OVERFLOW_REROUTE","site":bs["name"],"route":alt_ctrl,
                    "path":[bs["name"],alt_ctrl],"call":cid,"msg":"IAM","routing":"OSPF-OVERFLOW",
                    "detail":f"⚡ REROUTE {cid} | {bs['name']}→{alt_ctrl} | OSPF overflow | IAM CIC:{cic} | DPC:{SITE_MAP[alt_ctrl]['pc']}"})
                packet_anim.update({"path":[bs["name"],alt_ctrl],"progress":0.0,"visible":True,"color":"#ff6d00"})
            else:
                bs["blocked"]+=1; gos_stats["blocked"]+=1
                decode = make_ss7_decode("BLO", bs["name"], STATIC_TABLE.get(bs["name"],"CR-1"))
                ladder_log.appendleft({"step":"BLO","from":bs["name"],"to":"CR-1","decode":decode,"type":"BLOCKED"})
                events.append({"tick":TICK[0],"type":"BLOCKED","site":bs["name"],"route":None,
                    "path":[],"call":None,"msg":"BLO","routing":mode,
                    "detail":f"✖ BLOCKED | {bs['name']} | GOS LIMIT | BLO sent | OPC:{SITE_MAP[bs['name']]['pc']}"})

    # 28% release
    if active_calls and random.random()<0.28:
        cid = random.choice(list(active_calls.keys()))
        call= active_calls.pop(cid)
        SITE_MAP[call["site"]]["in_use"]=max(0,SITE_MAP[call["site"]]["in_use"]-1)
        SITE_MAP[call["ctrl"]]["in_use"]=max(0,SITE_MAP[call["ctrl"]]["in_use"]-1)
        gos_stats["releases"]+=1
        for msg in RELEASE_LADDER:
            decode=make_ss7_decode(msg,call["site"],call["ctrl"],call["cic"])
            ladder_log.appendleft({"step":msg,"from":call["site"],"to":call["ctrl"],"decode":decode,"type":"RELEASE"})
        events.append({"tick":TICK[0],"type":"RELEASE","site":call["site"],"route":call["ctrl"],
            "path":[call["ctrl"],call["site"]],"call":cid,"msg":"RLC","routing":mode,
            "detail":f"◀ RELEASE {cid} | {call['site']}←{call['ctrl']} | RLC CIC:{call['cic']} | ch freed"})
        packet_anim.update({"path":[call["ctrl"],call["site"]],"progress":0.0,"visible":True,"color":"#4a90d9"})

    # 14% handover with TCAP/MAP
    if active_calls and random.random()<0.14:
        cid  = random.choice(list(active_calls.keys()))
        call = active_calls[cid]
        nbrs = [s for s in SITES if s["type"]=="bs" and s["name"]!=call["site"] and s["in_use"]<s["channels"]]
        if nbrs:
            new_bs=random.choice(nbrs)
            SITE_MAP[call["site"]]["in_use"]=max(0,SITE_MAP[call["site"]]["in_use"]-1)
            SITE_MAP[call["site"]]["handovers"]+=1
            new_bs["in_use"]+=1; new_bs["handovers"]+=1
            old=call["site"]; call["site"]=new_bs["name"]
            active_calls[cid]=call; gos_stats["handovers"]+=1
            for msg in ["TC-BEGIN","MAP-SRI","MAP-PRN","TC-END"]:
                decode=make_ss7_decode(msg,old,new_bs["name"])
                ladder_log.appendleft({"step":msg,"from":old,"to":new_bs["name"],"decode":decode,"type":"HANDOVER"})
            events.append({"tick":TICK[0],"type":"HANDOVER","site":new_bs["name"],"route":call["ctrl"],
                "path":[old,new_bs["name"]],"call":cid,"msg":"HO_CPL","routing":mode,
                "detail":f"↔ HANDOVER {cid} | {old}→{new_bs['name']} | TC-BEGIN/MAP-SRI/PRN/TC-END | HO_CPL"})
            packet_anim.update({"path":[old,new_bs["name"]],"progress":0.0,"visible":True,"color":"#ffd600"})

    # 8% emergency (SDN preemption)
    if random.random()<0.08:
        bs=random.choice([s for s in SITES if s["type"]=="bs"])
        events.append({"tick":TICK[0],"type":"EMERGENCY","site":bs["name"],"route":"SDN",
            "path":[bs["name"],"CR-1","SDN"],"call":"EMG","msg":"IAM","routing":"SDN-PREEMPT",
            "detail":f"🚨 EMERGENCY | {bs['name']}→CR-1→SDN | OpenFlow preemption | priority QoS | IAM"})
        ladder_log.appendleft({"step":"IAM","from":bs["name"],"to":"SDN","decode":make_ss7_decode("IAM",bs["name"],"SDN"),"type":"EMERGENCY"})
        packet_anim.update({"path":[bs["name"],"SDN"],"progress":0.0,"visible":True,"color":"#ff1744"})

    for e in events:
        event_log.appendleft(e)
    return events

# ══════════════════════════════════════════════════════════════
# COLORS
# ══════════════════════════════════════════════════════════════
def usage_color(ratio):
    if ratio==0:    return "#00e5ff"
    if ratio<0.50:  return "#00ff88"
    if ratio<0.80:  return "#ffd600"
    if ratio<1.00:  return "#ff6d00"
    return "#ff1744"

def event_color(etype):
    return {"SETUP":"#00ff88","RELEASE":"#4a90d9","HANDOVER":"#ffd600",
            "BLOCKED":"#ff1744","OVERFLOW_REROUTE":"#ff6d00","EMERGENCY":"#ff1744"}.get(etype,"#aaa")

def link_display_color(lk):
    r = lk.get("routing","")
    if r=="SDN":          return "#ff1744"
    if r=="STATIC+MPLS":  return "#00e5ff"
    return "#4a90d9"

# ══════════════════════════════════════════════════════════════
# MAP BUILDER
# ══════════════════════════════════════════════════════════════
def make_figure(active_event=None):
    fig = go.Figure()

    # 1. Base links
    for lk in LINKS:
        src=SITE_MAP[lk["source"]]; tgt=SITE_MAP[lk["target"]]
        fig.add_trace(go.Scattermapbox(
            lat=[src["lat"],tgt["lat"],None],lon=[src["lon"],tgt["lon"],None],
            mode="lines",
            line=dict(width=4 if lk["type"]=="Fiber" else 2,color=link_display_color(lk)),
            opacity=0.45,hoverinfo="skip",showlegend=False
        ))
        # Link label at midpoint
        mid_lat=(src["lat"]+tgt["lat"])/2; mid_lon=(src["lon"]+tgt["lon"])/2
        fig.add_trace(go.Scattermapbox(
            lat=[mid_lat],lon=[mid_lon],mode="text",
            text=[lk["routing"]],
            textfont=dict(size=8,color=link_display_color(lk)),
            hoverinfo="skip",showlegend=False
        ))

    # 2. Active route highlight
    if active_event and active_event.get("path") and len(active_event["path"])>=2:
        path=active_event["path"]; ec=event_color(active_event["type"])
        for i in range(len(path)-1):
            if path[i] in SITE_MAP and path[i+1] in SITE_MAP:
                a=SITE_MAP[path[i]]; b=SITE_MAP[path[i+1]]
                fig.add_trace(go.Scattermapbox(
                    lat=[a["lat"],b["lat"],None],lon=[a["lon"],b["lon"],None],
                    mode="lines",line=dict(width=6,color=ec),
                    opacity=0.9,hoverinfo="skip",showlegend=False
                ))

    # 3. Packet animation
    if packet_anim["visible"] and len(packet_anim["path"])>=2:
        p=packet_anim["progress"]
        a=SITE_MAP.get(packet_anim["path"][0]); b=SITE_MAP.get(packet_anim["path"][1])
        if a and b:
            mid_lat=a["lat"]+(b["lat"]-a["lat"])*p
            mid_lon=a["lon"]+(b["lon"]-a["lon"])*p
            fig.add_trace(go.Scattermapbox(
                lat=[mid_lat],lon=[mid_lon],mode="markers",
                marker=dict(size=16,color=packet_anim["color"],opacity=1.0),
                hoverinfo="skip",showlegend=False
            ))

    # 4. Site markers
    for s in SITES:
        ratio=s["in_use"]/s["channels"] if s["type"]!="sdn" else 0
        is_ctrl=s["type"]=="controller"; is_sdn=s["type"]=="sdn"
        size=32 if is_sdn else 26 if is_ctrl else 18
        color="#ff1744" if is_sdn else usage_color(ratio)
        if active_event and s["name"] in (active_event.get("path") or []):
            size+=10

        tier_label={0:"Tier-0 SDN",1:"Tier-1 CORE",2:"Tier-2 BS"}.get(s["tier"],"")
        fig.add_trace(go.Scattermapbox(
            lat=[s["lat"]],lon=[s["lon"]],
            mode="markers+text",
            marker=dict(size=size,color=color,opacity=0.93,symbol="circle"),
            text=[f"{s['name']}\nPC:{s['pc']}"],
            textposition="top right",
            textfont=dict(color="white",size=9),
            hovertemplate=(
                f"<b>{s['name']} — {s['label']}</b><br>"
                f"{tier_label}<br>"
                f"SS7 Point Code: {s['pc']}<br>"
                f"Channels: {s['in_use']}/{s['channels']}<br>"
                f"Calls: {s.get('calls',0)} | Blocked: {s.get('blocked',0)} | HO: {s.get('handovers',0)}"
                "<extra></extra>"
            ),
            showlegend=False
        ))

    center_lat=sum(s["lat"] for s in SITES)/len(SITES)
    center_lon=sum(s["lon"] for s in SITES)/len(SITES)
    fig.update_layout(
        mapbox=dict(style="open-street-map",center=dict(lat=center_lat,lon=center_lon),zoom=8),
        margin=dict(l=0,r=0,t=0,b=0),height=480,paper_bgcolor="#020a17",
    )
    return fig

# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
def make_sidebar():
    rows=[]
    for tier,label,color in [(0,"TIER 0 — SDN","#ff1744"),(1,"TIER 1 — CORE (Static+MPLS)","#00e5ff"),(2,"TIER 2 — EDGE (OSPF)","#4a90d9")]:
        rows.append(html.Div(label,style={"color":color,"fontSize":"9px","letterSpacing":"1px","marginTop":"10px","marginBottom":"6px","fontWeight":"bold"}))
        for s in [x for x in SITES if x["tier"]==tier]:
            ratio=s["in_use"]/s["channels"] if s["channels"]<99 else 0
            pct=ratio*100
            bc="#ff1744" if pct>=100 else "#ff6d00" if pct>=80 else "#ffd600" if pct>=50 else "#00ff88"
            rows.append(html.Div(style={"marginBottom":"8px","padding":"7px","background":"#060d1a","border":"1px solid #0a2840","borderRadius":"3px"},children=[
                html.Div([
                    html.Span(s["name"],style={"fontSize":"11px","fontWeight":"bold","color":"white"}),
                    html.Span(f"PC:{s['pc']}",style={"fontSize":"8px","color":"#888"}),
                ],style={"display":"flex","justifyContent":"space-between"}),
                html.Div(s["label"],style={"fontSize":"8px","color":"#4a8aaa","marginBottom":"3px"}),
                html.Div(style={"height":"3px","background":"#111","borderRadius":"2px","marginBottom":"3px"},children=[
                    html.Div(style={"height":"100%","width":f"{pct:.0f}%","background":bc,"borderRadius":"2px"})
                ]),
                html.Div([
                    html.Span(f"▶{s.get('calls',0)}",style={"fontSize":"9px","color":"#00ff88","marginRight":"6px"}),
                    html.Span(f"✖{s.get('blocked',0)}",style={"fontSize":"9px","color":"#ff1744","marginRight":"6px"}),
                    html.Span(f"↔{s.get('handovers',0)}",style={"fontSize":"9px","color":"#ffd600"}),
                    html.Span(f" {s['in_use']}/{s['channels']}ch",style={"fontSize":"9px","color":bc,"marginLeft":"6px"}),
                ]),
            ]))
    return rows

# ══════════════════════════════════════════════════════════════
# GOS PANEL
# ══════════════════════════════════════════════════════════════
def make_gos():
    tot=gos_stats["total"]; blk=gos_stats["blocked"]
    gos=(blk/max(1,tot))*100
    used=sum(s["in_use"] for s in SITES); total_ch=sum(s["channels"] for s in SITES if s["channels"]<99)
    def stat(l,v,c="#00e5ff"):
        return html.Div([html.Span(l,style={"fontSize":"9px","color":"#4a8aaa"}),
                         html.Span(v,style={"fontSize":"10px","color":c,"fontWeight":"bold"})],
                        style={"display":"flex","justifyContent":"space-between","marginBottom":"5px"})
    return [
        html.Div("GOS & QoS METRICS",style={"color":"#ffd600","fontSize":"9px","letterSpacing":"2px","marginBottom":"8px"}),
        stat("Active Calls",    str(len(active_calls)),    "#00ff88"),
        stat("Total Attempts",  str(gos_stats["total"]),   "#00e5ff"),
        stat("Setups OK",       str(gos_stats["setups"]),  "#00ff88"),
        stat("Releases",        str(gos_stats["releases"]),"#4a90d9"),
        stat("Blocked (GOS)",   str(gos_stats["blocked"]), "#ff1744"),
        stat("Handovers",       str(gos_stats["handovers"]),"#ffd600"),
        stat("OSPF Reroutes",   str(gos_stats["reroutes"]),"#ff6d00"),
        stat("Grade of Service",f"{gos:.1f}%",             "#ff1744" if gos>5 else "#00ff88"),
        html.Div(style={"height":"4px","background":"#111","borderRadius":"2px","marginBottom":"8px"},children=[
            html.Div(style={"height":"100%","width":f"{min(gos,100):.1f}%","background":"#ff1744","borderRadius":"2px"})
        ]),
        html.Div("ROUTE MODE",style={"color":"#ffd600","fontSize":"9px","letterSpacing":"2px","marginTop":"10px","marginBottom":"6px"}),
        html.Div([
            html.Button("OSPF (Dynamic)",id="btn-ospf",n_clicks=0,style={
                "background":"#00e5ff" if ROUTE_MODE[0]=="OSPF" else "#0a1a2e",
                "color":"#000" if ROUTE_MODE[0]=="OSPF" else "#00e5ff",
                "border":"1px solid #00e5ff","padding":"4px 8px","fontSize":"9px",
                "cursor":"pointer","marginRight":"4px","fontFamily":"monospace"}),
            html.Button("STATIC",id="btn-static",n_clicks=0,style={
                "background":"#ffd600" if ROUTE_MODE[0]=="STATIC" else "#0a1a2e",
                "color":"#000" if ROUTE_MODE[0]=="STATIC" else "#ffd600",
                "border":"1px solid #ffd600","padding":"4px 8px","fontSize":"9px",
                "cursor":"pointer","fontFamily":"monospace"}),
        ]),
        html.Div(f"Active: {ROUTE_MODE[0]}",style={"fontSize":"9px","color":"#4a8aaa","marginTop":"6px"}),
    ]

# ══════════════════════════════════════════════════════════════
# MSC LADDER (SS7 message sequence chart)
# ══════════════════════════════════════════════════════════════
def make_ladder():
    rows=[]
    type_colors={"SETUP":"#00ff88","RELEASE":"#4a90d9","HANDOVER":"#ffd600",
                 "BLOCKED":"#ff1744","REROUTE":"#ff6d00","EMERGENCY":"#ff1744"}
    for entry in list(ladder_log)[:10]:
        d=entry["decode"]; tc=type_colors.get(entry["type"],"#aaa")
        msg_info=ALL_SS7.get(d["msg"],{})
        rows.append(html.Div(style={"marginBottom":"6px","padding":"6px","background":"#080f1a","border":f"1px solid {tc}22","borderLeft":f"3px solid {tc}"},children=[
            html.Div([
                html.Span(d["msg"],style={"color":tc,"fontWeight":"bold","fontSize":"11px","marginRight":"8px"}),
                html.Span(msg_info.get("layer",""),style={"color":"#888","fontSize":"9px","marginRight":"8px"}),
                html.Span(msg_info.get("desc",""),style={"color":"#666","fontSize":"9px"}),
            ]),
            html.Div([
                html.Span(f"{d['src']}",style={"color":"#00e5ff","fontSize":"10px"}),
                html.Span(" ──── ",style={"color":tc}),
                html.Span(d["msg"],style={"color":tc,"fontSize":"10px"}),
                html.Span(" ──▶ ",style={"color":tc}),
                html.Span(f"{d['dst']}",style={"color":"#00e5ff","fontSize":"10px"}),
            ],style={"marginTop":"3px"}),
            html.Div([
                html.Span(f"OPC:{d['opc']}",style={"color":"#4a8aaa","fontSize":"9px","marginRight":"10px"}),
                html.Span(f"DPC:{d['dpc']}",style={"color":"#4a8aaa","fontSize":"9px","marginRight":"10px"}),
                html.Span(f"CIC:{d['cic']}",style={"color":"#888","fontSize":"9px","marginRight":"10px"}),
                html.Span(f"SLS:{d['sls']}",style={"color":"#888","fontSize":"9px"}),
            ],style={"marginTop":"2px"}),
        ]))
    return rows

# ══════════════════════════════════════════════════════════════
# EVENT LOG
# ══════════════════════════════════════════════════════════════
def make_log():
    colors={"SETUP":"#00ff88","RELEASE":"#4a90d9","HANDOVER":"#ffd600",
            "BLOCKED":"#ff1744","OVERFLOW_REROUTE":"#ff6d00","EMERGENCY":"#ff1744"}
    return [html.Div(e["detail"],style={"color":colors.get(e["type"],"#aaa"),"fontSize":"9px",
            "marginBottom":"2px","whiteSpace":"nowrap","overflow":"hidden"})
            for e in list(event_log)[:20]]

# ══════════════════════════════════════════════════════════════
# APP LAYOUT
# ══════════════════════════════════════════════════════════════
app = dash.Dash(__name__)
app.title = "SS7 Routing & Signalling Monitor"

LEGEND_ITEMS = [
    ("━━","#ff1744","OpenFlow (SDN Tier-0)"),
    ("━━","#00e5ff","Fiber (Static+MPLS Tier-1)"),
    ("━━","#4a90d9","Microwave (OSPF Tier-2)"),
    ("●","#00e5ff","Idle node"),
    ("●","#00ff88","Low load <50%"),
    ("●","#ffd600","Medium 50-79%"),
    ("●","#ff6d00","High 80-99%"),
    ("●","#ff1744","Full / SDN"),
]

app.layout = html.Div(style={"backgroundColor":"#020a17","color":"white","fontFamily":"'Courier New',monospace","padding":"14px","minHeight":"100vh"},children=[
    # Header
    html.Div(style={"borderBottom":"1px solid #0a2840","paddingBottom":"10px","marginBottom":"12px","display":"flex","justifyContent":"space-between","alignItems":"center"},children=[
        html.Div([
            html.H2("SS7 ROUTING & SIGNALLING SIMULATION",style={"color":"#00e5ff","margin":"0","fontSize":"15px","letterSpacing":"3px"}),
            html.Div("Palapye District Telehealth Network  |  Static+MPLS / OSPF / SDN  |  ISUP · TCAP/MAP · MTP3",
                     style={"color":"#4a8aaa","fontSize":"9px","marginTop":"3px"}),
        ]),
        html.Div(id="tick-hdr",style={"color":"#4a8aaa","fontSize":"10px","textAlign":"right"}),
    ]),

    html.Div(style={"display":"flex","gap":"12px"},children=[

        # LEFT: site meters
        html.Div(style={"width":"190px","flexShrink":"0","overflowY":"auto","maxHeight":"760px"},
                 children=[html.Div(id="sidebar")]),

        # CENTER: map + event log
        html.Div(style={"flex":"1","minWidth":"0"},children=[
            dcc.Graph(id="map-graph",config={"displayModeBar":False}),

            # Event log
            html.Div(style={"marginTop":"8px","background":"#000","border":"1px solid #0a2840","padding":"8px","height":"130px","overflowY":"auto"},children=[
                html.Div("◈ CONTROL PLANE EVENT LOG",style={"color":"#00e5ff","fontSize":"9px","letterSpacing":"2px","marginBottom":"5px"}),
                html.Div(id="event-log"),
            ]),

            # MSC Ladder
            html.Div(style={"marginTop":"8px","background":"#050d1a","border":"1px solid #0a2840","padding":"8px","height":"260px","overflowY":"auto"},children=[
                html.Div("◈ SS7 MESSAGE SEQUENCE (MSC LADDER)  —  OPC / DPC / CIC / SLS",
                         style={"color":"#ffd600","fontSize":"9px","letterSpacing":"2px","marginBottom":"6px"}),
                html.Div(id="msc-ladder"),
            ]),
        ]),

        # RIGHT: GOS + legend
        html.Div(style={"width":"195px","flexShrink":"0"},children=[
            html.Div(id="gos-panel",style={"background":"#060d1a","border":"1px solid #0a2840","padding":"10px","marginBottom":"10px"}),
            html.Div(style={"background":"#060d1a","border":"1px solid #0a2840","padding":"10px"},children=[
                html.Div("LINK LEGEND",style={"color":"#4a8aaa","fontSize":"9px","letterSpacing":"2px","marginBottom":"6px"}),
                *[html.Div([html.Span(sym,style={"color":c,"marginRight":"6px"}),
                            html.Span(lbl,style={"fontSize":"9px","color":"#bbb"})],
                           style={"marginBottom":"4px"}) for sym,c,lbl in LEGEND_ITEMS],
            ]),
        ]),
    ]),

    dcc.Interval(id="heartbeat",interval=1600,n_intervals=0),
])

# ══════════════════════════════════════════════════════════════
# CALLBACKS
# ══════════════════════════════════════════════════════════════
@app.callback(
    [Output("map-graph","figure"),Output("sidebar","children"),
     Output("gos-panel","children"),Output("event-log","children"),
     Output("msc-ladder","children"),Output("tick-hdr","children")],
    Input("heartbeat","n_intervals"),
)
def update(n):
    events=run_tick()
    if packet_anim["visible"]:
        packet_anim["progress"]+=0.33
        if packet_anim["progress"]>=1.0:
            packet_anim["visible"]=False; packet_anim["progress"]=0.0
    latest=events[0] if events else None
    return (make_figure(latest),make_sidebar(),make_gos(),
            make_log(),make_ladder(),
            f"TICK {TICK[0]:04d} | MODE:{ROUTE_MODE[0]} | ACTIVE CALLS:{len(active_calls):02d}")

@app.callback(
    Output("gos-panel","children",allow_duplicate=True),
    [Input("btn-ospf","n_clicks"),Input("btn-static","n_clicks")],
    prevent_initial_call=True
)
def switch_mode(o,s):
    from dash import ctx
    if ctx.triggered_id=="btn-ospf":   ROUTE_MODE[0]="OSPF"
    if ctx.triggered_id=="btn-static": ROUTE_MODE[0]="STATIC"
    return make_gos()

if __name__=="__main__":
    app.run(debug=False,port=8050)