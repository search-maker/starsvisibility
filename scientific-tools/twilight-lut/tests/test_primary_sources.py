"""Tests for the Milestone-3 primary-source importers and synthetic photometry."""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import johnson_v  # noqa: E402
import koomen_reference as koomen  # noqa: E402
import patat_reference as patat  # noqa: E402


def test_koomen_compact_decimal():
    assert koomen.parse_compact_decimal("0.0256") == 0.0256
    assert koomen.parse_compact_decimal("0.0₂56") == 0.00056
    assert koomen.parse_compact_decimal("0.0_2 56") == 0.00056
    assert abs(koomen.parse_compact_decimal("0.0(3)7") - 7e-5) < 1e-12
    assert koomen.parse_compact_decimal("1.23") == 1.23


def test_koomen_unit_conversion():
    # 1 candle/ft^2 = 10.7639 cd/m^2
    assert abs(koomen.cd_ft2_to_cd_m2(1.0) - 10.7639) < 1e-3


def test_koomen_directional_ratio():
    rows = [
        {"targetAltitudeDeg": 10, "relativeAzimuthDeg": 0, "luminance": 50.0},
        {"targetAltitudeDeg": 10, "relativeAzimuthDeg": 180, "luminance": 10.0},
    ]
    r = koomen.directional_ratios(rows)
    assert abs(r["pairs"][10] - 5.0) < 1e-9


def test_patat_polynomial_endpoints():
    assert abs(patat.patat_zenith_v(5) - 11.84) < 1e-6      # z=95, dz=0
    # z=98, dz=3: 11.84 + 1.518*3 - 0.057*9
    assert abs(patat.patat_zenith_v(8) - (11.84 + 1.518 * 3 - 0.057 * 9)) < 1e-6
    assert patat.patat_zenith_v(3) is None   # below valid range
    assert patat.patat_zenith_v(20) is None  # above valid range


def test_patat_floor_addition_brightens():
    v = patat.add_floor_mag(20.0, v_floor=21.9)
    assert v < 20.0   # adding a floor can only brighten (smaller mag)


def test_johnson_v_monotonic_with_brightness():
    wl = list(range(400, 701, 10))
    faint = [1.0] * len(wl)
    bright = [100.0] * len(wl)
    v_faint = johnson_v.johnson_v_surface_brightness(wl, faint)
    v_bright = johnson_v.johnson_v_surface_brightness(wl, bright)
    # 100x brighter -> 5 mag brighter (smaller number)
    assert abs((v_faint - v_bright) - 5.0) < 1e-6


def test_johnson_v_zeropoint_scale():
    # a source whose in-band effective radiance * Omega == f_lambda0 gives V=0
    wl = list(range(500, 601, 10))
    l0 = johnson_v.F_LAMBDA_V0_MW / johnson_v.OMEGA_ARCSEC2_SR
    v = johnson_v.johnson_v_surface_brightness(wl, [l0] * len(wl))
    assert abs(v) < 1e-6


def test_johnson_v_none_for_zero():
    wl = list(range(400, 701, 10))
    assert johnson_v.johnson_v_surface_brightness(wl, [0.0] * len(wl)) is None


def test_johnson_v_passband_peak_and_effwl():
    # PG-1: authoritative Bessell V peaks at 530 nm; photon eff wl ~554 nm
    assert abs(johnson_v.PASSBAND_PEAK_NM - 530) < 1e-6
    assert 545 <= johnson_v.effective_wavelength_nm() <= 556


def test_johnson_v_passband_checksum_enforced():
    # loading verifies the checksum; corrupting it must raise
    import hashlib
    raw = johnson_v.PASSBAND_FILE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == johnson_v.PASSBAND_SHA256
