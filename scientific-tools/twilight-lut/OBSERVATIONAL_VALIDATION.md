# Observational Validation — data assessment (Milestone 2)

## Status

**No machine-readable calibrated observational dataset could be downloaded in
this environment.** The session's network policy blocks the primary literature
servers (verified during the run: `arxiv.org`, `ui.adsabs.harvard.edu`,
`aanda.org`, `articles.adsabs.harvard.edu` all unreachable/403, as is
`libradtran.org` itself). Milestone 2 therefore uses **literature anchor
values encoded offline** (below), each with a generous uncertainty band, and
the comparison is a *plausibility gate*, not a calibration. This is stated
prominently in the feasibility report; Milestone 3+ requires obtaining at
least one primary dataset.

## Datasets assessed for later milestones

| Dataset | What it provides | Feasibility use | Blocked/needed |
|---|---|---|---|
| Patat, Ugolnikov & Postylyakov 2006, A&A 455, 385 (UBVRI twilight at ESO Paranal) | calibrated V mag/arcsec² zenith twilight vs solar depression, 6–12° | decay-slope anchor ~1 mag/deg (the repo's own SCIENTIFIC_MODEL_REVIEW.md adopts 0.95) | need the paper's tables to compare absolute levels |
| Koomen et al. 1952, JOSA 42, 353 (Sacramento Peak twilight photometry) | calibrated zenith + directional twilight luminance, 0–18° | order-of-magnitude zenith-luminance anchors | need digitized curves |
| Rozenberg 1966, *Twilight: A Study in Atmospheric Optics* | canonical zenith brightness table spanning ~7 decades | same | book tables |
| Explanatory Supplement to the Astronomical Almanac (twilight illuminance) | horizontal illuminance vs depression (sunset ≈ 400–700 lx; civil dusk ≈ 3.4 lx; nautical dusk ≈ 8×10⁻³ lx) | crude illuminance quadrature test | canonical values, low risk |
| Spitschan et al. 2016, Sci. Rep. 6, 26756 (twilight spectral irradiance) | measured twilight spectra incl. Chappuis-band blue | future spectral-shape validation | data files |
| SQM twilight logs (e.g. Unihedron community data) | site SQM vs depression | future absolute check of the KS-convention magnitudes | none fetched |

For each dataset used in a later milestone the full metadata table required by
the project brief (instrument, calibration, bandpass, solar geometry, aerosol
state, cloud screening, license, transformations) must be filled in **before**
fitting anything to it, and part of the data must be held out from any tuning.

## Anchor values actually used in `validate_against_observations.py`

| Quantity | Anchor | Band | Source tag |
|---|---|---|---|
| Zenith luminance, dep 0° | 10^2.3 cd/m² ± 0.45 dex | photopic | Koomen/Rozenberg |
| Zenith luminance, dep 4° | 10^0.78 cd/m² ± 0.55 dex | photopic | interpolated Koomen/Rozenberg |
| Zenith luminance, dep 8° | 10^−1.22 cd/m² ± 0.65 dex | photopic | interpolated Koomen/Rozenberg |
| Zenith decay slope 4–8° | 0.8–1.2 mag/arcsec²/deg (±0.25 tolerance for the 4–8 vs 6–12 range mismatch) | V-like | Patat 2006 |
| Horizontal illuminance dep 0/4/8° | 550 / 12 / 0.35 lx, ±0.30/0.45/0.55 dex | photopic | Expl. Suppl. + interpolation |
| Directional pattern | sunward > antisolar; contrast grows with depression | — | qualitative, all twilight literature |

Anchors marked "interpolated" are log-linear interpolations between canonical
points and carry the widest bands. **None of these numbers were tuned against
the simulation output.**

## Independence policy

The anchors above are used once, as a pass/fail gate. If any future
calibration experiment adjusts model constants against observational data,
that data must be split into training and holdout sets and this file must
record the split.
