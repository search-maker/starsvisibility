# libRadtran Directional Twilight-Radiance LUT — Feasibility Report

**Milestones 1–2. Branch `claude/twilight-radiance-lut-feasibility-o5vioz`.**
All numbers below are produced by the scripts in `scripts/` from the real
simulation outputs; regenerate `FEASIBILITY_REPORT.json` first, then this prose
never exceeds the data. Companion machine-readable file:
`reports/FEASIBILITY_REPORT.json`.

## 0. Verdict in one paragraph

libRadtran **can** generate physically plausible, numerically stable,
observation-consistent directional twilight radiance over solar depression
0–10° at practical cost, and it converts cleanly into the photopic
luminance / SQM-like quantity the calculator's vision model consumes. **All six
feasibility gates pass.** However, the absolute libRadtran sky is ~1 dex (median
+1.06 dex, up to +1.95 dex) brighter than the calculator's current twilight
component, which would shift the naked-eye limiting magnitude by a median of
2.6 mag (up to 4.8 mag) if swapped in wholesale — and there is **no independent
first-visibility observational dataset** in hand to say whether that shift makes
predictions better or worse. **The recommended next step is Milestone 3 built
around the HYBRID directional-correction model, not the absolute model**, with
production integration explicitly *not* recommended yet. Rationale below.

## 1. Environment and provenance

| Item | Value |
|---|---|
| Solver binary | `uvspec, version 2.0.6-MYSTIC` |
| Provenance | conda-forge `rubin-libradtran` — a real build of the upstream libRadtran 2.0.6 tarball (sha256 `999e47f4…` per feedstock recipe). **Not mocked.** `check_environment.py` prints `ENVIRONMENT: REAL`; every `meta.json` carries `outputIsReal: true`. |
| Data package | `share/libRadtran/data` from the same package |
| Solvers verified | disort, twostr, sdisort, mystic all run |
| Twilight solver used | **MYSTIC backward, `mc_spherical 1D`** (Emde & Mayer 2007) |
| Network caveat | libradtran.org and the primary literature servers (arXiv/ADS/A&A) were blocked (403/timeout) from the build environment; libRadtran obtained via conda-forge, observational anchors encoded offline (see §6). |

## 2. Critical twilight-geometry finding (solver validity)

This is the single most important physical result of the feasibility phase.

- **Plane-parallel and pseudo-spherical DISORT are invalid below the horizon.**
  Directly measured on this machine: DISORT with `pseudospherical`, at SZA 92–98°
  (depression 2–8°), returns **negative radiances** in the antisolar and
  near-zenith directions (e.g. −9.4×10² at SZA 92, phi 180). Setting SZA>90° in
  a (pseudo-)plane-parallel configuration and trusting the result — the naive
  approach the brief warns against — is demonstrably wrong here.
- **MYSTIC 1D-spherical backward is valid.** It produces finite, positive,
  stable radiance for every depression tested, 0–12°. It required `mc_vroom on`
  (spiky aerosol phase function); an on/off spot-check at depression 4° agreed
  within Monte-Carlo error (0.1209 vs 0.1201 mW m⁻² nm⁻¹ sr⁻¹), though uvspec
  itself warns VROOM is "not yet validated for spherical geometry" — flagged as
  an open item.
- **Refraction is not modelled** in this build (no `mc_refraction`), which bends
  the true shadow geometry increasingly past ~6° depression; magnitude
  unquantified — a documented limitation, not a silent assumption.

**Supported domain (evidence-based, not application-driven):** depression
**0–10°** is practical; 0–8° resolves to ≤6% relative error, 9–10° to ~9–13% at
zenith (40M photons), 12° is marginal (~37%). Below-10°-altitude targets and
clouds are out of scope for this phase.

## 3. Feasibility grid and runtime

- **67 cases, 67 ok, 0 failed, 0 statistically unresolved.**
  36-core (dep {0,4,8} × alt {10,30,60,90} × relAz {0,90,180}, AOD 0.15)
  + depression/AOD/altitude/azimuth sensitivity + 2×6 MC-repeat groups
  + 3 deep-depression domain probes.
- Full spectral RT: 41 wavelength nodes 380–780 nm, `mol_abs_param crs`.
- Photon budget scales with depression: 2×10⁶ (dep 0–2) → 4×10⁷ (dep ≥8).
- **Runtime per case: median 39.8 s, max 224 s** (deep + high-photon), total
  1.5 h wall on 4 cores.
- **Raw output: 148 MB** for 67 cases (git-ignored; small fixture committed).
- **Projected 525-cell proof-of-concept grid: ≈10.0 h single-core** (≈2.5 h on
  4 cores) — comfortably practical.

## 4. Numerical stability and Monte Carlo uncertainty

- **Photopic relative uncertainty: median 1.14%, max 37% (only the dep-12
  probe).** Across the core grid it stays ≤ ~8%.
- **Independent-seed repeats** (6 seeds each): at dep 4/alt 30 the empirical
  scatter is 0.8% (mean 8.64 cd/m²); at the noisy dep 8/alt 10/relAz 90 it is
  2.1% (mean 0.173 cd/m²). The empirical-to-reported-σ ratio is **0.69–0.83**,
  i.e. the reported MYSTIC standard errors are *conservative* here (slightly
  overestimate the true scatter) — good, but LUT-node uncertainties should
  still come from repeats, per policy.
- **Fine-vs-node spectral-grid consistency: median 0.32%, max 0.77%** — the
  luminance integral is insensitive to the integration path, so the
  spectral→visual conversion is trustworthy.
- Reproducible-debug (fixed seed) and scientific-validation (independent seeds)
  modes are both implemented. No `log10` is taken of unresolved values.

## 5. Radiometric → visual conversion (unit contract satisfied)

Spectral radiance (mW m⁻² nm⁻¹ sr⁻¹) → CIE 1924 photopic luminance (cd/m²,
Kₘ=683.002) and CIE 1951 scotopic luminance (stored under an explicit scotopic
name, never mislabelled cd/m²) → nanolamberts (1 nL = 3.183×10⁻⁶ cd/m²) →
the calculator's own Krisciunas–Schaefer SQM convention. S/P ratio retained for
a future mesopic model. Independently unit-tested. The one caveat: the
"SQM-equivalent" magnitude uses the calculator's internal KS zero-point, which
is *not* a Vega-calibrated V mag/arcsec² (differs at the ~0.1–0.2 mag level);
comparisons are therefore reported primarily in luminance and log-radiance.

## 6. Independent observational plausibility (9/9 gate checks)

Primary literature servers were unreachable, so anchors are standard,
widely-reproduced literature values encoded offline with generous bands, used
as a **plausibility gate, not a calibration** (none were tuned to the sims).
See `OBSERVATIONAL_VALIDATION.md`.

| Check | Result |
|---|---|
| Zenith luminance, dep 0° | sim 10^2.12 cd/m² vs Koomen/Rozenberg 10^2.30 ± 0.45 — **PASS** |
| Zenith luminance, dep 4° | sim 10^0.70 vs 10^0.78 ± 0.55 — **PASS** |
| Zenith luminance, dep 8° | sim 10^−1.25 vs 10^−1.22 ± 0.65 — **PASS** |
| Zenith decay slope 4–8° | sim 1.22 mag/deg vs Patat 2006 ~1 (0.8–1.2, +0.25 tol) — **PASS** |
| Radiances finite & positive | 57 cases — **PASS** |
| Monotonic dim with depression | 12/12 geometries — **PASS** |
| Sunward brighter than antisolar (alt 10) | 5.5× (dep 0), 19× (dep 4), 22× (dep 8) — **PASS** |
| Contrast grows with depression | monotone — **PASS** |
| AOD response finite/documented | 163→110→59 cd/m² for AOD 0.05→0.15→0.30 (dep 4, alt 10 sunward) — **PASS** |

Diagnostics (not gates): a crude 12-direction illuminance quadrature over-reads
at dep 4 (sim 38 lx vs ~12 lx). This is an inadequate estimator for the
near-sun-concentrated field, **not** a model failure — a proper illuminance
check needs forward-mode irradiance output (Milestone 3). It is reported
transparently rather than hidden or gated on.

The absolute zenith luminances matching Koomen/Rozenberg at three depressions is
the key evidence that **libRadtran's absolute sky brightness is physically
faithful**.

## 7. Current vs hybrid vs absolute (the decisive comparison)

Core grid, seed-0, baseline SQM 21.8, moonless, default observer; NELM through
the calculator's **unchanged** chain (`reports/current-vs-libradtran-comparison.*`,
`reports/model-variant-comparison.*`).

- **Absolute libRadtran is systematically brighter than the current model:**
  median +1.06 dex in twilight nL (range +0.53 to +1.95 dex), i.e. **8–90×**.
  Through the NELM chain that is a **median 2.6 mag, up to 4.8 mag** limiting-
  magnitude change. Since the absolute levels match independent observations
  (§6) while the current model's implied luminance is ~1 dex fainter, the
  current model appears to **under-represent absolute twilight sky luminance**.
- **But the current model is co-calibrated with the NELM formula.** Its twilight
  curve was anchored to naked-eye-limit lore (NELM≈1.5 at dep 6°), not to
  radiometry. A wholesale absolute swap, keeping the NELM formula fixed, would
  move first-visible times by an unknown-correctness 1–5 mag. We have **no
  first-visibility observations** to say that is an improvement. This is exactly
  the "more physical ≠ more accurate for visibility" trap.
- **The directional structure is where libRadtran is both well-validated and
  materially different.** The libRadtran directional ratio R(dir)/R(zenith)
  reaches **21.8× (dep 4) and 42.8× (dep 8)** for the low sunward sky, whereas
  the calculator's `directionalTwilightFactor` maxes at ≈4.9× and has *no*
  depression dependence. The current model substantially **under-represents
  near-sun brightening**, growing worse with depression — the regime that most
  affects early-twilight planet/bright-star visibility near the sun.

## 8. Answers to the eleven required questions

1. **Plausible directional twilight radiance over the domain?** Yes, 0–10°
   depression, alt 10–90°, all relative azimuths, AOD 0.05–0.30 — finite,
   positive, stable, observation-consistent.
2. **Solver/geometry supported per sub-domain?** MYSTIC 1D-spherical backward
   for the whole 0–10° range; DISORT/pseudospherical demonstrated invalid
   below the horizon and unused. 10–12° needs >10⁸ photons; >12° impractical.
3. **Stable enough for a LUT?** Yes — median 1.1% photopic uncertainty,
   conservative reported errors, <0.8% grid-integration consistency.
4. **MC and interpolation uncertainties?** MC quantified (this phase); median
   1.1%, worst-geometry ~2%, deep-probe up to 37%. Interpolation uncertainty is
   Milestone 3 (not yet built).
5. **Agreement with independent observations?** Good on absolute zenith
   luminance (3 depressions), decay slope, and all directional/qualitative
   checks (9/9 gates). Caveat: offline anchors; a primary dataset is still
   required before any accuracy claim.
6. **Does absolute libRadtran outperform the current model?** It is more
   radiometrically faithful to *sky luminance*, but **outperformance for
   visibility is unproven** — no first-visibility data, and the current model is
   co-calibrated with the NELM formula. Do not assume yes.
7. **Does the hybrid outperform both?** Not yet measured on visibility, but the
   hybrid is the **most defensible** candidate: it corrects the well-validated,
   strongly-different directional structure while preserving the current
   absolute normalization that is co-calibrated with NELM. It is also more
   robust when the true atmosphere is only partly known (it cancels the
   normalization that AOD/atmosphere shift most).
8. **How much do the models change first-visible times?** Not computed this
   phase (requires the browser/search integration, Milestone 3+). The
   background-level deltas above (median 2.6, up to 4.8 mag NELM for absolute)
   bound the effect as large for absolute, much smaller and directional for
   hybrid.
9. **Assumptions realistic for available user inputs?** Partly. The calculator's
   only atmospheric user input is a kV estimate / AOD-like proxy; the LUT is
   indexed by AOD550 but represents **one** aerosol family and profile.
   Real-time AOD accuracy, aerosol type, refraction, and clouds are unmodelled.
   This favours the hybrid (ratio) form over the absolute form.
10. **Browser integration practical?** Plausibly (LUT ~10 h to generate, small
    once quantized), but **not built or measured this phase** by instruction.
11. **Production integration recommended?** **No — not yet.** Feasibility passes;
    but observational first-visibility validation, the interpolation error
    budget, the hybrid reference-direction study, and browser performance are
    all still required.

## 9. Recommended exact next implementation step

Proceed to **Milestone 3 with the HYBRID directional-correction model as the
primary candidate**, concretely:

1. Build the expanded but **still moderate** grid over the *evidence-supported*
   domain only: depression {0,2,4,6,8,10}, altitude {10,15,30,45,60,90},
   relAz {0,30,60,90,120,150,180}, AOD {0.05,0.15,0.30}, MYSTIC 1D-spherical,
   photon budget scaled as validated here (~10 h single-core). Do **not** extend
   below 10° altitude or beyond 10° depression without a photon-cost study.
2. Store the LUT as **directional ratios R(dir)/R(zenith)** *and* absolute
   luminance, with per-node uncertainties from independent-seed repeats, so both
   hybrid and absolute variants can be evaluated from one artifact.
3. Settle the **hybrid reference direction** empirically (zenith vs 4π-mean) —
   the one unresolved formulation choice — before any interpolation validation.
4. Add the tested 4-D interpolation library and validate against **independent
   non-grid direct simulations** (new seeds), reporting the full error
   percentile table.
5. **Obtain at least one primary observational dataset** (Patat 2006 tables or a
   calibrated all-sky/SQM twilight log) and redo §6 against it, with a
   train/holdout split, before any accuracy claim.
6. Only then build the disabled-by-default browser prototype and measure size /
   decode / lookup performance.

Do **not** adopt the absolute model as a drop-in replacement, and do **not**
touch production `index.html` behaviour, until first-visibility observations
show the change helps.

## 10. Reproduction

```
python scripts/check_environment.py
python scripts/generate_cases.py
python scripts/run_libradtran.py --jobs 4
python scripts/parse_outputs.py
python scripts/integrate_visual_response.py
python scripts/analyze_monte_carlo_uncertainty.py
python scripts/compare_current_model.py
python scripts/validate_against_observations.py
python scripts/make_sanity_plots.py
python scripts/write_feasibility_report.py
python -m pytest tests/ -q
```
