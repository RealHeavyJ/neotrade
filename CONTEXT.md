# Context - neotrade

## What
Local-first paper-trading decision support on MacBook Neo: LightGBM + Alpaca paper/MD + Ollama/LangGraph + Streamlit. **No cloud LLM at runtime.**

## Hardware
Apple MacBook Neo (A18 Pro, 8GB). Small local models only.

## Locked decisions
| Item | Choice |
|------|--------|
| Name / repo | neotrade · `~/dev/neotrade` |
| Signals | LightGBM → `models/signal.txt` |
| Agents | LangGraph · Ollama `llama3.2:3b` |
| UI | Streamlit `neotrade dashboard` |
| Broker | Alpaca **paper** only |
| Data | Alpaca MD REST (`iex`) + yfinance fallback |
| Universe | neotrade-core-22 (15 growth / 7 defensive sleeves) |
| Risk | 8% max name · 68/32 sleeves · execute needs `--confirm` |
| Session | **US RTH only** for execute (09:30–16:00 ET); no pre/after-hours trading |
| Monitoring | `neotrade monitor` poller (min 5s); quotes anytime free MD allows; execute RTH-only |

## Quality score (agents)
- Canonical: **`QUALITY_SCORE.md`** — overall **7.6/10**, floor **7.6**, target **8.5**
- Policy: code changes must **hold or raise** score; never regress below floor
- Rules for all agents: **`AGENTS.md`**
- Gap backlog to raise score: `TASKS.md` § senior-review gaps

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
2. Signal rigor (walk-forward, calibration, baselines) — P1
3. Structured logging + narrower error handling — P2
4. Advise learning policy (journal ≠ train) — P3
5. ~~Realtime REST monitor~~ **done** (`neotrade monitor`); optional WS later

Do not treat advise prose as ML labels. No default after-hours execute.

## Memory map (efficient resume)
| File | Use |
|------|-----|
| `QUALITY_SCORE.md` | **Score floor + non-regression (agents first)** |
| `AGENTS.md` | Mandatory agent rules |
| `DAILY_TODO.md` | Your daily ops checklist |
| `PROGRESS.md` top | Restart checkpoint |
| `TASKS.md` | Next coding priority + score-up backlog |
| `CONTEXT.md` | This file — decisions only |
| `TESTING.md` | Test inventory |
| `TOKEN_MANAGEMENT.md` | Context budget rules |
| `docs/dev-guide.md` | How to run subsystems |

## Next session one-liner
Ops → `DAILY_TODO.md` post-open. Code → P0 market-hours gate (raises score). Check `QUALITY_SCORE.md` first.

Last updated: 2026-07-19
