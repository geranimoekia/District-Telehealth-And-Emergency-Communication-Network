# tele527-pbl-group1

# District Telehealth & Emergency Communication Network

> **TELE 527 — Telecommunications Network and Infrastructures**  
> Python-Based Problem Based Learning (PBL) Laboratory  
> Department of Electrical, Computer and Telecommunications Engineering  
> Botswana International University of Science and Technology (BIUST)  
> Semester 2, 2026

---

## Project Overview

This repository contains the complete Python simulation pipeline for the **District Telehealth and Emergency Communication Network** — a cost-constrained district network designed to guarantee performance for critical healthcare services during peak load and partial backhaul degradation.

The network serves a rural administrative district of approximately 50,000 residents, connecting a central referral hospital, a district health office, and five community health clinics through a fully software-simulated pipeline. No physical hardware is involved. Every network element — base stations, routers, links, propagation environment, and traffic — is modelled as a Python object or mathematical function.

### Core Engineering Question

> *How do we design and validate a cost-constrained district network that guarantees performance for critical services during peak load and partial backhaul degradation?*

---

## Group Members

| Student | Full Name | Role |
|---|---|---|
| Student 1 | Atlang Zambezi | Network Architect — topology, scenario.yaml, main.py, report coordination |
| Student 2 | Pako Kgosintwa | Traffic & Teletraffic Lead — traffic.py, teletraffic.py, stress testing |
| Student 3 | Goitse Pihelo | Wireless Planning Lead — propagation.py, wireless.py |
| Student 4 | Tsotlhe Seiphepi | Signaling & Routing Lead — routing.py, signaling.py, backhaul.py |
| Student 5 | Thebe Ratsatsi | QoS & Data Networks Lead — qos.py, forecasting.py, app.py, tests |

**Supervisors:** Professor Abid Yahya and Eng. Robin Tau

---

## Network Architecture

The network adopts a **Topology 5 — North–South Dual-Core** architecture:

- **CR-1** (District Hospital) — primary core router, north position
- **CR-2** (District Health Office) — secondary core router, south position
- **BS1–BS5** — five community health clinics, dual-homed to both CR-1 and CR-2

Every base station has two independent upstream paths simultaneously — one to CR-1 and one to CR-2. If either core router fails, all five clinics remain connected through the surviving router.

The CR-1 ↔ CR-2 backbone uses **Option 4 — fibre primary + microwave backup**, eliminating the last remaining single point of failure with two physically diverse technologies.

### Traffic Classes and KPI Targets

| Class | Model | KPI Target | DSCP | Priority |
|---|---|---|---|---|
| Telemetry | M/M/N Queue | P95 delay ≤ 50 ms | EF (46) | Strict Priority Queue |
| Voice | M/M/N/0 (Erlang B) | Blocking ≤ 2% | AF31 (26) | WFQ 30% |
| Video | M/M/N Queue | P95 delay ≤ 150 ms | AF21 (18) | WFQ 40% |

---

## Repository Structure

```
tele527-pbl-group1/
│
├── scenario.yaml           # Single source of truth for all parameters
├── main.py                 # End-to-end pipeline entry point
├── app.py                  # Streamlit dashboard entry point
├── requirements.txt        # All Python dependencies
│
├── src/
│   ├── topology.py         # NetworkX graph — Student 1
│   ├── traffic.py          # Poisson traffic generation — Student 2
│   ├── teletraffic.py      # Erlang B/C analysis — Student 2
│   ├── routing.py          # Dijkstra SPF + failure injection — Student 4
│   ├── propagation.py      # COST 231-Hata path loss — Student 3
│   ├── wireless.py         # Coverage maps + reuse analysis — Student 3
│   ├── signaling.py        # SS7 call setup delay model — Student 4
│   ├── backhaul.py         # Microwave link budget — Student 4
│   ├── qos.py              # QoS metrics P50/P95/P99 — Student 5
│   └── forecasting.py      # CAGR growth model — Student 5
│
├── figures/                # All generated plot files (do not edit manually)
│
├── tests/
│   ├── test_teletraffic.py # Erlang B boundary and reference tests
│   ├── test_qos.py         # QoS metric range and DSCP tests
│   └── test_routing.py     # Dijkstra correctness and failure injection tests
│
└── report/
    └── main.tex            # LaTeX report source (compiled via Overleaf)
```

---

## Quickstart

### 1. Clone the repository

```bash
git clone https://github.com/Matlhi/tele527-pbl-group1.git
cd tele527-pbl-group1
```

### 2. Create and activate the environment

```bash
conda create -n tele527 python=3.11
conda activate tele527
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the full simulation pipeline

```bash
python main.py --scenario scenario.yaml
```

All figures are saved automatically to `figures/`. Results are written to a shared results dictionary passed between modules.

### 5. Launch the Streamlit dashboard

```bash
streamlit run app.py
```

The dashboard opens at `http://localhost:8501` with six tabs: Network Overview, QoS Performance, Coverage, Backhaul, Forecasting, and Baseline vs Stress vs Failure.

### 6. Run the test suite

```bash
pytest tests/
```

All tests must pass before any merge to `main`.

---

## Python Dependencies

```
numpy
scipy
pandas
matplotlib
networkx
pyyaml
streamlit
pytest
statsmodels
simpy
```

Install everything at once:

```bash
pip install numpy scipy pandas matplotlib networkx pyyaml streamlit pytest statsmodels simpy
pip freeze > requirements.txt
```

---

## Configuration — scenario.yaml

All simulation parameters live in `scenario.yaml`. Every module loads this file at runtime:

```python
import yaml
config = yaml.safe_load(open("scenario.yaml"))
```

**Never hardcode parameters inside module files.** If a value needs to change — a site coordinate, a traffic load, a KPI target — change it in `scenario.yaml` only. The entire pipeline updates automatically.

Key parameter groups:

| Section | What it controls |
|---|---|
| `simulation` | Random seed, load multiplier steps, forecast horizon |
| `sites` | 7 network nodes with coordinates and types |
| `links` | 28 directed edges with capacity, delay, type, role, weight |
| `traffic` | Offered load, DSCP, and KPI targets per class |
| `environment` | COST 231-Hata model inputs for propagation.py |
| `backhaul` | Microwave link budget parameters for backhaul.py |
| `qos` | Scheduler weights and utilisation zone thresholds |
| `forecasting` | Growth rate, horizon, and upgrade trigger thresholds |

### Verify the configuration loads correctly

```python
import yaml
config = yaml.safe_load(open("scenario.yaml"))
print(f"Sites       : {len(config['sites'])}")          # 7
print(f"Total links : {len(config['links'])}")          # 28
print(f"Primary     : {sum(1 for l in config['links'] if l.get('role')=='primary')}")  # 14
print(f"Backup      : {sum(1 for l in config['links'] if l.get('role')=='backup')}")   # 14
```

---

## Module Descriptions

### topology.py — Student 1
Loads `scenario.yaml` and builds a `networkx.DiGraph` with all 7 nodes and 28 directed edges. Assigns edge attributes: `capacity_mbps`, `delay_ms`, `type`, `role`, `weight`. Saves `figures/topology.png`.

### traffic.py — Student 2
Generates synthetic traffic for three service classes using Poisson arrivals and exponential holding times. Uses `numpy.random` with the fixed seed from `scenario.yaml`. Outputs per-site per-class offered load in Erlangs.

### teletraffic.py — Student 2
Implements Erlang B (Jagerman recursion) and Erlang C for channel dimensioning. Finds N* = minimum circuits satisfying each KPI. Plots blocking probability curves. Saves `figures/erlang.png`.

### routing.py — Student 4
Computes shortest paths via `networkx.shortest_path(G, weight='weight')`. Implements failure injection by removing edges and recomputing paths. Compares baseline vs failure: reroute count, delay increase, throughput loss.

### propagation.py — Student 3
Implements the COST 231-Hata path loss model at 1800 MHz. Generates a 2D received power grid at 100 m resolution across the 50×50 km district area.

### wireless.py — Student 3
Builds coverage heatmaps from the propagation grid at −85 dBm and −95 dBm thresholds. Computes C/I ratio for reuse factors K ∈ {1, 3, 4, 7, 9, 12}. Saves `figures/coverage_85.png`, `figures/coverage_95.png`, `figures/reuse.png`.

### signaling.py — Student 4
Models SS7-inspired call setup delay as the sum of per-hop propagation, processing (5 ms), and M/D/1 queuing delays across 5–7 message exchanges per call.

### backhaul.py — Student 4
Computes full link budget for all microwave backhaul hops: FSPL, rain attenuation (ITU-R P.838), RSL, and fade margin. Flags any link with fade margin below 20 dB as FAIL.

### qos.py — Student 5
Aggregates outputs from all upstream modules. Computes P50, P95, P99 delay percentiles, jitter, blocking probability, and throughput per traffic class. Produces per-class PASS/FAIL compliance table. Saves `figures/qos.png`.

### forecasting.py — Student 5
Projects traffic growth using CAGR model: λ(t) = λ₀(1+g)^t with g = 0.15. Identifies which KPI fails first and in which year. Plots upgrade trigger crossover years. Saves `figures/forecast.png`.

---

## Pipeline Architecture

```
scenario.yaml
     │
     ├── topology.py      → NetworkX graph G
     ├── traffic.py       → offered load per site per class
     ├── teletraffic.py   → Erlang B/C, N*, blocking curves
     ├── routing.py       → shortest paths, failure rerouting
     ├── propagation.py   → path loss grid
     ├── wireless.py      → coverage maps, C/I analysis
     ├── signaling.py     → call setup delay
     ├── backhaul.py      → link budget table
     ├── qos.py           → P95 delay, blocking, jitter, throughput
     └── forecasting.py   → growth model, upgrade triggers
                               │
                           app.py (Streamlit)
                           6-tab interactive dashboard
```

All modules share data through a single `results` dictionary. No module writes to global variables or copies code from another module.

---

## Dashboard — app.py

The Streamlit dashboard integrates all module outputs into one interactive application.

| Tab | Content |
|---|---|
| Network Overview | Topology diagram with link utilisation colour-coding |
| QoS Performance | Per-class PASS/FAIL compliance table and delay plots |
| Coverage | Heatmaps at both thresholds, C/I reuse factor selector |
| Backhaul | Full link budget table with fade margin pass/fail |
| Forecasting | Traffic growth chart with upgrade trigger year |
| Baseline vs Stress vs Failure | Side-by-side KPI comparison bars |

**Sidebar controls:**
- Offered load multiplier α slider (0.5× to 3×)
- Reuse factor selector K ∈ {1, 3, 4, 7}
- Backhaul failure toggle (enable/disable link failure injection)
- Run Scenario button (reruns full pipeline and updates all plots)

---

## Git Workflow

```bash
# Create a branch for your task
git checkout -b feature/your-task-name

# Commit regularly with clear messages
git add .
git commit -m "teletraffic: implement Erlang B recursion and blocking curves"

# Push and open a pull request
git push origin feature/your-task-name
```

**Rules:**
- One branch per task — never work directly on `main`
- Merge only after peer review and `pytest tests/` passes
- Commit messages must describe what changed, not just "update"
- All figures in `figures/` are generated by code — never commit manually created images

---

## Reproducibility

This project is fully reproducible from a clean environment:

```bash
git clone https://github.com/Matlhi/tele527-pbl-group1.git
cd tele527-pbl-group1
conda create -n tele527 python=3.11 && conda activate tele527
pip install -r requirements.txt
python main.py --scenario scenario.yaml
```

Running the above sequence on any machine must produce identical figures and results. The `random_seed: 42` in `scenario.yaml` guarantees this.

---

## Report

The final report is written in LaTeX and compiled via Overleaf.

**Overleaf project:** https://prism.openai.com/?u=e52a7669-40ed-470e-85f3-2c4fbccc1e5c&pg=1&m=sn-article.tex&d=7

**Required sections:**
1. Introduction and problem statement
2. Dataset description and justification
3. Methodology
4. Results and discussion
5. Conclusion and future work
6. References

**Report rules:**
- Target 10–15 pages including figures and references
- No cover page, table of contents, or list of figures
- Every figure in the report must be generated by code in this repository
- Every major claim must be backed by a figure, table, equation, or citation
- Compact numerical citation style throughout

---

## Academic Integrity

All code in this repository was written by the group members listed above. All writing in the report is original. Mathematical derivations and explanations are in the group's own words.

Plagiarism and code sharing with other groups constitutes serious academic misconduct under BIUST regulations.

---

## Contact

For questions about this repository, contact **Atlang Zambezi** (Student 1 — Network Architect) via the BIUST student portal or raise a GitHub issue.

> BIUST · Department of Electrical, Computer and Telecommunications Engineering · Semester 2, 2026