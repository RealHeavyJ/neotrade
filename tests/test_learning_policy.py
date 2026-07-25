"""P3 advise learning policy tests."""

from __future__ import annotations

import pytest

from neotrade.agents.recommend import AdviceReport
from neotrade.learning.policy import (
    DEFAULT_POLICY,
    KIND_ADVICE_FEEDBACK,
    KIND_ADVICE_RUN,
    NEVER_USE_FOR_LIGHTGBM,
    AdviceLearningPolicy,
    assert_not_lightgbm_source,
    policy_blurb,
    record_advice_run,
    validate_rating,
)


def _report() -> AdviceReport:
    return AdviceReport(
        trader_raw="THESIS: x\nTOP_PICKS: ARM, TSM\nACTION: hold",
        analyst_raw="STANCE: cautious\nSUMMARY: careful",
        stance="cautious",
        summary="careful",
        top_picks=["ARM", "TSM"],
        action="hold",
        model="mock",
    )


def test_policy_forbids_lightgbm_flag():
    bad = AdviceLearningPolicy(allow_lightgbm_from_advice=True)
    with pytest.raises(ValueError, match="forbids"):
        bad.validate()
    DEFAULT_POLICY.validate()


def test_validate_rating_bounds():
    assert validate_rating(None) is None
    assert validate_rating(3) == 3
    with pytest.raises(ValueError):
        validate_rating(0)
    with pytest.raises(ValueError):
        validate_rating(6)


def test_record_advice_run_and_feedback(monkeypatch, tmp_path):
    from neotrade.learning import log as log_mod
    from neotrade.learning import policy as policy_mod

    monkeypatch.setattr(log_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(policy_mod, "learning_dir", lambda: tmp_path / "data" / "learning")

    path = record_advice_run(_report(), source="cli", notes="auto")
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert KIND_ADVICE_RUN in text
    assert "lightgbm_eligible" in text
    assert "false" in text.lower() or "False" in text

    path2 = record_advice_run(_report(), source="dashboard", rating=5, notes="great")
    text2 = path2.read_text(encoding="utf-8")
    assert KIND_ADVICE_FEEDBACK in text2
    assert '"rating": 5' in text2


def test_assert_not_lightgbm_source():
    with pytest.raises(RuntimeError, match="LightGBM"):
        assert_not_lightgbm_source(KIND_ADVICE_RUN)
    assert KIND_ADVICE_FEEDBACK in NEVER_USE_FOR_LIGHTGBM


def test_policy_blurb_mentions_journal():
    blurb = policy_blurb()
    assert "LightGBM" in blurb
    assert "journal" in blurb.lower() or "OHLCV" in blurb
