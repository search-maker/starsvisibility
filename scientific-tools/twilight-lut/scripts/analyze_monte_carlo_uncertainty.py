#!/usr/bin/env python3
"""Monte Carlo uncertainty analysis from independent-seed repeats.

Modes represented in the case list:
- reproducible-debug: fixed seed 1000 for every non-repeat case (exact rerun).
- scientific-validation: repeat groups (mc-repeat, mc-repeat-deep) with
  independent seeds quantify whether the reported per-wavelength standard
  errors predict the real scatter of the integrated photopic luminance.

Writes reports/monte-carlo-uncertainty.{md,json}.
"""
import json
import math
import statistics
from lrt_common import PROCESSED_DIR, ROOT

REPORTS = ROOT / "reports"


def group_key(r):
    return (r["sunDepressionDeg"], r["targetAltitudeDeg"],
            r["relativeAzimuthDeg"], r["aod550"])


def main():
    data = json.loads((PROCESSED_DIR / "case_results.json").read_text())
    ok = [r for r in data if r.get("status") == "ok"]
    repeats = {}
    for r in ok:
        if r.get("group", "").startswith("mc-repeat") or r.get("repeatIndex", 0):
            repeats.setdefault(group_key(r), []).append(r)
        # the seed-1000 base case of each repeated geometry joins its group
    for r in ok:
        k = group_key(r)
        if k in repeats and not r.get("repeatIndex", 0):
            repeats[k].append(r)

    out = {"groups": []}
    lines = ["# Monte Carlo uncertainty from independent seeds", ""]
    for k, rs in sorted(repeats.items()):
        Ls = [r["photopicLuminanceCdM2"] for r in rs]
        reported = [r.get("photopicLuminanceStdCdM2") for r in rs]
        n = len(Ls)
        mean = statistics.mean(Ls)
        sd = statistics.stdev(Ls) if n > 1 else float("nan")
        rep_mean = statistics.mean([s for s in reported if s is not None])
        ratio = sd / rep_mean if rep_mean else float("nan")
        g = {
            "sunDepressionDeg": k[0], "targetAltitudeDeg": k[1],
            "relativeAzimuthDeg": k[2], "aod550": k[3],
            "nSeeds": n, "photonCount": rs[0]["photonCount"],
            "meanLuminanceCdM2": mean,
            "empiricalStdCdM2": sd,
            "empiricalRelStd": sd / mean if mean else None,
            "meanReportedStdCdM2": rep_mean,
            "empiricalToReportedRatio": ratio,
            "seeds": [r.get("randomSeed") for r in rs],
            "values": Ls,
        }
        out["groups"].append(g)
        lines += [
            f"## dep {k[0]} deg, alt {k[1]} deg, relAz {k[2]} deg, AOD {k[3]}",
            "",
            f"- seeds: {n}, photons/case: {rs[0]['photonCount']:,}",
            f"- luminance mean {mean:.4g} cd/m2, empirical std {sd:.2g} "
            f"({100 * sd / mean:.1f}%)",
            f"- mean reported std {rep_mean:.2g} "
            f"-> empirical/reported ratio {ratio:.2f}",
            f"- values: {', '.join(f'{v:.4g}' for v in sorted(Ls))}", "",
        ]
    verdicts = [g["empiricalToReportedRatio"] for g in out["groups"]
                if not math.isnan(g["empiricalToReportedRatio"])]
    if verdicts:
        worst = max(verdicts)
        lines += ["## Verdict", "",
                  f"Worst empirical/reported ratio: {worst:.2f}. Ratios well "
                  "above 1 mean the reported standard errors underestimate the "
                  "true scatter (heavy-tailed VROOM estimator); LUT-node "
                  "uncertainties must then be taken from repeats, not from the "
                  "reported std alone.", ""]
        out["worstEmpiricalToReportedRatio"] = worst
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "monte-carlo-uncertainty.md").write_text("\n".join(lines))
    (REPORTS / "monte-carlo-uncertainty.json").write_text(json.dumps(out, indent=1))
    print(f"analyzed {len(out['groups'])} repeat groups -> {REPORTS}")


if __name__ == "__main__":
    main()
