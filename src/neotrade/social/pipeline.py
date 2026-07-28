"""Fetch → grade → cache pipeline for social posts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from neotrade.logging_config import get_logger
from neotrade.social.accounts import SocialAccount, default_accounts_path, load_social_accounts
from neotrade.social.cache import SocialPost, append_posts, write_meta
from neotrade.social.client import RawTweet, XAPIError, XClient
from neotrade.social.features import extract_tickers
from neotrade.social.sentiment import grade_text

log = get_logger("social.pipeline")

_CASHTAG = re.compile(r"\$([A-Za-z]{1,5})\b")


@dataclass
class FetchResult:
    """Outcome of one social fetch run."""

    n_fetched: int = 0
    n_written: int = 0
    errors: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    token_present: bool = False


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def raw_to_post(raw: RawTweet, universe: list[str] | None) -> SocialPost:
    """Grade a raw tweet into a cacheable SocialPost."""
    grade = grade_text(raw.text)
    tickers = extract_tickers(raw.text, universe)
    for m in _CASHTAG.finditer(raw.query or ""):
        t = m.group(1).upper()
        if t not in tickers:
            tickers.append(t)
    return SocialPost(
        ts=_now_iso(),
        source=raw.source,
        text=raw.text,
        post_id=raw.post_id,
        account=raw.author_username,
        query=raw.query,
        tickers=tickers,
        likes=raw.likes,
        retweets=raw.retweets,
        replies=raw.replies,
        score=grade.score,
        label=grade.label,
        grade_method=grade.method,
        grade_version=grade.version,
        created_at=raw.created_at,
    )


def fetch_and_cache(
    *,
    symbols: list[str],
    root: Path | None = None,
    accounts: list[SocialAccount] | None = None,
    client: XClient | None = None,
    max_per_query: int = 10,
    max_accounts: int | None = None,
    include_accounts: bool = True,
    include_cashtags: bool = True,
    search_fn: Callable[[str, int], list[RawTweet]] | None = None,
) -> FetchResult:
    """Pull recent posts, grade with lexicon, append JSONL cache.

    ``search_fn(query, max_results)`` injects fixtures for tests (no network).
    """
    result = FetchResult()
    cli = client or XClient()
    result.token_present = cli.available or search_fn is not None

    if not result.token_present:
        result.errors.append(
            "no X_BEARER_TOKEN / TWITTER_BEARER_TOKEN — skip live fetch"
        )
        write_meta(
            {
                "last_fetch_ts": _now_iso(),
                "ok": False,
                "error": "missing_token",
                "n_written": 0,
            },
            root=root,
        )
        return result

    if accounts is None and include_accounts:
        accounts = load_social_accounts(default_accounts_path(root))
    accounts = accounts or []

    posts: list[SocialPost] = []
    seen_ids: set[str] = set()

    def _ingest(raws: list[RawTweet]) -> None:
        for raw in raws:
            if raw.post_id and raw.post_id in seen_ids:
                continue
            if raw.post_id:
                seen_ids.add(raw.post_id)
            posts.append(raw_to_post(raw, symbols))
            result.n_fetched += 1

    try:
        if include_cashtags:
            for sym in symbols:
                q = f"${sym} OR {sym} -is:retweet lang:en"
                result.queries.append(q)
                try:
                    if search_fn is not None:
                        raws = search_fn(q, max_per_query)
                    else:
                        raws = cli.search_recent(q, max_results=max_per_query)
                    _ingest(raws)
                except XAPIError as exc:
                    msg = f"search {sym}: {exc}"
                    log.warning("%s", msg)
                    result.errors.append(msg)

        if include_accounts and accounts:
            acc_list = accounts[: max_accounts] if max_accounts is not None else accounts
            for acc in acc_list:
                try:
                    if search_fn is not None:
                        q = f"from:{acc.username}"
                        result.queries.append(q)
                        raws = search_fn(q, max_per_query)
                    else:
                        result.queries.append(f"user:{acc.username}")
                        raws = cli.user_recent(acc.username, max_results=min(5, max_per_query))
                    _ingest(raws)
                except XAPIError as exc:
                    msg = f"user {acc.username}: {exc}"
                    log.warning("%s", msg)
                    result.errors.append(msg)
    except (XAPIError, OSError, ValueError, TypeError, RuntimeError) as exc:
        log.warning("social fetch failed: %s", exc)
        result.errors.append(str(exc))

    if posts:
        result.n_written = append_posts(posts, root=root)

    write_meta(
        {
            "last_fetch_ts": _now_iso(),
            "ok": result.n_written > 0 or not result.errors,
            "n_fetched": result.n_fetched,
            "n_written": result.n_written,
            "n_errors": len(result.errors),
            "errors": result.errors[:10],
            "n_queries": len(result.queries),
        },
        root=root,
    )
    return result
