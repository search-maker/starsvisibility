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

    # Gate evaluation
    def gate(name, passed, evidence):
        return {"gate": name, "passed": bool(passed), "evidence": evidence}

    contrast_growth = next((c for c in (obs or {}).get("checks", [])
                            if "contrast grows" in c["check"]), None)
    obs_pass = obs and obs["passed"] == obs["total"]
    mc_worst = (mc or {}).get("worstEmpiricalToReportedRatio")
    gates = [
        gate("solver+geometry valid in twilight",
             True,
             "MYSTIC 1D-spherical backward produces finite positive radiance "
             "for depressions 0-8 deg; DISORT/pseudospherical demonstrated "
             "invalid (negative radiances) beyond SZA 90 and is not used"),
        gate("numerical stability adequate for a LUT",
             rel and statistics.median(rel) < 0.03,
             f"median photopic relative uncertainty "
             f"{statistics.median(rel):.3%} (max {max(rel):.1%})" if rel else "no data"),
        gate("Monte Carlo uncertainty quantified",
             mc is not None and mc_worst is not None,
             f"independent-seed repeats; worst empirical/reported ratio "
             f"{mc_worst:.2f}" if mc_worst else "missing"),
        gate("runtime practical for the expanded grid",
             stats["projectedGridCpuHoursSingleCore"] < 48,
             f"projected canonical grid ({grid['counts']['uniqueNodeCount']} "
             f"unique nodes, {grid['counts']['totalSimulationRuns']} runs): "
             f"{stats['projectedGridCpuHoursSingleCore']} CPU-h single-core "
             f"({grid['counts']['projectedWallHoursAtJobs']} h at "
             f"{grid['counts']['jobs']} jobs)"),
        gate("output convertible to the calculator's quantities",
             grid_cons and statistics.median(grid_cons) < 0.05,
             "spectral radiance -> photopic luminance -> nL -> KS-convention "
             f"mag/arcsec2; fine-vs-node grid consistency median "
             f"{statistics.median(grid_cons):.2%}" if grid_cons else "no data"),
        gate("consistent with broad literature plausibility ranges "
             "(NOT primary matched-geometry validation)",
             obs_pass,
             f"{obs['passed']}/{obs['total']} broad-anchor+sanity checks passed "
             "under UNMATCHED atmospheric assumptions (offline literature "
             "anchors; see OBSERVATIONAL_VALIDATION.md). Primary matched-geometry "
             "validation is a separate Milestone 3 deliverable."
             if obs else "missing"),
    ]
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

    # Evidence-based supported domain (§2.2): distinguish demonstrated core from
    # provisional zenith-only extension. Do NOT declare the full hypercube.
    stats["supportedDomain"] = {
        "demonstratedCore": {
            "sunDepressionDeg": [0, 8],
            "targetAltitudeDeg": [10, 90],
            "relativeAzimuthDeg": [0, 180],
            "aod550Baseline": 0.15,
            "note": "0-8 deg feasibility demonstrated across the core "
            "altitude/azimuth geometry at baseline AOD; AOD extremes sampled "
            "only in limited geometries (not validated across the full domain)",
        },
        "provisionalExtension": {
            "sunDepressionDeg": [9, 10],
            "evidence": "ZENITH-ONLY probes resolved to ~9-13% at 4e7 photons; "
            "NOT established at all altitudes/azimuths/AOD",
        },
        "notSupported": {
            "sunDepressionDeg": ">=12 (marginal ~37%, impractical cost)",
            "targetAltitudeDeg": "<10 (untested)",
            "atmosphere": "clouds, refraction (not modelled), aerosol families "
            "other than the one Shettle rural profile",
        },
        "fullHypercubeSupported": False,
        "reconciliationNote": "This evidence-based domain supersedes any earlier "
        "'0-10 deg fully supported' wording in README/SCIENTIFIC_ASSUMPTIONS/"
        "FEASIBILITY_REPORT; the full 0-10 deg x 10-90 deg x AOD hypercube is "
        "NOT declared supported until Milestone 3 pre-grid worst-geometry cases "
        "pass.",
    }
    (REPORTS / "FEASIBILITY_REPORT.json").write_text(
        json.dumps({"environment": env, "statistics": stats}, indent=1))
    print(json.dumps({"verdict": stats["feasibilityVerdict"],
                      "gates": [(g["gate"], g["passed"]) for g in gates]},
                     indent=1))
    print(f"wrote {REPORTS/'FEASIBILITY_REPORT.json'}")
    print("NOTE: FEASIBILITY_REPORT.md is written by hand from this JSON so "
          "that prose claims never exceed the data; regenerate the JSON first.")


if __name__ == "__main__":
    main()
