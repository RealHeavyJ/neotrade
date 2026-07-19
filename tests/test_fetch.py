from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from neotrade.config.models import DataSettings, Ticker, TickersConfig
from neotrade.data.fetch import fetch_ohlcv, load_universe_ohlcv


def _frame() -> pd.DataFrame:
    idx = pd.to_datetime(["2024-06-03", "2024-06-04"])
    return pd.DataFrame(
        {
            "Open": [10.0, 11.0],
            "High": [12.0, 13.0],
            "Low": [9.0, 10.0],
            "Close": [11.0, 12.0],
            "Volume": [100, 110],
        },
        index=idx,
    )


def test_fetch_uses_cache_when_fresh(tmp_path: Path):
    from neotrade.data.cache import save_ohlcv, cache_path

    path = cache_path(tmp_path, "MSFT", "1d", "1y")
    save_ohlcv(path, _frame())
    with patch("neotrade.data.fetch.download_ohlcv") as download:
        out = fetch_ohlcv("MSFT", cache_dir=tmp_path, max_age_hours=24.0)
        download.assert_not_called()
    assert len(out) == 2


def test_fetch_downloads_when_missing(tmp_path: Path):
    with patch("neotrade.data.fetch.download_ohlcv", return_value=_frame()) as download:
        out = fetch_ohlcv("MSFT", cache_dir=tmp_path, force_refresh=True)
        download.assert_called_once()
    assert (tmp_path / "MSFT_1d_1y.csv").is_file()
    assert len(out) == 2


def test_load_universe_partial_errors(tmp_path: Path):
    cfg = TickersConfig(
        tickers=[Ticker(symbol="OK"), Ticker(symbol="BAD")],
        data=DataSettings(cache_dir=tmp_path, max_age_hours=24),
    )

    def fake_fetch(symbol: str, **kwargs):
        if symbol == "BAD":
            raise RuntimeError("boom")
        return _frame()

    with patch("neotrade.data.fetch.fetch_ohlcv", side_effect=fake_fetch):
        bars = load_universe_ohlcv(cfg, root=tmp_path)
    assert bars.symbols() == ["OK"]
    assert any("BAD" in e for e in bars.errors)


def test_load_universe_all_fail(tmp_path: Path):
    cfg = TickersConfig(
        tickers=[Ticker(symbol="BAD")],
        data=DataSettings(cache_dir=tmp_path),
    )
    with patch("neotrade.data.fetch.fetch_ohlcv", side_effect=RuntimeError("nope")):
        with pytest.raises(RuntimeError, match="failed to load"):
            load_universe_ohlcv(cfg, root=tmp_path)
