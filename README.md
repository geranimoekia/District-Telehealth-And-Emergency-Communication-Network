# District Telehealth And Emergency Communication Network

A QoS-aware network simulation and real-time monitoring dashboard for a district-level telehealth and emergency communication network serving clinics and hospitals across the Palapye and Serowe districts of Botswana.

---

## Overview

This project designs, simulates, and evaluates a multi-site wireless network that connects rural health facilities to district hospitals for telehealth consultations, remote patient monitoring (IoT telemetry), and emergency communications. It models realistic radio propagation, backhaul link budgets, traffic engineering, and Quality of Service (QoS) guarantees — then surfaces everything in an interactive Streamlit dashboard.

---

## Network Topology

| Node | Site | Role |
|------|------|------|
| CR-1 | Palapye Primary Hospital | Core Router (Primary) |
| CR-2 | Palapye Sub-District Health Office | Core Router (Backup) |
| BS1  | Radisele Clinic (NW) | Base Station |
| BS2  | Lecheng Clinic (NE) | Base Station |
| BS3  | Mogome Clinic (SW) | Base Station |
| BS4  | Maunatlala Clinic (South) | Base Station |
| BS5  | Lerala Clinic (SE) | Base Station |
| BS6  | Sekgoma Memorial Hospital | Base Station |
| BS7  | Serowe West Clinic | Base Station |
| BS8  | Paje Clinic | Base Station |
| BS9  | Mabeleapodi Clinic | Base Station |
| BS10 | Ratholo Clinic | Base Station |
| BS11 | Lecheng Clinic (S) | Base Station |
| BS12 | Lotsane Hospital | Base Station |
| BS13 | Tumasera-Seleka Clinic | Base Station |

**Backhaul links:** 7 GHz microwave (primary) and 13 GHz microwave (core backbone), with LTE Priority Bearer (BTC Botswana, 1800 MHz, QCI-65) as backup.

---

## Traffic Classes & QoS

| Class | Scheduler | KPI Target |
|-------|-----------|------------|
| Telemetry (IoT) | Strict Priority | P95 end-to-end delay < 50 ms |
| Voice (VoIP consultations) | WFQ 30% share | Erlang B blocking < 2% |
| Video (HD telehealth sessions) | WFQ 40% share | P95 delay < 150 ms |

Traffic growth projections use per-class CAGRs: Telemetry 25%, Voice 10%, Video 35%.

---

## Dashboard Pages

| Page | Description |
|------|-------------|
| Overview | Gauges, radar chart, 5-year utilisation forecast, upgrade timeline |
| Network Map | Live map with real GPS coordinates — click any marker for site details |
| QoS Metrics | Delay KPIs, Erlang B blocking rates, signaling load per site |
| Stress & Breaking Point | Interactive load slider, breaking-point sweep (video fails first at 1.25×, voice at 1.5×) |
| Forecast & Upgrades | 5-year capacity forecast, three upgrade strategies with CAPEX comparison |
| Wireless & Backhaul | COST-231 propagation, coverage grids, rain attenuation, link budgets |
| Routing & Signaling | Shortest-path routing, signaling load, failure-reroute scenarios |

---

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run src/dashboard.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Project Structure

```
├── src/
│   ├── dashboard.py        # Streamlit dashboard (main entry point)
│   ├── wireless.py         # COST-231 propagation & coverage analysis
│   ├── backhaul.py         # Microwave link budget & rain attenuation
│   ├── routing.py          # Dijkstra routing & failure rerouting
│   ├── signalling.py       # Signaling load model
│   ├── qos.py              # WFQ scheduler & Erlang B calculations
│   ├── teletraffic.py      # Traffic generation & Erlang traffic model
│   ├── forecasting.py      # 5-year utilisation forecasting
│   ├── stress_test.py      # Load stress sweep & breaking-point analysis
│   ├── pipeline.py         # End-to-end simulation pipeline
│   ├── topology.py         # Network graph construction
│   ├── plots.py            # Shared Plotly figure utilities
│   ├── tok.py              # Serowe district network expansion
│   └── scenario.yaml       # Network configuration (sites, links, traffic, QoS)
├── outputs/                # Generated CSV outputs consumed by the dashboard
├── src/outputs/            # Per-module simulation outputs
├── src/figures/            # Pre-rendered figures
├── results/                # Simulation results & documentation
├── scenario.yaml           # Root-level scenario config
└── requirements.txt        # Python dependencies
```

---

## Key Simulation Parameters

- **Carrier frequency:** 1800 MHz (LTE access), 7 GHz / 13 GHz (backhaul)
- **Base station height:** 30 m | **UE height:** 1.5 m
- **Shadow fading margin:** 8 dB | **Rainfall zone:** Botswana
- **Backhaul capacity:** 100 Mbps per BS link (primary), 500 Mbps core backbone
- **Forecast horizon:** 36 months with 3-month procurement lead time
- **Planning trigger:** ρ = 0.70 | **Action trigger:** ρ = 0.90

---

## Dependencies

| Package | Purpose |
|---------|---------|
| Streamlit | Interactive web dashboard |
| Plotly | Charts and visualisations |
| Folium + streamlit-folium | Geographic network map |
| NetworkX | Graph-based routing algorithms |
| Pandas / NumPy | Data processing & simulation |
| PyYAML | Scenario configuration parsing |
| Matplotlib | Static figure generation |

---

## Academic Context

**Course:** TELE 527 — Telecommunications Network Planning and Design  
**Institution:** Botswana International University of Science and Technology (BIUST)  
**Group:** PBL Group 1
