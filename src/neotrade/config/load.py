"""Load ticker universe and risk settings from YAML.

Environment overrides:
    * ``NEOTRADE_ROOT`` — project root (tests / alternate installs)
    * ``NEOTRADE_TICKERS`` — absolute path to tickers YAML
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from neotrade.config.models import TickersConfig

_ENV_TICKERS = "NEOTRADE_TICKERS"
_ENV_ROOT = "NEOTRADE_ROOT"


def project_root() -> Path:
    """Return the neotrade repository root directory.

    Resolution order:
        1. ``NEOTRADE_ROOT`` if set
        2. Path relative to this file (``src/neotrade/config/load.py`` → repo root)
    """
    env = os.environ.get(_ENV_ROOT)
    if env:
        return Path(env).expanduser().resolve()
    # parents: config → neotrade → src → repo root
    return Path(__file__).resolve().parents[3]


def default_config_path() -> Path:
    """Path to ``config/tickers.yaml``, or ``NEOTRADE_TICKERS`` override."""
    env = os.environ.get(_ENV_TICKERS)
    if env:
        return Path(env).expanduser().resolve()
    return project_root() / "config" / "tickers.yaml"


def load_tickers_config(path: Path | str | None = None) -> TickersConfig:
    """Parse and validate ticker YAML into :class:`TickersConfig`.

    Args:
        path: Optional YAML path. Defaults to :func:`default_config_path`.

    Raises:
        FileNotFoundError: Missing config file.
        ValueError: YAML root is not a mapping.
        pydantic.ValidationError: Schema validation failed.
    """
    config_path = Path(path) if path is not None else default_config_path()
    if not config_path.is_file():
        raise FileNotFoundError(f"ticker config not found: {config_path}")
    with config_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"ticker config must be a mapping: {config_path}")
    return TickersConfig.model_validate(raw)


def resolve_cache_dir(settings_cache: Path, root: Path | None = None) -> Path:
    """Resolve a possibly relative cache directory against project root."""
    root = root or project_root()
    if settings_cache.is_absolute():
        return settings_cache
    return (root / settings_cache).resolve()
