"""Social module unit tests (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from neotrade.agents.desk_context import DeskPacket
from neotrade.social.accounts import SocialAccount, load_social_accounts
from neotrade.social.cache import SocialPost, append_posts, cache_stats, load_posts
from neotrade.social.client import RawTweet
from neotrade.social.desk import social_desk_lines
from neotrade.social.features import aggregate_by_ticker, extract_tickers
from neotrade.social.pipeline import fetch_and_cache, raw_to_post
from neotrade.social.policy import (
    NEVER_USE_FOR_LIGHTGBM,
    assert_not_train_text,
    social_enabled,
)
from neotrade.social.sentiment import grade_text


def test_grade_bullish_and_bearish():
    bull = grade_text("Strong breakout buy long upgrade beat growth")
    bear = grade_text("Bearish dump sell short crash miss weak")
    assert bull.score > 0
    assert bull.label == "bullish"
    assert bear.score < 0
    assert bear.label == "bearish"
    neut = grade_text("The company filed a form today")
    assert neut.label == "neutral"
    assert neut.score == 0.0


def test_extract_tickers_cashtag_and_universe():
    text = "Watching $NVDA and AAPL into the open; TSLA noise"
    found = extract_tickers(text, universe=["NVDA", "AAPL", "MSFT"])
    assert "NVDA" in found
    assert "AAPL" in found
    assert "TSLA" not in found  # not in universe, no cashtag


def test_load_accounts_yaml():
    root = Path(__file__).resolve().parents[1]
    accounts = load_social_accounts(root / "config" / "social_accounts.yaml")
    assert len(accounts) >= 10
    handles = {a.username.lower() for a in accounts}
    assert "unusual_whales" in handles


def test_cache_roundtrip(tmp_path: Path):
    posts = [
        SocialPost(
            ts="2026-07-25T12:00:00+00:00",
            source="fixture",
            text="Bullish breakout on $NVDA",
            post_id="1",
            account="tester",
            tickers=["NVDA"],
            likes=10,
            retweets=2,
            score=0.5,
            label="bullish",
            grade_method="lexicon",
            grade_version="lexicon_v1",
        )
    ]
    n = append_posts(posts, root=tmp_path)
    assert n == 1
    loaded = load_posts(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].tickers == ["NVDA"]
    stats = cache_stats(tmp_path)
    assert stats["n_posts"] == 1
    assert stats["bytes"] > 0


def test_aggregate_by_ticker():
    posts = [
        SocialPost(
            ts="t",
            source="f",
            text="$AAPL buy",
            tickers=["AAPL"],
            score=0.8,
            label="bullish",
            likes=5,
        ),
        SocialPost(
            ts="t",
            source="f",
            text="$AAPL sell",
            tickers=["AAPL"],
            score=-0.4,
            label="bearish",
            likes=1,
        ),
        SocialPost(
            ts="t",
            source="f",
            text="$MSFT neutral",
            tickers=["MSFT"],
            score=0.0,
            label="neutral",
            likes=0,
        ),
    ]
    aggs = aggregate_by_ticker(posts, universe=["AAPL", "MSFT"])
    by = {a.ticker: a for a in aggs}
    assert by["AAPL"].n_posts == 2
    assert by["MSFT"].n_posts == 1


def test_policy_blocks_prose_fields():
    assert "tweet_text" in NEVER_USE_FOR_LIGHTGBM
    with pytest.raises(ValueError, match="refusing"):
        assert_not_train_text("tweet_text")


def test_social_enabled_default_off(monkeypatch):
    monkeypatch.delenv("NEOTRADE_SOCIAL_ENABLED", raising=False)
    assert social_enabled() is False
    monkeypatch.setenv("NEOTRADE_SOCIAL_ENABLED", "1")
    assert social_enabled() is True


def test_desk_lines_empty_when_disabled(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NEOTRADE_SOCIAL_ENABLED", "0")
    append_posts(
        [
            SocialPost(
                ts="2026-07-25T12:00:00+00:00",
                source="f",
                text="$NVDA moon",
                tickers=["NVDA"],
                score=0.5,
                label="bullish",
            )
        ],
        root=tmp_path,
    )
    assert social_desk_lines(root=tmp_path, universe=["NVDA"], enabled=False) == []


def test_desk_lines_when_enabled(tmp_path: Path):
    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat()
    append_posts(
        [
            SocialPost(
                ts=now,
                source="f",
                text="Strong buy breakout $NVDA growth",
                post_id="x",
                account="ripster47",
                tickers=["NVDA"],
                score=0.6,
                label="bullish",
                likes=3,
            )
        ],
        root=tmp_path,
    )
    lines = social_desk_lines(root=tmp_path, universe=["NVDA"], enabled=True)
    assert lines
    assert any("NVDA" in ln for ln in lines)
    assert any("journal only" in ln for ln in lines)


def test_fetch_pipeline_with_fixture_fn(tmp_path: Path):
    def search_fn(query: str, max_results: int) -> list[RawTweet]:
        return [
            RawTweet(
                post_id=f"id-{query[:8]}",
                text=f"Bullish upgrade on query {query}",
                created_at="2026-07-25T00:00:00Z",
                author_username="bot",
                likes=1,
                retweets=0,
                replies=0,
                query=query,
                source="search",
            )
        ]

    result = fetch_and_cache(
        symbols=["AAPL"],
        root=tmp_path,
        accounts=[SocialAccount(handle="tester", tags=("t",))],
        include_accounts=True,
        include_cashtags=True,
        max_per_query=10,
        search_fn=search_fn,
    )
    assert result.n_written >= 1
    assert result.token_present
    posts = load_posts(tmp_path)
    assert len(posts) >= 1
    assert posts[0].grade_method == "lexicon"


def test_fetch_missing_token_soft_fail(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)
    # Isolate from developer machine .env
    monkeypatch.setenv("NEOTRADE_ROOT", str(tmp_path))
    (tmp_path / ".env").write_text("", encoding="utf-8")
    result = fetch_and_cache(symbols=["AAPL"], root=tmp_path, include_accounts=False)
    assert result.n_written == 0
    assert result.errors
    assert not result.token_present


def test_bearer_token_loads_from_dotenv(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)
    monkeypatch.setenv("NEOTRADE_ROOT", str(tmp_path))
    (tmp_path / ".env").write_text("X_BEARER_TOKEN=test_token_from_dotenv\n", encoding="utf-8")
    from neotrade.social.policy import bearer_token

    assert bearer_token() == "test_token_from_dotenv"


def test_raw_to_post_grades():
    raw = RawTweet(
        post_id="1",
        text="Huge rally breakout buy",
        created_at="t",
        author_username="a",
        likes=0,
        retweets=0,
        replies=0,
        query="$MSFT",
        source="search",
    )
    post = raw_to_post(raw, ["MSFT"])
    assert post.score > 0
    assert "MSFT" in post.tickers


def test_desk_packet_includes_social_in_prompt():
    pkt = DeskPacket(
        ts="t",
        session_line="closed",
        allow_execute=False,
        universe="test",
        regime_line="neutral",
        social_lines=["NVDA n=2 mean=+0.40 bullish"],
    )
    block = pkt.to_prompt_block()
    assert "SOCIAL" in block
    assert "never LightGBM train" in block
    assert "NVDA n=2" in block


def test_cli_social_status(tmp_path: Path, monkeypatch):
    import argparse

    from neotrade.cli.social_cmds import cmd_social

    monkeypatch.setenv("NEOTRADE_ROOT", str(tmp_path))
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "config" / "tickers.yaml").write_text(
        "universe: {name: t}\ntickers: [{symbol: AAPL}]\n",
        encoding="utf-8",
    )
    args = argparse.Namespace(social_action="status")
    assert cmd_social(args) == 0
