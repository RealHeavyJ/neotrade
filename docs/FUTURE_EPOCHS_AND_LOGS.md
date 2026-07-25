# Future eng: log scale + paper epochs (MacBook Neo)

**Status:** design backlog only — **adopted 2026-07-25** with expert feedback.  
**When:** after research week; **T8 snapshot/diff before T7**; T7 only when log pain is real.  
**Hardware:** MacBook Neo, Apple A18 Pro, **8 GB RAM**, 6 cores (2P+4E).  
**Constraint:** local-only, paper-only, no cloud LLM; never train LightGBM on advise/era prose.  
**Boss metric:** bare `neotrade backtest` promote — not a composite maturity vanity score.

---

## Why

1. **JSON logs grow** — `data/learning/` already has many stamped `backtest_*.json`, plus `events.jsonl`, `experiments.jsonl`, `monitor.jsonl`, desk/eval/bench. Monitor + weekly will accelerate growth on a small disk/RAM machine.
2. **Paper resets** — need clean-slate paper testing without losing history; compare “eras” of the book and the model.
3. **Model maturity** — improve signals from **measured diffs across epochs** (eval/BT/promote/fills), not agent narrative.

---

## T7 — Learning log architecture (Neo-efficient)

### Principles

| Do | Don’t |
|----|--------|
| Append-only writes | Rewrite giant JSON arrays |
| Stream / window queries | `pd.read_json(entire_file)` by default |
| Compress cold data | Keep unlimited stamped BT JSON hot |
| One “latest” pointer per kind | Duplicate full reports everywhere |
| Budget disk (e.g. 200–500 MB learning/) | Unbounded monitor JSONL |

### Recommended layout

```
data/learning/
  events.jsonl              # hot append (rotate daily or @ 10–50 MB)
  events/                   # rotated: events-2026-07-25.jsonl.zst
  experiments.jsonl         # small; optional same rotate policy
  fills.jsonl
  monitor.jsonl             # aggressive rotate / ring
  archive/2026/07/          # cold stamped backtest_*, eval_*, desk_*
  backtest_latest.json      # only hot snapshot
  eval_latest.json
  desk_latest.json
  slip_calibration.json
  store.duckdb              # optional analytics index (lazy-built)
```

### Stack pick for 8 GB Apple Silicon

**Preferred:** JSONL hot path + **DuckDB** (or SQLite) for analytics.

- DuckDB: zero server, columnar, reads JSON/Parquet/JSONL, great on ARM, low idle cost.
- Build/refresh views from rotated files on demand (`neotrade logs index`), not on every write.
- Alternative if deps must stay minimal: **SQLite** + gzipped JSONL only (no DuckDB).

Avoid: Postgres, Spark, Elasticsearch, loading full history into Streamlit.

### CLI sketch

```bash
neotrade logs stats          # sizes, line counts, oldest/newest
neotrade logs gc --keep-days 30 --budget-mb 300
neotrade logs query --kind backtest --since 7d   # via DuckDB/SQLite
```

### Implementation notes

- Writer API stays `append_entry(kind, payload)` — rotation inside `learning/log.py`.
- Stamped writers (`save_backtest_report`) write to `archive/…` and update `*_latest.json` only.
- Monitor: max file size or daily rotate; drop or sample ticks if needed.
- Tests: rotate threshold, gc dry-run, query doesn’t OOM on large fake JSONL.

---

## T8 — Paper epochs (reset + maturity diffs)

### Concept

An **epoch** is a closed interval of paper trading under a known model/config:

```
epoch_id: ep_20260725_a1b2
ts_start / ts_end
reason: "clean slate after promote PASS" | "weekly reset" | ...
snapshot:
  account: equity, cash, positions[], open_orders[]
  model: path, content hash, train metrics if known
  gates: eval_latest + backtest_latest summarize (promote, edges, ret, sharpe, maxDD)
  risk/defaults: top_n, rebalance_every, slip_bps effective
  fills: n, median slip if any
artifacts_copied: optional paths into data/epochs/<id>/
```

### CLI sketch

```bash
neotrade epoch snapshot --reason "pre-reset"
neotrade epoch reset-paper --confirm     # requires fresh snapshot; paper wipe/liquidate
neotrade epoch list
neotrade epoch show ep_…
neotrade epoch diff ep_old ep_new        # maturity + book deltas
```

### Reset safety

1. Always **snapshot first** (fail if snapshot incomplete).
2. Require **`--confirm`**; refuse outside documented paper endpoint.
3. Prefer: cancel orders → liquidate positions → verify flat (Alpaca paper API).
4. If broker wipe is UI-only, CLI prints checklist and verifies account flat before marking epoch closed.
5. Never touch live keys; `require_paper=True` unchanged.

### Diff / maturity (for model improvement)

`epoch diff` outputs **numeric** journal fields agents can use:

| Field | Use |
|-------|-----|
| equity_end Δ, maxDD | Book health across eras |
| promote pass/fail | Gate stability |
| eval edge_al / edge_mom | Signal quality trend |
| BT signal_ret, sharpe, windows_pass | Strategy maturity |
| fill_n, median_slip_bps | Microstructure readiness |
| model_hash changed? | Attribute Δ to model vs luck |

**Maturity score (example, tunable):** weighted blend of promote streak, eval edge trend, BT gate pass rate, drawdown discipline — stored on epoch close, **not** fed into LightGBM labels.

Desk/QUANT may read last N epoch diffs when proposing experiments. Humans still approve train/config changes.

### Clean-slate testing workflow

```text
epoch snapshot → reset-paper --confirm → weekly/train/eval/backtest
→ trade epoch → epoch snapshot (close) → epoch diff vs prior
→ experiment from diff → complete experiment with gate after
```

---

## Suggested build order (adopted)

1. **T8a** `epoch snapshot` + list/show (no reset)  
2. **T8b** `epoch diff` (numeric gates/book only) + desk can read last diff  
3. **T8c** `reset-paper --confirm` + verify flat  
4. **T7a** rotate/archive + `logs stats/gc` (when pain; prioritize monitor JSONL)  
5. **T7b** optional DuckDB + `logs query`  

Each step: CI green, score ≥ floor, prefer hold overall **10.0**.

---

## Out of scope

- Cloud object storage as required path  
- Multi-account OMS  
- Auto-execute after reset  
- Training on desk/advise text or epoch narrative fields  
