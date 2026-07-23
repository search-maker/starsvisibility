#!/usr/bin/env python3
"""Line-faithful Python port of the calculator's twilight/sky/NELM chain.

Ported from index.html (branch base c9a48a6):
- nLFromMag/magFromNL          (lines 14447-14448)
- TWILIGHT_ANCHORS + legacy    (lines 14908-14943)
- defaultTwilightAddedNLAfter6 (lines 14945-14966)
- twilightExcessNL             (lines 14968-14976)
- directionalTwilightFactor    (lines 15006-15012)
- airMass (Kasten & Young)     (lines 14254-14258)
- limitingMagnitudeFromSkyBrightness (lines 15143-15151)
Any change here must mirror the JS exactly; tests compare against fixture
values generated from the same formulas.
"""
import math

TWILIGHT_ANCHORS = [(0, 6.6689), (3, 5.4580), (6, 4.4253), (9, 3.9513),
                    (12, 3.4965), (15, 2.7658), (18, -math.inf)]
TWILIGHT_POST6_SLOPE_MAG_PER_DEG = 0.95
TWILIGHT_FAST_SEGMENT_END_DEG = 12
TWILIGHT_NIGHT_BLEND_END_DEG = 16
OLD_TWILIGHT_LOG_NL_AT_6 = 4.4253
OLD_TWILIGHT_NL_AT_6 = 10 ** OLD_TWILIGHT_LOG_NL_AT_6


def nl_from_mag(sb):
    return 34.08 * math.exp(20.7233 - 0.92104 * sb)


def mag_from_nl(b):
    return (20.7233 - math.log(max(b, 1e-3) / 34.08)) / 0.92104


TWILIGHT_SQM_AT_6 = mag_from_nl(OLD_TWILIGHT_NL_AT_6)


def smoothstep01(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def legacy_twilight_excess_nl(sun_dep_deg):
    if sun_dep_deg >= 18:
        return 0.0
    if sun_dep_deg < 0:
        return 1e8
    for (d0, v0), (d1, v1) in zip(TWILIGHT_ANCHORS, TWILIGHT_ANCHORS[1:]):
        if d0 <= sun_dep_deg <= d1:
            if v1 == -math.inf:
                frac = (sun_dep_deg - d0) / (d1 - d0)
                return (10 ** v0) * (1 - frac) ** 3
            log_b = v0 + (v1 - v0) * (sun_dep_deg - d0) / (d1 - d0)
            return 10 ** log_b
    return 0.0


def default_twilight_added_nl_after6(dep, base_sqm):
    if not math.isfinite(dep):
        return 0.0
    if not math.isfinite(base_sqm):
        base_sqm = 21.8
    base_nl = nl_from_mag(base_sqm)
    if dep >= TWILIGHT_NIGHT_BLEND_END_DEG:
        return 0.0
    fast_sqm_at_12 = TWILIGHT_SQM_AT_6 + TWILIGHT_POST6_SLOPE_MAG_PER_DEG * (
        TWILIGHT_FAST_SEGMENT_END_DEG - 6)
    if dep <= TWILIGHT_FAST_SEGMENT_END_DEG:
        target_total_sqm = TWILIGHT_SQM_AT_6 + \
            TWILIGHT_POST6_SLOPE_MAG_PER_DEG * (dep - 6)
    else:
        t = smoothstep01((dep - TWILIGHT_FAST_SEGMENT_END_DEG) /
                         (TWILIGHT_NIGHT_BLEND_END_DEG - TWILIGHT_FAST_SEGMENT_END_DEG))
        start_sqm = min(fast_sqm_at_12, base_sqm)
        target_total_sqm = start_sqm + (base_sqm - start_sqm) * t
    target_total_sqm = min(target_total_sqm, base_sqm)
    return max(0.0, nl_from_mag(target_total_sqm) - base_nl)


def twilight_excess_nl(sun_dep_deg, baseline_sqm=21.8):
    if sun_dep_deg <= 6:
        return legacy_twilight_excess_nl(sun_dep_deg)
    return default_twilight_added_nl_after6(sun_dep_deg, baseline_sqm)


def directional_twilight_factor(sun_star_separation_deg, star_app_alt_deg):
    sep = max(0.0, sun_star_separation_deg)
    h = max(0.0, star_app_alt_deg)
    separation_factor = 1 + 1.8 * math.exp(-sep / 28)
    altitude_factor = 1 + 0.75 * math.exp(-h / 18)
    return separation_factor * altitude_factor


def air_mass(h_app_deg):
    if h_app_deg < -2:
        return 40.0
    denom = math.sin(math.radians(h_app_deg)) + \
        0.50572 * (h_app_deg + 6.07995) ** -1.6364
    return 1 / denom


def limiting_magnitude_from_sky_brightness(sb, pupil_mm=7, observer_age=30,
                                           acuity=1.0, dark_adaptation=1.0):
    m = 7.93 - 5 * math.log10(10 ** (4.316 - sb / 5) + 1)
    m += 2.5 * math.log10(max(0.3, pupil_mm / 7))
    m -= 0.02 * max(0, observer_age - 25)
    m += 2.5 * math.log10(max(0.5, acuity))
    m -= (1 - max(0.0, min(1.0, dark_adaptation)))
    return m


def sun_target_separation_deg(sun_depression_deg, target_alt_deg, rel_az_deg):
    """Angular separation between target (alt, relAz) and Sun (alt=-dep, az=0)."""
    a1, a2 = math.radians(target_alt_deg), math.radians(-sun_depression_deg)
    c = math.sin(a1) * math.sin(a2) + \
        math.cos(a1) * math.cos(a2) * math.cos(math.radians(rel_az_deg))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def current_model_twilight_nl(sun_depression_deg, target_alt_deg, rel_az_deg,
                              baseline_sqm=21.8):
    """The exact quantity Btwi the calculator adds at the target direction."""
    sep = sun_target_separation_deg(sun_depression_deg, target_alt_deg, rel_az_deg)
    return twilight_excess_nl(sun_depression_deg, baseline_sqm) * \
        directional_twilight_factor(sep, target_alt_deg)


def total_sky_mag_arcsec2(twilight_nl, target_alt_deg, baseline_sqm=21.8):
    """Reproduce localSkyBrightnessComponents for a moonless, zenith-referenced
    baseline: dark floor with horizon brightening + twilight excess."""
    b_dark = nl_from_mag(baseline_sqm)
    x = air_mass(max(target_alt_deg, 0.1))
    b_dark *= 1 + 0.4 * max(0.0, x - 1)
    return mag_from_nl(b_dark + twilight_nl)
