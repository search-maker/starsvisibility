"""PG-2: end-to-end current-model parity against production JavaScript.

Validates the COMPLETE Python chain (Btwi, total sky brightness, NELM) against
fixtures from the real index.html chain, exercising the geometric-vs-apparent
altitude contract. Regenerate with scripts/generate_js_e2e_fixtures.py.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import current_model_port as cur  # noqa: E402

FIX = ROOT / "fixtures" / "js_e2e_fixtures.json"
pytestmark = pytest.mark.skipif(not FIX.exists(),
                                reason="run generate_js_e2e_fixtures.py first")


def cases():
    return json.loads(FIX.read_text())["cases"]


def rel(a, b):
    return abs(a - b) / max(abs(a), abs(b), 1e-30)


def test_apparent_altitude_matches_js_chain():
    for c in cases():
        assert abs(cur.apparent_altitude(c["geometricAlt"]) - c["apparentAlt"]) < 1e-9


def test_separation_uses_geometric_altitude():
    for c in cases():
        sep = cur.sun_target_separation_deg(c["dep"], c["geometricAlt"], c["raz"])
        assert abs(sep - c["sunStarSeparationDeg"]) < 1e-6


def test_btwi_end_to_end_matches_js():
    for c in cases():
        btwi = cur.current_model_twilight_nl(
            c["dep"], c["geometricAlt"], c["apparentAlt"], c["raz"],
            c["baselineSqm"])
        assert rel(btwi, c["twilightAddedNL"]) < 1e-7, c


def test_total_sky_brightness_matches_js():
    for c in cases():
        btwi = cur.current_model_twilight_nl(
            c["dep"], c["geometricAlt"], c["apparentAlt"], c["raz"],
            c["baselineSqm"])
        total = cur.total_sky_mag_arcsec2(btwi, c["apparentAlt"], c["baselineSqm"])
        assert abs(total - c["totalSkyMag"]) < 1e-6, c


def test_nelm_end_to_end_matches_js():
    for c in cases():
        btwi = cur.current_model_twilight_nl(
            c["dep"], c["geometricAlt"], c["apparentAlt"], c["raz"],
            c["baselineSqm"])
        total = cur.total_sky_mag_arcsec2(btwi, c["apparentAlt"], c["baselineSqm"])
        nelm = cur.limiting_magnitude_from_sky_brightness(total)
        assert abs(nelm - c["nelm"]) < 1e-6, c


def test_geometric_apparent_contract_is_distinct_at_low_altitude():
    # at alt 10 the apparent altitude differs from geometric by ~0.09 deg, and
    # using the wrong one changes Btwi measurably -> proves the contract matters
    c = next(x for x in cases() if x["geometricAlt"] == 10 and x["raz"] == 0
             and x["dep"] == 4)
    correct = cur.current_model_twilight_nl(c["dep"], 10, c["apparentAlt"],
                                            c["raz"], c["baselineSqm"])
    swapped = cur.current_model_twilight_nl(c["dep"], 10, 10.0, c["raz"],
                                            c["baselineSqm"])   # apparent==geometric (wrong)
    assert correct != swapped
    assert abs(correct - c["twilightAddedNL"]) / c["twilightAddedNL"] < 1e-7
