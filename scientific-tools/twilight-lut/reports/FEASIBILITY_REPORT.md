# libRadtran Directional Twilight-Radiance LUT — Feasibility Report

**AUTO-GENERATED from `FEASIBILITY_REPORT.json` by `scripts/write_feasibility_report.py` (RH-6). Do not hand-edit; regenerate the JSON, which regenerates this file.** Every number below comes from the real simulation outputs and the evidence files.

- uvspec: `uvspec, version 2.0.6-MYSTIC` — conda-forge rubin-libradtran (real build of the upstream libRadtran 2.0.6 tarball)
- generator commit: `8a828df8e44ff20720d88be79d30fbc707b808bd`
- outputs are real: True

## Status model (six separate statuses)

- **solverFeasibilityStatus**: PASS — MYSTIC 1D-spherical backward valid 0-8 deg across core geometry; DISORT/pseudospherical invalid below the horizon
- **numericalStabilityStatus**: PASS — median photopic uncertainty 1.14% on resolved cases
- **literaturePlausibilityStatus**: PASS (broad, unmatched-atmosphere anchors only) — consistent with Koomen/Rozenberg/Patat plausibility ranges; NOT primary matched-geometry validation
- **primaryObservationalValidationStatus**: PENDING (Milestone 3) — matched-geometry Patat/Koomen comparison via synthetic Johnson V
- **firstVisibilityValidationStatus**: BLOCKED — no first-visibility observational dataset exists in the repository
- **productionReadinessStatus**: NOT RECOMMENDED — feasibility only

## Feasibility gates

Verdict: **PASS**

- PASS — solver+geometry valid in twilight (from solver-validation.json + full core-cell coverage): solver-validation pass=True, MYSTIC 7/7 valid, DISORT-invalid-below-horizon=True; core cells 36/36 resolved (expected >=36)
- PASS — numerical stability adequate for a LUT (coverage + p95 + max): resolved coverage 100.0%, p95 rel uncertainty 5.50%, max 37.1%
- PASS — Monte Carlo uncertainty quantified (repeat groups + spread + sigma-ratio band): 2 repeat groups across 2 depressions; empirical/reported ratios [0.83, 0.69] in [0.3,3.0]
- PASS — runtime practical for the expanded grid: projected canonical grid (540 unique nodes, 925 runs): 18.5 CPU-h single-core (4.62 h at 4 jobs)
- PASS — output convertible to the calculator's quantities (p95 grid consistency): spectral radiance -> photopic luminance -> nL -> KS-convention mag/arcsec2; fine-vs-node grid consistency p95 0.46%
- PASS — consistent with broad literature plausibility ranges (NOT primary matched-geometry validation): 9/9 broad-anchor+sanity checks passed under UNMATCHED atmospheric assumptions (offline literature anchors). Primary matched-geometry validation is a separate Milestone 3 deliverable.

### Gate inputs (measured)

- core cells resolved: 36/36 (expected >= 36)
- resolved coverage: 100.0%; rel-uncertainty p95 5.50%, max 37.1%
- Monte Carlo repeat groups: 2 across depressions [4, 8]; sigma ratios [0.83, 0.69]
- solver-validation pass: True
- grid-consistency p95: 0.457%

## Supported domain (evidence-based, NOT the full hypercube)

- **full core geometry** at depressions [0, 4, 8] deg — full core geometry (target altitudes {10,30,60,90} x relative azimuths {0,90,180}) tested and resolved at these depressions, at baseline AOD 0.15
- **spot checks only** at [2, 6] deg — partial spot checks only (single altitude/azimuth slices), NOT full core geometry
- **provisional zenith-only** at [9, 10] deg — ZENITH-ONLY probes resolved to ~9-13% at 4e7 photons; NOT established at other altitudes/azimuths/AOD
- AOD extremes: AOD 0.05 and 0.30 sampled only in limited geometries, not validated across the domain
- not supported: {'sunDepressionDeg': '>=12 (marginal ~37%, impractical cost)', 'targetAltitudeDeg': '<10 (untested)', 'atmosphere': 'clouds, refraction (not modelled), aerosol families other than the one Shettle rural profile'}
- full hypercube supported: **False**
- Supersedes any earlier '0-10 deg fully supported' wording. Full core geometry exists only at depressions 0/4/8; 2/6 are spot checks; 9/10 are zenith-only provisional probes.

## Cases and stability

- cases: 67 total, 67 ok, 0 failed, 0 unresolved
- runtime/case: median 39.8s, max 224s
- canonical grid (grid_def.py): 540 unique nodes, 925 runs, 18.5 CPU-h

## Scope of validation (what this report does and does NOT claim)

- This is a **feasibility and internal-consistency** result plus **broad literature-plausibility** checks under UNMATCHED atmospheric assumptions.
- It is **not** primary matched-geometry observational validation and **not** first-visibility validation; those statuses are PENDING and BLOCKED respectively (see status model).
- Production integration is **not recommended** from this report.

## Reproduction

```
python scripts/check_environment.py
python scripts/solver_validation.py
python scripts/run_libradtran.py --jobs 4
python scripts/parse_outputs.py
python scripts/integrate_visual_response.py
python scripts/analyze_monte_carlo_uncertainty.py
python scripts/validate_against_observations.py
python scripts/validate_primary_observations.py
python scripts/write_feasibility_report.py
python -m pytest tests/ -q
```
