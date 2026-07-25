"""Alpaca Market Data WebSocket stream (IEX free tier by default).

Monitor-only: updates in-memory quotes; **never** submits orders.
Uses the ``websockets`` library (async) behind a small sync runner.

Protocol (v2 stocks):
    1. connect ``wss://stream.data.alpaca.markets/v2/{feed}``
    2. auth with API key/secret
    3. subscribe trades and/or quotes
    4. receive ``t`` (trade) / ``q`` (quote) messages
"""

from __future__ import annotations

import asyncio
import json
import os
import ssl
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from neotrade.broker.credentials import AlpacaCredentials, load_alpaca_credentials
from neotrade.data.alpaca_md import data_feed
from neotrade.logging_config import get_logger

log = get_logger("monitor.stream")

DEFAULT_WS_HOST = "wss://stream.data.alpaca.markets"
# Free/paper default feed path segment
DEFAULT_WS_FEED = "iex"
# Free IEX plans typically allow ~30 concurrent symbol subscriptions.
# Trades+quotes both count toward the limit on many plans.
DEFAULT_MAX_SYMBOLS = 30


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def stream_url(*, feed: str | None = None, host: str | None = None) -> str:
    """Build Alpaca stock data WebSocket URL."""
    host = (host or os.environ.get("ALPACA_DATA_WS") or DEFAULT_WS_HOST).rstrip("/")
    feed = (feed or os.environ.get("ALPACA_DATA_FEED") or data_feed() or DEFAULT_WS_FEED).lower()
    # sandbox/test: wss://stream.data.sandbox.alpaca.markets/v2/iex
    return f"{host}/v2/{feed}"


def max_stream_symbols() -> int:
    """Max symbols per WS subscribe (free-tier safe default)."""
    raw = (os.environ.get("NEOTRADE_STREAM_MAX_SYMBOLS") or str(DEFAULT_MAX_SYMBOLS)).strip()
    try:
        n = int(raw)
    except ValueError:
        n = DEFAULT_MAX_SYMBOLS
    return max(1, n)


def limit_symbols(
    symbols: Iterable[str],
    *,
    max_symbols: int | None = None,
    prefer: Iterable[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Return (kept, dropped) under free-tier symbol cap.

    Prefer list order is honored first, then remaining alphabetically.
    """
    cap = max_symbols if max_symbols is not None else max_stream_symbols()
    uniq = sorted({s.strip().upper() for s in symbols if s and str(s).strip()})
    if not uniq:
        return [], []
    preferred = [s.strip().upper() for s in (prefer or []) if s and str(s).strip()]
    ordered: list[str] = []
    for s in preferred:
        if s in uniq and s not in ordered:
            ordered.append(s)
    for s in uniq:
        if s not in ordered:
            ordered.append(s)
    if len(ordered) <= cap:
        return ordered, []
    return ordered[:cap], ordered[cap:]


@dataclass
class StreamQuote:
    """Latest trade/quote snapshot for one symbol from the stream."""

    symbol: str
    price: float | None = None
    bid: float | None = None
    ask: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None
    trade_size: float | None = None
    ts: str = ""
    source: str = "ws"

    @property
    def mid(self) -> float | None:
        if self.bid is not None and self.ask is not None and self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return self.price

    def display_price(self) -> float | None:
        return self.price if self.price is not None else self.mid

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "price": self.display_price(),
            "bid": self.bid,
            "ask": self.ask,
            "ts": self.ts,
            "source": self.source,
        }


@dataclass
class StreamState:
    """Thread-safe book of latest quotes from the WebSocket."""

    quotes: dict[str, StreamQuote] = field(default_factory=dict)
    message_count: int = 0
    trade_count: int = 0
    quote_count: int = 0
    last_error: str = ""
    connected: bool = False
    authenticated: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def upsert_trade(self, symbol: str, price: float, *, size: float | None, ts: str) -> StreamQuote:
        with self._lock:
            q = self.quotes.get(symbol) or StreamQuote(symbol=symbol)
            q.price = price
            q.trade_size = size
            q.ts = ts or q.ts
            q.source = "ws:trade"
            self.quotes[symbol] = q
            self.trade_count += 1
            self.message_count += 1
            return q

    def upsert_quote(
        self,
        symbol: str,
        *,
        bid: float | None,
        ask: float | None,
        bid_size: float | None,
        ask_size: float | None,
        ts: str,
    ) -> StreamQuote:
        with self._lock:
            q = self.quotes.get(symbol) or StreamQuote(symbol=symbol)
            if bid is not None:
                q.bid = bid
            if ask is not None:
                q.ask = ask
            if bid_size is not None:
                q.bid_size = bid_size
            if ask_size is not None:
                q.ask_size = ask_size
            if q.price is None and q.mid is not None:
                q.price = q.mid
            q.ts = ts or q.ts
            q.source = "ws:quote"
            self.quotes[symbol] = q
            self.quote_count += 1
            self.message_count += 1
            return q

    def snapshot(self) -> list[StreamQuote]:
        with self._lock:
            return sorted(self.quotes.values(), key=lambda x: x.symbol)

    def prices(self) -> dict[str, float]:
        with self._lock:
            out: dict[str, float] = {}
            for sym, q in self.quotes.items():
                px = q.display_price()
                if px is not None:
                    out[sym] = px
            return out


def _f(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def parse_stream_messages(
    payload: list[dict[str, Any]] | dict[str, Any],
    state: StreamState,
    *,
    on_update: Callable[[StreamQuote], None] | None = None,
) -> None:
    """Apply one or more Alpaca stream JSON objects to ``state``.

    Handles auth responses, errors, trades (``T``), and quotes (``Q``).
    """
    items = payload if isinstance(payload, list) else [payload]
    for msg in items:
        if not isinstance(msg, dict):
            continue
        msg_type = str(msg.get("T") or msg.get("t") or "")
        # control messages use "T": "success" | "error" | "subscription"
        if msg_type == "success":
            msg_text = str(msg.get("msg") or "")
            if "authenticated" in msg_text.lower():
                state.authenticated = True
            log.debug("ws success: %s", msg_text)
            continue
        if msg_type == "error":
            err = str(msg.get("msg") or msg.get("message") or msg)
            state.last_error = err
            log.warning("ws error: %s", err)
            continue
        if msg_type == "subscription":
            log.info("ws subscription ack trades=%s quotes=%s", msg.get("trades"), msg.get("quotes"))
            # empty ack after error often means subscribe rejected
            continue
        # data: trade
        if msg_type == "t":
            sym = str(msg.get("S") or "").upper()
            price = _f(msg.get("p"))
            if not sym or price is None:
                continue
            q = state.upsert_trade(
                sym,
                price,
                size=_f(msg.get("s")),
                ts=str(msg.get("t") or ""),
            )
            if on_update:
                on_update(q)
            continue
        # data: quote
        if msg_type == "q":
            sym = str(msg.get("S") or "").upper()
            if not sym:
                continue
            q = state.upsert_quote(
                sym,
                bid=_f(msg.get("bp")),
                ask=_f(msg.get("ap")),
                bid_size=_f(msg.get("bs")),
                ask_size=_f(msg.get("as")),
                ts=str(msg.get("t") or ""),
            )
            if on_update:
                on_update(q)
            continue


class QuoteStream:
    """Async Alpaca stock quote/trade stream with sync helpers.

    Args:
        symbols: Tickers to subscribe.
        credentials: Alpaca keys (defaults to env / .env paper keys).
        feed: ``iex`` (free) or ``sip`` (paid).
        subscribe_trades: Subscribe trade channel.
        subscribe_quotes: Subscribe quote channel.
        on_update: Optional callback per trade/quote update.
        url: Override full WebSocket URL (tests).
    """

    def __init__(
        self,
        symbols: Iterable[str],
        *,
        credentials: AlpacaCredentials | None = None,
        feed: str | None = None,
        subscribe_trades: bool = True,
        subscribe_quotes: bool = False,
        on_update: Callable[[StreamQuote], None] | None = None,
        url: str | None = None,
        max_messages: int | None = None,
        idle_timeout_s: float | None = None,
        max_symbols: int | None = None,
    ) -> None:
        kept, dropped = limit_symbols(symbols, max_symbols=max_symbols)
        self.symbols = kept
        self.dropped_symbols = dropped
        if not self.symbols:
            raise ValueError("symbols must be non-empty")
        self.credentials = credentials or load_alpaca_credentials(require_paper=True)
        self.feed = (feed or data_feed() or DEFAULT_WS_FEED).lower()
        # Default trades-only: free IEX symbol budget is tight; quotes optional.
        self.subscribe_trades = subscribe_trades
        self.subscribe_quotes = subscribe_quotes
        if not self.subscribe_trades and not self.subscribe_quotes:
            self.subscribe_trades = True
        self.on_update = on_update
        self.url = url or stream_url(feed=self.feed)
        self.max_messages = max_messages
        self.idle_timeout_s = idle_timeout_s
        self.state = StreamState()
        self._stop = asyncio.Event()
        if self.dropped_symbols:
            log.warning(
                "ws symbol cap=%s; streaming %s names, dropped %s: %s",
                max_symbols if max_symbols is not None else max_stream_symbols(),
                len(self.symbols),
                len(self.dropped_symbols),
                ",".join(self.dropped_symbols[:12])
                + ("..." if len(self.dropped_symbols) > 12 else ""),
            )

    def request_stop(self) -> None:
        """Signal the running loop to exit."""
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._stop.set)
        except RuntimeError:
            self._stop = asyncio.Event()
            self._stop.set()

    async def run(self) -> StreamState:
        """Connect, auth, subscribe, and process until stop/max/idle."""
        try:
            import websockets
            from websockets.exceptions import ConnectionClosed
        except ImportError as exc:
            raise RuntimeError(
                "websockets package required for neotrade stream "
                "(pip install websockets)"
            ) from exc

        self._stop = asyncio.Event()
        log.info(
            "ws connecting url=%s symbols=%s trades=%s quotes=%s",
            self.url,
            len(self.symbols),
            self.subscribe_trades,
            self.subscribe_quotes,
        )
        ssl_ctx = _ssl_context()
        try:
            async with websockets.connect(
                self.url,
                ssl=ssl_ctx,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5,
                max_size=2**22,
            ) as ws:
                self.state.connected = True
                # greeting
                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                parse_stream_messages(json.loads(raw), self.state, on_update=self.on_update)

                await ws.send(
                    json.dumps(
                        {
                            "action": "auth",
                            "key": self.credentials.api_key,
                            "secret": self.credentials.secret_key,
                        }
                    )
                )
                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                parse_stream_messages(json.loads(raw), self.state, on_update=self.on_update)
                if not self.state.authenticated and self.state.last_error:
                    raise RuntimeError(f"websocket auth failed: {self.state.last_error}")

                sub: dict[str, Any] = {"action": "subscribe"}
                if self.subscribe_trades:
                    sub["trades"] = self.symbols
                if self.subscribe_quotes:
                    sub["quotes"] = self.symbols
                await ws.send(json.dumps(sub))

                last_data = time.monotonic()
                while not self._stop.is_set():
                    if self.max_messages is not None and self.state.message_count >= self.max_messages:
                        break
                    # Fail fast on subscribe limit / hard errors (don't burn --seconds idle)
                    err_l = (self.state.last_error or "").lower()
                    if "symbol limit" in err_l or "not authorized" in err_l:
                        raise RuntimeError(
                            f"websocket subscribe failed: {self.state.last_error}. "
                            f"Free IEX caps concurrent symbols (often ~{DEFAULT_MAX_SYMBOLS}). "
                            "Try: neotrade stream --symbols NVDA,AMD,ARM -v "
                            "or trades-only (default). Quotes: add --quotes with fewer names."
                        )
                    timeout = 1.0
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    except TimeoutError:
                        if (
                            self.idle_timeout_s is not None
                            and time.monotonic() - last_data >= self.idle_timeout_s
                        ):
                            log.info("ws idle timeout after %.0fs", self.idle_timeout_s)
                            break
                        continue
                    except ConnectionClosed as exc:
                        self.state.last_error = str(exc)
                        log.warning("ws closed: %s", exc)
                        break
                    last_data = time.monotonic()
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    parse_stream_messages(payload, self.state, on_update=self.on_update)
        finally:
            self.state.connected = False
            log.info(
                "ws stopped messages=%s trades=%s quotes=%s symbols_seen=%s",
                self.state.message_count,
                self.state.trade_count,
                self.state.quote_count,
                len(self.state.quotes),
            )
        return self.state

    def run_forever(self) -> StreamState:
        """Blocking entry: ``asyncio.run(self.run())``."""
        return asyncio.run(self.run())


def run_stream_cli(
    symbols: list[str],
    *,
    seconds: float | None = 30.0,
    max_messages: int | None = None,
    verbose: bool = False,
    feed: str | None = None,
    subscribe_trades: bool = True,
    subscribe_quotes: bool = False,
    max_symbols: int | None = None,
) -> StreamState:
    """Run stream for ``seconds`` or until ``max_messages``, print updates.

    Used by ``neotrade stream``. Never places orders.
    Defaults to **trades only** and caps symbols for free IEX limits.
    """
    stop_at = None if seconds is None else time.monotonic() + max(1.0, float(seconds))

    def on_update(q: StreamQuote) -> None:
        if not verbose:
            return
        px = q.display_price()
        px_s = f"{px:.2f}" if px is not None else "—"
        print(f"  {q.symbol:<6} {px_s:>10}  {q.source}  {q.ts[:19]}", flush=True)

    stream = QuoteStream(
        symbols,
        feed=feed,
        subscribe_trades=subscribe_trades,
        subscribe_quotes=subscribe_quotes,
        on_update=on_update if verbose else None,
        max_messages=max_messages,
        idle_timeout_s=None,
        max_symbols=max_symbols,
    )

    async def _bounded() -> StreamState:
        task = asyncio.create_task(stream.run())
        try:
            while not task.done():
                if stop_at is not None and time.monotonic() >= stop_at:
                    stream._stop.set()
                    break
                await asyncio.sleep(0.25)
            return await asyncio.wait_for(task, timeout=5.0)
        except TimeoutError:
            stream._stop.set()
            try:
                return await task
            except Exception:  # noqa: BLE001
                return stream.state
        except asyncio.CancelledError:
            stream._stop.set()
            return await task
        except Exception:
            # propagate run() failures (e.g. symbol limit)
            if not task.done():
                stream._stop.set()
                try:
                    await task
                except Exception:  # noqa: BLE001, S110
                    pass
            raise

    channels = []
    if stream.subscribe_trades:
        channels.append("trades")
    if stream.subscribe_quotes:
        channels.append("quotes")
    print(
        f"stream start feed={stream.feed} symbols={len(stream.symbols)} "
        f"channels={'+'.join(channels) or 'trades'} "
        f"seconds={seconds} max_messages={max_messages} "
        f"(monitor only; execute never called)",
        flush=True,
    )
    if stream.dropped_symbols:
        print(
            f"note: free-tier cap — dropped {len(stream.dropped_symbols)} symbols: "
            f"{','.join(stream.dropped_symbols[:15])}"
            + ("..." if len(stream.dropped_symbols) > 15 else ""),
            flush=True,
        )
    print(f"url={stream.url}", flush=True)
    print(f"watching: {','.join(stream.symbols)}", flush=True)
    state = asyncio.run(_bounded())
    print(
        f"stream done messages={state.message_count} "
        f"trades={state.trade_count} quotes={state.quote_count} "
        f"symbols={len(state.quotes)} authenticated={state.authenticated}",
        flush=True,
    )
    if state.last_error:
        print(f"last_error={state.last_error}", flush=True)
    # summary table
    for q in state.snapshot():
        px = q.display_price()
        px_s = f"{px:.2f}" if px is not None else "—"
        bid_s = f"{q.bid:.2f}" if q.bid is not None else "—"
        ask_s = f"{q.ask:.2f}" if q.ask is not None else "—"
        print(f"{q.symbol:<8} {px_s:>10} bid={bid_s:>8} ask={ask_s:>8} {q.source}")
    if not state.snapshot():
        now = datetime.now(UTC).isoformat()
        print(
            f"note: no trade/quote ticks by {now} "
            "(outside RTH, quiet tape, or subscribe rejected — see last_error)",
            flush=True,
        )
    return state
