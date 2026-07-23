# Primary Data Sources — Milestone 3

This document records the primary, traceable validation sources, what was
obtainable in the build environment, and exactly what remains blocked. The
machine-readable manifest is `validation-data/provenance.json`.

**Environment reality check.** Outbound HTTPS to DOI/arXiv/A&A/Figshare
returned HTTP `000` (blocked by the network policy). `raw.githubusercontent.com`
and `github.com` git-clone were reachable. Nothing below is invented; blocked
numeric tables are marked so and their importers are built and unit-tested
against the historical formats so that transcription is the only missing step.

## 1. Patat, Ugolnikov & Postylyakov 2006 — A&A 455, 385 — PRIMARY (zenith V)

- DOI `10.1051/0004-6361:20064992`, arXiv `astro-ph/0604128`.
- >2000 calibrated UBVRI twilight spectra at ESO Paranal (2640 m).
- **Used:** the reported zenith Johnson V law
  `V(z) = 11.84 + 1.518·(z−95) − 0.057·(z−95)²`, z = solar zenith distance,
  valid z 95–105° (depression 5–15°), V RMS ≈0.18 mag, early slope
  ≈1.14 mag/deg. Encoded in `scripts/patat_reference.py`.
- **Status:** coefficients **transcribed from the Milestone-3 task brief** and
  flagged `NEEDS-PRIMARY-VERIFICATION` — the PDF was not reachable to confirm
  them. `primaryObservationalValidationStatus = PENDING-VERIFICATION`.
- **Matched-comparison requirements met in this milestone:** synthetic Johnson V
  (`scripts/johnson_v.py`, Bessell 1990 passband, Bessell & Murphy 2012 zero
  point), elevation-matched Paranal simulations (2.64 km, Stage 3 hardening),
  Paranal zenith night-sky floor added in flux before comparison.
- **Holdout:** all Patat points are evaluation-only (never used to fit AOD or
  any constant).

## 2. Koomen et al. 1952 — JOSA 42, 353 — PRIMARY (directional ratios)

- DOI `10.1364/JOSA.42.000353`.
- Photopic directional twilight tables at Maryland (~30 m) and Sacramento Peak
  (~2800 m); multiple directions and solar altitudes; Table III oriented-surface
  illumination.
- **Historical-format machinery implemented and tested** (`scripts/koomen_reference.py`):
  candles/ft² → cd/m² (×10.7639) and the compact-decimal parser (`0.0₂56` →
  0.00056).
- **Primary comparison = dimensionless directional ratios within one table**
  (sunward/antisolar, altitude dependence, azimuth dependence, evolution with
  depression, elevation sensitivity), which avoid the historical zero-point
  ambiguity.
- **Status:** numeric tables `BLOCKED` (DOI PDF unreachable). Transcribe to
  `validation-data/koomen_tableN.csv` (columns: `table, solarAltitudeDeg,
  targetAltitudeDeg, relativeAzimuthDeg, luminanceCandlesPerFt2`) to activate
  the ratio comparison. **No page images are committed.**

## 3. Spitschan et al. 2016 — Sci. Rep. 6, 26756 (erratum 46930) — PRIMARY (spectral irradiance) — OBTAINED

- DOI `10.1038/srep26756`; erratum `10.1038/srep46930`; Figshare `2009070.v1`;
  repo `github.com/spitschan/IlluminationSpectraDataset` (MIT license).
- **Obtained via `git clone`** (commit `1d2ecc6…`, 2016-12-16). Rural (DRL) and
  city (CSSP) calibrated spectra, solar elevation −27° to +70°.
- This is **spectral irradiance, not directional radiance** — used only for the
  appropriate tests: spectral evolution with solar elevation, photopic/scotopic
  and S/P trends, forward-mode irradiance/illuminance comparison. It is **not**
  treated as directional radiance.
- **Committed under `validation-data/spitschan2016/`:** the small processed
  `Table1.csv` (per-session solar-elevation ranges, counts), `*_dataquality.csv`,
  and the MIT `LICENSE`. The full 566×3200 spectra CSVs and the MATLAB
  calibration pipeline are **not** committed (size + MATLAB dependency); the
  clone command reproduces them.
- **Holdout:** evaluation-only.

## 4. IPRT Phase III spherical intercomparison — SOLVER validation (not observational)

- Reference spherical-geometry cases (aerosol, vertically inhomogeneous) at
  surface observer altitude, SZA 93°/96°/99°.
- **Status:** `BLOCKED` — the IPRT reference archive was not reachable from the
  build environment. Would validate the MYSTIC configuration against community
  reference results; deferred with the importer stub documented.

## Training / holdout policy

No observational point is used to tune any model constant. AOD and all model
parameters are set from documented libRadtran configuration, never fitted to
Patat/Koomen/Spitschan. All primary points are therefore holdout/evaluation.
The hybrid-reference study (Stage 4) selects a normalization using **simulation
structure and the current model's own calibration meaning**, with Koomen ratios
(once transcribed) as an independent check — documented explicitly there.
