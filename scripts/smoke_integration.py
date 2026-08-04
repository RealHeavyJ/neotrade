#!/usr/bin/env python3
"""Non-CI integration smoke: quotes + account + signals + session.

Run manually (needs network, .env, trained model, optional Ollama):

    source .venv/bin/activate
    python scripts/smoke_integration.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running without install
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from neotrade.broker import get_session_status  # noqa: E402
from neotrade.broker.alpaca import AlpacaAPIError, AlpacaPaperClient  # noqa: E402
from neotrade.config import load_tickers_config  # noqa: E402
from neotrade.config.load import project_root  # noqa: E402
from neotrade.data import fetch_universe_quotes, load_universe_ohlcv  # noqa: E402
from neotrade.logging_config import get_logger, setup_logging  # noqa: E402
from neotrade.signals import SignalModel, score_universe  # noqa: E402


def main() -> int:
    setup_logging()
    log = get_logger("smoke")
    errors = 0

    session = get_session_status()
    log.info("session %s", session.summary_line())

    try:
        snap = fetch_universe_quotes(prefer_alpaca=True, fallback_cache=True)
        priced = sum(1 for r in snap.rows if r.price is not None)
        log.info("quotes feed=%s priced=%s/%s", snap.feed, priced, len(snap.rows))
        if priced == 0:
            errors += 1
            log.error("quotes: no prices")
    except (RuntimeError, OSError, AlpacaAPIError) as exc:
        errors += 1
        log.error("quotes failed: %s", exc)

    try:
        client = AlpacaPaperClient()
        acct = client.get_account()
        pos = client.list_positions()
        log.info(
            "account equity=%.2f cash=%.2f positions=%s",
            acct.equity,
            acct.cash,
            len(pos),
        )
    except (RuntimeError, OSError, AlpacaAPIError) as exc:
        errors += 1
        log.error("account failed: %s", exc)

    model_path = project_root() / "models" / "signal.txt"
    try:
        if not model_path.is_file():
            raise FileNotFoundError(f"missing {model_path}")
        cfg = load_tickers_config()
        bars = load_universe_ohlcv(cfg, force_refresh=False)
        model = SignalModel.load(model_path)
        scored = score_universe(model, bars.frames)
        log.info("signals n=%s errors=%s", len(scored.rows), len(scored.errors))
        if not scored.rows:
            errors += 1
    except (FileNotFoundError, RuntimeError, OSError, ValueError) as exc:
        errors += 1
        log.error("signals failed: %s", exc)

    if errors:
        log.error("smoke FAILED errors=%s", errors)
        return 1
    log.info("smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
