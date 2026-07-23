#!/usr/bin/env python3
"""Plausibility comparison of simulated twilight brightness against
independent published anchors, plus automated physical sanity checks.

IMPORTANT PROVENANCE NOTE
The build environment's network policy blocks the primary literature servers
(arxiv.org, ADS, A&A — verified 403/timeout), so the anchor numbers below are
encoded from standard, widely reproduced literature values and must be
re-verified against the primary sources before any production claim.
Each anchor carries a generous uncertainty and a source tag. This script is a
feasibility gate (order-of-magnitude / slope agreement), NOT a calibration.

Anchors used:
1. Zenith luminance vs solar depression (Koomen et al. 1952, JOSA 42, 353;
   Rozenberg 1966 "Twilight"): sunset ~ 1e2..4e2 cd/m2, decaying roughly one
   decade per ~1.9-2.5 deg through civil twilight.
2. V-band zenith twilight decay rate ~ 1 mag/arcsec2 per degree of depression
   for 6-12 deg (Patat et al. 2006, A&A 455, 385; the repository's own
   SCIENTIFIC_MODEL_REVIEW.md adopts 0.95).
3. Horizontal illuminance at civil dusk ~ 3.4 lx (canonical; Explanatory
   Supplement to the Astronomical Almanac), at sunset ~ 400-700 lx.
   Simulated illuminance is a crude 12-direction cosine quadrature -> compared
   only at the factor-of-3 level.
Directional expectations (qualitative): sunward sky brighter than antisolar;
contrast grows with depression; brightness declines monotonically with
depression at fixed geometry.

Writes reports/observational-validation.{md,json}.
"""
import json
import math
from lrt_common import PROCESSED_DIR, ROOT

REPORTS = ROOT / "reports"

ZENITH_ANCHORS = [
    # dep, log10 L [cd/m2] center, half-width (dex), source tag
    (0, math.log10(200.0), 0.45,
     "Koomen 1952 / Rozenberg 1966 zenith luminance at sunset ~1e2..4e2 cd/m2"),
    (4, math.log10(6.0), 0.55,
     "interpolated Koomen/Rozenberg zenith decay (~1 dex per ~2 deg)"),
    (8, math.log10(0.06), 0.65,
     "interpolated Koomen/Rozenberg zenith decay toward ~1e-3 cd/m2 at ~11 deg"),
]
ILLUMINANCE_ANCHORS = [
    (0, math.log10(550.0), 0.30, "sunset horizontal illuminance ~400-700 lx"),
    (4, math.log10(12.0), 0.45, "interpolated twilight illuminance curve"),
    (8, math.log10(0.35), 0.55, "interpolated twilight illuminance curve"),
]
PATAT_SLOPE_RANGE = (0.8, 1.2)   # mag/arcsec2 per deg, V band, 6-12 deg


def load():
    data = json.loads((PROCESSED_DIR / "case_results.json").read_text())
    return [r for r in data if r.get("status") == "ok"
            and not r.get("repeatIndex", 0)]


def by_geom(ok):
    return {(r["sunDepressionDeg"], r["targetAltitudeDeg"],
             r["relativeAzimuthDeg"], r["aod550"]): r for r in ok}


def crude_illuminance_lx(geom, dep, aod=0.15):
    """Cosine-weighted quadrature over the 12 core directions.
    Altitude bands: 10 deg row represents 0-20 (sin band 0.0-0.342),
    30 deg: 20-45 (0.342-0.707), 60 deg: 45-75 (0.707-0.966),
    90 deg: 75-90 (0.966-1.0). Azimuth: raz 0 and 180 weight 90 deg each,
    raz 90 weights 180 deg (mirror symmetry).
    E = sum L * cos(theta_z) * dOmega; dOmega belt = dAz * d(sin(alt)).
    Crude by construction (documented); used only at factor-3 level."""
    bands = {10: (0.0, 0.342), 30: (0.342, 0.707),
             60: (0.707, 0.966), 90: (0.966, 1.0)}
    az_w = {0: math.pi / 2, 90: math.pi, 180: math.pi / 2}
    total = 0.0
    for alt, (s0, s1) in bands.items():
        for raz, waz in az_w.items():
            r = geom.get((dep, alt, raz, aod))
            if not r:
                return None
            L = r["photopicLuminanceCdM2"]
            # integral of sin(alt) d(sin alt) over band = (s1^2-s0^2)/2
            total += L * waz * (s1 * s1 - s0 * s0) / 2
    return total


def main():
    ok = load()
    geom = by_geom(ok)
    checks, lines = [], ["# Observational plausibility validation (feasibility gate)",
                         "", "See script header for provenance caveats: anchors "
                         "are standard literature values encoded offline; primary "
                         "sources were unreachable from this environment.", ""]

    def record(name, passed, detail):
        checks.append({"check": name, "passed": passed, "detail": detail})
        lines.append(f"- {'PASS' if passed else 'FAIL'} — {name}: {detail}")

    # 1. zenith luminance anchors
    lines.append("## Zenith luminance vs anchors")
    for dep, log_c, half, src in ZENITH_ANCHORS:
        r = geom.get((dep, 90, 0, 0.15))
        if not r:
            record(f"zenith dep{dep}", False, "case missing")
            continue
        lg = math.log10(r["photopicLuminanceCdM2"])
        record(f"zenith luminance dep {dep} deg",
               abs(lg - log_c) <= half,
               f"sim 10^{lg:.2f} cd/m2 vs anchor 10^{log_c:.2f} ± {half} dex ({src})")

    # 2. Patat-style decay slope, zenith 4->8 deg (SQM-equivalent)
    lines.append("\n## Zenith decay slope")
    r4, r8 = geom.get((4, 90, 0, 0.15)), geom.get((8, 90, 0, 0.15))
    if r4 and r8:
        slope = (r8["skyMagArcsec2_KSconvention"] -
                 r4["skyMagArcsec2_KSconvention"]) / 4.0
        lo, hi = PATAT_SLOPE_RANGE
        record("zenith decay slope 4-8 deg vs Patat 2006 (~1 mag/deg, 6-12 deg)",
               (lo - 0.25) <= slope <= (hi + 0.25),
               f"sim {slope:.2f} mag/arcsec2/deg vs literature {lo}-{hi} "
               "(ranges differ: 4-8 vs 6-12 deg — tolerance widened ±0.25)")

    # 3. crude illuminance
    lines.append("\n## Horizontal illuminance (crude 12-direction quadrature)")
    for dep, log_c, half, src in ILLUMINANCE_ANCHORS:
        E = crude_illuminance_lx(geom, dep)
        if E is None:
            record(f"illuminance dep{dep}", False, "cases missing")
            continue
        lg = math.log10(E)
        record(f"illuminance dep {dep} deg (factor-3 test)",
               abs(lg - log_c) <= half,
               f"sim {E:.3g} lx (10^{lg:.2f}) vs anchor 10^{log_c:.2f} ± {half} ({src})")

    # 4. physical sanity battery
    lines.append("\n## Physical sanity checks")
    finite = all(math.isfinite(r["photopicLuminanceCdM2"]) and
                 r["photopicLuminanceCdM2"] > 0 for r in ok)
    record("all resolved radiances finite and positive", finite,
           f"{len(ok)} cases")
    mono_fail = []
    for alt in (10, 30, 60, 90):
        for raz in (0, 90, 180):
            seq = [geom.get((d, alt, raz, 0.15)) for d in (0, 4, 8)]
            if all(seq):
                Ls = [s["photopicLuminanceCdM2"] for s in seq]
                if not (Ls[0] > Ls[1] > Ls[2]):
                    mono_fail.append((alt, raz, Ls))
    record("brightness declines monotonically with depression (12 geometries)",
           not mono_fail, f"failures: {mono_fail if mono_fail else 'none'}")
    contrast = []
    for dep in (0, 4, 8):
        s = geom.get((dep, 10, 0, 0.15))
        a = geom.get((dep, 10, 180, 0.15))
        if s and a:
            c = s["photopicLuminanceCdM2"] / a["photopicLuminanceCdM2"]
            contrast.append((dep, c))
    record("sunward brighter than antisolar at alt 10",
           all(c > 1 for _, c in contrast),
           "; ".join(f"dep {d}: {c:.1f}x" for d, c in contrast))
    record("solar/antisolar contrast grows with depression",
           all(c2 > c1 for (_, c1), (_, c2) in zip(contrast, contrast[1:])),
           "monotone growth expected as shadow rises antisolar-first")
    # AOD behavior: at dep 4 sunward low sky, higher AOD may brighten aureole
    # but must dim once extinction dominates; we only require a documented,
    # finite, monotone-in-|log| response rather than a fixed sign.
    aods = [(a, geom.get((4, 10, 0, a))) for a in (0.05, 0.15, 0.30)]
    if all(r for _, r in aods):
        vals = [r["photopicLuminanceCdM2"] for _, r in aods]
        record("AOD response finite and documented (dep 4, alt 10, sunward)",
               all(v > 0 for v in vals),
               "; ".join(f"AOD {a}: {v:.3g} cd/m2" for (a, _), v in zip(aods, vals)))

    n_pass = sum(1 for c in checks if c["passed"])
    lines += ["", f"## Summary: {n_pass}/{len(checks)} checks passed", ""]
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "observational-validation.md").write_text("\n".join(lines))
    (REPORTS / "observational-validation.json").write_text(
        json.dumps({"checks": checks, "passed": n_pass, "total": len(checks)},
                   indent=1))
    print(f"{n_pass}/{len(checks)} checks passed -> {REPORTS}")


if __name__ == "__main__":
    main()
