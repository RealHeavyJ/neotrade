"""CSV cache helpers for OHLCV bars."""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def cache_path(cache_dir: Path, symbol: str, interval: str, period: str) -> Path:
    """Return canonical cache file path for one ticker."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    sym = symbol.strip().upper()
    return cache_dir / f"{sym}_{interval}_{period}.csv"


def is_cache_fresh(path: Path, *, max_age_hours: float) -> bool:
    """True when cache file exists and is newer than ``max_age_hours``."""
    if not path.is_file():
        return False
    age_s = max(0.0, time.time() - path.stat().st_mtime)
    return age_s <= float(max_age_hours) * 3600.0


def load_cached_ohlcv(path: Path) -> pd.DataFrame:
    """Load cached OHLCV CSV into a datetime-indexed frame."""
    frame = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
    for col in OHLCV_COLUMNS:
        if col not in frame.columns:
            raise ValueError(f"cache missing column {col}: {path}")
    frame = frame[OHLCV_COLUMNS].sort_index()
    return frame


def save_ohlcv(path: Path, frame: pd.DataFrame) -> None:
    """Write OHLCV frame to CSV using canonical columns."""
    out = frame.copy()
    out.index = pd.to_datetime(out.index)
    out = out[OHLCV_COLUMNS]
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index_label="Date")
