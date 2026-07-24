"""Directive #2: observerElevationM must reach uvspec via `altitude` (km), not
be silently dropped; `zout 0` is separate; the configuration hash must match the
input actually sent, and different elevations must produce different input."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import lrt_common as L  # noqa: E402


def case(elev):
    return {"sunDepressionDeg": 4, "targetAltitudeDeg": 30, "relativeAzimuthDeg": 90,
            "aod550": 0.15, "observerElevationM": elev, "photonCount": 200000,
            "randomSeed": 1000}


def build(elev, tmp_path):
    wl = tmp_path / "wl.dat"
    L.write_wavelength_grid(wl)
    return L.build_input(case(elev), "/data", wl, tmp_path / "mc")


def test_sea_level_has_no_altitude_line(tmp_path):
    txt = build(0, tmp_path)
    assert "\naltitude " not in txt
    assert "zout 0" in txt


def test_elevated_mystic_refuses_broken_altitude(tmp_path):
    # FINDING: `altitude` is rejected by the montecarlo solver. build_input must
    # NOT emit broken input for elevated MYSTIC cases; it raises instead.
    import pytest
    with pytest.raises(NotImplementedError):
        build(2640, tmp_path)   # default solver is mystic


def test_elevation_emits_altitude_for_disort(tmp_path):
    wl = tmp_path / "wl.dat"
    L.write_wavelength_grid(wl)
    c = case(2640)
    c["solver"] = "disort"
    txt = L.build_input(c, "/data", wl, tmp_path / "mc")
    assert "altitude 2.6400" in txt      # 2640 m -> 2.64 km (DISORT-family)
    assert "zout 0" in txt               # zout is separate from altitude


def test_negative_elevation_fails_closed_all_solvers(tmp_path):
    # fail-closed for EVERY unsupported nonzero elevation, incl negative
    import pytest
    wl = tmp_path / "wl.dat"
    L.write_wavelength_grid(wl)
    for solver in ("mystic", "disort"):
        c = case(-50)
        c["solver"] = solver
        with pytest.raises(NotImplementedError):
            L.build_input(c, "/data", wl, tmp_path / "mc")


def test_config_hash_tracks_elevation_even_if_run_deferred():
    # elevation is part of the restart identity regardless of solver support
    assert (L.configuration_hash(case(0), "v", {"d": 1})
            != L.configuration_hash(case(2640), "v", {"d": 1}))


def test_config_hash_tracks_elevation():
    h0 = L.configuration_hash(case(0), "v", {"d": 1})
    h2 = L.configuration_hash(case(2640), "v", {"d": 1})
    assert h0 != h2
    # and the canonical config records the elevation actually used
    assert L.canonical_config(case(2640))["observerElevationM"] == 2640.0


def test_default_vroom_is_off(tmp_path):
    # grid production default (directive #3)
    txt = build(0, tmp_path)
    assert "mc_vroom off" in txt
    assert L.canonical_config(case(0))["vroom"] == "off"
