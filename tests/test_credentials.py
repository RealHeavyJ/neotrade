import pytest

from neotrade.broker.credentials import (
    PAPER_BASE_URL,
    load_alpaca_credentials,
)


def test_strips_trailing_v2(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "PK")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "SK")
    monkeypatch.setenv("ALPACA_PAPER", "true")
    monkeypatch.setenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets/v2")
    c = load_alpaca_credentials(require_paper=True)
    assert c.base_url == PAPER_BASE_URL


def test_load_credentials_paper_ok(monkeypatch, tmp_path):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text(
        "ALPACA_API_KEY=PKTEST\nALPACA_SECRET_KEY=SECRET\nALPACA_PAPER=true\n"
        f"ALPACA_BASE_URL={PAPER_BASE_URL}\n",
        encoding="utf-8",
    )
    # load via env after dotenv path injection
    from neotrade.broker import credentials as cred_mod

    monkeypatch.setattr(cred_mod, "project_root", lambda: tmp_path)
    # clear and reload
    monkeypatch.setenv("ALPACA_API_KEY", "PKTEST")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "SECRET")
    monkeypatch.setenv("ALPACA_PAPER", "true")
    monkeypatch.setenv("ALPACA_BASE_URL", PAPER_BASE_URL)
    c = load_alpaca_credentials(require_paper=True)
    assert c.paper is True
    assert "paper-api" in c.base_url


def test_rejects_live_url(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "PK")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "SK")
    monkeypatch.setenv("ALPACA_PAPER", "false")
    monkeypatch.setenv("ALPACA_BASE_URL", "https://api.alpaca.markets")
    with pytest.raises(RuntimeError, match="refuses non-paper"):
        load_alpaca_credentials(require_paper=True)


def test_missing_keys(monkeypatch, tmp_path):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    monkeypatch.setenv("ALPACA_PAPER", "true")
    # Avoid loading the real project .env during unit tests
    from neotrade.broker import credentials as cred_mod

    monkeypatch.setattr(cred_mod, "project_root", lambda: tmp_path)
    with pytest.raises(RuntimeError, match="keys missing"):
        load_alpaca_credentials(require_paper=True)
