# neotrade

Local-first paper-trading decision-support app for MacBook Neo (A18 Pro, 8GB).

**Status**: v1 loop live (signals · Alpaca paper/MD · Ollama agents · dashboard).  
**You**: `DAILY_TODO.md` daily. **Dev**: `PROGRESS.md` / `TASKS.md` (next: market-hours gate).

## Quick Start

### First-time setup (new machine or new venv)

```bash
cd ~/dev/neotrade
python -m venv .venv
source .venv/bin/activate   # must source, not execute
pip install -e ".[dev]"     # install package + deps into this venv
pytest -q
```

`pip install -e ".[dev]"` is **not** needed every day. Run it when:

- Creating the venv the first time
- On a new machine / after deleting `.venv`
- After `pyproject.toml` dependencies change
- If `neotrade` is missing from PATH or imports fail

### Daily use (venv already set up)

```bash
cd ~/dev/neotrade
source .venv/bin/activate   # must source, not execute
neotrade tickers
neotrade fetch              # OHLCV (Alpaca auto, yfinance fallback)
neotrade quotes             # latest Alpaca market data prices
neotrade monitor --once     # one poll; or --interval 15 (watch only)
neotrade stream --seconds 30 -v   # Alpaca IEX WebSocket (watch only)
neotrade train              # LightGBM -> models/signal.txt
neotrade eval               # walk-forward vs baselines (ML rigor)
neotrade backtest           # portfolio WF BT + promotion gate
neotrade signals            # score universe
# Paper (after copying .env.example -> .env with paper keys):
neotrade session              # US RTH? execute allowed?
neotrade account
neotrade paper-plan           # warns outside RTH
# neotrade paper-execute --confirm   # RTH only; blocked pre/after-hours
# Agents (local Ollama — no cloud LLM):
# brew services start ollama && ollama pull llama3.2:3b
neotrade advise
# neotrade advise --mock-llm   # offline stub
neotrade bench                 # local Ollama + signal efficiency
neotrade dashboard             # Streamlit UI (http://localhost:8501)
# python scripts/smoke_integration.py   # manual integration check
```

Config: `config/tickers.yaml` (override with `NEOTRADE_TICKERS` or `--config`).  
Secrets: `.env` only (gitignored). See `docs/dev-guide.md`.

Local-only runtime; paper trading via Alpaca paper API; agents via Ollama.

Daily checklist: `DAILY_TODO.md`  
User guide: `docs/user-guide.md`  
Dev memory: `PROGRESS.md` · `TASKS.md` · `CONTEXT.md`  
**Agents:** `AGENTS.md` (bootstrap + **session close checklist**) · `QUALITY_SCORE.md` (floor 7.6)

### Architecture (v1)

```
quotes/bars → features → LightGBM signals
                              ↓
                    risk plan (sleeves/caps)
                              ↓
              paper-plan / paper-execute (Alpaca paper)
                              ↓
              advise (local Ollama) · dashboard (Streamlit)
```

Advise is **narrative only** — it does not retrain LightGBM. Train only via `neotrade train`.
