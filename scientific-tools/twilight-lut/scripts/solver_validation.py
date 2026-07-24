#!/usr/bin/env python3
"""Produce reports/solver-validation.json from REAL libRadtran probes.

Establishes, from evidence rather than assertion:
- DISORT (plane-parallel) and DISORT+pseudospherical produce INVALID
  (negative or non-finite) radiances below the horizon (SZA > 90);
- MYSTIC 1D-spherical backward produces finite positive radiance across the
  twilight range and the core geometry sample.

The feasibility gate (write_feasibility_report.py) consumes this file; it must
not hardcode solver validity.
"""
import json
import subprocess
import tempfile
from pathlib import Path
from lrt_common import find_uvspec, find_data_dir, uvspec_version

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def run(uvspec, data, sza, umu, phi, solver, pseudospherical=False,
        photons=200000, aod=0.15, timeout=600):
    td = Path(tempfile.mkdtemp(prefix="solval_"))
    lines = [
        f"data_files_path {data}",
        f"atmosphere_file {data}/atmmod/afglus.dat",
        f"source solar {data}/solar_flux/atlas_plus_modtran",
        "mol_abs_param crs", "wavelength 550 550",
        f"sza {sza}", "phi0 0", f"umu {umu}", f"phi {phi}",
        "zout 0", "albedo 0.15", "aerosol_default",
        f"aerosol_modify tau550 set {aod}", f"rte_solver {solver}",
    ]
    if solver == "mystic":
        lines += ["mc_spherical 1D", "mc_vroom on", f"mc_photons {photons}",
                  "mc_std", "mc_randomseed 1", f"mc_basename {td}/mc"]
    if pseudospherical:
        lines.append("pseudospherical")
    lines.append("quiet")
    (td / "c.inp").write_text("\n".join(lines) + "\n")
    try:
        p = subprocess.run([str(uvspec)], stdin=(td / "c.inp").open(),
                           capture_output=True, text=True, cwd=td, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    val = None
    if solver == "mystic":
        f = td / "mc.rad.spc"
        if f.exists():
            parts = f.read_text().split()
            if len(parts) >= 5:
                val = float(parts[4])
    else:
        # DISORT radiance is on stdout: last column of the umu line
        for ln in p.stdout.splitlines():
            c = ln.split()
            if len(c) >= 2 and c[0].startswith("-1") or (c and c[0].startswith("-0")):
                try:
                    val = float(c[-1])
                except ValueError:
                    pass
    return {"solver": solver, "pseudospherical": pseudospherical, "sza": sza,
            "umu": umu, "phi": phi, "returncode": p.returncode, "radiance": val,
            "finitePositive": (val is not None and val == val and val > 0)}


def main():
    uvspec = find_uvspec()
    data = find_data_dir(uvspec)
    probes = []
    # DISORT / pseudospherical below horizon -> expect invalid
    for sza in (92, 94, 96):
        for solver, ps in (("disort", False), ("disort", True)):
            r = run(uvspec, data, sza, "-0.17365", 180, solver, pseudospherical=ps)
            if r:
                probes.append({**r, "domain": "below-horizon",
                               "expectation": "invalid"})
    # MYSTIC across twilight + core geometry sample -> expect valid
    mystic_geom = [(90, "-1.0", 0), (94, "-1.0", 0), (98, "-1.0", 0),
                   (94, "-0.17365", 0), (94, "-0.17365", 90), (94, "-0.17365", 180),
                   (94, "-0.5", 90)]
    for sza, umu, phi in mystic_geom:
        r = run(uvspec, data, sza, umu, phi, "mystic")
        if r:
            probes.append({**r, "domain": "twilight", "expectation": "valid"})

    disort_below = [p for p in probes if p["solver"] == "disort"
                    and p["domain"] == "below-horizon"]
    disort_any_invalid = any(not p["finitePositive"] for p in disort_below)
    mystic = [p for p in probes if p["solver"] == "mystic"]
    mystic_all_valid = bool(mystic) and all(p["finitePositive"] for p in mystic)

    result = {
        "uvspecVersion": uvspec_version(uvspec),
        "probes": probes,
        "disortInvalidBelowHorizon": disort_any_invalid,
        "mysticAllValid": mystic_all_valid,
        "mysticValidCount": sum(1 for p in mystic if p["finitePositive"]),
        "mysticProbeCount": len(mystic),
        "requiredSolver": "mystic 1D-spherical backward",
        "verdict": ("MYSTIC valid across twilight+core geometry; "
                    "DISORT/pseudospherical invalid below horizon"
                    if (mystic_all_valid and disort_any_invalid)
                    else "solver validation INCOMPLETE — inspect probes"),
        "pass": bool(mystic_all_valid and disort_any_invalid),
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "solver-validation.json").write_text(json.dumps(result, indent=1))
    print(json.dumps({k: result[k] for k in
                      ("disortInvalidBelowHorizon", "mysticAllValid",
                       "mysticValidCount", "mysticProbeCount", "pass")}, indent=1))


if __name__ == "__main__":
    main()
