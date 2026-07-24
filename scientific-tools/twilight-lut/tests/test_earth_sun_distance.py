"""FC-5: Earth-Sun distance inverse-square radiance scaling contract."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import earth_sun_distance as ES  # noqa: E402


def test_factor_is_inverse_square():
    assert abs(ES.sun_distance_radiance_factor(1.0) - 1.0) < 1e-12
    assert abs(ES.sun_distance_radiance_factor(2.0) - 0.25) < 1e-12
    # perihelion closer than 1 AU -> brighter (>1)
    assert ES.sun_distance_radiance_factor(0.983) > 1.0
    # aphelion farther -> fainter (<1)
    assert ES.sun_distance_radiance_factor(1.017) < 1.0


def test_distance_series_perihelion_aphelion():
    r_jan = ES.earth_sun_distance_au(3)     # ~perihelion
    r_jul = ES.earth_sun_distance_au(185)   # ~aphelion
    assert r_jan < 1.0 < r_jul
    assert 0.98 < r_jan < 0.985
    assert 1.015 < r_jul < 1.018


def test_invalid_distance_raises():
    import pytest
    with pytest.raises(ValueError):
        ES.sun_distance_radiance_factor(0)
