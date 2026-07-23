#!/usr/bin/env python3
"""Generate the Milestone-2 feasibility case list (test-cases/feasibility_cases.json).

Core grid (36):  depression {0,4,8} x altitude {10,30,60,90} x relAz {0,90,180},
                 AOD550 = 0.15 baseline.
Sensitivity:     intermediate depression/altitude/azimuth, low/high AOD,
                 Monte Carlo seed repeats, deep-depression domain probes.
All cases: afglus atmosphere, default rural aerosol scaled to tau550,
albedo 0.15, sea level, MYSTIC 1D-spherical backward, VROOM on.
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
    "photonCount": 200000,
    "randomSeed": 1000,
    "vroom": "on",
}


def make(dep, alt, raz, aod, group, **kw):
    c = {**BASE, "sunDepressionDeg": dep, "targetAltitudeDeg": alt,
         "relativeAzimuthDeg": raz, "aod550": aod, "group": group, **kw}
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
    # Monte Carlo repeats: independent seeds, same physical case
    for i, seed in enumerate((2001, 2002, 2003, 2004, 2005), start=1):
        cases.append(make(4, 30, 90, 0.15, "mc-repeat",
                          randomSeed=seed, repeatIndex=i))
    # Deep-depression domain probes (expected to fail / go noisy; that is the point)
    for dep in (9, 10, 12):
        cases.append(make(dep, 90, 0, 0.15, "domain-probe",
                          photonCount=2000000))
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
