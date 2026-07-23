"""Regression tests pinning the Python port to the JS implementation.

Reference values are computed from the identical formulas at fixed inputs and
serve as tamper detection for both sides of the port. The SCIENTIFIC_MODEL_REVIEW
table in the repository root provides independent anchors for the twilight curve
(old-vs-new default twilight example, base SQM 21.8).
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import current_model_port as cur  # noqa: E402


def total_sqm(dep, base=21.8):
    b_dark = cur.nl_from_mag(base)
    return cur.mag_from_nl(b_dark + cur.twilight_excess_nl(dep, base))


def test_review_table_anchor_dep6():
    # SCIENTIFIC_MODEL_REVIEW.md: dep 6 -> 15.27 SQM (base 21.8)
    assert abs(total_sqm(6) - 15.27) < 0.01


def test_code_anchor_dep8():
    # NOTE: SCIENTIFIC_MODEL_REVIEW.md's example table (17.27 at dep 8) used a
    # 1.0 mag/deg slope, but the implemented constant is 0.95 -> 17.17. The
    # port follows the CODE; the doc-table inconsistency is recorded in
    # CURRENT_MODEL_ANALYSIS.md.
    assert abs(total_sqm(8) - 17.168) < 0.01


def test_code_anchor_dep12():
    assert abs(total_sqm(12) - 20.968) < 0.01


def test_review_table_anchor_dep16():
    assert abs(total_sqm(16) - 21.80) < 0.01


def test_legacy_anchor_nodes():
    for dep, log_nl in [(0, 6.6689), (3, 5.4580), (6, 4.4253)]:
        assert math.isclose(math.log10(cur.legacy_twilight_excess_nl(dep)),
                            log_nl, abs_tol=1e-9)


def test_daylight_placeholder():
    assert cur.legacy_twilight_excess_nl(-0.1) == 1e8


def test_directional_factor_bounds():
    assert math.isclose(cur.directional_twilight_factor(0, 0), 2.8 * 1.75,
                        rel_tol=1e-12)
    assert cur.directional_twilight_factor(180, 90) < 1.01


def test_directional_factor_monotone_in_sep():
    vals = [cur.directional_twilight_factor(s, 30) for s in (0, 30, 90, 150)]
    assert vals == sorted(vals, reverse=True)


def test_airmass_kasten_young():
    # Kasten & Young evaluates to 0.99971 at the zenith, not exactly 1
    assert math.isclose(cur.air_mass(90), 1.0, rel_tol=1e-3)
    assert 37 < cur.air_mass(0) < 41
    assert cur.air_mass(-3) == 40.0


def test_nelm_dark_sky():
    # sb=21.8, default observer (age 30 -> -0.1 mag) ~ 6.4-6.6
    m = cur.limiting_magnitude_from_sky_brightness(21.8)
    assert 6.2 < m < 6.8


def test_nelm_bright_sky_lower():
    assert cur.limiting_magnitude_from_sky_brightness(10.0) < \
           cur.limiting_magnitude_from_sky_brightness(20.0)
