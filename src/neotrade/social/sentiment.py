"""Fast lexicon sentiment for trading text (no external NLP deps).

Scores are in ``[-1.0, 1.0]``. Version string is stored on each graded post so
historical series stay point-in-time if the lexicon changes later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

LEXICON_VERSION = "lexicon_v1"

# Small finance-oriented word lists (not comprehensive; good enough for archive grading)
_BULL = frozenset(
    {
        "bull",
        "bullish",
        "buy",
        "long",
        "breakout",
        "moon",
        "rally",
        "upgrade",
        "beat",
        "beats",
        "strong",
        "growth",
        "outperform",
        "accumulate",
        "upside",
        "squeeze",
        "call",
        "calls",
        "support",
        "bounce",
        "surge",
        "rip",
        "ripping",
        "green",
        "higher",
        "ath",
        "all-time",
        "record",
    }
)
_BEAR = frozenset(
    {
        "bear",
        "bearish",
        "sell",
        "short",
        "breakdown",
        "crash",
        "downgrade",
        "miss",
        "misses",
        "weak",
        "underperform",
        "dump",
        "downside",
        "put",
        "puts",
        "resistance",
        "fade",
        "red",
        "lower",
        "fraud",
        "scam",
        "overvalued",
        "bubble",
        "panic",
        "plunge",
        "tank",
        "tanking",
    }
)

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_\-]{1,30}")


@dataclass(frozen=True)
class SentimentScore:
    """Lexicon grade for one post."""

    score: float
    label: str  # bullish | bearish | neutral
    method: str
    version: str
    bull_hits: int
    bear_hits: int


def grade_text(text: str) -> SentimentScore:
    """Score free text with a simple finance lexicon."""
    tokens = [t.lower() for t in _TOKEN_RE.findall(text or "")]
    bull = sum(1 for t in tokens if t in _BULL)
    bear = sum(1 for t in tokens if t in _BEAR)
    total = bull + bear
    if total == 0:
        return SentimentScore(
            score=0.0,
            label="neutral",
            method="lexicon",
            version=LEXICON_VERSION,
            bull_hits=0,
            bear_hits=0,
        )
    raw = (bull - bear) / total
    # damp extreme single-hit noise slightly
    score = max(-1.0, min(1.0, float(raw)))
    if score > 0.15:
        label = "bullish"
    elif score < -0.15:
        label = "bearish"
    else:
        label = "neutral"
    return SentimentScore(
        score=score,
        label=label,
        method="lexicon",
        version=LEXICON_VERSION,
        bull_hits=bull,
        bear_hits=bear,
    )
