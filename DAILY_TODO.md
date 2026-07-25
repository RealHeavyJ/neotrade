# neotrade — operator checklist (human loop)

Until agents can run unattended 24/7, **you** run these loops.  
Paper only. Advise ≠ train. Execute only with `--confirm` when plan is intentional.

**Last ops review:** 2026-07-25 (Sat) — session closed; eng research-ready  
**Model gate:** bare `backtest` **PASS** (top_n=7 rebal=14 · 3/3 windows)  
**Next RTH:** 2026-07-27 09:30 ET  
**Mon loop:** `status` → `desk` → one exp → train/eval/BT → `experiment complete`  
**Do not Mon:** T7/T8 eng plumbing (future only)

---

## How to use this file

1. **Daily** — every US market day you care about the book.  
2. **Weekly** — once per week (Sun eve or Fri after close).  
3. Update the **status log** at the bottom when you finish.  
4. Engineering → `TASKS.md`. Coding session end → `AGENTS.md` close checklist.  

```bash
cd ~/dev/neotrade
source .venv/bin/activate    # must source, not execute
```

---

## DAILY (human — until automation)

**When:** Mon–Fri, after **09:45 ET** and/or near **EOD**.  
**Time:** ~10–15 min full · ~3 min light.

### A. Session start

- [ ] `source .venv/bin/activate`
- [ ] Ollama if advising: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:11434/api/tags` → `200`
- [ ] Optional: `pytest -q` after pulls / env changes only

### B. Market data + book

- [ ] `neotrade quotes` — prices sane, feed=`iex`
- [ ] `neotrade account` — equity, cash, positions, open_orders
- [ ] If `open_orders > 0`: not inventory until filled
- [ ] If blocked / flat unexpectedly: check Alpaca paper UI

### C. Decision loop

| # | Action | Command |
|---|--------|---------|
| 1 | Bars if cache stale | `neotrade fetch` |
| 2 | Signals | `neotrade signals` |
| 3 | Dry-run plan | `neotrade paper-plan` |
| 4 | Desk / narrative | `neotrade desk` (preferred) or `advise` |
| 5 | Execute only if intentional + RTH + promote | `neotrade paper-execute --confirm` (logs fill slip) |
| 6 | Promote snapshot | `neotrade status` |
| 7 | Optional fill calib | `neotrade fills` · `--apply` when n≥20 |

**Rules:** advise-only most days · execute **RTH only** (`neotrade session`) · advise ≠ train.

### D. End of day (~2 min)

- [ ] `neotrade account`
- [ ] Status log line below
- [ ] No need to retrain daily

---

## WEEKLY (human — until automation)

**When:** once/week · **~20–40 min**

### Data + model

- [ ] **`neotrade weekly`** (preferred) — fetch→train→eval→backtest→desk; exit 0 = promote PASS  
  - or manual: `fetch --force` → `train` → `eval` → `backtest` → `desk`
- [ ] `neotrade signals` — sanity if not already via weekly
- [ ] `neotrade bench` — Ollama still OK
- [ ] Optional schedule: `scripts/com.neotrade.weekly.plist` / `./scripts/weekly_promote.sh`

### Book + risk

- [ ] `neotrade account` — growth vs defensive eyeball
- [ ] `neotrade paper-plan` — no surprise turnover
- [ ] Single-name ~≤8% equity
- [ ] Cancel stale weekend working orders in Alpaca UI

### Health

- [ ] `pytest -q` after pulls
- [ ] Still **paper** keys only
- [ ] Optional: rate advise / skim `data/learning/`

---

## NOT daily (eng owns)

| Item | You |
|------|-----|
| Unattended scheduler / 24/7 driver | Still manual daily/weekly |
| Backtest gate PASS strategy work | See `TASKS.md` |
| REST/WS monitor tools | Optional: `monitor` / `stream` |

---

## Standing rules

- Paper only — never live trading URL  
- `source .venv/bin/activate` (never execute)  
- Dashboard: `neotrade dashboard`  
- Quality floor for code: `QUALITY_SCORE.md`  

| Dep | Status |
|-----|--------|
| libomp / LightGBM | OK |
| Ollama + llama3.2:3b | OK when service up |
| `.env` paper + data | OK |
| Tests | **94 passed** |

---

## Status log

| Date | Equity | Cash | Pos | Open | Notes |
|------|--------|------|-----|------|--------|
| 2026-07-19 | 100,000 | 100,000 | 0 | 8 accepted | Pre-open weekend orders |
| 2026-07-20 AM | ~99,954 | ~20,208 | 10 | 0 | Fills OK |
| 2026-07-20 EOD | 100,297 | 20,208 | 10 | 0 | Day 1 live book |
| 2026-07-21 EOD | **101,744** | 20,208 | 10 | 0 | +1.4% vs 7/20 EOD; leaders MU/MRVL/AMD/ARM; lag CRWD |
| 2026-07-25 | **98,909** | 20,208 | 10 | 0 | Weekly: eval OK; BT was FAIL then **strategy fix → BT PASS** (+72% vs eq+39%/mom+44%). Ranked top-5 + mom blend. |
| | | | | | |

### Weekly model check — 2026-07-25

| Check | Result |
|-------|--------|
| `eval` | mean_acc ~0.52 · edge_al **+0.022** · OK |
| `backtest` (after fix) | signal **+71.9%** · eq **+39%** · mom **+44%** · maxDD 21.9% · sharpe 2.29 |
| Gate | **PASS** — ranked top-N + 40/60 model·mom blend |
| Action | Promote OK on this window; re-run BT after each weekly train |

### Latest book snapshot — 2026-07-25

equity≈$98,909 · cash≈$20,208 · 10 pos · 0 open · ACTIVE · weekend (execute blocked until Mon RTH)

---

## Copy-paste

**Daily**
```bash
cd ~/dev/neotrade && source .venv/bin/activate
neotrade session && neotrade quotes && neotrade account
neotrade signals && neotrade paper-plan
neotrade desk                 # preferred over advise alone
# neotrade paper-execute --confirm   # RTH only, rare, after desk
```

**Weekly**
```bash
cd ~/dev/neotrade && source .venv/bin/activate
neotrade fetch --force && neotrade train && neotrade eval && neotrade backtest
# bare backtest = production defaults (2y, slip, multi-window); do not use --fast for promote
neotrade signals && neotrade account && neotrade paper-plan
neotrade desk
neotrade bench && pytest -q && ./scripts/ci_local.sh
```

Last updated: 2026-07-25 (weekly complete; BT gate FAIL)
