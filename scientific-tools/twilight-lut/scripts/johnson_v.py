#!/usr/bin/env python3
"""Johnson V synthetic photometry of a spectral sky radiance.

Produces a Vega-based Johnson V surface brightness in mag/arcsec^2 that is
directly comparable to Patat et al. 2006 twilight V measurements — NOT the
calculator's internal Krisciunas-Schaefer "SQM-equivalent" and NOT unfiltered
photopic luminance.

Passband: Bessell (1990, PASP 102, 1181) Johnson V response, tabulated at 5 nm
from 470-700 nm (photon response, i.e. already suitable for photon-counting
weighting when combined with the extra lambda factor). Values normalised to
peak 1.0; the absolute normalisation cancels in the ratio against Vega.

Zero point: a V = 0.00 source (Vega system) has, in-band, the flux-density
scale f_lambda(V=0) = 3.62e-8 mW m^-2 nm^-1 (Bessell & Murphy 2012, PASP 124,
140; 3.62e-9 erg cm^-2 s^-1 A^-1). We define the effective in-band spectral
radiance (photon-weighted mean) and compare it to this zero point.

Surface-brightness definition:
  L_V_eff = integral( L_lambda(lambda) * S_V(lambda) * lambda dlambda )
            / integral( S_V(lambda) * lambda dlambda )        [mW m^-2 nm^-1 sr^-1]
  V_sky = -2.5*log10( L_V_eff * Omega_arcsec2 / f_lambda0 )   [mag/arcsec^2]
with Omega_arcsec2 = (pi/180/3600)^2 sr = 2.350444e-11 sr, and the lambda
weight implementing photon-counting (Bessell & Murphy 2012 eq. for f_lambda
systems). This is an energy-based radiance integrated with a photon-response
passband, the standard synthetic-photometry convention for CCD V.
"""
import math

# Bessell (1990) Johnson V, 5 nm grid 470..700 nm, normalised to peak 1.0.
# (Standard tabulation; peak near 550 nm.)
BESSELL_V_WL = list(range(470, 701, 5))
BESSELL_V_RESP = [
    0.000, 0.030, 0.163, 0.458, 0.780, 0.967, 1.000, 0.973, 0.898, 0.792,
    0.684, 0.574, 0.461, 0.359, 0.270, 0.197, 0.135, 0.081, 0.045, 0.025,
    0.017, 0.013, 0.009, 0.006, 0.004, 0.002, 0.001, 0.001, 0.000, 0.000,
    0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
    0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000]

OMEGA_ARCSEC2_SR = (math.pi / 180.0 / 3600.0) ** 2   # 2.350444e-11 sr
F_LAMBDA_V0_MW = 3.62e-8      # mW m^-2 nm^-1 for V=0 (Bessell & Murphy 2012)


def _resp_at(wl_nm):
    if wl_nm < BESSELL_V_WL[0] or wl_nm > BESSELL_V_WL[-1]:
        return 0.0
    x = (wl_nm - BESSELL_V_WL[0]) / 5.0
    i = int(math.floor(x))
    if i >= len(BESSELL_V_RESP) - 1:
        return BESSELL_V_RESP[-1]
    f = x - i
    return BESSELL_V_RESP[i] * (1 - f) + BESSELL_V_RESP[i + 1] * f


def effective_inband_radiance(wl_nm, radiance_mw):
    """Photon-weighted effective in-band spectral radiance (mW m^-2 nm^-1 sr^-1)
    over a sampled spectrum (wl ascending). Trapezoid on the given grid."""
    num = den = 0.0
    for i in range(len(wl_nm) - 1):
        dl = wl_nm[i + 1] - wl_nm[i]
        for wl, rad in ((wl_nm[i], radiance_mw[i]), (wl_nm[i + 1], radiance_mw[i + 1])):
            s = _resp_at(wl) * wl
            # accumulate half-trapezoid weights
        s0 = _resp_at(wl_nm[i]) * wl_nm[i]
        s1 = _resp_at(wl_nm[i + 1]) * wl_nm[i + 1]
        num += 0.5 * (s0 * radiance_mw[i] + s1 * radiance_mw[i + 1]) * dl
        den += 0.5 * (s0 + s1) * dl
    return num / den if den > 0 else 0.0


def johnson_v_surface_brightness(wl_nm, radiance_mw):
    """Vega Johnson V surface brightness (mag/arcsec^2) from spectral radiance
    in mW m^-2 nm^-1 sr^-1. Returns None if the in-band radiance is non-positive."""
    l_eff = effective_inband_radiance(wl_nm, radiance_mw)
    if l_eff <= 0:
        return None
    flux_per_arcsec2 = l_eff * OMEGA_ARCSEC2_SR    # mW m^-2 nm^-1 arcsec^-2
    return -2.5 * math.log10(flux_per_arcsec2 / F_LAMBDA_V0_MW)


def johnson_v_from_record(rec):
    """Convenience for a processed case_results record (fine binned grid)."""
    wl = rec.get("binnedWavelengthNm")
    rad = rec.get("binnedRadiance_mW_m2_nm_sr")
    if not wl or not rad:
        return None
    return johnson_v_surface_brightness(wl, rad)


if __name__ == "__main__":
    # Self-check: a flat 550nm-only-ish grey radiance should give a sane V.
    wl = list(range(400, 701, 10))
    # 1 mW/m2/nm/sr flat
    rad = [1.0] * len(wl)
    print("V for 1 mW/m2/nm/sr flat:",
          round(johnson_v_surface_brightness(wl, rad), 3), "mag/arcsec2")
