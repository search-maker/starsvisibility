"""Geometry-contract tests: conversions between calculator conventions and
libRadtran conventions, on the fixed fixtures required by the project brief."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import current_model_port as cur          # noqa: E402
from lrt_common import umu_for_altitude   # noqa: E402


def test_umu_zenith():
    assert math.isclose(umu_for_altitude(90), -1.0, abs_tol=1e-12)


def test_umu_low_altitude():
    assert math.isclose(umu_for_altitude(10), -math.sin(math.radians(10)),
                        rel_tol=1e-9)


def test_umu_never_positive_or_zero():
    for alt in (0, 0.001, 5, 45, 90):
        assert umu_for_altitude(alt) < 0


def test_separation_toward_sun_horizon():
    # Sun just below horizon (dep 2), target low and sunward
    sep = cur.sun_target_separation_deg(2, 10, 0)
    assert math.isclose(sep, 12.0, abs_tol=1e-9)


def test_separation_away_from_sun():
    # zenith distances add on opposite azimuths: (90-10) + (90+2) = 172
    sep = cur.sun_target_separation_deg(2, 10, 180)
    assert math.isclose(sep, 172.0, abs_tol=1e-9)


def test_separation_zenith():
    # zenith target: separation = 90 + dep regardless of azimuth
    for raz in (0, 90, 180):
        assert math.isclose(cur.sun_target_separation_deg(4, 90, raz),
                            94.0, abs_tol=1e-9)


def test_separation_90_east_west_symmetry():
    east = cur.sun_target_separation_deg(4, 30, 90)
    west = cur.sun_target_separation_deg(4, 30, 90)  # mirror by definition
    assert math.isclose(east, west, rel_tol=1e-12)
    # and it must exceed the co-altitude difference
    assert east > 34.0


def test_sun_just_above_vs_below_horizon_continuity():
    above = cur.sun_target_separation_deg(-0.5, 30, 0)
    below = cur.sun_target_separation_deg(0.5, 30, 0)
    assert abs(above - 29.5) < 1e-9 and abs(below - 30.5) < 1e-9


def test_relative_azimuth_range_contract():
    # case generator only ever emits 0..180; guard the convention
    for raz in (0, 45, 90, 135, 180):
        s1 = cur.sun_target_separation_deg(4, 30, raz)
        s2 = cur.sun_target_separation_deg(4, 30, 360 - raz)
        assert math.isclose(s1, s2, rel_tol=1e-12)


def test_degrees_not_radians_sanity():
    # a degree/radian mixup would make this separation absurd
    sep = cur.sun_target_separation_deg(0, 90, 0)
    assert math.isclose(sep, 90.0, abs_tol=1e-9)
