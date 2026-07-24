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
    """Human-readable GEOMETRY label. NOT the restart identity — that is the
    configurationHash below, which also covers photons/seed/solver/atmosphere/
    elevation/albedo/vroom/wavelength grid."""
    dep = case["sunDepressionDeg"]
    alt = case["targetAltitudeDeg"]
    raz = case["relativeAzimuthDeg"]
    aod = case["aod550"]
    cid = f"sd{dep:04.1f}_alt{alt:04.1f}_raz{raz:05.1f}_aod{aod:.3f}".replace(".", "p")
    if case.get("repeatIndex", 0):
        cid += f"_rep{case['repeatIndex']}"
    return cid


# Every parameter that changes the physics or the numerics of a uvspec run.
# Anything omitted here would make two scientifically different runs collide.
CONFIG_KEYS = (
    "sunDepressionDeg", "targetAltitudeDeg", "relativeAzimuthDeg", "aod550",
    "atmosphere", "surfaceAlbedo", "observerElevationM", "solver",
    "photonCount", "randomSeed", "vroom", "pseudospherical",
)


def canonical_config(case):
    """Deterministic dict of every run-affecting parameter, with defaults made
    explicit so two nominally-equal cases always hash identically."""
    return {
        "sunDepressionDeg": float(case["sunDepressionDeg"]),
        "targetAltitudeDeg": float(case["targetAltitudeDeg"]),
        "relativeAzimuthDeg": float(case["relativeAzimuthDeg"]),
        "aod550": float(case["aod550"]),
        "atmosphere": case.get("atmosphere", "afglus"),
        "surfaceAlbedo": float(case.get("surfaceAlbedo", 0.15)),
        "observerElevationM": float(case.get("observerElevationM", 0)),
        "solver": case.get("solver", "mystic"),
        "photonCount": int(case.get("photonCount", 200000)),
        "randomSeed": int(case.get("randomSeed", 1000)),
        "vroom": case.get("vroom", "off"),   # grid default OFF (directive #3)
        "pseudospherical": bool(case.get("pseudospherical", False)),
        "wavelengthGrid": list(WAVELENGTH_NM),
        "molAbsParam": "crs",
        "solarSpectrum": "atlas_plus_modtran",
        "radianceUnits": "mW m-2 nm-1 sr-1",
        "pipelineVersion": 4,   # bump: elevation now emitted; vroom default off
    }


def configuration_hash(case, uvspec_ver, data_provenance):
    """Full restart identity: canonical config + libRadtran version + data
    provenance. Two runs may be treated as the same only if this matches."""
    payload = {
        "config": canonical_config(case),
        "uvspecVersion": uvspec_ver,
        "dataProvenance": data_provenance,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def _sha256_file(path):
    p = Path(path)
    if not p.exists():
        return None
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def data_provenance(data_dir):
    """A stable fingerprint of the libRadtran data package: sha256 of the ACTUAL
    atmosphere, aerosol, and solar-spectrum files used (PG-6), not just a
    directory path and one file size."""
    d = Path(data_dir)
    files = {
        "atmosphere_afglus": d / "atmmod" / "afglus.dat",
        "solar_atlas_plus_modtran": d / "solar_flux" / "atlas_plus_modtran",
    }
    # aerosol_default uses the Shettle tau550 scaling tables.
    shettle = d / "aerosol" / "shettle"
    if shettle.is_dir():
        for f in sorted(shettle.glob("tau550.*"))[:2]:
            files["aerosol_shettle_" + f.name] = f
    checks = {k: _sha256_file(v) for k, v in files.items()}
    return {"dataDir": str(d), "fileSha256": checks}


SENTINEL_MAX = 1e30   # MYSTIC missing-pixel placeholders (~8.99e306) and inf


def validate_run_outputs(adir):
    """Rigorous output validation (PG-6). Returns (status, detail).
    status 'ok' only if: every required wavelength present in BOTH the radiance
    and std spectra; all radiances finite, non-sentinel; all std finite and
    non-negative. 'noise-dominated' if EVERY required wavelength is unresolved
    (std >= value). Otherwise a specific failure status."""
    adir = Path(adir)
    rad_f, std_f = adir / "mc.rad.spc", adir / "mc.rad.std.spc"
    if not rad_f.exists():
        return "no-radiance-output", {}
    try:
        rad = parse_spc(rad_f)
    except (OSError, ValueError) as e:
        return f"rad-parse-error:{e}", {}
    if not rad:
        return "empty-radiance", {}

    def cover(d):
        return [w for w in WAVELENGTH_NM if not any(abs(w - x) < 1.0 for x in d)]

    miss = cover(rad)
    if miss:
        return f"incomplete-spectrum-missing-{len(miss)}", {"missing": miss}
    bad = [w for w, v in rad.items()
           if not math.isfinite(v) or abs(v) > SENTINEL_MAX]
    if bad:
        return "nonfinite-or-sentinel-radiance", {"badWavelengths": bad[:10]}
    if not std_f.exists():
        return "no-std-output", {}
    try:
        std = parse_spc(std_f)
    except (OSError, ValueError) as e:
        return f"std-parse-error:{e}", {}
    if cover(std):
        return "incomplete-std-spectrum", {"missing": cover(std)}
    badstd = [w for w, s in std.items()
              if not math.isfinite(s) or s < 0 or abs(s) > SENTINEL_MAX]
    if badstd:
        return "invalid-std", {"badWavelengths": badstd[:10]}
    # noise-dominated: unresolved at EVERY required wavelength
    def nearest_val(d, w):
        return d[min(d, key=lambda x: abs(x - w))]
    unresolved = sum(1 for w in WAVELENGTH_NM
                     if nearest_val(std, w) >= max(nearest_val(rad, w), 0))
    if unresolved == len(WAVELENGTH_NM):
        return "noise-dominated", {"unresolvedWavelengths": unresolved}
    detail = {"radianceSha256": _sha256_file(rad_f),
              "stdSha256": _sha256_file(std_f),
              "unresolvedWavelengths": unresolved}
    return "ok", detail


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
    elev_m = float(case.get("observerElevationM", 0))
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
    ]
    solver = case.get("solver", "mystic")
    # Observer elevation. FINDING (verified on uvspec 2.0.6): the `altitude`
    # option is REJECTED by the montecarlo solver ("option altitude does not
    # work with solver montecarlo! Use mc_elevation_file!"). So the directive's
    # `altitude <km>` mechanism applies only to DISORT-family solvers. For the
    # production MYSTIC 1D-spherical solver, a raised ground observer requires
    # `mc_elevation_file` (a surface-elevation map), which is a separate
    # implementation validated in the elevation sensitivity study. Until then we
    # refuse to emit broken input for elevated MYSTIC cases rather than silently
    # producing a wrong (sea-level) result.
    if elev_m > 0:
        if solver == "mystic":
            raise NotImplementedError(
                "observerElevationM>0 with MYSTIC needs mc_elevation_file "
                "(altitude is rejected by the montecarlo solver); elevation "
                "axis is deferred to the elevation sensitivity study")
        lines.append(f"altitude {elev_m / 1000.0:.4f}")   # DISORT-family only
    lines += [
        "zout 0",
        f"albedo {case.get('surfaceAlbedo', 0.15)}",
        "aerosol_default",
        f"aerosol_modify tau550 set {case['aod550']}",
        f"rte_solver {case.get('solver', 'mystic')}",
    ]
    if case.get("solver", "mystic") == "mystic":
        lines += [
            "mc_spherical 1D",
            # Grid production DEFAULT is VROOM OFF (Milestone directive #3):
            # VROOM is not authorized for production until a paired, spectral,
            # multi-seed study also validates the event-time impact.
            f"mc_vroom {case.get('vroom', 'off')}",
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


def _valid_completed_attempt(attempt_dir, expected_hash, expected_ver):
    """A completed run may be reused only if EVERY check passes: manifest hash
    matches, libRadtran version matches, status ok, radiance file exists AND
    parses AND covers the full wavelength grid."""
    meta_f = attempt_dir / "meta.json"
    if not meta_f.exists():
        return False, "no-meta"
    try:
        meta = json.loads(meta_f.read_text())
    except json.JSONDecodeError:
        return False, "meta-unreadable"
    if meta.get("configurationHash") != expected_hash:
        return False, "hash-mismatch"
    if meta.get("uvspecVersion") != expected_ver:
        return False, "version-mismatch"
    if meta.get("status") != "ok":
        return False, "status-" + str(meta.get("status"))
    # PG-6: re-run the full output validation on reuse, and verify the recorded
    # radiance checksum still matches the file on disk (tamper/corruption guard).
    status, detail = validate_run_outputs(attempt_dir)
    if status != "ok":
        return False, "revalidation-" + status
    recorded = meta.get("outputValidation", {}).get("radianceSha256")
    if recorded and recorded != detail.get("radianceSha256"):
        return False, "radiance-checksum-changed"
    return True, "ok"


def _next_attempt_index(cdir):
    existing = [int(p.name.split("-")[1]) for p in cdir.glob("attempt-*")
                if p.name.split("-")[1].isdigit()]
    return max(existing) + 1 if existing else 0


def run_case(case, uvspec, data_dir, overwrite=False, timeout=3600):
    """Execute one case into raw-output/<caseId>/attempt-NNN/ (IMMUTABLE) and
    update raw-output/<caseId>/active.json.

    Restart identity is the configurationHash (geometry + photons + seed +
    solver + atmosphere + elevation + albedo + vroom + wavelength grid +
    libRadtran version + data provenance). A prior attempt is reused ONLY when
    its hash, version, status, output files and parseability all validate.
    A changed configuration or a failure never overwrites earlier output — it
    creates a new immutable attempt directory. `overwrite=True` forces a fresh
    attempt even when a valid one exists."""
    cid = case_id(case)
    cdir = RAW_DIR / cid
    cdir.mkdir(parents=True, exist_ok=True)
    uvspec_ver = uvspec_version(uvspec)
    prov = data_provenance(data_dir)
    cfg_hash = configuration_hash(case, uvspec_ver, prov)

    active_f = cdir / "active.json"
    if not overwrite and active_f.exists():
        try:
            active = json.loads(active_f.read_text())
            sel = cdir / active.get("selectedAttempt", "")
            valid, why = _valid_completed_attempt(sel, cfg_hash, uvspec_ver)
            if valid:
                return {"caseId": cid, "status": "skipped-complete",
                        "configurationHash": cfg_hash,
                        "attempt": active["selectedAttempt"]}
        except (json.JSONDecodeError, OSError):
            pass

    idx = _next_attempt_index(cdir)
    adir = cdir / f"attempt-{idx:03d}"
    adir.mkdir()
    wl_file = adir / "wavelengths.dat"
    write_wavelength_grid(wl_file)
    basename = adir / "mc"
    inp_text = build_input(case, data_dir, wl_file, basename)
    (adir / "case.inp").write_text(inp_text)
    t0 = time.time()
    try:
        proc = subprocess.run([str(uvspec)], stdin=(adir / "case.inp").open(),
                              stdout=(adir / "stdout.txt").open("w"),
                              stderr=(adir / "stderr.txt").open("w"),
                              cwd=adir, timeout=timeout)
        rc, err = proc.returncode, None
    except subprocess.TimeoutExpired:
        rc, err = -1, "timeout"
    runtime = time.time() - t0
    if err:
        status, out_detail = err, {}
    elif rc != 0:
        status, out_detail = f"uvspec-exit-{rc}", {}
    else:
        status, out_detail = validate_run_outputs(adir)   # PG-6 rigorous check
    meta = {
        "caseId": cid, "attempt": f"attempt-{idx:03d}",
        "configurationHash": cfg_hash,
        "canonicalConfig": canonical_config(case),
        "dataProvenance": prov,
        **{k: case.get(k) for k in CONFIG_KEYS if k in case},
        "group": case.get("group"), "repeatIndex": case.get("repeatIndex", 0),
        "sza": 90.0 + case["sunDepressionDeg"],
        "umu": umu_for_altitude(case["targetAltitudeDeg"]),
        "phi": case["relativeAzimuthDeg"], "phi0": 0.0,
        "status": status, "runtimeSeconds": round(runtime, 3),
        "outputValidation": out_detail,
        "inputSha256": sha256_text(inp_text),
        "uvspecVersion": uvspec_ver,
        "generatorCommit": git_commit_hash(),
        "radianceUnits": "mW m-2 nm-1 sr-1",
        "outputIsReal": True,
        "generatedUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (adir / "meta.json").write_text(json.dumps(meta, indent=1))

    # Update manifest: select this attempt if ok, else keep last ok if any.
    selected = f"attempt-{idx:03d}"
    if status != "ok" and active_f.exists():
        try:
            prev = json.loads(active_f.read_text())
            psel = cdir / prev.get("selectedAttempt", "")
            if _valid_completed_attempt(psel, cfg_hash, uvspec_ver)[0]:
                selected = prev["selectedAttempt"]
        except (json.JSONDecodeError, OSError):
            pass
    active_f.write_text(json.dumps({
        "caseId": cid, "selectedAttempt": selected,
        "configurationHash": cfg_hash, "status": status,
        "latestAttempt": f"attempt-{idx:03d}",
        "totalAttempts": idx + 1,
        "updatedUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, indent=1))
    return {"caseId": cid, "status": status, "runtimeSeconds": runtime,
            "configurationHash": cfg_hash, "attempt": f"attempt-{idx:03d}"}


def selected_attempt_dir(cdir):
    """Return the active/selected attempt directory for a case, or None."""
    active_f = Path(cdir) / "active.json"
    if not active_f.exists():
        return None
    try:
        active = json.loads(active_f.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    sel = Path(cdir) / active.get("selectedAttempt", "")
    return sel if sel.exists() else None
