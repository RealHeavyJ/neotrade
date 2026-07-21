"""Rate-limited universe quote poller for agent/human monitoring.

Does **not** place orders. Execute remains RTH-gated in the broker layer.
Respects free Alpaca MD limits via a minimum poll interval (default 15s).
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from neotrade.broker.hours import SessionStatus, get_session_status
from neotrade.config import load_tickers_config
from neotrade.config.load import project_root
from neotrade.config.models import TickersConfig
from neotrade.data.quotes import QuoteSnapshot, fetch_universe_quotes
from neotrade.logging_config import get_logger

# Free-tier friendly default; override via NEOTRADE_MONITOR_INTERVAL or CLI
DEFAULT_INTERVAL_S = 15.0
MIN_INTERVAL_S = 5.0
log = get_logger("monitor")


@dataclass(frozen=True)
class MonitorConfig:
    """Poller settings.

    Attributes:
        interval_s: Seconds between polls (clamped to >= MIN_INTERVAL_S).
        move_pct: Absolute pct move vs prior tick to flag a symbol (e.g. 1.0 = 1%).
        prefer_alpaca: Use Alpaca MD when possible.
        fallback_cache: Fall back to cached closes if MD fails.
        log_path: Optional JSONL path for ticks (None = no file log).
    """

    interval_s: float = DEFAULT_INTERVAL_S
    move_pct: float = 1.0
    prefer_alpaca: bool = True
    fallback_cache: bool = True
    log_path: Path | None = None

    def clamped_interval(self) -> float:
        """Return interval not below :data:`MIN_INTERVAL_S`."""
        return max(MIN_INTERVAL_S, float(self.interval_s))


def default_monitor_config() -> MonitorConfig:
    """Build config from env defaults."""
    interval = float(os.environ.get("NEOTRADE_MONITOR_INTERVAL", str(DEFAULT_INTERVAL_S)))
    move = float(os.environ.get("NEOTRADE_MONITOR_MOVE_PCT", "1.0"))
    log_env = os.environ.get("NEOTRADE_MONITOR_LOG", "").strip()
    log_path = Path(log_env) if log_env else (project_root() / "data" / "learning" / "monitor.jsonl")
    return MonitorConfig(interval_s=interval, move_pct=move, log_path=log_path)


@dataclass
class MoveAlert:
    """Symbol that moved beyond the configured threshold since last tick."""

    symbol: str
    prev: float
    price: float
    pct: float

    def describe(self) -> str:
        sign = "+" if self.pct >= 0 else ""
        return f"{self.symbol} {sign}{self.pct:.2f}% ({self.prev:.2f}→{self.price:.2f})"


@dataclass
class MonitorTick:
    """One poll cycle result for agents/CLI/dashboard."""

    ts: str
    snapshot: QuoteSnapshot
    session: SessionStatus
    moves: list[MoveAlert] = field(default_factory=list)
    tick_index: int = 0

    def priced_count(self) -> int:
        return sum(1 for r in self.snapshot.rows if r.price is not None)

    def summary_line(self) -> str:
        sess = "RTH" if self.session.allow_execute else self.session.phase.value
        move_s = f" moves={len(self.moves)}" if self.moves else ""
        return (
            f"tick={self.tick_index} ts={self.ts} feed={self.snapshot.feed or 'n/a'} "
            f"priced={self.priced_count()}/{len(self.snapshot.rows)} "
            f"session={sess}{move_s}"
        )

    def to_log_dict(self) -> dict:
        """Compact dict for JSONL (no full bid/ask dump unless needed)."""
        return {
            "ts": self.ts,
            "tick_index": self.tick_index,
            "feed": self.snapshot.feed,
            "session": self.session.phase.value,
            "allow_execute": self.session.allow_execute,
            "priced": self.priced_count(),
            "n_symbols": len(self.snapshot.rows),
            "moves": [asdict(m) for m in self.moves],
            "errors": list(self.snapshot.errors),
            "prices": {
                r.symbol: r.price for r in self.snapshot.rows if r.price is not None
            },
        }


FetchFn = Callable[..., QuoteSnapshot]


class QuoteMonitor:
    """Poll universe quotes on an interval for monitoring only.

    Args:
        config: Poll settings.
        cfg: Optional tickers config (loaded if omitted).
        fetch_fn: Injected fetcher for tests (default :func:`fetch_universe_quotes`).
        sleep_fn: Injected sleep (default :func:`time.sleep`).
        session_fn: Injected session clock (default :func:`get_session_status`).
    """

    def __init__(
        self,
        config: MonitorConfig | None = None,
        *,
        cfg: TickersConfig | None = None,
        fetch_fn: FetchFn | None = None,
        sleep_fn: Callable[[float], None] | None = None,
        session_fn: Callable[[], SessionStatus] | None = None,
    ) -> None:
        self.config = config or default_monitor_config()
        self._tickers_cfg = cfg
        self._fetch = fetch_fn or fetch_universe_quotes
        self._sleep = sleep_fn or time.sleep
        self._session = session_fn or get_session_status
        self._prev_prices: dict[str, float] = {}
        self._tick_index = 0

    def poll_once(self) -> MonitorTick:
        """Fetch one snapshot, compute moves vs previous poll, optionally log."""
        tickers = self._tickers_cfg or load_tickers_config()
        snap = self._fetch(
            tickers,
            prefer_alpaca=self.config.prefer_alpaca,
            fallback_cache=self.config.fallback_cache,
        )
        session = self._session()
        moves = self._detect_moves(snap)
        self._tick_index += 1
        tick = MonitorTick(
            ts=datetime.now(timezone.utc).isoformat(),
            snapshot=snap,
            session=session,
            moves=moves,
            tick_index=self._tick_index,
        )
        self._prev_prices = {
            r.symbol: r.price for r in snap.rows if r.price is not None
        }
        self._append_log(tick)
        return tick

    def _detect_moves(self, snap: QuoteSnapshot) -> list[MoveAlert]:
        thr = abs(float(self.config.move_pct))
        if thr <= 0 or not self._prev_prices:
            return []
        alerts: list[MoveAlert] = []
        for row in snap.rows:
            if row.price is None:
                continue
            prev = self._prev_prices.get(row.symbol)
            if prev is None or prev == 0:
                continue
            pct = (row.price - prev) / prev * 100.0
            if abs(pct) >= thr:
                alerts.append(
                    MoveAlert(symbol=row.symbol, prev=prev, price=row.price, pct=pct)
                )
        alerts.sort(key=lambda a: abs(a.pct), reverse=True)
        return alerts

    def _append_log(self, tick: MonitorTick) -> None:
        path = self.config.log_path
        if path is None:
            return
        try:
            path = Path(path)
            if not path.is_absolute():
                path = project_root() / path
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(tick.to_log_dict()) + "\n")
        except OSError as exc:
            log.warning("monitor log write failed path=%s: %s", path, exc)

    def iter_ticks(
        self,
        *,
        max_ticks: int | None = None,
        stop_fn: Callable[[], bool] | None = None,
    ) -> Iterator[MonitorTick]:
        """Yield ticks forever (or until ``max_ticks`` / ``stop_fn``).

        Sleeps ``interval_s`` between polls (not before the first).
        """
        n = 0
        while True:
            if stop_fn is not None and stop_fn():
                break
            yield self.poll_once()
            n += 1
            if max_ticks is not None and n >= max_ticks:
                break
            self._sleep(self.config.clamped_interval())
