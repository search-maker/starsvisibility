"""PG-7: the expanded grid must be blocked until every pre-grid gate passes.

Uses run_tests=False to avoid recursively invoking pytest; the pytest gates are
exercised by the real run in the evidence pass, not here.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import grid_authorization as GA  # noqa: E402


def write(reports, name, obj):
    (reports / name).write_text(json.dumps(obj))


def full_evidence(reports):
    write(reports, "solver-validation.json",
          {"pass": True, "mysticValidCount": 12, "expectedMysticProbes": 12})
    write(reports, "vroom-validation.json",
          {"vroomStatus": "experimental-not-authorized", "complete": True,
           "photopicEquivalenceDemonstrated": False,
           "okCellCount": 42, "cellCount": 42})
    write(reports, "PREGRID_HARDENING_REPORT.json",
          {"quickMode": False, "authorization": {"coreGridAuthorized": True}})
    write(reports, "FEASIBILITY_REPORT.json",
          {"statistics": {"gates": [{"passed": True}, {"passed": True}]}})
    write(reports, "johnson-v-validation.json",
          {"pass": True, "passed": 6, "total": 6})


def test_authorized_when_all_evidence_present(tmp_path, monkeypatch):
    monkeypatch.setattr(GA, "REPORTS", tmp_path)
    full_evidence(tmp_path)
    # run_tests=False -> the three pytest gates are marked not-run (fail),
    # so overall must be NOT authorized even with all evidence present.
    r = GA.evaluate(run_tests=False)
    assert r["authorized"] is False
    # but all the evidence gates themselves pass
    ev = {g["gate"]: g["passed"] for g in r["gates"]}
    assert ev["solver validation passes (exact MYSTIC probe count)"] is True
    assert any("VROOM" in k and v for k, v in ev.items())


def test_vroom_is_not_a_grid_prerequisite(tmp_path, monkeypatch):
    # grid uses mc_vroom off; the VROOM study status (even unauthorized) must NOT
    # block the grid. The gate instead confirms the grid config is VROOM off.
    monkeypatch.setattr(GA, "REPORTS", tmp_path)
    full_evidence(tmp_path)
    write(tmp_path, "vroom-validation.json",
          {"vroomStatus": "experimental-not-authorized", "complete": True,
           "photopicEquivalenceDemonstrated": False,
           "okCellCount": 42, "cellCount": 42})
    vroom_gate = next(g for g in GA.evaluate(run_tests=False)["gates"]
                      if "VROOM off" in g["gate"])
    assert vroom_gate["passed"] is True   # VROOM-off config, not a blocker


def test_grid_vroom_gate_passes_even_without_vroom_report(tmp_path, monkeypatch):
    monkeypatch.setattr(GA, "REPORTS", tmp_path)
    full_evidence(tmp_path)
    (tmp_path / "vroom-validation.json").unlink()   # no VROOM study at all
    vroom_gate = next(g for g in GA.evaluate(run_tests=False)["gates"]
                      if "VROOM off" in g["gate"])
    assert vroom_gate["passed"] is True


def test_blocked_when_pregrid_quick(tmp_path, monkeypatch):
    monkeypatch.setattr(GA, "REPORTS", tmp_path)
    full_evidence(tmp_path)
    write(tmp_path, "PREGRID_HARDENING_REPORT.json",
          {"quickMode": True, "authorization": {"coreGridAuthorized": True}})
    pg = next(g for g in GA.evaluate(run_tests=False)["gates"] if "pre-grid" in g["gate"])
    assert pg["passed"] is False


def test_blocked_when_solver_probe_count_short(tmp_path, monkeypatch):
    monkeypatch.setattr(GA, "REPORTS", tmp_path)
    full_evidence(tmp_path)
    write(tmp_path, "solver-validation.json",
          {"pass": True, "mysticValidCount": 1, "expectedMysticProbes": 12})
    sg = next(g for g in GA.evaluate(run_tests=False)["gates"] if "solver" in g["gate"])
    assert sg["passed"] is False


def test_records_git_commit(tmp_path, monkeypatch):
    monkeypatch.setattr(GA, "REPORTS", tmp_path)
    full_evidence(tmp_path)
    r = GA.evaluate(run_tests=False)
    assert "gitCommit" in r
