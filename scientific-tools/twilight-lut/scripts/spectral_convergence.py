#!/usr/bin/env python3
"""FC-4: report the convergence among the three spectral-integration methods for
photopic luminance, and assert it is below the documented threshold:
  - raw-grid direct trapezoid (~0.05 nm) — the PRIMARY value;
  - energy-preserving 1 nm grid trapezoid;
  - RT-node 10 nm rectangle (the uncertainty path).
Writes reports/spectral-integration-convergence.json.
"""
import json
import statistics
from lrt_common import ROOT, PROCESSED_DIR

REPORTS = ROOT / "reports"
RAW_VS_1NM_MAX = 0.001    # 0.1 %
RAW_VS_NODE_MAX = 0.02    # 2 %


def main():
    data = json.loads((PROCESSED_DIR / "case_results.json").read_text())
    ok = [r for r in data if r.get("status") == "ok"
          and r.get("spectralIntegrationConvergence")]
    r1 = [r["spectralIntegrationConvergence"]["raw_vs_1nm_rel"] for r in ok
          if r["spectralIntegrationConvergence"]["raw_vs_1nm_rel"] is not None]
    rn = [r["spectralIntegrationConvergence"]["raw_vs_node_rel"] for r in ok
          if r["spectralIntegrationConvergence"]["raw_vs_node_rel"] is not None]
    result = {
        "nCases": len(ok),
        "primaryMethod": "raw-grid direct trapezoid (~0.05 nm)",
        "rawVs1nm": {"max": max(r1), "median": statistics.median(r1),
                     "threshold": RAW_VS_1NM_MAX,
                     "pass": max(r1) < RAW_VS_1NM_MAX},
        "rawVsNode": {"max": max(rn), "median": statistics.median(rn),
                      "threshold": RAW_VS_NODE_MAX,
                      "pass": max(rn) < RAW_VS_NODE_MAX},
    }
    result["pass"] = result["rawVs1nm"]["pass"] and result["rawVsNode"]["pass"]
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "spectral-integration-convergence.json").write_text(
        json.dumps(result, indent=1))
    print(json.dumps({"rawVs1nmMax": result["rawVs1nm"]["max"],
                      "rawVsNodeMax": result["rawVsNode"]["max"],
                      "pass": result["pass"]}, indent=1))


if __name__ == "__main__":
    main()
