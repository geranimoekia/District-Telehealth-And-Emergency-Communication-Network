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
