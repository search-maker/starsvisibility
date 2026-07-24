"""VROOM authorization criterion: significance AND non-negligibility required
to count a difference as a real bias (justified by vroom-deep-diagnostic:
deep-cell scatter sign-flips and is non-significant at high photons)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import vroom_validation as V  # noqa: E402


def stat(mean, significant):
    return {"mean": mean, "significant": significant, "n": 3, "sd": 0, "se": 0,
            "t": 0, "ci95HalfWidth": 0}


def test_large_but_nonsignificant_is_not_a_bias():
    # a big point estimate that is NOT statistically significant -> noise, ok
    assert V._biased(stat(0.20, significant=False)) is False


def test_significant_but_negligible_is_not_a_bias():
    # significant but below the 3% negligibility threshold -> ok
    assert V._biased(stat(0.02, significant=True)) is False


def test_significant_and_nonnegligible_is_a_bias():
    assert V._biased(stat(0.08, significant=True)) is True


def test_authorize_when_only_negligible_significant_bias():
    overall = stat(0.014, False)
    dir_bias = {"sunward": stat(0.020, True),   # significant but negligible
                "cross": stat(-0.004, False),
                "anti": stat(0.021, False)}      # large but not significant
    ratio = stat(-0.003, False)
    auth, reason = V.decide_authorization(True, True, overall, dir_bias, ratio)
    assert auth is True


def test_block_when_real_bias_present():
    overall = stat(0.05, True)   # significant AND non-negligible
    dir_bias = {"sunward": stat(0.01, False), "cross": stat(0.0, False),
                "anti": stat(0.0, False)}
    ratio = stat(0.0, False)
    auth, _ = V.decide_authorization(True, True, overall, dir_bias, ratio)
    assert auth is False


def test_block_when_incomplete():
    auth, _ = V.decide_authorization(False, True, stat(0, False),
                                     {"sunward": stat(0, False)}, stat(0, False))
    assert auth is False


def test_block_when_mandatory_stat_missing():
    auth, _ = V.decide_authorization(True, False, None,
                                     {"sunward": None}, None)
    assert auth is False
