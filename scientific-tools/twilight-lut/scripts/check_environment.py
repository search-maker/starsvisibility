#!/usr/bin/env python3
"""Verify the twilight-LUT computation environment.

Checks Python, required packages, uvspec presence/version, the libRadtran data
directory, a minimal real DISORT run, and which solvers accept a trivial input.
Prints REAL vs MOCKED honestly; exits non-zero if the environment cannot run
real libRadtran cases.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REQUIRED_PY = (3, 10)
SOLVERS_TO_PROBE = ["disort", "twostr", "sdisort", "mystic"]


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


def run_uvspec(uvspec, text, timeout=120):
    with tempfile.TemporaryDirectory() as td:
        inp = Path(td) / "case.inp"
        inp.write_text(text)
        try:
            proc = subprocess.run(
                [str(uvspec)], stdin=inp.open(), capture_output=True,
                text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, "timeout"
        return proc, None


def main():
    ok = True
    print(f"Python: {sys.version.split()[0]}", end=" ")
    if sys.version_info < REQUIRED_PY:
        print("FAIL (need >= %d.%d)" % REQUIRED_PY)
        ok = False
    else:
        print("OK")

    for mod in ("numpy", "scipy", "pytest"):
        try:
            m = __import__(mod)
            print(f"{mod}: {getattr(m, '__version__', '?')} OK")
        except ImportError:
            print(f"{mod}: MISSING")
            ok = False

    uvspec = find_uvspec()
    if not uvspec or not os.access(uvspec, os.X_OK):
        print("uvspec: NOT FOUND (set LIBRADTRAN_BIN). Environment is MOCKED-ONLY.")
        print("ENVIRONMENT: MOCKED (no real radiative-transfer results possible)")
        sys.exit(1)
    ver = subprocess.run([str(uvspec), "-v"], capture_output=True, text=True)
    version = (ver.stdout + ver.stderr).strip().splitlines()[0] if (ver.stdout or ver.stderr) else "?"
    print(f"uvspec: {uvspec} ({version}) OK")

    data = find_data_dir(uvspec)
    if not data:
        print("libRadtran data dir: NOT FOUND (set LIBRADTRAN_DATA)")
        print("ENVIRONMENT: BROKEN")
        sys.exit(1)
    print(f"libRadtran data dir: {data} OK")

    base = (
        f"data_files_path {data}\n"
        f"atmosphere_file {data}/atmmod/afglus.dat\n"
        f"source solar {data}/solar_flux/atlas_plus_modtran\n"
        "sza 30\nwavelength 550 550\nquiet\n"
    )
    proc, err = run_uvspec(uvspec, base + "rte_solver disort\n")
    if err or proc.returncode != 0 or not proc.stdout.strip():
        print(f"minimal DISORT case: FAIL ({err or proc.stderr[:200]})")
        ok = False
    else:
        edir = float(proc.stdout.split()[1])
        good = 500 < edir < 2500
        print(f"minimal DISORT case: edir(550nm, sza30) = {edir:.1f} mW/m2/nm "
              + ("OK" if good else "IMPLAUSIBLE"))
        ok = ok and good

    for solver in SOLVERS_TO_PROBE:
        extra = "rte_solver %s\n" % solver
        if solver == "mystic":
            extra = "rte_solver mystic\nmc_photons 1000\n"
        proc, err = run_uvspec(uvspec, base + extra, timeout=300)
        status = "OK" if (proc and proc.returncode == 0 and proc.stdout.strip()) else \
                 f"UNAVAILABLE ({err or (proc.stderr[:120].strip() if proc else '?')})"
        print(f"solver {solver}: {status}")

    print("ENVIRONMENT: REAL (uvspec executes real radiative-transfer cases)"
          if ok else "ENVIRONMENT: DEGRADED — see failures above")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
