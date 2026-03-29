"""
forecasting.py
--------------
Traffic forecasting and upgrade trigger module for TELE 527 Group 1.

Implements:
  - Compound annual growth model: U(t) = U0 * (1 + r)^t
  - Link utilisation forecast with planning and action trigger crossovers
  - Voice Erlang growth forecast with channel upgrade trigger
  - Phased upgrade recommendation text for the report

All parameters are read from scenario.yaml (forecasting section).

Design note
-----------
The initial utilisation is set to 0.60 (60%) in the scenario, not a low value
like 5-10%. This ensures the forecast crosses both upgrade triggers within the
5-year horizon - a flat forecast that never triggers is an engineering error,
not a good result.

Student 2 responsibility - Traffic and Teletraffic Lead
TELE 527 | Group 1 | BIUST | 2026
"""

import math
import numpy as np
import pandas as pd
import yaml
from pathlib import Path


# -----------------------------------------------------------------------
# Scenario loader
# -----------------------------------------------------------------------

def load_scenario(path: str = "scenario.yaml") -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# -----------------------------------------------------------------------
# Utilisation growth forecast
# -----------------------------------------------------------------------

def forecast_utilisation(
    scenario: dict,
    link_capacity_mbps: float = 100.0,
) -> dict:
    """
    Project backhaul link utilisation over the forecast horizon.

    Growth model:  U(t) = U0 * (1 + r)^t

    Crossover times are computed analytically:
        t = log(U_trigger / U0) / log(1 + r)

    Parameters
    ----------
    scenario : dict
        Loaded scenario YAML.
    link_capacity_mbps : float
        Backhaul link capacity. Default 100 Mbps (from scenario links).

    Returns
    -------
    dict with keys:
        annual_table   : pd.DataFrame - year-by-year snapshot
        curve          : pd.DataFrame - high-resolution curve for plotting
        t_plan         : float        - year when planning trigger fires
        t_act          : float        - year when action trigger fires
        planning_trigger, action_trigger, initial_utilisation, growth_rate
    """
    fc      = scenario["forecasting"]
    U0      = fc["initial_utilisation"]
    r       = fc["annual_growth_rate"]
    horizon = fc["horizon_years"]
    u_plan  = fc["planning_trigger_rho"]
    u_act   = fc["action_trigger_rho"]

    # Analytical crossover times
    t_plan = math.log(u_plan / U0) / math.log(1.0 + r) if U0 < u_plan else 0.0
    t_act  = math.log(u_act  / U0) / math.log(1.0 + r) if U0 < u_act  else 0.0

    # Annual snapshot table
    years    = list(range(0, horizon + 1))
    U_annual = [U0 * (1.0 + r) ** t for t in years]

    annual_table = pd.DataFrame({
        "year":          years,
        "utilisation":   [round(u, 4) for u in U_annual],
        "traffic_mbps":  [round(u * link_capacity_mbps, 2) for u in U_annual],
        "status": [
            "UPGRADE NOW"  if u >= u_act  else
            "PLAN UPGRADE" if u >= u_plan else
            "SAFE"
            for u in U_annual
        ],
    })

    # High-resolution curve for smooth plot
    t_fine  = np.linspace(0, horizon, 500)
    U_fine  = U0 * (1.0 + r) ** t_fine
    curve   = pd.DataFrame({"year": t_fine, "utilisation": U_fine})

    return {
        "annual_table":       annual_table,
        "curve":              curve,
        "t_plan":             round(t_plan, 2),
        "t_act":              round(t_act, 2),
        "planning_trigger":   u_plan,
        "action_trigger":     u_act,
        "initial_utilisation": U0,
        "growth_rate":        r,
        "horizon_years":      horizon,
    }


# -----------------------------------------------------------------------
# Erlang (voice channel) growth forecast
# -----------------------------------------------------------------------

def forecast_erlang(scenario: dict) -> pd.DataFrame:
    """
    Project voice offered load (Erlang) and blocking probability over time.

    The baseline channel count N is fixed at what was dimensioned for year 0.
    As traffic grows, blocking rises above the 2% KPI, signalling when a
    channel upgrade is needed.

    Returns
    -------
    pd.DataFrame
        Columns: year, offered_load_erl, blocking_prob, blocking_kpi_met,
                 channels_required, n_baseline, upgrade_needed
    """
    from teletraffic import erlang_b, dimension_channels

    fc      = scenario["forecasting"]
    r       = fc["annual_growth_rate"]
    horizon = fc["horizon_years"]

    A0       = scenario["traffic"]["voice"]["offered_load_erl"]
    target_B = scenario["traffic"]["voice"]["kpi_blocking_prob"]
    N_base   = dimension_channels(A0, target_B)

    rows = []
    for t in range(0, horizon + 1):
        A     = A0 * (1.0 + r) ** t
        B     = erlang_b(A, N_base)
        N_req = dimension_channels(A, target_B)
        rows.append({
            "year":             t,
            "offered_load_erl": round(A, 4),
            "blocking_prob":    round(B, 6),
            "blocking_kpi_met": bool(B <= target_B),
            "channels_required": N_req,
            "n_baseline":       N_base,
            "upgrade_needed":   bool(N_req > N_base),
        })

    return pd.DataFrame(rows)


# -----------------------------------------------------------------------
# Trunk Erlang forecast (aggregate all sites)
# -----------------------------------------------------------------------

def forecast_trunk_erlang(scenario: dict) -> pd.DataFrame:
    """
    Project aggregate backhaul trunk offered load over the forecast horizon.

    Trunk carries voice from all 5 sites combined.

    Returns
    -------
    pd.DataFrame
        Columns: year, trunk_offered_erl, blocking_prob, kpi_met,
                 channels_required, n_baseline, upgrade_needed
    """
    from teletraffic import erlang_b, dimension_channels

    fc      = scenario["forecasting"]
    r       = fc["annual_growth_rate"]
    horizon = fc["horizon_years"]

    A0_trunk = scenario["traffic"]["backhaul_trunk_erl"]
    target_B = scenario["traffic"]["voice"]["kpi_blocking_prob"]
    N_base   = dimension_channels(A0_trunk, target_B)

    rows = []
    for t in range(0, horizon + 1):
        A     = A0_trunk * (1.0 + r) ** t
        B     = erlang_b(A, N_base)
        N_req = dimension_channels(A, target_B)
        rows.append({
            "year":               t,
            "trunk_offered_erl":  round(A, 4),
            "blocking_prob":      round(B, 6),
            "kpi_met":            bool(B <= target_B),
            "channels_required":  N_req,
            "n_baseline":         N_base,
            "upgrade_needed":     bool(N_req > N_base),
        })

    return pd.DataFrame(rows)


# -----------------------------------------------------------------------
# Phased upgrade recommendation
# -----------------------------------------------------------------------

def upgrade_recommendation(scenario: dict) -> dict:
    """
    Generate structured upgrade recommendations for the report.

    Returns
    -------
    dict with keys:
        utilisation_summary : str  - plain text summary of utilisation triggers
        erlang_summary      : str  - plain text summary of voice channel upgrade
        phased_plan         : list - list of dicts describing each upgrade phase
        full_text           : str  - full recommendation paragraph
    """
    fc_util  = forecast_utilisation(scenario)
    fc_erl   = forecast_erlang(scenario)
    fc_trunk = forecast_trunk_erlang(scenario)

    t_plan = fc_util["t_plan"]
    t_act  = fc_util["t_act"]
    r      = fc_util["growth_rate"]
    U0     = fc_util["initial_utilisation"]

    # First year per-site voice upgrade needed
    site_fail = fc_erl[fc_erl["upgrade_needed"]]
    site_upgrade_year = int(site_fail["year"].iloc[0]) if not site_fail.empty else None
    site_N_new = int(site_fail["channels_required"].iloc[0]) if not site_fail.empty else None

    # First year trunk upgrade needed
    trunk_fail = fc_trunk[fc_trunk["upgrade_needed"]]
    trunk_upgrade_year = int(trunk_fail["year"].iloc[0]) if not trunk_fail.empty else None
    trunk_N_new = int(trunk_fail["channels_required"].iloc[0]) if not trunk_fail.empty else None

    # Build phased upgrade plan
    phases = []
    phases.append({
        "phase":        "Phase 1 - Planning",
        "trigger_year": t_plan,
        "action":       "Begin capacity planning. Initiate procurement for backhaul upgrades.",
        "utilisation":  f"{fc_util['planning_trigger'] * 100:.0f}%",
    })
    phases.append({
        "phase":        "Phase 2 - Action",
        "trigger_year": t_act,
        "action":       "Upgrade backhaul links from 100 Mbps to 200 Mbps.",
        "utilisation":  f"{fc_util['action_trigger'] * 100:.0f}%",
    })
    if trunk_upgrade_year is not None:
        phases.append({
            "phase":        "Phase 3 - Trunk voice channels",
            "trigger_year": trunk_upgrade_year,
            "action":       f"Expand backhaul trunk voice circuits from baseline to {trunk_N_new}.",
            "utilisation":  "N/A (Erlang KPI driven — trunk blocking exceeds 2%)",
        })
    if site_upgrade_year is not None:
        phases.append({
            "phase":        "Phase 4 - Per-site voice channels",
            "trigger_year": site_upgrade_year,
            "action":       f"Expand per-site voice circuits from baseline to {site_N_new}.",
            "utilisation":  "N/A (Erlang KPI driven — per-site blocking exceeds 2%)",
        })

    util_summary = (
        f"Starting at {U0*100:.0f}% utilisation and growing at {r*100:.0f}% per year, "
        f"the planning trigger (70%) fires at year {t_plan:.1f} "
        f"and the action trigger (90%) fires at year {t_act:.1f}."
    )

    if site_upgrade_year is not None:
        erl_summary = (
            f"With 15% annual traffic growth, per-site voice offered load exceeds "
            f"the baseline channel capacity in year {site_upgrade_year}, "
            f"requiring an increase from baseline to {site_N_new} circuits per site."
        )
    else:
        erl_summary = (
            "Per-site voice channel capacity is sufficient for the full 5-year forecast horizon."
        )

    if trunk_upgrade_year is not None:
        trunk_note = (
            f" The backhaul trunk requires circuit expansion to {trunk_N_new} by year {trunk_upgrade_year}"
            f" (aggregate blocking exceeds 2% KPI)."
        )
    else:
        trunk_note = ""

    full_text = (
        f"{util_summary} {erl_summary}{trunk_note} "
        f"A phased approach is recommended: procure equipment at year {t_plan:.1f}, "
        f"deploy upgraded links at year {t_act:.1f},"
        f" expand trunk circuits by year {trunk_upgrade_year if trunk_upgrade_year else 'N/A'},"
        f" and expand per-site voice circuits by year "
        f"{site_upgrade_year if site_upgrade_year else 'N/A'}."
    )

    return {
        "utilisation_summary": util_summary,
        "erlang_summary":      erl_summary,
        "phased_plan":         phases,
        "full_text":           full_text,
        "t_plan":              t_plan,
        "t_act":               t_act,
        "site_upgrade_year":   site_upgrade_year,
    }


# -----------------------------------------------------------------------
# Dashboard entry point
# -----------------------------------------------------------------------

def run_forecasting(scenario: dict) -> dict:
    """
    Run full forecasting analysis. Called by dashboard.py.

    Returns
    -------
    dict with keys:
        utilisation  : dict       - output of forecast_utilisation()
        erlang       : pd.DataFrame
        trunk        : pd.DataFrame
        recommendation : dict
    """
    return {
        "utilisation":     forecast_utilisation(scenario),
        "erlang":          forecast_erlang(scenario),
        "trunk":           forecast_trunk_erlang(scenario),
        "recommendation":  upgrade_recommendation(scenario),
    }


# -----------------------------------------------------------------------
# Standalone demo
# -----------------------------------------------------------------------

if __name__ == "__main__":
    import os

    path = os.path.join(os.path.dirname(__file__), "..", "scenario.yaml")
    sc   = load_scenario(path)

    print("=" * 65)
    print("UTILISATION FORECAST")
    print("=" * 65)
    fc = forecast_utilisation(sc)
    print(fc["annual_table"].to_string(index=False))
    print(f"\n  Planning trigger (70%) at year : {fc['t_plan']}")
    print(f"  Action trigger  (90%) at year : {fc['t_act']}")

    print("\n" + "=" * 65)
    print("ERLANG FORECAST (per site, fixed N_baseline)")
    print("=" * 65)
    print(forecast_erlang(sc).to_string(index=False))

    print("\n" + "=" * 65)
    print("TRUNK ERLANG FORECAST")
    print("=" * 65)
    print(forecast_trunk_erlang(sc).to_string(index=False))

    print("\n" + "=" * 65)
    print("UPGRADE RECOMMENDATION")
    print("=" * 65)
    rec = upgrade_recommendation(sc)
    print(rec["full_text"])
    print("\nPhased plan:")
    for p in rec["phased_plan"]:
        print(f"  [{p['phase']}] Year {p['trigger_year']} — {p['action']}")