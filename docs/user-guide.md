# neotrade — user guide

Local paper-trading decision support on your Mac. **No cloud LLM** for agents.
**Paper only** — never live trading.

## Setup (once)

```bash
cd ~/dev/neotrade
source .venv/bin/activate
# first time only:
# python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
cp .env.example .env   # add Alpaca paper keys
brew services start ollama && ollama pull llama3.2:3b
```

Daily checklist: **`DAILY_TODO.md`**.

## What each piece does

| Piece | Role |
|--------|------|
| LightGBM signals | Scores tickers from price history (`train` / `signals` / `eval`) |
| Paper plan/execute | Risk-sized orders on **Alpaca paper**, **US RTH only** |
| Advise | Local Ollama agents — **opinion only** |
| Monitor | Polls quotes; **never** trades |
| Dashboard | UI over the same tools |

## Daily loop

```bash
source .venv/bin/activate
neotrade session          # is execute allowed?
neotrade quotes
neotrade account
neotrade signals
neotrade paper-plan
neotrade advise           # optional narrative
# neotrade paper-execute --confirm   # rare; RTH only
```

Or: `neotrade dashboard` → http://localhost:8501

## Desk (smarter agents)

```bash
neotrade eval && neotrade backtest   # refresh gates when possible
neotrade desk                        # morning/weekly brain
```

Four local agents (ops, quant, PM, critic) read **real** account/signals/plan/gates.
They tell you what to do next — they do **not** place orders. Follow `human_todo`.

Questions that improve judgment: `docs/IMPROVEMENT_QUESTIONS.md`.

## Advise learning policy (important)

1. Each `advise` run is **logged** to `data/learning/events.jsonl` as a journal.
2. You may **rate** advice 1–5 (CLI `--rating` or Dashboard → Advise → Save rating).
3. Ratings help **you** (and future prompt work) — they do **not** retrain LightGBM.
4. To update the signal model: `neotrade fetch` then `neotrade train` only.
5. Check quality with `neotrade eval` (classification) and `neotrade backtest` (portfolio P&amp;L gate).

```bash
neotrade advise --mock-llm --rating 4 --notes "clear and useful"
```

## Weekly

```bash
neotrade fetch --force && neotrade train && neotrade eval && neotrade backtest
neotrade bench && pytest -q
```

Promote a new model only if **eval** looks sane and **backtest** prints `gate=PASS`.

## Safety

- Execute needs `--confirm` **and** US regular hours (09:30–16:00 ET).
- No pre-market / after-hours trading by design.
- Never put live API URLs in `.env`.

## Troubleshooting

| Symptom | Try |
|---------|-----|
| `neotrade` not found | `source .venv/bin/activate` |
| LightGBM / libomp error | `brew reinstall libomp` |
| Ollama down | `brew services start ollama` |
| Execute blocked | `neotrade session` — wait for RTH |
| Advise error | Train model; fix ScoreResult bugs already patched — refresh dashboard |

More detail: `docs/dev-guide.md`.
