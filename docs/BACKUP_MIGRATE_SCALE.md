# Backup, migrate, and scale (operator guide)

Related: `README.md` · `DAILY_TODO.md` · `docs/OPERATOR_SKILL.md` · `docs/user-guide.md` · `AGENTS.md`.

---

## 1. Mental model: three layers

| Layer | Examples | How you keep it |
|-------|----------|-----------------|
| **A. Source code** | `src/`, `tests/`, docs, config templates | **Git** (push to private remote) |
| **B. Runtime artifacts** | `models/signal.txt*`, `data/learning/`, `data/cache/` | **Private backup** (not git) |
| **C. Secrets** | `.env` (Alpaca paper keys, etc.) | **Password manager / encrypted only** — never git, never chat logs, never public cloud “sync all” |

```text
git clone          →  code runs
restore B + C      →  same promote model + same broker identity
fetch (optional)   →  rebuild cache if you skipped it
```

`neotrade status` promote=PASS lives in **B** (`data/learning/backtest_latest.json` + model files).  
A clean `git status` after train/backtest is **normal** — those paths are gitignored on purpose.

---

## 2. What to back up

### Always (small, high value)

| Path | Why |
|------|-----|
| `models/signal.txt` | Live LightGBM booster used by `signals` / plan |
| `models/signal.txt.meta.json` | Features, horizon, label_mode, best_iteration |
| `data/learning/backtest_latest.json` | **Promote proof** (full + stable gates) |
| `data/learning/slip_calibration.json` | If present (after fills `--apply`) |
| `data/learning/events.jsonl` / desk JSON | Journal only (not for training) — optional but useful history |

### Optional (rebuildable, larger)

| Path | Why | If missing |
|------|-----|------------|
| `data/cache/` | OHLCV bars | `neotrade fetch` / `--force` |
| Older `data/learning/backtest_*.json` | History | Nice-to-have; not required for status |

### Never in the artifact tarball if the drive is shared / unencrypted

| Path | Do instead |
|------|------------|
| `.env` | 1Password / Bitwarden / encrypted disk image only |
| Live trading keys | **Don’t use** — paper only |
| Random screenshots of keys | Delete |

---

## 3. When to back up

| Trigger | Action |
|---------|--------|
| **After weekly promote PASS** (`neotrade status` → promote=PASS, ages fresh) | New artifact tarball (model + learning) |
| Before OS reinstall / laptop travel / hardware swap | Full artifact tarball + secrets check |
| Before risky experiments that might overwrite `models/signal.txt` | Snapshot `models/` + `backtest_latest.json` with a dated name |
| Monthly (habit) | Even if no promote change — cheap insurance |
| After changing `.env` | Update secrets vault only (not git) |

Priority backups: **artifacts + gate JSON** after promote changes; paper equity snapshots are optional ops logs (`DAILY_TODO`).

---

## 4. How to back up (local + secure)

### 4.1 Artifact archive (no secrets)

```bash
cd ~/dev/neotrade
source .venv/bin/activate
neotrade status   # optional: note promote=PASS and ages

STAMP=$(date -u +%Y%m%dT%H%MZ)
DEST="${HOME}/Backups/neotrade"
mkdir -p "$DEST"

# Minimum (recommended after promote)
tar -czf "$DEST/neotrade-model-$STAMP.tgz" \
  models/signal.txt \
  models/signal.txt.meta.json \
  data/learning/backtest_latest.json \
  data/learning/slip_calibration.json \
  2>/dev/null || true

# Fuller (model + all learning + cache)
tar -czf "$DEST/neotrade-artifacts-$STAMP.tgz" \
  models \
  data/learning \
  data/cache
```

Store `$DEST` on:

- External SSD you control, or  
- Encrypted disk image, or  
- **Private** cloud folder (not a public repo, not a Discord dump)

Verify:

```bash
tar -tzf "$DEST/neotrade-model-$STAMP.tgz" | head
```

### 4.2 Secrets (separate from tarball)

1. Keep the only copy of `.env` values in a **password manager** (or encrypted notes).  
2. On disk: `.env` stays local and gitignored.  
3. If you must file-backup `.env`:

```bash
# Example: encrypt with age or gpg — do NOT leave plaintext .env on USB
# age -r <recipient> -o ~/Backups/neotrade/env-$STAMP.age .env
```

4. Confirm paper endpoint only (Alpaca **paper** URL/keys). Never “backup” live keys into this project.

### 4.3 Code

```bash
git status
git push origin main   # when you have real commits; never force-add data/ or .env
```

---

## 5. Restore on the same machine (damage / accidental overwrite)

```bash
cd ~/dev/neotrade
source .venv/bin/activate

# Example restore from a known good tarball
tar -xzf ~/Backups/neotrade/neotrade-model-YYYYMMDDTHHMMZ.tgz -C .

neotrade status    # expect promote + ages consistent with backup
neotrade signals   # smoke
```

If only the model is wrong but cache is fine: restore `models/*` and `backtest_latest.json`.  
If everything is gone: restore tarball + `.env` from vault + `pip install -e ".[dev]"` if venv died.

---

## 6. Migrate to another machine

### 6.1 Same class machine (e.g. another 8GB Neo / similar Mac)

**Order:**

1. **Code:** `git clone <your-private-remote> neotrade && cd neotrade`  
2. **Python:** `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]" && pytest -q`  
3. **Secrets:** create `.env` from vault (paper keys only) — never copy from chat history  
4. **Artifacts:** extract backup tarball into repo root  
5. **Ollama (if desk/advise):** install Ollama, `ollama pull llama3.2:3b` (or your chosen tag)  
6. **Verify:**

```bash
neotrade status
neotrade account    # paper endpoint ok
neotrade signals
neotrade bench      # optional LLM + signal timing
```

7. If cache missing or stale: `neotrade fetch` then signals again.

You do **not** need more RAM to “activate” a promoted model. The booster is a small file.

### 6.2 Stronger machine (more CPU/RAM/GPU)

Same steps as 6.1. Then optionally:

| Resource | What it speeds up | What it does **not** auto-fix |
|----------|-------------------|--------------------------------|
| More CPU cores | LightGBM train, backtest windows, fetch | Bad labels, W1-style underperformance |
| More RAM (16–32GB+) | Larger Ollama models, bigger panels, less swap thrash | Promote honesty rules |
| GPU (Metal/CUDA) | Some LLM inference; **LightGBM is usually CPU** | Magical Sharpe |

**First week on a new box:** restore promoted artifacts and run ops. Only then run heavier research (more BT windows, ablations, larger LLM). Don’t retrain from scratch “because the machine is faster” unless you intend a **measured experiment**.

### 6.3 Checklist — “did migration work?”

- [ ] `pytest -q` green  
- [ ] `neotrade status` → promote matches backup expectation  
- [ ] `neotrade account` → ACTIVE paper (not live)  
- [ ] `neotrade signals` produces scores  
- [ ] Desk/advise only if Ollama up (`neotrade bench`)  
- [ ] No `.env` in git (`git status` clean of secrets)

---

## 7. Scaling compute

### 7.1 Invariants (any hardware)

1. Promote = bare `backtest` full gate ∧ stable multi-window gate.  
2. Execute = RTH + `--confirm`; desk/advise never place orders.  
3. Advise/desk logs are journal-only — not LightGBM labels/features.  
4. One open experiment row at a time (`neotrade experiment`).  

Same code + data on a faster machine reproduces the same gates; hardware changes runtime, not the metric definitions.

### 7.2 LightGBM — where extra compute helps

| Lever | Effect | Risk / note |
|-------|--------|-------------|
| Faster train/BT iteration | More experiments per weekend | Don’t multi-open exps; still one knob |
| Slightly higher `rounds` / capacity | Only if `best_iteration` hits the cap | Early stop often stops early (e.g. best_iteration=10) — extra rounds do nothing |
| More `train_days` / longer `period` in BT | Different history | Can change gates; treat as experiment |
| More tickers in universe | Richer CS ranks | More noise, more data, more ops load |
| Feature research + `eval --ablate` | Find useful groups | Already dropped `vol` for a reason |
| Hyperparam search (grid/random) | Possible small gains | Easy to **overfit** windows; require stable_gate PASS to keep |
| GPU for LightGBM | Optional; often not the bottleneck vs panel build + BT loop | Measure before depending on it |

**Primary model/portfolio levers (hardware-independent):**

- Label mode + horizon vs rebalance cadence  
- Feature set / leakage controls / `eval --ablate`  
- `top_n`, `rebalance_every`, cost_bps, slip (incl. fill calib n≥20)  
- Stable-window criteria and worst-window edges  
- Data freshness (`fetch`) before train/BT  

### 7.3 Ollama / agents

| Lever | Effect | Constraint |
|-------|--------|------------|
| Larger local weights (7B–8B+) | Desk/advise quality & latency | RAM; still non-executing |
| Longer packets / more tools | More context to agents | 8GB Neo: 3B default is deliberate |
| Cloud LLM | Out of default architecture | Local-first policy; no keys in prompts |
| Extra agent roles | More prose paths | No effect on `signal.txt` |

Ratings on advise are UX/journal metadata only.

### 7.4 Workstation research loop

```text
1. Same git SHA + restored promoted artifacts as baseline
2. neotrade status
3. One experiment ledger row (single knob)
4. train → eval → bare backtest
5. Keep iff stable_gate PASS; archive models/ + backtest_latest.json
6. neotrade experiment complete
7. Sync tarball back to daily driver if needed
```

### 7.5 Non-goals / hard limits

- `num_boost_round` ≫ `best_iteration` → no extra trees used  
- Single-window cherry-picks ≠ promote  
- Desk output ≠ order routing  
- Live trading disabled by design  
- `models/`, `data/`, `.env` stay out of git

---

## 8. Research surface (model + book)

### 8.1 Concept map → metrics

| Concept | Primary commands / fields |
|---------|---------------------------|
| Features / labels / horizon | `train`, meta, `eval` |
| Classification vs portfolio | `eval` vs `backtest` / promote |
| Full vs stable gate | `backtest_latest.json` `gate` / `stable_gate` |
| Baselines | `equal_weight`, `momentum` edges |
| Retrain vs rebalance vs fill | BT config: `retrain_every`, `rebalance_every`, `fill` |
| Friction | `cost_bps`, `slip_bps`, `fills` |
| Experiment ledger | `neotrade experiment` |

### 8.2 Weekly pipeline

1. `neotrade weekly` (or fetch → train → eval → backtest)  
2. `neotrade status`  
3. Inspect per-window edges + worst window  
4. On FAIL: one hypothesis → one ledger experiment  
5. On PASS: artifact tarball (§4)  
6. Paper rebalance on operator policy (~BT `rebalance_every`), not per desk line  

### 8.3 Work queue (typical ROI order)

| Pri | Work | Interface |
|-----|------|-----------|
| P0 | Data refresh | `neotrade fetch --force` |
| P0 | Promote path | bare `neotrade backtest` |
| P0 | Window diagnostics | BT output / JSON |
| P1 | Feature groups | `neotrade eval --ablate` |
| P1 | WF classification | `neotrade eval` |
| P1 | Slip calib | `fills` → `--apply` (n≥20) |
| P2 | Horizon ↔ rebalance | experiment + BT |
| P2 | `top_n` / `rebalance_every` | defaults + ledger |
| P3 | Tree capacity (leaves, lr, depth) | when train/valid disagree with OOS |
| P3 | LLM size | desk only |
| Later | Universe expansion | tickers + CS features |

### 8.4 Objective split

| Objective | Measured by |
|-----------|-------------|
| Throughput | train/BT wall time; cache hit rate; avoid `--fast` for promote |
| Predictive grade | `eval` edges, Brier/calibration, ablation deltas |
| Book grade | BT signal vs eq/mom, maxDD, Sharpe, stable_gate |

Classification edge can be weak while ranked book still passes (or the reverse). Promote keys off **book + windows**.

### 8.5 Open questions (repo history)

- Window failures vs mom/eq: regime filter, features, or turnover?  
- Horizon 5 vs empirical winner half-life in universe  
- Post n≥20 slip calib → gate sensitivity  
- Cash drag vs plan/risk sleeves  
- Desk text vs subsequent plan quality (journal only)

See `docs/IMPROVEMENT_QUESTIONS.md`.

---

## 9. Quick reference card

| I want to… | Do this |
|------------|---------|
| Save promoted model | Tarball `models/signal.txt*` + `data/learning/backtest_latest.json` after PASS |
| Save secrets | Password manager only |
| New PC same power | git clone → venv → `.env` → extract tarball → status |
| New PC more power | Same restore → use extra CPU for **one-at-a-time** BT/eval research |
| GPU / bigger box | Faster iteration; re-run gates on same protocol |
| Larger local LLM | Desk/advise only |
| Act on promote | `signals` → `paper-plan` → RTH `paper-execute --confirm` per policy |

---

## 10. Related files

| File | Role |
|------|------|
| `README.md` | Setup + short backup pointer |
| `DAILY_TODO.md` | Human daily/weekly ops |
| `docs/user-guide.md` | Operator commands |
| `docs/OPERATOR_SKILL.md` | Your learning stage / promote-as-human |
| `CONTEXT.md` | Locked product decisions |
| `QUALITY_SCORE.md` | Eng score floor (agents) |

Last updated: 2026-09-12
