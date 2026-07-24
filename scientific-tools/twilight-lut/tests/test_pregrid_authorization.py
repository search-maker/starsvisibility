"""PG-4: pre-grid gates derived from measured results; core/extension split;
--quick can never pass a gate."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import run_pregrid_hardening as P  # noqa: E402
import current_model_port as cur  # noqa: E402


def good_result():
    return {
        "quickMode": False,
        "refraction": {"estimatedRefractionErrorMagAt0p1deg": 0.05},
        "elevation": {"cases": [{"radiance": 1.0}, {"radiance": 0.5}]},
        "deepBoundary": {"cases": [{"status": "ok", "reportedRelErr": 0.10}]},
        "geoApparent": {"mapping": [
            {"geometricAltDeg": a, "apparentAltDeg": cur.apparent_altitude(a)}
            for a in (10, 30, 90)]},
    }


def test_quick_mode_never_authorizes_core(monkeypatch):
    monkeypatch.setattr(P, "_load_vroom_authorization", lambda: True)
    g = P.gate(good_result(), quick=True)
    assert g["coreGridAuthorized"] is False
    assert g["extension9to10Authorized"] is False


def test_core_authorized_with_full_evidence(monkeypatch):
    monkeypatch.setattr(P, "_load_vroom_authorization", lambda: True)
    g = P.gate(good_result(), quick=False)
    assert g["coreGridAuthorized"] is True


def test_core_blocked_when_vroom_unauthorized(monkeypatch):
    monkeypatch.setattr(P, "_load_vroom_authorization", lambda: False)
    assert P.gate(good_result(), quick=False)["coreGridAuthorized"] is False


def test_core_blocked_when_refraction_missing(monkeypatch):
    monkeypatch.setattr(P, "_load_vroom_authorization", lambda: True)
    r = good_result()
    r["refraction"]["estimatedRefractionErrorMagAt0p1deg"] = None
    assert P.gate(r, quick=False)["coreGridAuthorized"] is False


def test_geo_apparent_verified_against_port(monkeypatch):
    monkeypatch.setattr(P, "_load_vroom_authorization", lambda: True)
    r = good_result()
    # corrupt the mapping so it no longer matches the ported refraction
    r["geoApparent"]["mapping"][0]["apparentAltDeg"] += 1.0
    assert P.gate(r, quick=False)["coreGridAuthorized"] is False


def test_extension_needs_deep_boundary_but_core_independent(monkeypatch):
    monkeypatch.setattr(P, "_load_vroom_authorization", lambda: True)
    r = good_result()
    r["deepBoundary"]["cases"] = [{"status": "ok", "reportedRelErr": 0.40}]  # too noisy
    g = P.gate(r, quick=False)
    assert g["coreGridAuthorized"] is True          # core unaffected
    assert g["extension9to10Authorized"] is False   # extension blocked
