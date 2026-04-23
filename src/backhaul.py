"""
backhaul.py
===========
Student 4 — Tsotlhe Seiphepi (Signaling and Routing Lead)
TELE 527 Group 1 | BIUST | 2026

Microwave link budget for ALL 12 links:
  - 5 primary:   BS1-BS5 → CR-1 (7 GHz)
  - 5 backup:    BS1-BS5 → CR-2 (7 GHz)
  - 2 backbone:  CR-1 ↔ CR-2 (13 GHz)

Deliverables from PDF:
  - 12 rows with FSPL, rain attenuation, Pr, fade margin, PASS/FAIL
  - All links must show PASS (fade margin >= 20 dB)
  - Output for figures/backhaul.png
"""

import math
import os
import sys
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from propagation import microwave_budget, rain_attenuation_db


def load_scenario(scenario_path="scenario.yaml"):
    """Load scenario.yaml - standalone fallback if not passed."""
    import yaml
    with open(scenario_path, 'r') as f:
        return yaml.safe_load(f)


def compute_distances(scenario):
    """
    Compute distances between all site pairs.
    
    Returns dict: {(from, to): distance_km}
    """
    # Build coordinate lookup
    coords = {site['name']: (site['x_km'], site['y_km']) 
              for site in scenario['sites']}
    
    distances = {}
    for link in scenario['links']:
        from_site = link['from']
        to_site = link['to']
        
        x1, y1 = coords[from_site]
        x2, y2 = coords[to_site]
        dist = math.hypot(x2 - x1, y2 - y1)
        distances[(from_site, to_site)] = dist
        
    return distances


def compute_link_budgets(scenario, distances=None):
    """
    Compute link budget for ALL 12 microwave links.
    
    Returns:
        list of dicts, each containing:
            link_name, from, to, type, role, frequency_ghz,
            distance_km, fspl_db, rain_attenuation_db,
            rx_power_dbm, fade_margin_db, required_margin,
            pass_fail, capacity_mbps
    """
    if distances is None:
        distances = compute_distances(scenario)
    
    # Extract backhaul configs
    bh_cfg = scenario['backhaul']
    bb_cfg = scenario['backbone_13ghz']
    
    results = []
    
    # 1. Primary backhaul links: BS → CR-1 (7 GHz)
    for site in scenario['sites']:
        if site['type'] != 'base_station':
            continue
        
        from_site = site['name']
        to_site = 'CR-1'
        dist = distances.get((from_site, to_site))
        if dist is None:
            # Try reverse direction
            dist = distances.get((to_site, from_site))
        
        if dist is None:
            print(f"Warning: No distance found for {from_site} → {to_site}")
            continue
        
        # Microwave budget
        mw = microwave_budget(bh_cfg['frequency_ghz'], dist, bh_cfg)
        
        # Rain attenuation
        rain_db = rain_attenuation_db(dist, bh_cfg['frequency_ghz'])
        
        # Net margin after rain
        net_margin = mw['link_margin_db'] - rain_db
        
        results.append({
            'link_name': f"{from_site}→{to_site}",
            'from': from_site,
            'to': to_site,
            'type': 'backhaul',
            'role': 'primary',
            'frequency_ghz': bh_cfg['frequency_ghz'],
            'distance_km': round(dist, 2),
            'fspl_db': mw['fspl_db'],
            'rain_attenuation_db': rain_db,
            'rx_power_dbm': mw['rx_power_dbm'],
            'fade_margin_db': mw['link_margin_db'],
            'net_margin_after_rain_db': round(net_margin, 1),
            'required_margin_db': mw['required_margin'],
            'pass_fail': mw['status'],
            'capacity_mbps': mw['capacity_mbps'],
        })
    
    # 2. Backup backhaul links: BS → CR-2 (7 GHz)
    for site in scenario['sites']:
        if site['type'] != 'base_station':
            continue
        
        from_site = site['name']
        to_site = 'CR-2'
        dist = distances.get((from_site, to_site))
        if dist is None:
            dist = distances.get((to_site, from_site))
        
        if dist is None:
            continue
        
        mw = microwave_budget(bh_cfg['frequency_ghz'], dist, bh_cfg)
        rain_db = rain_attenuation_db(dist, bh_cfg['frequency_ghz'])
        net_margin = mw['link_margin_db'] - rain_db
        
        results.append({
            'link_name': f"{from_site}→{to_site}",
            'from': from_site,
            'to': to_site,
            'type': 'backhaul',
            'role': 'backup',
            'frequency_ghz': bh_cfg['frequency_ghz'],
            'distance_km': round(dist, 2),
            'fspl_db': mw['fspl_db'],
            'rain_attenuation_db': rain_db,
            'rx_power_dbm': mw['rx_power_dbm'],
            'fade_margin_db': mw['link_margin_db'],
            'net_margin_after_rain_db': round(net_margin, 1),
            'required_margin_db': mw['required_margin'],
            'pass_fail': mw['status'],
            'capacity_mbps': mw['capacity_mbps'],
        })
    
    # 3. Backbone links: CR-1 ↔ CR-2 (13 GHz) - both directions
    for from_site, to_site in [('CR-1', 'CR-2'), ('CR-2', 'CR-1')]:
        dist = distances.get((from_site, to_site))
        if dist is None:
            dist = distances.get((to_site, from_site))
        
        if dist is None:
            continue
        
        mw = microwave_budget(bb_cfg['frequency_ghz'], dist, bb_cfg)
        rain_db = rain_attenuation_db(dist, bb_cfg['frequency_ghz'])
        net_margin = mw['link_margin_db'] - rain_db
        
        results.append({
            'link_name': f"{from_site}→{to_site}",
            'from': from_site,
            'to': to_site,
            'type': 'backbone',
            'role': 'primary',
            'frequency_ghz': bb_cfg['frequency_ghz'],
            'distance_km': round(dist, 2),
            'fspl_db': mw['fspl_db'],
            'rain_attenuation_db': rain_db,
            'rx_power_dbm': mw['rx_power_dbm'],
            'fade_margin_db': mw['link_margin_db'],
            'net_margin_after_rain_db': round(net_margin, 1),
            'required_margin_db': mw['required_margin'],
            'pass_fail': mw['status'],
            'capacity_mbps': mw['capacity_mbps'],
        })
    
    return results


def check_all_links_pass(results):
    """Verify all links have fade_margin >= 20 dB (PASS)."""
    failures = [r for r in results if r['pass_fail'] != 'PASS']
    return {
        'all_pass': len(failures) == 0,
        'fail_count': len(failures),
        'failures': failures
    }


def generate_link_budget_table(results):
    """Generate DataFrame for the link budget table (for figure)."""
    df = pd.DataFrame(results)
    
    # Select and order columns for display
    columns = [
        'link_name', 'type', 'role', 'frequency_ghz', 'distance_km',
        'fspl_db', 'rain_attenuation_db', 'rx_power_dbm',
        'fade_margin_db', 'required_margin_db', 'pass_fail', 'capacity_mbps'
    ]
    
    return df[columns]


def save_link_budget_figure(df, output_path="figures/backhaul.png"):
    """Create and save the link budget table figure."""
    import matplotlib.pyplot as plt
    from matplotlib.table import Table
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.axis('off')
    
    # Prepare table data
    headers = ['Link', 'Type', 'Role', 'Freq\n(GHz)', 'Dist\n(km)', 
               'FSPL\n(dB)', 'Rain\n(dB)', 'Rx Power\n(dBm)', 
               'Margin\n(dB)', 'Req\n(dB)', 'Status', 'Cap\n(Mbps)']
    
    cell_text = []
    for _, row in df.iterrows():
        # Color-code status
        status = row['pass_fail']
        cell_text.append([
            row['link_name'],
            row['type'],
            row['role'],
            f"{row['frequency_ghz']:.1f}",
            f"{row['distance_km']:.1f}",
            f"{row['fspl_db']:.1f}",
            f"{row['rain_attenuation_db']:.2f}",
            f"{row['rx_power_dbm']:.1f}",
            f"{row['fade_margin_db']:.1f}",
            f"{row['required_margin_db']:.0f}",
            status,
            f"{row['capacity_mbps']}"
        ])
    
    # Create table
    table = ax.table(cellText=cell_text, colLabels=headers,
                     loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1.2, 1.5)
    
    # Color rows by pass/fail
    for i, (_, row) in enumerate(df.iterrows()):
        if row['pass_fail'] == 'PASS':
            table[(i+1, 10)].set_facecolor('#90EE90')  # Light green
        else:
            table[(i+1, 10)].set_facecolor('#FFCCCC')  # Light red
    
    # Style header
    for j in range(len(headers)):
        table[(0, j)].set_facecolor('#2C3E50')
        table[(0, j)].set_text_props(color='white', fontweight='bold')
    
    ax.set_title('Microwave Link Budget Table - All 12 Links\n(Required Margin ≥ 20 dB)',
                 fontsize=12, fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Link budget figure saved → {output_path}")


# ============================================================================
# Main execution (for standalone testing)
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("BACKHAUL LINK BUDGET ANALYSIS")
    print("=" * 70)
    
    # Load scenario
    scenario = load_scenario("scenario.yaml")
    
    # Compute distances
    distances = compute_distances(scenario)
    print(f"\n✓ Computed distances for {len(distances)} directed links")
    
    # Compute link budgets
    results = compute_link_budgets(scenario, distances)
    print(f"✓ Computed budgets for {len(results)} microwave links")
    
    # Create DataFrame
    df = generate_link_budget_table(results)
    print("\n" + "=" * 70)
    print("LINK BUDGET TABLE")
    print("=" * 70)
    print(df.to_string(index=False))
    
    # Check all links pass
    check = check_all_links_pass(results)
    print("\n" + "=" * 70)
    print("VALIDATION")
    print("=" * 70)
    print(f"All links PASS (margin ≥ 20 dB): {check['all_pass']}")
    if not check['all_pass']:
        print(f"FAILING LINKS: {len(check['failures'])}")
        for f in check['failures']:
            print(f"  - {f['link_name']}: margin={f['fade_margin_db']:.1f} dB")
    
    # Save figure
    save_link_budget_figure(df)
    
    # Output for results dict (matches PDF)
    results_dict = {
        'backhaul': {
            'link_budgets': results,
            'all_links_pass': check['all_pass'],
            'total_links': len(results),
            'pass_count': len([r for r in results if r['pass_fail'] == 'PASS']),
            'fail_count': check['fail_count']
        }
    }
    
    print("\n✓ Results stored in results_dict['backhaul']")
