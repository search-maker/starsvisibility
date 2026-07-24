#!/usr/bin/env python3
"""Pre-grid scientific hardening (Milestone 3 §4). Runs compact REAL libRadtran
studies and writes reports/PREGRID_HARDENING_REPORT.{md,json}.

Sub-studies:
  4.1 VROOM on/off stratified (z-scores, direction-dependent bias)
  4.2 Deep-boundary photon scaling at worst geometries (9,10 deg)
  4.3 Refraction sensitivity (effective-SZA-shift radiance response)
  4.4 Scalar vs polarized (documented not-supported-in-config + bound)
  4.5 Forward irradiance (edn) vs canonical twilight illuminance
  4.6 Observer elevation (sea / Paranal 2.64 km / Sac Peak 2.8 km)
  4.7 Geometric vs apparent target-altitude mapping (analytic + runs)

Photon counts are kept modest; differences (not absolute values) drive the
conclusions. Runtime is dominated by the deep-boundary study.
"""
import argparse
import json
import math
import statistics
from pathlib import Path
from lrt_common import ROOT
import hardening_common as H
import current_model_port as cur

REPORTS = ROOT / "reports"



def study_deep_boundary():
    """Photon scaling at the hardest 9,10 deg geometries."""
    rows = []
    for dep in (9, 10):
        for alt, raz in ((10, 0), (10, 90), (15, 180)):
            for photons in (4_000_000, 20_000_000):
                reps = [H.run_radiance(dep, alt, raz, 0.15, photons=photons,
                                       seed=s) for s in (11, 22)]
                good = [r for r in reps if r["status"] == "ok"]
                if not good:
                    rows.append({"dep": dep, "alt": alt, "raz": raz,
                                 "photons": photons, "status": "failed"})
                    continue
                vals = [r["radiance"] for r in good]
                rels = [(r["std"] / r["radiance"]) if r["radiance"] > 0 else None
                        for r in good]
                emp = (statistics.stdev(vals) / statistics.mean(vals)
                       if len(vals) > 1 and statistics.mean(vals) > 0 else None)
                rows.append({
                    "dep": dep, "alt": alt, "raz": raz, "photons": photons,
                    "meanRad": statistics.mean(vals),
                    "reportedRelErr": statistics.mean([x for x in rels if x]) if any(rels) else None,
                    "empiricalRelErrAcross2Seeds": emp,
                    "runtimeSec": statistics.mean([r["runtime"] for r in good]),
                    "status": "ok"})
    # decide support
    ok = [r for r in rows if r["status"] == "ok"]
    resolved_20m = [r for r in ok if r["photons"] == 20_000_000
                    and (r.get("reportedRelErr") or 1) < 0.15]
    verdict = (f"{len(resolved_20m)}/{len([r for r in ok if r['photons']==20_000_000])} "
               "worst-geometry 9-10 deg cases reach <15% at 20M photons")
    return {"cases": rows, "verdict": verdict}


def study_refraction():
    """Effective-SZA-shift sensitivity. Bennett refraction lowers the true Sun
    ~0.03-0.1 deg near the horizon; but for the SKY radiance the relevant shift
    is how much the illuminated-layer geometry moves. We bound the radiance
    sensitivity dR/d(SZA) by finite differences at +/-0.1 and +/-0.3 deg."""
    rows = []
    for dep in (4, 6, 8, 10):
        base = H.run_radiance(dep, 30, 90, 0.15, photons=8_000_000, seed=5)
        if base["status"] != "ok":
            continue
        for off in (0.1, 0.3):
            hi = H.run_radiance(dep, 30, 90, 0.15, photons=8_000_000, seed=5,
                                effective_sza_offset=off)
            if hi["status"] != "ok":
                continue
            # fractional change in radiance per degree of effective SZA
            frac_per_deg = (hi["radiance"] - base["radiance"]) / base["radiance"] / off
            rows.append({"dep": dep, "szaOffsetDeg": off,
                         "fracChangePerDeg": frac_per_deg,
                         "impliedMagPerDeg": -2.5 * math.log10(
                             hi["radiance"] / base["radiance"]) / off})
    # a plausible unmodelled refraction offset ~0.1 deg at the horizon -> error
    worst = max((abs(r["impliedMagPerDeg"]) * 0.1 for r in rows), default=None)
    return {"cases": rows,
            "estimatedRefractionErrorMagAt0p1deg": worst,
            "note": "Refraction is NOT modelled by this MYSTIC build. The table "
            "bounds radiance sensitivity to an effective solar-altitude shift; a "
            "plausible ~0.1 deg horizon refraction implies the listed magnitude "
            "error, growing with depression. Domain/uncertainty must reflect this."}


def study_polarisation():
    """Scalar vs polarized: documented not-supported-in-config + literature bound."""
    # aerosol_default rejects mc_polarisation; a Rayleigh-only VROOM polarized run
    # gave an implausible ~9x intensity deficit (VROOM local-estimate + spherical
    # polarisation not validated). We therefore do NOT report a numeric ratio.
    return {
        "supportedInProductionConfig": False,
        "reason": "aerosol_default rejects mc_polarisation (needs OPAC "
        "aerosol_species_file); Rayleigh-only VROOM polarized run produced an "
        "implausible ~9x intensity deficit, indicating the "
        "spherical+VROOM+polarisation local-estimate path is not valid for this "
        "comparison in libRadtran 2.0.6.",
        "literatureBoundOnIntensityMag": 0.05,
        "note": "Scalar-vs-vector RT differences on total INTENSITY in "
        "Rayleigh-dominated twilight directions are typically <=~3-5% "
        "(<=0.05 mag) (Emde et al. 2010; Mishchenko). Adopted as a documented "
        "systematic-uncertainty contribution, not a measured value."}


def study_irradiance():
    """Forward diffuse-down irradiance vs canonical twilight illuminance shape."""
    rows = []
    for dep in (0, 4, 8):
        r = H.run_irradiance(dep, photons=1_000_000, seed=3)
        rows.append({"dep": dep, **r})
    return {"cases": rows,
            "note": "Direct-beam (edir) is nan in spherical backward mode at the "
            "surface; diffuse-down (edn) is valid and used here for the SHAPE of "
            "the twilight decay (a proper illuminance calibration needs a "
            "forward-mode irradiance setup, deferred). Replaces the crude "
            "12-direction radiance quadrature as the illuminance diagnostic."}


def study_elevation():
    """Zenith radiance at sea / Paranal / Sac Peak elevations."""
    rows = []
    for dep in (4, 8):
        for elev, site in ((0.0, "sea"), (2.64, "Paranal"), (2.8, "SacPeak")):
            r = H.run_radiance(dep, 90, 0, 0.15, photons=8_000_000, seed=9,
                               elevation_km=elev)
            if r["status"] == "ok":
                rows.append({"dep": dep, "elevationKm": elev, "site": site,
                             "radiance": r["radiance"],
                             "relErr": (r["std"] / r["radiance"]) if r["radiance"] else None})
    return {"cases": rows,
            "note": "libRadtran 'altitude' truncates the profile at the observer "
            "level (pressure/aerosol column reduced accordingly). Higher sites "
            "are darker in twilight (less air/aerosol above)."}


def study_geo_apparent():
    """Geometric vs apparent target-altitude mapping (analytic)."""
    rows = []
    for alt in (10, 15, 30, 45, 60, 90):
        app = cur.apparent_altitude(alt) if hasattr(cur, "apparent_altitude") else None
        # calculator uses Saemundsson via refractionDeg; reproduce it:
        refr = _saemundsson_refr(alt)
        rows.append({"geometricAltDeg": alt, "refractionDeg": round(refr, 4),
                     "apparentAltDeg": round(alt + refr, 4)})
    return {
        "mapping": rows,
        "contract": {
            "lutIndexAltitude": "GEOMETRIC target altitude (the MYSTIC umu ray, "
            "no refraction in this build)",
            "browserQueryAltitude": "the browser passes GEOMETRIC altitude to "
            "the LUT; if only apparent altitude is available it must first "
            "subtract refraction to recover geometric before indexing",
            "difference": "refraction raises apparent above geometric by ~0.5 "
            "deg at alt 10 and ~0.01 deg at zenith (Saemundsson); using apparent "
            "as geometric would mis-index low targets by up to ~0.5 deg",
            "angularSeparation": "diagnostic only, from geometric alt/az of Sun "
            "and target",
        }}


def _saemundsson_refr(h_true):
    if h_true < -1:
        return 0.0
    r = 1.02 / math.tan(math.radians(h_true + 10.3 / (h_true + 5.11)))  # arcmin
    return max(0.0, r) / 60.0


def _load_vroom_authorization():
    p = REPORTS / "vroom-validation.json"
    if not p.exists():
        return None
    return json.loads(p.read_text()).get("vroomAuthorizedForGrid")


def gate(result, quick=False):
    """PG-4: every gate is DERIVED from measured results/tests. A study that was
    skipped (including by --quick) can never produce a passing gate. Split into
    coreGridAuthorized (0-8 deg) and extension9to10Authorized (provisional)."""
    ref = result["refraction"]
    elev = result["elevation"]
    deep = result["deepBoundary"]
    geo = result["geoApparent"]

    # VROOM comes from the dedicated hardened validation, not a --quick proxy.
    vroom_auth = _load_vroom_authorization()

    # refraction: a finite numeric sensitivity estimate must exist.
    refr_ok = (ref.get("estimatedRefractionErrorMagAt0p1deg") is not None
               and math.isfinite(ref["estimatedRefractionErrorMagAt0p1deg"])
               and not quick)

    # elevation: >=2 sites with finite, distinct radiances (higher site darker).
    ecases = [c for c in elev["cases"] if c.get("radiance") is not None]
    elev_ok = (len(ecases) >= 2
               and all(math.isfinite(c["radiance"]) and c["radiance"] > 0 for c in ecases)
               and not quick)

    # geo/apparent contract: VERIFY the mapping against the ported refraction
    # (a real test, not a hardcoded True).
    geo_ok = _verify_geo_apparent(geo)

    # deep boundary (for the 9-10 extension only): every deep cell resolved to
    # the target uncertainty. Skipped in --quick -> not authorized.
    deep_cells = [c for c in deep.get("cases", []) if c.get("status") == "ok"]
    deep_ok = (not quick and len(deep_cells) > 0
               and all((c.get("reportedRelErr") or 1) < 0.15 for c in deep_cells))

    core_gates = {
        "vroomAuthorized": bool(vroom_auth),
        "refractionQuantified": bool(refr_ok),
        "elevationHandled": bool(elev_ok),
        "geoApparentContractVerified": bool(geo_ok),
    }
    core_authorized = all(core_gates.values())
    ext_gates = {**core_gates, "deepBoundaryResolved": bool(deep_ok)}
    ext_authorized = all(ext_gates.values())
    return {
        "quickMode": quick,
        "coreGates": core_gates, "coreGridAuthorized": core_authorized,
        "extensionGates": ext_gates, "extension9to10Authorized": ext_authorized,
        "vroomAuthorizationSource": "reports/vroom-validation.json",
        "note": "coreGridAuthorized covers depression 0-8; extension9to10 is "
        "provisional and may remain unauthorized without blocking the core.",
    }


def _verify_geo_apparent(geo):
    """Check the reported apparent = geometric + Saemundsson refraction against
    current_model_port (independent computation), for every mapping row."""
    for m in geo.get("mapping", []):
        expected = cur.apparent_altitude(m["geometricAltDeg"])
        if abs(expected - m["apparentAltDeg"]) > 1e-3:
            return False
    return len(geo.get("mapping", [])) > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="smaller photon counts for a fast dry run")
    args = ap.parse_args()
    result = {"quickMode": args.quick,
              "vroomReference": "reports/vroom-validation.json (dedicated "
              "hardened paired VROOM study; not re-run here)"}
    print("4.2 deep boundary ...", flush=True)
    result["deepBoundary"] = (study_deep_boundary() if not args.quick
                              else {"cases": [], "verdict": "SKIPPED (--quick) "
                                    "-> extension not authorizable"})
    print("4.3 refraction ...", flush=True)
    result["refraction"] = study_refraction() if not args.quick else {
        "cases": [], "estimatedRefractionErrorMagAt0p1deg": None,
        "note": "SKIPPED (--quick) -> gate cannot pass"}
    print("4.4 polarisation ...", flush=True)
    result["polarisation"] = study_polarisation()
    print("4.5 irradiance ...", flush=True)
    result["irradiance"] = study_irradiance() if not args.quick else {
        "cases": [], "note": "SKIPPED (--quick)"}
    print("4.6 elevation ...", flush=True)
    result["elevation"] = study_elevation() if not args.quick else {
        "cases": [], "note": "SKIPPED (--quick) -> gate cannot pass"}
    print("4.7 geo/apparent ...", flush=True)
    result["geoApparent"] = study_geo_apparent()
    result["authorization"] = gate(result, quick=args.quick)

    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "PREGRID_HARDENING_REPORT.json").write_text(json.dumps(result, indent=1))
    _write_md(result)
    print("authorization:", json.dumps(result["authorization"], indent=1))


def _write_md(r):
    L = ["# Pre-grid Hardening Report (Milestone 3 §4)", "",
         f"quick mode: {r.get('quickMode')}", "",
         "## 4.1 VROOM on/off", "",
         f"- see the dedicated hardened paired VROOM study: {r['vroomReference']}",
         ""]
    d = r["deepBoundary"]
    L += ["## 4.2 Deep boundary (9-10 deg worst geometry)", "", f"- {d['verdict']}", "",
          "| dep | alt | raz | photons | mean rad | reported relErr | runtime s |",
          "|---|---|---|---|---|---|---|"]
    for c in d["cases"]:
        if c.get("status") == "ok":
            L.append(f"| {c['dep']} | {c['alt']} | {c['raz']} | {c['photons']:,} | "
                     f"{c['meanRad']:.3g} | {c.get('reportedRelErr')} | {c['runtimeSec']:.0f} |")
    rf = r["refraction"]
    L += ["", "## 4.3 Refraction sensitivity", "",
          f"- estimated error at 0.1 deg offset: "
          f"{rf['estimatedRefractionErrorMagAt0p1deg']:.3f} mag" if rf.get('estimatedRefractionErrorMagAt0p1deg') else "- n/a",
          f"- {rf['note']}", ""]
    p = r["polarisation"]
    L += ["## 4.4 Scalar vs polarized", "",
          f"- supported in production config: {p['supportedInProductionConfig']}",
          f"- {p['reason']}",
          f"- adopted literature bound: <= {p['literatureBoundOnIntensityMag']} mag", ""]
    ir = r["irradiance"]
    L += ["## 4.5 Forward irradiance", ""]
    for c in ir["cases"]:
        L.append(f"- dep {c['dep']}: mean diffuse-down = "
                 f"{c.get('meanDiffuseDown_mW_m2_nm')} mW/m2/nm ({c.get('nWavelengths')} wl)")
    L += ["", f"{ir['note']}", ""]
    el = r["elevation"]
    L += ["## 4.6 Observer elevation", "",
          "| dep | site | elev km | radiance | relErr |", "|---|---|---|---|---|"]
    for c in el["cases"]:
        L.append(f"| {c['dep']} | {c['site']} | {c['elevationKm']} | "
                 f"{c['radiance']:.3g} | {c.get('relErr')} |")
    L += ["", f"{el['note']}", "", "## 4.7 Geometric vs apparent altitude", ""]
    ga = r["geoApparent"]
    L += ["| geometric alt | refraction deg | apparent alt |", "|---|---|---|"]
    for m in ga["mapping"]:
        L.append(f"| {m['geometricAltDeg']} | {m['refractionDeg']} | {m['apparentAltDeg']} |")
    L += ["", "Contract:", ""]
    for k, val in ga["contract"].items():
        L.append(f"- **{k}**: {val}")
    a = r["authorization"]
    L += ["", "## Authorization (split core vs extension)", "",
          f"- **coreGridAuthorized (0-8 deg): {a['coreGridAuthorized']}**"]
    for k, val in a["coreGates"].items():
        L.append(f"  - {k}: {val}")
    L += ["", f"- **extension9to10Authorized: {a['extension9to10Authorized']}**"]
    for k, val in a["extensionGates"].items():
        L.append(f"  - {k}: {val}")
    L += ["", f"- {a['note']}"]
    (REPORTS / "PREGRID_HARDENING_REPORT.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
