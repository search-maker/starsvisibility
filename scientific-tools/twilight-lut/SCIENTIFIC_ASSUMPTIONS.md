# Scientific Assumptions — twilight-LUT feasibility phase

Every choice below is tagged **[fixed]** (documented, deliberate),
**[uncertain]** (plausible but unvalidated — must be revisited before any
production claim), or **[limitation]** (known missing physics).

## Radiative-transfer configuration

| Item | Value | Status / source |
|---|---|---|
| libRadtran version | 2.0.6 (`uvspec, version 2.0.6-MYSTIC`) | [fixed] conda-forge `rubin-libradtran` build; upstream tarball sha256 `999e47f4…` per feedstock recipe |
| Data package | the `share/libRadtran/data` tree shipped in the same package | [fixed] |
| Solver (twilight domain) | MYSTIC, backward, `mc_spherical 1D` (Emde & Mayer 2007) | [fixed] — plane-parallel & pseudo-spherical DISORT produce negative/invalid radiances at SZA>90°, verified on this machine |
| Variance reduction | `mc_vroom on` | [uncertain] — uvspec warns "vroom not yet validated for spherical geometry"; on/off agree within MC errors in our dep-4 check (0.1209 vs 0.1201 mW m⁻² nm⁻¹ sr⁻¹ ± ~1%), but only spot-checked |
| Photon budget | 2×10⁶ (dep 0–2), 8×10⁶ (dep 4), 2×10⁷ (dep 6), 4×10⁷ (dep ≥8), total per spectral case | [fixed] from measured 1/√N convergence |
| Atmosphere profile | AFGL US Standard (`afglus.dat`) | [uncertain] — one profile only; no seasonal/latitudinal variation in the feasibility phase |
| Ozone column | profile default (≈345 DU reported by verbose run) | [uncertain] — Chappuis absorption shapes twilight blue; column not varied |
| Aerosol | `aerosol_default`: Shettle rural boundary layer, background above, spring–summer, then `aerosol_modify tau550 set {0.05, 0.15, 0.30}` | [uncertain] — ONE aerosol family and vertical profile. A LUT axis labelled `aod550` represents *this family only*, not every atmosphere with that AOD |
| Aerosol phase function / SSA / g | as implied by the Shettle model files shipped with libRadtran | [uncertain] — not independently varied |
| Ångström exponent | not applied (tau550 scaling only, spectral slope from the aerosol model) | [uncertain] |
| Surface albedo | 0.15, Lambertian, wavelength-independent | [uncertain] |
| Observer elevation / pressure | sea level (`zout 0`), profile pressure | [fixed] feasibility scope |
| Clouds | none (clear-sky only) | [limitation] |
| Wavelength grid | 380–780 nm, 10 nm steps (41 points), `mol_abs_param crs` (Rayleigh + O3/NO2 cross-sections; no O2/H2O line absorption) | [uncertain] — O2-A/B and H2O bands are neglected; their V(λ) weight is small (V<0.01 beyond 690 nm) but unquantified here |
| Extraterrestrial spectrum | `atlas_plus_modtran` (energy units, mW m⁻² nm⁻¹) | [fixed] |
| Refraction | **not modelled** (no `mc_refraction` in this build) | [limitation] — bends the effective shadow geometry; largest effect at dep ≳6°; magnitude unquantified here |
| Earth radius | default 6370 km | [fixed] |
| Polarisation | off | [limitation] — affects radiance ~% level via Rayleigh polarisation |
| Radiance convention | `umu<0` ground sensor looking up; umu=−sin(target altitude); `phi−phi0` = relative azimuth, phi=phi0 looks toward the Sun (verified empirically: sunward sky brightest) | [fixed] manual + empirical check |
| Solar depression | geometric (SZA = 90° + depression); matches the calculator's true-Sun convention | [fixed] |
| Output units | mW m⁻² nm⁻¹ sr⁻¹ (energy radiance) | [fixed] |

## Visual integration

| Item | Value | Status |
|---|---|---|
| Photopic weighting | CIE 1924 V(λ), 10 nm tabulation, Km = 683.002 lm/W | [fixed] |
| Scotopic weighting | CIE 1951 V′(λ), K′m = 1700.06 lm/W, stored as `scotopicLuminanceScotCdM2` (scotopic cd/m², explicitly NOT ordinary cd/m²) | [fixed] |
| Integration | rectangle rule on the uniform 10 nm grid | [fixed] |
| Mesopic model | none — S/P ratio stored to enable one later | [limitation] |
| nL conversion | 1 nL = 3.1830989×10⁻⁶ cd/m² | [fixed] |
| "SQM-equivalent" | via the calculator's own Krisciunas–Schaefer pair `mag = (20.7233 − ln(nL/34.08))/0.92104` | [fixed] as an internal convention; **not** a Vega-calibrated V mag/arcsec² — the V-band zero point differs from the photopic-luminance zero point at the ~0.1–0.2 mag level depending on spectrum |
| MC uncertainty propagation | per-λ standard errors treated as independent; luminance σ from quadrature sum; **repeat-seed analysis overrides** the reported σ where they disagree | [fixed] |

## Known unresolved choices

- Hybrid-model reference direction: zenith adopted for feasibility (the
  calculator's twilight curve is calibrated against zenith-ish SQM values);
  the 4π-mean alternative was not tested. [uncertain]
- Night-sky floor subtraction convention: libRadtran output is solar-only, so
  the LUT quantity is intrinsically twilight-only; near dep 8–10° the excess
  approaches the airglow floor and comparisons must be floor-added. [fixed]
- The LUT domain limit (dep ≈ 8–9°) is an evidence-based solver/noise limit,
  not the application's desired limit. [fixed]
