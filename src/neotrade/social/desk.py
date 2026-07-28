"""Format social cache for desk packet (token-capped)."""

from __future__ import annotations

from pathlib import Path

from neotrade.social.cache import load_posts
from neotrade.social.features import aggregate_by_ticker
from neotrade.social.policy import social_enabled

# Keep llama3.2:3b context small on Neo 8GB
MAX_TICKER_LINES = 8
MAX_SAMPLE_LINES = 4
MAX_TEXT_CHARS = 120
DEFAULT_MAX_AGE_HOURS = 48.0


def social_desk_lines(
    *,
    root: Path | None = None,
    universe: list[str] | None = None,
    enabled: bool | None = None,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
) -> list[str]:
    """Return short SOCIAL: lines for the desk, or empty if disabled/stale/empty.

    When ``enabled`` is None, uses :func:`social_enabled` env flag.
    """
    if enabled is None:
        enabled = social_enabled()
    if not enabled:
        return []

    posts = load_posts(root, max_age_hours=max_age_hours)
    if not posts:
        return ["(no recent social cache — run: neotrade social fetch; set NEOTRADE_SOCIAL_ENABLED=1)"]

    aggs = aggregate_by_ticker(posts, universe=universe)
    lines: list[str] = [
        f"posts={len(posts)} window_h={max_age_hours:g} (journal only; not LightGBM train)",
    ]
    if not aggs:
        lines.append("(no ticker matches in cache for universe)")
        return lines

    for a in aggs[:MAX_TICKER_LINES]:
        lines.append(
            f"{a.ticker} n={a.n_posts} mean={a.mean_score:+.2f} "
            f"w={a.eng_weighted_score:+.2f} {a.label} "
            f"(b/n/s={a.bullish}/{a.neutral}/{a.bearish})"
        )

    # sample short headlines
    samples = 0
    for p in reversed(posts):
        if samples >= MAX_SAMPLE_LINES:
            break
        text = " ".join((p.text or "").split())
        if not text:
            continue
        if len(text) > MAX_TEXT_CHARS:
            text = text[: MAX_TEXT_CHARS - 1] + "…"
        handle = p.account or "?"
        lines.append(f"sample @{handle} [{p.label} {p.score:+.2f}]: {text}")
        samples += 1
    return lines
