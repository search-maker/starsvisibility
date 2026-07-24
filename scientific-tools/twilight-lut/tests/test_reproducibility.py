"""RH-1/RH-2: configurationHash restart identity and immutable attempts.

Uses a mock uvspec (a shell script writing a valid MYSTIC radiance file) so the
runner logic is tested without a real multi-second MYSTIC run.
"""
import json
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import lrt_common as L  # noqa: E402


@pytest.fixture
def mock_env(tmp_path, monkeypatch):
    # point RAW_DIR at a temp dir
    monkeypatch.setattr(L, "RAW_DIR", tmp_path / "raw")
    (tmp_path / "raw").mkdir()
    # mock uvspec: emit a full-grid mc.rad.spc + std into cwd
    uvspec = tmp_path / "uvspec"
    wl = " ".join(str(w) for w in L.WAVELENGTH_NM)
    uvspec.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"wls = [{','.join(str(w) for w in L.WAVELENGTH_NM)}]\n"
        "if '-v' in sys.argv:\n"
        "    print('uvspec, version 2.0.6-MYSTIC'); sys.exit(0)\n"
        "open('mc.rad.spc','w').write(''.join(f'{w}.0 0 0 0 1.5\\n' for w in wls))\n"
        "open('mc.rad.std.spc','w').write(''.join(f'{w}.0 0 0 0 0.05\\n' for w in wls))\n"
    )
    uvspec.chmod(uvspec.stat().st_mode | stat.S_IEXEC)
    data = tmp_path / "data"
    (data / "solar_flux").mkdir(parents=True)
    (data / "solar_flux" / "atlas_plus_modtran").write_text("x" * 100)
    (data / "atmmod").mkdir()
    (data / "atmmod" / "afglus.dat").write_text("# atm\n")
    return uvspec, data


def base_case(**kw):
    c = {"sunDepressionDeg": 4, "targetAltitudeDeg": 30, "relativeAzimuthDeg": 90,
         "aod550": 0.15, "photonCount": 200000, "randomSeed": 1000}
    c.update(kw)
    return c


def test_config_hash_depends_on_photons_and_seed():
    ver, prov = "v", {"d": 1}
    h1 = L.configuration_hash(base_case(photonCount=200000), ver, prov)
    h2 = L.configuration_hash(base_case(photonCount=800000), ver, prov)
    h3 = L.configuration_hash(base_case(randomSeed=42), ver, prov)
    h4 = L.configuration_hash(base_case(vroom="on"), ver, prov)  # default is off
    h5 = L.configuration_hash(base_case(observerElevationM=2640), ver, prov)
    assert len({h1, h2, h3, h4, h5}) == 5   # all distinct


def test_config_hash_depends_on_uvspec_version():
    c = base_case()
    assert L.configuration_hash(c, "2.0.6", {}) != L.configuration_hash(c, "2.0.7", {})


def test_run_creates_attempt_and_manifest(mock_env):
    uvspec, data = mock_env
    r = L.run_case(base_case(), uvspec, data)
    assert r["status"] == "ok"
    cdir = L.RAW_DIR / L.case_id(base_case())
    assert (cdir / "attempt-000" / "mc.rad.spc").exists()
    active = json.loads((cdir / "active.json").read_text())
    assert active["selectedAttempt"] == "attempt-000"
    assert active["configurationHash"] == r["configurationHash"]


def test_valid_attempt_is_reused(mock_env):
    uvspec, data = mock_env
    L.run_case(base_case(), uvspec, data)
    r2 = L.run_case(base_case(), uvspec, data)
    assert r2["status"] == "skipped-complete"
    cdir = L.RAW_DIR / L.case_id(base_case())
    assert not (cdir / "attempt-001").exists()   # no new attempt


def test_changed_config_creates_new_immutable_attempt(mock_env):
    uvspec, data = mock_env
    L.run_case(base_case(photonCount=200000), uvspec, data)
    cdir = L.RAW_DIR / L.case_id(base_case())
    original = (cdir / "attempt-000" / "meta.json").read_text()
    # same geometry (same caseId) but different photon count -> new attempt
    r = L.run_case(base_case(photonCount=800000), uvspec, data)
    assert r["attempt"] == "attempt-001"
    assert (cdir / "attempt-001").exists()
    # attempt-000 is immutable
    assert (cdir / "attempt-000" / "meta.json").read_text() == original
    active = json.loads((cdir / "active.json").read_text())
    assert active["selectedAttempt"] == "attempt-001"
    assert active["totalAttempts"] == 2


def test_failed_run_does_not_clobber_previous_ok(mock_env, tmp_path):
    uvspec, data = mock_env
    L.run_case(base_case(), uvspec, data)
    # a uvspec that fails (no output)
    bad = tmp_path / "bad_uvspec"
    bad.write_text("#!/usr/bin/env python3\nimport sys\n"
                   "print('uvspec, version 2.0.6-MYSTIC') if '-v' in sys.argv else sys.exit(3)\n")
    bad.chmod(bad.stat().st_mode | stat.S_IEXEC)
    r = L.run_case(base_case(), bad, data, overwrite=True)
    assert r["status"] != "ok"
    cdir = L.RAW_DIR / L.case_id(base_case())
    active = json.loads((cdir / "active.json").read_text())
    # manifest keeps pointing at the earlier OK attempt
    assert active["selectedAttempt"] == "attempt-000"
