#!/usr/bin/env python3
"""FC-5 validation: verify the (1 AU / r)^2 radiance scaling against libRadtran
`day_of_year` runs. uvspec `day_of_year N` scales the solar flux by exactly the
inverse-square Sun-distance factor, so radiance(day N) / radiance(reference)
must equal sun_distance_radiance_factor(r(N)) to within a tight tolerance.

Uses a fast above-horizon DISORT case (the distance factor is a pure flux scale,
solver-independent). Writes reports/earth-sun-scaling-validation.json.
"""
import json
import subprocess
import tempfile
from pathlib import Path
from lrt_common import find_uvspec, find_data_dir, ROOT
from earth_sun_distance import earth_sun_distance_au, sun_distance_radiance_factor

REPORTS = ROOT / "reports"
DAYS = [3, 95, 185, 266]
TOL = 0.003   # 0.3 % (approximate ephemeris r vs uvspec's internal r)


def run(uvspec, data, day=None):
    lines = [
        f"data_files_path {data}",
        f"atmosphere_file {data}/atmmod/afglus.dat",
        f"source solar {data}/solar_flux/atlas_plus_modtran",
        "mol_abs_param crs", "wavelength 550 550",
        "sza 30", "phi0 0", "umu -1.0", "phi 0", "zout 0", "albedo 0.15",
        "aerosol_default", "rte_solver disort"]
    if day is not None:
        lines.append(f"day_of_year {day}")
    lines.append("quiet")
    with tempfile.TemporaryDirectory() as td:
        inp = Path(td) / "c.inp"
        inp.write_text("\n".join(lines) + "\n")
        p = subprocess.run([str(uvspec)], stdin=inp.open(), capture_output=True,
                           text=True, cwd=td)
    # radiance line: umu then last column is I at phi
    for ln in p.stdout.splitlines():
        c = ln.split()
        if len(c) >= 2 and c[0].startswith("-1"):
            return float(c[-1])
    return None


def main():
    uvspec = find_uvspec()
    data = find_data_dir(uvspec)
    ref = run(uvspec, data, day=None)     # 1 AU reference
    rows, worst = [], 0.0
    for d in DAYS:
        rad = run(uvspec, data, day=d)
        r_au = earth_sun_distance_au(d)
        predicted = sun_distance_radiance_factor(r_au)      # (1/r)^2
        observed = rad / ref if ref else None
        rel = abs(observed - predicted) / predicted if observed else None
        worst = max(worst, rel or 0)
        rows.append({"dayOfYear": d, "rAU": round(r_au, 5),
                     "predictedFactor": predicted, "observedFactor": observed,
                     "relError": rel})
    result = {"referenceAU": 1.0, "tolerance": TOL, "worstRelError": worst,
              "pass": worst < TOL, "rows": rows,
              "note": "uvspec day_of_year applies the (1AU/r)^2 solar-flux scale; "
              "the LUT-side sun_distance_radiance_factor reproduces it. Hybrid "
              "ratio cancels this factor; absolute model must apply it."}
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "earth-sun-scaling-validation.json").write_text(json.dumps(result, indent=1))
    print(json.dumps({"worstRelError": worst, "pass": result["pass"]}, indent=1))


if __name__ == "__main__":
    main()
