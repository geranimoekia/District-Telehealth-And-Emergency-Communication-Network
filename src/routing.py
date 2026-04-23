"""
routing.py
==========
Student 4 — Tsotlhe Seiphepi (Signaling and Routing Lead)
TELE 527 Group 1 | BIUST | 2026

Dijkstra shortest-path routing with failure handling.

Deliverables from PDF:
  - Dijkstra on NetworkX DiGraph using edge weights from scenario.yaml
  - Routing tables for all 42 directed pairs (7 nodes)
  - CR-1 failure injection: remove all CR-1 edges, confirm all 5 BSs reroute via CR-2
  - Reroute count = 5
  - Routing figures: normal vs failure paths
"""

import os
import sys
import math
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from topology import build_topology, load_config, get_positions


def compute_routing_table(G, source):
    """
    Compute routing table for a single source node using Dijkstra.
    
    Args:
        G: NetworkX DiGraph with edge attribute 'weight'
        source: Source node name
    
    Returns:
        dict: {destination: next_hop} for all destinations reachable from source
              next_hop is the first node on the shortest path (excluding source)
    """
    routing_table = {}
    
    # Run Dijkstra to get shortest paths
    try:
        distances, paths = nx.single_source_dijkstra(G, source, weight='weight')
        
        for dest in G.nodes():
            if dest == source:
                routing_table[dest] = None  # No next hop to self
                continue
            
            if dest not in paths:
                routing_table[dest] = None  # Unreachable
                continue

            path = paths[dest]
            routing_table[dest] = path[1] if len(path) > 1 else None
    
    except nx.NetworkXNoPath:
        for dest in G.nodes():
            routing_table[dest] = None
    
    return routing_table


def compute_all_routing_tables(G):
    """
    Compute routing tables for all nodes in the graph.
    
    Args:
        G: NetworkX DiGraph
    
    Returns:
        dict: {source: {destination: next_hop}} for all 42 directed pairs
    """
    all_tables = {}
    
    for source in G.nodes():
        all_tables[source] = compute_routing_table(G, source)
    
    return all_tables


def get_all_shortest_paths(G):
    """
    Get all shortest paths for all source-destination pairs.
    
    Returns:
        dict: {source: {destination: list_of_nodes_in_path}}
    """
    all_paths = {}
    
    for source in G.nodes():
        all_paths[source] = {}
        try:
            # Get all shortest paths (though we only need one per destination)
            distances, paths = nx.single_source_dijkstra(G, source, weight='weight')
            for dest, path in paths.items():
                all_paths[source][dest] = path
        except nx.NetworkXNoPath:
            pass
    
    return all_paths


def inject_cr1_failure(G):
    """
    Simulate CR-1 failure by removing all edges connected to CR-1.
    
    Returns:
        G_failed: New graph with CR-1 edges removed
        removed_edges: List of edges that were removed
    """
    G_failed = G.copy()
    removed_edges = []
    
    # Find all edges incident to CR-1
    edges_to_remove = list(G_failed.edges(['CR-1'])) + list(G_failed.in_edges(['CR-1']))
    
    for u, v in edges_to_remove:
        if G_failed.has_edge(u, v):
            G_failed.remove_edge(u, v)
            removed_edges.append((u, v))
    
    return G_failed, removed_edges


def check_reroute_after_failure(G_normal, G_failed):
    """
    Verify that after CR-1 failure, all 5 base stations reroute to CR-2.
    
    Returns:
        dict with:
            reroute_count: Number of BSs that successfully reach CR-2
            bs_routes: Dict mapping each BS to its path to CR-2
            all_rerouted: Boolean if all 5 BSs can reach CR-2
    """
    bs_nodes = [n for n in G_normal.nodes() 
                if n.startswith('BS') or (hasattr(G_normal.nodes[n], 'get') and 
                   G_normal.nodes[n].get('type') == 'base_station')]
    
    # Also capture by type attribute if available
    if hasattr(G_normal, 'nodes'):
        bs_nodes = [n for n in G_normal.nodes() 
                    if G_normal.nodes[n].get('type') == 'base_station']
    
    results = {}
    
    for bs in bs_nodes:
        try:
            # Try to find path from BS to CR-2 in failed graph
            path = nx.shortest_path(G_failed, source=bs, target='CR-2', weight='weight')
            results[bs] = {
                'reachable': True,
                'path': path,
                'path_length': len(path) - 1
            }
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            results[bs] = {
                'reachable': False,
                'path': None,
                'path_length': None
            }
    
    reroute_count = sum(1 for r in results.values() if r['reachable'])
    
    return {
        'reroute_count': reroute_count,
        'total_bs': len(bs_nodes),
        'all_rerouted': reroute_count == len(bs_nodes),
        'bs_routes': results
    }


def compute_failure_comparison(G_normal, G_failed, normal_tables, failed_tables):
    """
    Compare baseline vs CR-1 failure scenario.
    
    Returns:
        dict with comparison metrics
    """
    # Get all paths for comparison
    normal_paths = get_all_shortest_paths(G_normal)
    failed_paths = get_all_shortest_paths(G_failed)
    
    # Count reroutes: paths that changed for BS -> CR-2
    bs_nodes = [n for n in G_normal.nodes() 
                if G_normal.nodes[n].get('type') == 'base_station']
    
    rerouted = 0
    delay_increases = []
    
    for bs in bs_nodes:
        normal_path = normal_paths.get(bs, {}).get('CR-2', [])
        failed_path = failed_paths.get(bs, {}).get('CR-2', [])
        
        if normal_path != failed_path and failed_path:
            rerouted += 1
            
            # Calculate delay increase (using edge delay_ms attribute)
            normal_delay = 0
            failed_delay = 0
            
            for i in range(len(normal_path) - 1):
                u, v = normal_path[i], normal_path[i+1]
                if G_normal.has_edge(u, v):
                    normal_delay += G_normal[u][v].get('delay_ms', 10)
            
            for i in range(len(failed_path) - 1):
                u, v = failed_path[i], failed_path[i+1]
                if G_failed.has_edge(u, v):
                    failed_delay += G_failed[u][v].get('delay_ms', 10)
            
            if normal_delay > 0:
                delay_increases.append((failed_delay - normal_delay) / normal_delay * 100)
    
    avg_delay_increase = sum(delay_increases) / len(delay_increases) if delay_increases else 0
    
    # Throughput change estimate (inversely proportional to path length/hops)
    avg_normal_hops = 0
    avg_failed_hops = 0
    hop_counts = 0
    
    for bs in bs_nodes:
        normal_path = normal_paths.get(bs, {}).get('CR-2', [])
        failed_path = failed_paths.get(bs, {}).get('CR-2', [])
        
        if normal_path and failed_path:
            avg_normal_hops += len(normal_path) - 1
            avg_failed_hops += len(failed_path) - 1
            hop_counts += 1
    
    if hop_counts > 0:
        avg_normal_hops /= hop_counts
        avg_failed_hops /= hop_counts
        throughput_change = (avg_normal_hops / avg_failed_hops - 1) * 100 if avg_failed_hops > 0 else 0
    else:
        throughput_change = 0
    
    return {
        'reroute_count': rerouted,
        'total_bs': len(bs_nodes),
        'avg_delay_increase_pct': round(avg_delay_increase, 2),
        'throughput_change_pct': round(throughput_change, 2),
        'delay_increases': delay_increases
    }


def draw_routing_figure(G_normal, G_failed, output_path="figures/routing.png"):
    """
    Create side-by-side routing diagrams: normal paths vs post-failure paths.
    Shows all 5 BSs and their paths to core routers.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    fig.patch.set_facecolor('#0d1117')
    
    pos = get_positions(G_normal)
    
    # Color mapping
    bs_color = '#3b82f6'  # Blue
    cr_color = '#22c55e'  # Green
    
    # Node types
    bs_nodes = [n for n in G_normal.nodes() if G_normal.nodes[n].get('type') == 'base_station']
    cr_nodes = [n for n in G_normal.nodes() if G_normal.nodes[n].get('type') == 'core_router']
    
    # ========== LEFT: Normal paths ==========
    ax1.set_facecolor('#0d1117')
    ax1.set_title('Normal Operation\n(All links active)', color='white', fontsize=12, pad=10)
    
    # Draw all edges (gray, faint)
    nx.draw_networkx_edges(G_normal, pos, edge_color='#555555', 
                           width=0.8, alpha=0.3, arrows=False, ax=ax1)
    
    # Draw primary paths from BS to CR-1 (highlighted)
    for bs in bs_nodes:
        try:
            path = nx.shortest_path(G_normal, source=bs, target='CR-1', weight='weight')
            edges = [(path[i], path[i+1]) for i in range(len(path)-1)]
            nx.draw_networkx_edges(G_normal, pos, edgelist=edges,
                                   edge_color='#3b82f6', width=2.5, alpha=0.8,
                                   arrows=False, ax=ax1)
        except nx.NetworkXNoPath:
            pass
    
    # Draw backbone (CR-1 to CR-2) in gold
    try:
        backbone = nx.shortest_path(G_normal, source='CR-1', target='CR-2', weight='weight')
        backbone_edges = [(backbone[i], backbone[i+1]) for i in range(len(backbone)-1)]
        nx.draw_networkx_edges(G_normal, pos, edgelist=backbone_edges,
                               edge_color='#eab308', width=3.0, alpha=0.9,
                               arrows=False, ax=ax1)
    except nx.NetworkXNoPath:
        pass
    
    # Draw nodes
    nx.draw_networkx_nodes(G_normal, pos, nodelist=cr_nodes,
                           node_color=cr_color, node_size=600,
                           node_shape='o', ax=ax1)
    nx.draw_networkx_nodes(G_normal, pos, nodelist=bs_nodes,
                           node_color=bs_color, node_size=450,
                           node_shape='s', ax=ax1)
    
    # Labels
    nx.draw_networkx_labels(G_normal, pos, font_color='white', 
                            font_size=9, font_weight='bold', ax=ax1)
    
    # ========== RIGHT: Post-failure paths ==========
    ax2.set_facecolor('#0d1117')
    ax2.set_title('CR-1 Failure Recovery\n(All BS → CR-2)', color='white', fontsize=12, pad=10)
    
    # Draw all remaining edges (gray, faint)
    nx.draw_networkx_edges(G_failed, pos, edge_color='#555555', 
                           width=0.8, alpha=0.3, arrows=False, ax=ax2)
    
    # Draw backup paths from BS to CR-2 (highlighted in orange)
    for bs in bs_nodes:
        try:
            path = nx.shortest_path(G_failed, source=bs, target='CR-2', weight='weight')
            edges = [(path[i], path[i+1]) for i in range(len(path)-1)]
            nx.draw_networkx_edges(G_failed, pos, edgelist=edges,
                                   edge_color='#f59e0b', width=2.5, alpha=0.8,
                                   arrows=False, ax=ax2)
        except nx.NetworkXNoPath:
            pass
    
    # Draw remaining backbone if CR-2 can reach CR-1 (unlikely after failure)
    # But CR-2 may still have outbound edges
    
    # Draw nodes (CR-1 now shown as failed - dimmed)
    nx.draw_networkx_nodes(G_failed, pos, nodelist=['CR-1'],
                           node_color='#666666', node_size=600,
                           node_shape='o', ax=ax2, alpha=0.4)
    nx.draw_networkx_nodes(G_failed, pos, nodelist=[n for n in cr_nodes if n != 'CR-1'],
                           node_color=cr_color, node_size=600,
                           node_shape='o', ax=ax2)
    nx.draw_networkx_nodes(G_failed, pos, nodelist=bs_nodes,
                           node_color=bs_color, node_size=450,
                           node_shape='s', ax=ax2)
    
    nx.draw_networkx_labels(G_failed, pos, font_color='white', 
                            font_size=9, font_weight='bold', ax=ax2)
    
    # Legend
    legend_elements = [
        Line2D([0], [0], color='#3b82f6', lw=2.5, label='Normal: BS → CR-1'),
        Line2D([0], [0], color='#f59e0b', lw=2.5, label='Failure: BS → CR-2'),
        Line2D([0], [0], color='#eab308', lw=3.0, label='Backbone (CR-1 ↔ CR-2)'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=cr_color,
                   markersize=10, label='Core Router (active)'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#666666',
                   markersize=10, label='Core Router (failed)'),
        plt.Line2D([0], [0], marker='s', color='w', markerfacecolor=bs_color,
                   markersize=10, label='Base Station'),
    ]
    
    ax1.legend(handles=legend_elements, loc='lower left', fontsize=8,
               facecolor='#161b22', edgecolor='#30363d', labelcolor='#8b949e')
    
    for ax in (ax1, ax2):
        ax.set_xlim(-4, 54)
        ax.set_ylim(-4, 54)
        ax.set_aspect('equal')
        ax.axis('off')
    
    plt.suptitle('Routing: Normal Operation vs CR-1 Failure Recovery\nTELE 527 Group 1',
                 color='white', fontsize=14, y=0.98)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='#0d1117')
    plt.close()
    print(f"Routing figure saved → {output_path}")


def run_routing_analysis(scenario_path="scenario.yaml"):
    """
    Main function to run complete routing analysis.
    
    Returns:
        dict: Complete results matching PDF deliverables
    """
    # Load scenario and build topology
    config = load_config(scenario_path)
    G_normal = build_topology(config)
    
    print("\n" + "=" * 70)
    print("ROUTING ANALYSIS")
    print("=" * 70)
    
    # 1. Compute routing tables for all 42 directed pairs
    print("\n[1/5] Computing routing tables for all node pairs...")
    routing_tables = compute_all_routing_tables(G_normal)
    
    # Verify 42 directed pairs (7 nodes * 6 destinations = 42)
    total_pairs = sum(len(table) - 1 for table in routing_tables.values())  # exclude self
    print(f"  ✓ {total_pairs} directed pairs processed")
    
    # 2. Get all shortest paths
    all_paths = get_all_shortest_paths(G_normal)
    
    # 3. Inject CR-1 failure
    print("\n[2/5] Injecting CR-1 failure...")
    G_failed, removed_edges = inject_cr1_failure(G_normal)
    print(f"  ✓ Removed {len(removed_edges)} edges connected to CR-1")
    
    # 4. Check rerouting
    print("\n[3/5] Checking rerouting for all 5 base stations...")
    reroute_check = check_reroute_after_failure(G_normal, G_failed)
    print(f"  ✓ Reroute count: {reroute_check['reroute_count']}/5 base stations reach CR-2")
    print(f"  ✓ All rerouted: {reroute_check['all_rerouted']}")
    
    # 5. Compute failure comparison
    print("\n[4/5] Computing failure comparison metrics...")
    failed_tables = compute_all_routing_tables(G_failed)
    comparison = compute_failure_comparison(G_normal, G_failed, routing_tables, failed_tables)
    print(f"  ✓ Reroute count: {comparison['reroute_count']}/{comparison['total_bs']}")
    print(f"  ✓ Avg delay increase: {comparison['avg_delay_increase_pct']}%")
    print(f"  ✓ Throughput change: {comparison['throughput_change_pct']}%")
    
    # 6. Draw routing figure
    print("\n[5/5] Generating routing figure...")
    draw_routing_figure(G_normal, G_failed, "figures/routing.png")
    
    # Package results
    results = {
        'routing': {
            'routing_tables': routing_tables,
            'paths': all_paths,
            'total_pairs': total_pairs,
            'nodes': list(G_normal.nodes())
        },
        'failure_analysis': {
            'removed_edges': removed_edges,
            'reroute_check': reroute_check,
            'comparison': comparison,
            'reroute_count': reroute_check['reroute_count'],
            'delay_increase_pct': comparison['avg_delay_increase_pct'],
            'throughput_change_pct': comparison['throughput_change_pct']
        }
    }
    
    # Print summary
    print("\n" + "=" * 70)
    print("ROUTING SUMMARY")
    print("=" * 70)
    print(f"Normal operation:")
    print(f"  - Nodes: {G_normal.number_of_nodes()}")
    print(f"  - Edges: {G_normal.number_of_edges()}")
    print(f"  - Routing pairs: {total_pairs}")
    print(f"\nCR-1 failure:")
    print(f"  - Removed edges: {len(removed_edges)}")
    print(f"  - BS → CR-2 reachable: {reroute_check['reroute_count']}/5")
    print(f"  - Delay increase: {comparison['avg_delay_increase_pct']:.1f}%")
    print(f"  - Throughput change: {comparison['throughput_change_pct']:.1f}%")
    
    return results


# ============================================================================
# Standalone execution
# ============================================================================

if __name__ == "__main__":
    # Find scenario.yaml path
    scenario_path = os.path.join(os.path.dirname(__file__), "..", "scenario.yaml")
    if not os.path.exists(scenario_path):
        scenario_path = "scenario.yaml"
    
    results = run_routing_analysis(scenario_path)
    
    # Export results dict for use by other modules
    print("\n✓ Results available in 'results' variable")
