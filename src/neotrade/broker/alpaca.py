"""Minimal Alpaca **Trading** API client (paper-first).

Uses stdlib ``urllib`` + certifi SSL. Refuses non-paper credentials when
constructed via :func:`~neotrade.broker.credentials.load_alpaca_credentials`.

Market data lives in :mod:`neotrade.data.alpaca_md` (separate host).
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from neotrade.broker.credentials import AlpacaCredentials, load_alpaca_credentials


class AlpacaAPIError(RuntimeError):
    """HTTP error from the Alpaca trading API."""

    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"Alpaca API {status}: {body}")
        self.status = status
        self.body = body


def _ssl_context() -> ssl.SSLContext:
    """Prefer certifi CA bundle (fixes macOS python.org CERTIFICATE_VERIFY_FAILED)."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


@dataclass(frozen=True)
class AccountSnapshot:
    """Normalized paper account fields used by risk planning."""

    equity: float
    cash: float
    buying_power: float
    portfolio_value: float
    status: str
    currency: str
    pattern_day_trader: bool
    trading_blocked: bool
    account_blocked: bool

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> AccountSnapshot:
        """Build from Alpaca ``GET /v2/account`` JSON."""
        return cls(
            equity=float(data.get("equity") or 0),
            cash=float(data.get("cash") or 0),
            buying_power=float(data.get("buying_power") or 0),
            portfolio_value=float(data.get("portfolio_value") or data.get("equity") or 0),
            status=str(data.get("status") or ""),
            currency=str(data.get("currency") or "USD"),
            pattern_day_trader=bool(data.get("pattern_day_trader")),
            trading_blocked=bool(data.get("trading_blocked")),
            account_blocked=bool(data.get("account_blocked")),
        )


@dataclass(frozen=True)
class Position:
    """Filled long/short position (not an open working order)."""

    symbol: str
    qty: float
    market_value: float
    current_price: float
    avg_entry_price: float
    unrealized_pl: float
    side: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Position:
        """Build from Alpaca position object."""
        return cls(
            symbol=str(data["symbol"]).upper(),
            qty=float(data.get("qty") or 0),
            market_value=float(data.get("market_value") or 0),
            current_price=float(data.get("current_price") or 0),
            avg_entry_price=float(data.get("avg_entry_price") or 0),
            unrealized_pl=float(data.get("unrealized_pl") or 0),
            side=str(data.get("side") or "long"),
        )


@dataclass(frozen=True)
class OrderResult:
    """Subset of Alpaca order fields returned after submit."""

    id: str
    symbol: str
    side: str
    qty: str
    type: str
    status: str
    submitted_at: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> OrderResult:
        """Build from Alpaca order JSON."""
        return cls(
            id=str(data.get("id") or ""),
            symbol=str(data.get("symbol") or "").upper(),
            side=str(data.get("side") or ""),
            qty=str(data.get("qty") or data.get("notional") or ""),
            type=str(data.get("type") or ""),
            status=str(data.get("status") or ""),
            submitted_at=str(data.get("submitted_at") or ""),
        )


class AlpacaPaperClient:
    """Thin wrapper over Alpaca paper trading REST endpoints.

    Args:
        credentials: Optional preloaded credentials. Defaults to env / ``.env``
            with ``require_paper=True``.
    """

    def __init__(self, credentials: AlpacaCredentials | None = None) -> None:
        self.credentials = credentials or load_alpaca_credentials(require_paper=True)
        if not self.credentials.paper:
            raise RuntimeError("AlpacaPaperClient requires paper credentials")

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        """JSON request helper. ``path`` must include the ``/v2/...`` prefix."""
        url = f"{self.credentials.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers=self.credentials.headers(),
            method=method.upper(),
        )
        try:
            with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise AlpacaAPIError(exc.code, err_body) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Alpaca network/SSL error: {exc.reason}") from exc

    def get_account(self) -> AccountSnapshot:
        """Return account equity, cash, and trading flags."""
        return AccountSnapshot.from_api(self._request("GET", "/v2/account"))

    def list_positions(self) -> list[Position]:
        """Return filled positions only (not working orders)."""
        data = self._request("GET", "/v2/positions") or []
        return [Position.from_api(row) for row in data]

    def list_orders(self, *, status: str = "open", limit: int = 50) -> list[dict[str, Any]]:
        """List orders by status (``open``, ``closed``, ``all``)."""
        data = self._request(
            "GET",
            "/v2/orders",
            query={"status": status, "limit": str(limit), "direction": "desc"},
        )
        return list(data or [])

    def submit_market_order(
        self,
        *,
        symbol: str,
        side: str,
        qty: float | None = None,
        notional: float | None = None,
        time_in_force: str = "day",
    ) -> OrderResult:
        """Submit a market order using either share qty or notional dollars.

        Exactly one of ``qty`` or ``notional`` must be provided.
        """
        if (qty is None) == (notional is None):
            raise ValueError("provide exactly one of qty or notional")
        side = side.lower()
        if side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        payload: dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": side,
            "type": "market",
            "time_in_force": time_in_force,
        }
        if qty is not None:
            # fractional qty supported on paper for many equities
            payload["qty"] = str(round(float(qty), 6))
        else:
            payload["notional"] = str(round(float(notional), 2))
        data = self._request("POST", "/v2/orders", body=payload)
        return OrderResult.from_api(data)

    def cancel_all_orders(self) -> None:
        """Cancel all open orders on the paper account."""
        self._request("DELETE", "/v2/orders")
