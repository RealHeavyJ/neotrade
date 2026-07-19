from pathlib import Path

import pandas as pd

from neotrade.data.cache import (
    cache_path,
    is_cache_fresh,
    load_cached_ohlcv,
    save_ohlcv,
)


def _sample_frame() -> pd.DataFrame:
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 100.0],
            "Close": [101.0, 102.0],
            "Volume": [1_000_000, 1_100_000],
        },
        index=idx,
    )


def test_cache_roundtrip(tmp_path: Path):
    path = cache_path(tmp_path, "aapl", "1d", "1y")
    assert path.name == "AAPL_1d_1y.csv"
    save_ohlcv(path, _sample_frame())
    loaded = load_cached_ohlcv(path)
    assert list(loaded.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(loaded) == 2
    assert is_cache_fresh(path, max_age_hours=24.0)


def test_stale_cache(tmp_path: Path, monkeypatch):
    path = tmp_path / "X_1d_1y.csv"
    save_ohlcv(path, _sample_frame())
    monkeypatch.setattr(
        "neotrade.data.cache.time.time",
        lambda: path.stat().st_mtime + 100_000,
    )
    assert not is_cache_fresh(path, max_age_hours=1.0)
