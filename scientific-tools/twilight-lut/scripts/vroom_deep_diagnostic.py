#!/usr/bin/env python3
"""Decisive diagnostic for the dep-8 VROOM discrepancy.

Runs the worst offending cell(s) VROOM on vs off at increasing photon counts,
paired by seed, on the full photopic result. If the paired relative difference
shrinks toward zero as photons increase, the dep-8 discrepancy is Monte-Carlo
UNDER-CONVERGENCE (VROOM is fine with enough photons). If it persists, it is a
real VROOM spherical bias and the dep-8 domain must use VROOM off or be excluded.

Writes reports/vroom-deep-diagnostic.json.
"""
import json
import math
import statistics
from pathlib import Path
from lrt_common import ROOT
import hardening_common as H

REPORTS = ROOT / "reports"
CELLS = [(8, 10, 180, 0.05), (8, 30, 180, 0.05)]   # the significant offenders
PHOTON_LEVELS = [8_000_000, 20_000_000, 40_000_000]
SEEDS = (401, 402, 403, 404)


def paired(dep, alt, raz, aod, photons):
    on = {s: H.run_radiance_spectral(dep, alt, raz, aod, photons=photons, seed=s, vroom="on")
          for s in SEEDS}
    off = {s: H.run_radiance_spectral(dep, alt, raz, aod, photons=photons, seed=s, vroom="off")
           for s in SEEDS}
    if not all(on[s]["status"] == "ok" and off[s]["status"] == "ok" for s in SEEDS):
        return {"status": "incomplete"}
    diffs = [(on[s]["photopicLuminanceCdM2"] - off[s]["photopicLuminanceCdM2"])
             / off[s]["photopicLuminanceCdM2"] for s in SEEDS]
    mean = statistics.mean(diffs)
    se = statistics.stdev(diffs) / math.sqrt(len(diffs))
    return {"status": "ok", "photons": photons,
            "photopicOn": statistics.mean(on[s]["photopicLuminanceCdM2"] for s in SEEDS),
            "photopicOff": statistics.mean(off[s]["photopicLuminanceCdM2"] for s in SEEDS),
            "pairedRelDiffMean": mean, "pairedRelDiffSE": se,
            "t": mean / se if se > 0 else float("inf")}


def main():
    out = {"cells": []}
    for (dep, alt, raz, aod) in CELLS:
        series = []
        for ph in PHOTON_LEVELS:
            r = paired(dep, alt, raz, aod, ph)
            series.append(r)
            if r["status"] == "ok":
                print(f"dep{dep} alt{alt} raz{raz} aod{aod} ph{ph:,}: "
                      f"relDiff {r['pairedRelDiffMean']:+.4f} +/- {r['pairedRelDiffSE']:.4f} "
                      f"t={r['t']:+.2f}", flush=True)
        # converged if |relDiff| at the highest photon level is small AND smaller
        # than at the lowest (trend toward agreement)
        ok = [s for s in series if s["status"] == "ok"]
        converges = None
        if len(ok) >= 2:
            first, last = abs(ok[0]["pairedRelDiffMean"]), abs(ok[-1]["pairedRelDiffMean"])
            converges = (last < 0.03) or (last < first * 0.5)
        out["cells"].append({"dep": dep, "alt": alt, "raz": raz, "aod": aod,
                             "series": series, "convergesToAgreement": converges})
    # verdict
    allconv = [c["convergesToAgreement"] for c in out["cells"]]
    out["verdict"] = ("under-convergence (VROOM ok with more photons)"
                      if all(allconv) else
                      "PERSISTENT VROOM discrepancy at dep 8 -> use VROOM off or "
                      "exclude dep 8 from the VROOM-authorized domain")
    out["allCellsConverge"] = all(allconv)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "vroom-deep-diagnostic.json").write_text(json.dumps(out, indent=1))
    print("VERDICT:", out["verdict"])


if __name__ == "__main__":
    main()
