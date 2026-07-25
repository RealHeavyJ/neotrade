# neotrade

[![CI](https://github.com/RealHeavyJ/neotrade/actions/workflows/ci.yml/badge.svg)](https://github.com/RealHeavyJ/neotrade/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/RealHeavyJ/neotrade/branch/main/graph/badge.svg)](https://codecov.io/gh/RealHeavyJ/neotrade)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![pytest](https://img.shields.io/badge/tests-94%20passed-success?logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![coverage](https://img.shields.io/badge/coverage-68%25-yellow)](https://codecov.io/gh/RealHeavyJ/neotrade)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Quality](https://img.shields.io/badge/quality_score-9.2%2F10-brightgreen)](QUALITY_SCORE.md)
[![Paper only](https://img.shields.io/badge/trading-paper%20only-orange)](docs/user-guide.md)
[![Local LLM](https://img.shields.io/badge/LLM-Ollama%20local-purple)](docs/dev-guide.md)
[![RTH gate](https://img.shields.io/badge/execute-US%20RTH%20only-critical)](docs/user-guide.md)
[![License](https://img.shields.io/badge/license-proprietary-lightgrey)](README.md)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/RealHeavyJ/neotrade/pulls)

Local-first paper-trading decision-support app for MacBook Neo (A18 Pro, 8GB).

**Status**: v1 loop live (signals · Alpaca paper/MD · Ollama agents · dashboard · backtest gate).  
**You**: `DAILY_TODO.md` daily. **Dev**: `PROGRESS.md` / `TASKS.md` · score floor in `QUALITY_SCORE.md`.

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
neotrade stream --symbols NVDA,AMD,ARM,TSM -v   # IEX WebSocket (watch only)
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
neotrade desk                  # multi-agent desk (ops/quant/PM/critic)
# neotrade desk --mock-llm
neotrade bench                 # local Ollama + signal efficiency
neotrade dashboard             # Streamlit UI (http://localhost:8501)
# python scripts/smoke_integration.py   # manual integration check
```

Config: `config/tickers.yaml` (override with `NEOTRADE_TICKERS` or `--config`).  
Secrets: `.env` only (gitignored). See `docs/dev-guide.md`.

Local-only runtime; paper trading via Alpaca paper API; agents via Ollama.

Daily checklist: `DAILY_TODO.md`  
User guide: `docs/user-guide.md`  
Improvement questions: `docs/IMPROVEMENT_QUESTIONS.md`  
Dev memory: `PROGRESS.md` · `TASKS.md` · `CONTEXT.md`  
**Agents:** `AGENTS.md` · `QUALITY_SCORE.md` (floor 7.6) · desk = smarter process, not auto-trade

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

## Badges & CI

| Badge | Meaning |
|-------|---------|
| **CI** | GitHub Actions: install, ruff, pytest on Python 3.11 & 3.12 |
| **codecov** | Line coverage uploaded from CI (optional `CODECOV_TOKEN` secret) |
| **Python 3.11+** | Minimum supported runtime |
| **Quality** | Internal score from `QUALITY_SCORE.md` (agents must not regress) |
| **Paper only / RTH** | Safety posture: no live trading; execute only US regular hours |

```bash
# same checks as CI (local)
source .venv/bin/activate
ruff check src/neotrade tests
pytest -q --cov=neotrade --cov-report=term-missing
```
