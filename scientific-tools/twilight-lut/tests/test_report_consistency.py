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
    assert dom["fullCoreGeometryDepressionsDeg"] == [0, 4, 8]
    assert dom["provisionalZenithOnlyDepressionsDeg"] == [9, 10]


def test_feasibility_md_no_bare_525_claim():
    # RH-6: the MD is now auto-generated and must not contain a bare 525 figure
    # anywhere (it uses the canonical 540-node count from grid_def).
    md = (REPORTS / "FEASIBILITY_REPORT.md").read_text()
    for m in re.finditer(r"525", md):
        window = md[max(0, m.start() - 90): m.start() + 90].lower()
        assert "withdraw" in window or "supersed" in window, \
            "bare 525-cell claim present in auto-generated FEASIBILITY_REPORT.md"


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


def test_solver_validation_reports_three_solvers_separately():
    # PG-5: plane-parallel, pseudospherical, MYSTIC reported separately, and the
    # pseudospherical-vs-MYSTIC disagreement is quantified (not a false claim
    # that every pseudospherical value is negative).
    sv = json.loads((REPORTS / "solver-validation.json").read_text())
    assert "planeParallelDisort" in sv
    assert "pseudosphericalDisort" in sv
    assert "pseudosphericalVsMystic" in sv
    # MYSTIC must pass the EXACT expected probe count
    assert sv["mysticValidCount"] == sv["expectedMysticProbes"]
    # plane-parallel is zero below horizon; pseudospherical differs materially
    assert sv["planeParallelDisort"]["allZeroBelowHorizon"] is True
    assert sv["pseudosphericalVsMystic"]["maxAbsRelDiff"] > 0.5
    assert "not a claim" in sv["decision"].lower() or \
        "NOT a claim" in sv["decision"]


# RH-6: withdrawn claims must not appear in the auto-generated body except in an
# explicit withdrawal/supersede/NOT sentence.
BANNED = ["observation-consistent", "physically faithful",
          "independent observations", "fully supported", "525-cell"]


def test_feasibility_md_body_has_no_withdrawn_claims():
    md = (REPORTS / "FEASIBILITY_REPORT.md").read_text()
    low = md.lower()
    for phrase in BANNED:
        for m in re.finditer(re.escape(phrase.lower()), low):
            window = low[max(0, m.start() - 90): m.start() + 90]
            assert any(w in window for w in
                       ("withdraw", "supersed", "not ", "no ", "earlier")), \
                f"withdrawn claim '{phrase}' present without disclaimer"


def test_feasibility_md_is_autogenerated_marker():
    md = (REPORTS / "FEASIBILITY_REPORT.md").read_text()
    assert "AUTO-GENERATED" in md
    # the six-status model and honest scope must be present
    assert "firstVisibilityValidationStatus" in md
    assert "not recommended" in md.lower()


def test_domain_wording_is_precise_rh7():
    j = json.loads((REPORTS / "FEASIBILITY_REPORT.json").read_text())
    dom = j["statistics"]["supportedDomain"]
    assert dom["fullCoreGeometryDepressionsDeg"] == [0, 4, 8]
    assert dom["spotCheckDepressionsDeg"] == [2, 6]
    assert dom["provisionalZenithOnlyDepressionsDeg"] == [9, 10]


def test_paranal_contradiction_resolved_rh9():
    src = (ROOT / "PRIMARY_DATA_SOURCES.md").read_text().lower()
    prim = (REPORTS / "primary-observational-validation.json")
    data = json.loads(prim.read_text())
    # the live comparison must be unmatched, and the doc must not claim matched
    assert data["patat"]["matchedElevation"] is False
    assert "not yet run" in src or "not yet been run" in src or "unmatched" in src
    assert "requirements met in this milestone" not in src
