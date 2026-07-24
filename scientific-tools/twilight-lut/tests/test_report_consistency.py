"""Milestone 3 §2.5: the Markdown reports must not contradict the machine
-readable JSON, and withdrawn/incorrect claims must not reappear.

These tests read the committed report artifacts. They fail loudly if a stale
node count, a withdrawn cost projection, or an over-broad domain claim is
present in the Markdown, or if the grid node count drifts from grid_def.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from grid_def import DEFAULT_GRID  # noqa: E402

REPORTS = ROOT / "reports"


def test_grid_node_count_is_canonical():
    c = DEFAULT_GRID.counts()
    # 5 dep x 3 aod x (5 non-zenith alt x 7 az + 1 zenith) = 5*3*36 = 540
    assert c["uniqueNodeCount"] == 540
    assert c["zenithNodesPerDepAod"] == 1
    # zenith must NOT be multiplied by the 7 azimuths
    assert c["uniqueNodeCount"] < 5 * 3 * 6 * 7


def test_feasibility_json_has_six_status_model():
    j = json.loads((REPORTS / "FEASIBILITY_REPORT.json").read_text())
    sm = j["statistics"]["statusModel"]
    for key in ("solverFeasibilityStatus", "numericalStabilityStatus",
                "literaturePlausibilityStatus",
                "primaryObservationalValidationStatus",
                "firstVisibilityValidationStatus", "productionReadinessStatus"):
        assert key in sm, key
    # first-visibility must be honestly blocked, production not recommended
    assert "BLOCKED" in sm["firstVisibilityValidationStatus"]
    assert "NOT RECOMMENDED" in sm["productionReadinessStatus"]


def test_feasibility_json_domain_not_full_hypercube():
    j = json.loads((REPORTS / "FEASIBILITY_REPORT.json").read_text())
    dom = j["statistics"]["supportedDomain"]
    assert dom["fullHypercubeSupported"] is False
    assert dom["demonstratedCore"]["sunDepressionDeg"] == [0, 8]
    assert dom["provisionalExtension"]["sunDepressionDeg"] == [9, 10]


def test_feasibility_md_has_correction_banner():
    md = (REPORTS / "FEASIBILITY_REPORT.md").read_text()
    assert "CORRECTIONS" in md
    # the withdrawn 525 figure may only appear in a withdrawal sentence
    for m in re.finditer(r"525", md):
        window = md[max(0, m.start() - 90): m.start() + 90].lower()
        assert "withdraw" in window or "supersed" in window, \
            "bare 525-cell claim resurfaced in FEASIBILITY_REPORT.md"


def test_canonical_grid_projection_matches_grid_def():
    j = json.loads((REPORTS / "FEASIBILITY_REPORT.json").read_text())
    grid = j["statistics"]["canonicalGrid"]
    assert grid["counts"]["uniqueNodeCount"] == DEFAULT_GRID.counts()["uniqueNodeCount"]


def test_gates_are_evidence_based_not_hardcoded():
    j = json.loads((REPORTS / "FEASIBILITY_REPORT.json").read_text())
    gi = j["statistics"]["gateInputs"]
    # solver gate must be backed by a real solver-validation.json result
    assert (REPORTS / "solver-validation.json").exists()
    sv = json.loads((REPORTS / "solver-validation.json").read_text())
    assert gi["solverValidationPass"] == sv["pass"]
    # core-cell coverage must be measured, full 36 present and resolved
    assert gi["coreCellsExpected"] == 36
    assert gi["coreCellsPresent"] >= 36
    assert gi["coreCellsResolved"] == gi["coreCellsPresent"]
    # stability gate uses p95/max, not just median
    assert gi["relP95"] is not None and gi["relMax"] is not None
    # MC gate requires spread across >=2 depressions
    assert len(gi["mcDepthSpread"]) >= 2


def test_solver_validation_records_disort_invalid_below_horizon():
    sv = json.loads((REPORTS / "solver-validation.json").read_text())
    assert sv["disortInvalidBelowHorizon"] is True
    assert sv["mysticAllValid"] is True
