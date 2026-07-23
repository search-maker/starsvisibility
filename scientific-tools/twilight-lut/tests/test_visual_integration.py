"""Unit tests for spectral parsing, visual integration, and unit conversions."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import integrate_visual_response as ivr   # noqa: E402
import current_model_port as cur          # noqa: E402
from lrt_common import parse_spc, WAVELENGTH_NM  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_tables_cover_grid():
    assert len(ivr.V_PHOT) == len(WAVELENGTH_NM) == len(ivr.V_SCOT) == 41


def test_photopic_peak_at_555():
    i = WAVELENGTH_NM.index(550)
    assert max(ivr.V_PHOT) == ivr.V_PHOT[i] or max(ivr.V_PHOT) == ivr.V_PHOT[i + 1]


def test_flat_spectrum_luminance():
    # Flat radiance 1 mW/m2/nm/sr -> L = 683.002*1e-3*10*sum(V)
    rad = [1.0] * 41
    std = [0.0] * 41
    L, sL = ivr.weighted_sum(rad, std, ivr.V_PHOT, ivr.KM_PHOTOPIC)
    expected = 683.002 * 1e-3 * 10 * sum(ivr.V_PHOT)
    assert math.isclose(L, expected, rel_tol=1e-12)
    assert sL == 0.0


def test_uncertainty_quadrature():
    rad = [1.0] * 41
    std = [0.1] * 41
    _, sL = ivr.weighted_sum(rad, std, ivr.V_PHOT, ivr.KM_PHOTOPIC)
    expected = math.sqrt(sum((683.002 * v * 0.1 * 1e-3 * 10) ** 2
                             for v in ivr.V_PHOT))
    assert math.isclose(sL, expected, rel_tol=1e-12)


def test_nl_mag_roundtrip():
    for sb in (6.0, 12.0, 18.0, 21.8):
        assert math.isclose(cur.mag_from_nl(cur.nl_from_mag(sb)), sb,
                            rel_tol=1e-9)


def test_nl_conversion_constant():
    # 21.8 mag/arcsec2 should be ~1.7e-4 cd/m2 in the K&S convention
    nl = cur.nl_from_mag(21.8)
    cd = nl * ivr.CD_M2_PER_NL
    assert 1.2e-4 < cd < 2.4e-4


def _rec(rad, std):
    return {"binnedWavelengthNm": list(range(380, 781)),
            "binnedRadiance_mW_m2_nm_sr": [rad] * 401,
            "nodeRadiance_mW_m2_nm_sr": [rad] * 41,
            "nodeRadianceStd_mW_m2_nm_sr": [std] * 41}


def test_no_log_of_unresolved():
    out = ivr.integrate_record(_rec(1e-9, 1e-6))
    assert out["statisticallyResolved"] is False


def test_fine_vs_node_grid_consistency_flat():
    out = ivr.integrate_record(_rec(1.0, 0.0))
    # flat spectrum: trapezoid on 1 nm grid vs rectangle on 10 nm nodes agree
    assert out["wavelengthGridConsistency"] < 0.02


def test_interp_v_at_nodes():
    for i, w in enumerate(range(380, 781, 10)):
        assert math.isclose(ivr.interp_v(ivr.V_PHOT, w), ivr.V_PHOT[i],
                            rel_tol=1e-12)


def test_parse_spc_fixture():
    # committed fixture is a REAL uvspec 2.0.6-MYSTIC output
    # (sd00p0_alt90p0_raz000p0_aod0p150), fine solar-spectrum grid
    d = parse_spc(FIXTURES / "mc.rad.spc")
    assert len(d) == 8001
    assert math.isclose(d[550.0], 1.81648, rel_tol=1e-5)


def test_parse_spc_malformed(tmp_path):
    bad = tmp_path / "bad.spc"
    bad.write_text("550.0 0 0\nnot numbers here at all\n")
    try:
        parse_spc(bad)
    except ValueError:
        return
    # lines with <5 fields are skipped; the malformed line must not
    # silently produce a value
    assert parse_spc(bad) == {}
