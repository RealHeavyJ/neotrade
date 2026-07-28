"""Load curated X account watchlist from YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from neotrade.config.load import project_root


@dataclass(frozen=True)
class SocialAccount:
    """One FinTwit / research handle."""

    handle: str
    tags: tuple[str, ...] = ()
    tier: str = "core"
    note: str = ""

    @property
    def username(self) -> str:
        return self.handle.lstrip("@").strip()


def default_accounts_path(root: Path | None = None) -> Path:
    """Path to ``config/social_accounts.yaml``."""
    root = root or project_root()
    return root / "config" / "social_accounts.yaml"


def load_social_accounts(path: Path | str | None = None) -> list[SocialAccount]:
    """Parse accounts YAML; empty list if missing (soft)."""
    p = Path(path) if path is not None else default_accounts_path()
    if not p.is_file():
        return []
    with p.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise TypeError(f"social accounts config must be a mapping: {p}")
    rows = raw.get("accounts") or []
    out: list[SocialAccount] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        handle = str(item.get("handle") or item.get("username") or "").strip()
        if not handle:
            continue
        tags = item.get("tags") or []
        if isinstance(tags, str):
            tag_t = tuple(t.strip() for t in tags.split(",") if t.strip())
        else:
            tag_t = tuple(str(t).strip() for t in tags if str(t).strip())
        out.append(
            SocialAccount(
                handle=handle.lstrip("@"),
                tags=tag_t,
                tier=str(item.get("tier") or "core"),
                note=str(item.get("note") or ""),
            )
        )
    return out


def accounts_to_dict(accounts: list[SocialAccount]) -> list[dict[str, Any]]:
    """Serialize for status/debug."""
    return [
        {
            "handle": a.handle,
            "tags": list(a.tags),
            "tier": a.tier,
            "note": a.note,
        }
        for a in accounts
    ]
