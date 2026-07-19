from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from neotrade.config.load import load_tickers_config, project_root, resolve_cache_dir
from neotrade.config.models import TickersConfig


def test_load_default_tickers_config():
    cfg = load_tickers_config()
    assert len(cfg.tickers) == 22
    assert "NVDA" in cfg.symbols()
    assert "JNJ" in cfg.symbols()
    assert cfg.data.provider == "auto"
    assert cfg.universe.name == "neotrade-core-22"
    assert cfg.risk.growth_target_pct == 0.68
    sleeves = {t.symbol: t.sleeve for t in cfg.tickers}
    assert sleeves["NVDA"] == "growth"
    assert sleeves["JNJ"] == "defensive"
    assert sum(1 for s in sleeves.values() if s == "growth") == 15
    assert sum(1 for s in sleeves.values() if s == "defensive") == 7


def test_duplicate_symbols_rejected(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        yaml.dump(
            {
                "tickers": [
                    {"symbol": "AAPL"},
                    {"symbol": "aapl"},
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_tickers_config(path)


def test_empty_tickers_rejected():
    with pytest.raises(ValidationError):
        TickersConfig.model_validate({"tickers": []})


def test_symbol_normalized():
    cfg = TickersConfig.model_validate({"tickers": [{"symbol": " aapl "}]})
    assert cfg.symbols() == ["AAPL"]


def test_resolve_cache_dir_relative():
    root = project_root()
    resolved = resolve_cache_dir(Path("data/cache"), root)
    assert resolved == (root / "data" / "cache").resolve()


def test_missing_config_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_tickers_config(tmp_path / "missing.yaml")
