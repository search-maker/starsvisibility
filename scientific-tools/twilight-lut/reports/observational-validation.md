# Observational plausibility validation (feasibility gate)

See script header for provenance caveats: anchors are standard literature values encoded offline; primary sources were unreachable from this environment.

## Zenith luminance vs anchors
- PASS — zenith luminance dep 0 deg: sim 10^2.12 cd/m2 vs anchor 10^2.30 ± 0.45 dex (Koomen 1952 / Rozenberg 1966 zenith luminance at sunset ~1e2..4e2 cd/m2)
- PASS — zenith luminance dep 4 deg: sim 10^0.70 cd/m2 vs anchor 10^0.78 ± 0.55 dex (interpolated Koomen/Rozenberg zenith decay (~1 dex per ~2 deg))
- PASS — zenith luminance dep 8 deg: sim 10^-1.25 cd/m2 vs anchor 10^-1.22 ± 0.65 dex (interpolated Koomen/Rozenberg zenith decay toward ~1e-3 cd/m2 at ~11 deg)

## Zenith decay slope
- PASS — zenith decay slope 4-8 deg vs Patat 2006 (~1 mag/deg, 6-12 deg): sim 1.22 mag/arcsec2/deg vs literature 0.8-1.2 (ranges differ: 4-8 vs 6-12 deg — tolerance widened ±0.25)

## Horizontal illuminance (crude 12-direction quadrature — DIAGNOSTIC)
- DIAGNOSTIC (as expected) — illuminance dep 0 deg (factor-3, crude quadrature): sim 919 lx (10^2.96) vs anchor 10^2.74 ± 0.3 (sunset horizontal illuminance ~400-700 lx)
- DIAGNOSTIC (OFF) — illuminance dep 4 deg (factor-3, crude quadrature): sim 37.8 lx (10^1.58) vs anchor 10^1.08 ± 0.45 (interpolated twilight illuminance curve)
- DIAGNOSTIC (as expected) — illuminance dep 8 deg (factor-3, crude quadrature): sim 0.618 lx (10^-0.21) vs anchor 10^-0.46 ± 0.55 (interpolated twilight illuminance curve)

## Physical sanity checks
- PASS — all resolved radiances finite and positive: 57 cases
- PASS — brightness declines monotonically with depression (12 geometries): failures: none
- PASS — sunward brighter than antisolar at alt 10: dep 0: 5.5x; dep 4: 19.2x; dep 8: 22.0x
- PASS — solar/antisolar contrast grows with depression: monotone growth expected as shadow rises antisolar-first
- PASS — AOD response finite and documented (dep 4, alt 10, sunward): AOD 0.05: 163 cd/m2; AOD 0.15: 110 cd/m2; AOD 0.3: 59 cd/m2

## Summary: 9/9 GATE checks passed; 2/3 diagnostics as expected
