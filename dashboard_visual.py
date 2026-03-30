import dash
from dash import html, dcc, Input, Output
import folium
import random

SITES = [
    {"id": "CR-1", "name": "District Hospital (Core)", "lat": -22.9997, "lon": 23.9950, "type": "Core", "channels": 15},
    {"id": "BS1",  "name": "Clinic North-West",        "lat": -22.8646, "lon": 23.8284, "type": "BS",   "channels": 5},
    {"id": "BS2",  "name": "Clinic North-East",        "lat": -22.8646, "lon": 24.1617, "type": "BS",   "channels": 5},
    {"id": "BS3",  "name": "Clinic South-West",        "lat": -23.1349, "lon": 23.8284, "type": "BS",   "channels": 5},
    {"id": "BS4",  "name": "Clinic South",             "lat": -23.1529, "lon": 23.9950, "type": "BS",   "channels": 5},
    {"id": "BS5",  "name": "Clinic South-East",        "lat": -23.1349, "lon": 24.1617, "type": "BS",   "channels": 5},
]
for s in SITES:
    s["in_use"] = 0
    s["last_event"] = "IDLE"

def build_map():
    m = folium.Map(location=[-23.0, 23.99], zoom_start=10, tiles="CartoDB dark_matter")
    core = SITES[0]
    for bs in SITES[1:]:
        folium.PolyLine([[core["lat"], core["lon"]], [bs["lat"], bs["lon"]]],
                        color="#1a7ab5", weight=2, opacity=0.7).add_to(m)
    for s in SITES:
        ratio = s["in_use"] / s["channels"]
        color = "#ff1744" if s["last_event"] == "BLOCKED" else "#ffd600" if ratio >= 0.7 else "#00e5ff"
        radius = 12 + s["in_use"] * 3
        folium.CircleMarker(
            location=[s["lat"], s["lon"]], radius=radius,
            color=color, fill=True, fill_color=color, fill_opacity=0.85,
            popup=folium.Popup(
                f"<b>{s['name']}</b><br>Sessions: {s['in_use']}/{s['channels']}<br>Status: {s['last_event']}",
                max_width=200),
            tooltip=f"{s['id']}: {s['in_use']}/{s['channels']}"
        ).add_to(m)
        folium.Marker(
            location=[s["lat"], s["lon"]],
            icon=folium.DivIcon(
                html=f'<div style="font-size:11px;color:white;font-weight:bold;'
                     f'font-family:monospace;text-shadow:0 0 6px #000;'
                     f'white-space:nowrap;margin-top:-24px;margin-left:16px">{s["id"]}</div>',
                icon_size=(80, 20), icon_anchor=(0, 0))
        ).add_to(m)
    return m._repr_html_()

app = dash.Dash(__name__)
app.title = "Network Monitor"

app.layout = html.Div(style={"backgroundColor":"#020a17","color":"white","fontFamily":"monospace","padding":"20px","minHeight":"100vh"}, children=[
    html.H2("GEOGRAPHIC ROUTING & SIGNALING MONITOR", style={"color":"#00e5ff","margin":"0 0 4px 0"}),
    html.P("Live Control Plane — Palapye District Grid", style={"color":"#4a8aaa","fontSize":"12px","margin":"0 0 16px 0"}),
    html.Div(style={"display":"flex","gap":"20px"}, children=[
        html.Div(id="sidebar", style={"width":"240px","flexShrink":"0","background":"#060d1a","padding":"14px","border":"1px solid #0a2840"}),
        html.Div(style={"flex":"1","minWidth":"0"}, children=[
            html.Iframe(id="map-frame", srcDoc="Loading map...",
                        style={"width":"100%","height":"520px","border":"none","borderRadius":"4px"}),
            html.Div(id="log", style={"marginTop":"10px","padding":"10px","background":"#000",
                                      "color":"#00ff00","fontSize":"11px","height":"55px",
                                      "borderLeft":"3px solid #00e5ff","overflowY":"auto"}),
        ]),
    ]),
    dcc.Interval(id="tick", interval=2000, n_intervals=0),
])

@app.callback(
    [Output("map-frame","srcDoc"), Output("sidebar","children"), Output("log","children")],
    Input("tick","n_intervals")
)
def tick(n):
    site = random.choice(SITES)
    if random.random() > 0.4:
        if site["in_use"] < site["channels"]:
            site["in_use"] += 1
            site["last_event"] = "CONNECTED"
            mode = "DYNAMIC-OSPF" if site["in_use"]/site["channels"] > 0.7 else "STATIC"
            log = f"TICK {n} | {site['id']} SETUP OK | ROUTE: {mode}"
        else:
            site["last_event"] = "BLOCKED"
            log = f"TICK {n} | {site['id']} REJECTED | CAUSE: GOS_LIMIT"
    else:
        if site["in_use"] > 0:
            site["in_use"] -= 1
            site["last_event"] = "RELEASED"
            log = f"TICK {n} | {site['id']} RELEASED | CHANNEL FREED"
        else:
            log = f"TICK {n} | SYSTEM IDLE"

    sidebar = [html.Div("SIGNALING METRICS", style={"color":"#4a8aaa","marginBottom":"14px","fontWeight":"bold","fontSize":"12px"})]
    for s in SITES:
        ec = {"CONNECTED":"#00ff00","BLOCKED":"#ff1744","RELEASED":"#ffd600"}.get(s["last_event"],"#4a8aaa")
        pct = (s["in_use"]/s["channels"])*100
        bc = "#ff1744" if pct>=100 else "#ffd600" if pct>=70 else "#00e5ff"
        sidebar.append(html.Div(style={"marginBottom":"13px"}, children=[
            html.Div([html.Span(s["id"],style={"fontSize":"11px"}),
                      html.Span(s["last_event"],style={"fontSize":"9px","color":ec})],
                     style={"display":"flex","justifyContent":"space-between"}),
            html.Div(f"{s['in_use']}/{s['channels']} ch",style={"fontSize":"9px","color":"#4a8aaa"}),
            html.Div(style={"height":"4px","background":"#111","marginTop":"4px","borderRadius":"2px"},children=[
                html.Div(style={"height":"100%","width":f"{pct}%","background":bc,"borderRadius":"2px"})
            ])
        ]))

    return build_map(), sidebar, log

if __name__ == "__main__":
    app.run(debug=False, port=8050)