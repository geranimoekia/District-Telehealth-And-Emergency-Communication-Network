# TELE 527 — QoS Dashboard
### Student 5 (Thebe Ratsatsi) · Group 1 · BIUST

---

## Setup (one-time)

```bash
pip install streamlit plotly pandas folium streamlit-folium
```

## Run

```bash
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

---

## Project structure

```
tele527_dashboard/
├── app.py               ← main dashboard
├── requirements.txt     ← dependencies
└── data/                ← all CSV and JSON files go here
    ├── network_design_brief.json       (Student 1)
    ├── wireless_results.json           (Student 3)
    ├── teletraffic_delay_kpis.csv      (Student 2)
    ├── teletraffic_dimensioning_table.csv
    ├── teletraffic_erlang_curves.csv
    ├── teletraffic_signaling_load.csv
    ├── teletraffic_stress_sweep.csv
    ├── teletraffic_trunk_summary.csv
    ├── forecasting_utilisation_annual.csv
    ├── forecasting_utilisation_curve.csv
    ├── forecasting_upgrade_plan.csv
    ├── forecasting_erlang_per_site.csv
    ├── forecasting_trunk_erlang.csv
    ├── traffic_matrix.csv
    └── traffic_stress_bandwidth_sweep.csv
```

## Pages

| Page | Description |
|------|-------------|
| 🏠 Overview | Gauges, radar chart, 5-year forecast, upgrade timeline |
| 🗺️ Network Map | Live Google Maps with real Palapye coordinates. Click any marker for full site details |
| 📊 QoS Metrics | Delay KPIs, Erlang B blocking, signaling per site |
| 🔥 Stress & Demo | Interactive stress slider, break point at 1.5×, demo scenario |
| 📈 Forecast & Upgrades | 5-year utilisation forecast, upgrade plan, Erlang forecasts |
| 📡 Wireless & Backhaul | Link budgets, rain attenuation, COST-231 coverage |
| 🔀 Routing & Signaling | Upload Student 4 files here when ready |

## Adding Student 4 data

Go to the **Routing & Signaling** page and upload:
- `routing_table.csv` — path_id, source (BS1–BS5), destination (CR-1/CR-2), end_to_end_delay_ms, utilisation_pct, backup_path_id
- `signaling_model.json` — call_setup_delay_ms, signaling_load_per_node, failure_reroute_delay_ms, degraded_backhaul_paths
- `failure_scenarios.csv` — scenario, failed_component, reroute_path, reroute_delay_ms, kpis_still_met

## Auto-refresh

Toggle **Auto-refresh (30s)** in the sidebar to keep the dashboard live during your demo.
