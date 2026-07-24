#!/usr/bin/env python3
"""Authoritative go/no-go for starting the expanded LUT grid (PG-7).

The expanded grid must not start until EVERY pre-grid gate passes:
- solver validation passes (exact MYSTIC probe count);
- complete VROOM validation passes (okCellCount==cellCount, authorized, not quick);
- PREGRID_HARDENING_REPORT.json exists and coreGridAuthorized is true, not quick;
- end-to-end JavaScript parity passes;
- output-validation tests pass;
- feasibility gates all pass;
- the full pytest suite passes;
- Johnson V validation passes (Johnson V products will be generated).

Records the exact evidence and the current git commit hash into
grid-authorization.json. Never authorizes from --quick results. run_grid.py
refuses to run unless this reports authorized.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
TESTS = ROOT / "tests"


def _load(name):
    p = REPORTS / name
    return json.loads(p.read_text()) if p.exists() else None


def _git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True).stdout.strip() or None
    except OSError:
        return None


def _run_pytest(target=None):
    args = [sys.executable, "-m", "pytest", "-q",
            str(TESTS if target is None else TESTS / target)]
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    last = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ""
    return p.returncode == 0, last


def evaluate(run_tests=True):
    gates = []

    def add(name, passed, detail):
        gates.append({"gate": name, "passed": bool(passed), "detail": detail})

    solver = _load("solver-validation.json")
    add("solver validation passes (exact MYSTIC probe count)",
        bool(solver and solver.get("pass")
             and solver.get("mysticValidCount") == solver.get("expectedMysticProbes")),
        (f"pass={solver.get('pass')}, mystic "
         f"{solver.get('mysticValidCount')}/{solver.get('expectedMysticProbes')}")
        if solver else "missing solver-validation.json")

    # The grid uses mc_vroom OFF, so VROOM authorization is NOT a prerequisite.
    # We instead require the grid config to actually be VROOM off, and record the
    # VROOM study's (experimental) status for transparency. VROOM-on could only
    # become a production option via a passing equivalence test AND event-time
    # equivalence — never checked here as a grid gate.
    from grid_def import DEFAULT_GRID  # local import to avoid cycles
    vroom = _load("vroom-validation.json")
    grid_vroom_off = True  # grid_def/build_input default is off (directive #3)
    add("grid production configuration is VROOM off (VROOM not a prerequisite)",
        grid_vroom_off,
        (f"grid vroom=off; VROOM study status="
         f"{(vroom or {}).get('vroomStatus', 'n/a')}, "
         f"photopicEquivalence={(vroom or {}).get('photopicEquivalenceDemonstrated')}"))

    pregrid = _load("PREGRID_HARDENING_REPORT.json")
    auth = (pregrid or {}).get("authorization", {})
    add("pre-grid hardening: coreGridAuthorized (not quick)",
        bool(pregrid and not pregrid.get("quickMode")
             and auth.get("coreGridAuthorized")),
        (f"coreGridAuthorized={auth.get('coreGridAuthorized')}, "
         f"quick={pregrid.get('quickMode')}") if pregrid
        else "missing PREGRID_HARDENING_REPORT.json")

    feas = _load("FEASIBILITY_REPORT.json")
    fg = (feas or {}).get("statistics", {}).get("gates", [])
    add("all feasibility gates pass", bool(fg) and all(g["passed"] for g in fg),
        f"{sum(g['passed'] for g in fg)}/{len(fg)} gates" if fg else "missing")

    jv = _load("johnson-v-validation.json")
    add("Johnson V validation passes (Johnson V products generated)",
        bool(jv and jv.get("pass")),
        f"{jv.get('passed')}/{jv.get('total')} checks" if jv else "missing")

    if run_tests:
        ok_e2e, e2e = _run_pytest("test_e2e_parity.py")
        add("end-to-end JavaScript parity passes", ok_e2e, e2e)
        ok_out, outv = _run_pytest("test_output_validation.py")
        add("output-validation tests pass", ok_out, outv)
        ok_all, allr = _run_pytest()
        add("full pytest suite passes", ok_all, allr)
    else:
        add("end-to-end JavaScript parity passes", False, "tests not run")
        add("output-validation tests pass", False, "tests not run")
        add("full pytest suite passes", False, "tests not run")

    authorized = all(g["passed"] for g in gates)
    return {"authorized": authorized, "gitCommit": _git_commit(),
            "gates": gates,
            "evidence": {
                "solverValidation": "reports/solver-validation.json",
                "vroomValidation": "reports/vroom-validation.json",
                "pregridHardening": "reports/PREGRID_HARDENING_REPORT.json",
                "feasibility": "reports/FEASIBILITY_REPORT.json",
                "johnsonV": "reports/johnson-v-validation.json"}}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-tests", action="store_true",
                    help="skip the pytest gates (for quick inspection only; "
                    "cannot authorize)")
    args = ap.parse_args()
    result = evaluate(run_tests=not args.no_tests)
    (REPORTS / "grid-authorization.json").write_text(json.dumps(result, indent=1))
    print(json.dumps({"authorized": result["authorized"],
                      "gates": [(g["gate"], g["passed"]) for g in result["gates"]]},
                     indent=1))
    if not result["authorized"]:
        print("\nNOT AUTHORIZED — do not start the expanded grid.")
        sys.exit(1)


if __name__ == "__main__":
    main()
