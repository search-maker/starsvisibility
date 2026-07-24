#!/usr/bin/env python3
"""RH-10: complete stratified VROOM on/off validation (gate before the grid).

For a stratified matrix over solar depression x target altitude x relative
azimuth x AOD, run MYSTIC with mc_vroom on and off, each with independent seeds,
and test whether the two modes are statistically consistent. VROOM is authorized
for the production grid ONLY if there is no systematic, direction-dependent, or
large bias across the supported domain.

Per cell we report: pooled means and sigmas (from independent seeds), absolute
and relative difference, combined MC uncertainty, z-score, runtime ratio.
Aggregate: max |z|, mean/median relative difference, per-direction mean bias,
and a boolean vroomAuthorizedForGrid.

Writes reports/vroom-validation.{json,md}. Real libRadtran; runtime is minutes.
"""
import argparse
import json
import math
import statistics
from pathlib import Path
from lrt_common import ROOT
import hardening_common as H

REPORTS = ROOT / "reports"

# Photon budget per depression for the VROOM comparison. The DIFFERENCE between
# modes is what matters; budgets are chosen so per-run sigma is small enough to
# detect a ~few-% bias with 3 independent seeds.
PHOTONS = {0: 2_000_000, 4: 4_000_000, 8: 8_000_000, 10: 12_000_000}
SEEDS = (101, 202, 303)


def pooled(runs):
    """Mean and standard error of the mean across independent-seed runs."""
    vals = [r["radiance"] for r in runs]
    n = len(vals)
    mean = statistics.mean(vals)
    if n > 1:
        sem = statistics.stdev(vals) / math.sqrt(n)
    else:
        sem = runs[0].get("std") or 0.0
    return mean, sem


def cell(dep, alt, raz, aod):
    ph = PHOTONS[dep]
    on = [H.run_radiance(dep, alt, raz, aod, photons=ph, seed=s, vroom="on")
          for s in SEEDS]
    off = [H.run_radiance(dep, alt, raz, aod, photons=ph, seed=s, vroom="off")
           for s in SEEDS]
    on_ok = [r for r in on if r["status"] == "ok"]
    off_ok = [r for r in off if r["status"] == "ok"]
    if len(on_ok) < 2 or len(off_ok) < 2:
        return {"dep": dep, "alt": alt, "raz": raz, "aod": aod,
                "status": "insufficient-ok-runs"}
    m_on, s_on = pooled(on_ok)
    m_off, s_off = pooled(off_ok)
    comb = math.sqrt(s_on ** 2 + s_off ** 2)
    z = (m_on - m_off) / comb if comb > 0 else float("nan")
    rel = (m_on - m_off) / m_off if m_off else None
    rt_on = statistics.mean([r["runtime"] for r in on_ok])
    rt_off = statistics.mean([r["runtime"] for r in off_ok])
    return {
        "dep": dep, "alt": alt, "raz": raz, "aod": aod, "photons": ph,
        "direction": {0: "sunward", 90: "cross", 180: "anti"}.get(raz, str(raz)),
        "meanOn": m_on, "semOn": s_on, "meanOff": m_off, "semOff": s_off,
        "absDiff": m_on - m_off, "relDiff": rel, "combinedSigma": comb,
        "zScore": z, "runtimeRatioOnOverOff": rt_on / rt_off if rt_off else None,
        "nSeedsOn": len(on_ok), "nSeedsOff": len(off_ok), "status": "ok"}


def matrix(deps):
    cells = []
    for dep in deps:
        for aod in (0.05, 0.30):
            for alt in (10, 30):
                for raz in (0, 90, 180):
                    cells.append(cell(dep, alt, raz, aod))
            cells.append(cell(dep, 90, 0, aod))   # zenith: azimuth-degenerate
    return cells


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deps", default="0,4,8",
                    help="comma depressions (default 0,4,8; add 10 for the "
                    "provisional extension)")
    args = ap.parse_args()
    deps = [int(x) for x in args.deps.split(",")]
    cells = matrix(deps)
    ok = [c for c in cells if c["status"] == "ok"]
    zs = [abs(c["zScore"]) for c in ok if c["zScore"] == c["zScore"]]
    rels = [c["relDiff"] for c in ok if c["relDiff"] is not None]
    dir_bias = {}
    for d in ("sunward", "cross", "anti"):
        v = [c["relDiff"] for c in ok if c["direction"] == d and c["relDiff"] is not None]
        if v:
            dir_bias[d] = statistics.mean(v)

    max_z = max(zs) if zs else None
    mean_rel = statistics.mean(rels) if rels else None
    median_rel = statistics.median(rels) if rels else None
    # fraction of cells with |z|>3 (would indicate systematic disagreement)
    frac_significant = (sum(1 for z in zs if z > 3) / len(zs)) if zs else None
    # direction-dependent bias trend: spread of per-direction mean rel diffs
    dir_spread = (max(dir_bias.values()) - min(dir_bias.values())
                  if len(dir_bias) >= 2 else None)

    authorized = bool(
        zs and max_z < 4.0
        and mean_rel is not None and abs(mean_rel) < 0.03
        and frac_significant is not None and frac_significant <= 0.05
        and (dir_spread is None or abs(dir_spread) < 0.03))

    result = {
        "depressions": deps, "seeds": list(SEEDS), "photonsByDepression": PHOTONS,
        "cellCount": len(cells), "okCellCount": len(ok),
        "maxAbsZ": max_z, "meanRelDiff": mean_rel, "medianRelDiff": median_rel,
        "fractionCellsZgt3": frac_significant,
        "directionMeanRelDiff": dir_bias, "directionBiasSpread": dir_spread,
        "vroomAuthorizedForGrid": authorized,
        "criteria": "authorized iff max|z|<4 AND |mean rel diff|<3% AND "
        "<=5% of cells with |z|>3 AND direction-bias spread<3%",
        "cells": cells,
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "vroom-validation.json").write_text(json.dumps(result, indent=1))

    L = ["# VROOM on/off validation (RH-10, gate before the grid)", "",
         f"Depressions {deps}, seeds {list(SEEDS)}, "
         f"{len(ok)}/{len(cells)} cells ok.", "",
         f"- max |z| = {max_z}", f"- mean rel diff = {mean_rel}",
         f"- median rel diff = {median_rel}",
         f"- fraction of cells with |z|>3 = {frac_significant}",
         f"- direction mean rel diff = {dir_bias}",
         f"- direction bias spread = {dir_spread}", "",
         f"## VROOM authorized for grid: **{authorized}**",
         f"Criteria: {result['criteria']}", "",
         "| dep | alt | raz | dir | AOD | meanOn | meanOff | relDiff | z | rt on/off |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for c in ok:
        L.append(f"| {c['dep']} | {c['alt']} | {c['raz']} | {c['direction']} | "
                 f"{c['aod']} | {c['meanOn']:.4g} | {c['meanOff']:.4g} | "
                 f"{c['relDiff']:+.3f} | {c['zScore']:+.2f} | "
                 f"{c['runtimeRatioOnOverOff']:.2f} |")
    (REPORTS / "vroom-validation.md").write_text("\n".join(L) + "\n")
    print(json.dumps({"okCells": len(ok), "maxAbsZ": max_z,
                      "meanRelDiff": mean_rel, "fractionZgt3": frac_significant,
                      "vroomAuthorizedForGrid": authorized}, indent=1))


if __name__ == "__main__":
    main()
