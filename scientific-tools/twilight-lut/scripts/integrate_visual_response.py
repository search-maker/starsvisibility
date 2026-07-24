#!/usr/bin/env python3
"""Convert spectral radiance to photopic/scotopic quantities with uncertainty.

Definitions (documented; see SCIENTIFIC_ASSUMPTIONS.md §Visual response):
- Photopic luminance:  L  = 683.002 lm/W * sum V(l)  * L_e(l) * dl   [cd/m2]
  V(l): CIE 1924 photopic luminous efficiency, 10 nm tabulation.
- Scotopic luminance:  L' = 1700.06 lm/W * sum V'(l) * L_e(l) * dl   [scotopic cd/m2]
  V'(l): CIE 1951 scotopic function. This is a SCOTOPIC luminance, not
  ordinary cd/m2; it is stored under an explicit name.
- S/P ratio = L'/L.
- Radiance input: mW m-2 nm-1 sr-1 (energy-based). PRIMARY luminance value is a
  FINE-GRID TRAPEZOID (fine_weighted_sum) over the ~1 nm binned spectrum, which
  preserves Fraunhofer/solar structure. The 10 nm RECTANGLE sum (weighted_sum)
  over the 41 RT nodes is the NODE-GRID / UNCERTAINTY path, not the primary
  luminance; the two agree to <1% (wavelengthGridConsistency).
- MC uncertainty: per-wavelength standard errors are treated as independent on
  the node grid; sigma_L = Km*sqrt(sum (V*sigma*dl)^2). Conservative for
  correlated noise.
- nanolamberts: 1 nL = 1e-9 lambert = (1e-5/pi) cd/m2 = 3.183099e-6 cd/m2.
- mag/arcsec2 via the calculator's own Krisciunas & Schaefer pair:
  mag = (20.7233 - ln(nL/34.08)) / 0.92104  (V-like SQM scale; valid only as
  the calculator-internal convention, not an absolute Vega calibration).
"""
import json
import math
from lrt_common import (PROCESSED_DIR, RAW_DIR, selected_attempt_dir, parse_spc)
# johnson_v is REQUIRED (directive #4: do not silently hide passband/checksum/
# unit/programming errors). Import at module load so a broken passband fails the
# whole processing step loudly rather than producing a null magnitude.
import johnson_v as JV

KM_PHOTOPIC = 683.002
KM_SCOTOPIC = 1700.06
DL_NM = 10.0
CD_M2_PER_NL = 3.1830989e-6

# CIE 1924 V(lambda), 380-780 nm, 10 nm steps
V_PHOT = [0.00004, 0.00012, 0.0004, 0.0012, 0.0040, 0.0116, 0.023, 0.038,
          0.060, 0.09098, 0.13902, 0.20802, 0.323, 0.503, 0.710, 0.862,
          0.954, 0.99495, 0.995, 0.952, 0.870, 0.757, 0.631, 0.503, 0.381,
          0.265, 0.175, 0.107, 0.061, 0.032, 0.017, 0.00821, 0.004102,
          0.002091, 0.001047, 0.00052, 0.000249, 0.00012, 0.00006, 0.00003,
          0.000015]
# CIE 1951 V'(lambda), 380-780 nm, 10 nm steps
V_SCOT = [0.000589, 0.002209, 0.00929, 0.03484, 0.0966, 0.1998, 0.3281,
          0.455, 0.567, 0.676, 0.793, 0.904, 0.982, 0.997, 0.935, 0.811,
          0.650, 0.481, 0.3288, 0.2076, 0.1212, 0.0655, 0.03315, 0.01593,
          0.00737, 0.003335, 0.001497, 0.000677, 0.0003129, 0.000148,
          0.0000715, 0.00003533, 0.0000178, 0.00000914, 0.00000478,
          0.000002546, 0.000001379, 0.00000076, 0.000000425, 0.000000241,
          0.000000139]


def mag_from_nl(b):
    return (20.7233 - math.log(max(b, 1e-3) / 34.08)) / 0.92104


def nl_from_mag(sb):
    return 34.08 * math.exp(20.7233 - 0.92104 * sb)


def interp_v(table, wavelength_nm):
    """Linear interpolation of a 380..780/10nm table."""
    x = (wavelength_nm - 380.0) / 10.0
    i = int(math.floor(x))
    if i < 0 or i >= len(table) - 1:
        return table[0] if i < 0 else table[-1]
    f = x - i
    return table[i] * (1 - f) + table[i + 1] * f


def weighted_sum(rad_mw, std_mw, weights, km):
    """(value, sigma) of km * sum w*L_e*dl on the 41-node/10nm grid,
    radiance in mW units. Used for uncertainty (node noise is coherent)."""
    val = km * sum(w * r * 1e-3 * DL_NM for w, r in zip(weights, rad_mw))
    var, missing = 0.0, 0
    for w, s in zip(weights, std_mw):
        if s is None:
            missing += 1
            continue
        var += (km * w * s * 1e-3 * DL_NM) ** 2
    if missing == len(std_mw):
        return val, None
    return val, math.sqrt(var)


def trapezoid_weighted(wl, rad_mw, table, km):
    """km * DIRECT trapezoidal integral of table(lambda)*radiance over the given
    (wl, radiance) samples. When wl is the RAW ~0.05 nm grid this is the primary
    luminance (direct integration on the original samples, directive #4); it is
    also reused for the energy-preserving 1 nm grid in the convergence check."""
    total = 0.0
    for i in range(len(wl) - 1):
        dl = wl[i + 1] - wl[i]
        f0 = interp_v(table, wl[i]) * rad_mw[i]
        f1 = interp_v(table, wl[i + 1]) * rad_mw[i + 1]
        total += 0.5 * (f0 + f1) * dl
    return km * total * 1e-3


def read_raw_spectrum(case_id):
    """Return (wl_nm, radiance_mw) on the RAW ~0.05 nm grid from the selected
    attempt's mc.rad.spc. Raises if unavailable — the raw grid is required for
    the primary integral and the convergence check."""
    cdir = RAW_DIR / case_id
    adir = selected_attempt_dir(cdir)
    if adir is None:
        raise FileNotFoundError(f"no selected attempt for {case_id}")
    d = parse_spc(adir / "mc.rad.spc")
    if not d:
        raise ValueError(f"empty raw spectrum for {case_id}")
    wl = sorted(d)
    return wl, [d[w] for w in wl]


def integrate_record(rec, raw=None):
    # PRIMARY integration is a DIRECT trapezoid on the RAW ~0.05 nm grid
    # (directive #4). The 1 nm binned grid and the RT-node 10 nm grid are also
    # integrated, only to report the convergence among the three methods.
    # `raw` may be injected as (wl, radiance); otherwise it is read from the
    # selected attempt's mc.rad.spc.
    wl_raw, rad_raw = raw if raw is not None else read_raw_spectrum(rec["caseId"])
    wl_bin = rec["binnedWavelengthNm"]
    rad_bin = rec["binnedRadiance_mW_m2_nm_sr"]
    rad = rec["nodeRadiance_mW_m2_nm_sr"]
    std = rec["nodeRadianceStd_mW_m2_nm_sr"]

    L = trapezoid_weighted(wl_raw, rad_raw, V_PHOT, KM_PHOTOPIC)         # primary
    Ls = trapezoid_weighted(wl_raw, rad_raw, V_SCOT, KM_SCOTOPIC)
    L_bin = trapezoid_weighted(wl_bin, rad_bin, V_PHOT, KM_PHOTOPIC)     # 1 nm
    L_node, sL = weighted_sum(rad, std, V_PHOT, KM_PHOTOPIC)            # RT node
    _, sLs = weighted_sum(rad, std, V_SCOT, KM_SCOTOPIC)
    # synthetic Johnson V from the raw grid; JV import failure already raised.
    v_mag = JV.johnson_v_surface_brightness(wl_raw, rad_raw)
    out = {
        "photopicLuminanceCdM2": L,                       # primary (raw trapezoid)
        "photopicLuminanceStdCdM2": sL,
        "photopicLuminance1nmGridCdM2": L_bin,
        "photopicLuminanceNodeGridCdM2": L_node,
        # convergence among the three integration methods (directive #4)
        "spectralIntegrationConvergence": {
            "raw_vs_1nm_rel": (abs(L - L_bin) / L) if L > 0 else None,
            "raw_vs_node_rel": (abs(L - L_node) / L) if L > 0 else None,
        },
        "wavelengthGridConsistency": (abs(L - L_node) / L) if L > 0 else None,
        "scotopicLuminanceScotCdM2": Ls,
        "scotopicLuminanceStdScotCdM2": sLs,
        "sToPRatio": (Ls / L) if L > 0 else None,
        "syntheticJohnsonVMagArcsec2": v_mag,
        "negativeSpectralValues": sum(1 for r in rad_raw if r < 0),
        "zeroSpectralValues": sum(1 for r in rad_raw if r == 0),
    }
    out["photopicRelativeUncertainty"] = (sL / L) if (sL and L > 0) else None
    if L > 0:
        nl = L / CD_M2_PER_NL
        out["twilightNl"] = nl
        out["log10PhotopicLuminance"] = math.log10(L)
        out["skyMagArcsec2_KSconvention"] = mag_from_nl(nl)
        # do NOT log-transform statistically unresolved values
        if sL is not None and sL >= L:
            out["statisticallyResolved"] = False
        else:
            out["statisticallyResolved"] = True
    else:
        out["twilightNl"] = 0.0
        out["log10PhotopicLuminance"] = None
        out["skyMagArcsec2_KSconvention"] = None
        out["statisticallyResolved"] = False
    return out


def main():
    src = PROCESSED_DIR / "spectral_results.json"
    records = json.loads(src.read_text())
    results = []
    for rec in records:
        if rec.get("status") != "ok":
            results.append(rec)
            continue
        results.append({**rec, **integrate_record(rec)})
    out = PROCESSED_DIR / "case_results.json"
    out.write_text(json.dumps(results, indent=1))
    ok = [r for r in results if r.get("status") == "ok"]
    resolved = [r for r in ok if r.get("statisticallyResolved")]
    print(f"integrated {len(ok)} ok cases ({len(resolved)} statistically "
          f"resolved) -> {out}")


if __name__ == "__main__":
    main()
