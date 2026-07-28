"""Advise learning policy — what to store, what never trains LightGBM.

Canonical rules for humans and agents:

1. **Advise is narrative decision-support only.** It must never become a
   LightGBM training label or feature.
2. **Auto-log** each advise run as ``advice_run`` (snapshot of stance/picks).
3. **Human rating** (1–5) is optional ``advice_feedback``; used for journal /
   prompt review only — not model fit.
4. **Retrain** only via ``neotrade train`` / ``neotrade eval`` on OHLCV labels.
5. Dashboard and CLI share :func:`record_advice_run` for parity.

See also ``docs/user-guide.md`` and ``AGENTS.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from neotrade.agents.recommend import AdviceReport
from neotrade.learning.log import append_entry, learning_dir, load_recent
from neotrade.logging_config import get_logger

log = get_logger("learning.policy")

# Kinds written to events.jsonl
KIND_ADVICE_RUN = "advice_run"
KIND_ADVICE_FEEDBACK = "advice_feedback"
KIND_RETRAIN = "retrain"

# Explicit denylist for any future “auto improve” feature
NEVER_USE_FOR_LIGHTGBM = frozenset(
    {
        KIND_ADVICE_RUN,
        KIND_ADVICE_FEEDBACK,
        "advise_prose",
        "trader_raw",
        "analyst_raw",
        "social_prose",
        "tweet_text",
        "desk_social_block",
    }
)

POLICY_SUMMARY = (
    "Advise logs are a journal only. LightGBM trains solely on OHLCV forward-return "
    "labels via `neotrade train`. Never feed stance/picks/prose into the signal model."
)


@dataclass(frozen=True)
class AdviceLearningPolicy:
    """Immutable policy knobs (documentation + validation helpers)."""

    min_rating: int = 1
    max_rating: int = 5
    auto_log_runs: bool = True
    allow_lightgbm_from_advice: bool = False  # must stay False

    def validate(self) -> None:
        if self.allow_lightgbm_from_advice:
            raise ValueError("policy forbids training LightGBM from advice")
        if self.min_rating < 1 or self.max_rating > 5 or self.min_rating > self.max_rating:
            raise ValueError("rating bounds must be within 1..5")


DEFAULT_POLICY = AdviceLearningPolicy()


def validate_rating(rating: int | None, *, policy: AdviceLearningPolicy = DEFAULT_POLICY) -> int | None:
    """Return rating if in range, else raise ``ValueError``."""
    if rating is None:
        return None
    r = int(rating)
    if r < policy.min_rating or r > policy.max_rating:
        raise ValueError(f"rating must be {policy.min_rating}..{policy.max_rating}, got {r}")
    return r


def record_advice_run(
    report: AdviceReport,
    *,
    source: str = "cli",
    rating: int | None = None,
    notes: str = "",
    policy: AdviceLearningPolicy = DEFAULT_POLICY,
) -> Path:
    """Persist an advise snapshot (+ optional human rating) under learning policy.

    Args:
        report: Parsed multi-agent advice.
        source: ``cli``, ``dashboard``, or other caller id.
        rating: Optional 1–5 human quality score.
        notes: Free-text journal note (not used for ML).
        policy: Policy instance (must keep ``allow_lightgbm_from_advice=False``).

    Returns:
        Path to ``events.jsonl``.

    Raises:
        ValueError: Invalid rating or forbidden policy.
    """
    policy.validate()
    rating = validate_rating(rating, policy=policy)
    # Never store full raw prose by default (token/privacy); keep short fields only
    payload: dict[str, Any] = {
        "source": source,
        "stance": report.stance,
        "summary": (report.summary or "")[:500],
        "top_picks": list(report.top_picks)[:20],
        "action": (report.action or "")[:300],
        "risks": list(report.risks)[:20],
        "model": report.model,
        "rating": rating,
        "notes": (notes or "")[:500],
        "lightgbm_eligible": False,
        "policy": "journal_only",
    }

    kind = KIND_ADVICE_FEEDBACK if rating is not None else KIND_ADVICE_RUN
    path = append_entry(kind, payload)
    log.info(
        "advice recorded kind=%s source=%s stance=%s rating=%s path=%s",
        kind,
        source,
        report.stance,
        rating,
        path,
    )
    return path


def advice_events(limit: int = 50) -> list[dict]:
    """Load recent advice_run / advice_feedback events only."""
    rows = load_recent(limit=max(limit * 3, 50))
    out = [r for r in rows if r.get("kind") in {KIND_ADVICE_RUN, KIND_ADVICE_FEEDBACK}]
    return out[-limit:]


def assert_not_lightgbm_source(kind: str) -> None:
    """Raise if a log kind is in the ML denylist (guard for future code)."""
    if kind in NEVER_USE_FOR_LIGHTGBM:
        raise RuntimeError(
            f"refusing to use log kind={kind!r} for LightGBM ({POLICY_SUMMARY})"
        )


def policy_blurb() -> str:
    """Short text for CLI/dashboard captions."""
    return POLICY_SUMMARY


def events_path() -> Path:
    """Path to the append-only learning events file."""
    return learning_dir() / "events.jsonl"
