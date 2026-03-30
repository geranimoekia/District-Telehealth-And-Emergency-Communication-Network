import dash
from dash import html, dcc, Input, Output
import plotly.graph_objects as go
import random
import math
from collections import deque

# ── DMS helper
def dms(d, m, s, direction):
    dd = d + m/60 + s/3600
    return -dd if direction in ("S","W") else dd

# ══════════════════════════════════════════════════════════════
# NETWORK TOPOLOGY
# ══════════════════════════════════════════════════════════════
SITES = [
    {"name":"SDN", "label":"SDN Controller (Core)",       "lat":dms(22,50,0,"S"),  "lon":dms(23,59,42,"E"), "channels":99,"tier":0,"type":"sdn",       "pc":"1-1-1"},
    {"name":"CR-1","label":"District Hospital (SSP/STP)", "lat":dms(22,59,59,"S"), "lon":dms(23,59,42,"E"), "channels":8, "tier":1,"type":"controller", "pc":"1-1-2"},
    {"name":"CR-2","label":"Co-located Controller (SSP)", "lat":dms(22,59,40,"S"), "lon":dms(23,59,20,"E"), "channels":8, "tier":1,"type":"controller", "pc":"1-1-3"},
    {"name":"BS1", "label":"Clinic North-West",           "lat":dms(22,51,52,"S"), "lon":dms(23,49,42,"E"), "channels":4, "tier":2,"type":"bs",         "pc":"2-1-1"},
    {"name":"BS2", "label":"Clinic North-East",           "lat":dms(22,51,52,"S"), "lon":dms(24, 9,42,"E"), "channels":4, "tier":2,"type":"bs",         "pc":"2-1-2"},
    {"name":"BS3", "label":"Clinic South-West",           "lat":dms(23, 8, 5,"S"), "lon":dms(23,49,42,"E"), "channels":4, "tier":2,"type":"bs",         "pc":"2-2-1"},
    {"name":"BS4", "label":"Clinic South",                "lat":dms(23, 9,10,"S"), "lon":dms(23,59,42,"E"), "channels":4, "tier":2,"type":"bs",         "pc":"2-2-2"},
    {"name":"BS5", "label":"Clinic South-East",           "lat":dms(23, 8, 5,"S"), "lon":dms(24, 9,42,"E"), "channels":4, "tier":2,"type":"bs",         "pc":"2-2-3"},
]

LINKS = [
    {"source":"SDN", "target":"CR-1","type":"OpenFlow",    "routing":"SDN",        "capacity":99,"cost":1},
    {"source":"SDN", "target":"CR-2","type":"OpenFlow",    "routing":"SDN",        "capacity":99,"cost":1},
    {"source":"CR-1","target":"CR-2","type":"Fiber",       "routing":"STATIC+MPLS","capacity":16,"cost":2},
    {"source":"CR-1","target":"BS1", "type":"Microwave",   "routing":"OSPF",       "capacity":4, "cost":5},
    {"source":"CR-1","target":"BS2", "type":"Microwave",   "routing":"OSPF",       "capacity":4, "cost":5},
    {"source":"CR-2","target":"BS3", "type":"Microwave",   "routing":"OSPF",       "capacity":4, "cost":5},
    {"source":"CR-2","target":"BS4", "type":"Fiber",       "routing":"STATIC+MPLS","capacity":4, "cost":3},
    {"source":"CR-2","target":"BS5", "type":"Microwave",   "routing":"OSPF",       "capacity":4, "cost":5},
    {"source":"BS1", "target":"BS2", "type":"Microwave",   "routing":"OSPF",       "capacity":2, "cost":8},
    {"source":"BS3", "target":"BS4", "type":"Microwave",   "routing":"OSPF",       "capacity":2, "cost":8},
    {"source":"BS4", "target":"BS5", "type":"Microwave",   "routing":"OSPF",       "capacity":2, "cost":8},
]

SITE_MAP   = {s["name"]: s for s in SITES}
LINK_LOOKUP= {}
for lk in LINKS:
    LINK_LOOKUP[(lk["source"],lk["target"])] = lk
    LINK_LOOKUP[(lk["target"],lk["source"])] = lk

# ══════════════════════════════════════════════════════════════
# 7 AMBULANCES — mobile devices that roam around the district
# Each has a current position, a target BS it drives toward,
# a status, and signalling state
# ══════════════════════════════════════════════════════════════
# Spread initial positions around the district
AMB_INIT = [
    {"lat": dms(22,54,10,"S"), "lon": dms(23,53,20,"E")},
    {"lat": dms(22,56,30,"S"), "lon": dms(24, 5,10,"E")},
    {"lat": dms(23, 2,45,"S"), "lon": dms(23,51,30,"E")},
    {"lat": dms(23, 5,20,"S"), "lon": dms(24, 7,40,"E")},
    {"lat": dms(22,58,50,"S"), "lon": dms(23,57,10,"E")},
    {"lat": dms(23, 3,30,"S"), "lon": dms(24, 2,20,"E")},
    {"lat": dms(22,53,15,"S"), "lon": dms(24, 0,55,"E")},
]

AMBULANCES = []
for i, pos in enumerate(AMB_INIT):
    AMBULANCES.append({
        "id":       f"AMB-{i+1}",
        "lat":      pos["lat"],
        "lon":      pos["lon"],
        "target_bs": random.choice(["BS1","BS2","BS3","BS4","BS5"]),
        "status":   "PATROLLING",   # PATROLLING / RESPONDING / CALLING / AUTH_WAIT
        "active_call": None,
        "auth_done": False,
        "speed":    random.uniform(0.0008, 0.0015),  # degrees per tick
        "calls":    0,
        "handovers":0,
        "color":    "#ff1744",
    })

# ══════════════════════════════════════════════════════════════
# SS7 / SIGNALLING DEFINITIONS
# ══════════════════════════════════════════════════════════════
SS7_MSGS = {
    # ISUP
    "IAM":        {"desc":"Initial Address Message",    "layer":"ISUP",    "color":"#00ff88"},
    "ACM":        {"desc":"Address Complete Message",   "layer":"ISUP",    "color":"#00e5ff"},
    "ANM":        {"desc":"Answer Message",             "layer":"ISUP",    "color":"#00e5ff"},
    "REL":        {"desc":"Release Message",            "layer":"ISUP",    "color":"#ff6d00"},
    "RLC":        {"desc":"Release Complete",           "layer":"ISUP",    "color":"#ff6d00"},
    "BLO":        {"desc":"Blocking — GOS exceeded",    "layer":"ISUP",    "color":"#ff1744"},
    # TCAP/MAP
    "TC-BEGIN":   {"desc":"TCAP Begin",                 "layer":"TCAP/MAP","color":"#b388ff"},
    "MAP-SRI":    {"desc":"Send Routing Info",          "layer":"TCAP/MAP","color":"#ea80fc"},
    "MAP-PRN":    {"desc":"Provide Roaming Number",     "layer":"TCAP/MAP","color":"#ea80fc"},
    "TC-END":     {"desc":"TCAP End",                   "layer":"TCAP/MAP","color":"#b388ff"},
    "MAP-UL":     {"desc":"Update Location",            "layer":"TCAP/MAP","color":"#ea80fc"},
    # SIP (teleconsultation)
    "SIP-INVITE": {"desc":"SIP Invite (session start)", "layer":"SIP",     "color":"#40c4ff"},
    "SIP-200":    {"desc":"SIP 200 OK",                 "layer":"SIP",     "color":"#40c4ff"},
    "SIP-BYE":    {"desc":"SIP BYE (session end)",      "layer":"SIP",     "color":"#40c4ff"},
    # AAA Diameter
    "DIA-REQ":    {"desc":"Diameter Auth-Request",      "layer":"Diameter","color":"#ffd600"},
    "DIA-ANS":    {"desc":"Diameter Auth-Answer (OK)",  "layer":"Diameter","color":"#ffd600"},
    # RSVP-TE
    "RSVP-PATH":  {"desc":"RSVP-TE Path (QoS reserve)", "layer":"RSVP-TE","color":"#ff6d00"},
    "RSVP-RESV":  {"desc":"RSVP-TE Resv (confirmed)",   "layer":"RSVP-TE","color":"#ff6d00"},
    # Emergency (no AAA — SDN preemption)
    "EMG-IAM":    {"desc":"Emergency IAM (no auth)",    "layer":"SDN-PREEMPT","color":"#ff1744"},
    "OF-PREEMPT": {"desc":"OpenFlow Preemption Rule",   "layer":"SDN-PREEMPT","color":"#ff1744"},
}

# ══════════════════════════════════════════════════════════════
# STATE
# ══════════════════════════════════════════════════════════════
for s in SITES:
    s["in_use"]=0; s["calls"]=0; s["blocked"]=0; s["handovers"]=0

active_calls  = {}
call_counter  = [0]
event_log     = deque(maxlen=80)
ladder_log    = deque(maxlen=14)
TICK          = [0]
ROUTE_MODE    = ["OSPF"]
gos_stats     = {"total":0,"blocked":0,"handovers":0,"setups":0,"releases":0,"reroutes":0,"emergency":0}

# Multi-packet animations
packets = []  # list of {path, progress, color, label}

STATIC_TABLE = {"BS1":"CR-1","BS2":"CR-1","BS3":"CR-2","BS4":"CR-2","BS5":"CR-2"}
OSPF_COSTS   = {
    ("BS1","CR-1"):5,("BS1","CR-2"):7,
    ("BS2","CR-1"):5,("BS2","CR-2"):7,
    ("BS3","CR-2"):5,("BS3","CR-1"):7,
    ("BS4","CR-2"):3,("BS4","CR-1"):5,
    ("BS5","CR-2"):5,("BS5","CR-1"):7,
}

def pick_route(bs_name, mode="OSPF"):
    candidates = ["CR-1","CR-2"]
    if mode=="STATIC":
        preferred = STATIC_TABLE.get(bs_name,"CR-1")
        for c in [preferred]+[x for x in candidates if x!=preferred]:
            if SITE_MAP[c]["in_use"] < SITE_MAP[c]["channels"]: return c,"STATIC"
        return None,"STATIC"
    else:
        ranked = sorted(candidates, key=lambda c: OSPF_COSTS.get((bs_name,c),99))
        for c in ranked:
            if SITE_MAP[c]["in_use"] < SITE_MAP[c]["channels"]: return c,"OSPF"
        return None,"OSPF"

def add_ladder(msg, src, dst, etype):
    info = SS7_MSGS.get(msg,{})
    src_pc = SITE_MAP.get(src,{}).get("pc","?") if src in SITE_MAP else "MOB"
    dst_pc = SITE_MAP.get(dst,{}).get("pc","?") if dst in SITE_MAP else "MOB"
    cic = random.randint(1,31); sls=random.randint(0,15)
    ladder_log.appendleft({
        "msg":msg,"layer":info.get("layer","?"),"desc":info.get("desc",""),
        "color":info.get("color","#aaa"),
        "src":src,"dst":dst,"opc":src_pc,"dpc":dst_pc,"cic":cic,"sls":sls,"type":etype
    })

def add_packet(path, color, label=""):
    packets.append({"path":path,"progress":0.0,"color":color,"label":label})

# ══════════════════════════════════════════════════════════════
# AMBULANCE MOVEMENT ENGINE
# ══════════════════════════════════════════════════════════════
def move_ambulances():
    for amb in AMBULANCES:
        tgt = SITE_MAP.get(amb["target_bs"])
        if not tgt: continue
        dlat = tgt["lat"] - amb["lat"]
        dlon = tgt["lon"] - amb["lon"]
        dist = math.sqrt(dlat**2 + dlon**2)
        if dist < 0.01:
            # Reached target — pick new destination
            amb["target_bs"] = random.choice(["BS1","BS2","BS3","BS4","BS5"])
            amb["status"] = "PATROLLING"
        else:
            step = min(amb["speed"], dist)
            amb["lat"] += (dlat/dist)*step
            amb["lon"] += (dlon/dist)*step

def nearest_bs(amb):
    bs_sites = [s for s in SITES if s["type"]=="bs"]
    return min(bs_sites, key=lambda s: (s["lat"]-amb["lat"])**2+(s["lon"]-amb["lon"])**2)

# ══════════════════════════════════════════════════════════════
# MAIN SIGNALLING TICK
# ══════════════════════════════════════════════════════════════
def run_tick():
    TICK[0] += 1
    mode = ROUTE_MODE[0]
    events = []

    # Move ambulances
    move_ambulances()

    # ── 1. AMBULANCE EMERGENCY CALL (20% chance per tick) ──
    for amb in AMBULANCES:
        if random.random() < 0.20 and amb["status"]=="PATROLLING":
            amb["status"] = "RESPONDING"
            # Emergency → NO AAA, SDN preemption directly
            nb = nearest_bs(amb)
            ctrl = "CR-1"  # emergency always hits primary controller
            cid = f"EMG-{call_counter[0]:03d}"; call_counter[0]+=1
            amb["active_call"] = cid; amb["calls"]+=1
            gos_stats["emergency"]+=1; gos_stats["total"]+=1; gos_stats["setups"]+=1

            # Signalling sequence: OF-PREEMPT → EMG-IAM → ACM → ANM
            for msg,src,dst in [("OF-PREEMPT","SDN",ctrl),("EMG-IAM",amb["id"],ctrl),("ACM",ctrl,amb["id"]),("ANM",ctrl,amb["id"])]:
                add_ladder(msg, src, dst, "EMERGENCY")

            path_drawn = [nb["name"], ctrl, "SDN"]
            add_packet([nb["name"],ctrl],"#ff1744","EMG")
            add_packet([ctrl,"SDN"],"#ff1744","OF")

            ev = {
                "tick":TICK[0],"type":"EMERGENCY","site":nb["name"],"route":ctrl,
                "path":path_drawn,"call":cid,"routing":"SDN-PREEMPT",
                "detail": f"🚨 {amb['id']} EMERGENCY | NO-AUTH→SDN PREEMPT | OF-PREEMPT+EMG-IAM | {nb['name']}→{ctrl}→SDN"
            }
            events.append(ev); event_log.appendleft(ev)
            break  # one emergency per tick max

    # ── 2. AMBULANCE HANDOVER (when moving between BS coverage) ──
    for amb in AMBULANCES:
        if amb["active_call"] and random.random()<0.12:
            nb = nearest_bs(amb)
            old_call = amb["active_call"]
            amb["handovers"]+=1; gos_stats["handovers"]+=1
            for msg,src,dst in [("TC-BEGIN",nb["name"],"CR-1"),("MAP-SRI","CR-1",nb["name"]),
                                 ("MAP-PRN",nb["name"],"CR-1"),("MAP-UL",nb["name"],"CR-1"),("TC-END","CR-1",nb["name"])]:
                add_ladder(msg,src,dst,"HANDOVER")
            add_packet([nb["name"],"CR-1"],"#ffd600","HO")
            ev={"tick":TICK[0],"type":"HANDOVER","site":nb["name"],"route":"CR-1",
                "path":[nb["name"],"CR-1"],"call":old_call,"routing":mode,
                "detail":f"↔ {amb['id']} HANDOVER | {nb['name']}→CR-1 | TC-BEGIN/MAP-SRI/PRN/UL/TC-END"}
            events.append(ev); event_log.appendleft(ev)
            break

    # ── 3. NORMAL BS CALL with full AAA + ISUP/SIP/RSVP ──
    if random.random()<0.38:
        bs = random.choice([s for s in SITES if s["type"]=="bs"])
        ctrl,rmode = pick_route(bs["name"],mode)
        gos_stats["total"]+=1

        if ctrl and bs["in_use"]<bs["channels"] and SITE_MAP[ctrl]["in_use"]<SITE_MAP[ctrl]["channels"]:
            bs["in_use"]+=1; bs["calls"]+=1; SITE_MAP[ctrl]["in_use"]+=1
            cid=f"C{call_counter[0]:04d}"; call_counter[0]+=1
            cic=random.randint(1,31)
            active_calls[cid]={"site":bs["name"],"ctrl":ctrl,"cic":cic,"tick":TICK[0]}
            gos_stats["setups"]+=1

            # Determine traffic type
            traffic = random.choice(["TELECONSULT","MONITORING","ROUTINE"])

            if traffic=="TELECONSULT":
                # SIP + RSVP-TE + MPLS
                for msg,src,dst in [("DIA-REQ",bs["name"],"SDN"),("DIA-ANS","SDN",bs["name"]),
                                     ("RSVP-PATH",bs["name"],ctrl),("RSVP-RESV",ctrl,bs["name"]),
                                     ("SIP-INVITE",bs["name"],ctrl),("SIP-200",ctrl,bs["name"])]:
                    add_ladder(msg,src,dst,"SETUP")
                add_packet([bs["name"],"SDN"],"#ffd600","DIA")
                add_packet([bs["name"],ctrl],"#40c4ff","SIP")
                add_packet([bs["name"],ctrl],"#ff6d00","RSVP")
                detail=f"▶ TELECONSULT {cid} | DIA-REQ→SIP-INVITE→RSVP-PATH | {bs['name']}→{ctrl} | {rmode}"

            elif traffic=="MONITORING":
                # Diameter AAA + OSPF/ISUP
                for msg,src,dst in [("DIA-REQ",bs["name"],"SDN"),("DIA-ANS","SDN",bs["name"]),
                                     ("IAM",bs["name"],ctrl),("ACM",ctrl,bs["name"]),("ANM",ctrl,bs["name"])]:
                    add_ladder(msg,src,dst,"SETUP")
                add_packet([bs["name"],"SDN"],"#ffd600","DIA")
                add_packet([bs["name"],ctrl],"#00ff88","IAM")
                detail=f"▶ MONITORING {cid} | DIA-REQ+IAM/ACM/ANM | {bs['name']}→{ctrl} | {rmode}"

            else:
                # Routine ISUP only
                for msg,src,dst in [("IAM",bs["name"],ctrl),("ACM",ctrl,bs["name"]),("ANM",ctrl,bs["name"])]:
                    add_ladder(msg,src,dst,"SETUP")
                add_packet([bs["name"],ctrl],"#00ff88","IAM")
                detail=f"▶ ROUTINE {cid} | IAM/ACM/ANM | {bs['name']}→{ctrl} | {rmode} | CIC:{cic}"

            ev={"tick":TICK[0],"type":"SETUP","site":bs["name"],"route":ctrl,
                "path":[bs["name"],ctrl],"call":cid,"routing":rmode,"detail":detail}
            events.append(ev); event_log.appendleft(ev)

        else:
            # BLOCKED
            alt = "CR-2" if STATIC_TABLE.get(bs["name"])=="CR-1" else "CR-1"
            if SITE_MAP[alt]["in_use"]<SITE_MAP[alt]["channels"] and bs["in_use"]<bs["channels"]:
                bs["in_use"]+=1; SITE_MAP[alt]["in_use"]+=1
                cid=f"C{call_counter[0]:04d}"; call_counter[0]+=1
                active_calls[cid]={"site":bs["name"],"ctrl":alt,"cic":random.randint(1,31),"tick":TICK[0]}
                gos_stats["reroutes"]+=1; gos_stats["setups"]+=1
                add_ladder("IAM",bs["name"],alt,"REROUTE")
                add_packet([bs["name"],alt],"#ff6d00","RRT")
                ev={"tick":TICK[0],"type":"OVERFLOW_REROUTE","site":bs["name"],"route":alt,
                    "path":[bs["name"],alt],"call":cid,"routing":"OSPF-OVERFLOW",
                    "detail":f"⚡ REROUTE {cid} | {bs['name']}→{alt} | OSPF overflow | IAM"}
            else:
                bs["blocked"]+=1; gos_stats["blocked"]+=1
                add_ladder("BLO",bs["name"],STATIC_TABLE.get(bs["name"],"CR-1"),"BLOCKED")
                ev={"tick":TICK[0],"type":"BLOCKED","site":bs["name"],"route":None,
                    "path":[],"call":None,"routing":mode,
                    "detail":f"✖ BLOCKED | {bs['name']} | GOS LIMIT | BLO | PC:{SITE_MAP[bs['name']]['pc']}"}
            events.append(ev); event_log.appendleft(ev)

    # ── 4. RELEASE ──
    if active_calls and random.random()<0.25:
        cid=random.choice(list(active_calls.keys()))
        call=active_calls.pop(cid)
        SITE_MAP[call["site"]]["in_use"]=max(0,SITE_MAP[call["site"]]["in_use"]-1)
        SITE_MAP[call["ctrl"]]["in_use"]=max(0,SITE_MAP[call["ctrl"]]["in_use"]-1)
        gos_stats["releases"]+=1
        for msg,src,dst in [("REL",call["site"],call["ctrl"]),("RLC",call["ctrl"],call["site"])]:
            add_ladder(msg,src,dst,"RELEASE")
        add_packet([call["ctrl"],call["site"]],"#4a90d9","RLC")
        ev={"tick":TICK[0],"type":"RELEASE","site":call["site"],"route":call["ctrl"],
            "path":[call["ctrl"],call["site"]],"call":cid,"routing":mode,
            "detail":f"◀ RELEASE {cid} | {call['site']}←{call['ctrl']} | REL/RLC | CIC:{call['cic']}"}
        events.append(ev); event_log.appendleft(ev)

    # Advance all packet animations
    for pkt in packets[:]:
        pkt["progress"]+=0.4
        if pkt["progress"]>=1.0:
            packets.remove(pkt)

    return events

# ══════════════════════════════════════════════════════════════
# COLOR HELPERS
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

def link_color(lk):
    r=lk.get("routing","")
    if r=="SDN": return "#ff1744"
    if r=="STATIC+MPLS": return "#00e5ff"
    return "#4a90d9"

# ══════════════════════════════════════════════════════════════
# AMBULANCE SVG ICON (rendered as DivIcon via Scattermapbox text)
# We use a Unicode ambulance + colour overlay approach
# ══════════════════════════════════════════════════════════════
STATUS_COLORS = {
    "PATROLLING":"#ff9800",
    "RESPONDING":"#ff1744",
    "CALLING":   "#00ff88",
    "HANDOVER":  "#ffd600",
}

# ══════════════════════════════════════════════════════════════
# MAP BUILDER
# ══════════════════════════════════════════════════════════════
def make_figure(latest=None):
    fig = go.Figure()

    # 1. Base links
    for lk in LINKS:
        src=SITE_MAP[lk["source"]]; tgt=SITE_MAP[lk["target"]]
        fig.add_trace(go.Scattermapbox(
            lat=[src["lat"],tgt["lat"],None],lon=[src["lon"],tgt["lon"],None],
            mode="lines",line=dict(width=4 if lk["type"]=="Fiber" else 2,color=link_color(lk)),
            opacity=0.45,hoverinfo="skip",showlegend=False
        ))
        mid_lat=(src["lat"]+tgt["lat"])/2; mid_lon=(src["lon"]+tgt["lon"])/2
        fig.add_trace(go.Scattermapbox(
            lat=[mid_lat],lon=[mid_lon],mode="text",
            text=[lk["routing"]],textfont=dict(size=7,color=link_color(lk)),
            hoverinfo="skip",showlegend=False
        ))

    # 2. Active route highlight
    if latest and latest.get("path") and len(latest["path"])>=2:
        path=latest["path"]; ec=event_color(latest["type"])
        for i in range(len(path)-1):
            if path[i] in SITE_MAP and path[i+1] in SITE_MAP:
                a=SITE_MAP[path[i]]; b=SITE_MAP[path[i+1]]
                fig.add_trace(go.Scattermapbox(
                    lat=[a["lat"],b["lat"],None],lon=[a["lon"],b["lon"],None],
                    mode="lines",line=dict(width=7,color=ec),opacity=0.85,
                    hoverinfo="skip",showlegend=False
                ))

    # 3. Packet animations (multiple simultaneous)
    for pkt in packets:
        if len(pkt["path"])>=2:
            a=SITE_MAP.get(pkt["path"][0]); b=SITE_MAP.get(pkt["path"][1])
            if a and b:
                p=min(pkt["progress"],1.0)
                mlat=a["lat"]+(b["lat"]-a["lat"])*p
                mlon=a["lon"]+(b["lon"]-a["lon"])*p
                fig.add_trace(go.Scattermapbox(
                    lat=[mlat],lon=[mlon],mode="markers+text",
                    marker=dict(size=13,color=pkt["color"],opacity=0.95),
                    text=[pkt["label"]],textfont=dict(size=8,color="white"),
                    textposition="top right",hoverinfo="skip",showlegend=False
                ))

    # 4. Network site nodes
    for s in SITES:
        ratio=s["in_use"]/s["channels"] if s["channels"]<99 else 0
        is_sdn=s["type"]=="sdn"; is_ctrl=s["type"]=="controller"
        size=30 if is_sdn else 24 if is_ctrl else 17
        color="#ff1744" if is_sdn else usage_color(ratio)
        if latest and s["name"] in (latest.get("path") or []):
            size+=10
        tier_lbl={0:"Tier-0 SDN",1:"Tier-1 CORE (co-located)",2:"Tier-2 BS"}.get(s["tier"],"")
        fig.add_trace(go.Scattermapbox(
            lat=[s["lat"]],lon=[s["lon"]],
            mode="markers+text",
            marker=dict(size=size,color=color,opacity=0.93),
            text=[f"{s['name']}\nPC:{s['pc']}"],
            textposition="top right",
            textfont=dict(color="white",size=9),
            hovertemplate=(f"<b>{s['name']} — {s['label']}</b><br>{tier_lbl}<br>"
                           f"PC:{s['pc']}<br>Channels:{s['in_use']}/{s['channels']}<br>"
                           f"Calls:{s.get('calls',0)} Blocked:{s.get('blocked',0)}<extra></extra>"),
            showlegend=False
        ))

    # 5. AMBULANCES — rendered as emoji markers with status colour
    for amb in AMBULANCES:
        sc = STATUS_COLORS.get(amb["status"],"#ff9800")
        # Outer glow ring
        fig.add_trace(go.Scattermapbox(
            lat=[amb["lat"]],lon=[amb["lon"]],mode="markers",
            marker=dict(size=26,color=sc,opacity=0.25),
            hoverinfo="skip",showlegend=False
        ))
        # Ambulance body marker
        fig.add_trace(go.Scattermapbox(
            lat=[amb["lat"]],lon=[amb["lon"]],
            mode="markers+text",
            marker=dict(size=14,color=sc,opacity=1.0,symbol="circle"),
            text=[f"🚑"],
            textposition="middle center",
            textfont=dict(size=14),
            hovertemplate=(
                f"<b>{amb['id']}</b><br>"
                f"Status: {amb['status']}<br>"
                f"Nearest BS: {nearest_bs(amb)['name']}<br>"
                f"Calls: {amb['calls']} | HO: {amb['handovers']}"
                "<extra></extra>"
            ),
            showlegend=False
        ))
        # Label
        fig.add_trace(go.Scattermapbox(
            lat=[amb["lat"]],lon=[amb["lon"]],mode="text",
            text=[amb["id"]],textposition="top right",
            textfont=dict(size=8,color=sc),
            hoverinfo="skip",showlegend=False
        ))

    center_lat=sum(s["lat"] for s in SITES)/len(SITES)
    center_lon=sum(s["lon"] for s in SITES)/len(SITES)
    fig.update_layout(
        mapbox=dict(style="open-street-map",center=dict(lat=center_lat,lon=center_lon),zoom=9),
        margin=dict(l=0,r=0,t=0,b=0),height=500,paper_bgcolor="#020a17",
    )
    return fig

# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
def make_sidebar():
    rows=[]
    for tier,label,color in [(0,"TIER 0 — SDN CONTROLLER","#ff1744"),
                              (1,"TIER 1 — CORE (Co-located, Static+MPLS)","#00e5ff"),
                              (2,"TIER 2 — EDGE CLINICS (OSPF)","#4a90d9")]:
        rows.append(html.Div(label,style={"color":color,"fontSize":"8px","letterSpacing":"1px",
                                          "marginTop":"10px","marginBottom":"5px","fontWeight":"bold"}))
        for s in [x for x in SITES if x["tier"]==tier]:
            ratio=s["in_use"]/s["channels"] if s["channels"]<99 else 0
            pct=ratio*100
            bc="#ff1744" if pct>=100 else "#ff6d00" if pct>=80 else "#ffd600" if pct>=50 else "#00ff88"
            rows.append(html.Div(style={"marginBottom":"7px","padding":"6px","background":"#060d1a",
                                        "border":"1px solid #0a2840","borderRadius":"3px"},children=[
                html.Div([html.Span(s["name"],style={"fontSize":"10px","fontWeight":"bold","color":"white"}),
                          html.Span(f"PC:{s['pc']}",style={"fontSize":"7px","color":"#555"})],
                         style={"display":"flex","justifyContent":"space-between"}),
                html.Div(s["label"],style={"fontSize":"7px","color":"#4a8aaa","marginBottom":"3px"}),
                html.Div(style={"height":"3px","background":"#111","borderRadius":"2px","marginBottom":"3px"},children=[
                    html.Div(style={"height":"100%","width":f"{pct:.0f}%","background":bc,"borderRadius":"2px"})
                ]),
                html.Div([html.Span(f"▶{s.get('calls',0)}",style={"fontSize":"8px","color":"#00ff88","marginRight":"5px"}),
                          html.Span(f"✖{s.get('blocked',0)}",style={"fontSize":"8px","color":"#ff1744","marginRight":"5px"}),
                          html.Span(f"{s['in_use']}/{s['channels']}ch",style={"fontSize":"8px","color":bc})]),
            ]))

    # Ambulance status
    rows.append(html.Div("AMBULANCES (7)",style={"color":"#ff9800","fontSize":"8px","letterSpacing":"1px",
                                                  "marginTop":"12px","marginBottom":"5px","fontWeight":"bold"}))
    for amb in AMBULANCES:
        sc=STATUS_COLORS.get(amb["status"],"#ff9800")
        rows.append(html.Div(style={"marginBottom":"5px","padding":"5px","background":"#060d1a",
                                    "border":f"1px solid {sc}44","borderRadius":"3px"},children=[
            html.Div([html.Span(f"🚑 {amb['id']}",style={"fontSize":"9px","color":"white"}),
                      html.Span(amb["status"],style={"fontSize":"7px","color":sc})],
                     style={"display":"flex","justifyContent":"space-between"}),
            html.Div(f"Nearest: {nearest_bs(amb)['name']} | Calls:{amb['calls']} HO:{amb['handovers']}",
                     style={"fontSize":"7px","color":"#4a8aaa"}),
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
        return html.Div([html.Span(l,style={"fontSize":"8px","color":"#4a8aaa"}),
                         html.Span(v,style={"fontSize":"9px","color":c,"fontWeight":"bold"})],
                        style={"display":"flex","justifyContent":"space-between","marginBottom":"4px"})
    return [
        html.Div("GOS & QoS METRICS",style={"color":"#ffd600","fontSize":"8px","letterSpacing":"2px","marginBottom":"7px"}),
        stat("Active Calls",    str(len(active_calls)),          "#00ff88"),
        stat("Ambulances Active",str(sum(1 for a in AMBULANCES if a["status"]!="PATROLLING")),"#ff1744"),
        stat("Total Attempts",  str(gos_stats["total"]),         "#00e5ff"),
        stat("Setups OK",       str(gos_stats["setups"]),        "#00ff88"),
        stat("Releases",        str(gos_stats["releases"]),      "#4a90d9"),
        stat("Blocked (GOS)",   str(gos_stats["blocked"]),       "#ff1744"),
        stat("Handovers",       str(gos_stats["handovers"]),     "#ffd600"),
        stat("Emergency Calls", str(gos_stats["emergency"]),     "#ff1744"),
        stat("OSPF Reroutes",   str(gos_stats["reroutes"]),      "#ff6d00"),
        stat("Grade of Service",f"{gos:.1f}%",                   "#ff1744" if gos>5 else "#00ff88"),
        html.Div(style={"height":"4px","background":"#111","borderRadius":"2px","marginBottom":"10px"},children=[
            html.Div(style={"height":"100%","width":f"{min(gos,100):.1f}%","background":"#ff1744","borderRadius":"2px"})
        ]),
        html.Div("ROUTE MODE",style={"color":"#ffd600","fontSize":"8px","letterSpacing":"2px","marginBottom":"6px"}),
        html.Div([
            html.Button("OSPF",id="btn-ospf",n_clicks=0,style={
                "background":"#00e5ff" if ROUTE_MODE[0]=="OSPF" else "#0a1a2e",
                "color":"#000" if ROUTE_MODE[0]=="OSPF" else "#00e5ff",
                "border":"1px solid #00e5ff","padding":"3px 8px","fontSize":"8px",
                "cursor":"pointer","marginRight":"4px","fontFamily":"monospace"}),
            html.Button("STATIC",id="btn-static",n_clicks=0,style={
                "background":"#ffd600" if ROUTE_MODE[0]=="STATIC" else "#0a1a2e",
                "color":"#000" if ROUTE_MODE[0]=="STATIC" else "#ffd600",
                "border":"1px solid #ffd600","padding":"3px 8px","fontSize":"8px",
                "cursor":"pointer","fontFamily":"monospace"}),
        ]),
        html.Div(f"Mode: {ROUTE_MODE[0]} | {used}/{total_ch} ch used",
                 style={"fontSize":"8px","color":"#4a8aaa","marginTop":"5px"}),
    ]

# ══════════════════════════════════════════════════════════════
# MSC LADDER
# ══════════════════════════════════════════════════════════════
def make_ladder():
    rows=[]
    type_colors={"SETUP":"#00ff88","RELEASE":"#4a90d9","HANDOVER":"#ffd600",
                 "BLOCKED":"#ff1744","REROUTE":"#ff6d00","EMERGENCY":"#ff1744"}
    for e in list(ladder_log)[:12]:
        tc=type_colors.get(e["type"],"#aaa"); mc=e.get("color","#aaa")
        rows.append(html.Div(style={"marginBottom":"5px","padding":"5px","background":"#080f1a",
                                    "border":f"1px solid {tc}22","borderLeft":f"3px solid {mc}"},children=[
            html.Div([html.Span(e["msg"],style={"color":mc,"fontWeight":"bold","fontSize":"10px","marginRight":"6px"}),
                      html.Span(e["layer"],style={"color":"#555","fontSize":"8px","marginRight":"6px"}),
                      html.Span(e["desc"],style={"color":"#555","fontSize":"8px"})]),
            html.Div([html.Span(e["src"],style={"color":"#00e5ff","fontSize":"9px"}),
                      html.Span(" ──▶ ",style={"color":mc}),
                      html.Span(e["dst"],style={"color":"#00e5ff","fontSize":"9px"})],style={"margin":"2px 0"}),
            html.Div([html.Span(f"OPC:{e['opc']}",style={"color":"#4a8aaa","fontSize":"8px","marginRight":"8px"}),
                      html.Span(f"DPC:{e['dpc']}",style={"color":"#4a8aaa","fontSize":"8px","marginRight":"8px"}),
                      html.Span(f"CIC:{e['cic']}",style={"color":"#555","fontSize":"8px","marginRight":"8px"}),
                      html.Span(f"SLS:{e['sls']}",style={"color":"#555","fontSize":"8px"})]),
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
# LAYOUT
# ══════════════════════════════════════════════════════════════
app = dash.Dash(__name__)
app.title = "SS7 Routing & Signalling — Palapye Telehealth"

LEGEND = [
    ("━━","#ff1744","OpenFlow (SDN Tier-0)"),
    ("━━","#00e5ff","Fiber (Static+MPLS)"),
    ("━━","#4a90d9","Microwave (OSPF)"),
    ("●","#00e5ff","Node: Idle"),("●","#00ff88","Node: Low <50%"),
    ("●","#ffd600","Node: Med 50-79%"),("●","#ff6d00","Node: High 80-99%"),("●","#ff1744","Node: Full/SDN"),
    ("🚑","#ff9800","Ambulance: Patrolling"),("🚑","#ff1744","Ambulance: Emergency"),
    ("▶","#00ff88","Packet: ISUP/SIP"),("▶","#ffd600","Packet: Diameter"),
    ("▶","#ff6d00","Packet: RSVP-TE"),("▶","#ff1744","Packet: Emergency"),
]

app.layout = html.Div(style={"backgroundColor":"#020a17","color":"white",
    "fontFamily":"'Courier New',monospace","padding":"12px","minHeight":"100vh"},children=[
    # Header
    html.Div(style={"borderBottom":"1px solid #0a2840","paddingBottom":"8px","marginBottom":"10px",
                    "display":"flex","justifyContent":"space-between","alignItems":"center"},children=[
        html.Div([
            html.H2("SS7 · SIP · DIAMETER · RSVP-TE  SIGNALLING SIMULATION",
                    style={"color":"#00e5ff","margin":"0","fontSize":"13px","letterSpacing":"2px"}),
            html.Div("Palapye District Telehealth  |  Static+MPLS / OSPF / SDN-Preempt  |  7 Ambulances  |  Full Protocol Stack",
                     style={"color":"#4a8aaa","fontSize":"8px","marginTop":"2px"}),
        ]),
        html.Div(id="tick-hdr",style={"color":"#4a8aaa","fontSize":"9px","textAlign":"right"}),
    ]),

    html.Div(style={"display":"flex","gap":"10px"},children=[
        # LEFT sidebar
        html.Div(style={"width":"175px","flexShrink":"0","overflowY":"auto","maxHeight":"820px"},
                 children=[html.Div(id="sidebar")]),
        # CENTER
        html.Div(style={"flex":"1","minWidth":"0"},children=[
            dcc.Graph(id="map-graph",config={"displayModeBar":False}),
            html.Div(style={"marginTop":"6px","background":"#000","border":"1px solid #0a2840",
                            "padding":"7px","height":"110px","overflowY":"auto"},children=[
                html.Div("◈ CONTROL PLANE EVENT LOG",style={"color":"#00e5ff","fontSize":"8px","letterSpacing":"2px","marginBottom":"4px"}),
                html.Div(id="event-log"),
            ]),
            html.Div(style={"marginTop":"6px","background":"#050d1a","border":"1px solid #0a2840",
                            "padding":"7px","height":"240px","overflowY":"auto"},children=[
                html.Div("◈ SS7/SIP/DIAMETER MESSAGE SEQUENCE (MSC LADDER)  —  OPC · DPC · CIC · SLS",
                         style={"color":"#ffd600","fontSize":"8px","letterSpacing":"2px","marginBottom":"5px"}),
                html.Div(id="msc-ladder"),
            ]),
        ]),
        # RIGHT
        html.Div(style={"width":"185px","flexShrink":"0"},children=[
            html.Div(id="gos-panel",style={"background":"#060d1a","border":"1px solid #0a2840",
                                           "padding":"10px","marginBottom":"8px"}),
            html.Div(style={"background":"#060d1a","border":"1px solid #0a2840","padding":"10px"},children=[
                html.Div("LEGEND",style={"color":"#4a8aaa","fontSize":"8px","letterSpacing":"2px","marginBottom":"6px"}),
                *[html.Div([html.Span(sym,style={"color":c,"marginRight":"5px"}),
                            html.Span(lbl,style={"fontSize":"8px","color":"#bbb"})],
                           style={"marginBottom":"3px"}) for sym,c,lbl in LEGEND],
            ]),
        ]),
    ]),
    dcc.Interval(id="heartbeat",interval=1500,n_intervals=0),
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
    latest=events[0] if events else None
    tick_str=(f"TICK {TICK[0]:04d} | MODE:{ROUTE_MODE[0]} | "
              f"CALLS:{len(active_calls):02d} | AMB:{sum(1 for a in AMBULANCES if a['status']!='PATROLLING')}/7 active")
    return make_figure(latest),make_sidebar(),make_gos(),make_log(),make_ladder(),tick_str

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