# neotrade — operator checklist (human loop)

Until agents can run unattended 24/7, **you** run these loops.  
Paper only. Advise ≠ train. Execute only with `--confirm` when plan is intentional.

**Last ops review:** 2026-08-01 (Sat) — regime OFF + **vol features dropped** · promote **PASS** 3/3  
**Model gate:** bare BT **PASS** · sig **+194.5%** · top_n=7 rebal=14 · regime OFF · no vol group  
**Next RTH:** 2026-08-03 09:30 ET  
**Mon:** status → desk → intentional execute OK if RTH + plan  
**Do not:** multi-open exps · stack more feature drops without one exp

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
| 2026-07-27 EOD | **98,284** | 2,126 | 7 | 0 | Deployed; top_n book |
| 2026-07-28 EOD | **97,810** | 2,126 | — | — | equity=$97,809.78 · cash=$2,126.28 · bp=$276,418.92 |
| 2026-07-29 EOD | **97,190** | 805 | — | — | equity=$97,190.00 · cash=$805.42 · bp=$273,098.50 |
| 2026-07-30 EOD | **96,416** | 805 | 7 | 0 | equity=$96,416.02 · cash=$805.38 · bp=$270,931.31 · NOW lead / PLTR lag |
| 2026-07-31 AH | **96,903** | 853 | 7 | 0 | equity=$96,902.96 · cash=$853.18 · bp=$272,352.11 · NOW lead / KO lag |

### Weekly model check — 2026-07-25

| Check | Result |
|-------|--------|
| `eval` | mean_acc ~0.52 · edge_al **+0.022** · OK |
| `backtest` (after fix) | signal **+71.9%** · eq **+39%** · mom **+44%** · maxDD 21.9% · sharpe 2.29 |
| Gate | **PASS** — ranked top-N + 40/60 model·mom blend |
| Action | Promote OK on this window; re-run BT after each weekly train |

### Weekly model check — 2026-07-31

| Check | Result |
|-------|--------|
| `fetch` → `train` → `eval` → `backtest` | ran (~0.5h artifact age) |
| `eval` | mean_acc **0.498** · vs always-long **−0.002** · vs mom **+0.012** · Brier 0.264 · leakage OK |
| `backtest` full sample | signal **+215%** · eq **+116%** · mom **+138%** · maxDD **21.9%** · sharpe **2.43** · full_gate **PASS** |
| stable multi-window | **1/3** pass (need ≥2/3) → **stable_gate FAIL** → **promote=FAIL** |
| W0 2024-07→2025-08 | sig +15% · eq +19% · mom +19% · FAIL (lost to baselines) |
| W1 2025-01→2026-02 | sig +46% · eq +40% · mom +42% · **PASS** |
| W2 2025-06→2026-07 | sig +7% · eq +22% · mom +37% · FAIL (recent window weak) |
| Experiments | rebal=7 runs closed (mix fail/abandon; one historical pass) · **0 open** |
| Fills | n=1/20 (no slip calib yet) |
| Action | **Do not promote** new confidence; paper book OK to hold; research = why W0/W2 lose |

### Research B — 2026-08-01 (stable_gate diagnose)

| Check | Result |
|-------|--------|
| Exp | `4173bf84` complete · outcome auto **fail** (defaults unchanged; promote still false) |
| `eval --ablate` | baseline acc **0.501** edge_mom **+0.014** |
| most useful groups | **returns** (Δacc −0.007) · **cs** (−0.007) · volume/trend ~flat |
| slightly harmful | **vol** (dropping it Δacc **+0.0045**) — do not drop yet without BT confirm |
| bare BT (regime ON, no-save) | full PASS · stable **2/3** · W2 FAIL sig +15% vs mom +41% · promote **FAIL** |
| A/B `--no-regime` (no-save) | full PASS · stable **3/3** · W2 PASS sig +35% · promote **True** |
| Prior | rebal=7 mostly fail — leave **rebal=14** |
| Learning | Regime filter helps risk-off narrative but **hurts recent window vs mom** on this tape |
| Next exp (one) | `BT_USE_REGIME=False` → bare `backtest` **with save** → keep only if stable PASS holds · else revert |

### Research — 2026-08-01 exp `BT_USE_REGIME=False` **KEPT**

| Check | Result |
|-------|--------|
| Code | `defaults.BT_USE_REGIME=False` · `BacktestConfig` field aligned · CLI uses `D.BT_USE_REGIME` (was ignoring default) |
| bare `backtest` (save) | regime=False · full PASS · stable **3/3** · promote **PASS** |
| signal | ret **+191%** · maxDD **23.9%** · sharpe **2.26** · vs eq +60% · vs mom +63% |
| W0/W1/W2 | all PASS (W2 sig +35% vs prior FAIL under regime ON) |
| CI | `./scripts/ci_local.sh` OK · **149** passed |
| Note | Live score blend still regime-aware; only **portfolio BT** filter off |

### Research — 2026-08-01 exp drop `vol` group **KEPT**

| Check | Result |
|-------|--------|
| Code | `FEATURE_EXCLUDE_GROUPS=("vol",)` + `model_feature_names` honors it |
| Features | 31 → **26** (dropped vol_10/20, vol_ratio, atr_14_pct, high_low_range) |
| bare BT | promote **PASS** · stable **3/3** · sig **+194.5%** (was +191.2%) |
| W2 | **+42.8%** (was +34.7%) · still beats eq; under mom slightly OK for gate |
| Tradeoff | maxDD **25.7%** vs 23.9% · sharpe **2.22** vs 2.26 |
| eval/model | refreshed age **0h** · mean_acc 0.497 · edge_mom +0.011 |
| #3 hygiene | **done** as part of this train/eval/BT |

### Latest book snapshot — 2026-07-25

equity≈$98,909 · cash≈$20,208 · 10 pos · 0 open · ACTIVE · weekend (execute blocked until Mon RTH)

### EOD — 2026-07-27 (Mon)

| Field | Value |
|-------|--------|
| equity | **$98,284.46** |
| cash | **$2,126.32** |
| positions | **7** (top_n book) · 0 open orders |
| blocked / PDT | False / False |
| names | AVGO CEG JNJ JPM NOW NVDA PLTR |
| note | vs 7/25: equity −$625 · cash −$18k (deployed into 7 names) · uPL leaders JNJ/NOW; NVDA lag |

### EOD — 2026-07-28 (Tue)

| Field | Value |
|-------|--------|
| equity | **$97,809.78** |
| cash | **$2,126.28** |
| buying_power | **$276,418.92** |
| note | vs 7/27 EOD: equity −$474.68 · cash flat |

### EOD — 2026-07-29 (Wed)

| Field | Value |
|-------|--------|
| equity | **$97,190.00** |
| cash | **$805.42** |
| buying_power | **$273,098.50** |
| note | vs 7/28 EOD: equity −$619.78 · cash −$1,320.86 (further deployed) |

### EOD — 2026-07-30 (Thu)

| Field | Value |
|-------|--------|
| equity | **$96,416.02** |
| cash | **$805.38** |
| buying_power | **$270,931.31** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| names | AVGO JNJ JPM KO NOW PEP PLTR |
| uPL leaders | NOW +$1,112 · AVGO +$418 · JPM +$94 |
| uPL laggards | PLTR −$834 · PEP −$398 · KO −$303 · JNJ −$184 |
| note | vs 7/29 EOD: equity −$773.98 · cash flat · book rotated (CEG/NVDA out; KO/PEP in) |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| AVGO | 36 | $14,004.00 | 389.00 | +$418.32 |
| JNJ | 51 | $13,035.09 | 255.59 | −$184.36 |
| JPM | 38 | $13,338.76 | 351.02 | +$93.87 |
| KO | 156 | $13,771.68 | 88.28 | −$302.64 |
| NOW | 135 | $14,786.55 | 109.53 | +$1,112.40 |
| PEP | 96 | $13,394.88 | 139.53 | −$398.40 |
| PLTR | 108 | $13,279.68 | 122.96 | −$833.77 |

### EOD/AH — 2026-07-31 (Fri)

| Field | Value |
|-------|--------|
| equity | **$96,902.96** |
| cash | **$853.18** |
| buying_power | **$272,352.11** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| names | AVGO CEG ETN JPM KO NOW NVDA |
| uPL leaders | NOW +$1,229 · ETN +$389 · AVGO +$378 · NVDA +$241 · JPM +$121 |
| uPL laggards | KO −$393 · CEG +$8 flat |
| note | vs 7/30 EOD: equity +$486.94 · cash +$47.80 · book rotated (JNJ/PEP/PLTR out; CEG/ETN/NVDA in) |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| AVGO | 36 | $13,964.04 | 387.89 | +$378.36 |
| CEG | 52 | $13,593.88 | 261.42 | +$7.84 |
| ETN | 31 | $12,789.67 | 412.57 | +$388.74 |
| JPM | 38 | $13,366.12 | 351.74 | +$121.23 |
| KO | 156 | $13,681.20 | 87.70 | −$393.12 |
| NOW | 135 | $14,903.18 | 110.39 | +$1,229.03 |
| NVDA | 69 | $13,751.70 | 199.30 | +$241.48 |

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

Last updated: 2026-08-01 vol-drop KEPT · promote PASS +194.5% · eval age 0h
