# Dev guide — neotrade

## Layout

```
config/tickers.yaml
src/neotrade/
  config/      # Pydantic schema + YAML load
  data/        # cache, Alpaca MD, quotes, fetch
  signals/     # features, LightGBM, score
  broker/      # paper client, risk, trade plan
  agents/      # LangGraph + Ollama
  dashboard/   # Streamlit app
  perf/        # local bench
  learning/    # JSONL event log (not ML training)
  main.py      # CLI only
tests/
data/cache/    # gitignored OHLCV
models/        # gitignored signal.txt
```

Docstrings use **Google style** (Args/Returns/Raises) for IDE hover and
self-documenting tools. Prefer reading module/class docs over inline noise.

## Config

- Default path: `config/tickers.yaml`
- Override: `NEOTRADE_TICKERS=/path/to.yaml` or `neotrade tickers --config ...`
- Project root override: `NEOTRADE_ROOT` (tests / alternate installs)

## Data

```bash
neotrade fetch                    # provider=auto (Alpaca bars → yfinance fallback)
neotrade fetch --provider alpaca  # Alpaca only
neotrade fetch --force
neotrade quotes                   # latest trade/quote via Alpaca Market Data API
neotrade quotes --cache-only      # last close from cache
```

Cache files: `data/cache/{SYMBOL}_{interval}_{period}.csv` with columns
`Date,Open,High,Low,Close,Volume`.

**Live path:** Alpaca Market Data REST (`data.alpaca.markets`) with feed `iex` (default free/paper).  
**Fallback:** yfinance + on-disk cache. Same paper API keys authorize data.

## Signals (LightGBM)

Features (per bar): returns, volatility, RSI, SMA ratios, Bollinger %, volume z-score.

Label: binary — forward close return over `horizon` days > 0 (default 5).

```bash
neotrade train                 # models/signal.txt (+ .meta.json)
neotrade signals               # proba + buy/hold/sell per ticker
neotrade train --horizon 3 --rounds 80
```

Thresholds: buy ≥ 0.55, sell ≤ 0.45 (override on `signals`).

`models/` is gitignored.

## Alpaca paper

1. Copy `.env.example` → `.env` and paste **paper** keys only.
2. Confirm base URL is `https://paper-api.alpaca.markets` and `ALPACA_PAPER=true`.
3. Commands:

```bash
neotrade account              # equity, cash, positions
neotrade paper-plan           # dry-run intents from signals + risk
neotrade paper-execute --confirm   # submit market orders (paper only)
```

Risk defaults live under `risk:` in `config/tickers.yaml` (8% max name, 68/32 sleeves).
Client **refuses live** Alpaca URLs when `require_paper=True`.

## Agents (LangGraph + Ollama) — fully local

Success criterion: trading signals, paper account/plan, and multi-agent advice run
on this machine with **no cloud LLM**. Market data = yfinance cache + Alpaca paper API.

### One-time Ollama setup (macOS)
```bash
brew install ollama
brew services start ollama          # starts at login
ollama pull llama3.2:3b             # ~2GB; fits 8GB Neo
ollama list
curl -s http://127.0.0.1:11434/api/tags
```

### Run
```bash
source .venv/bin/activate
neotrade fetch && neotrade train    # if cache/model stale
neotrade account                    # Alpaca paper
neotrade paper-plan
neotrade advise                     # local Ollama agents
# neotrade advise --mock-llm        # offline stub only
```

Graph: signals (+ optional Alpaca account/plan) → Trading Expert → Performance Analyst.  
Env: `OLLAMA_HOST`, `NEOTRADE_OLLAMA_MODEL` (default `llama3.2:3b`), `NEOTRADE_OLLAMA_TEMP`.

## Dashboard

```bash
neotrade dashboard
# opens Streamlit: Overview | Signals | Account | Plan | Advise | Bench
```

## Local efficiency + continuous improvement

```bash
neotrade bench                 # Ollama latency + signal score timing → data/learning/
neotrade train                 # retrain LightGBM; logs metrics to learning events
neotrade advise                # logs advice snapshot for later review
```

**Complexity ladder (local models)**
| Task | Engine | Notes |
|------|--------|--------|
| Universe score | LightGBM | Fast; retrain on new bars |
| Risk plan | Rules | Deterministic sleeves/caps |
| Narrative advise | Ollama 3b | Heavier; bench after model change |
| UI | Streamlit | Thin client over same APIs |

Learning artifacts (gitignored under `data/`): `data/learning/events.jsonl`, `bench_*.json`.

## Tests

```bash
pytest -q
```

Fetch tests mock the network; model tests use synthetic OHLCV; agents use MockLLM.