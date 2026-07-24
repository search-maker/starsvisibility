#!/usr/bin/env python3
"""Johnson V synthetic photometry of a spectral sky radiance (PG-1 corrected).

Produces a Vega-based Johnson V surface brightness in mag/arcsec^2 comparable to
Patat et al. 2006 twilight V measurements — NOT the calculator's internal
Krisciunas-Schaefer "SQM-equivalent" and NOT unfiltered photopic luminance.

PASSBAND (authoritative, machine-readable, checksummed):
  validation-data/passbands/bessell-V.ecsv, the Johnson/Cousins standard V from
  Bessell (1990, PASP 102, 1181; DOI 10.1086/132749), as distributed by the
  `speclite` package. 100 Angstrom grid, 4700-7000 A, response normalised to
  max 1.0, PEAK AT 5300 A. (The previous hand-entered array used a wrong 5 nm
  grid that pushed the peak to ~500 nm; replaced.)

ENERGY vs PHOTON: the Bessell 1990 response is the standard normalised system
response. Johnson V synthetic photometry for a photon-counting detector weights
the spectrum by response*lambda (Bessell & Murphy 2012, PASP 124, 140). We use
that photon-counting convention and pair it with the Bessell & Murphy 2012
photon-weighted V zero point below, so weighting and zero point are consistent.

ZERO POINT: a V=0.00 (Vega system) source has photon-weighted in-band flux
density f_lambda(V=0) = 3.63e-9 erg cm^-2 s^-1 A^-1 = 3.63e-8 mW m^-2 nm^-1
(Bessell & Murphy 2012).

SURFACE BRIGHTNESS:
  L_V_eff = int(L_lambda * R(lambda) * lambda dlambda) / int(R * lambda dlambda)
  V_sky   = -2.5*log10( L_V_eff * Omega_arcsec2 / f_lambda0 )   [mag/arcsec^2]
with Omega_arcsec2 = (pi/180/3600)^2 sr = 2.350444e-11 sr.
"""
import hashlib
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASSBAND_FILE = ROOT / "validation-data" / "passbands" / "bessell-V.ecsv"
PASSBAND_SHA256 = "20e8d89346b5bc71f848ff3eee054a92e1ba53872fb048ac670151b52dac99a1"

OMEGA_ARCSEC2_SR = (math.pi / 180.0 / 3600.0) ** 2   # 2.350444e-11 sr
F_LAMBDA_V0_MW = 3.63e-8      # mW m^-2 nm^-1 for V=0 (Bessell & Murphy 2012)


def _load_passband():
    """Return (wavelength_nm ascending, response) from the checksummed ecsv."""
    raw = PASSBAND_FILE.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != PASSBAND_SHA256:
        raise ValueError(f"bessell-V.ecsv checksum mismatch: {got}")
    wl_nm, resp = [], []
    for line in raw.decode().splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("wavelength"):
            continue
        a, b = s.split()
        wl_nm.append(float(a) / 10.0)   # Angstrom -> nm
        resp.append(float(b))
    return wl_nm, resp


_WL_NM, _RESP = _load_passband()
PASSBAND_PEAK_NM = _WL_NM[_RESP.index(max(_RESP))]


def _resp_at(wl_nm):
    if wl_nm < _WL_NM[0] or wl_nm > _WL_NM[-1]:
        return 0.0
    # linear interpolation on the (uniform 10 nm) grid
    lo = 0
    hi = len(_WL_NM) - 1
    if wl_nm <= _WL_NM[0]:
        return _RESP[0]
    if wl_nm >= _WL_NM[-1]:
        return _RESP[-1]
    # binary search
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if _WL_NM[mid] <= wl_nm:
            lo = mid
        else:
            hi = mid
    f = (wl_nm - _WL_NM[lo]) / (_WL_NM[hi] - _WL_NM[lo])
    return _RESP[lo] * (1 - f) + _RESP[hi] * f


def effective_wavelength_nm(photon=True):
    """Photon- (default) or energy-weighted effective wavelength of the passband."""
    num = den = 0.0
    for i in range(len(_WL_NM) - 1):
        dl = _WL_NM[i + 1] - _WL_NM[i]
        for k in (i, i + 1):
            pass
        r0, r1 = _RESP[i], _RESP[i + 1]
        l0, l1 = _WL_NM[i], _WL_NM[i + 1]
        w0 = r0 * (l0 if photon else 1.0)
        w1 = r1 * (l1 if photon else 1.0)
        num += 0.5 * (w0 * l0 + w1 * l1) * dl
        den += 0.5 * (w0 + w1) * dl
    return num / den if den else None


def effective_inband_radiance(wl_nm, radiance_mw):
    """Photon-weighted effective in-band spectral radiance (mW m^-2 nm^-1 sr^-1)
    over a sampled spectrum (wl ascending). Trapezoid on the given grid."""
    num = den = 0.0
    for i in range(len(wl_nm) - 1):
        dl = wl_nm[i + 1] - wl_nm[i]
        s0 = _resp_at(wl_nm[i]) * wl_nm[i]
        s1 = _resp_at(wl_nm[i + 1]) * wl_nm[i + 1]
        num += 0.5 * (s0 * radiance_mw[i] + s1 * radiance_mw[i + 1]) * dl
        den += 0.5 * (s0 + s1) * dl
    return num / den if den > 0 else 0.0


def johnson_v_surface_brightness(wl_nm, radiance_mw):
    """Vega Johnson V surface brightness (mag/arcsec^2) from spectral radiance
    in mW m^-2 nm^-1 sr^-1. None if the in-band radiance is non-positive."""
    l_eff = effective_inband_radiance(wl_nm, radiance_mw)
    if l_eff <= 0:
        return None
    flux_per_arcsec2 = l_eff * OMEGA_ARCSEC2_SR    # mW m^-2 nm^-1 arcsec^-2
    return -2.5 * math.log10(flux_per_arcsec2 / F_LAMBDA_V0_MW)


def johnson_v_from_record(rec):
    wl = rec.get("binnedWavelengthNm")
    rad = rec.get("binnedRadiance_mW_m2_nm_sr")
    if not wl or not rad:
        return None
    return johnson_v_surface_brightness(wl, rad)


if __name__ == "__main__":
    print(f"passband peak: {PASSBAND_PEAK_NM} nm (expect 530)")
    print(f"photon effective wavelength: {effective_wavelength_nm():.1f} nm "
          f"(Johnson V ~545-554)")
    print(f"energy effective wavelength: {effective_wavelength_nm(False):.1f} nm")
