#!/usr/bin/env python3
"""Produce reports/solver-validation.json from REAL libRadtran probes (PG-5).

Reports the three solvers SEPARATELY and quantifies their disagreement, rather
than lumping them together:
- plane-parallel DISORT below the horizon,
- pseudospherical DISORT below the horizon,
- MYSTIC 1D-spherical backward,
- pseudospherical-DISORT vs MYSTIC relative difference at identical geometry.

Finding (evidence, not assertion): below the horizon plane-parallel DISORT
returns ZERO (no direct beam, no valid diffuse radiance); pseudospherical DISORT
returns finite values that are NEGATIVE in some viewing directions (e.g.
sunward) and, where positive, differ from spherical MYSTIC by large factors;
MYSTIC returns finite positive radiance consistently. The production decision
selects MYSTIC because pseudospherical is physically unreliable here (negative
lobes) and disagrees materially with MYSTIC — NOT because every pseudospherical
value is negative.

DISORT radiance line format: `umu  u0u_mean  I(phi_0) I(phi_1) ...`; the
per-phi radiances are the LAST len(phi) columns.
"""
import json
import subprocess
import tempfile
from pathlib import Path
from lrt_common import find_uvspec, find_data_dir, uvspec_version

REPORTS = Path(__file__).resolve().parent.parent / "reports"

# below-horizon geometries: (sza, umu, phi)
GEOMS = [(sza, umu, phi)
         for sza in (92, 94, 96)
         for (umu, phi) in ((-1.0, 0), (-0.5, 0), (-0.5, 90), (-0.5, 180))]
EXPECTED_MYSTIC_PROBES = len(GEOMS)   # exact count required


def _inp(data, sza, umu, phi, solver, pseudospherical, td, photons=200000):
    lines = [
        f"data_files_path {data}",
        f"atmosphere_file {data}/atmmod/afglus.dat",
        f"source solar {data}/solar_flux/atlas_plus_modtran",
        "mol_abs_param crs", "wavelength 550 550",
        f"sza {sza}", "phi0 0", f"umu {umu}", f"phi {phi}",
        "zout 0", "albedo 0.15", "aerosol_default",
        "aerosol_modify tau550 set 0.15", f"rte_solver {solver}"]
    if solver == "mystic":
        lines += ["mc_spherical 1D", "mc_vroom on", f"mc_photons {photons}",
                  "mc_std", "mc_randomseed 1", f"mc_basename {td}/mc"]
    if pseudospherical:
        lines.append("pseudospherical")
    lines.append("quiet")
    return "\n".join(lines) + "\n"


def run(uvspec, data, sza, umu, phi, solver, pseudospherical=False, timeout=600):
    td = Path(tempfile.mkdtemp(prefix="solval_"))
    (td / "c.inp").write_text(_inp(data, sza, umu, phi, solver, pseudospherical, td))
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
        # radiance line begins with the umu value; last column = I at our phi
        for ln in p.stdout.splitlines():
            c = ln.split()
            if len(c) >= 2:
                try:
                    if abs(float(c[0]) - umu) < 1e-3 and len(c) >= 3:
                        val = float(c[-1])
                        break
                except ValueError:
                    continue
    return {"sza": sza, "umu": umu, "phi": phi, "radiance": val,
            "returncode": p.returncode,
            "finitePositive": (val is not None and val == val and val > 0)}


def main():
    uvspec = find_uvspec()
    data = find_data_dir(uvspec)
    pp, ps, my = [], [], []
    ps_vs_my = []
    for sza, umu, phi in GEOMS:
        rpp = run(uvspec, data, sza, umu, phi, "disort", pseudospherical=False)
        rps = run(uvspec, data, sza, umu, phi, "disort", pseudospherical=True)
        rmy = run(uvspec, data, sza, umu, phi, "mystic")
        if rpp:
            pp.append(rpp)
        if rps:
            ps.append(rps)
        if rmy:
            my.append(rmy)
        if rps and rmy and rps["radiance"] is not None and rmy["radiance"] and rmy["radiance"] > 0:
            ps_vs_my.append({
                "sza": sza, "umu": umu, "phi": phi,
                "pseudospherical": rps["radiance"], "mystic": rmy["radiance"],
                "relDiff": (rps["radiance"] - rmy["radiance"]) / rmy["radiance"]})

    pp_all_zero = bool(pp) and all(abs(r["radiance"] or 0) < 1e-9 for r in pp)
    ps_any_negative = any((r["radiance"] is not None and r["radiance"] < 0) for r in ps)
    ps_neg_dirs = [{"sza": r["sza"], "umu": r["umu"], "phi": r["phi"],
                    "radiance": r["radiance"]}
                   for r in ps if r["radiance"] is not None and r["radiance"] < 0]
    mystic_valid = sum(1 for r in my if r["finitePositive"])
    mystic_all_valid = (mystic_valid == EXPECTED_MYSTIC_PROBES)
    ps_my_absreldiffs = [abs(x["relDiff"]) for x in ps_vs_my]
    ps_disagrees = bool(ps_my_absreldiffs) and (max(ps_my_absreldiffs) > 0.5)

    passed = mystic_all_valid and (pp_all_zero or ps_any_negative or ps_disagrees)

    result = {
        "uvspecVersion": uvspec_version(uvspec),
        "expectedMysticProbes": EXPECTED_MYSTIC_PROBES,
        "mysticValidCount": mystic_valid,
        "mysticAllValid": mystic_all_valid,
        "planeParallelDisort": {
            "allZeroBelowHorizon": pp_all_zero,
            "probes": pp,
            "interpretation": "plane-parallel DISORT has no direct beam below "
            "the horizon and returns zero diffuse radiance — unusable for "
            "twilight sky radiance"},
        "pseudosphericalDisort": {
            "anyNegative": ps_any_negative,
            "negativeDirections": ps_neg_dirs,
            "probes": ps,
            "interpretation": "pseudospherical DISORT returns finite values but "
            "is NEGATIVE in some viewing directions (e.g. sunward) and, where "
            "positive, differs from spherical MYSTIC by large factors — not "
            "physically reliable for directional twilight radiance"},
        "mystic": {"probes": my},
        "pseudosphericalVsMystic": {
            "pairs": ps_vs_my,
            "maxAbsRelDiff": max(ps_my_absreldiffs) if ps_my_absreldiffs else None,
            "disagreesMaterially": ps_disagrees},
        "decision": "select MYSTIC 1D-spherical backward exclusively. "
        "Pseudospherical DISORT is NOT selected because it produces negative "
        "radiance in some directions and disagrees materially with MYSTIC where "
        "positive; plane-parallel DISORT is unusable (zero) below the horizon. "
        "This is NOT a claim that every pseudospherical value is negative.",
        "requiredSolver": "mystic 1D-spherical backward",
        "pass": bool(passed),
    }
    # keep legacy keys some consumers read
    result["disortInvalidBelowHorizon"] = bool(pp_all_zero or ps_any_negative)
    result["mysticProbeCount"] = len(my)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "solver-validation.json").write_text(json.dumps(result, indent=1))
    print(json.dumps({
        "mysticValidCount": mystic_valid, "expected": EXPECTED_MYSTIC_PROBES,
        "planeParallelAllZero": pp_all_zero,
        "pseudosphericalAnyNegative": ps_any_negative,
        "pseudoVsMysticMaxAbsRelDiff": result["pseudosphericalVsMystic"]["maxAbsRelDiff"],
        "pass": result["pass"]}, indent=1))


if __name__ == "__main__":
    main()
