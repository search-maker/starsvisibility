#!/usr/bin/env python3
"""Shared infrastructure for the twilight-LUT feasibility pipeline.

Geometry contract (documented in CURRENT_MODEL_ANALYSIS.md §5 and README):
- sunDepressionDeg: GEOMETRIC solar depression (deg below the true horizon).
  libRadtran sza = 90 + sunDepressionDeg. No refraction is applied to the Sun
  (matches the calculator, which keys twilight on the true Sun).
- targetAltitudeDeg: GEOMETRIC target altitude above the horizon.
  uvspec viewing convention: umu < 0 is a ground sensor looking upward;
  umu = -sin(targetAltitudeDeg) = -cos(viewing zenith angle).
- relativeAzimuthDeg: smallest angular difference between the target azimuth
  and the solar azimuth, range 0..180. uvspec: phi0 = 0 and phi =
  relativeAzimuthDeg, because "phi = phi0 means the sensor looks into the
  direction of the sun" (libRadtran manual, uvspec basic usage).
- Output radiance units: mW m-2 nm-1 sr-1 (source solar file in mW m-2 nm-1).
"""
import hashlib
import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent          # scientific-tools/twilight-lut
RAW_DIR = ROOT / "raw-output"
PROCESSED_DIR = ROOT / "processed-output"
CASES_DIR = ROOT / "test-cases"

WAVELENGTH_NM = list(range(380, 781, 10))   # 41 points, V(lambda) support


def find_uvspec():
    env = os.environ.get("LIBRADTRAN_BIN")
    if env and Path(env).is_file():
        return Path(env)
    which = shutil.which("uvspec")
    if which:
        return Path(which)
    raise FileNotFoundError("uvspec not found; set LIBRADTRAN_BIN")


def find_data_dir(uvspec_path=None):
    env = os.environ.get("LIBRADTRAN_DATA")
    if env and Path(env).is_dir():
        return Path(env)
    uvspec_path = uvspec_path or find_uvspec()
    cand = Path(uvspec_path).parent.parent / "share" / "libRadtran" / "data"
    if cand.is_dir():
        return cand
    raise FileNotFoundError("libRadtran data dir not found; set LIBRADTRAN_DATA")


def uvspec_version(uvspec_path):
    p = subprocess.run([str(uvspec_path), "-v"], capture_output=True, text=True)
    return (p.stdout + p.stderr).strip().splitlines()[0]


def case_id(case):
    dep = case["sunDepressionDeg"]
    alt = case["targetAltitudeDeg"]
    raz = case["relativeAzimuthDeg"]
    aod = case["aod550"]
    cid = f"sd{dep:04.1f}_alt{alt:04.1f}_raz{raz:05.1f}_aod{aod:.3f}".replace(".", "p")
    if case.get("repeatIndex", 0):
        cid += f"_rep{case['repeatIndex']}"
    return cid


def umu_for_altitude(target_altitude_deg):
    """Ground sensor looking up at geometric altitude h: umu = -sin(h)."""
    umu = -math.sin(math.radians(target_altitude_deg))
    return max(-1.0, min(-1e-4, umu))


def build_input(case, data_dir, wl_file, basename):
    """uvspec input for one MYSTIC 1D-spherical backward twilight case."""
    dep = case["sunDepressionDeg"]
    sza = 90.0 + dep
    umu = umu_for_altitude(case["targetAltitudeDeg"])
    phi = float(case["relativeAzimuthDeg"])  # phi0=0; phi=raz => raz from sun
    lines = [
        f"data_files_path {data_dir}",
        f"atmosphere_file {data_dir}/atmmod/{case.get('atmosphere', 'afglus')}.dat",
        f"source solar {data_dir}/solar_flux/atlas_plus_modtran",
        "mol_abs_param crs",
        f"wavelength_grid_file {wl_file}",
        f"wavelength {WAVELENGTH_NM[0]} {WAVELENGTH_NM[-1]}",
        f"sza {sza:.4f}",
        "phi0 0",
        f"umu {umu:.8f}",
        f"phi {phi:.2f}",
        "zout 0",
        f"albedo {case.get('surfaceAlbedo', 0.15)}",
        "aerosol_default",
        f"aerosol_modify tau550 set {case['aod550']}",
        f"rte_solver {case.get('solver', 'mystic')}",
    ]
    if case.get("solver", "mystic") == "mystic":
        lines += [
            "mc_spherical 1D",
            f"mc_vroom {case.get('vroom', 'on')}",
            f"mc_photons {case.get('photonCount', 200000)}",
            "mc_std",
            f"mc_randomseed {case.get('randomSeed', 1000)}",
            f"mc_basename {basename}",
        ]
    if case.get("pseudospherical"):
        lines.append("pseudospherical")
    lines.append("quiet")
    return "\n".join(lines) + "\n"


def write_wavelength_grid(path):
    path.write_text("\n".join(f"{w:.1f}" for w in WAVELENGTH_NM) + "\n")


def parse_spc(path):
    """Parse a MYSTIC .spc file -> {wavelength_nm: value}. Values are
    mW m-2 nm-1 sr-1 for mc.rad.spc."""
    out = {}
    for line in Path(path).read_text().splitlines():
        parts = line.split()
        if len(parts) >= 5:
            out[float(parts[0])] = float(parts[4])
    return out


def sha256_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def git_commit_hash():
    try:
        p = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                           text=True, cwd=ROOT)
        return p.stdout.strip() or None
    except OSError:
        return None


def run_case(case, uvspec, data_dir, overwrite=False, timeout=3600):
    """Execute one case into raw-output/<caseId>/. Restartable: a completed,
    parseable case is skipped unless overwrite. Never silently overwrites."""
    cid = case_id(case)
    cdir = RAW_DIR / cid
    done = cdir / "meta.json"
    if done.exists() and not overwrite:
        try:
            meta = json.loads(done.read_text())
            if meta.get("status") == "ok":
                return {"caseId": cid, "status": "skipped-complete"}
        except json.JSONDecodeError:
            pass
    cdir.mkdir(parents=True, exist_ok=True)
    wl_file = cdir / "wavelengths.dat"
    write_wavelength_grid(wl_file)
    basename = cdir / "mc"
    inp_text = build_input(case, data_dir, wl_file, basename)
    (cdir / "case.inp").write_text(inp_text)
    t0 = time.time()
    try:
        proc = subprocess.run([str(uvspec)], stdin=(cdir / "case.inp").open(),
                              stdout=(cdir / "stdout.txt").open("w"),
                              stderr=(cdir / "stderr.txt").open("w"),
                              cwd=cdir, timeout=timeout)
        rc = proc.returncode
        err = None
    except subprocess.TimeoutExpired:
        rc, err = -1, "timeout"
    runtime = time.time() - t0
    rad_file = cdir / "mc.rad.spc"
    std_file = cdir / "mc.rad.std.spc"
    status = "ok"
    if err:
        status = err
    elif rc != 0:
        status = f"uvspec-exit-{rc}"
    elif not rad_file.exists() or not parse_spc(rad_file):
        status = "no-radiance-output"
    meta = {
        "caseId": cid, **case,
        "sza": 90.0 + case["sunDepressionDeg"],
        "umu": umu_for_altitude(case["targetAltitudeDeg"]),
        "phi": case["relativeAzimuthDeg"], "phi0": 0.0,
        "status": status, "runtimeSeconds": round(runtime, 3),
        "inputSha256": sha256_text(inp_text),
        "uvspecVersion": uvspec_version(uvspec),
        "generatorCommit": git_commit_hash(),
        "radianceUnits": "mW m-2 nm-1 sr-1",
        "outputIsReal": True,
        "generatedUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    done.write_text(json.dumps(meta, indent=1))
    return {"caseId": cid, "status": status, "runtimeSeconds": runtime}
