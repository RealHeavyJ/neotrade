"""Numeric ticker×window aggregates from cached posts (desk/summary only).

Not wired into LightGBM train/eval/backtest in Phase A/B.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from neotrade.social.cache import SocialPost

_CASHTAG = re.compile(r"\$([A-Za-z]{1,5})\b")
_TICKER_WORD = re.compile(r"\b([A-Z]{1,5})\b")


@dataclass(frozen=True)
class TickerSocialAgg:
    """Per-ticker social snapshot."""

    ticker: str
    n_posts: int
    mean_score: float
    eng_weighted_score: float
    total_engagement: int
    bullish: int
    bearish: int
    neutral: int

    @property
    def label(self) -> str:
        if self.mean_score > 0.15:
            return "bullish"
        if self.mean_score < -0.15:
            return "bearish"
        return "neutral"


def extract_tickers(text: str, universe: Iterable[str] | None = None) -> list[str]:
    """Pull cashtags and optional universe word matches from text."""
    found: set[str] = set()
    for m in _CASHTAG.finditer(text or ""):
        found.add(m.group(1).upper())
    if universe:
        uni = {u.upper() for u in universe}
        # word-boundary uppercase tickers that are in universe
        for m in _TICKER_WORD.finditer(text or ""):
            t = m.group(1).upper()
            if t in uni:
                found.add(t)
        # also lowercase mentions of universe symbols as whole words
        lower = (text or "").upper()
        for u in uni:
            if re.search(rf"\b{re.escape(u)}\b", lower):
                found.add(u)
    return sorted(found)


def aggregate_by_ticker(
    posts: Iterable[SocialPost],
    *,
    universe: Iterable[str] | None = None,
) -> list[TickerSocialAgg]:
    """Aggregate graded posts per ticker."""
    uni = {u.upper() for u in universe} if universe else None
    buckets: dict[str, list[SocialPost]] = defaultdict(list)
    for p in posts:
        tickers = list(p.tickers) if p.tickers else extract_tickers(p.text, universe)
        if uni is not None:
            tickers = [t for t in tickers if t in uni]
        if not tickers and p.tickers:
            tickers = list(p.tickers)
        for t in tickers:
            buckets[t].append(p)

    out: list[TickerSocialAgg] = []
    for ticker, rows in sorted(buckets.items()):
        n = len(rows)
        if n == 0:
            continue
        scores = [r.score for r in rows]
        mean = sum(scores) / n
        eng = [(r.likes + r.retweets + 1) for r in rows]
        total_eng = sum(eng)
        wmean = sum(s * e for s, e in zip(scores, eng, strict=True)) / total_eng
        bull = sum(1 for r in rows if r.label == "bullish")
        bear = sum(1 for r in rows if r.label == "bearish")
        neut = n - bull - bear
        out.append(
            TickerSocialAgg(
                ticker=ticker,
                n_posts=n,
                mean_score=mean,
                eng_weighted_score=wmean,
                total_engagement=total_eng - n,  # strip the +1 padding mass
                bullish=bull,
                bearish=bear,
                neutral=neut,
            )
        )
    # sort by |eng_weighted| * mentions for desk relevance
    out.sort(key=lambda a: (a.n_posts * (1.0 + abs(a.eng_weighted_score))), reverse=True)
    return out
