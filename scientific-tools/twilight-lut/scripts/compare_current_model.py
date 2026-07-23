#!/usr/bin/env python3
"""Compare three twilight-background candidates on the real feasibility cases.

A. current  : calculator's parametric excess x directional factor (port).
B. hybrid   : current model evaluated AT ZENITH as normalization, times the
              libRadtran directional ratio  R(target)/R(zenith)  at the same
              depression and AOD. Reference direction = zenith (documented
              choice: the calculator's curve is calibrated against zenith-ish
              SQM measurements; tested, not assumed).
C. absolute : libRadtran photopic luminance converted to nL.

Intermediate quantity compared: Btwi (solar twilight excess, nL) at the target
direction, and the implied total sky brightness / NELM / visibility margin
through the calculator's unchanged chain (moonless, baseline SQM 21.8,
default observer). Writes reports/current-vs-libradtran-comparison.{md,csv}
and reports/model-variant-comparison.{md,csv}.
"""
import csv
import json
import math
from pathlib import Path
from lrt_common import PROCESSED_DIR, ROOT
import current_model_port as cur

REPORTS = ROOT / "reports"
BASELINE_SQM = 21.8
REP_MAGS = [0.0, 1.0, 2.0, 3.0]


def load_ok_cases():
    data = json.loads((PROCESSED_DIR / "case_results.json").read_text())
    return [r for r in data if r.get("status") == "ok"
            and r.get("statisticallyResolved")]


def zenith_lookup(cases):
    z = {}
    for r in cases:
        if r["targetAltitudeDeg"] == 90 and r.get("repeatIndex", 0) == 0:
            z[(r["sunDepressionDeg"], r["aod550"])] = r
    return z


def evaluate(r, zenith):
    dep, alt, raz = r["sunDepressionDeg"], r["targetAltitudeDeg"], r["relativeAzimuthDeg"]
    aod = r["aod550"]
    sep = cur.sun_target_separation_deg(dep, alt, raz)
    row = {
        "caseId": r["caseId"], "group": r["group"],
        "sunDepressionDeg": dep, "targetAltitudeDeg": alt,
        "relativeAzimuthDeg": raz, "angularSeparationDeg": round(sep, 2),
        "aod550": aod,
    }
    cur_nl = cur.current_model_twilight_nl(dep, alt, raz, BASELINE_SQM)
    abs_nl = r["twilightNl"]
    row["currentTwilightNl"] = cur_nl
    row["absoluteTwilightNl"] = abs_nl
    row["absoluteRelUncert"] = r.get("photopicRelativeUncertainty")
    zref = zenith.get((dep, aod))
    if zref and zref["twilightNl"] > 0:
        ratio = abs_nl / zref["twilightNl"]
        cur_zenith_nl = cur.current_model_twilight_nl(dep, 90, 0, BASELINE_SQM)
        hyb_nl = cur_zenith_nl * ratio
        row["lutDirectionalRatio"] = ratio
        row["hybridTwilightNl"] = hyb_nl
    else:
        row["lutDirectionalRatio"] = None
        row["hybridTwilightNl"] = None
    for name in ("current", "hybrid", "absolute"):
        nl = row[f"{name}TwilightNl"]
        if nl is None or nl <= 0:
            continue
        row[f"{name}Log10Nl"] = math.log10(nl)
        sb = cur.total_sky_mag_arcsec2(nl, alt, BASELINE_SQM)
        row[f"{name}TotalSkyMag"] = sb
        row[f"{name}NELM"] = cur.limiting_magnitude_from_sky_brightness(sb)
    if row.get("currentLog10Nl") is not None and row.get("absoluteLog10Nl") is not None:
        row["absMinusCurrentDex"] = row["absoluteLog10Nl"] - row["currentLog10Nl"]
        row["absMinusCurrentNELMMag"] = row["absoluteNELM"] - row["currentNELM"]
    if row.get("hybridLog10Nl") is not None and row.get("currentLog10Nl") is not None:
        row["hybMinusCurrentDex"] = row["hybridLog10Nl"] - row["currentLog10Nl"]
        row["hybMinusCurrentNELMMag"] = row["hybridNELM"] - row["currentNELM"]
    return row


def fmt(x, nd=3):
    if x is None:
        return ""
    if isinstance(x, float):
        return f"{x:.{nd}g}" if abs(x) < 1e-2 or abs(x) >= 1e4 else f"{x:.{nd}f}"
    return str(x)


def main():
    REPORTS.mkdir(exist_ok=True)
    cases = load_ok_cases()
    zenith = zenith_lookup(cases)
    rows = [evaluate(r, zenith) for r in cases if r.get("repeatIndex", 0) == 0]

    cols = ["caseId", "group", "sunDepressionDeg", "targetAltitudeDeg",
            "relativeAzimuthDeg", "angularSeparationDeg", "aod550",
            "currentTwilightNl", "hybridTwilightNl", "absoluteTwilightNl",
            "absoluteRelUncert", "lutDirectionalRatio",
            "currentTotalSkyMag", "hybridTotalSkyMag", "absoluteTotalSkyMag",
            "currentNELM", "hybridNELM", "absoluteNELM",
            "absMinusCurrentDex", "absMinusCurrentNELMMag",
            "hybMinusCurrentDex", "hybMinusCurrentNELMMag"]
    with open(REPORTS / "current-vs-libradtran-comparison.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    core = [r for r in rows if r["group"] == "core" and "absMinusCurrentDex" in r]
    dex = sorted(r["absMinusCurrentDex"] for r in core)
    nelm = sorted(abs(r["absMinusCurrentNELMMag"]) for r in core)

    md = ["# Current vs libRadtran twilight-background comparison (feasibility grid)",
          "",
          f"Cases compared: {len(rows)} (statistically resolved, seed-0 only); "
          f"core grid rows: {len(core)}.",
          f"Baseline SQM {BASELINE_SQM}, moonless, default observer; NELM through "
          "the calculator's unchanged chain.", "",
          "## Summary statistics, core grid (absolute libRadtran minus current model)",
          "",
          f"- log10(Btwi) difference: median {dex[len(dex)//2]:+.3f} dex, "
          f"min {dex[0]:+.3f}, max {dex[-1]:+.3f}",
          f"- |NELM difference|: median {nelm[len(nelm)//2]:.3f} mag, "
          f"max {nelm[-1]:.3f} mag", "",
          "## Per-case table", "",
          "| case | dep | alt | raz | sep | current nL | hybrid nL | absolute nL | "
          "abs-cur dex | ΔNELM(abs) mag | ΔNELM(hyb) mag |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append("| " + " | ".join([
            r["caseId"], fmt(r["sunDepressionDeg"]), fmt(r["targetAltitudeDeg"]),
            fmt(r["relativeAzimuthDeg"]), fmt(r["angularSeparationDeg"]),
            fmt(r["currentTwilightNl"]), fmt(r.get("hybridTwilightNl")),
            fmt(r["absoluteTwilightNl"]), fmt(r.get("absMinusCurrentDex")),
            fmt(r.get("absMinusCurrentNELMMag")),
            fmt(r.get("hybMinusCurrentNELMMag"))]) + " |")
    (REPORTS / "current-vs-libradtran-comparison.md").write_text("\n".join(md) + "\n")

    # model-variant table: representative-star visibility margins
    md2 = ["# Model-variant comparison: implied visibility margins", "",
           "Margin = NELM - magEff for representative effective magnitudes "
           "(extinction already applied upstream; identical for all variants).",
           "", "| case | dep | alt | raz | " +
           " | ".join(f"m={m:.0f} cur/hyb/abs" for m in REP_MAGS) + " |",
           "|---|---|---|---|" + "---|" * len(REP_MAGS)]
    rows2 = []
    for r in rows:
        if "currentNELM" not in r or "absoluteNELM" not in r:
            continue
        cells, rec = [], {"caseId": r["caseId"]}
        for m in REP_MAGS:
            c = r["currentNELM"] - m
            h = (r["hybridNELM"] - m) if r.get("hybridNELM") is not None else None
            a = r["absoluteNELM"] - m
            rec[f"marginCurrent_m{m:.0f}"] = c
            rec[f"marginHybrid_m{m:.0f}"] = h
            rec[f"marginAbsolute_m{m:.0f}"] = a
            cells.append(f"{c:+.2f}/{(f'{h:+.2f}' if h is not None else '--')}/{a:+.2f}")
        rows2.append(rec)
        md2.append(f"| {r['caseId']} | {r['sunDepressionDeg']} | "
                   f"{r['targetAltitudeDeg']} | {r['relativeAzimuthDeg']} | "
                   + " | ".join(cells) + " |")
    (REPORTS / "model-variant-comparison.md").write_text("\n".join(md2) + "\n")
    with open(REPORTS / "model-variant-comparison.csv", "w", newline="") as f:
        if rows2:
            w = csv.DictWriter(f, fieldnames=list(rows2[0]))
            w.writeheader()
            w.writerows(rows2)
    print(f"wrote {len(rows)} comparison rows -> {REPORTS}")


if __name__ == "__main__":
    main()
