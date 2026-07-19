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

## Layout (current)
```
src/neotrade/
  config/ data/ signals/ broker/ agents/
  dashboard/ perf/ learning/ main.py
config/tickers.yaml
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

## Memory map (efficient resume)
| File | Use |
|------|-----|
| `DAILY_TODO.md` | Your daily ops checklist |
| `PROGRESS.md` top | Restart checkpoint |
| `TASKS.md` | Next coding priority |
| `CONTEXT.md` | This file — decisions only |
| `TESTING.md` | Test inventory |
| `TOKEN_MANAGEMENT.md` | Context budget rules |
| `docs/dev-guide.md` | How to run subsystems |

## Next session one-liner
Ops → `DAILY_TODO.md` post-open. Code → market-hours gate. Do not rebuild v1 stack.

Last updated: 2026-07-19
