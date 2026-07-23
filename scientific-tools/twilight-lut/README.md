# Twilight directional sky-radiance LUT experiment (libRadtran)

## The question being investigated

The StarsVisibility calculator predicts when stars first become visible during
twilight. Its physical model already computes solar/stellar/lunar ephemerides,
refraction, airmass, extinction, moonlight (Krisciunas & Schaefer 1991), a
night-sky floor, an NELM-style limiting magnitude, and a **parametric twilight
sky background**: a depression-only brightness curve multiplied by a small
directional factor (`directionalTwilightFactor`, max ≈4.9×, no depression
dependence, uncited constants).

This experiment asks whether a precomputed **libRadtran** directional
twilight-radiance lookup table gives a *scientifically justified and
practically useful* improvement over that parametric component — and only that
component. Everything else in the calculator stays untouched.

**A radiative-transfer model is not automatically more accurate.** Predicted
first-visible times depend at least as strongly on aerosol state, artificial
light, eye adaptation, and the human-threshold model — all of which carry
0.2–0.5 mag-level uncertainties of their own. That is why the work is gated:
each milestone must produce evidence before the next is attempted, and
production integration is *not recommended* until every gate in the project
brief passes, including independent observational validation.

## What exists on this branch (Milestones 1–2)

| Deliverable | File |
|---|---|
| Current-model audit, unit/geometry/combination contracts, integration boundary | `CURRENT_MODEL_ANALYSIS.md` |
| Every atmospheric/visual assumption with status tags | `SCIENTIFIC_ASSUMPTIONS.md` |
| Observational-data assessment + anchor provenance | `OBSERVATIONAL_VALIDATION.md` |
| Install instructions (conda binary path + WSL2 source path) | `INSTALLATION.md` |
| Feasibility results and the go/no-go recommendation | `reports/FEASIBILITY_REPORT.md` (+ `.json`) |
| Comparison tables current/hybrid/absolute | `reports/current-vs-libradtran-comparison.{md,csv}`, `reports/model-variant-comparison.{md,csv}` |
| MC uncertainty from independent seeds | `reports/monte-carlo-uncertainty.{md,json}` |
| Observational plausibility + sanity checks | `reports/observational-validation.{md,json}` |

Not yet built (by design — Milestone 3+ only if feasibility passes):
the expanded 4-D LUT, interpolation library, browser module, and any change to
`index.html`.

## Reproduction

```bash
cd scientific-tools/twilight-lut
pip install -r requirements.txt            # numpy scipy pytest
# install libRadtran (see INSTALLATION.md), then:
export LIBRADTRAN_BIN=/path/to/uvspec
export LIBRADTRAN_DATA=/path/to/share/libRadtran/data

python scripts/check_environment.py        # must print ENVIRONMENT: REAL
python -m pytest tests/ -q                 # unit tests (no libRadtran needed)

python scripts/generate_cases.py           # writes test-cases/feasibility_cases.json
python scripts/run_libradtran.py --jobs 4  # ~40 min on 4 cores; restartable
python scripts/parse_outputs.py
python scripts/integrate_visual_response.py
python scripts/analyze_monte_carlo_uncertainty.py
python scripts/validate_against_observations.py
python scripts/compare_current_model.py
python scripts/write_feasibility_report.py
```

`run_libradtran.py` skips completed cases, records per-case runtime, errors,
seeds, input hashes, uvspec version, and generator commit; use `--overwrite`
to force regeneration. Raw output lands in `raw-output/` (git-ignored except
the committed fixture in `fixtures/`).

## Honesty rules used throughout

- Mocked or fixture data is never represented as real RT output
  (`check_environment.py` prints REAL vs MOCKED; every `meta.json` carries
  `outputIsReal`).
- Monte Carlo values comparable to their own noise are flagged
  `statisticallyResolved: false` and excluded from log-space products.
- Failed or unsupported domains (e.g. solar depression ≥ 9–10°) are reported
  as such, not tuned away.
- The observational comparison in this phase uses offline-encoded literature
  anchors (network policy blocked the primary servers) and is labelled a
  plausibility gate, not a calibration — see `OBSERVATIONAL_VALIDATION.md`.

## Remaining scientific uncertainties (short list)

Aerosol phase function/SSA/vertical profile (one Shettle rural family only),
real-time AOD accuracy, stratospheric aerosol, thin clouds/smoke/dust, ozone
column variation, refraction (absent from this MYSTIC build), polarisation,
VROOM-in-spherical validation status, artificial-light interaction, eye
adaptation and observer experience, known-position vs casual search, and the
absolute calibration of the calculator's SQM-like magnitude convention.
See `SCIENTIFIC_ASSUMPTIONS.md` for the full tagged table.
