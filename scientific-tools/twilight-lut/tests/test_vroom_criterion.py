"""VROOM authorization uses a TOST-style EQUIVALENCE test: a bias counts as
equivalent to zero only if its 95% CI lies ENTIRELY within the tolerance.
Failure to reject a difference is NOT equivalence (directive #2)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import vroom_validation as V  # noqa: E402


def stat(mean, ci):
    return {"mean": mean, "ci95HalfWidth": ci, "significant": abs(mean) > ci,
            "n": 3, "sd": 0, "se": 0, "t": 0}


def test_wide_ci_is_not_equivalence_even_if_nonsignificant():
    # large noisy difference, CI spills past tolerance -> NOT equivalent
    assert V._equivalent(stat(0.005, 0.20), tol=0.03) is False


def test_tight_ci_within_tolerance_is_equivalent():
    assert V._equivalent(stat(0.01, 0.015), tol=0.03) is True   # 0.025 <= 0.03


def test_ci_touching_edge_fails():
    assert V._equivalent(stat(0.02, 0.02), tol=0.03) is False   # 0.04 > 0.03


def test_authorize_requires_all_biases_equivalent():
    overall = stat(0.005, 0.01)
    dir_bias = {"sunward": stat(0.01, 0.015), "cross": stat(0.0, 0.01),
                "anti": stat(0.005, 0.02)}
    ratio = stat(0.0, 0.01)
    auth, _ = V.decide_authorization(True, True, overall, dir_bias, ratio)
    assert auth is True


def test_block_when_any_bias_ci_too_wide():
    overall = stat(0.005, 0.01)
    dir_bias = {"sunward": stat(0.02, 0.30), "cross": stat(0.0, 0.01),
                "anti": stat(0.0, 0.01)}     # wide noisy CI
    ratio = stat(0.0, 0.01)
    auth, reason = V.decide_authorization(True, True, overall, dir_bias, ratio)
    assert auth is False
    assert "equivalence NOT demonstrated" in reason


def test_block_when_incomplete():
    auth, _ = V.decide_authorization(False, True, stat(0, 0.01),
                                     {"sunward": stat(0, 0.01)}, stat(0, 0.01))
    assert auth is False


def test_block_when_mandatory_stat_missing():
    auth, _ = V.decide_authorization(True, False, None,
                                     {"sunward": None}, None)
    assert auth is False
