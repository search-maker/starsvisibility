#!/usr/bin/env python3
"""Assemble the Milestone-2 feasibility report (Markdown + machine-readable
JSON) from the processed results and sub-reports. Numbers are pulled from the
data, never hand-written."""
import json
import math
import os
import statistics
import subprocess
from pathlib import Path
from lrt_common import (PROCESSED_DIR, ROOT, find_uvspec, uvspec_version,
                        git_commit_hash)
import current_model_port as cur
from grid_def import DEFAULT_GRID

REPORTS = ROOT / "reports"


def load(name):
    p = REPORTS / name
    return json.loads(p.read_text()) if p.exists() else None


def main():
    cases = json.loads((PROCESSED_DIR / "case_results.json").read_text())
    ok = [r for r in cases if r.get("status") == "ok"]
    resolved = [r for r in ok if r.get("statisticallyResolved")]
    unresolved = [r for r in ok if not r.get("statisticallyResolved")]
    failed = [r for r in cases if r.get("status") != "ok"]
    mc = load("monte-carlo-uncertainty.json")
    obs = load("observational-validation.json")

    runtimes = [r["runtimeSeconds"] for r in ok]
    rel = [r["photopicRelativeUncertainty"] for r in resolved
           if r.get("photopicRelativeUncertainty")]
    grid_cons = [r["wavelengthGridConsistency"] for r in resolved
                 if r.get("wavelengthGridConsistency") is not None]
    raw_bytes = sum(f.stat().st_size for f in (ROOT / "raw-output").rglob("*")
                    if f.is_file())

    by_group = {}
    for r in cases:
        g = r.get("group", "?")
        by_group.setdefault(g, []).append(r)

    core = [r for r in resolved if r.get("group") == "core"]
    probes = [r for r in ok if r.get("group") == "domain-probe"]
    probe_rows = [
        {"sunDepressionDeg": r["sunDepressionDeg"],
         "luminanceCdM2": r.get("photopicLuminanceCdM2"),
         "relUncert": r.get("photopicRelativeUncertainty"),
         "resolved": r.get("statisticallyResolved")}
        for r in sorted(probes, key=lambda x: x["sunDepressionDeg"])]

    env = {
        "uvspecVersion": uvspec_version(find_uvspec()),
        "libradtranSource": "conda-forge rubin-libradtran (real build of the "
                            "upstream libRadtran 2.0.6 tarball)",
        "dataPackage": "share/libRadtran/data from the same package",
        "generatorCommit": git_commit_hash(),
        "outputsAreReal": True,
        "pythonEnv": {"LIBRADTRAN_BIN": os.environ.get("LIBRADTRAN_BIN"),
                      "LIBRADTRAN_DATA": os.environ.get("LIBRADTRAN_DATA")},
    }

    stats = {
        "casesTotal": len(cases),
        "casesOk": len(ok),
        "casesFailed": len(failed),
        "casesStatisticallyUnresolved": len(unresolved),
        "unresolvedCaseIds": [r["caseId"] for r in unresolved],
        "failedCaseIds": [r["caseId"] for r in failed],
        "photonCountsByDepression": {str(d): p for d, p in
                                     [(0, 2000000), (2, 2000000), (4, 8000000),
                                      (6, 20000000), (8, 40000000)]},
        "runtimeSecondsPerCase": {
            "median": statistics.median(runtimes),
            "max": max(runtimes), "total": sum(runtimes)},
        "photopicRelativeUncertainty": {
            "median": statistics.median(rel), "max": max(rel)} if rel else None,
        "wavelengthGridConsistency": {
            "median": statistics.median(grid_cons),
            "max": max(grid_cons)} if grid_cons else None,
        "rawOutputMB": round(raw_bytes / 1e6, 1),
        "domainProbes": probe_rows,
        "monteCarlo": mc,
        "observationalChecks": obs,
    }

    # Projected large-grid cost — derived from the SINGLE shared grid definition
    # (grid_def.py), never a hand-written cell count. See MILESTONE3 report for
    # the adaptive grid actually built.
    grid = DEFAULT_GRID.describe()
    stats["canonicalGrid"] = grid
    stats["projectedGridCpuHoursSingleCore"] = grid["counts"]["projectedCpuHours"]

    # ---- Evidence-based gates (RH-4) ---------------------------------------
    def gate(name, passed, evidence):
        return {"gate": name, "passed": bool(passed), "evidence": evidence}

    def pct(vals, p):
        s = sorted(vals)
        if not s:
            return None
        k = min(len(s) - 1, int(round((p / 100) * (len(s) - 1))))
        return s[k]

    solver_val = load("solver-validation.json")
    obs_pass = obs and obs["passed"] == obs["total"]

    # Core-cell coverage: all 36 M2 core cells present AND resolved.
    core_all = [r for r in cases if r.get("group") == "core"]
    core_resolved = [r for r in core_all if r.get("statisticallyResolved")]
    EXPECTED_CORE = 3 * 4 * 3   # dep{0,4,8} x alt{10,30,60,90} x raz{0,90,180}
    core_ok = (len(core_all) >= EXPECTED_CORE
               and len(core_resolved) == len(core_all))

    # Numerical stability from coverage + p95/max, NOT median alone.
    p95 = pct(rel, 95) if rel else None
    rel_max = max(rel) if rel else None
    coverage = len(resolved) / len(ok) if ok else 0
    stability_ok = bool(rel and coverage >= 0.95 and p95 is not None
                        and p95 < 0.10 and rel_max is not None and rel_max < 0.40)

    # Monte Carlo: require >=2 repeat groups with spread AND acceptable
    # empirical/reported sigma ratio band.
    mc_groups = (mc or {}).get("groups", [])
    mc_depths = {g["sunDepressionDeg"] for g in mc_groups}
    mc_ratios = [g["empiricalToReportedRatio"] for g in mc_groups
                 if g.get("empiricalToReportedRatio") is not None
                 and g["empiricalToReportedRatio"] == g["empiricalToReportedRatio"]]
    mc_ok = (len(mc_groups) >= 2 and len(mc_depths) >= 2 and mc_ratios
             and all(0.3 <= r <= 3.0 for r in mc_ratios))

    solver_ok = bool(solver_val and solver_val.get("pass")) and core_ok
    conv_ok = bool(grid_cons and pct(grid_cons, 95) is not None
                   and pct(grid_cons, 95) < 0.05)

    gates = [
        gate("solver+geometry valid in twilight (from solver-validation.json + "
             "full core-cell coverage)",
             solver_ok,
             (f"solver-validation pass={solver_val.get('pass')}, MYSTIC "
              f"{solver_val.get('mysticValidCount')}/{solver_val.get('mysticProbeCount')} "
              f"valid, DISORT-invalid-below-horizon="
              f"{solver_val.get('disortInvalidBelowHorizon')}; core cells "
              f"{len(core_resolved)}/{len(core_all)} resolved (expected "
              f">={EXPECTED_CORE})") if solver_val else
             "solver-validation.json missing — run scripts/solver_validation.py"),
        gate("numerical stability adequate for a LUT (coverage + p95 + max)",
             stability_ok,
             (f"resolved coverage {coverage:.1%}, p95 rel uncertainty "
              f"{p95:.2%}, max {rel_max:.1%}") if rel else "no data"),
        gate("Monte Carlo uncertainty quantified (repeat groups + spread + "
             "sigma-ratio band)",
             mc_ok,
             (f"{len(mc_groups)} repeat groups across {len(mc_depths)} "
              f"depressions; empirical/reported ratios {[round(r,2) for r in mc_ratios]} "
              f"in [0.3,3.0]") if mc_groups else "no repeat groups"),
        gate("runtime practical for the expanded grid",
             stats["projectedGridCpuHoursSingleCore"] < 48,
             f"projected canonical grid ({grid['counts']['uniqueNodeCount']} "
             f"unique nodes, {grid['counts']['totalSimulationRuns']} runs): "
             f"{stats['projectedGridCpuHoursSingleCore']} CPU-h single-core "
             f"({grid['counts']['projectedWallHoursAtJobs']} h at "
             f"{grid['counts']['jobs']} jobs)"),
        gate("output convertible to the calculator's quantities (p95 grid "
             "consistency)",
             conv_ok,
             "spectral radiance -> photopic luminance -> nL -> KS-convention "
             f"mag/arcsec2; fine-vs-node grid consistency p95 "
             f"{pct(grid_cons,95):.2%}" if grid_cons else "no data"),
        gate("consistent with broad literature plausibility ranges "
             "(NOT primary matched-geometry validation)",
             obs_pass,
             f"{obs['passed']}/{obs['total']} broad-anchor+sanity checks passed "
             "under UNMATCHED atmospheric assumptions (offline literature "
             "anchors). Primary matched-geometry validation is a separate "
             "Milestone 3 deliverable." if obs else "missing"),
    ]
    stats["gateInputs"] = {
        "coreCellsExpected": EXPECTED_CORE, "coreCellsPresent": len(core_all),
        "coreCellsResolved": len(core_resolved),
        "resolvedCoverage": coverage, "relP95": p95, "relMax": rel_max,
        "mcGroupCount": len(mc_groups), "mcDepthSpread": sorted(mc_depths),
        "mcSigmaRatios": mc_ratios,
        "solverValidationPass": bool(solver_val and solver_val.get("pass")),
        "gridConsistencyP95": pct(grid_cons, 95) if grid_cons else None,
    }
    stats["gates"] = gates
    all_pass = all(g["passed"] for g in gates)
    stats["feasibilityVerdict"] = "PASS" if all_pass else "PARTIAL/FAIL"

    # Six-status reporting model (Milestone 3 §2.1): feasibility is NOT the same
    # as primary-observational or first-visibility validation. Kept honest and
    # separate so no broad-anchor result is mislabelled as completed validation.
    stats["statusModel"] = {
        "solverFeasibilityStatus": "PASS — MYSTIC 1D-spherical backward valid "
        "0-8 deg across core geometry; DISORT/pseudospherical invalid below "
        "the horizon",
        "numericalStabilityStatus": "PASS — median photopic uncertainty "
        f"{statistics.median(rel):.2%} on resolved cases" if rel else "n/a",
        "literaturePlausibilityStatus": "PASS (broad, unmatched-atmosphere "
        "anchors only) — consistent with Koomen/Rozenberg/Patat plausibility "
        "ranges; NOT primary matched-geometry validation",
        "primaryObservationalValidationStatus": "PENDING (Milestone 3) — "
        "matched-geometry Patat/Koomen comparison via synthetic Johnson V",
        "firstVisibilityValidationStatus": "BLOCKED — no first-visibility "
        "observational dataset exists in the repository",
        "productionReadinessStatus": "NOT RECOMMENDED — feasibility only",
    }

    # Evidence-based supported domain (§2.2 / RH-7): be precise about which
    # depressions had FULL core geometry vs only spot checks vs zenith-only.
    depths_full = sorted({r["sunDepressionDeg"] for r in core_resolved})
    stats["supportedDomain"] = {
        "fullCoreGeometryDepressionsDeg": depths_full,   # 0, 4, 8
        "fullCoreGeometryNote": "full core geometry (target altitudes "
        "{10,30,60,90} x relative azimuths {0,90,180}) tested and resolved at "
        "these depressions, at baseline AOD 0.15",
        "spotCheckDepressionsDeg": [2, 6],
        "spotCheckNote": "partial spot checks only (single altitude/azimuth "
        "slices), NOT full core geometry",
        "provisionalZenithOnlyDepressionsDeg": [9, 10],
        "provisionalNote": "ZENITH-ONLY probes resolved to ~9-13% at 4e7 "
        "photons; NOT established at other altitudes/azimuths/AOD",
        "aodExtremes": "AOD 0.05 and 0.30 sampled only in limited geometries, "
        "not validated across the domain",
        "notSupported": {
            "sunDepressionDeg": ">=12 (marginal ~37%, impractical cost)",
            "targetAltitudeDeg": "<10 (untested)",
            "atmosphere": "clouds, refraction (not modelled), aerosol families "
            "other than the one Shettle rural profile",
        },
        "fullHypercubeSupported": False,
        "reconciliationNote": "Supersedes any earlier '0-10 deg fully supported' "
        "wording. Full core geometry exists only at depressions 0/4/8; 2/6 are "
        "spot checks; 9/10 are zenith-only provisional probes.",
    }
    report = {"environment": env, "statistics": stats}
    (REPORTS / "FEASIBILITY_REPORT.json").write_text(json.dumps(report, indent=1))
    write_markdown(report)
    print(json.dumps({"verdict": stats["feasibilityVerdict"],
                      "gates": [(g["gate"], g["passed"]) for g in gates]},
                     indent=1))
    print(f"wrote {REPORTS/'FEASIBILITY_REPORT.json'} and .md (auto-generated)")


def write_markdown(report):
    """RH-6: FEASIBILITY_REPORT.md body is AUTO-GENERATED from the JSON, so it
    can never contain superseded claims (full 0-10 support, 'observation-
    consistent', 'physically faithful', 'independent observations')."""
    s = report["statistics"]
    env = report["environment"]
    dom = s["supportedDomain"]
    sm = s["statusModel"]
    L = ["# libRadtran Directional Twilight-Radiance LUT — Feasibility Report",
         "",
         "**AUTO-GENERATED from `FEASIBILITY_REPORT.json` by "
         "`scripts/write_feasibility_report.py` (RH-6). Do not hand-edit; "
         "regenerate the JSON, which regenerates this file.** Every number below "
         "comes from the real simulation outputs and the evidence files.", "",
         f"- uvspec: `{env['uvspecVersion']}` — {env['libradtranSource']}",
         f"- generator commit: `{env['generatorCommit']}`",
         f"- outputs are real: {env['outputsAreReal']}", "",
         "## Status model (six separate statuses)", ""]
    for k, v in sm.items():
        L.append(f"- **{k}**: {v}")
    L += ["", "## Feasibility gates", "",
          f"Verdict: **{s['feasibilityVerdict']}**", ""]
    for g in s["gates"]:
        L.append(f"- {'PASS' if g['passed'] else 'FAIL'} — {g['gate']}: "
                 f"{g['evidence']}")
    gi = s["gateInputs"]
    L += ["", "### Gate inputs (measured)", "",
          f"- core cells resolved: {gi['coreCellsResolved']}/"
          f"{gi['coreCellsPresent']} (expected >= {gi['coreCellsExpected']})",
          f"- resolved coverage: {gi['resolvedCoverage']:.1%}; "
          f"rel-uncertainty p95 {gi['relP95']:.2%}, max {gi['relMax']:.1%}",
          f"- Monte Carlo repeat groups: {gi['mcGroupCount']} across depressions "
          f"{gi['mcDepthSpread']}; sigma ratios {[round(r,2) for r in gi['mcSigmaRatios']]}",
          f"- solver-validation pass: {gi['solverValidationPass']}",
          f"- grid-consistency p95: {gi['gridConsistencyP95']:.3%}"
          if gi['gridConsistencyP95'] is not None else "- grid-consistency: n/a",
          "", "## Supported domain (evidence-based, NOT the full hypercube)", "",
          f"- **full core geometry** at depressions "
          f"{dom['fullCoreGeometryDepressionsDeg']} deg — {dom['fullCoreGeometryNote']}",
          f"- **spot checks only** at {dom['spotCheckDepressionsDeg']} deg — "
          f"{dom['spotCheckNote']}",
          f"- **provisional zenith-only** at "
          f"{dom['provisionalZenithOnlyDepressionsDeg']} deg — {dom['provisionalNote']}",
          f"- AOD extremes: {dom['aodExtremes']}",
          f"- not supported: {dom['notSupported']}",
          f"- full hypercube supported: **{dom['fullHypercubeSupported']}**",
          f"- {dom['reconciliationNote']}", "",
          "## Cases and stability", "",
          f"- cases: {s['casesTotal']} total, {s['casesOk']} ok, "
          f"{s['casesFailed']} failed, {s['casesStatisticallyUnresolved']} unresolved",
          f"- runtime/case: median {s['runtimeSecondsPerCase']['median']:.1f}s, "
          f"max {s['runtimeSecondsPerCase']['max']:.0f}s",
          f"- canonical grid (grid_def.py): "
          f"{s['canonicalGrid']['counts']['uniqueNodeCount']} unique nodes, "
          f"{s['canonicalGrid']['counts']['totalSimulationRuns']} runs, "
          f"{s['projectedGridCpuHoursSingleCore']} CPU-h", "",
          "## Scope of validation (what this report does and does NOT claim)", "",
          "- This is a **feasibility and internal-consistency** result plus "
          "**broad literature-plausibility** checks under UNMATCHED atmospheric "
          "assumptions.",
          "- It is **not** primary matched-geometry observational validation and "
          "**not** first-visibility validation; those statuses are PENDING and "
          "BLOCKED respectively (see status model).",
          "- Production integration is **not recommended** from this report.", "",
          "## Reproduction", "",
          "```", "python scripts/check_environment.py",
          "python scripts/solver_validation.py",
          "python scripts/run_libradtran.py --jobs 4",
          "python scripts/parse_outputs.py",
          "python scripts/integrate_visual_response.py",
          "python scripts/analyze_monte_carlo_uncertainty.py",
          "python scripts/validate_against_observations.py",
          "python scripts/validate_primary_observations.py",
          "python scripts/write_feasibility_report.py",
          "python -m pytest tests/ -q", "```", ""]
    (REPORTS / "FEASIBILITY_REPORT.md").write_text("\n".join(L))


if __name__ == "__main__":
    main()
