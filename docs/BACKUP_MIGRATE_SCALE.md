# Backup, migrate, and scale (operator guide)

**Goals this supports:** learn · keep the loop alive · honest promote · paper edge —  
**not** “buy a bigger GPU and alpha appears.”

Related: `README.md` (short pointer) · `DAILY_TODO.md` (ops) · `docs/OPERATOR_SKILL.md` (your skill track) ·  
`docs/user-guide.md` · `AGENTS.md` (no live trading; advise ≠ train).

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

**Do not** back up only because equity had a green day. Back up **artifacts + gates**, not paper P&amp;L mood.

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

## 7. Scaling compute: honesty first

### 7.1 Project north star (unchanged on a 64GB box)

1. **Honest edge** — bare `backtest` + multi-window stable gate.  
2. **Paper discipline** — RTH, `--confirm`, desk ≠ execute.  
3. **Advise never trains LightGBM.**  
4. **One open experiment** at a time.  
5. **More compute is a tool**, not a promote bypass.

If stable_gate FAIL on Neo, the same code on a workstation will usually still FAIL until the **strategy/data** story changes.

### 7.2 LightGBM — where extra compute helps

| Lever | Effect | Risk / note |
|-------|--------|-------------|
| Faster train/BT iteration | More experiments per weekend | Don’t multi-open exps; still one knob |
| Slightly higher `rounds` / capacity | Only if `best_iteration` hits the cap | Early stop often stops early (e.g. best_iteration=10) — extra rounds do nothing |
| More `train_days` / longer `period` in BT | Different history | Can change gates; treat as experiment |
| More tickers in universe | Richer CS ranks | More noise, more data, more ops load |
| Feature research + `eval --ablate` | Find useful groups | Already dropped `vol` for a reason |
| Hyperparam search (grid/random) | Possible small gains | Easy to **overfit** windows; require stable_gate PASS to keep |
| GPU for LightGBM | Rarely the bottleneck here | Prefer CPU + better protocol |

**Accuracy/profit levers that beat “bigger machine” for this stack:**

- Label definition (relative vs absolute) + **horizon** aligned with hold/rebalance  
- Features with **no leakage**  
- Portfolio rules: `top_n`, `rebalance_every`, costs/slip  
- Multi-window honesty (fix worst window, don’t chase full-sample ret)  
- Fill calibration when `n≥20`  
- Fresh data (`fetch`) before weekly train  

### 7.3 Ollama / agents — where extra compute helps

| Lever | Effect | Risk / note |
|-------|--------|-------------|
| Larger local model (e.g. 7B–8B if RAM allows) | Better desk prose | Still **opinion only**; no promote |
| More context / longer desk packets | Richer critique | RAM/latency on 8GB is tight — 3B is intentional on Neo |
| Cloud LLM | Not default; project prefers local | Policy + privacy; don’t feed keys |
| More agents / longer chains | Diminishing returns | Busywork; critic already slows bad trades |

**Agents do not make LightGBM more accurate.** Rate advise for *your* learning; never pipe ratings into `train`.

### 7.4 Suggested use of a bigger machine (research plan)

Stay on Neo for **daily paper ops** if you want; use the big box for **batch research**:

```text
1. Restore same git SHA + promoted model as baseline
2. neotrade status  # baseline promote
3. ONE experiment (e.g. horizon or rebalance_every) via experiment ledger
4. train → eval → bare backtest
5. keep only if stable_gate PASS and you understand window table
6. copy winning models/ + backtest_latest.json back to Neo via secure tarball
7. neotrade experiment complete
```

### 7.5 What not to do with more power

- Train for hours with huge `rounds` while early stopping at tree 10  
- “Optimize” until one window looks good (curve-fit)  
- Auto-execute from desk because the LLM sounds confident  
- Live trading  
- Commit models/secrets “so CI has them”  

---

## 8. Learning track — what to study so models get better (you + system)

You don’t need a PhD. You need a **repeatable honesty loop**.

### 8.1 Skills to build (see also `docs/OPERATOR_SKILL.md`)

| Topic | Why it affects P&amp;L |
|-------|----------------------|
| Features vs labels vs horizon | Wrong question → wrong model |
| Train vs eval vs backtest | Promote is portfolio truth, not train accuracy |
| Full gate vs stable gate | Stops lucky full-sample stories |
| Baselines (eq / mom) | “Up 100%” is meaningless if mom did 120% |
| Rebalance vs retrain clocks | Avoid daily churn |
| Costs / slip / bps | Edge dies to friction |
| Experiment discipline | One change → measure → keep/revert |

### 8.2 Weekly research ritual (profitable process)

1. `neotrade weekly` (or fetch → train → eval → backtest).  
2. `neotrade status` — promote PASS/FAIL + ages.  
3. Read **worst window** edges, not only headline return.  
4. If FAIL: one hypothesis (write it down) — e.g. “W1 loses because ranks chase late momentum.”  
5. One experiment only → complete/abandon.  
6. Backup tarball if PASS.  
7. Paper: calendar rebalance (~14d), not daily desk clicks.

### 8.3 Tasks that improve accuracy (ordered by typical ROI)

| Priority | Task | Command / artifact |
|----------|------|--------------------|
| P0 | Fresh data | `neotrade fetch --force` |
| P0 | Honest promote path | bare `neotrade backtest` (no `--fast`) |
| P0 | Understand FAIL windows | BT printout + desk |
| P1 | Feature ablation | `neotrade eval --ablate` |
| P1 | Walk-forward ML grade | `neotrade eval` |
| P1 | Slip closer to reality | `neotrade fills` → `--apply` at n≥20 |
| P2 | Horizon ↔ rebalance alignment | experiment + BT |
| P2 | top_n / rebalance_every | one knob; ledger |
| P3 | Hyperparams (leaves, lr, depth) | only if overfit evidence |
| P3 | Larger LLM | desk quality only |
| Later | More universe names | data + CS design |

### 8.4 Fast vs accurate vs profitable

| Goal | Means |
|------|--------|
| **Fast** | Cache bars; don’t refetch every hour; early stopping; Neo-sized LLM; `--fast` **only** for smoke |
| **Accurate** (ML sense) | eval edges, calibration, no leakage, stable windows |
| **Profitable** (paper sense) | beat eq/mom after costs across windows + sane ops (low churn, RTH, intentional execute) |

A model can be “accurate” at 52% direction and still lose to momentum on the book.  
A book can be profitable in one year and **FAIL promote** on stability — trust the gate.

### 8.5 Open research questions (for you to explore)

- Why did W1-style periods lose to eq/mom — regime, feature set, or top_n churn?  
- Does horizon 5 still match how long winners persist in the universe?  
- After 20+ real paper fills, does calibrated slip change promote?  
- Is cash drag intentional or stuck plan?  
- Are desk recommendations correlated with good plan days — or noise? (journal ratings)

Use `docs/IMPROVEMENT_QUESTIONS.md` in weekly reviews.

---

## 9. Quick reference card

| I want to… | Do this |
|------------|---------|
| Save promoted model | Tarball `models/signal.txt*` + `data/learning/backtest_latest.json` after PASS |
| Save secrets | Password manager only |
| New PC same power | git clone → venv → `.env` → extract tarball → status |
| New PC more power | Same restore → use extra CPU for **one-at-a-time** BT/eval research |
| Make model “smarter” with GPU | Usually wrong lever; fix labels/features/gates first |
| Make agents smarter | Optional larger Ollama; still no train-on-advise |
| Trade the new promote | `signals` → `paper-plan` → rare RTH `--confirm` per your policy |

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
