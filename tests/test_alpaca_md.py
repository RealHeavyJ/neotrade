import inspect
import ssl
from unittest.mock import MagicMock, patch

from neotrade.config.models import Ticker, TickersConfig
from neotrade.data.alpaca_md import AlpacaMarketDataClient, _ssl_context
from neotrade.data.quotes import fetch_universe_quotes


def test_ssl_context_uses_certifi_when_available():
    """Regression: macOS python.org builds need certifi CA bundle."""
    ctx = _ssl_context()
    assert isinstance(ctx, ssl.SSLContext)
    # source must keep certifi path (CI restore once dropped this)
    src = inspect.getsource(AlpacaMarketDataClient._request)
    assert "context=" in src
    assert "_ssl_context" in src
    import neotrade.data.alpaca_md as mod

    mod_src = inspect.getsource(mod)
    assert "certifi" in mod_src


def test_request_passes_ssl_context_to_urlopen():
    """Unit guard: urlopen must receive SSL context (not bare default)."""
    client = AlpacaMarketDataClient.__new__(AlpacaMarketDataClient)
    client.data_url = "https://data.alpaca.markets"
    client.feed = "iex"
    client.credentials = MagicMock()
    client.credentials.headers.return_value = {
        "APCA-API-KEY-ID": "x",
        "APCA-API-SECRET-KEY": "y",
    }

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"ok": true}'

    with patch("neotrade.data.alpaca_md.urllib.request.urlopen", return_value=FakeResp()) as uo:
        out = client._request("/v2/stocks/trades/latest", {"symbols": "NVDA"})
    assert out == {"ok": True}
    assert uo.called
    kwargs = uo.call_args.kwargs
    assert "context" in kwargs
    assert isinstance(kwargs["context"], ssl.SSLContext)


def test_parse_latest_trades_via_request():
    client = AlpacaMarketDataClient.__new__(AlpacaMarketDataClient)
    client.data_url = "https://data.alpaca.markets"
    client.feed = "iex"
    client.credentials = MagicMock()
    client.credentials.headers.return_value = {}

    def fake_request(path, query=None):
        assert "trades/latest" in path
        return {
            "trades": {
                "NVDA": {"p": 120.5, "s": 10, "t": "2026-07-18T20:00:00Z", "x": "V"},
            }
        }

    client._request = fake_request  # type: ignore[method-assign]
    out = AlpacaMarketDataClient.get_latest_trades(client, ["NVDA"])
    assert out["NVDA"].price == 120.5


def test_bars_to_dataframe():
    client = AlpacaMarketDataClient.__new__(AlpacaMarketDataClient)
    client.data_url = "https://data.alpaca.markets"
    client.feed = "iex"
    client.credentials = MagicMock()

    def fake_request(path, query=None):
        return {
            "bars": [
                {
                    "t": "2026-07-17T04:00:00Z",
                    "o": 1.0,
                    "h": 2.0,
                    "l": 0.5,
                    "c": 1.5,
                    "v": 1000,
                }
            ],
            "next_page_token": None,
        }

    client._request = fake_request  # type: ignore[method-assign]
    df = AlpacaMarketDataClient.get_stock_bars(client, "AMD")
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 1
    assert float(df["Close"].iloc[0]) == 1.5


def test_fetch_universe_quotes_fallback(monkeypatch):
    cfg = TickersConfig(tickers=[Ticker(symbol="AAA", sleeve="growth")])

    class Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("no keys")

    monkeypatch.setattr("neotrade.data.quotes.AlpacaMarketDataClient", Boom)

    # empty cache path — still returns row with None price
    snap = fetch_universe_quotes(cfg, prefer_alpaca=True, fallback_cache=False)
    assert len(snap.rows) == 1
    assert snap.rows[0].symbol == "AAA"
