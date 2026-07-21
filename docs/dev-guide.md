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

Features (per bar): multi-horizon returns, vol/ATR, RSI, SMA/EMA/MACD, Bollinger,
volume z, gap, momentum/vol, trend strength, plus **cross-sectional ranks**.

Label default: **relative** — `fwd_ret` > same-day cross-sectional median
(stock-picking). Use `--label-mode absolute` for raw up/down.

```bash
neotrade train                 # relative + CS features → models/signal.txt
neotrade train --label-mode absolute
neotrade signals               # proba + buy/hold/sell (CS ranks on universe)
neotrade train --horizon 5 --rounds 160
```

Thresholds: buy ≥ 0.55, sell ≤ 0.45 (override on `signals`).

`models/` is gitignored. Re-train after feature upgrades.

### Signal evaluation (P1 rigor)

```bash
neotrade eval                 # walk-forward vs always-long + momentum (relative labels)
neotrade eval --absolute-label
neotrade eval --folds 4 --horizon 5 --rounds 100
```

- Expanding-window folds; train dates strictly before each test block.
- Baselines: always-predict-1; momentum via `cs_rank_ret_5` (relative mode).
- Calibration bins + Brier; leakage notes documented.
- Writes `data/learning/eval_latest.json` (not the production model).
- Exit code `2` if model fails to beat **both** baselines (honest signal).

### Portfolio backtest (model promotion)

```bash
neotrade backtest
neotrade backtest --cost-bps 5 --retrain-every 21 --train-days 120
```

Walk-forward portfolio simulation using **production** `build_trade_plan` risk rules:

- Decision at close *t*, fill at **next open** (or next close)
- One-way costs (`--cost-bps`)
- Retrain LightGBM every N days on past data only
- Baselines: equal-weight buy-hold, momentum top-N rebalance
- Metrics: total return, CAGR, maxDD, Sharpe, turnover
- **Promotion gate** (exit 0 pass / 2 fail): beat ≥1 baseline on return, maxDD ≤ 35%, Sharpe ≥ 0
- Writes `data/learning/backtest_latest.json`

Use before promoting a new `models/signal.txt`. Does not place broker orders.

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

### Market hours gate (RTH only)

```bash
neotrade session              # phase + allow_execute
neotrade account              # prints session banner
neotrade paper-plan           # warns outside RTH (still dry-runs)
neotrade paper-execute --confirm   # blocked outside 09:30–16:00 ET
```

- **Execute allowed:** US regular hours only (weekdays, not in holiday table).
- **No pre-market / after-hours** trading (by design).
- **Quotes / advise / signals** still work anytime (monitoring ≠ execute).
- Holidays: lightweight set in `broker/hours.py` (not full exchange calendar).

### Quote monitor (P4 — watch only)

```bash
neotrade monitor --once              # single poll
neotrade monitor --interval 15 -v    # loop; Ctrl+C to stop
neotrade monitor --max-ticks 10 --move-pct 1.5
```

- Polls Alpaca MD (or cache) on an interval (**min 5s**, default 15s).
- Flags symbols moving ≥ `--move-pct` vs prior tick.
- Optional JSONL: `data/learning/monitor.jsonl` (disable with `--no-log`).
- **Never executes** orders. Session banner shows RTH vs blocked.
- Env: `NEOTRADE_MONITOR_INTERVAL`, `NEOTRADE_MONITOR_MOVE_PCT`, `NEOTRADE_MONITOR_LOG`.

### WebSocket stream (optional realtime)

```bash
neotrade stream --seconds 30 -v                    # trades only, universe capped
neotrade stream --symbols NVDA,AMD,ARM,TSM -v      # recommended on free IEX
neotrade stream --quotes --symbols NVDA,AMD -v     # trades+quotes (fewer names)
neotrade stream --until-interrupt -v
```

- URL: `wss://stream.data.alpaca.markets/v2/iex` (override host via `ALPACA_DATA_WS`).
- Feed default `iex` (free/paper). `sip` needs a paid plan.
- **Free IEX symbol cap** (~30). Default: **trades only**, auto-cap via
  `NEOTRADE_STREAM_MAX_SYMBOLS` (default 30). Full 22-name trades+quotes often
  errors with `symbol limit exceeded`.
- **Monitor only** — never places orders; RTH execute gate unchanged.
- Outside RTH you may connect but receive few/no ticks.
- Dep: `websockets` (in project dependencies).
- Full universe prices anytime: `neotrade quotes` / `neotrade monitor` (REST).

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

## Logging (P2)

```bash
# default: INFO text on stderr
neotrade session

NEOTRADE_LOG_LEVEL=DEBUG neotrade quotes
NEOTRADE_LOG_JSON=1 neotrade account
NEOTRADE_LOG_FILE=data/learning/neotrade.log neotrade train
```

- Module loggers under ``neotrade.*`` via :func:`neotrade.logging_config.get_logger`.
- Broad ``except Exception`` narrowed on fetch/score/advise/dashboard paths.
- Silent ``except: pass`` on learning logs now ``log.warning``.

### Integration smoke (manual, not CI)

```bash
python scripts/smoke_integration.py
```

Checks session + quotes + account + signals (needs `.env` + model).

### Advise learning policy (P3)

```bash
neotrade advise --rating 4 --notes "useful"
# dashboard: Advise → Run → Save rating
```

- Policy module: `learning/policy.py` — journal only; **never** LightGBM labels.
- CLI and dashboard both call `record_advice_run`.
- User-facing: `docs/user-guide.md`.

## Tests & CI

```bash
pytest -q
ruff check src/neotrade tests
pytest -q --cov=neotrade --cov-report=term-missing
```

GitHub Actions (`.github/workflows/ci.yml`): matrix Python **3.11 / 3.12**, ruff, pytest-cov, Codecov upload (optional repo secret `CODECOV_TOKEN`).

Fetch tests mock the network; model tests use synthetic OHLCV; agents use MockLLM.