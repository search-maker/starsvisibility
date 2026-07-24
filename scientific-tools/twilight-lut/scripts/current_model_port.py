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


# Saemundsson refraction (index.html refractionDeg), with the production global
# defaults currentPressureHPa=1010, currentTemperatureC=10. Ported so the LUT
# geometry contract can convert between GEOMETRIC (true) and APPARENT target
# altitude explicitly instead of conflating them.
CURRENT_PRESSURE_HPA = 1010.0
CURRENT_TEMPERATURE_C = 10.0


def refraction_deg(h_true, pressure_hpa=CURRENT_PRESSURE_HPA,
                   temperature_c=CURRENT_TEMPERATURE_C):
    if h_true < -1:
        return 0.0
    r = 1.02 / math.tan(math.radians(h_true + 10.3 / (h_true + 5.11)))  # arcmin
    weather = (pressure_hpa / 1010.0) * (283.0 / (273.0 + temperature_c))
    return max(0.0, r) * weather / 60.0


def apparent_altitude(h_true, **kw):
    """APPARENT (refracted) altitude from GEOMETRIC/true altitude."""
    return h_true + refraction_deg(h_true, **kw)


def geometric_from_apparent(h_app, **kw):
    """Invert refraction: recover GEOMETRIC altitude from an APPARENT one.
    The LUT is indexed by GEOMETRIC altitude; a browser holding only apparent
    altitude must call this before indexing. Newton-free fixed-point iteration."""
    h = h_app
    for _ in range(40):
        h_new = h_app - refraction_deg(h, **kw)
        if abs(h_new - h) < 1e-9:
            break
        h = h_new
    return h


def limiting_magnitude_from_sky_brightness(sb, pupil_mm=7, acuity=1.0,
                                           dark_adaptation=1.0):
    # Synced to the current index.html (commit 6e7728f, "final scientific model
    # corrections"): the observer-AGE term was REMOVED from this formula upstream
    # and must NOT be restored (Milestone directive: do not restore deleted
    # logic). Age effects, if any, live elsewhere in the production model now.
    m = 7.93 - 5 * math.log10(10 ** (4.316 - sb / 5) + 1)
    m += 2.5 * math.log10(max(0.3, pupil_mm / 7))
    m += 2.5 * math.log10(max(0.5, acuity))
    m -= (1 - max(0.0, min(1.0, dark_adaptation)))
    return m


def sun_target_separation_deg(sun_depression_deg, target_alt_deg, rel_az_deg):
    """Angular separation between target (alt, relAz) and Sun (alt=-dep, az=0)."""
    a1, a2 = math.radians(target_alt_deg), math.radians(-sun_depression_deg)
    c = math.sin(a1) * math.sin(a2) + \
        math.cos(a1) * math.cos(a2) * math.cos(math.radians(rel_az_deg))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def local_sky_components(sun_depression_deg, target_geometric_altitude_deg,
                         target_apparent_altitude_deg, relative_azimuth_deg,
                         baseline_sqm=21.8):
    """Faithful port of localSkyBrightnessComponents for the moonless,
    zenith-referenced, no-calibration case (PG-2 end-to-end contract).

    Reproduces production exactly, including that the twilight excess is
    computed against the HORIZON-BRIGHTENED baseSkySqm (not raw baseline), and
    that horizon brightening + directional factor use the APPARENT altitude
    while the Sun-target separation uses the GEOMETRIC altitude."""
    b_dark = nl_from_mag(baseline_sqm)
    xs = air_mass(max(target_apparent_altitude_deg, 0.1))
    b_dark *= 1 + 0.4 * max(0.0, xs - 1)          # horizon brightening (apparent)
    base_sky_sqm = mag_from_nl(b_dark)
    sep = sun_target_separation_deg(sun_depression_deg,
                                    target_geometric_altitude_deg,
                                    relative_azimuth_deg)
    twilight_base_nl = twilight_excess_nl(sun_depression_deg, base_sky_sqm)
    b_twi = twilight_base_nl * directional_twilight_factor(
        sep, target_apparent_altitude_deg)
    total_mag = mag_from_nl(b_dark + b_twi)
    return {"twilightAddedNL": b_twi, "baseSkyNL": b_dark,
            "baseSkySqm": base_sky_sqm, "skyBrightnessMagArcsec2": total_mag,
            "sunStarSeparationDeg": sep}


def current_model_twilight_nl(sun_depression_deg, target_geometric_altitude_deg,
                              target_apparent_altitude_deg, relative_azimuth_deg,
                              baseline_sqm=21.8):
    """Btwi the calculator adds at the target direction (PG-2 explicit
    contract). Delegates to local_sky_components so it matches production
    including the horizon-brightened base used for the excess."""
    return local_sky_components(
        sun_depression_deg, target_geometric_altitude_deg,
        target_apparent_altitude_deg, relative_azimuth_deg,
        baseline_sqm)["twilightAddedNL"]


def current_model_twilight_nl_from_geometric(sun_depression_deg,
                                             target_geometric_altitude_deg,
                                             relative_azimuth_deg,
                                             baseline_sqm=21.8):
    """Convenience: derive apparent altitude from geometric via the production
    Saemundsson refraction, then evaluate."""
    app = apparent_altitude(target_geometric_altitude_deg)
    return current_model_twilight_nl(sun_depression_deg,
                                     target_geometric_altitude_deg, app,
                                     relative_azimuth_deg, baseline_sqm)


def total_sky_mag_arcsec2(twilight_nl, target_apparent_altitude_deg,
                          baseline_sqm=21.8):
    """Total sky brightness given an already-computed twilight excess. NOTE:
    this recomputes b_dark; it is exact only when `twilight_nl` was produced
    with the same apparent altitude and baseline. For a faithful end-to-end
    value prefer local_sky_components(...)['skyBrightnessMagArcsec2']."""
    b_dark = nl_from_mag(baseline_sqm)
    x = air_mass(max(target_apparent_altitude_deg, 0.1))
    b_dark *= 1 + 0.4 * max(0.0, x - 1)
    return mag_from_nl(b_dark + twilight_nl)
