"""
pipeline.py — TELE 527 Group 1: District Telehealth & Emergency Network
Master Integration Pipeline

Runs every stage end-to-end in the correct dependency order:
  1. Validate scenario.yaml
  2. Build network topology
  3. Traffic & teletraffic analysis
  4. Wireless propagation & coverage
  5. Routing (Dijkstra) & failure injection
  6. Signalling (call setup delay)
  7. Backhaul link budget
  8. QoS KPI verification
  9. Stress test (load sweep)
 10. Forecasting (5-year utilisation + upgrade triggers)
 11. Launch Streamlit dashboard (optional)

Usage:
    python pipeline.py                          # run all stages, skip dashboard
    python pipeline.py --dashboard              # run all stages + launch dashboard
    python pipeline.py --stage routing          # run a single named stage only
    python pipeline.py --skip wireless backhaul # skip specific stages
    python pipeline.py --strict                 # abort on first stage failure
"""

import argparse
import importlib
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# Colour helpers (works on Windows via ANSI if terminal supports it)
# ─────────────────────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
DIM    = "\033[2m"

def ok(msg):   print(f"  {GREEN}✔{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET}  {msg}")
def fail(msg): print(f"  {RED}✘{RESET}  {msg}")
def info(msg): print(f"  {CYAN}→{RESET}  {msg}")
def header(msg):
    width = 70
    print(f"\n{BOLD}{CYAN}{'─' * width}{RESET}")
    print(f"{BOLD}{CYAN}  {msg}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * width}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# Stage registry — order matters; each entry is:
#   name          : short identifier used in --stage / --skip flags
#   module        : dotted import path inside src/  (None = subprocess only)
#   run_fn        : function name inside the module (called as run_fn(config))
#   subprocess_cmd: fallback command list if module import fails
#   objective     : project manual objective IDs this stage satisfies
#   required_inputs : list of keys that must exist in the shared results{} dict
#   outputs_key   : key this stage writes back into results{}
# ─────────────────────────────────────────────────────────────────────────────
STAGES = [
    {
        "name": "scenario",
        "label": "Validate scenario.yaml",
        "module": None,
        "subprocess_cmd": None,
        "objective": "O-01",
        "required_inputs": [],
        "outputs_key": "config",
    },
    {
        "name": "topology",
        "label": "Build network topology",
        "module": "src.topology",
        "run_fn": "run",
        "subprocess_cmd": ["python", "-m", "src.topology"],
        "objective": "O-02",
        "required_inputs": ["config"],
        "outputs_key": "topology",
    },
    {
        "name": "traffic",
        "label": "Traffic & teletraffic analysis (Erlang B)",
        "module": "src.traffic",
        "run_fn": "run",
        "subprocess_cmd": ["python", "-m", "src.traffic"],
        "objective": "O-04 / O-05",
        "required_inputs": ["config"],
        "outputs_key": "traffic",
    },
    {
        "name": "teletraffic",
        "label": "Teletraffic KPIs (delay, GoS, stress sweep)",
        "module": "src.teletraffic",
        "run_fn": "run",
        "subprocess_cmd": ["python", "-m", "src.teletraffic"],
        "objective": "O-05 / O-07",
        "required_inputs": ["config", "traffic"],
        "outputs_key": "teletraffic",
    },
    {
        "name": "wireless",
        "label": "Wireless propagation & coverage (COST 231-Hata)",
        "module": "src.wireless",
        "run_fn": "run",
        "subprocess_cmd": ["python", "-m", "src.wireless"],
        "objective": "O-08 / O-09",
        "required_inputs": ["config"],
        "outputs_key": "wireless",
    },
    {
        "name": "routing",
        "label": "Routing (Dijkstra) & CR-1 failure injection",
        "module": "src.routing",
        "run_fn": "run",
        "subprocess_cmd": ["python", "-m", "src.routing"],
        "objective": "O-10 / O-12",
        "required_inputs": ["config", "topology"],
        "outputs_key": "routing",
    },
    {
        "name": "signalling",
        "label": "Signalling — SS7 call setup delay model",
        "module": "src.signalling",
        "run_fn": "run",
        "subprocess_cmd": ["python", "-m", "src.signalling"],
        "objective": "O-11",
        "required_inputs": ["config", "routing"],
        "outputs_key": "signalling",
    },
    {
        "name": "backhaul",
        "label": "Backhaul link budget (fade margin, rain attenuation)",
        "module": "src.backhaul",
        "run_fn": "run",
        "subprocess_cmd": ["python", "-m", "src.backhaul"],
        "objective": "O-13 / O-14",
        "required_inputs": ["config"],
        "outputs_key": "backhaul",
    },
    {
        "name": "qos",
        "label": "QoS KPI verification (telemetry P95, voice blocking, video P95)",
        "module": "src.qos",
        "run_fn": "run",
        "subprocess_cmd": ["python", "-m", "src.qos"],
        "objective": "O-15",
        "required_inputs": ["config", "traffic", "teletraffic", "routing"],
        "outputs_key": "qos",
    },
    {
        "name": "stress",
        "label": "Stress test — breaking point load sweep (α = 1.0 → 5.0)",
        "module": "src.stress_test",
        "run_fn": "run",
        "subprocess_cmd": ["python", "-m", "src.stress_test"],
        "objective": "O-07 / O-12",
        "required_inputs": ["config", "qos"],
        "outputs_key": "stress",
    },
    {
        "name": "forecasting",
        "label": "5-year utilisation forecast & upgrade triggers",
        "module": "src.forecasting",
        "run_fn": "run",
        "subprocess_cmd": ["python", "-m", "src.forecasting"],
        "objective": "O-16",
        "required_inputs": ["config", "traffic"],
        "outputs_key": "forecasting",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# KPI targets — used in the post-run compliance check
# ─────────────────────────────────────────────────────────────────────────────
KPI_TARGETS = {
    "telemetry_p95_ms":    {"target": 50,   "op": "le", "label": "Telemetry P95 latency ≤ 50 ms"},
    "voice_blocking_pct":  {"target": 2.0,  "op": "le", "label": "Voice Erlang B blocking ≤ 2 %"},
    "video_p95_ms":        {"target": 150,  "op": "le", "label": "Video P95 latency ≤ 150 ms"},
    "min_fade_margin_db":  {"target": 20,   "op": "ge", "label": "All backhaul links fade margin ≥ 20 dB"},
}

# ─────────────────────────────────────────────────────────────────────────────
# Required output files produced by the full pipeline
# ─────────────────────────────────────────────────────────────────────────────
REQUIRED_OUTPUTS = [
    "outputs/traffic_matrix.csv",
    "outputs/traffic_offered_load.csv",
    "outputs/teletraffic_delay_kpis.csv",
    "outputs/teletraffic_erlang_curves.csv",
    "outputs/teletraffic_stress_sweep.csv",
    "outputs/forecasting_utilisation_annual.csv",
    "outputs/forecasting_upgrade_plan.csv",
    "figures/topology.png",
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_scenario(scenario_path: str = "scenario.yaml") -> dict:
    """Load and minimally validate scenario.yaml."""
    try:
        import yaml
    except ImportError:
        fail("PyYAML is not installed. Run: pip install pyyaml")
        sys.exit(1)

    path = Path(scenario_path)
    if not path.exists():
        fail(f"scenario.yaml not found at: {path.resolve()}")
        sys.exit(1)

    with open(path) as f:
        config = yaml.safe_load(f)

    required_keys = ["sites", "links", "traffic_classes"]
    missing = [k for k in required_keys if k not in config]
    if missing:
        fail(f"scenario.yaml is missing required keys: {missing}")
        sys.exit(1)

    ok(f"scenario.yaml loaded — {len(config.get('sites', []))} sites, "
       f"{len(config.get('links', []))} links, "
       f"{len(config.get('traffic_classes', []))} traffic classes")
    return config


def try_module_run(stage: dict, results: dict) -> bool:
    """
    Try to import the module and call its run(config) function.
    Returns True on success, False on failure.
    """
    module_path = stage.get("module")
    run_fn_name = stage.get("run_fn", "run")

    if not module_path:
        return False

    try:
        mod = importlib.import_module(module_path)
        run_fn = getattr(mod, run_fn_name, None)
        if run_fn is None:
            warn(f"Module {module_path} has no '{run_fn_name}()' function — trying subprocess fallback")
            return False
        result = run_fn(results.get("config", {}))
        if result is not None:
            results[stage["outputs_key"]] = result
        return True
    except ImportError as e:
        warn(f"Could not import {module_path}: {e} — trying subprocess fallback")
        return False
    except Exception as e:
        fail(f"Module {module_path} raised an exception:")
        traceback.print_exc()
        return False


def try_subprocess_run(stage: dict) -> bool:
    """
    Fall back to running the stage as a subprocess.
    Returns True on success (exit code 0), False otherwise.
    """
    cmd = stage.get("subprocess_cmd")
    if not cmd:
        return False
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        fail(f"Command not found: {' '.join(cmd)}")
        return False


def check_outputs() -> tuple[int, int]:
    """Check that all required output files exist. Returns (found, total)."""
    found = 0
    for path_str in REQUIRED_OUTPUTS:
        p = Path(path_str)
        if p.exists() and p.stat().st_size > 0:
            ok(f"{path_str}")
            found += 1
        else:
            warn(f"Missing or empty: {path_str}")
    return found, len(REQUIRED_OUTPUTS)


def check_kpis(results: dict) -> dict:
    """
    Extract KPI values from results dict and evaluate against targets.
    Returns a dict of {kpi_key: {"value": v, "passed": bool}}.
    """
    kpi_results = {}

    # Try to pull values from the qos results sub-dict
    qos = results.get("qos", {}) or {}
    backhaul = results.get("backhaul", {}) or {}

    kpi_values = {
        "telemetry_p95_ms":   qos.get("telemetry_p95_ms"),
        "voice_blocking_pct": qos.get("voice_blocking_pct"),
        "video_p95_ms":       qos.get("video_p95_ms"),
        "min_fade_margin_db": backhaul.get("min_fade_margin_db"),
    }

    # Also try to read from CSV if module didn't populate results dict
    try:
        import csv
        kpi_csv = Path("outputs/teletraffic_delay_kpis.csv")
        if kpi_csv.exists() and kpi_values.get("telemetry_p95_ms") is None:
            with open(kpi_csv) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("class") == "telemetry":
                        kpi_values["telemetry_p95_ms"] = float(row.get("p95_ms", 0))
                    if row.get("class") == "video":
                        kpi_values["video_p95_ms"] = float(row.get("p95_ms", 0))
    except Exception:
        pass

    for key, target_spec in KPI_TARGETS.items():
        value = kpi_values.get(key)
        if value is None:
            kpi_results[key] = {"value": None, "passed": None, "label": target_spec["label"]}
            continue
        op = target_spec["op"]
        target = target_spec["target"]
        passed = (value <= target) if op == "le" else (value >= target)
        kpi_results[key] = {"value": value, "passed": passed, "label": target_spec["label"]}

    return kpi_results


def print_kpi_table(kpi_results: dict):
    """Print a formatted KPI compliance table."""
    header("KPI Compliance Report")
    col_w = [42, 12, 8, 8]
    divider = "  +" + "+".join("-" * (w + 2) for w in col_w) + "+"
    row_fmt = "  | {:<42} | {:>12} | {:>8} | {:>8} |"

    print(divider)
    print(row_fmt.format("KPI", "Value", "Target", "Status"))
    print(divider)

    all_pass = True
    any_data = False

    for key, kpi in kpi_results.items():
        label = kpi["label"]
        value = kpi["value"]
        passed = kpi["passed"]
        target = KPI_TARGETS[key]["target"]
        op_sym = "≤" if KPI_TARGETS[key]["op"] == "le" else "≥"

        if value is None:
            val_str = "N/A"
            status_str = f"{YELLOW}SKIP{RESET}"
        else:
            any_data = True
            val_str = f"{value:.1f}"
            if passed:
                status_str = f"{GREEN}PASS{RESET}"
            else:
                status_str = f"{RED}FAIL{RESET}"
                all_pass = False

        print(row_fmt.format(label, val_str, f"{op_sym}{target}", status_str))

    print(divider)

    if any_data:
        if all_pass:
            print(f"\n  {GREEN}{BOLD}All measured KPIs PASSED.{RESET}")
        else:
            print(f"\n  {RED}{BOLD}One or more KPIs FAILED — review outputs above.{RESET}")
    else:
        print(f"\n  {YELLOW}No KPI values were returned — modules may not have populated results dict.{RESET}")
        print(f"  {DIM}Run check_kpis.py separately after all CSVs are generated.{RESET}")


def print_summary_table(stage_results: list):
    """Print a final stage-by-stage summary."""
    header("Pipeline Run Summary")
    for entry in stage_results:
        icon = GREEN + "✔" + RESET if entry["passed"] else RED + "✘" + RESET
        skipped = DIM + " [skipped]" + RESET if entry["skipped"] else ""
        elapsed = f"{entry['elapsed']:.1f}s"
        print(f"  {icon}  {entry['label']:<52} {DIM}{elapsed}{RESET}{skipped}")


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline runner
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(
    scenario_path: str = "scenario.yaml",
    skip_stages: list = None,
    only_stage: Optional[str] = None,
    strict: bool = False,
    launch_dashboard: bool = False,
):
    skip_stages = skip_stages or []
    results = {}
    stage_results = []
    overall_pass = True

    # ── Banner ────────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{CYAN}{'═' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  TELE 527 — Group 1: District Telehealth & Emergency Network{RESET}")
    print(f"{BOLD}{CYAN}  Master Integration Pipeline{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 70}{RESET}\n")

    # ── Stage 0: Validate scenario.yaml ──────────────────────────────────────
    if only_stage is None or only_stage == "scenario":
        header("Stage 0 / scenario  ·  O-01  ·  Validate scenario.yaml")
        t0 = time.time()
        config = load_scenario(scenario_path)
        results["config"] = config
        elapsed = time.time() - t0
        stage_results.append({"label": "Validate scenario.yaml", "passed": True,
                               "skipped": False, "elapsed": elapsed})

    # ── Stages 1–N ────────────────────────────────────────────────────────────
    for i, stage in enumerate(STAGES, start=1):
        name = stage["name"]

        # Apply filters
        if only_stage and name != only_stage:
            continue
        if name in skip_stages:
            warn(f"Skipping stage: {name}")
            stage_results.append({"label": stage["label"], "passed": True,
                                   "skipped": True, "elapsed": 0})
            continue
        if name == "scenario":
            continue  # already handled above

        header(f"Stage {i} / {name}  ·  {stage['objective']}  ·  {stage['label']}")

        # Check required inputs are present
        missing_inputs = [k for k in stage["required_inputs"] if k not in results]
        if missing_inputs:
            warn(f"Required inputs not yet available: {missing_inputs} — attempting anyway")

        t0 = time.time()
        passed = False

        # Try module import first, fall back to subprocess
        if stage.get("module"):
            passed = try_module_run(stage, results)
            if passed:
                ok(f"Module {stage['module']} completed successfully")
            else:
                info("Trying subprocess fallback …")
                passed = try_subprocess_run(stage)
                if passed:
                    ok(f"Subprocess {' '.join(stage.get('subprocess_cmd', []))} completed")
                else:
                    fail(f"Stage '{name}' failed (both module and subprocess)")
        elif stage.get("subprocess_cmd"):
            passed = try_subprocess_run(stage)

        elapsed = time.time() - t0
        stage_results.append({"label": stage["label"], "passed": passed,
                               "skipped": False, "elapsed": elapsed})

        if not passed:
            overall_pass = False
            if strict:
                fail("--strict mode: aborting on first failure.")
                break

    # ── Output file check ─────────────────────────────────────────────────────
    if only_stage is None:
        header("Output File Check")
        found, total = check_outputs()
        if found < total:
            warn(f"{found}/{total} output files present — some stages may not have run yet")
        else:
            ok(f"All {total} required output files present")

    # ── KPI compliance ────────────────────────────────────────────────────────
    if only_stage is None:
        kpi_results = check_kpis(results)
        print_kpi_table(kpi_results)

    # ── Summary table ─────────────────────────────────────────────────────────
    print_summary_table(stage_results)

    # ── Dashboard (optional) ──────────────────────────────────────────────────
    if launch_dashboard:
        header("Launching Streamlit Dashboard")
        info("Running: streamlit run src/dashboard.py")
        info("Open http://localhost:8501 in your browser")
        info("Press Ctrl+C to stop the dashboard\n")
        try:
            subprocess.run(["streamlit", "run", "src/dashboard.py"])
        except KeyboardInterrupt:
            print("\n")
            ok("Dashboard stopped.")
        except FileNotFoundError:
            fail("streamlit not found — run: pip install streamlit")

    # ── Exit code ─────────────────────────────────────────────────────────────
    if overall_pass:
        print(f"\n{GREEN}{BOLD}Pipeline completed successfully.{RESET}\n")
        return 0
    else:
        print(f"\n{RED}{BOLD}Pipeline completed with errors — review the summary above.{RESET}\n")
        return 1


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="TELE 527 Group 1 — Master Integration Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline.py                        Run all stages
  python pipeline.py --dashboard            Run all stages then open dashboard
  python pipeline.py --stage routing        Run only the routing stage
  python pipeline.py --skip wireless stress Run all except wireless and stress
  python pipeline.py --strict               Abort on first failure
  python pipeline.py --scenario path/to/scenario.yaml
        """
    )
    parser.add_argument(
        "--scenario", default="scenario.yaml",
        help="Path to scenario YAML file (default: scenario.yaml)"
    )
    parser.add_argument(
        "--stage", default=None,
        choices=[s["name"] for s in STAGES] + ["scenario"],
        help="Run only a single named stage"
    )
    parser.add_argument(
        "--skip", nargs="+", default=[],
        metavar="STAGE",
        help="Stage names to skip"
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Abort the pipeline on the first stage failure"
    )
    parser.add_argument(
        "--no-dashboard", action="store_true",
        help="Skip launching the Streamlit dashboard at the end"
    )

    args = parser.parse_args()
    exit_code = run_pipeline(
        scenario_path=args.scenario,
        skip_stages=args.skip,
        only_stage=args.stage,
        strict=args.strict,
        launch_dashboard=not args.no_dashboard,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()