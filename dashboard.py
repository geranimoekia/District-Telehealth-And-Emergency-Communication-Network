# dashboard.py
import dash
from dash import dcc, html
from dash.dependencies import Output, Input
import plotly.graph_objs as go
import threading
import time

# -----------------------
# Simulated controller events
# -----------------------
# You should replace this with your real controller's event data
call_log = []  # Shared list to hold live call events

def simulate_controller():
    """Simulates your controller generating events"""
    bs_states = {"BS1":0, "BS2":0, "BS3":0, "BS4":0, "BS5":0}
    channels_per_bs = 4
    while True:
        for bs in bs_states:
            # randomly generate call attempts
            import random
            action = random.choice(["connect", "release"])
            if action == "connect" and bs_states[bs] < channels_per_bs:
                bs_states[bs] += 1
                call_log.append({"bs": bs, "status": "connected", "time": time.time()})
            elif action == "release" and bs_states[bs] > 0:
                bs_states[bs] -= 1
                call_log.append({"bs": bs, "status": "released", "time": time.time()})
        time.sleep(1)

# Start simulation in background
threading.Thread(target=simulate_controller, daemon=True).start()

# -----------------------
# Dash App
# -----------------------
app = dash.Dash(__name__)
app.layout = html.Div([
    html.H2("Base Station Call Dashboard"),
    dcc.Graph(id="bs-graph"),
    dcc.Interval(id="interval-component", interval=1000, n_intervals=0)  # update every second
])

@app.callback(
    Output("bs-graph", "figure"),
    Input("interval-component", "n_intervals")
)
def update_graph(n):
    # Count channels in use per base station
    bs_counts = {"BS1":0, "BS2":0, "BS3":0, "BS4":0, "BS5":0}
    for event in call_log[-50:]:  # last 50 events
        if event["status"] == "connected":
            bs_counts[event["bs"]] += 1
        elif event["status"] == "released" and bs_counts[event["bs"]] > 0:
            bs_counts[event["bs"]] -= 1

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=list(bs_counts.keys()),
        y=list(bs_counts.values()),
        text=[f"{v}/4 channels" for v in bs_counts.values()],
        textposition='auto'
    ))
    fig.update_layout(yaxis=dict(title="Channels in Use", range=[0,4]))
    return fig

if __name__ == "__main__":
  app.run(debug=True)