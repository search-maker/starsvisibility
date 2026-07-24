#!/usr/bin/env python3
"""FC-5: Earth-Sun distance contract for absolute twilight radiance.

Absolute solar twilight radiance scales as the inverse square of the Earth-Sun
distance. Day-of-year is NOT a LUT axis. Instead:
  - the LUT is generated at a documented REFERENCE distance of 1 AU (libRadtran's
    default solar spectrum, i.e. no `day_of_year`, is the 1 AU mean);
  - the reference is stored in the LUT metadata (`sunEarthDistanceReferenceAU`);
  - at runtime the ABSOLUTE model scales the looked-up radiance by
    (1 AU / r_actual)^2, where r_actual comes from the production ephemerides;
  - the HYBRID directional-ratio model is (target/reference) at the same instant,
    so this factor cancels and need not be applied.

`day_of_year` in uvspec applies exactly this (1/r)^2 factor to the solar flux;
`validate_earth_sun_scaling.py` checks the LUT-side scaling against it.
"""
import math

REFERENCE_AU = 1.0


def earth_sun_distance_au(day_of_year):
    """Approximate Earth-Sun distance (AU) vs day-of-year. Standard first-order
    eccentricity series (perihelion ~ Jan 3). Matches the production ephemeris
    only to ~1e-4 AU; the runtime scaling must use the production r directly."""
    g = math.radians(357.528 + 0.9856003 * (day_of_year - 1))
    return 1.00014 - 0.01671 * math.cos(g) - 0.00014 * math.cos(2 * g)


def sun_distance_radiance_factor(sun_earth_distance_au, reference_au=REFERENCE_AU):
    """Multiplicative factor to convert radiance generated at `reference_au` to
    radiance at `sun_earth_distance_au`: (reference/actual)^2. Absolute model
    applies this; hybrid ratio cancels it."""
    if not (sun_earth_distance_au and sun_earth_distance_au > 0):
        raise ValueError("sun_earth_distance_au must be > 0")
    return (reference_au / sun_earth_distance_au) ** 2


if __name__ == "__main__":
    for d in (3, 95, 185, 266):   # ~perihelion, equinox, ~aphelion, equinox
        r = earth_sun_distance_au(d)
        print(f"day {d:3d}: r={r:.5f} AU, radiance factor from 1 AU = "
              f"{sun_distance_radiance_factor(r):.5f}")
