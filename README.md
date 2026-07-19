# neotrade

Local-first paper-trading decision-support app for MacBook Neo (A18 Pro, 8GB).

**Status**: v1 loop live (signals · Alpaca paper/MD · Ollama agents · dashboard).  
**You**: `DAILY_TODO.md` daily. **Dev**: `PROGRESS.md` / `TASKS.md` (next: market-hours gate).

## Quick Start

```bash
cd ~/dev/neotrade
python -m venv .venv
source .venv/bin/activate   # must source, not execute
pip install -e ".[dev]"
pytest
neotrade tickers
neotrade fetch              # OHLCV (Alpaca auto, yfinance fallback)
neotrade quotes             # latest Alpaca market data prices
neotrade train              # LightGBM -> models/signal.txt
neotrade signals            # score universe
# Paper (after copying .env.example -> .env with paper keys):
neotrade account
neotrade paper-plan
# neotrade paper-execute --confirm
# Agents (local Ollama — no cloud LLM):
# brew services start ollama && ollama pull llama3.2:3b
neotrade advise
# neotrade advise --mock-llm   # offline stub
neotrade bench                 # local Ollama + signal efficiency
neotrade dashboard             # Streamlit UI (http://localhost:8501)
```

Config: `config/tickers.yaml` (override with `NEOTRADE_TICKERS` or `--config`).  
Secrets: `.env` only (gitignored). See `docs/dev-guide.md`.

Local-only runtime; paper trading via Alpaca paper API; agents via Ollama.

Daily checklist: `DAILY_TODO.md`
