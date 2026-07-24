"""PG-6: rigorous output validation and provenance checksums."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import lrt_common as L  # noqa: E402


def write_spc(path, values):
    """values: dict wl->value. Writes MYSTIC-style .spc lines."""
    path.write_text("".join(f"{w}.0 0 0 0 {v}\n" for w, v in values.items()))


def full(val):
    return {w: val for w in L.WAVELENGTH_NM}


def test_ok_when_complete_finite(tmp_path):
    write_spc(tmp_path / "mc.rad.spc", full(1.5))
    write_spc(tmp_path / "mc.rad.std.spc", full(0.05))
    status, detail = L.validate_run_outputs(tmp_path)
    assert status == "ok"
    assert detail["radianceSha256"] and detail["stdSha256"]


def test_missing_wavelength_flagged(tmp_path):
    vals = full(1.5)
    del vals[L.WAVELENGTH_NM[10]]
    write_spc(tmp_path / "mc.rad.spc", vals)
    write_spc(tmp_path / "mc.rad.std.spc", full(0.05))
    status, _ = L.validate_run_outputs(tmp_path)
    assert status.startswith("incomplete-spectrum-missing")


def test_sentinel_value_rejected(tmp_path):
    vals = full(1.5)
    vals[L.WAVELENGTH_NM[5]] = 8.98847e306
    write_spc(tmp_path / "mc.rad.spc", vals)
    write_spc(tmp_path / "mc.rad.std.spc", full(0.05))
    status, _ = L.validate_run_outputs(tmp_path)
    assert status == "nonfinite-or-sentinel-radiance"


def test_missing_std_flagged(tmp_path):
    write_spc(tmp_path / "mc.rad.spc", full(1.5))
    status, _ = L.validate_run_outputs(tmp_path)
    assert status == "no-std-output"


def test_negative_std_rejected(tmp_path):
    write_spc(tmp_path / "mc.rad.spc", full(1.5))
    stds = full(0.05)
    stds[L.WAVELENGTH_NM[3]] = -0.1
    write_spc(tmp_path / "mc.rad.std.spc", stds)
    status, _ = L.validate_run_outputs(tmp_path)
    assert status == "invalid-std"


def test_noise_dominated_flagged(tmp_path):
    # std >= value at every wavelength -> not ordinary ok
    write_spc(tmp_path / "mc.rad.spc", full(0.01))
    write_spc(tmp_path / "mc.rad.std.spc", full(0.02))
    status, _ = L.validate_run_outputs(tmp_path)
    assert status == "noise-dominated"


def test_provenance_has_file_checksums():
    prov = L.data_provenance(L.find_data_dir())
    fs = prov["fileSha256"]
    assert fs.get("atmosphere_afglus")
    assert fs.get("solar_atlas_plus_modtran")
    # each checksum is a 64-hex sha256
    for v in fs.values():
        if v is not None:
            assert len(v) == 64
