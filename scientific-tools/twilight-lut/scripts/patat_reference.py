#!/usr/bin/env python3
"""Patat, Ugolnikov & Postylyakov (2006) zenith twilight V reference.

Primary source: A&A 455, 385. DOI 10.1051/0004-6361:20064992,
arXiv astro-ph/0604128. >2000 calibrated UBVRI twilight spectra at ESO Paranal
(2640 m). We use the reported zenith V-band surface-brightness law.

>>> COEFFICIENTS BELOW ARE TRANSCRIBED FROM THE MILESTONE-3 TASK BRIEF AND
>>> MUST BE VERIFIED AGAINST THE PRIMARY PDF BEFORE ANY PRODUCTION CLAIM.
>>> The build environment could not reach the DOI/arXiv servers (HTTP 000),
>>> so primaryObservationalValidationStatus remains PENDING-VERIFICATION.

Zenith V surface brightness vs solar zenith distance z (deg):
  V(z) = 11.84 + 1.518*(z-95) - 0.057*(z-95)^2      [mag/arcsec^2]
valid z in 95..105 deg  <=>  solar depression 5..15 deg.
Reported V-band RMS ~0.18 mag; early-range slope ~1.14 +/- 0.02 mag/deg.

Site: Paranal, elevation ~2640 m, low aerosol, clear. A sea-level AOD-0.15
simulation is NOT a matched comparison; use the elevation-matched hardening
runs and add the Paranal zenith night-sky floor (V ~ 21.9 mag/arcsec^2) before
comparing to a measurement that contains the total background.
"""
PATAT_V = {"c0": 11.84, "c1": 1.518, "c2": -0.057,
           "zRefDeg": 95.0, "zValidDeg": (95.0, 105.0),
           "depressionValidDeg": (5.0, 15.0), "rmsMag": 0.18,
           "earlySlopeMagPerDeg": 1.14, "earlySlopeErrMagPerDeg": 0.02,
           "siteElevationM": 2640, "band": "Johnson V",
           "source": "Patat et al. 2006 A&A 455,385 (astro-ph/0604128)",
           "status": "TRANSCRIBED-FROM-BRIEF-NEEDS-PRIMARY-VERIFICATION"}
PARANAL_ZENITH_V_FLOOR = 21.9   # mag/arcsec^2, dark-sky zenith (approx)


def patat_zenith_v(sun_depression_deg):
    """Patat zenith V (mag/arcsec^2) for solar depression 5..15 deg, else None."""
    lo, hi = PATAT_V["depressionValidDeg"]
    if not (lo <= sun_depression_deg <= hi):
        return None
    z = 90.0 + sun_depression_deg
    dz = z - PATAT_V["zRefDeg"]
    return PATAT_V["c0"] + PATAT_V["c1"] * dz + PATAT_V["c2"] * dz * dz


def add_floor_mag(v_twilight, v_floor=PARANAL_ZENITH_V_FLOOR):
    """Combine a twilight-only V surface brightness with a night floor in flux."""
    if v_twilight is None:
        return v_floor
    import math
    f = 10 ** (-0.4 * v_twilight) + 10 ** (-0.4 * v_floor)
    return -2.5 * math.log10(f)


if __name__ == "__main__":
    for d in (5, 6, 8, 10, 12, 15):
        print(f"dep {d}: Patat zenith V = {patat_zenith_v(d):.2f} mag/arcsec2")
