"""RH-5: validate the Python port against fixtures generated from the REAL
production JavaScript (index.html via node), not against the same Python
formulas. Regenerate fixtures with scripts/generate_js_parity_fixtures.py.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import current_model_port as cur  # noqa: E402

FIX = ROOT / "fixtures" / "js_parity_fixtures.json"
pytestmark = pytest.mark.skipif(not FIX.exists(),
                                reason="run generate_js_parity_fixtures.py first")


def fixtures():
    return json.loads(FIX.read_text())["fixtures"]


def approx(a, b, rel=1e-9, abs_=1e-9):
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))


def test_refraction_and_apparent_altitude_match_js():
    for row in fixtures()["refraction_apparent"]:
        assert approx(cur.refraction_deg(row["hTrue"]), row["refractionDeg"], 1e-9)
        assert approx(cur.apparent_altitude(row["hTrue"]), row["apparentAltitude"], 1e-9)


def test_geometric_apparent_roundtrip():
    # inverting the JS apparent altitude recovers the JS true altitude
    for row in fixtures()["refraction_apparent"]:
        if row["hTrue"] < -0.5:
            continue
        recovered = cur.geometric_from_apparent(row["apparentAltitude"])
        assert approx(recovered, row["hTrue"], rel=1e-6, abs_=1e-4)


def test_airmass_matches_js():
    for row in fixtures()["airmass"]:
        assert approx(cur.air_mass(row["hApp"]), row["airMass"], 1e-9)


def test_twilight_excess_matches_js():
    for row in fixtures()["twilightExcessNL"]:
        assert approx(cur.twilight_excess_nl(row["dep"], row["base"]), row["nl"],
                      rel=1e-8, abs_=1e-6)


def test_directional_factor_matches_js():
    for row in fixtures()["directionalFactor"]:
        assert approx(cur.directional_twilight_factor(row["sep"], row["h"]),
                      row["factor"], 1e-9)


def test_nl_mag_roundtrip_matches_js():
    for row in fixtures()["nlmag"]:
        assert approx(cur.nl_from_mag(row["sb"]), row["nl"], rel=1e-9)
        assert approx(cur.mag_from_nl(cur.nl_from_mag(row["sb"])), row["back"], 1e-9)


def test_nelm_matches_js():
    for row in fixtures()["nelm"]:
        assert approx(cur.limiting_magnitude_from_sky_brightness(row["sb"]),
                      row["nelm"], rel=1e-9)


def test_true_and_apparent_altitude_are_separated():
    # the port must NOT treat geometric and apparent as the same at low altitude
    assert abs(cur.apparent_altitude(10) - 10) > 0.05   # ~0.09 deg at 10
    assert abs(cur.apparent_altitude(90) - 90) < 0.01
