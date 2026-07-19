"""Load ticker config from YAML."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from neotrade.config.models import TickersConfig

_ENV_TICKERS = "NEOTRADE_TICKERS"
_ENV_ROOT = "NEOTRADE_ROOT"


def project_root() -> Path:
    env = os.environ.get(_ENV_ROOT)
    if env:
        return Path(env).expanduser().resolve()
    # src/neotrade/config/load.py -> parents: config, neotrade, src, root
    return Path(__file__).resolve().parents[3]


def default_config_path() -> Path:
    env = os.environ.get(_ENV_TICKERS)
    if env:
        return Path(env).expanduser().resolve()
    return project_root() / "config" / "tickers.yaml"


def load_tickers_config(path: Path | str | None = None) -> TickersConfig:
    config_path = Path(path) if path is not None else default_config_path()
    if not config_path.is_file():
        raise FileNotFoundError(f"ticker config not found: {config_path}")
    with config_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"ticker config must be a mapping: {config_path}")
    return TickersConfig.model_validate(raw)


def resolve_cache_dir(settings_cache: Path, root: Path | None = None) -> Path:
    root = root or project_root()
    if settings_cache.is_absolute():
        return settings_cache
    return (root / settings_cache).resolve()
