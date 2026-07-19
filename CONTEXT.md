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

## Quality plan (from 2026-07-19 senior review ~7.6/10)
What held the score back → tracked in `TASKS.md`:
1. Market-hours / session gate (ops safety)
2. Signal rigor (walk-forward, calibration, baselines)
3. Structured logging + narrower error handling
4. Advise learning policy (journal ≠ train)
5. Optional WS / richer order lifecycle

Do not treat advise prose as ML labels.

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
