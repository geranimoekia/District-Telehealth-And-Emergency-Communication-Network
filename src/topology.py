# src/topology.py
# Owner: Student 1 — Atlang Zambezi
# Purpose: Load scenario.yaml and build the NetworkX graph
#          that all other modules use for routing and analysis.

import yaml
import networkx as nx
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
import os


def load_config(scenario_path="scenario.yaml"):
    """Load and return the scenario configuration dictionary."""
    with open(scenario_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def build_topology(config):
    """
    Build and return a NetworkX DiGraph from the scenario config.
    Nodes = sites (CR-1, CR-2, BS1-BS5)
    Edges = links with attributes: capacity_mbps, delay_ms,
            link_type, role, weight
    """
    G = nx.DiGraph()

    # Add nodes
    for site in config['sites']:
        G.add_node(
            site['name'],
            label=site['label'],
            type=site['type'],
            x=site['x_km'],
            y=site['y_km']
        )

    # Add edges
    for link in config['links']:
        G.add_edge(
            link['from'],
            link['to'],
            capacity_mbps=link['capacity_mbps'],
            delay_ms=link['delay_ms'],
            link_type=link['type'],
            role=link['role'],
            weight=link['weight']
        )

    return G


def get_positions(G):
    """
    Extract node positions from graph attributes.
    Returns dict: {node_name: (x_km, y_km)}
    """
    return {
        node: (G.nodes[node]['x'], G.nodes[node]['y'])
        for node in G.nodes
    }


def draw_topology(G, output_path="figures/topology.png"):
    """
    Draw the network topology and save to output_path.
    Green circles  = core routers
    Blue squares   = base stations
    Green solid    = fibre backbone
    Blue dashed    = microwave primary
    Amber dashed   = microwave backup
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    fig, ax = plt.subplots(figsize=(14, 10))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")
    ax.set_xlim(-4, 54)
    ax.set_ylim(-4, 54)
    ax.set_aspect('equal')
    ax.axis('off')

    pos = get_positions(G)

    # Separate edges by type and role
    fibre_primary = [(u, v) for u, v, d in G.edges(data=True)
                     if d['link_type'] == 'fibre' and d['role'] == 'primary']
    mw_primary    = [(u, v) for u, v, d in G.edges(data=True)
                     if d['link_type'] == 'microwave' and d['role'] == 'primary']
    mw_backup     = [(u, v) for u, v, d in G.edges(data=True)
                     if d['link_type'] == 'microwave' and d['role'] == 'backup']

    # Draw edges
    nx.draw_networkx_edges(G, pos, edgelist=fibre_primary,
                           edge_color='#22c55e', width=3.5,
                           style='solid', alpha=0.9,
                           arrows=False, ax=ax)

    nx.draw_networkx_edges(G, pos, edgelist=mw_primary,
                           edge_color='#3b82f6', width=1.8,
                           style='dashed', alpha=0.75,
                           arrows=False, ax=ax)

    nx.draw_networkx_edges(G, pos, edgelist=mw_backup,
                           edge_color='#f59e0b', width=1.4,
                           style='dashed', alpha=0.55,
                           arrows=False, ax=ax)

    # Draw nodes
    core_nodes = [n for n in G.nodes if G.nodes[n]['type'] == 'core_router']
    bs_nodes   = [n for n in G.nodes if G.nodes[n]['type'] == 'base_station']

    nx.draw_networkx_nodes(G, pos, nodelist=core_nodes,
                           node_color='#22c55e', node_size=800,
                           node_shape='o', ax=ax)

    nx.draw_networkx_nodes(G, pos, nodelist=bs_nodes,
                           node_color='#3b82f6', node_size=500,
                           node_shape='s', ax=ax)

    # Node name labels
    nx.draw_networkx_labels(G, pos,
                            font_color='white',
                            font_size=9,
                            font_weight='bold',
                            ax=ax)

    # Site name sub-labels
    for node, (x, y) in pos.items():
        label = G.nodes[node]['label']
        ax.text(x, y - 2.8, label,
                color='#8b949e', fontsize=7.5,
                ha='center', va='top',
                fontfamily='monospace',
                path_effects=[pe.withStroke(linewidth=2,
                              foreground='#0d1117')])

    # Legend
    legend_elements = [
        plt.Line2D([0],[0], color='#22c55e', lw=3,
                   label='Fibre backbone (1000 Mbps)'),
        plt.Line2D([0],[0], color='#3b82f6', lw=1.8,
                   linestyle='--', label='Microwave primary (100 Mbps)'),
        plt.Line2D([0],[0], color='#f59e0b', lw=1.4,
                   linestyle='--', label='Microwave backup (100 Mbps)'),
        plt.scatter([],[], c='#22c55e', s=80,
                   marker='o', label='Core router (CR)'),
        plt.scatter([],[], c='#3b82f6', s=60,
                   marker='s', label='Base station (BS)'),
    ]
    ax.legend(handles=legend_elements,
              loc='lower left', fontsize=8,
              facecolor='#161b22', edgecolor='#30363d',
              labelcolor='#8b949e')

    # Title
    ax.set_title(
        "District Telehealth & Emergency Communication Network\n"
        "TELE 527 · Group 1 · BIUST · topology.py output",
        color='#e6edf3', fontsize=11, pad=12,
        fontfamily='monospace'
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150,
                bbox_inches='tight',
                facecolor='#0d1117')
    plt.close()
    print(f"Topology saved → {output_path}")


def topology_summary(G):
    """Print a readable graph summary to the terminal."""
    print("\n── Topology Summary ──────────────────────")
    print(f"  Nodes : {G.number_of_nodes()}")
    print(f"  Edges : {G.number_of_edges()}")
    print(f"  Core routers  : "
          f"{[n for n in G.nodes if G.nodes[n]['type']=='core_router']}")
    print(f"  Base stations : "
          f"{[n for n in G.nodes if G.nodes[n]['type']=='base_station']}")
    primary = [(u,v) for u,v,d in G.edges(data=True) if d['role']=='primary']
    backup  = [(u,v) for u,v,d in G.edges(data=True) if d['role']=='backup']
    print(f"  Primary links : {len(primary)}")
    print(f"  Backup links  : {len(backup)}")
    print("──────────────────────────────────────────\n")


if __name__ == "__main__":
    config = load_config("scenario.yaml")
    G      = build_topology(config)
    topology_summary(G)
    draw_topology(G)