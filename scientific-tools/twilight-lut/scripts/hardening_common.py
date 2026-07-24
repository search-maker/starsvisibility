#!/usr/bin/env python3
"""Generic single-case libRadtran runner for the pre-grid hardening studies.

Unlike lrt_common.build_input (grid-locked), this accepts arbitrary uvspec
options so the hardening studies can vary VROOM, polarisation, elevation,
solver, forward vs radiance mode, and effective SZA. Radiance is always read
from mc.rad.spc (Stokes I = first line) to avoid the stdout-vs-file confusion.
"""
import math
import subprocess
import tempfile
import time
from pathlib import Path
from lrt_common import find_uvspec, find_data_dir

DATA = None
UVSPEC = None


def _init():
    global DATA, UVSPEC
    if UVSPEC is None:
        UVSPEC = find_uvspec()
        DATA = find_data_dir(UVSPEC)


def umu_for_altitude(alt_deg):
    return max(-1.0, min(-1e-4, -math.sin(math.radians(alt_deg))))


def run_radiance(sun_depression_deg, target_alt_deg, rel_az_deg, aod=0.15,
                 photons=2_000_000, seed=1000, vroom="on", polarisation=False,
                 elevation_km=0.0, aerosol=True, wavelength=(550, 550),
                 effective_sza_offset=0.0, timeout=1200):
    """Run one MYSTIC 1D-spherical backward radiance case; return dict with
    Stokes I radiance (mW m-2 nm-1 sr-1), std, runtime, status."""
    _init()
    sza = 90.0 + sun_depression_deg + effective_sza_offset
    umu = umu_for_altitude(target_alt_deg)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        lines = [
            f"data_files_path {DATA}",
            f"atmosphere_file {DATA}/atmmod/afglus.dat",
            f"source solar {DATA}/solar_flux/atlas_plus_modtran",
            "mol_abs_param crs",
            f"wavelength {wavelength[0]} {wavelength[1]}",
            f"sza {sza:.5f}", "phi0 0",
            f"umu {umu:.8f}", f"phi {rel_az_deg:.2f}",
            "zout 0", "albedo 0.15",
        ]
        if elevation_km > 0:
            lines.append(f"altitude {elevation_km:.3f}")
        if aerosol:
            lines += ["aerosol_default", f"aerosol_modify tau550 set {aod}"]
        lines += ["rte_solver mystic", "mc_spherical 1D",
                  f"mc_vroom {vroom}", f"mc_photons {photons}", "mc_std",
                  f"mc_randomseed {seed}", f"mc_basename {td}/mc"]
        if polarisation:
            lines.append("mc_polarisation 1")
        lines.append("quiet")
        (td / "c.inp").write_text("\n".join(lines) + "\n")
        t0 = time.time()
        try:
            p = subprocess.run([str(UVSPEC)], stdin=(td / "c.inp").open(),
                               capture_output=True, text=True, cwd=td,
                               timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "runtime": timeout}
        rt = time.time() - t0
        rad_f = td / "mc.rad.spc"
        if p.returncode != 0 or not rad_f.exists():
            return {"status": f"exit-{p.returncode}", "runtime": rt,
                    "stderr": p.stderr[-300:]}
        rad_lines = rad_f.read_text().splitlines()
        std_f = td / "mc.rad.std.spc"
        std_lines = std_f.read_text().splitlines() if std_f.exists() else []
        try:
            I = float(rad_lines[0].split()[4])
            Istd = float(std_lines[0].split()[4]) if std_lines else None
        except (IndexError, ValueError):
            return {"status": "parse-error", "runtime": rt}
        return {"status": "ok", "radiance": I, "std": Istd, "runtime": rt,
                "sza": sza, "umu": umu, "photons": photons, "seed": seed,
                "vroom": vroom, "polarisation": polarisation,
                "elevationKm": elevation_km, "aod": aod}


def run_irradiance(sun_depression_deg, aod=0.15, photons=1_000_000, seed=1000,
                   elevation_km=0.0, timeout=600):
    """Forward-mode: surface diffuse-down + direct irradiance (mc.flx.spc).
    Returns diffuse-down (edn) which is valid in spherical backward mode."""
    _init()
    sza = 90.0 + sun_depression_deg
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        lines = [
            f"data_files_path {DATA}",
            f"atmosphere_file {DATA}/atmmod/afglus.dat",
            f"source solar {DATA}/solar_flux/atlas_plus_modtran",
            "mol_abs_param crs", "wavelength 400 700",
            f"sza {sza:.5f}", "phi0 0", "zout 0", "albedo 0.15",
            "aerosol_default", f"aerosol_modify tau550 set {aod}",
            "rte_solver mystic", "mc_spherical 1D", "mc_vroom on",
            f"mc_photons {photons}", f"mc_randomseed {seed}",
            f"mc_basename {td}/mc", "quiet",
        ]
        if elevation_km > 0:
            lines.insert(6, f"altitude {elevation_km:.3f}")
        (td / "c.inp").write_text("\n".join(lines) + "\n")
        try:
            p = subprocess.run([str(UVSPEC)], stdin=(td / "c.inp").open(),
                               capture_output=True, text=True, cwd=td,
                               timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"status": "timeout"}
        flx = td / "mc.flx.spc"
        if not flx.exists():
            return {"status": f"exit-{p.returncode}"}
        # columns: wl ix iy iz Edir Edn Eup ... ; sum diffuse-down over wl
        edn = {}
        for ln in flx.read_text().splitlines():
            c = ln.split()
            if len(c) >= 6:
                try:
                    edn[float(c[0])] = float(c[5])
                except ValueError:
                    pass
        vals = [v for v in edn.values() if v == v]  # drop nan
        return {"status": "ok", "meanDiffuseDown_mW_m2_nm": (
            sum(vals) / len(vals) if vals else None),
            "nWavelengths": len(vals)}
