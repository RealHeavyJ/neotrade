# Context - neotrade

## What
Local-first paper-trading decision support on MacBook Neo: LightGBM + Alpaca paper/MD + Ollama/LangGraph + Streamlit. **No cloud LLM at runtime.**

## Hardware
Apple MacBook Neo (A18 Pro, 8GB). Small local models only.

## Locked decisions
| Item | Choice |
|------|--------|
| Name / repo | neotrade · `~/dev/neotrade` |
| Signals | LightGBM relative labels + CS ranks → `models/signal.txt` |
| Model gate | `neotrade eval` + `neotrade backtest` before trusting retrain |
| Agents | LangGraph · Ollama `llama3.2:3b` |
| UI | Streamlit `neotrade dashboard` |
| Broker | Alpaca **paper** only |
| Data | Alpaca MD REST (`iex`) + yfinance fallback |
| Universe | neotrade-core-22 (15 growth / 7 defensive sleeves) |
| Risk | ranked top-5 · max name 18% · execute needs `--confirm` |
| Score blend | Regime-aware model/mom blend (default ~40/60) |
| Promote | `backtest` exit 0 = full_sample + multi-window stable gates |
| Session | **US RTH only** for execute (09:30–16:00 ET); no pre/after-hours trading |
| Monitoring | REST `monitor` + WS `stream` (IEX); quotes anytime free MD allows; execute RTH-only |

## Quality score (agents)
- Canonical: **`QUALITY_SCORE.md`** — overall **9.1/10**, floor **7.6**, next target **9.3**
- Policy: code changes must **hold or raise** score; never regress below floor
- Rules for all agents: **`AGENTS.md`**
- Gap backlog: ML edge (`eval`), optional WS — `TASKS.md`

## Layout (current)
```
src/neotrade/
  config/ data/ signals/ broker/ agents/
  dashboard/ perf/ learning/ main.py
config/tickers.yaml
QUALITY_SCORE.md AGENTS.md
DAILY_TODO.md PROGRESS.md TASKS.md CONTEXT.md
```

## Env (`.env` gitignored)
- Trading: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_PAPER=true`, `ALPACA_BASE_URL=https://paper-api.alpaca.markets`
- Data: `ALPACA_DATA_URL=https://data.alpaca.markets`, `ALPACA_DATA_FEED=iex`
- LLM: `OLLAMA_HOST`, `NEOTRADE_OLLAMA_MODEL=llama3.2:3b`

## Advise vs train
- **Advise** = human narrative (optional log). Does not tune LightGBM.  
- **Train** = only path that updates the signal model (from OHLCV labels).

## Gotchas
- `source .venv/bin/activate`  
- libomp already installed (reinstall only if LightGBM import breaks)  
- Open/unfilled orders ≠ positions (agents prompted accordingly)

## Open product questions
- Rebalance cadence  
- Default advise-only vs more automation  
- How aggressively to use learning logs (policy TBD)

## Quality plan
Canonical score: `QUALITY_SCORE.md` (**7.8**, floor **7.6**).
1. ~~Market-hours / session gate~~ **done** (RTH execute only)
2. ~~Signal rigor (walk-forward, calibration, baselines)~~ **done** (`neotrade eval`)
3. ~~Structured logging + narrower error handling~~ **done** (`logging_config`, smoke)
4. ~~Advise learning policy~~ **done** (`learning/policy.py`, user-guide)
5. ~~Realtime REST monitor~~ **done** (`neotrade monitor`); optional WS later

Do not treat advise prose as ML labels. No default after-hours execute.

## Memory map (efficient resume)
| File | Use |
|------|-----|
| `QUALITY_SCORE.md` | **Score floor + non-regression (agents first)** |
| `AGENTS.md` | Mandatory rules + **session close checklist** |
| `DAILY_TODO.md` | Your daily ops checklist |
| `PROGRESS.md` top | Restart checkpoint + close checklist reminder |
| `TASKS.md` | Next coding priority + score-up backlog |
| `CONTEXT.md` | This file — decisions only |
| `TESTING.md` | Test inventory |
| `TOKEN_MANAGEMENT.md` | Context budget rules |
| `docs/dev-guide.md` | How to run subsystems |
| `docs/user-guide.md` | Operator guide |

## Next session one-liner
Ops → `DAILY_TODO.md`. Code → backtest gate PASS work (or see `TASKS.md`). Close → `AGENTS.md` session checklist.

Last updated: 2026-07-19
