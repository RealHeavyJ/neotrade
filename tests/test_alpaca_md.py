from unittest.mock import MagicMock


from neotrade.data.alpaca_md import AlpacaMarketDataClient
from neotrade.data.quotes import fetch_universe_quotes
from neotrade.config.models import Ticker, TickersConfig


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
