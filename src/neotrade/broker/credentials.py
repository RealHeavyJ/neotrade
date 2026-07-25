"""Load Alpaca paper credentials from environment / .env (never commit secrets)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from neotrade.config.load import project_root

PAPER_BASE_URL = "https://paper-api.alpaca.markets"
LIVE_BASE_URL = "https://api.alpaca.markets"

_ENV_KEYS = (
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
    "ALPACA_PAPER",
    "ALPACA_BASE_URL",
    "APCA_API_KEY_ID",
    "APCA_API_SECRET_KEY",
    "APCA_API_BASE_URL",
)


@dataclass(frozen=True)
class AlpacaCredentials:
    api_key: str
    secret_key: str
    base_url: str
    paper: bool

    def headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }


def _parse_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key:
            out[key] = val
    return out


def load_dotenv(path: Path | None = None) -> None:
    """Load .env into os.environ without overwriting existing vars."""
    env_path = path or (project_root() / ".env")
    for key, val in _parse_dotenv(env_path).items():
        os.environ.setdefault(key, val)


def _truthy(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_alpaca_credentials(*, require_paper: bool = True) -> AlpacaCredentials:
    load_dotenv()
    api_key = os.environ.get("ALPACA_API_KEY") or os.environ.get("APCA_API_KEY_ID") or ""
    secret = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("APCA_API_SECRET_KEY") or ""
    paper = _truthy(os.environ.get("ALPACA_PAPER"), default=True)
    base = (
        os.environ.get("ALPACA_BASE_URL")
        or os.environ.get("APCA_API_BASE_URL")
        or (PAPER_BASE_URL if paper else LIVE_BASE_URL)
    ).strip().rstrip("/")
    # Users often paste .../v2 from docs; client paths already include /v2/...
    base = base.removesuffix("/v2")

    if not api_key or not secret:
        raise RuntimeError(
            "Alpaca keys missing. Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env "
            "(see .env.example)."
        )

    is_paper_url = "paper-api.alpaca.markets" in base
    if require_paper and (not paper or not is_paper_url):
        raise RuntimeError(
            "neotrade refuses non-paper Alpaca endpoints. "
            f"Set ALPACA_PAPER=true and ALPACA_BASE_URL={PAPER_BASE_URL} "
            f"(got paper={paper}, base_url={base})"
        )
    if is_paper_url:
        paper = True

    return AlpacaCredentials(
        api_key=api_key.strip(),
        secret_key=secret.strip(),
        base_url=base,
        paper=paper,
    )
