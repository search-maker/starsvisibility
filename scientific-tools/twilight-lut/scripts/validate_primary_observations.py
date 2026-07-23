#!/usr/bin/env python3
"""Primary-source observational comparison (matched-geometry where possible).

Currently active comparisons:
- Patat 2006 zenith Johnson V vs synthetic Johnson V of elevation-matched
  Paranal simulations (if present in raw-output under group 'paranal'), else
  the sea-level baseline with an explicit UNMATCHED flag.
- Spitschan 2016 S/P trend direction (rural) as an independent spectral check.

Koomen ratio comparison activates automatically once
validation-data/koomen_table*.csv exist; until then it is reported BLOCKED.

Writes reports/primary-observational-validation.{md,json}. Honest status codes;
nothing is invented.
"""
import csv
import json
import math
import re
from pathlib import Path
from lrt_common import PROCESSED_DIR, ROOT
from johnson_v import johnson_v_from_record
from patat_reference import patat_zenith_v, add_floor_mag, PATAT_V
import koomen_reference as koomen

REPORTS = ROOT / "reports"
VD = ROOT / "validation-data"


def load_cases():
    return json.loads((PROCESSED_DIR / "case_results.json").read_text())


def zenith_case(cases, dep, group=None, aod=0.15):
    for r in cases:
        if (r.get("status") == "ok" and r["sunDepressionDeg"] == dep
                and r["targetAltitudeDeg"] == 90 and r["relativeAzimuthDeg"] == 0
                and r["aod550"] == aod and not r.get("repeatIndex", 0)
                and (group is None or r.get("group") == group)):
            return r
    return None


def patat_comparison(cases):
    """Returns rows comparing synthetic V (matched elevation if available)."""
    matched_group = "paranal" if any(r.get("group") == "paranal" for r in cases) else None
    rows = []
    for dep in (6, 8, 10):
        pat = patat_zenith_v(dep)
        if pat is None:
            continue
        r = zenith_case(cases, dep, group=matched_group, aod=0.05 if matched_group else 0.15)
        if not r:
            r = zenith_case(cases, dep, aod=0.15)
        if not r:
            continue
        v_sim = johnson_v_from_record(r)
        if v_sim is None:
            continue
        # add Paranal night floor only for the matched comparison
        v_sim_total = add_floor_mag(v_sim) if matched_group else v_sim
        rows.append({
            "sunDepressionDeg": dep,
            "patatZenithV": round(pat, 3),
            "simSyntheticV": round(v_sim, 3),
            "simVWithFloor": round(v_sim_total, 3),
            "residualMag": round(v_sim_total - pat, 3),
            "matched": bool(matched_group),
            "simSiteElevationM": r.get("observerElevationM", 0),
            "simAod550": r["aod550"],
        })
    return rows, matched_group


def spitschan_sp_trend():
    """Report the presence + basic shape of the ingested Spitschan Table1.
    Full S/P-vs-elevation extraction needs the calibrated spectra (not committed);
    here we confirm the artifact and its solar-elevation coverage."""
    t1 = VD / "spitschan2016" / "Table1.csv"
    if not t1.exists():
        return {"status": "MISSING"}
    rural = city = 0
    elev_min, elev_max = 999, -999
    for row in csv.reader(t1.open()):
        if not row or len(row) < 7:
            continue
        site = row[0].strip()
        if site == "Rural":
            rural += 1
        elif site == "City":
            city += 1
        nums = re.findall(r"-?\d+\.?\d*", row[3])
        if len(nums) >= 2:
            lo, hi = float(nums[0]), float(nums[-1])
            elev_min = min(elev_min, lo); elev_max = max(elev_max, hi)
    return {"status": "OBTAINED", "ruralSessions": rural, "citySessions": city,
            "solarElevationCoverageDeg": [elev_min, elev_max],
            "note": "spectral S/P-vs-elevation extraction requires the "
            "calibrated spectra (reproduce via git clone); irradiance source, "
            "used for spectral/S-P trend only, not directional radiance"}


def koomen_comparison(cases):
    tables = sorted(VD.glob("koomen_table*.csv"))
    if not tables:
        return {"status": "BLOCKED",
                "note": "transcribe Koomen tables to validation-data/"
                "koomen_table*.csv to activate the directional-ratio comparison"}
    # (activated automatically once data present)
    out = {"status": "ACTIVE", "tables": []}
    for t in tables:
        rows = [dict(targetAltitudeDeg=float(r["targetAltitudeDeg"]),
                     relativeAzimuthDeg=float(r["relativeAzimuthDeg"]),
                     luminance=koomen.parse_compact_decimal(r["luminanceCandlesPerFt2"]))
                for r in csv.DictReader(t.open())]
        out["tables"].append({"file": t.name,
                              "ratios": koomen.directional_ratios(rows)})
    return out


def main():
    cases = load_cases()
    patat_rows, matched = patat_comparison(cases)
    spits = spitschan_sp_trend()
    koom = koomen_comparison(cases)

    result = {
        "patat": {
            "coefficientStatus": PATAT_V["status"],
            "matchedElevation": bool(matched),
            "rows": patat_rows,
            "note": "UNMATCHED sea-level AOD-0.15 comparison" if not matched
            else "elevation-matched Paranal comparison with night floor",
        },
        "spitschan": spits,
        "koomen": koom,
        "primaryObservationalValidationStatus":
            "PENDING-VERIFICATION (Patat coefficients unverified from primary "
            "PDF; Koomen tables not transcribed; comparisons are indicative)",
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "primary-observational-validation.json").write_text(
        json.dumps(result, indent=1))

    lines = ["# Primary observational validation (Milestone 3)", "",
             "Status: **" + result["primaryObservationalValidationStatus"] + "**",
             "", "## Patat 2006 zenith Johnson V", "",
             f"Comparison is {'ELEVATION-MATCHED' if matched else 'UNMATCHED (sea-level AOD 0.15)'}. "
             f"Patat coefficient status: {PATAT_V['status']}.", "",
             "| dep | Patat V | sim synthetic V | sim V+floor | residual (sim−Patat) | matched |",
             "|---|---|---|---|---|---|"]
    for r in patat_rows:
        lines.append(f"| {r['sunDepressionDeg']} | {r['patatZenithV']} | "
                     f"{r['simSyntheticV']} | {r['simVWithFloor']} | "
                     f"{r['residualMag']:+.3f} | {r['matched']} |")
    lines += ["", "## Spitschan 2016 (irradiance; spectral/S-P only)", "",
              f"- status: {spits['status']}"]
    if spits["status"] == "OBTAINED":
        lines.append(f"- rural sessions {spits['ruralSessions']}, city "
                     f"{spits['citySessions']}, solar elevation coverage "
                     f"{spits['solarElevationCoverageDeg']} deg")
    lines += ["", "## Koomen 1952 directional ratios", "",
              f"- status: {koom['status']}", "",
              koom.get("note", "")]
    (REPORTS / "primary-observational-validation.md").write_text("\n".join(lines))
    print(f"patat rows: {len(patat_rows)} (matched={bool(matched)}); "
          f"spitschan: {spits['status']}; koomen: {koom['status']}")


if __name__ == "__main__":
    main()
