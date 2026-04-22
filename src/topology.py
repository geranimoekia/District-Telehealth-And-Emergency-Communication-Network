# src/topology.py
# Owner: Student 1 — Atlang Zambezi
# Purpose: Load scenario.yaml and build the NetworkX graph
#          that all other modules use for routing and analysis.
#
# UPDATED: backbone link types changed from fibre/microwave to
#          microwave_13ghz (primary) and lte_priority (backup).
#          draw_topology() and legend updated accordingly.

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
    Build and return a NetworkX MultiDiGraph from the scenario config.
    Nodes = sites (CR-1, CR-2, BS1-BS5)
    Edges = links with attributes: capacity_mbps, delay_ms,
            link_type, role, weight

    Supported link types:
        microwave_13ghz  — CR-1 <-> CR-2 backbone primary (500 Mbps, 13 GHz)
        lte_priority     — CR-1 <-> CR-2 backbone backup  ( 30 Mbps, QCI-65)
        microwave        — BS backhaul primary and CR-2 dual-home backup
    """
    G = nx.MultiDiGraph()

    # Add nodes
    for site in config['sites']:
        G.add_node(
            site['name'],
            label=site['label'],
            type=site['type'],
            x=site['x_km'],
            y=site['y_km']
        )

    # Add edges — capture all link attributes present in the yaml
    for link in config['links']:
        attrs = dict(
            capacity_mbps=link['capacity_mbps'],
            delay_ms=link['delay_ms'],
            link_type=link['type'],
            role=link['role'],
            weight=link['weight'],
        )
        # Optional attributes (only present on backbone links)
        if 'frequency_ghz' in link:
            attrs['frequency_ghz'] = link['frequency_ghz']
        if 'frequency_mhz' in link:
            attrs['frequency_mhz'] = link['frequency_mhz']
        if 'qci_class' in link:
            attrs['qci_class'] = link['qci_class']

        G.add_edge(link['from'], link['to'], **attrs)

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

    Node styles:
        Green circles  = core routers  (CR-1, CR-2)
        Blue squares   = base stations (BS1-BS5)

    Edge styles:
        Gold  solid  thick  = 13 GHz microwave backbone primary  (CR-1 <-> CR-2)
        Coral dashed medium = LTE priority bearer backup          (CR-1 <-> CR-2)
        Blue  solid  medium = 7 GHz microwave backhaul primary    (CR-1 <-> BS*)
        Amber dashed thin   = 7 GHz microwave dual-home backup    (CR-2 <-> BS*)
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

    # ── Separate edges by link type and role ──────────────────────────────────

    # CR-1 <-> CR-2 backbone — 13 GHz microwave primary
    mw13_primary = [(u, v) for u, v, d in G.edges(data=True)
                    if d['link_type'] == 'microwave_13ghz'
                    and d['role'] == 'primary']

    # CR-1 <-> CR-2 backbone — LTE priority bearer backup
    lte_backup   = [(u, v) for u, v, d in G.edges(data=True)
                    if d['link_type'] == 'lte_priority'
                    and d['role'] == 'backup']

    # CR-1 <-> BS* — 7 GHz microwave backhaul primary
    mw7_primary  = [(u, v) for u, v, d in G.edges(data=True)
                    if d['link_type'] == 'microwave'
                    and d['role'] == 'primary']

    # CR-2 <-> BS* — 7 GHz microwave dual-home backup
    mw7_backup   = [(u, v) for u, v, d in G.edges(data=True)
                    if d['link_type'] == 'microwave'
                    and d['role'] == 'backup']

    # ── Draw edges (back-to-front: backup first, primary on top) ─────────────

    # CR-2 dual-home backup links (thin amber dashed)
    nx.draw_networkx_edges(G, pos, edgelist=mw7_backup,
                           edge_color='#f59e0b', width=1.2,
                           style='dashed', alpha=0.50,
                           arrows=False, ax=ax)

    # LTE backbone backup (coral dashed, slightly offset so it doesn't
    # fully overlap the 13 GHz line — drawn first so 13 GHz sits on top)
    if lte_backup:
        # Compute a small perpendicular offset for the LTE line
        for (u, v) in lte_backup:
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            dx, dy = x1 - x0, y1 - y0
            length = max((dx**2 + dy**2)**0.5, 0.001)
            # Perpendicular unit vector * 0.5 km offset
            ox, oy = -dy / length * 0.6, dx / length * 0.6
            ax.annotate("",
                xy=(x1 + ox, y1 + oy),
                xytext=(x0 + ox, y0 + oy),
                arrowprops=dict(arrowstyle='-',
                                color='#f97316',
                                lw=1.8,
                                linestyle=(0, (5, 4)),
                                alpha=0.85))

    # 7 GHz microwave backhaul primary (blue solid)
    nx.draw_networkx_edges(G, pos, edgelist=mw7_primary,
                           edge_color='#3b82f6', width=1.8,
                           style='solid', alpha=0.75,
                           arrows=False, ax=ax)

    # 13 GHz backbone primary (gold solid, thickest — drawn last = on top)
    nx.draw_networkx_edges(G, pos, edgelist=mw13_primary,
                           edge_color='#eab308', width=3.8,
                           style='solid', alpha=0.95,
                           arrows=False, ax=ax)

    # ── Draw nodes ────────────────────────────────────────────────────────────

    core_nodes = [n for n in G.nodes if G.nodes[n]['type'] == 'core_router']
    bs_nodes   = [n for n in G.nodes if G.nodes[n]['type'] == 'base_station']

    nx.draw_networkx_nodes(G, pos, nodelist=core_nodes,
                           node_color='#22c55e', node_size=900,
                           node_shape='o', ax=ax)

    nx.draw_networkx_nodes(G, pos, nodelist=bs_nodes,
                           node_color='#3b82f6', node_size=520,
                           node_shape='s', ax=ax)

    # ── Node labels ───────────────────────────────────────────────────────────

    nx.draw_networkx_labels(G, pos,
                            font_color='white',
                            font_size=9,
                            font_weight='bold',
                            ax=ax)

    # Site name sub-labels (smaller, below each node)
    for node, (x, y) in pos.items():
        label = G.nodes[node]['label']
        ax.text(x, y - 2.8, label,
                color='#8b949e', fontsize=7.5,
                ha='center', va='top',
                fontfamily='monospace',
                path_effects=[pe.withStroke(linewidth=2,
                              foreground='#0d1117')])

    # ── Backbone technology annotations ───────────────────────────────────────
    # Place a small annotation near the midpoint of the CR-1 <-> CR-2 link

    if 'CR-1' in pos and 'CR-2' in pos:
        mx = (pos['CR-1'][0] + pos['CR-2'][0]) / 2
        my = (pos['CR-1'][1] + pos['CR-2'][1]) / 2
        ax.text(mx + 1.5, my + 2.0,
                "13 GHz\nprimary",
                color='#eab308', fontsize=7, ha='left', va='bottom',
                fontfamily='monospace',
                path_effects=[pe.withStroke(linewidth=2,
                              foreground='#0d1117')])
        ax.text(mx + 1.5, my - 0.5,
                "LTE QCI-65\nbackup",
                color='#f97316', fontsize=7, ha='left', va='top',
                fontfamily='monospace',
                path_effects=[pe.withStroke(linewidth=2,
                              foreground='#0d1117')])

    # ── Legend ────────────────────────────────────────────────────────────────

    legend_elements = [
        plt.Line2D([0], [0], color='#eab308', lw=3.5,
                   linestyle='solid',
                   label='13 GHz microwave backbone — primary (500 Mbps)'),
        plt.Line2D([0], [0], color='#f97316', lw=1.8,
                   linestyle='dashed',
                   label='LTE priority bearer QCI-65 — backup (30 Mbps)'),
        plt.Line2D([0], [0], color='#3b82f6', lw=1.8,
                   linestyle='solid',
                   label='7 GHz microwave backhaul — primary (100 Mbps)'),
        plt.Line2D([0], [0], color='#f59e0b', lw=1.2,
                   linestyle='dashed',
                   label='7 GHz microwave dual-home — backup (100 Mbps)'),
        plt.scatter([], [], c='#22c55e', s=80,
                    marker='o', label='Core router (CR)'),
        plt.scatter([], [], c='#3b82f6', s=60,
                    marker='s', label='Base station / clinic (BS)'),
    ]

    ax.legend(handles=legend_elements,
              loc='lower left', fontsize=8,
              facecolor='#161b22', edgecolor='#30363d',
              labelcolor='#8b949e')

    # ── Title ─────────────────────────────────────────────────────────────────

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
    print(f"Topology saved -> {output_path}")


def topology_summary(G):
    """Print a readable graph summary to the terminal."""
    print("\n-- Topology Summary ----------------------")
    print(f"  Nodes : {G.number_of_nodes()}")
    print(f"  Edges : {G.number_of_edges()}")
    print(f"  Core routers  : "
          f"{[n for n in G.nodes if G.nodes[n]['type'] == 'core_router']}")
    print(f"  Base stations : "
          f"{[n for n in G.nodes if G.nodes[n]['type'] == 'base_station']}")

    primary = [(u, v) for u, v, d in G.edges(data=True)
               if d['role'] == 'primary']
    backup  = [(u, v) for u, v, d in G.edges(data=True)
               if d['role'] == 'backup']
    print(f"  Primary links : {len(primary)}")
    print(f"  Backup links  : {len(backup)}")

    # Backbone-specific summary
    mw13 = [(u, v) for u, v, d in G.edges(data=True)
            if d['link_type'] == 'microwave_13ghz']
    lte  = [(u, v) for u, v, d in G.edges(data=True)
            if d['link_type'] == 'lte_priority']
    print(f"  Backbone 13 GHz links : {len(mw13)}")
    print(f"  Backbone LTE links    : {len(lte)}")
    print("------------------------------------------\n")


if __name__ == "__main__":
    config = load_config("scenario.yaml")
    G      = build_topology(config)
    topology_summary(G)
    draw_topology(G)
