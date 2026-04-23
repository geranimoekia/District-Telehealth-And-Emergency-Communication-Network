# TELE 527 - QoS Dashboard
### Student 5 (Thebe Ratsatsi) - Group 1 - BIUST

---

## Setup (one-time)

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run src/dashboard.py
```

Then open http://localhost:8501 in your browser.

---

## Project structure

```text
tele527_dashboard/
├── src/
│   ├── dashboard.py      <- main Streamlit dashboard
│   ├── backhaul.py
│   ├── forecasting.py
│   ├── plots.py
│   ├── routing.py
│   ├── signalling.py
│   └── wireless.py
├── outputs/              <- generated CSV inputs used by the dashboard
├── scenario.yaml         <- network scenario configuration
└── requirements.txt      <- dependencies
```

## Pages

| Page | Description |
|------|-------------|
| Overview | Gauges, radar chart, 5-year forecast, upgrade timeline |
| Network Map | Live map with real Palapye coordinates. Click any marker for full site details |
| QoS Metrics | Delay KPIs, Erlang B blocking, signaling per site |
| Stress & Demo | Interactive stress slider, break point at 1.5x, demo scenario |
| Forecast & Upgrades | 5-year utilisation forecast, upgrade plan, Erlang forecasts |
| Wireless & Backhaul | Link budgets, rain attenuation, COST-231 coverage |
| Routing & Signaling | Routing paths, signaling load, and failure handling |

## Adding Student 4 data

Go to the **Routing & Signaling** page and upload:

- `routing_table.csv` - path_id, source (BS1-BS5), destination (CR-1/CR-2), end_to_end_delay_ms, utilisation_pct, backup_path_id
- `signaling_model.json` - call_setup_delay_ms, signaling_load_per_node, failure_reroute_delay_ms, degraded_backhaul_paths
- `failure_scenarios.csv` - scenario, failed_component, reroute_path, reroute_delay_ms, kpis_still_met

## Auto-refresh

Toggle **Auto-refresh (30s)** in the sidebar to keep the dashboard live during your demo.
