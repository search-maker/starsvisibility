"""FC-4: spectral-integration convergence + fail-loud Johnson V."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import integrate_visual_response as IV  # noqa: E402


def test_raw_vs_1nm_and_node_convergence():
    # a smooth reference spectrum: raw 0.05 nm grid vs 1 nm vs 10 nm all agree
    def spec(step):
        wl = [400 + i * step for i in range(int(300 / step) + 1)]
        rad = [1.0 + 0.001 * (w - 550) for w in wl]   # smooth ramp
        return wl, rad
    wl_raw, r_raw = spec(0.05)
    wl_1nm, r_1nm = spec(1.0)
    wl_10, r_10 = spec(10.0)
    L_raw = IV.trapezoid_weighted(wl_raw, r_raw, IV.V_PHOT, IV.KM_PHOTOPIC)
    L_1nm = IV.trapezoid_weighted(wl_1nm, r_1nm, IV.V_PHOT, IV.KM_PHOTOPIC)
    L_10 = IV.trapezoid_weighted(wl_10, r_10, IV.V_PHOT, IV.KM_PHOTOPIC)
    assert abs(L_raw - L_1nm) / L_raw < 1e-3
    assert abs(L_raw - L_10) / L_raw < 2e-2


def test_johnson_v_import_is_mandatory():
    # directive #4: JV is imported at module load, not swallowed by try/except
    assert hasattr(IV, "JV")
    assert hasattr(IV.JV, "johnson_v_surface_brightness")
