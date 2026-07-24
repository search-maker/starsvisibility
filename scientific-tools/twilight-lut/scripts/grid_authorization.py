#!/usr/bin/env python3
"""Authoritative go/no-go for starting the expanded LUT grid.

The expanded grid must not start until every pre-grid gate passes (user
directive). This script aggregates the evidence files and returns a single
`authorized` boolean with per-gate reasons. run_grid.py refuses to run unless
this reports authorized (or an explicit --force override is given AND recorded).
"""
import json
from pathlib import Path

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def _load(name):
    p = REPORTS / name
    return json.loads(p.read_text()) if p.exists() else None


def evaluate():
    gates = []

    solver = _load("solver-validation.json")
    gates.append(("solver-validation present and pass",
                  bool(solver and solver.get("pass")),
                  solver.get("verdict") if solver else "missing solver-validation.json"))

    vroom = _load("vroom-validation.json")
    gates.append(("VROOM authorized for grid (RH-10)",
                  bool(vroom and vroom.get("vroomAuthorizedForGrid")),
                  (f"maxAbsZ={vroom.get('maxAbsZ')}, meanRelDiff="
                   f"{vroom.get('meanRelDiff')}, dirSpread="
                   f"{vroom.get('directionBiasSpread')}")
                  if vroom else "missing vroom-validation.json"))

    feas = _load("FEASIBILITY_REPORT.json")
    feas_gates = (feas or {}).get("statistics", {}).get("gates", [])
    all_feas = bool(feas_gates) and all(g["passed"] for g in feas_gates)
    gates.append(("all feasibility gates pass", all_feas,
                  f"{sum(g['passed'] for g in feas_gates)}/{len(feas_gates)} gates"
                  if feas_gates else "missing FEASIBILITY_REPORT.json"))

    authorized = all(g[1] for g in gates)
    return {"authorized": authorized,
            "gates": [{"gate": g, "passed": p, "detail": d} for g, p, d in gates]}


def main():
    result = evaluate()
    print(json.dumps(result, indent=1))
    (REPORTS / "grid-authorization.json").write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
