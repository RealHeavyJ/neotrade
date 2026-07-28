"""Thin X API v2 client (stdlib urllib + certifi). Soft-fails without token."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from neotrade.social.policy import bearer_token

API_BASE = "https://api.twitter.com/2"


class XAPIError(RuntimeError):
    """HTTP or API error from X."""

    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"X API {status}: {body[:400]}")
        self.status = status
        self.body = body


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


@dataclass
class RawTweet:
    """Normalized tweet from API or fixture."""

    post_id: str
    text: str
    created_at: str
    author_username: str
    likes: int
    retweets: int
    replies: int
    query: str = ""
    source: str = "search"


class XClient:
    """Minimal recent-search + user-timeline helper."""

    def __init__(self, token: str | None = None, *, timeout: float = 30.0) -> None:
        self.token = (token if token is not None else bearer_token()) or ""
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.token)

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        if not self.token:
            raise XAPIError(0, "no bearer token (set X_BEARER_TOKEN)")
        qs = urllib.parse.urlencode(params)
        url = f"{API_BASE}{path}?{qs}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "neotrade-social/0.1",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, context=_ssl_context(), timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                data = json.loads(body) if body else {}
                if not isinstance(data, dict):
                    raise XAPIError(resp.status, "non-object JSON")
                return data
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise XAPIError(exc.code, err_body) from exc
        except urllib.error.URLError as exc:
            raise XAPIError(0, str(exc.reason)) from exc

    def search_recent(
        self,
        query: str,
        *,
        max_results: int = 10,
    ) -> list[RawTweet]:
        """``GET /2/tweets/search/recent``."""
        max_results = max(10, min(100, int(max_results)))
        data = self._get(
            "/tweets/search/recent",
            {
                "query": query,
                "max_results": str(max_results),
                "tweet.fields": "created_at,public_metrics,author_id",
                "expansions": "author_id",
                "user.fields": "username",
            },
        )
        return _parse_tweets(data, query=query, source="search")

    def user_recent(
        self,
        username: str,
        *,
        max_results: int = 5,
    ) -> list[RawTweet]:
        """Resolve user then fetch recent tweets."""
        username = username.lstrip("@")
        u = self._get(
            f"/users/by/username/{urllib.parse.quote(username)}",
            {"user.fields": "username"},
        )
        user = u.get("data") or {}
        uid = user.get("id")
        if not uid:
            return []
        data = self._get(
            f"/users/{uid}/tweets",
            {
                "max_results": str(max(5, min(100, int(max_results)))),
                "tweet.fields": "created_at,public_metrics,author_id",
                "exclude": "retweets,replies",
            },
        )
        tweets = _parse_tweets(data, query=f"from:{username}", source="user")
        for t in tweets:
            if not t.author_username:
                t.author_username = username
        return tweets


def _parse_tweets(
    data: dict[str, Any],
    *,
    query: str,
    source: str,
) -> list[RawTweet]:
    users = {}
    for u in (data.get("includes") or {}).get("users") or []:
        if isinstance(u, dict) and u.get("id"):
            users[str(u["id"])] = str(u.get("username") or "")
    out: list[RawTweet] = []
    for row in data.get("data") or []:
        if not isinstance(row, dict):
            continue
        metrics = row.get("public_metrics") or {}
        author_id = str(row.get("author_id") or "")
        out.append(
            RawTweet(
                post_id=str(row.get("id") or ""),
                text=str(row.get("text") or ""),
                created_at=str(row.get("created_at") or ""),
                author_username=users.get(author_id, ""),
                likes=int(metrics.get("like_count") or 0),
                retweets=int(metrics.get("retweet_count") or 0),
                replies=int(metrics.get("reply_count") or 0),
                query=query,
                source=source,
            )
        )
    return out
