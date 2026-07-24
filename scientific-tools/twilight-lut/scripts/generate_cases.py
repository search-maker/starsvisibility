#!/usr/bin/env python3
"""Generate the Milestone-2 feasibility case list (test-cases/feasibility_cases.json).

Core grid (36):  depression {0,4,8} x altitude {10,30,60,90} x relAz {0,90,180},
                 AOD550 = 0.15 baseline.
Sensitivity:     intermediate depression/altitude/azimuth, low/high AOD,
                 Monte Carlo seed repeats, deep-depression domain probes.
All cases: afglus atmosphere, default rural aerosol scaled to tau550,
albedo 0.15, sea level, MYSTIC 1D-spherical backward, VROOM on.

Photon budget: mc_photons in spectral mode is the TOTAL photon count
distributed over the 41-wavelength grid (measured empirically: a 41-lambda run
costs the same as a single-lambda run at equal mc_photons). Deeper twilight
needs more photons for the same relative error, so the budget scales with
depression. Values chosen from the measured 1/sqrt(N) convergence at 550 nm.
"""
import json
from lrt_common import CASES_DIR, case_id

BASE = {
    "atmosphere": "afglus",
    "aerosolModel": "libRadtran aerosol_default (Shettle rural boundary layer, "
                    "background above), scaled via aerosol_modify tau550 set",
    "surfaceAlbedo": 0.15,
    "observerElevationM": 0,
    "solver": "mystic",
    "randomSeed": 1000,
    # Grid/pilot production default is VROOM OFF (directive #3). The legacy
    # feasibility raw-output committed earlier was generated with VROOM ON and is
    # labelled legacy; a fresh VROOM-off pilot must supply the runtime/uncertainty
    # /event-time evidence for the future grid.
    "vroom": "off",
}

PHOTONS_BY_DEPRESSION = {0: 2000000, 2: 2000000, 4: 8000000,
                         6: 20000000, 8: 40000000}


def make(dep, alt, raz, aod, group, **kw):
    c = {**BASE, "sunDepressionDeg": dep, "targetAltitudeDeg": alt,
         "relativeAzimuthDeg": raz, "aod550": aod, "group": group,
         "photonCount": PHOTONS_BY_DEPRESSION.get(dep, 40000000), **kw}
    c["caseId"] = case_id(c)
    return c


def main():
    cases = []
    # Core 36
    for dep in (0, 4, 8):
        for alt in (10, 30, 60, 90):
            for raz in (0, 90, 180):
                cases.append(make(dep, alt, raz, 0.15, "core"))
    # Intermediate depressions
    for dep in (2, 6):
        for raz in (0, 90, 180):
            cases.append(make(dep, 30, raz, 0.15, "sensitivity-depression"))
    # AOD sensitivity
    for aod in (0.05, 0.30):
        for alt in (10, 30):
            for raz in (0, 180):
                cases.append(make(4, alt, raz, aod, "sensitivity-aod"))
    # Intermediate altitude / azimuth
    for alt in (20, 45):
        cases.append(make(4, alt, 90, 0.15, "sensitivity-altitude"))
    for raz in (45, 135):
        cases.append(make(4, 30, raz, 0.15, "sensitivity-azimuth"))
    # Monte Carlo repeats: independent seeds, same physical case.
    # dep 4 mid-sky and the noisiest core geometry (dep 8, low alt, raz 90).
    for i, seed in enumerate((2001, 2002, 2003, 2004, 2005), start=1):
        cases.append(make(4, 30, 90, 0.15, "mc-repeat",
                          randomSeed=seed, repeatIndex=i))
    for i, seed in enumerate((3001, 3002, 3003, 3004, 3005), start=1):
        cases.append(make(8, 10, 90, 0.15, "mc-repeat-deep",
                          randomSeed=seed, repeatIndex=i))
    # Deep-depression domain probes (expected to fail / go noisy; that is the point)
    for dep in (9, 10, 12):
        cases.append(make(dep, 90, 0, 0.15, "domain-probe",
                          photonCount=40000000))
    CASES_DIR.mkdir(exist_ok=True)
    out = CASES_DIR / "feasibility_cases.json"
    out.write_text(json.dumps(cases, indent=1))
    print(f"wrote {len(cases)} cases -> {out}")
    groups = {}
    for c in cases:
        groups[c["group"]] = groups.get(c["group"], 0) + 1
    for g, n in groups.items():
        print(f"  {g}: {n}")


if __name__ == "__main__":
    main()
