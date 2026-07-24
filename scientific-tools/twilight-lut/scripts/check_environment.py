#!/usr/bin/env python3
"""Verify the twilight-LUT computation environment (RH-3 hardened).

Checks Python, required packages, uvspec presence/version, the libRadtran data
directory, and — critically — that the REQUIRED solver (MYSTIC 1D-spherical
backward) actually produces a valid radiance file. Every uvspec probe runs with
cwd set to a fresh temp dir and mc_basename inside it, so MYSTIC output files
cannot leak into the repository. A valid MYSTIC radiance file (finite positive
value at the requested wavelength) is required — nonempty stdout is NOT
accepted as success. Exits nonzero if the required solver fails.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REQUIRED_PY = (3, 10)
# (label, extra_lines, needs_radiance_file)
PROBES = [
    ("disort", ["rte_solver disort"], False),
    ("twostr", ["rte_solver twostr"], False),
    ("sdisort", ["rte_solver sdisort"], False),
]


def find_uvspec():
    env = os.environ.get("LIBRADTRAN_BIN")
    if env and Path(env).is_file():
        return Path(env)
    which = shutil.which("uvspec")
    return Path(which) if which else None


def find_data_dir(uvspec_path):
    env = os.environ.get("LIBRADTRAN_DATA")
    if env and Path(env).is_dir():
        return Path(env)
    if uvspec_path:
        cand = uvspec_path.parent.parent / "share" / "libRadtran" / "data"
        if cand.is_dir():
            return cand
    return None


def run_probe(uvspec, text, timeout=600):
    """Run uvspec with cwd in a fresh temp dir; return (proc, tmpdir_path)."""
    td = tempfile.mkdtemp(prefix="lrtcheck_")
    inp = Path(td) / "case.inp"
    inp.write_text(text)
    try:
        proc = subprocess.run([str(uvspec)], stdin=inp.open(),
                              capture_output=True, text=True, cwd=td,
                              timeout=timeout)
        return proc, Path(td)
    except subprocess.TimeoutExpired:
        return None, Path(td)


def radiance_ok(tmpdir, wl=550.0):
    """A valid MYSTIC radiance file exists with a finite positive value."""
    f = tmpdir / "mc.rad.spc"
    if not f.exists():
        return False, "no mc.rad.spc"
    for line in f.read_text().splitlines():
        parts = line.split()
        if len(parts) >= 5 and abs(float(parts[0]) - wl) < 1.0:
            v = float(parts[4])
            if v != v or v <= 0:
                return False, f"radiance {v} not finite-positive"
            return True, f"radiance {v:.4g}"
    return False, "no radiance line at 550 nm"


def main():
    ok = True
    print(f"Python: {sys.version.split()[0]}", end=" ")
    if sys.version_info < REQUIRED_PY:
        print("FAIL"); ok = False
    else:
        print("OK")
    for mod in ("numpy", "scipy", "pytest"):
        try:
            m = __import__(mod)
            print(f"{mod}: {getattr(m, '__version__', '?')} OK")
        except ImportError:
            print(f"{mod}: MISSING"); ok = False

    uvspec = find_uvspec()
    if not uvspec or not os.access(uvspec, os.X_OK):
        print("uvspec: NOT FOUND (set LIBRADTRAN_BIN).")
        print("ENVIRONMENT: MOCKED (no real radiative-transfer possible)")
        sys.exit(1)
    ver = subprocess.run([str(uvspec), "-v"], capture_output=True, text=True)
    version = (ver.stdout + ver.stderr).strip().splitlines()[0]
    print(f"uvspec: {uvspec} ({version}) OK")

    data = find_data_dir(uvspec)
    if not data:
        print("libRadtran data dir: NOT FOUND"); print("ENVIRONMENT: BROKEN")
        sys.exit(1)
    print(f"libRadtran data dir: {data} OK")

    base = (
        f"data_files_path {data}\n"
        f"atmosphere_file {data}/atmmod/afglus.dat\n"
        f"source solar {data}/solar_flux/atlas_plus_modtran\n"
        "sza 30\nwavelength 550 550\nquiet\n"
    )
    # non-required solver probes (informational)
    for label, extra, _ in PROBES:
        proc, td = run_probe(uvspec, base + "\n".join(extra) + "\n")
        good = proc is not None and proc.returncode == 0 and proc.stdout.strip()
        print(f"solver {label}: {'OK' if good else 'UNAVAILABLE'}")
        shutil.rmtree(td, ignore_errors=True)

    # REQUIRED probe: MYSTIC 1D-spherical backward radiance, cwd=tmp,
    # mc_basename inside tmp, verified via a valid radiance file.
    print("REQUIRED solver MYSTIC 1D-spherical backward:")
    td = Path(tempfile.mkdtemp(prefix="lrtcheck_mystic_"))
    mystic = (
        f"data_files_path {data}\n"
        f"atmosphere_file {data}/atmmod/afglus.dat\n"
        f"source solar {data}/solar_flux/atlas_plus_modtran\n"
        "mol_abs_param crs\nwavelength 550 550\n"
        "sza 94\nphi0 0\numu -1.0\nphi 90\nzout 0\nalbedo 0.15\n"
        "aerosol_default\naerosol_modify tau550 set 0.15\n"
        "rte_solver mystic\nmc_spherical 1D\nmc_vroom on\n"
        "mc_photons 200000\nmc_std\nmc_randomseed 1\n"
        f"mc_basename {td}/mc\nquiet\n"
    )
    (td / "case.inp").write_text(mystic)
    try:
        proc = subprocess.run([str(uvspec)], stdin=(td / "case.inp").open(),
                              capture_output=True, text=True, cwd=td, timeout=600)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        rc = -1
    if rc != 0:
        print(f"  FAIL: uvspec exit {rc}")
        ok = False
    else:
        good, why = radiance_ok(td)
        print(f"  radiance file: {'OK' if good else 'FAIL'} ({why})")
        ok = ok and good
    # confirm no output leaked into repo cwd
    leaked = [f for f in ("mc.rad.spc", "mc.flx", "randomseed")
              if Path.cwd().joinpath(f).exists()]
    if leaked:
        print(f"  WARNING: MYSTIC files leaked into cwd: {leaked}")
    shutil.rmtree(td, ignore_errors=True)

    print("ENVIRONMENT: REAL (required MYSTIC solver verified)" if ok
          else "ENVIRONMENT: DEGRADED — required solver failed")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
