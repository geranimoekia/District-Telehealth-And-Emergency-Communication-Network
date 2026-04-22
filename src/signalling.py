"""
signaling.py
============
Student 4 — Tsotlhe Seiphepi (Signaling and Routing Lead)
TELE 527 Group 1 | BIUST | 2026

SS7-inspired call setup delay model with signaling load analysis.

Deliverables from PDF:
  - Call setup delay = propagation delay (0.005 ms/km per hop) 
                     + processing delay (5 ms per core node, 2 ms per BS)
                     + queuing delay (proportional to congestion, rho/(1-rho) * service_time)
  - Signaling load (kbps) = calls/sec × messages/call × avg message size × 8 / 1000
  - Signaling channel utilisation < 70%
  - Burst/emergency analysis: normal (5 cps) vs emergency (25 cps)
  - Telemetry SLA: < 50 ms, Voice SLA: < 200 ms
"""

import os
import sys
import math
import numpy as np
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from topology import build_topology, load_config, get_positions


# ============================================================================
# Signaling Model Constants (SS7-inspired)
# ============================================================================

# Propagation delay: 0.005 ms per km (speed of light in fiber ~200 km/ms)
PROPAGATION_DELAY_PER_KM_MS = 0.005

# Processing delays (SS7 message processing)
PROCESSING_DELAY_CORE_MS = 5.0   # ms per core router (CR-1, CR-2)
PROCESSING_DELAY_BS_MS = 2.0     # ms per base station

# Signaling message parameters
SIGNALING_MSG_SIZE_BYTES = 100   # Average SS7/SIP message size
SIGNALING_MSGS_PER_CALL = 10     # Messages per call (INVITE, 100 Trying, 180 Ringing, 200 OK, ACK, BYE, etc.)

# Signaling channel capacity (dedicated 64 kbps per ITU-T standards)
SIGNALING_CHANNEL_CAPACITY_KBPS = 64.0

# Service time for queuing model (processing time per message)
SERVICE_TIME_MS = 5.0  # ms per message at the signaling gateway


# ============================================================================
# Helper Functions
# ============================================================================

def get_propagation_delay_ms(G, source, destination):
    """
    Calculate total propagation delay along the shortest path between nodes.
    
    Uses edge delay_ms attribute from scenario.yaml if available,
    otherwise falls back to Euclidean distance × 0.005 ms/km.
    """
    try:
        # Get shortest path
        path = nx.shortest_path(G, source=source, target=destination, weight='weight')
        
        total_delay = 0.0
        
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            
            # Use delay_ms from edge if available
            if G.has_edge(u, v) and 'delay_ms' in G[u][v]:
                total_delay += G[u][v]['delay_ms']
            else:
                # Fallback: estimate from positions
                pos = get_positions(G)
                if u in pos and v in pos:
                    x1, y1 = pos[u]
                    x2, y2 = pos[v]
                    dist_km = math.hypot(x2 - x1, y2 - y1)
                    total_delay += dist_km * PROPAGATION_DELAY_PER_KM_MS
                else:
                    total_delay += 1.0  # Default fallback
        
        return total_delay
    
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return float('inf')


def get_processing_delay_ms(G, path):
    """
    Calculate processing delay along a path.
    
    Processing delay = 5 ms per core node + 2 ms per BS
    (excluding source node, including destination if it processes)
    """
    delay = 0.0
    
    for node in path:
        node_type = G.nodes[node].get('type', 'unknown')
        
        if node_type == 'core_router':
            delay += PROCESSING_DELAY_CORE_MS
        elif node_type == 'base_station':
            delay += PROCESSING_DELAY_BS_MS
    
    return delay


def compute_queuing_delay_ms(arrival_rate_cps, service_rate_ps, service_time_ms):
    """
    Compute M/M/1 queuing delay.
    
    Formula: queuing_delay = (rho / (1 - rho)) × service_time
    where rho = arrival_rate / service_rate (utilization)
    
    Args:
        arrival_rate_cps: Call arrival rate (calls per second)
        service_rate_ps: Service rate (calls per second)
        service_time_ms: Service time per call (ms)
    
    Returns:
        Queuing delay in milliseconds
    """
    if service_rate_ps <= 0 or arrival_rate_cps >= service_rate_ps:
        return float('inf')  # System overloaded
    
    rho = arrival_rate_cps / service_rate_ps
    
    if rho >= 1.0:
        return float('inf')
    
    queuing_delay_ms = (rho / (1 - rho)) * service_time_ms
    
    return queuing_delay_ms


# ============================================================================
# Signaling Load Calculation
# ============================================================================

def compute_signaling_load_kbps(calls_per_sec, msgs_per_call=SIGNALING_MSGS_PER_CALL, 
                                 msg_size_bytes=SIGNALING_MSG_SIZE_BYTES):
    """
    Calculate signaling load in kbps.
    
    Formula: Load = calls/sec × msgs/call × msg_size_bytes × 8 / 1000
    
    Args:
        calls_per_sec: Call arrival rate (calls per second)
        msgs_per_call: Number of signaling messages per call
        msg_size_bytes: Average signaling message size in bytes
    
    Returns:
        Signaling load in kbps
    """
    load_bps = calls_per_sec * msgs_per_call * msg_size_bytes * 8
    load_kbps = load_bps / 1000.0
    return load_kbps


def compute_channel_utilisation(signaling_load_kbps, channel_capacity_kbps=SIGNALING_CHANNEL_CAPACITY_KBPS):
    """
    Calculate signaling channel utilisation percentage.
    
    Args:
        signaling_load_kbps: Current signaling load
        channel_capacity_kbps: Maximum channel capacity
    
    Returns:
        Utilisation as percentage (0-100)
    """
    if channel_capacity_kbps <= 0:
        return 100.0
    
    utilisation = (signaling_load_kbps / channel_capacity_kbps) * 100
    return min(utilisation, 100.0)


# ============================================================================
# Call Setup Delay Model
# ============================================================================

def compute_call_setup_delay_ms(G, source, destination, calls_per_sec, 
                                 service_rate_ps=200,  # Default service rate (calls/sec)
                                 include_queuing=True):
    """
    Compute SS7-inspired call setup delay.
    
    Total delay = propagation_delay + processing_delay + queuing_delay
    
    Args:
        G: NetworkX graph
        source: Source node (e.g., BS1)
        destination: Destination node (e.g., CR-1 or CR-2)
        calls_per_sec: Call arrival rate at this source
        service_rate_ps: Service rate at the signaling gateway
        include_queuing: Whether to include queuing delay
    
    Returns:
        dict with delay components and total
    """
    try:
        # Get shortest path
        path = nx.shortest_path(G, source=source, target=destination, weight='weight')
        
        # 1. Propagation delay
        prop_delay = get_propagation_delay_ms(G, source, destination)
        
        # 2. Processing delay
        proc_delay = get_processing_delay_ms(G, path)
        
        # 3. Queuing delay (M/M/1 model)
        queuing_delay = 0.0
        if include_queuing:
            queuing_delay = compute_queuing_delay_ms(calls_per_sec, service_rate_ps, SERVICE_TIME_MS)
        
        total_delay = prop_delay + proc_delay + queuing_delay
        
        return {
            'path': path,
            'path_hops': len(path) - 1,
            'propagation_delay_ms': round(prop_delay, 2),
            'processing_delay_ms': round(proc_delay, 2),
            'queuing_delay_ms': round(queuing_delay, 2) if queuing_delay != float('inf') else float('inf'),
            'total_delay_ms': round(total_delay, 2) if total_delay != float('inf') else float('inf'),
            'overloaded': total_delay == float('inf')
        }
    
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return {
            'path': None,
            'path_hops': 0,
            'propagation_delay_ms': float('inf'),
            'processing_delay_ms': float('inf'),
            'queuing_delay_ms': float('inf'),
            'total_delay_ms': float('inf'),
            'overloaded': True
        }


# ============================================================================
# Normal vs Burst Analysis
# ============================================================================

def analyze_normal_vs_burst(scenario, G, normal_cps=5.0, burst_cps=25.0):
    """
    Compare normal traffic vs emergency burst scenario.
    
    Returns:
        dict with comparison metrics for both scenarios
    """
    # Get base stations
    bs_nodes = [n for n in G.nodes() if G.nodes[n].get('type') == 'base_station']
    
    # Service rate for signaling (calls per second)
    # Assuming signaling gateway can handle 200 calls/sec normally
    service_rate = 200.0
    
    results = {
        'normal': {
            'calls_per_sec': normal_cps,
            'per_bs': {},
            'aggregate': {}
        },
        'burst': {
            'calls_per_sec': burst_cps,
            'per_bs': {},
            'aggregate': {}
        }
    }
    
    for scenario_type, cps in [('normal', normal_cps), ('burst', burst_cps)]:
        total_signaling_load = 0.0
        total_setup_delays = []
        
        for bs in bs_nodes:
            # Compute signaling load for this BS
            sig_load_kbps = compute_signaling_load_kbps(cps)
            
            # Compute call setup delay to CR-1 (primary)
            delay_result = compute_call_setup_delay_ms(G, bs, 'CR-1', cps, service_rate)
            
            # Channel utilisation
            utilisation_pct = compute_channel_utilisation(sig_load_kbps)
            
            # SLA compliance
            telemetry_sla_met = delay_result['total_delay_ms'] <= 50.0
            voice_sla_met = delay_result['total_delay_ms'] <= 200.0
            
            results[scenario_type]['per_bs'][bs] = {
                'signaling_load_kbps': round(sig_load_kbps, 2),
                'channel_utilisation_pct': round(utilisation_pct, 1),
                'call_setup_delay_ms': delay_result['total_delay_ms'],
                'propagation_delay_ms': delay_result['propagation_delay_ms'],
                'processing_delay_ms': delay_result['processing_delay_ms'],
                'queuing_delay_ms': delay_result['queuing_delay_ms'],
                'telemetry_sla_met': telemetry_sla_met,
                'voice_sla_met': voice_sla_met,
                'overloaded': delay_result['overloaded']
            }
            
            total_signaling_load += sig_load_kbps
            if not delay_result['overloaded']:
                total_setup_delays.append(delay_result['total_delay_ms'])
        
        # Aggregate metrics
        results[scenario_type]['aggregate'] = {
            'total_signaling_load_kbps': round(total_signaling_load, 2),
            'avg_setup_delay_ms': round(np.mean(total_setup_delays), 2) if total_setup_delays else float('inf'),
            'max_setup_delay_ms': round(max(total_setup_delays), 2) if total_setup_delays else float('inf'),
            'p95_setup_delay_ms': round(np.percentile(total_setup_delays, 95), 2) if total_setup_delays else float('inf'),
            'utilisation_ok': all(r['channel_utilisation_pct'] < 70 for r in results[scenario_type]['per_bs'].values()),
            'sla_telemetry_ok': all(r['telemetry_sla_met'] for r in results[scenario_type]['per_bs'].values()),
            'sla_voice_ok': all(r['voice_sla_met'] for r in results[scenario_type]['per_bs'].values())
        }
    
    # Compute comparison
    comparison = {
        'load_multiplier': burst_cps / normal_cps,
        'signaling_load_increase_pct': ((results['burst']['aggregate']['total_signaling_load_kbps'] / 
                                          results['normal']['aggregate']['total_signaling_load_kbps']) - 1) * 100,
        'delay_increase_pct': ((results['burst']['aggregate']['avg_setup_delay_ms'] / 
                                results['normal']['aggregate']['avg_setup_delay_ms']) - 1) * 100,
        'normal_utilisation_ok': results['normal']['aggregate']['utilisation_ok'],
        'burst_utilisation_ok': results['burst']['aggregate']['utilisation_ok'],
        'normal_sla_met': results['normal']['aggregate']['sla_telemetry_ok'],
        'burst_sla_met': results['burst']['aggregate']['sla_telemetry_ok']
    }
    
    results['comparison'] = comparison
    
    return results


# ============================================================================
# Signaling Performance Dashboard
# ============================================================================

def generate_signaling_report(scenario, G, load_multiplier=1.0):
    """
    Generate complete signaling analysis report.
    
    Args:
        scenario: Loaded scenario dict
        G: NetworkX graph
        load_multiplier: Traffic multiplier (1.0 = normal, 2.0 = 2x load)
    
    Returns:
        dict with all signaling metrics
    """
    # Get traffic parameters from scenario
    traffic = scenario.get('traffic', {})
    voice_calls_per_hour = traffic.get('voice', {}).get('arrival_rate_per_hour', 15)
    video_calls_per_hour = traffic.get('video', {}).get('arrival_rate_per_hour', 8)
    
    # Total calls per second (normal)
    normal_cps = (voice_calls_per_hour + video_calls_per_hour) / 3600.0 * load_multiplier
    burst_cps = normal_cps * 5  # 5x burst for emergency
    
    # Run analysis
    results = analyze_normal_vs_burst(scenario, G, normal_cps, burst_cps)
    
    # Add metadata
    results['metadata'] = {
        'load_multiplier': load_multiplier,
        'normal_calls_per_sec': normal_cps,
        'burst_calls_per_sec': burst_cps,
        'signaling_msg_size_bytes': SIGNALING_MSG_SIZE_BYTES,
        'signaling_msgs_per_call': SIGNALING_MSGS_PER_CALL,
        'channel_capacity_kbps': SIGNALING_CHANNEL_CAPACITY_KBPS
    }
    
    return results


def create_burst_analysis_table(results):
    """
    Create DataFrame for burst analysis comparison.
    
    Returns:
        DataFrame with normal vs burst metrics
    """
    data = []
    
    for scenario_type in ['normal', 'burst']:
        agg = results[scenario_type]['aggregate']
        data.append({
            'Scenario': scenario_type.upper(),
            'Calls/sec': results[scenario_type]['calls_per_sec'],
            'Signaling Load (kbps)': agg['total_signaling_load_kbps'],
            'Channel Utilisation (%)': round(agg['total_signaling_load_kbps'] / SIGNALING_CHANNEL_CAPACITY_KBPS * 100, 1),
            'Avg Setup Delay (ms)': agg['avg_setup_delay_ms'],
            'P95 Setup Delay (ms)': agg['p95_setup_delay_ms'],
            'Telemetry SLA (<50ms)': '✓' if agg['sla_telemetry_ok'] else '✗',
            'Voice SLA (<200ms)': '✓' if agg['sla_voice_ok'] else '✗',
            'Utilisation <70%': '✓' if agg['utilisation_ok'] else '✗'
        })
    
    return pd.DataFrame(data)


def print_signaling_summary(results):
    """Print formatted signaling analysis summary."""
    print("\n" + "=" * 80)
    print("SIGNALING ANALYSIS SUMMARY")
    print("=" * 80)
    
    print(f"\n📡 Configuration:")
    print(f"   Signaling msg size: {SIGNALING_MSG_SIZE_BYTES} bytes")
    print(f"   Msgs per call: {SIGNALING_MSGS_PER_CALL}")
    print(f"   Channel capacity: {SIGNALING_CHANNEL_CAPACITY_KBPS} kbps")
    
    print(f"\n📊 Normal vs Burst Comparison:")
    print(f"   Load multiplier: {results['comparison']['load_multiplier']:.1f}x")
    print(f"   Signaling load increase: {results['comparison']['signaling_load_increase_pct']:.1f}%")
    print(f"   Delay increase: {results['comparison']['delay_increase_pct']:.1f}%")
    
    print(f"\n📈 Normal Scenario ({results['normal']['calls_per_sec']:.2f} calls/sec):")
    norm = results['normal']['aggregate']
    print(f"   Total signaling load: {norm['total_signaling_load_kbps']:.2f} kbps")
    print(f"   Channel utilisation: {norm['total_signaling_load_kbps'] / SIGNALING_CHANNEL_CAPACITY_KBPS * 100:.1f}%")
    print(f"   Avg setup delay: {norm['avg_setup_delay_ms']:.2f} ms")
    print(f"   P95 setup delay: {norm['p95_setup_delay_ms']:.2f} ms")
    print(f"   SLA telemetry (<50ms): {'✓ PASS' if norm['sla_telemetry_ok'] else '✗ FAIL'}")
    print(f"   SLA voice (<200ms): {'✓ PASS' if norm['sla_voice_ok'] else '✗ FAIL'}")
    
    print(f"\n🚨 Burst/Emergency Scenario ({results['burst']['calls_per_sec']:.2f} calls/sec):")
    burst = results['burst']['aggregate']
    print(f"   Total signaling load: {burst['total_signaling_load_kbps']:.2f} kbps")
    print(f"   Channel utilisation: {burst['total_signaling_load_kbps'] / SIGNALING_CHANNEL_CAPACITY_KBPS * 100:.1f}%")
    print(f"   Avg setup delay: {burst['avg_setup_delay_ms']:.2f} ms")
    print(f"   P95 setup delay: {burst['p95_setup_delay_ms']:.2f} ms")
    print(f"   SLA telemetry (<50ms): {'✓ PASS' if burst['sla_telemetry_ok'] else '✗ FAIL'}")
    print(f"   SLA voice (<200ms): {'✓ PASS' if burst['sla_voice_ok'] else '✗ FAIL'}")
    
    print(f"\n⚠️ Requirements Check:")
    print(f"   Channel utilisation <70% in normal: {'✓' if results['comparison']['normal_utilisation_ok'] else '✗'}")
    print(f"   Channel utilisation <70% in burst: {'✓' if results['comparison']['burst_utilisation_ok'] else '✗'}")
    print(f"   Telemetry SLA met in normal: {'✓' if results['comparison']['normal_sla_met'] else '✗'}")
    print(f"   Telemetry SLA met in burst: {'✓' if results['comparison']['burst_sla_met'] else '✗'}")


# ============================================================================
# Main Execution
# ============================================================================

if __name__ == "__main__":
    import networkx as nx
    
    print("=" * 80)
    print("TELE 527 - SIGNALING ANALYSIS MODULE")
    print("SS7-Inspired Call Setup Delay Model")
    print("=" * 80)
    
    # Load scenario and build topology
    scenario_path = os.path.join(os.path.dirname(__file__), "..", "scenario.yaml")
    if not os.path.exists(scenario_path):
        scenario_path = "scenario.yaml"
    
    config = load_config(scenario_path)
    G = build_topology(config)
    
    print(f"\n✓ Loaded topology: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    
    # Run signaling analysis
    results = generate_signaling_report(config, G, load_multiplier=1.0)
    
    # Print summary
    print_signaling_summary(results)
    
    # Create comparison table
    df = create_burst_analysis_table(results)
    print("\n" + "=" * 80)
    print("BURST ANALYSIS TABLE")
    print("=" * 80)
    print(df.to_string(index=False))
    
    # Export results to dict format expected by main.py
    output_results = {
        'signaling': {
            'normal': results['normal'],
            'burst': results['burst'],
            'comparison': results['comparison'],
            'metadata': results['metadata']
        }
    }
    
    # Optionally save to file
    import json
    
    # Convert numpy types to Python native for JSON
    def convert_to_serializable(obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj
    
    output_path = "results/signaling_results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(output_results, f, indent=2, default=convert_to_serializable)
    
    print(f"\n✓ Results saved to {output_path}")
    print("\n✓ Signaling analysis complete!")