"""JSONL cache for social posts under ``data/social/``."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from neotrade.config.load import project_root


@dataclass
class SocialPost:
    """One cached post (graded at ingest)."""

    ts: str
    source: str  # search | user | fixture
    text: str
    post_id: str = ""
    account: str = ""
    query: str = ""
    tickers: list[str] = field(default_factory=list)
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    score: float = 0.0
    label: str = "neutral"
    grade_method: str = "lexicon"
    grade_version: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SocialPost:
        tickers = data.get("tickers") or []
        if isinstance(tickers, str):
            tickers = [tickers]
        return cls(
            ts=str(data.get("ts") or ""),
            source=str(data.get("source") or ""),
            text=str(data.get("text") or ""),
            post_id=str(data.get("post_id") or ""),
            account=str(data.get("account") or ""),
            query=str(data.get("query") or ""),
            tickers=[str(t).upper() for t in tickers],
            likes=int(data.get("likes") or 0),
            retweets=int(data.get("retweets") or 0),
            replies=int(data.get("replies") or 0),
            score=float(data.get("score") or 0.0),
            label=str(data.get("label") or "neutral"),
            grade_method=str(data.get("grade_method") or "lexicon"),
            grade_version=str(data.get("grade_version") or ""),
            created_at=str(data.get("created_at") or ""),
        )


def social_dir(root: Path | None = None) -> Path:
    """``data/social`` under project root."""
    root = root or project_root()
    return root / "data" / "social"


def posts_path(root: Path | None = None) -> Path:
    return social_dir(root) / "posts.jsonl"


def meta_path(root: Path | None = None) -> Path:
    return social_dir(root) / "meta.json"


def ensure_social_dir(root: Path | None = None) -> Path:
    d = social_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    return d


def append_posts(posts: Iterable[SocialPost], root: Path | None = None) -> int:
    """Append posts to JSONL; return count written."""
    ensure_social_dir(root)
    path = posts_path(root)
    n = 0
    with path.open("a", encoding="utf-8") as fh:
        for p in posts:
            fh.write(json.dumps(p.to_dict(), ensure_ascii=False) + "\n")
            n += 1
    return n


def load_posts(
    root: Path | None = None,
    *,
    limit: int | None = None,
    max_age_hours: float | None = None,
) -> list[SocialPost]:
    """Load posts newest-last from JSONL.

    If ``limit`` is set, keep the last N lines (most recent appends).
    If ``max_age_hours`` is set, filter by ``ts`` parse when possible.
    """
    path = posts_path(root)
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if limit is not None and limit > 0:
        lines = lines[-limit:]
    posts: list[SocialPost] = []
    cutoff: datetime | None = None
    if max_age_hours is not None and max_age_hours > 0:
        cutoff = datetime.now(UTC).timestamp() - max_age_hours * 3600
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        post = SocialPost.from_dict(data)
        if cutoff is not None and post.ts:
            try:
                pt = datetime.fromisoformat(post.ts.replace("Z", "+00:00"))
                if pt.timestamp() < cutoff:
                    continue
            except ValueError:
                pass
        posts.append(post)
    return posts


def write_meta(meta: dict[str, Any], root: Path | None = None) -> None:
    ensure_social_dir(root)
    path = meta_path(root)
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_meta(root: Path | None = None) -> dict[str, Any]:
    path = meta_path(root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def cache_stats(root: Path | None = None) -> dict[str, Any]:
    """Summary for ``social status``."""
    path = posts_path(root)
    posts = load_posts(root, limit=50_000)
    size = path.stat().st_size if path.is_file() else 0
    last_ts = posts[-1].ts if posts else None
    return {
        "path": str(path),
        "n_posts": len(posts),
        "bytes": size,
        "last_ts": last_ts,
        "meta": read_meta(root),
    }
