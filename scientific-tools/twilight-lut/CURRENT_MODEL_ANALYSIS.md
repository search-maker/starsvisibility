# Current Model Analysis — StarsVisibility Twilight Sky Background

**Milestone 1 deliverable.** Audit of the existing star-visibility calculator
(`index.html`, single-file application, ~20,750 lines) performed by direct source
inspection on branch `claude/twilight-radiance-lut-feasibility-o5vioz`
(base commit `c9a48a6`). All line numbers refer to that revision of `index.html`.

---

## 1. Repository structure

```
starsvisibility/
├── index.html                        # entire application (HTML+CSS+JS, ~3.0 MB)
├── README.md
├── SCIENTIFIC_MODEL_REVIEW.md        # prior scientific-review notes
├── favicon.png
├── star-visibility-guide.pdf
└── star-visibility-guide-english.pdf
```

There is no build system, no JS modules, no test framework in the repository.
The application is a single self-contained HTML file that embeds:

- the full Yale Bright Star (BSC5-derived) catalog as JS arrays (~lines 3300–14200);
- all astronomy/physics code (~lines 14200–17000);
- UI, workers (annual "Three-Star" worker re-executes the same script with a fake
  DOM), CSV export, and help text (~lines 17000–20748).

The annual worker deliberately re-runs the *same* script so both paths use
identical physics (`SCIENTIFIC_MODEL_REVIEW.md`, "Three-Star annual worker
architecture"). Any change to the physics functions therefore automatically
affects both interactive and worker paths — a key regression-safety fact.

## 2. Where each quantity is computed

| Quantity | Function / location | Line |
|---|---|---|
| Solar RA/Dec, alt/az | `sunRaDec`, `altAzAtLst`, used in `computeSunMoon` | ~15752 |
| Sun apparent altitude | `apparentAltitude(sun.alt)` | 15756 |
| Solar depression (used everywhere) | `sunDep = -sun.alt` (TRUE/geometric) | 15772–15780 |
| Star alt/az | `altAzAtLst(lst, lat, ra, dec)` (precession/PM handled upstream) | — |
| Star apparent altitude | `apparentAltitude(hTrue)` = hTrue + Saemundsson refraction | 14249 |
| Refraction | `refractionDeg(hTrue)`, Saemundsson, pressure/temperature scaled | 14241 |
| Sun–star angular separation | `angularSeparation(alt1,az1,alt2,az2)` — spherical law of cosines on **true** altitudes | 14219 |
| Air mass | `airMass(hApp)` — Kasten & Young (1989), clamped to 40 below −2° | 14254 |
| Extinction → effective magnitude | `effectiveVisualMagnitude` : `m + kV·max(0, X−1) + colorCorrection` | 14307 |
| Color correction | `colorCorrectionTerms` (B−V Purkinje term + 2nd-order extinction, capped ±0.35 mag) | 14270 |
| Twilight sky brightness | `twilightExcessNL` / `twilightExcessNLCalibrated` × `directionalTwilightFactor` | 14968, 14997, 15006 |
| Moonlight | `moonBrightnessNL` — Krisciunas & Schaefer (1991) | 15017 |
| Natural night background | baseline SQM (`baselineSqm`/`sqmZenith`) → nL, plus airmass horizon brightening | 15047–15053 |
| Artificial light | **implicit in baseline SQM** (site SQM/Bortle/directional SQM map); no separate additive term |  |
| Total sky brightness | `localSkyBrightnessComponents(p)` | 15034 |
| Limiting magnitude | `limitingMagnitudeFromSkyBrightness(p)` | 15143 |
| Observer bonus | `getObserverBonusMag` (0 / 0.60 / 1.10 mag, added to limit) | 14300 |
| Visibility decision | `evalPhysical`: `visible = magEff <= originalLimit + observerBonus` | 15767–15813 |
| First-visible time | coarse scan at `step`, then `refineBoundary` bisection (24 iters or <5 s) | 16088 |
| Empirical comparison model | `evalEmpirical` (depression law `5.0 + 1.05·mag`, near-Sun penalty) | 15832 |

## 3. Complete data flow (physical model)

```
date/location/settings
  → computeSunMoon(t):     sun alt/az (true), sun.appAlt; moon alt/az/illum
  → per star at time t:
      starAppAlt   = starTrueAlt + Saemundsson refraction     [deg]
      sunDep       = −sunTrueAlt   (TRUE geometric depression) [deg]
      sunSep       = angularSeparation(star, sun)  (true alts) [deg]
      magEff       = mag + kV·max(0, X(starAppAlt) − 1) + colorCorr   [mag]
      skyBaseline  = resolveSkyBaseline(az, alt)  → baselineSqm [mag/arcsec²]
      components   = localSkyBrightnessComponents({...})       [nL internally]
      limitMag     = limitingMagnitudeFromSkyBrightness(...) + observerBonus [mag]
      visible      = magEff ≤ limitMag
  → coarse time scan (step) → refineBoundary bisection → first-visible time
```

### 3.1 `localSkyBrightnessComponents` in detail (lines 15034–15074)

All brightness components are combined **linearly in nanolamberts (nL)** and
converted to mag/arcsec² only at the end:

```
Bdark  = nLFromMag(baselineSqm)                       # night-sky floor incl. light pollution
Bdark *= 1 + 0.4·max(0, X(starAppAlt) − 1)            # horizon brightening (skipped when
                                                      #   baseline is directional or manual)
baseSkySqm = magFromNL(Bdark)
BtwiBase = twilightExcessNLCalibrated(sunDep, baseSkySqm, calibrationRows)   # zenith-ish reference
Btwi     = BtwiBase · directionalTwilightFactor({sunStarSeparationDeg, starAppAltDeg})
Bmoon    = moonBrightnessNL(moonAlt, illum, moonSep, starAppAlt, kV)         # K&S 1991
skyBrightnessMagArcsec2 = magFromNL(Bdark + Btwi + Bmoon)
```

Special mode: `skyBrightnessMode === "live-total"` short-circuits everything and
uses a measured total SQM directly (twilight and moon set to 0 — the measurement
already contains them).

### 3.2 The twilight curve (lines 14900–15004)

`twilightExcessNL(sunDepDeg, baselineSqm)` returns the **twilight excess above
the dark-sky floor, in nL**, as a function of solar depression only:

- **d < 0** (Sun up): constant `1e8` nL (daylight saturation placeholder).
- **0 ≤ d ≤ 6**: piecewise-linear in log10(nL) through anchors
  `[0, 6.6689], [3, 5.4580], [6, 4.4253]` ("legacy calibration").
- **6 < d ≤ 12**: total sky SQM darkens at 0.95 mag/arcsec² per degree from the
  d=6 total (`TWILIGHT_SQM_AT_6`); excess = totalNL − baseNL.
- **12 < d < 16**: smoothstep blend of the total SQM toward the local base SQM.
- **d ≥ 16**: excess = 0. (18° anchor of the legacy curve tapers with (1−frac)³.)

The curve is a **calibration, not a measurement** (stated in-source, line 14907)
and is **monotonically decreasing in d by construction**.
An external "twilight calibration CSV" (`sunDepressionDeg, skyBrightnessMagArcsec2`)
overrides the built-in curve via `twilightExcessNLCalibrated`, which interpolates
the *measured total* linearly **in nL** between rows and subtracts the dark floor.

### 3.3 The directional twilight factor (lines 15006–15012)

```js
function directionalTwilightFactor(p) {
  const sep = max(0, p.sunStarSeparationDeg);   // Sun–target angular separation, deg
  const h   = max(0, p.starAppAltDeg);          // target apparent altitude, deg
  const separationFactor = 1 + 1.8·exp(−sep/28);
  const altitudeFactor   = 1 + 0.75·exp(−h/18);
  return separationFactor · altitudeFactor;     // range ≈ 1.0 … 4.9
}
```

**The existing model IS directional**, but only weakly and parametrically:

- depends on Sun–target *angular separation* (not on relative azimuth and target
  altitude independently — the two are conflated through separation);
- depends on target apparent altitude;
- does **not** depend on solar depression (the same directional pattern is used
  at d=1° and d=15°, where real twilight anisotropy differs strongly);
- multiplier never goes below 1 and never above ≈4.9× — real solar/antisolar
  contrast at low Sun depression can exceed a factor of 10–30 near the horizon;
- the constants (1.8, 28, 0.75, 18) are empirical with no cited source.

**This factor, together with the depression-only excess curve, is the exact
quantity the LUT experiment targets.**

### 3.4 Limiting-magnitude model (lines 15143–15151)

```
NELM = 7.93 − 5·log10(10^(4.316 − sb/5) + 1)      # sb = total mag/arcsec²
     + 2.5·log10(max(0.3, pupilMm/7))
     − 0.02·max(0, age − 25)
     + 2.5·log10(max(0.5, acuity))
     − (1 − darkAdaptation)
```

The first term is the Schaefer-style NELM-vs-sky-brightness relation (as used in
Bortle/SQM conversions). Its **only input is the scalar total sky brightness in
mag/arcsec² (V band, SQM-like)**. This defines the unit contract for any
replacement background.

## 4. Unit contract

| Boundary | Unit | Notes |
|---|---|---|
| Baseline sky input | mag/arcsec² (SQM, V-band-like) | from user SQM, Bortle→SQM (`bortleToSQM`), sky preset (`SKY_SQM`), or directional SQM map |
| Internal accumulation | nanolamberts (nL) | `nLFromMag(sb) = 34.08·exp(20.7233 − 0.92104·sb)`; `magFromNL(b) = (20.7233 − ln(max(b,1e-3)/34.08))/0.92104` — Krisciunas & Schaefer (1991) eq. 1–2 |
| Twilight excess | nL | linear, additive |
| Moon brightness | nL | K&S91 formulation natively in nL |
| Output to vision model | mag/arcsec² | via `magFromNL` |
| Stellar magnitudes | Johnson V (catalog), mag | extinction in mag/airmass (kV) |
| Angles | degrees everywhere in the physics layer | `toRad`/`toDeg` at trig call sites |
| Time | ms since epoch; JD internally for ephemerides | |

Useful physical equivalences (needed by the LUT pipeline):

- 1 nL = 10⁻⁹ lambert = (10⁻⁵/π) cd/m² ≈ **3.1831×10⁻⁶ cd/m²**.
- `magFromNL`/`nLFromMag` imply mag/arcsec² 21.8 ≈ 0.000171 cd/m² —
  consistent with the standard `L[cd/m²] ≈ 10.8×10⁴ · 10^(−0.4·SQM)` within the
  K&S approximation (few-% level; the pair is exactly self-inverse, which is what
  matters for internal consistency).
- The clamp `max(b, 1e-3)` in `magFromNL` caps representable darkness at
  ≈ mag 26.9/arcsec² — irrelevant in practice.

**The V-band/SQM system is photopic-luminance-like.** The LUT must therefore
deliver (or be convertible to) a photopic-weighted V-like surface brightness in
mag/arcsec² (equivalently a luminance) for drop-in compatibility. Scotopic and
S/P outputs are additional science products, not the integration quantity.

## 5. Geometry contract

- **Azimuth convention:** astronomical, degrees, computed by `altAzAtLst` (N=0°,
  E=90°, i.e. clockwise from north — verified from the `atan2` form used).
- **Solar depression:** TRUE (geometric) solar altitude negated
  (`sunDep = −sunTrueAlt`, line 15772). Explicit in-source comment (15774–15779):
  twilight timing intentionally uses the geometric Sun, matching the standard
  civil/nautical/astronomical definitions. **The LUT axis must therefore be
  geometric solar depression.**
- **Target altitude for airmass and the directional factor:** APPARENT
  (refracted) altitude, Saemundsson.
- **Sun–star separation:** computed from TRUE altitudes of both bodies
  (`angularSeparation(s.alt, s.az, sm.sun.alt, sm.sun.az)`, line 15773).
- **Relative azimuth:** available as `azimuthDifference(az1, az2)` (line 14225),
  smallest difference, range 0–180°, used only for display (`azDiff`) in the
  empirical model — the physical model uses total separation only.
- Refraction: applied to star and Moon; **not** applied to the Sun for twilight
  purposes (by design).

## 6. Physical vs. empirical/parametric classification

| Component | Class | Source |
|---|---|---|
| Ephemerides (Sun/Moon/stars) | physical | Meeus algorithms |
| Refraction | physical (standard approx.) | Saemundsson |
| Airmass | physical (empirical fit) | Kasten & Young 1989 |
| Extinction kV | empirical estimate | site table / weather heuristics |
| nL↔mag conversions | physical convention | K&S 1991 |
| Moon brightness | published empirical model | K&S 1991 |
| **Twilight excess curve** | **calibration (parametric)** | in-house anchors + 0.95 mag/deg post-6° (motivated by Patat et al. 2006) |
| **Directional twilight factor** | **parametric, uncited** | in-house |
| NELM(sb) | published empirical | Schaefer-style |
| Observer terms | empirical | in-house |
| Empirical comparison model | empirical | in-house depression law |

## 7. Exact experimental integration boundary

**Replace/augment exactly one product:**

```
Btwi = twilightExcessNLCalibrated(sunDep, baseSkySqm, rows) · directionalTwilightFactor(p)
```

i.e. the **solar-twilight excess in nL at the target direction**, inside
`localSkyBrightnessComponents`. Everything else (Bdark incl. its airmass
brightening, Bmoon, magFromNL, NELM, observer terms, search logic) stays
unchanged.

Component-combination contract (verified, no double counting at this boundary):

```
totalNL = BdarkNL(baseline SQM, incl. light pollution & horizon brightening)
        + BtwilightNL(solar twilight ONLY — the LUT quantity)
        + BmoonNL(K&S91)
skyBrightnessMagArcsec2 = magFromNL(totalNL)
```

Therefore the LUT quantity must be **twilight-only** radiance:
- **no moonlight** (handled by `moonBrightnessNL`);
- **no airglow / starlight / zodiacal light night floor** (handled by baseline
  SQM). A libRadtran run with the Sun as the only source naturally satisfies
  this — but the simulated *total* radiance at large depressions approaches
  zero, whereas the observed sky approaches the night floor; the subtraction
  convention must be documented in the LUT metadata;
- **no artificial light** (inside baseline SQM);
- extinction of the *star* stays on the star (magEff) — the sky background never
  includes it (explicit in-source comment, lines 15030–15033).

Double-counting risks identified:

1. **Night floor at large depressions.** The current curve forces excess → 0 at
   d ≥ 16°. An *absolute* LUT model must likewise deliver only the solar excess;
   since a Sun-only RT calculation contains no airglow, this is automatic, but
   near d≈16–18° the RT excess and the observational "twilight" both fade into
   the airglow floor and the comparison must be done in total (floor-added) space.
2. **Horizon brightening.** `Bdark` is multiplied by `1 + 0.4·(X−1)`; that models
   airglow/light-pollution slant-path brightening, not twilight, so it is not a
   double count — but a LUT that included a "background" atmosphere glow would be.
3. **live-total SQM mode** bypasses the boundary entirely; the LUT must be
   inactive in that mode.
4. **External twilight calibration CSV** replaces the built-in curve; interaction
   with the LUT (hybrid normalization source) must be defined — in the
   experiment, the hybrid reference is whatever `twilightExcessNLCalibrated`
   returns, so the CSV continues to work.

## 8. What must remain unchanged

Ephemerides, refraction, airmass, extinction/magEff, color correction, Moon
model, baseline-SQM logic incl. directional SQM maps, NELM and observer terms,
empirical comparison model, time search, annual/weekly views, CSV export, all
UI defaults and labels. The annual worker re-executes the same script, so a
boundary-respecting change automatically propagates; no separate worker change
is needed (and none is planned in the feasibility phase).

## 9. Uncertainties in the current implementation

- Twilight anchors 0–6° are an in-house calibration with unstated uncertainty;
  the post-6° slope 0.95 mag/deg is literature-motivated (Patat 2006 reports
  ≈1 mag/deg in V between d=6–12°) but the absolute level at d=6° is anchored to
  NELM≈1.5 lore, not radiometry.
- The directional factor's constants are unsourced; its maximum brightening
  (≈4.9× at sep=0, h=0) is likely far too small near the horizon at small
  depressions and possibly too large at d>12° where the factor still applies
  at full strength (no depression dependence).
- `1e8` nL daylight placeholder for d<0 is a saturation hack (≈ mag −0.9/arcsec²);
  fine for "not visible in daylight" but not radiometric.
- kV estimates are heuristics; kV is also reused for lunar extinction.
- NELM formula, pupil/age/acuity/adaptation terms each carry ≥0.2–0.5 mag of
  systematic uncertainty (acknowledged in app help text).

## 10. Three-candidate-model comparison plan (Milestone ≥2)

Identical inputs `(sunDepressionDeg, targetAppAltDeg, relativeAzimuthDeg, aod550, baselineSqm)`
for all three:

- **A. Current:** `Btwi_A = twilightExcessNL(d, baseSqm) · directionalTwilightFactor(sep, h)`.
- **B. Hybrid:** `Btwi_B = twilightExcessNL(d, baseSqm) · R_LUT(d, h, Δaz, aod) / R_LUT(d, ref, ·, aod)`
  with a documented reference direction (candidate: zenith, since the current
  curve is calibrated against zenith-ish SQM measurements; to be tested in
  Milestone 2 against the alternative "4π-mean" normalization).
- **C. Absolute:** `Btwi_C = nLFromCdM2(L_LUT_photopic(d, h, Δaz, aod))`,
  where `nL = cd/m² / 3.1831×10⁻⁶`.

Comparison metrics, in order: (1) background brightness in log-nL and
mag/arcsec² on a case grid; (2) implied limiting magnitude via the *unchanged*
NELM chain; (3) implied visibility margins for representative magnitudes;
(4) (Milestone 3+) first-visible times through the real search.

Gate to proceed to Milestone 3: libRadtran produces finite, positive, stable,
physically plausible directional twilight radiance over a documented depression
range, convertible to V-like luminance, at practical runtime.
