#!/usr/bin/env python3
"""Generate physical-sanity figures from the feasibility results.

All figures are produced from data files by this script (no manual editing).
Outputs go to reports/figures/. Skipped gracefully if matplotlib is absent.
"""
import json
import sys
from pathlib import Path
from lrt_common import PROCESSED_DIR, ROOT

FIGDIR = ROOT / "reports" / "figures"


def main():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping figures")
        return
    data = json.loads((PROCESSED_DIR / "case_results.json").read_text())
    ok = [r for r in data if r.get("status") == "ok"
          and not r.get("repeatIndex", 0)]
    geom = {(r["sunDepressionDeg"], r["targetAltitudeDeg"],
             r["relativeAzimuthDeg"], r["aod550"]): r for r in ok}
    FIGDIR.mkdir(parents=True, exist_ok=True)

    # Fig 1: luminance vs depression, by relative azimuth, at alt 30, AOD 0.15
    fig, ax = plt.subplots(figsize=(6, 4))
    for raz, style in ((0, "o-"), (90, "s--"), (180, "^:")):
        xs, ys, es = [], [], []
        for dep in (0, 2, 4, 6, 8):
            r = geom.get((dep, 30, raz, 0.15))
            if r:
                xs.append(dep)
                ys.append(r["photopicLuminanceCdM2"])
                es.append((r.get("photopicRelativeUncertainty") or 0) *
                          r["photopicLuminanceCdM2"])
        ax.errorbar(xs, ys, yerr=es, fmt=style, label=f"relAz {raz}°", capsize=3)
    ax.set_yscale("log")
    ax.set_xlabel("solar depression (deg)")
    ax.set_ylabel("photopic luminance (cd/m²)")
    ax.set_title("Twilight sky luminance vs depression (alt 30°, AOD 0.15)")
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGDIR / "luminance_vs_depression.png", dpi=110)
    plt.close(fig)

    # Fig 2: solar/antisolar contrast vs depression at alt 10
    fig, ax = plt.subplots(figsize=(6, 4))
    xs, ys = [], []
    for dep in (0, 2, 4, 6, 8):
        s = geom.get((dep, 10, 0, 0.15))
        a = geom.get((dep, 10, 180, 0.15))
        if s and a:
            xs.append(dep)
            ys.append(s["photopicLuminanceCdM2"] / a["photopicLuminanceCdM2"])
    ax.plot(xs, ys, "o-")
    ax.set_xlabel("solar depression (deg)")
    ax.set_ylabel("sunward / antisolar luminance ratio")
    ax.set_title("Solar–antisolar contrast at alt 10° (AOD 0.15)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGDIR / "solar_antisolar_contrast.png", dpi=110)
    plt.close(fig)

    # Fig 3: current vs absolute twilight nL (needs comparison CSV)
    comp = ROOT / "reports" / "current-vs-libradtran-comparison.csv"
    if comp.exists():
        import csv
        cur_nl, abs_nl = [], []
        for row in csv.DictReader(comp.open()):
            try:
                c = float(row["currentTwilightNl"])
                a = float(row["absoluteTwilightNl"])
            except (ValueError, KeyError):
                continue
            cur_nl.append(c)
            abs_nl.append(a)
        if cur_nl:
            fig, ax = plt.subplots(figsize=(5, 5))
            ax.loglog(cur_nl, abs_nl, "o", alpha=0.6)
            lo = min(min(cur_nl), min(abs_nl))
            hi = max(max(cur_nl), max(abs_nl))
            ax.plot([lo, hi], [lo, hi], "k--", label="1:1")
            ax.set_xlabel("current model twilight (nL)")
            ax.set_ylabel("absolute libRadtran twilight (nL)")
            ax.set_title("Current vs absolute twilight background")
            ax.legend()
            ax.grid(True, which="both", alpha=0.3)
            fig.tight_layout()
            fig.savefig(FIGDIR / "current_vs_absolute_nl.png", dpi=110)
            plt.close(fig)

    print(f"figures written to {FIGDIR}")


if __name__ == "__main__":
    main()
