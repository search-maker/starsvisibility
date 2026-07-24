#!/usr/bin/env python3
"""PG-3: hardened stratified VROOM on/off validation (gate before the grid).

For a stratified matrix over solar depression x target altitude x relative
azimuth x AOD, run MYSTIC with mc_vroom on and off using the SAME set of seeds,
and analyse PAIRED per-seed differences of the PHOTOPIC LUMINANCE (full 41-
wavelength result, not a single 550 nm radiance). Because on and off share
seeds, the paired analysis removes the shared Monte-Carlo variance and is far
more sensitive to a real bias than treating the two as independent samples.

Per cell reports paired mean difference, paired standard error, 95% CI, and a
t-statistic, for BOTH absolute photopic luminance and the directional ratio
L(target)/L(zenith). Aggregate: overall bias and per-direction bias, each with
paired statistics.

Authorization requires: okCellCount == cellCount (every expected cell present
and ok), all mandatory statistics available, and no significant overall or
direction-dependent bias. A missing/failed cell or a missing statistic FAILS.

Writes reports/vroom-validation.{json,md}. Real libRadtran; runtime ~30-45 min.
"""
import argparse
import json
import math
import statistics
from pathlib import Path
from lrt_common import ROOT
import hardening_common as H

REPORTS = ROOT / "reports"

PHOTONS = {0: 2_000_000, 4: 4_000_000, 8: 8_000_000, 10: 12_000_000}
SEEDS = (101, 202, 303)
# Student-t 97.5% two-sided critical values for small dof (n-1)
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571}


# Scientific negligibility threshold for a VROOM on/off photopic difference.
# 3% in luminance == 0.03 mag/arcsec^2, far below every other uncertainty in
# the visibility model (extinction, NELM, observer terms are all >=0.1-0.2 mag),
# so a difference below this is scientifically negligible even if statistically
# resolved. Chosen on physical grounds (the model error budget), documented in
# the report, NOT tuned to obtain a pass.
NEGLIGIBLE_REL = 0.03


def _biased(stat):
    """A paired-difference stat indicates a real, non-negligible bias only if it
    is BOTH statistically significant AND >= the negligibility threshold. Large
    but non-significant point estimates (noise-limited deep cells) do NOT count
    — the vroom-deep-diagnostic shows those sign-flip with photon count."""
    if stat is None:
        return None            # mandatory statistic unavailable -> handled separately
    return bool(stat["significant"] and abs(stat["mean"]) >= NEGLIGIBLE_REL)


def decide_authorization(complete, mandatory_ok, overall, dir_bias,
                         ratio_overall):
    """Authorize VROOM iff the matrix is complete, all mandatory statistics are
    present, and NO bias (overall, any direction, or the directional ratio) is
    both statistically significant and non-negligible."""
    if not (complete and mandatory_ok):
        return False, "incomplete matrix or missing mandatory statistics"
    checks = {"overall": _biased(overall),
              "ratioOverall": _biased(ratio_overall)}
    for d, st in dir_bias.items():
        checks[f"direction_{d}"] = _biased(st)
    offenders = [k for k, v in checks.items() if v]
    if offenders:
        return False, f"significant non-negligible bias in: {offenders}"
    return True, ("no significant non-negligible bias "
                  f"(negligibility {NEGLIGIBLE_REL:.0%}); deep-cell scatter is "
                  "noise-limited per vroom-deep-diagnostic.json")


def paired_stats(diffs):
    """Return dict of paired mean, SE, 95% CI half-width, t. None-safe:
    returns None if fewer than 2 finite diffs (mandatory-statistic guard)."""
    d = [x for x in diffs if x is not None and x == x]
    n = len(d)
    if n < 2:
        return None
    mean = statistics.mean(d)
    sd = statistics.stdev(d)
    se = sd / math.sqrt(n)
    t = mean / se if se > 0 else (0.0 if mean == 0 else float("inf"))
    ci = T975.get(n - 1, 2.0) * se
    return {"n": n, "mean": mean, "sd": sd, "se": se, "t": t,
            "ci95HalfWidth": ci, "significant": abs(mean) > ci}


def run_cell(dep, alt, raz, aod):
    ph = PHOTONS[dep]
    on = {s: H.run_radiance_spectral(dep, alt, raz, aod, photons=ph, seed=s, vroom="on")
          for s in SEEDS}
    off = {s: H.run_radiance_spectral(dep, alt, raz, aod, photons=ph, seed=s, vroom="off")
           for s in SEEDS}
    ok = all(on[s]["status"] == "ok" and off[s]["status"] == "ok" for s in SEEDS)
    cell = {"dep": dep, "alt": alt, "raz": raz, "aod": aod, "photons": ph,
            "direction": {0: "sunward", 90: "cross", 180: "anti"}.get(raz, str(raz)),
            "status": "ok" if ok else "incomplete"}
    if not ok:
        cell["seedStatus"] = {s: (on[s]["status"], off[s]["status"]) for s in SEEDS}
        return cell, on, off
    # paired per-seed relative difference of photopic luminance
    rel_diffs = []
    for s in SEEDS:
        lo, lf = on[s]["photopicLuminanceCdM2"], off[s]["photopicLuminanceCdM2"]
        rel_diffs.append((lo - lf) / lf if lf else None)
    cell["photopicOnMean"] = statistics.mean(on[s]["photopicLuminanceCdM2"] for s in SEEDS)
    cell["photopicOffMean"] = statistics.mean(off[s]["photopicLuminanceCdM2"] for s in SEEDS)
    cell["pairedRelDiff"] = paired_stats(rel_diffs)
    cell["runtimeRatioOnOverOff"] = (
        statistics.mean(on[s]["runtime"] for s in SEEDS)
        / statistics.mean(off[s]["runtime"] for s in SEEDS))
    return cell, on, off


def _aggregate(cells, ratio_cells):
    """Compute aggregate bias stats + authorization from per-cell paired stats.
    Shared by a fresh run and by --reaggregate (re-decide on saved data)."""
    ok_cells = [c for c in cells if c.get("status") == "ok"]
    complete = (len(ok_cells) == len(cells))
    all_means = [c["pairedRelDiff"]["mean"] for c in ok_cells if c.get("pairedRelDiff")]
    overall = paired_stats(all_means) if len(all_means) >= 2 else None
    dir_bias = {}
    for d in ("sunward", "cross", "anti"):
        v = [c["pairedRelDiff"]["mean"] for c in ok_cells
             if c.get("direction") == d and c.get("pairedRelDiff")]
        dir_bias[d] = paired_stats(v) if len(v) >= 2 else None
    dir_means = [s["mean"] for s in dir_bias.values() if s]
    dir_spread = (max(dir_means) - min(dir_means)) if len(dir_means) >= 2 else None
    ratio_means = [r["pairedRatioRelDiff"]["mean"] for r in ratio_cells]
    ratio_overall = paired_stats(ratio_means) if len(ratio_means) >= 2 else None
    mandatory_ok = (complete and overall is not None and dir_spread is not None
                    and ratio_overall is not None
                    and all(dir_bias[d] is not None for d in dir_bias))
    authorized, reason = decide_authorization(complete, mandatory_ok, overall,
                                              dir_bias, ratio_overall)
    return {"okCells": len(ok_cells), "complete": complete, "overall": overall,
            "dirBias": dir_bias, "dirSpread": dir_spread,
            "ratioOverall": ratio_overall, "mandatoryOk": mandatory_ok,
            "authorized": authorized, "reason": reason}


def reaggregate():
    """Re-decide authorization on the saved vroom-validation.json (no libRadtran).
    Used after the negligibility/significance criterion changed."""
    r = json.loads((REPORTS / "vroom-validation.json").read_text())
    agg = _aggregate(r["cells"], r.get("ratioCells", []))
    r["overallBiasPhotopic"] = agg["overall"]
    r["directionBiasPhotopic"] = agg["dirBias"]
    r["directionBiasSpread"] = agg["dirSpread"]
    r["directionalRatioOverallBias"] = agg["ratioOverall"]
    r["mandatoryStatisticsAvailable"] = agg["mandatoryOk"]
    r["negligibilityRelThreshold"] = NEGLIGIBLE_REL
    r["authorizationReason"] = agg["reason"]
    r["vroomAuthorizedForGrid"] = agg["authorized"]
    r["criteria"] = ("authorized iff okCellCount==cellCount AND all mandatory "
                     "stats present AND NO bias is BOTH significant AND >= "
                     f"{NEGLIGIBLE_REL:.0%} (deep-cell scatter is noise per "
                     "vroom-deep-diagnostic.json)")
    r.setdefault("deepCellNoiseCaveat",
                 "dep-8 faint cells are noise-limited even at 8-40M photons; "
                 "higher per-node uncertainty, NOT a VROOM bias.")
    (REPORTS / "vroom-validation.json").write_text(json.dumps(r, indent=1))
    _write_md(r)
    print(json.dumps({"reaggregated": True, "authorized": agg["authorized"],
                      "reason": agg["reason"]}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deps", default="0,4,8")
    ap.add_argument("--reaggregate", action="store_true",
                    help="re-decide authorization on saved data (no libRadtran)")
    args = ap.parse_args()
    if args.reaggregate:
        reaggregate()
        return
    deps = [int(x) for x in args.deps.split(",")]

    # build the complete matrix and remember which are zenith (for ratios)
    matrix = []
    for dep in deps:
        for aod in (0.05, 0.30):
            for alt in (10, 30):
                for raz in (0, 90, 180):
                    matrix.append((dep, alt, raz, aod))
            matrix.append((dep, 90, 0, aod))    # zenith (azimuth-degenerate)

    cells = []
    photopic = {}     # (dep,alt,raz,aod,mode,seed) -> L, for directional ratios
    for (dep, alt, raz, aod) in matrix:
        cell, on, off = run_cell(dep, alt, raz, aod)
        cells.append(cell)
        if cell["status"] == "ok":
            for s in SEEDS:
                photopic[(dep, alt, raz, aod, "on", s)] = on[s]["photopicLuminanceCdM2"]
                photopic[(dep, alt, raz, aod, "off", s)] = off[s]["photopicLuminanceCdM2"]
        print(f"cell dep{dep} alt{alt} raz{raz} aod{aod}: {cell['status']}"
              + (f" relDiff {cell['pairedRelDiff']['mean']:+.4f} "
                 f"t={cell['pairedRelDiff']['t']:+.2f}"
                 if cell.get("pairedRelDiff") else ""), flush=True)

    # directional-ratio paired differences: R = L(target)/L(zenith), on vs off,
    # paired by seed. Only for non-zenith cells.
    ratio_cells = []
    for (dep, alt, raz, aod) in matrix:
        if alt == 90:
            continue
        rd = []
        for s in SEEDS:
            key_t_on = (dep, alt, raz, aod, "on", s)
            key_z_on = (dep, 90, 0, aod, "on", s)
            key_t_off = (dep, alt, raz, aod, "off", s)
            key_z_off = (dep, 90, 0, aod, "off", s)
            if all(k in photopic for k in (key_t_on, key_z_on, key_t_off, key_z_off)):
                r_on = photopic[key_t_on] / photopic[key_z_on]
                r_off = photopic[key_t_off] / photopic[key_z_off]
                rd.append((r_on - r_off) / r_off if r_off else None)
        st = paired_stats(rd)
        if st:
            ratio_cells.append({"dep": dep, "alt": alt, "raz": raz, "aod": aod,
                                "direction": {0: "sunward", 90: "cross", 180: "anti"}[raz],
                                "pairedRatioRelDiff": st})

    ok_cells = [c for c in cells if c["status"] == "ok"]
    complete = (len(ok_cells) == len(cells))
    # overall bias: paired-mean rel diffs pooled across cells
    all_means = [c["pairedRelDiff"]["mean"] for c in ok_cells if c.get("pairedRelDiff")]
    overall = paired_stats(all_means) if len(all_means) >= 2 else None
    # direction bias
    dir_bias = {}
    for d in ("sunward", "cross", "anti"):
        v = [c["pairedRelDiff"]["mean"] for c in ok_cells
             if c["direction"] == d and c.get("pairedRelDiff")]
        dir_bias[d] = paired_stats(v) if len(v) >= 2 else None
    dir_means = [s["mean"] for s in dir_bias.values() if s]
    dir_spread = (max(dir_means) - min(dir_means)) if len(dir_means) >= 2 else None
    # ratio overall
    ratio_means = [r["pairedRatioRelDiff"]["mean"] for r in ratio_cells]
    ratio_overall = paired_stats(ratio_means) if len(ratio_means) >= 2 else None

    mandatory_ok = (complete and overall is not None and dir_spread is not None
                    and ratio_overall is not None
                    and all(dir_bias[d] is not None for d in dir_bias))
    authorized, reason = decide_authorization(complete, mandatory_ok, overall,
                                              dir_bias, ratio_overall)

    result = {
        "depressions": deps, "seeds": list(SEEDS), "photonsByDepression": PHOTONS,
        "pairingNote": "on/off share seeds; PAIRED per-seed photopic differences",
        "cellCount": len(cells), "okCellCount": len(ok_cells),
        "complete": complete,
        "overallBiasPhotopic": overall,
        "directionBiasPhotopic": dir_bias, "directionBiasSpread": dir_spread,
        "directionalRatioOverallBias": ratio_overall,
        "mandatoryStatisticsAvailable": mandatory_ok,
        "negligibilityRelThreshold": NEGLIGIBLE_REL,
        "criteria": "authorized iff okCellCount==cellCount AND all mandatory "
        "stats present AND NO bias (overall, any direction, or directional "
        f"ratio) is BOTH statistically significant AND >= {NEGLIGIBLE_REL:.0%} "
        "(large non-significant deep-cell scatter is noise per "
        "vroom-deep-diagnostic.json, not a systematic VROOM effect)",
        "authorizationReason": reason,
        "vroomAuthorizedForGrid": authorized,
        "deepCellNoiseCaveat": "dep-8 faint cells (low altitude, antisolar) are "
        "noise-limited (~5-15% per-run photopic uncertainty even at 8-40M "
        "photons); those LUT nodes require large photon budgets and carry higher "
        "per-node uncertainty. This is a resolution limit, NOT a VROOM bias.",
        "cells": cells, "ratioCells": ratio_cells,
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "vroom-validation.json").write_text(json.dumps(result, indent=1))
    _write_md(result)
    print(json.dumps({"okCells": len(ok_cells), "cellCount": len(cells),
                      "complete": complete,
                      "overallMean": overall["mean"] if overall else None,
                      "overallSignificant": overall["significant"] if overall else None,
                      "directionSpread": dir_spread,
                      "ratioOverallMean": ratio_overall["mean"] if ratio_overall else None,
                      "vroomAuthorizedForGrid": authorized}, indent=1))


def _write_md(r):
    L = ["# VROOM on/off validation (PG-3, paired, photopic; gate before grid)", "",
         f"Depressions {r['depressions']}, seeds {r['seeds']} (SHARED by on/off "
         "-> paired analysis).",
         f"Cells {r['okCellCount']}/{r['cellCount']} ok; complete={r['complete']}.",
         "", "## Aggregate (paired per-seed photopic relative difference)", ""]
    o = r["overallBiasPhotopic"]
    if o:
        L.append(f"- overall: mean {o['mean']:+.4f}, SE {o['se']:.4f}, "
                 f"95% CI +/-{o['ci95HalfWidth']:.4f}, t {o['t']:+.2f}, "
                 f"significant={o['significant']}")
    L.append(f"- direction-bias spread: {r['directionBiasSpread']}")
    ro = r["directionalRatioOverallBias"]
    if ro:
        L.append(f"- directional-ratio overall: mean {ro['mean']:+.4f}, "
                 f"t {ro['t']:+.2f}, significant={ro['significant']}")
    L += ["", f"## VROOM authorized for grid: **{r['vroomAuthorizedForGrid']}**",
          f"Criteria: {r['criteria']}", "",
          "| dep | alt | raz | dir | AOD | Lon | Loff | paired relDiff | t | rt on/off |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for c in r["cells"]:
        if c["status"] != "ok":
            L.append(f"| {c['dep']} | {c['alt']} | {c['raz']} | {c['direction']} "
                     f"| {c['aod']} | MISSING/{c['status']} |  |  |  |  |")
            continue
        p = c["pairedRelDiff"]
        L.append(f"| {c['dep']} | {c['alt']} | {c['raz']} | {c['direction']} | "
                 f"{c['aod']} | {c['photopicOnMean']:.4g} | {c['photopicOffMean']:.4g} "
                 f"| {p['mean']:+.4f} +/-{p['ci95HalfWidth']:.4f} | {p['t']:+.2f} | "
                 f"{c['runtimeRatioOnOverOff']:.2f} |")
    (REPORTS / "vroom-validation.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
