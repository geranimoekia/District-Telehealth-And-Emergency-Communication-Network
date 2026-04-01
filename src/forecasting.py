"""
forecasting.py
--------------
Traffic forecasting and upgrade trigger module for TELE 527 Group 1.

Implements per the Student 2 specification:
  - Per-class compound monthly growth (CAGR):
        telemetry 25%/yr, voice 10%/yr, video 35%/yr
  - 36-month projection horizon
  - Planning trigger (70% utilisation) and action trigger (90%)
  - Procurement lead time (default 3 months) so orders are placed BEFORE
    the trigger month
  - Voice Erlang growth forecast with per-site and trunk upgrade triggers
  - Three-strategy upgrade comparison (cost kUSD, extended months,
    cost/month, rank)

Growth rate justification (cite in report §4.6)
-----------------------------------------------
  * Telemetry 25%/yr - typical IoT / remote-monitoring growth benchmark
  * Voice      10%/yr - conservative telehealth consultation growth
  * Video      35%/yr - telehealth video-consultation adoption benchmark

All parameters are read from scenario.yaml (forecasting section).

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
# Default per-class growth rates (overridable via scenario.yaml)
# -----------------------------------------------------------------------

DEFAULT_CAGR = {
    "telemetry": 0.25,   # 25 % / yr (IoT growth benchmark)
    "voice":     0.10,   # 10 % / yr (telehealth consultation growth)
    "video":     0.35,   # 35 % / yr (telehealth video adoption)
}

DEFAULT_HORIZON_MONTHS   = 36
DEFAULT_LEAD_TIME_MONTHS = 3
DEFAULT_PLAN_TRIGGER     = 0.70
DEFAULT_ACT_TRIGGER      = 0.90


def _get_cagr(scenario: dict) -> dict:
    """
    Pull per-class CAGR from scenario.yaml if present, else fall back to
    spec defaults. Scenario format (optional):

        forecasting:
          cagr:
            telemetry: 0.25
            voice:     0.10
            video:     0.35
    """
    fc   = scenario.get("forecasting", {})
    cagr = fc.get("cagr", {})
    return {
        "telemetry": cagr.get("telemetry", DEFAULT_CAGR["telemetry"]),
        "voice":     cagr.get("voice",     DEFAULT_CAGR["voice"]),
        "video":     cagr.get("video",     DEFAULT_CAGR["video"]),
    }


def _monthly_rate(annual_rate: float) -> float:
    """Convert an annual CAGR to the equivalent monthly compound rate."""
    return (1.0 + annual_rate) ** (1.0 / 12.0) - 1.0


# -----------------------------------------------------------------------
# Per-class Mbps projection over 36 months
# -----------------------------------------------------------------------

def forecast_mbps_per_class(scenario: dict) -> pd.DataFrame:
    """
    Project Mbps per class over the forecast horizon using per-class CAGR.

    Growth model (monthly compounding):
        Mbps(m) = Mbps(0) * (1 + r_month)^m
        where   r_month = (1 + r_yr)^(1/12) - 1

    The month-0 Mbps per class is computed from the traffic matrix
    aggregated across all base stations at alpha = 1.0, reusing traffic.py's
    compute_traffic_matrix() so the forecast starts from a physically
    consistent baseline.

    Returns
    -------
    pd.DataFrame
        Columns: month, telemetry_mbps, voice_mbps, video_mbps, total_mbps
    """
    from traffic import compute_traffic_matrix

    horizon = scenario.get("forecasting", {}).get(
        "horizon_months", DEFAULT_HORIZON_MONTHS
    )
    cagr = _get_cagr(scenario)
    rm   = {svc: _monthly_rate(r) for svc, r in cagr.items()}

    # Baseline: aggregate Mbps across all BS sites at alpha = 1.0
    matrix = compute_traffic_matrix(scenario, load_multiplier=1.0)
    base = {
        "telemetry": matrix["telemetry_mbps"].sum(),
        "voice":     matrix["voice_mbps"].sum(),
        "video":     matrix["video_mbps"].sum(),
    }

    rows = []
    for m in range(0, horizon + 1):
        tel = base["telemetry"] * (1.0 + rm["telemetry"]) ** m
        vox = base["voice"]     * (1.0 + rm["voice"])     ** m
        vid = base["video"]     * (1.0 + rm["video"])     ** m
        rows.append({
            "month":          m,
            "telemetry_mbps": round(tel, 6),
            "voice_mbps":     round(vox, 4),
            "video_mbps":     round(vid, 4),
            "total_mbps":     round(tel + vox + vid, 4),
        })
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------
# Utilisation growth forecast (worst-site link)
# -----------------------------------------------------------------------

def forecast_utilisation(
    scenario: dict,
    link_capacity_mbps: float = 100.0,
) -> dict:
    """
    Project backhaul link utilisation over the 36-month horizon using
    per-class CAGR applied to each traffic class's Mbps contribution on the
    busiest site (worst link).

        U(m) = (telemetry(m) + voice(m) + video(m)) / link_capacity

    Because each class grows at a different rate, U(m) is NOT a pure
    geometric series, so trigger crossovers are found by linear
    interpolation between adjacent months.

    Parameters
    ----------
    scenario : dict
        Loaded scenario YAML.
    link_capacity_mbps : float
        Backhaul link capacity in Mbps. Default 100.

    Returns
    -------
    dict with keys:
        table              : pd.DataFrame - month-by-month Mbps per class + U
        t_plan_months      : float        - month when 70% trigger fires
        t_act_months       : float        - month when 90% trigger fires
        order_plan_month   : float        - t_plan minus lead time
        order_act_month    : float        - t_act minus lead time
        planning_trigger, action_trigger, lead_time_months, horizon_months,
        worst_site, link_capacity_mbps, cagr
    """
    from traffic import compute_traffic_matrix

    fc      = scenario.get("forecasting", {})
    horizon = fc.get("horizon_months",       DEFAULT_HORIZON_MONTHS)
    u_plan  = fc.get("planning_trigger_rho", DEFAULT_PLAN_TRIGGER)
    u_act   = fc.get("action_trigger_rho",   DEFAULT_ACT_TRIGGER)
    lead_m  = fc.get("lead_time_months",     DEFAULT_LEAD_TIME_MONTHS)

    cagr = _get_cagr(scenario)
    rm   = {svc: _monthly_rate(r) for svc, r in cagr.items()}

    # Baseline Mbps per class on the BUSIEST site (worst-link focus)
    matrix    = compute_traffic_matrix(scenario, load_multiplier=1.0)
    worst_row = matrix.loc[matrix["total_mbps"].idxmax()]
    base = {
        "telemetry": float(worst_row["telemetry_mbps"]),
        "voice":     float(worst_row["voice_mbps"]),
        "video":     float(worst_row["video_mbps"]),
    }

    # Optional override: force month-0 utilisation to a specified value by
    # scaling all per-class baselines by the same factor. This preserves the
    # per-class growth rates while letting the report start from the spec's
    # assumed initial_utilisation (§4.4: init = 0.60, CAGR reaches 0.70 in ~1 yr).
    init_override = fc.get("initial_utilisation_override", None)
    if init_override is not None:
        natural_u0 = (base["telemetry"] + base["voice"] + base["video"]) / link_capacity_mbps
        if natural_u0 > 0:
            scale = float(init_override) / natural_u0
            base = {k: v * scale for k, v in base.items()}

    rows = []
    for m in range(0, horizon + 1):
        tel = base["telemetry"] * (1.0 + rm["telemetry"]) ** m
        vox = base["voice"]     * (1.0 + rm["voice"])     ** m
        vid = base["video"]     * (1.0 + rm["video"])     ** m
        total = tel + vox + vid
        u     = total / link_capacity_mbps
        rows.append({
            "month":          m,
            "telemetry_mbps": round(tel, 6),
            "voice_mbps":     round(vox, 4),
            "video_mbps":     round(vid, 4),
            "total_mbps":     round(total, 4),
            "utilisation":    round(u, 4),
            "status": (
                "UPGRADE NOW"  if u >= u_act  else
                "PLAN UPGRADE" if u >= u_plan else
                "SAFE"
            ),
        })
    table = pd.DataFrame(rows)

    def _crossover_month(u_target: float) -> float:
        """Linear-interpolate the month at which utilisation crosses u_target."""
        u = table["utilisation"].values
        if u[0] >= u_target:
            return 0.0
        for i in range(1, len(u)):
            if u[i] >= u_target:
                frac = (u_target - u[i-1]) / (u[i] - u[i-1])
                return round(float(i - 1 + frac), 2)
        return float("inf")  # never crosses within horizon

    t_plan = _crossover_month(u_plan)
    t_act  = _crossover_month(u_act)

    order_plan = max(0.0, t_plan - lead_m) if math.isfinite(t_plan) else float("inf")
    order_act  = max(0.0, t_act  - lead_m) if math.isfinite(t_act)  else float("inf")

    return {
        "table":              table,
        "t_plan_months":      t_plan,
        "t_act_months":       t_act,
        "order_plan_month":   order_plan,
        "order_act_month":    order_act,
        "planning_trigger":   u_plan,
        "action_trigger":     u_act,
        "lead_time_months":   lead_m,
        "horizon_months":     horizon,
        "worst_site":         str(worst_row["site"]),
        "link_capacity_mbps": link_capacity_mbps,
        "cagr":               cagr,
    }


# -----------------------------------------------------------------------
# Voice Erlang forecast (per site, fixed baseline N)
# -----------------------------------------------------------------------

def forecast_erlang(scenario: dict) -> pd.DataFrame:
    """
    Project per-site voice offered load and blocking probability over the
    36-month horizon using the voice CAGR (10%/yr).

    The baseline channel count N is dimensioned for month 0. As traffic
    grows, blocking rises; the month where blocking first exceeds the KPI
    is the voice upgrade trigger month.

    Returns
    -------
    pd.DataFrame
        Columns: month, offered_load_erl, blocking_prob, blocking_kpi_met,
                 channels_required, n_baseline, upgrade_needed
    """
    from src.teletraffic import erlang_b, dimension_channels

    horizon = scenario.get("forecasting", {}).get(
        "horizon_months", DEFAULT_HORIZON_MONTHS
    )
    r_month = _monthly_rate(_get_cagr(scenario)["voice"])

    A0       = scenario["traffic"]["voice"]["offered_load_erl"]
    target_B = scenario["traffic"]["voice"]["kpi_blocking_prob"]
    N_base   = dimension_channels(A0, target_B)

    rows = []
    for m in range(0, horizon + 1):
        A     = A0 * (1.0 + r_month) ** m
        B     = erlang_b(A, N_base)
        N_req = dimension_channels(A, target_B)
        rows.append({
            "month":             m,
            "offered_load_erl":  round(A, 4),
            "blocking_prob":     round(B, 6),
            "blocking_kpi_met":  bool(B <= target_B),
            "channels_required": N_req,
            "n_baseline":        N_base,
            "upgrade_needed":    bool(N_req > N_base),
        })
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------
# Trunk Erlang forecast (aggregate)
# -----------------------------------------------------------------------

def forecast_trunk_erlang(scenario: dict) -> pd.DataFrame:
    """
    Project aggregate backhaul trunk voice offered load over 36 months.

    Returns
    -------
    pd.DataFrame
        Columns: month, trunk_offered_erl, blocking_prob, kpi_met,
                 channels_required, n_baseline, upgrade_needed
    """
    from src.teletraffic import erlang_b, dimension_channels

    horizon = scenario.get("forecasting", {}).get(
        "horizon_months", DEFAULT_HORIZON_MONTHS
    )
    r_month = _monthly_rate(_get_cagr(scenario)["voice"])

    A0_trunk = scenario["traffic"]["backhaul_trunk_erl"]
    target_B = scenario["traffic"]["voice"]["kpi_blocking_prob"]
    N_base   = dimension_channels(A0_trunk, target_B)

    rows = []
    for m in range(0, horizon + 1):
        A     = A0_trunk * (1.0 + r_month) ** m
        B     = erlang_b(A, N_base)
        N_req = dimension_channels(A, target_B)
        rows.append({
            "month":             m,
            "trunk_offered_erl": round(A, 4),
            "blocking_prob":     round(B, 6),
            "kpi_met":           bool(B <= target_B),
            "channels_required": N_req,
            "n_baseline":        N_base,
            "upgrade_needed":    bool(N_req > N_base),
        })
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------
# Three-strategy upgrade comparison (spec §4.3 / Report Table 3)
# -----------------------------------------------------------------------

def strategy_comparison(scenario: dict) -> pd.DataFrame:
    """
    Compare at least three upgrade strategies to defer the action trigger.

    Each strategy is rated by:
      - cost_kUSD           : rough CAPEX in thousands of USD
      - extended_months     : additional months until the 90% action trigger
                              fires under the strategy (vs. do-nothing)
      - cost_per_month_kUSD : cost_kUSD / extended_months
      - rank                : 1 = best value (lowest cost per extended month)

    Strategies modelled
    -------------------
      1. Do nothing                  - baseline, no extension
      2. Backhaul link upgrade       - 100 Mbps → 200 Mbps per BS
      3. Core / CR upgrade           - ≈ +20% effective headroom
      4. Add one base station        - 5 sites → 6 sites (≈ +20% per-site)

    Cost figures are indicative; override via scenario.yaml under
    forecasting.strategy_costs_kusd if real quotes are available.

    Returns
    -------
    pd.DataFrame
        Columns: strategy, description, cost_kUSD, extended_months,
                 cost_per_month_kUSD, rank
    """
    # When comparing upgrade strategies, the initial_utilisation_override (if
    # set) must be disabled — otherwise every strategy's U(0) would be
    # rescaled back to the same fixed value, making all strategies appear
    # equivalent. Instead we fix the base case's absolute Mbps and let the
    # alternative link capacities change the DENOMINATOR.
    import copy

    # Cost defaults (override via scenario.yaml -> forecasting.strategy_costs_kusd)
    cfg_costs = scenario.get("forecasting", {}).get("strategy_costs_kusd", {})
    cost = {
        "do_nothing": cfg_costs.get("do_nothing",  0.0),
        "backhaul":   cfg_costs.get("backhaul",   40.0),  # 5 sites × ~8k link upgrade
        "core":       cfg_costs.get("core",       25.0),  # CR-1/CR-2 blade + licences
        "add_bs":     cfg_costs.get("add_bs",     60.0),  # new BS + microwave link
    }

    fc_base     = forecast_utilisation(scenario, link_capacity_mbps=100.0)
    base_action = fc_base["t_act_months"]

    # Build an upgrade-comparison scenario with the override lifted but traffic
    # rescaled so the natural U(0) equals the base-case override. This way,
    # bumping link_capacity_mbps actually reduces U(m) rather than forcing
    # U(0) back to the override value.
    sc_upgrade = copy.deepcopy(scenario)
    if "forecasting" in sc_upgrade and "initial_utilisation_override" in sc_upgrade["forecasting"]:
        sc_upgrade["forecasting"] = {
            k: v for k, v in sc_upgrade["forecasting"].items()
            if k != "initial_utilisation_override"
        }
        from traffic import compute_traffic_matrix as _ctm
        matrix       = _ctm(sc_upgrade, load_multiplier=1.0)
        worst_row    = matrix.loc[matrix["total_mbps"].idxmax()]
        natural_u0   = float(worst_row["total_mbps"]) / 100.0
        override_val = scenario["forecasting"]["initial_utilisation_override"]
        if natural_u0 > 0:
            scale = override_val / natural_u0
            t = sc_upgrade["traffic"]
            t["telemetry"] = {
                **t["telemetry"],
                "arrival_rate_per_hour": t["telemetry"]["arrival_rate_per_hour"] * scale,
                "offered_load_erl":      t["telemetry"]["offered_load_erl"]      * scale,
            }
            t["voice"] = {
                **t["voice"],
                "offered_load_erl": t["voice"]["offered_load_erl"] * scale,
            }
            t["video"] = {
                **t["video"],
                "offered_load_erl": t["video"]["offered_load_erl"] * scale,
            }

    # Strategy 1: Do nothing
    s1_ext = 0.0

    # Strategy 2: Backhaul 100 → 200 Mbps
    fc_2x  = forecast_utilisation(sc_upgrade, link_capacity_mbps=200.0)
    s2_ext = (fc_2x["t_act_months"] - base_action) \
             if (math.isfinite(fc_2x["t_act_months"]) and math.isfinite(base_action)) \
             else float("inf")

    # Strategy 3: Core upgrade - modelled as 20% effective capacity gain
    fc_core = forecast_utilisation(sc_upgrade, link_capacity_mbps=120.0)
    s3_ext  = (fc_core["t_act_months"] - base_action) \
              if (math.isfinite(fc_core["t_act_months"]) and math.isfinite(base_action)) \
              else float("inf")

    # Strategy 4: Add one BS - 5 sites → 6 sites ≡ effective cap × 6/5
    fc_add = forecast_utilisation(sc_upgrade, link_capacity_mbps=100.0 * 6.0 / 5.0)
    s4_ext = (fc_add["t_act_months"] - base_action) \
             if (math.isfinite(fc_add["t_act_months"]) and math.isfinite(base_action)) \
             else float("inf")

    def _cpm(c, ext):
        if ext is None or ext <= 0 or not math.isfinite(ext):
            return float("inf")
        return round(c / ext, 3)

    def _round_ext(x):
        return round(x, 2) if math.isfinite(x) else float("inf")

    rows = [
        {
            "strategy":            "1. Do nothing",
            "description":         "No upgrade; accept degraded service after trigger",
            "cost_kUSD":           cost["do_nothing"],
            "extended_months":     s1_ext,
            "cost_per_month_kUSD": _cpm(cost["do_nothing"], s1_ext),
        },
        {
            "strategy":            "2. Backhaul upgrade 100→200 Mbps",
            "description":         "Double backhaul capacity on all 5 BS links",
            "cost_kUSD":           cost["backhaul"],
            "extended_months":     _round_ext(s2_ext),
            "cost_per_month_kUSD": _cpm(cost["backhaul"], s2_ext),
        },
        {
            "strategy":            "3. Core router upgrade",
            "description":         "Upgrade CR-1/CR-2 processing (≈ +20% effective headroom)",
            "cost_kUSD":           cost["core"],
            "extended_months":     _round_ext(s3_ext),
            "cost_per_month_kUSD": _cpm(cost["core"], s3_ext),
        },
        {
            "strategy":            "4. Add one base station",
            "description":         "Split load across 6 sites instead of 5 (≈ +20% per-site)",
            "cost_kUSD":           cost["add_bs"],
            "extended_months":     _round_ext(s4_ext),
            "cost_per_month_kUSD": _cpm(cost["add_bs"], s4_ext),
        },
    ]

    df = pd.DataFrame(rows)

    # Ranking rules, in order of priority:
    #   (a) strategies that actually extend runway beat "do nothing" or
    #       strategies that do not extend (0 months)
    #   (b) among strategies that extend, lower cost_per_month_kUSD wins
    #   (c) if cost_per_month is inf (because the strategy pushes the trigger
    #       beyond the forecast horizon -> extended_months = inf), then
    #       rank by lowest absolute cost as a tie-breaker, since any of
    #       these are "good enough" for the horizon
    def _rank_key(row):
        ext = row["extended_months"]
        cpm = row["cost_per_month_kUSD"]
        # Bucket 0: real extension with finite CPM (best)
        # Bucket 1: extension pushed beyond horizon (tie-break by cost)
        # Bucket 2: zero or negative extension (worst)
        if math.isfinite(cpm) and ext > 0:
            return (0, cpm)
        if math.isfinite(ext) and ext > 0:
            return (0, cpm)
        if not math.isfinite(ext):   # ext == inf => beyond horizon
            return (1, row["cost_kUSD"])
        return (2, row["cost_kUSD"])  # ext <= 0

    keys = [_rank_key(r) for _, r in df.iterrows()]
    # Stable sort order; then assign dense ranks 1..N
    order = sorted(range(len(df)), key=lambda i: keys[i])
    ranks = [0] * len(df)
    for rank_pos, idx in enumerate(order, start=1):
        ranks[idx] = rank_pos
    df["rank"] = ranks
    return df


# -----------------------------------------------------------------------
# Phased upgrade recommendation (report §11)
# -----------------------------------------------------------------------

def upgrade_recommendation(scenario: dict) -> dict:
    """
    Generate structured upgrade recommendations for the report, including
    procurement order dates computed as (trigger month - lead time).

    Returns
    -------
    dict with keys:
        utilisation_summary : str
        erlang_summary      : str
        phased_plan         : list[dict]
        strategy_table      : pd.DataFrame
        full_text           : str
        t_plan_months, t_act_months, lead_time_months,
        site_upgrade_month, trunk_upgrade_month
    """
    fc_util  = forecast_utilisation(scenario)
    fc_erl   = forecast_erlang(scenario)
    fc_trunk = forecast_trunk_erlang(scenario)

    t_plan = fc_util["t_plan_months"]
    t_act  = fc_util["t_act_months"]
    lead   = fc_util["lead_time_months"]
    u_plan = fc_util["planning_trigger"]
    u_act  = fc_util["action_trigger"]

    # First month per-site voice upgrade needed
    site_fail  = fc_erl[fc_erl["upgrade_needed"]]
    site_month = int(site_fail["month"].iloc[0])            if not site_fail.empty else None
    site_N_new = int(site_fail["channels_required"].iloc[0]) if not site_fail.empty else None

    # First month trunk upgrade needed
    trunk_fail  = fc_trunk[fc_trunk["upgrade_needed"]]
    trunk_month = int(trunk_fail["month"].iloc[0])            if not trunk_fail.empty else None
    trunk_N_new = int(trunk_fail["channels_required"].iloc[0]) if not trunk_fail.empty else None

    def _order_month(trigger):
        if trigger is None or not math.isfinite(trigger):
            return None
        return max(0.0, round(trigger - lead, 2))

    phases = [
        {
            "phase":          "Phase 1 — Planning",
            "trigger_month":  t_plan,
            "order_month":    _order_month(t_plan),
            "trigger_metric": f"{u_plan*100:.0f}% link utilisation",
            "action":         "Begin capacity planning; initiate procurement for backhaul upgrades.",
        },
        {
            "phase":          "Phase 2 — Backhaul action",
            "trigger_month":  t_act,
            "order_month":    _order_month(t_act),
            "trigger_metric": f"{u_act*100:.0f}% link utilisation",
            "action":         "Deploy 100 → 200 Mbps backhaul link upgrade on all 5 BS sites.",
        },
    ]
    if trunk_month is not None:
        phases.append({
            "phase":          "Phase 3 — Trunk voice channels",
            "trigger_month":  float(trunk_month),
            "order_month":    _order_month(float(trunk_month)),
            "trigger_metric": "Trunk blocking > 2% KPI",
            "action":         f"Expand backhaul trunk voice circuits to {trunk_N_new}.",
        })
    if site_month is not None:
        phases.append({
            "phase":          "Phase 4 — Per-site voice channels",
            "trigger_month":  float(site_month),
            "order_month":    _order_month(float(site_month)),
            "trigger_metric": "Per-site blocking > 2% KPI",
            "action":         f"Expand per-site voice circuits from "
                              f"{fc_erl['n_baseline'].iloc[0]} to {site_N_new}.",
        })

    u0_pct = fc_util['table']['utilisation'].iloc[0] * 100
    op     = _order_month(t_plan)
    oa     = _order_month(t_act)

    def _fmt_month(x):
        if x is None or not (isinstance(x, (int, float)) and math.isfinite(float(x))):
            return "n/a (not reached in horizon)"
        return f"{x:.1f}"

    if math.isfinite(t_plan) and math.isfinite(t_act):
        trigger_line = (
            f"the 70% planning trigger fires at month {_fmt_month(t_plan)} "
            f"and the 90% action trigger at month {_fmt_month(t_act)}. "
            f"With a {lead}-month procurement lead time, orders must be placed by "
            f"months {_fmt_month(op)} and {_fmt_month(oa)} respectively."
        )
    else:
        trigger_line = (
            f"neither the 70% planning trigger nor the 90% action trigger is reached "
            f"within the {fc_util['horizon_months']}-month horizon "
            f"(t_plan = {_fmt_month(t_plan)}, t_act = {_fmt_month(t_act)}). "
            f"The network has sufficient headroom for the full forecast period."
        )

    util_summary = (
        f"Starting from {u0_pct:.1f}% utilisation on the worst link "
        f"({fc_util['worst_site']}) and growing at per-class CAGR "
        f"(tel {fc_util['cagr']['telemetry']*100:.0f}%/yr, "
        f"voice {fc_util['cagr']['voice']*100:.0f}%/yr, "
        f"video {fc_util['cagr']['video']*100:.0f}%/yr), "
        + trigger_line
    )

    if site_month is not None:
        erl_summary = (
            f"Per-site voice offered load exceeds the baseline "
            f"{fc_erl['n_baseline'].iloc[0]} circuits in month {site_month}, "
            f"requiring expansion to {site_N_new} circuits."
        )
    else:
        erl_summary = (
            f"Per-site voice capacity is sufficient across the full "
            f"{fc_util['horizon_months']}-month horizon."
        )

    strategies = strategy_comparison(scenario)
    best = strategies[strategies["rank"] == 1].iloc[0]
    if math.isfinite(best["cost_per_month_kUSD"]) and best["extended_months"] > 0:
        strat_note = (
            f"Of the {len(strategies)} strategies compared, '{best['strategy']}' offers the best "
            f"value at {best['cost_per_month_kUSD']} kUSD per extended month "
            f"({best['extended_months']} months of runway for {best['cost_kUSD']} kUSD)."
        )
    else:
        strat_note = (
            f"No upgrade strategy is required within the {fc_util['horizon_months']}-month "
            f"horizon because the 90% action trigger is not reached. The three upgrade "
            f"options remain on the shelf for reassessment at the next planning review."
        )

    full_text = f"{util_summary} {erl_summary} {strat_note}"

    return {
        "utilisation_summary": util_summary,
        "erlang_summary":      erl_summary,
        "phased_plan":         phases,
        "strategy_table":      strategies,
        "full_text":           full_text,
        "t_plan_months":       t_plan,
        "t_act_months":        t_act,
        "lead_time_months":    lead,
        "site_upgrade_month":  site_month,
        "trunk_upgrade_month": trunk_month,
    }


# -----------------------------------------------------------------------
# Dashboard entry point
# -----------------------------------------------------------------------

def run_forecasting(scenario: dict) -> dict:
    """
    Run full forecasting analysis. Called by dashboard.py.
    """
    return {
        "utilisation":    forecast_utilisation(scenario),
        "mbps_per_class": forecast_mbps_per_class(scenario),
        "erlang":         forecast_erlang(scenario),
        "trunk":          forecast_trunk_erlang(scenario),
        "strategies":     strategy_comparison(scenario),
        "recommendation": upgrade_recommendation(scenario),
    }


# -----------------------------------------------------------------------
# Self-test (spec §4.4)  -  t_plan must fire within 5 years (60 months)
# -----------------------------------------------------------------------

def test_t_plan_fires_within_5_years(scenario: dict) -> None:
    """Assertion required by the spec: planning trigger within 5 years."""
    fc = forecast_utilisation(scenario)
    assert fc["t_plan_months"] <= 60.0, (
        f"Planning trigger must fire within 5 years (60 months), "
        f"but t_plan_months = {fc['t_plan_months']}"
    )


# -----------------------------------------------------------------------
# Standalone demo
# -----------------------------------------------------------------------

if __name__ == "__main__":
    import os

    path = os.path.join(os.path.dirname(__file__), "..", "scenario.yaml")
    sc   = load_scenario(path)

    print("=" * 70)
    print("PER-CLASS Mbps FORECAST  (first 6 + last 6 months)")
    print("=" * 70)
    mbps = forecast_mbps_per_class(sc)
    print(pd.concat([mbps.head(6), mbps.tail(6)]).to_string(index=False))

    print("\n" + "=" * 70)
    print("UTILISATION FORECAST  (every 6 months)")
    print("=" * 70)
    fc = forecast_utilisation(sc)
    print(fc["table"].iloc[::6].to_string(index=False))
    print(f"\n  Worst site                     : {fc['worst_site']}")
    print(f"  Planning trigger (70%) month   : {fc['t_plan_months']}")
    print(f"  Action trigger   (90%) month   : {fc['t_act_months']}")
    print(f"  Lead time (months)             : {fc['lead_time_months']}")
    print(f"  → order by month (planning)    : {fc['order_plan_month']}")
    print(f"  → order by month (action)      : {fc['order_act_month']}")

    print("\n" + "=" * 70)
    print("VOICE ERLANG FORECAST  (every 6 months)")
    print("=" * 70)
    erl = forecast_erlang(sc)
    print(erl.iloc[::6].to_string(index=False))

    print("\n" + "=" * 70)
    print("TRUNK ERLANG FORECAST  (every 6 months)")
    print("=" * 70)
    trunk = forecast_trunk_erlang(sc)
    print(trunk.iloc[::6].to_string(index=False))

    print("\n" + "=" * 70)
    print("STRATEGY COMPARISON   (Report Table 3)")
    print("=" * 70)
    strat = strategy_comparison(sc)
    print(strat.to_string(index=False))

    print("\n" + "=" * 70)
    print("UPGRADE RECOMMENDATION")
    print("=" * 70)
    rec = upgrade_recommendation(sc)
    print(rec["full_text"])
    print("\nPhased plan:")
    for p in rec["phased_plan"]:
        t  = p["trigger_month"]
        om = p["order_month"]
        t_str  = f"{t:.1f}"  if isinstance(t, (int, float)) and math.isfinite(float(t))  else "n/a"
        om_str = f"{om:.1f}" if isinstance(om, (int, float)) and om is not None and math.isfinite(float(om)) else "n/a"
        print(f"  [{p['phase']}] trigger month {t_str} (order by {om_str}) — {p['action']}")

    # KPI self-test
    try:
        test_t_plan_fires_within_5_years(sc)
        print("\n  [OK] t_plan fires within 5-year horizon.")
    except AssertionError as e:
        print(f"\n  [FAIL] {e}")

    # ------------------------------------------------------------------
    # CSV export
    # ------------------------------------------------------------------
    out_dir = os.path.join(os.path.dirname(__file__), "..", "outputs")
    os.makedirs(out_dir, exist_ok=True)

    mbps.to_csv(os.path.join(out_dir, "forecasting_mbps_per_class.csv"),   index=False)
    fc["table"].to_csv(os.path.join(out_dir, "forecasting_utilisation_monthly.csv"), index=False)
    erl.to_csv(os.path.join(out_dir,  "forecasting_erlang_per_site.csv"), index=False)
    trunk.to_csv(os.path.join(out_dir, "forecasting_trunk_erlang.csv"),    index=False)
    strat.to_csv(os.path.join(out_dir, "forecasting_strategy_comparison.csv"), index=False)
    pd.DataFrame(rec["phased_plan"]).to_csv(
        os.path.join(out_dir, "forecasting_upgrade_plan.csv"), index=False
    )

    print("\nCSV files saved to outputs/:")
    for name in [
        "forecasting_mbps_per_class.csv",
        "forecasting_utilisation_monthly.csv",
        "forecasting_erlang_per_site.csv",
        "forecasting_trunk_erlang.csv",
        "forecasting_strategy_comparison.csv",
        "forecasting_upgrade_plan.csv",
    ]:
        print(f"  {name}")