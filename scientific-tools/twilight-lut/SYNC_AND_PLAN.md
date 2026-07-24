# Production Sync + Directive Status & Plan

This document tracks the branch's synchronization with the latest production
`index.html` and maps every directive from the latest instruction set to its
current status and the remaining plan. **No production `index.html` change and
no default change is made until all acceptance gates pass.** The allowed
description of the model until validation completes is:

> Experimental spherical radiative-transfer twilight model; not yet validated
> for production first-visibility prediction.

## Production sync (DONE)

- Branch merged `origin/main`; `index.html` is now the current production
  version (commit `6e7728f`, "Apply final scientific model corrections"),
  replacing the old `c9a48a6` base the original audit used.
- Re-audit of the integration boundary against the NEW code:
  - `twilightExcessNL`, `directionalTwilightFactor`, `twilightExcessNLCalibrated`,
    `nLFromMag`/`magFromNL` are **byte-identical** to the old version → the LUT
    boundary is unchanged and the boundary analysis remains valid.
  - `refractionDeg`/`apparentAltitude` now require an explicit `atmosphereState`
    (pressure+temperature) and return `null` when absent (no globals).
  - `limitingMagnitudeFromSkyBrightness` **dropped the observer-age term** — the
    port now matches (age removed, not restored).
- JS parity and end-to-end fixtures regenerated from the NEW `index.html`; all
  parity tests pass. Deleted logic was **not** restored.

## Directive-by-directive status

| # | Directive | Status |
|---|---|---|
| 1 | Preserve exact integration boundary (LUT = solar twilight excess only; totalSkyNL = dark + solarTwilight + moon; live-total bypasses LUT) | **Documented & preserved.** Boundary unchanged post-sync. Metadata contract §16 pending in the browser module. |
| 2 | Site elevation reaches uvspec | **Fixed + FINDING.** `altitude` is rejected by MYSTIC ("use mc_elevation_file"). `build_input` emits `altitude` only for DISORT-family; RAISES for elevated MYSTIC instead of silently returning sea-level. `observerElevationM` stays in the config hash. MYSTIC elevation via `mc_elevation_file` is **deferred to the elevation sensitivity study**. |
| 3 | Don't use VROOM until authorized | **DONE.** Grid production default is now `mc_vroom off`. VROOM-on stays experimental pending an event-time-impact study; the criterion change was not used to force a production PASS. |
| 4 | Validate MYSTIC vs external benchmark (IPRT Phase III) | **TODO (blocked download).** IPRT reference archive was not reachable from the build environment. Importer/stub + provenance to be added; gate marked BLOCKED until data is obtained. |
| 5 | Sensitivity analysis before full hypercube (atmosphere, elevation, AOD, aerosol family/phase/SSA/profile, albedo, ozone, refraction, polarization) → only event-time-moving params become axes | **TODO.** Requires the first-visible evaluator harness (§12) to measure event-time impact per parameter. |
| 6 | Expand required domain without extrapolation (depression 0–12°+, dense near-horizon altitude 0..90, denser sunward azimuth, AOD 0.01–0.8 log/adaptive, elevation 0–5000 m); out-of-domain → `lut-outside-validated-domain` + fallback | **TODO.** New grid design supersedes the old 540-node `grid_def`. Deep radiance that is unresolvable must be proven negligible vs the sky floor, with a validated continuous taper to 0 (no extrapolation). |
| 7 | Multiple aerosol families (rural/continental, maritime, desert/dust, urban/smoke); store family/SSA/g/phase/profile/Ångström separately; never call it a general-AOD LUT | **TODO.** Current feasibility used one Shettle rural family only (already documented in SCIENTIFIC_ASSUMPTIONS). |
| 8 | Multiple atmosphere profiles (tropical, mid-lat summer/winter, sub-arctic summer/winter) + albedo {0.05,0.15,0.30,0.60}; snow as separate scenario | **TODO.** Feasibility used AFGL US-Standard + albedo 0.15 only. |
| 9 | Refraction handled scientifically (refraction-capable build OR proven-small domain OR explicit systematic uncertainty + indeterminate output); never use apparent as geometric LUT axis | **PARTIAL.** Geometric/apparent contract fixed (PG-2). Refraction sensitivity study exists; a validated-small domain or explicit indeterminate handling is TODO. Current MYSTIC build lacks refraction. |
| 10 | Fix spectral integration; keep `photopicLuminanceCdM2` and `syntheticJohnsonVMagArcsec2` separate; don't mislabel; trapezoid/energy-preserving; test vs high-res; store zero points/passbands/checksums | **DONE (core).** Primary luminance is the fine-grid trapezoid; node 10 nm rectangle is the uncertainty path; both products stored separately; Johnson V passband checksummed (PG-1). High-res convergence test TODO. |
| 11 | Better MC control; gate on total-sky mag / limiting mag / event-time, not raw radiance error; targets p95 total-sky ≤0.05 mag, max ≤0.10 mag, event-time within tolerance | **TODO.** Requires the floor-added total-sky + event-time propagation harness. Adaptive photons + repeats per node. |
| 12 | Safe positive interpolation (log-radiance, no negative/overshoot/extrapolation/magnitude-averaging/double-zenith); validate vs ≥dozens of holdout non-grid runs incl. edges/near-horizon/near-sun/AOD/elevation transitions; event-time tests via real index.html | **TODO.** Interpolation library + holdout validation is a core remaining deliverable. |
| 13 | Matched observational validation (Patat verified + matched sims; Koomen directional ratios; first-visible holdout) | **PARTIAL.** Patat status kept PENDING-VERIFICATION; corrected Johnson V improved the (still UNMATCHED) residual to −0.18 mag. Matched 2640 m sims need MYSTIC elevation (deferred). Koomen tables BLOCKED (transcription needed). First-visible dataset absent. |
| 14 | Staged software integration A(dual-run)→B(hybrid)→C(absolute)→D(production default) with strict parity | **TODO.** No production wiring yet; A/B/C/D harness pending, all behind a disabled flag. |
| 15 | Preserve all latest software fixes; don't restore deleted logic | **DONE (sync).** Age term removal honored; boundary functions confirmed unchanged; no deleted logic restored. |
| 16 | LUT metadata + fallback (`lutVersion`, `gridSha256`, hashes, solver, vroom, atmosphere, aerosol family, aod550, elevation, albedo, geometry, interpolation nodes/method, uncertainty, `validatedDomainStatus`, `fallbackReason`); out-of-domain → existing model + `twilight-lut-fallback` | **TODO.** To be implemented with the browser lookup module. |
| 17 | Delivery set before any `index.html` change | **IN PROGRESS.** Corrected pipeline, feasibility/solver/VROOM/diagnostic reports done; IPRT, matched Patat, directional, grid-authorization, full grid def, interpolation holdout, event-time sensitivity, and the go/hybrid/absolute recommendation remain. |

## What is solid now (committed on this branch)

- Reproducibility: configurationHash restart identity, immutable `attempt-###`
  + `active.json`, rigorous output validation + data-package checksums.
- Real solver evidence: plane-parallel vs pseudospherical vs MYSTIC reported
  separately; pseudospherical disagrees with MYSTIC by up to ~56×; exact MYSTIC
  probe count required.
- VROOM: complete paired, spectral, multi-seed matrix + a photon-scaling
  diagnostic proving the dep-8 scatter is Monte-Carlo noise, not bias. Grid
  default is nonetheless **VROOM off** per directive.
- Genuine JS parity from the real (now current) `index.html`; end-to-end
  Btwi / total-sky / NELM parity.
- Authoritative Johnson V (checksummed Bessell passband, independent
  speclite cross-check); separate photopic / Johnson V / KS products.
- Six-status reporting, evidence-based domain, auto-generated feasibility body.

## Immediate next steps (proposed order)

1. **First-visible evaluator harness** driving the real `index.html` via node
   (headless), returning event time / total-sky mag / NELM for a scenario. This
   unblocks directives 5, 11, 12, 14 (event-time gating).
2. **MYSTIC elevation via `mc_elevation_file`** (validate 0 vs 2.64 vs 5 km) —
   unblocks the elevation axis and matched Paranal Patat comparison.
3. **IPRT Phase III importer** + benchmark (mark BLOCKED if unreachable).
4. **Sensitivity analysis** (directive 5) → decide which parameters become LUT
   axes vs systematic-uncertainty scenarios.
5. **New grid design** (directive 6–8) from the sensitivity result; supersede
   the old 540-node `grid_def`. Staged rollout with a resolved dep-8 pilot,
   `mc_vroom off`, adaptive photons.
6. **Safe log-space interpolation** + holdout validation (directive 12).
7. **Matched observational validation** (directive 13).
8. **Staged browser module A→D** behind a disabled flag (directives 14, 16).

Nothing above modifies production behavior or enables the experimental model by
default; all of it lives under `scientific-tools/twilight-lut/` and
`src/experimental/` (when created) behind a disabled flag.
