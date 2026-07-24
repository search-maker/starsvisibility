"""RH-10: the expanded grid must be blocked until every pre-grid gate passes."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import grid_authorization as GA  # noqa: E402


def write(reports, name, obj):
    (reports / name).write_text(json.dumps(obj))


def test_not_authorized_when_vroom_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(GA, "REPORTS", tmp_path)
    write(tmp_path, "solver-validation.json", {"pass": True, "verdict": "ok"})
    write(tmp_path, "FEASIBILITY_REPORT.json",
          {"statistics": {"gates": [{"passed": True}]}})
    # no vroom-validation.json
    result = GA.evaluate()
    assert result["authorized"] is False
    vroom_gate = next(g for g in result["gates"] if "VROOM" in g["gate"])
    assert vroom_gate["passed"] is False


def test_not_authorized_when_vroom_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(GA, "REPORTS", tmp_path)
    write(tmp_path, "solver-validation.json", {"pass": True, "verdict": "ok"})
    write(tmp_path, "FEASIBILITY_REPORT.json",
          {"statistics": {"gates": [{"passed": True}]}})
    write(tmp_path, "vroom-validation.json",
          {"vroomAuthorizedForGrid": False, "maxAbsZ": 9.0})
    assert GA.evaluate()["authorized"] is False


def test_authorized_when_all_gates_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(GA, "REPORTS", tmp_path)
    write(tmp_path, "solver-validation.json", {"pass": True, "verdict": "ok"})
    write(tmp_path, "FEASIBILITY_REPORT.json",
          {"statistics": {"gates": [{"passed": True}, {"passed": True}]}})
    write(tmp_path, "vroom-validation.json",
          {"vroomAuthorizedForGrid": True, "maxAbsZ": 1.2,
           "meanRelDiff": 0.001, "directionBiasSpread": 0.005})
    assert GA.evaluate()["authorized"] is True


def test_not_authorized_when_a_feasibility_gate_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(GA, "REPORTS", tmp_path)
    write(tmp_path, "solver-validation.json", {"pass": True, "verdict": "ok"})
    write(tmp_path, "FEASIBILITY_REPORT.json",
          {"statistics": {"gates": [{"passed": True}, {"passed": False}]}})
    write(tmp_path, "vroom-validation.json", {"vroomAuthorizedForGrid": True})
    assert GA.evaluate()["authorized"] is False
