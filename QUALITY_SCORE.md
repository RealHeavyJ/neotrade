# neotrade — codebase quality score (canonical)

**All coding agents must read this before changing code.**  
Goal: every change **holds or raises** the score; **never regress**.

---

## Current score

| Field | Value |
|-------|--------|
| **Overall** | **8.0 / 10** |
| **Floor (do not go below)** | **7.6** |
| **Target (next milestone)** | **8.5** |
| **Rated** | 2026-07-20 (P4 monitor) |
| **Rater** | Senior review + P0/P4 uplifts |
| **Tests at rating** | 53+ baseline; monitor tests added |

### Dimension scores

| Dimension | Score | Notes |
|-----------|------:|-------|
| Architecture / modularity | 8.0 | Clear packages; advise ≠ train |
| Safety / ops | **8.8** | Paper-only, `--confirm`, sleeves, RTH execute gate |
| Correctness / tests | **7.8** | Hours + execute CLI + monitor unit tests |
| Code quality | 7.5 | Post-cleanup; `main.py` still large |
| Docs / self-describing APIs | 7.5 | Google-style on core public APIs |
| ML rigor | 5.5 | Baseline model; weak edge proof |
| Observability | **6.4** | Bench + learning JSONL + **monitor JSONL** |
| Scalability / realtime | **6.8** | REST poller + move alerts; WS still open |

**Weighted overall ≈ 8.0** — v1 + RTH gate + quote monitor; ML rigor still the main gap to 8.5.

---

## Non-regression policy (mandatory for agents)

1. **Floor:** After any code change, overall score must be **≥ 7.6**. Prefer **≥ previous overall**.
2. **No silent trade-downs:** Do not lower any dimension by **≥ 0.3** unless a higher-priority dimension rises enough that **overall still ≥ floor**, and the trade-off is documented in the score log below.
3. **Before coding:** Skim this file + `TASKS.md` P0–P4 gaps. Prefer work that closes a gap (raises score).
4. **After coding:**  
   - Run `pytest -q` (must pass; do not reduce coverage without replacement).  
   - Run `ruff check src/neotrade tests` if available.  
   - If the change is structural/quality-relevant, update **Score log** and adjust dimensions/overall **honestly** (no vanity inflation).
5. **Forbidden regressions (automatic fail):**  
   - Live trading endpoints / removing paper guard  
   - Execute without `--confirm`  
   - Feeding advise prose into LightGBM training  
   - Cloud LLM required for runtime agents  
   - Secrets committed  
   - Deleting tests to “make green”  
   - Broadening bare `except:` that swallows errors without logging
6. **Allowed temporary dips:** None for **overall**. Dimension reshuffles only if overall holds and rationale is logged.

---

## What raises the score (priority)

See `TASKS.md` → “Plan: close senior-review gaps”:

| Pri | Work | Dimensions lifted |
|-----|------|-------------------|
| P0 | Market-hours gate | Safety, ops, scalability |
| P1 | Walk-forward / calibration / baselines | ML rigor, correctness |
| P2 | Structured logging; narrower excepts | Observability, code quality |
| P3 | Advise learning policy + dashboard parity | Product completeness / docs |
| P4 | WS quotes; order lifecycle | Scalability / realtime |

Cosmetic refactors that do not close a gap should still **not** lower any dimension.

---

## Score log

| Date | Overall | Δ | Notes |
|------|--------:|---|-------|
| 2026-07-19 | 7.6 | — | Baseline after v1 + review cleanup |
| 2026-07-20 | 7.8 | +0.2 | P0 US RTH execute gate; no after-hours; session CLI/UI |
| 2026-07-20 | 8.0 | +0.2 | P4 quote monitor poller (watch only; min interval; move alerts) |
| | | | *Agents: append a row when overall or any dimension changes* |

### How to update a dimension

```text
1. Edit the dimension table above.
2. Recompute overall (honest judgment; keep one decimal).
3. Append score log row with Δ and 1-line why.
4. If overall < 7.6 → revert or fix before finishing the session.
```

---

## Related

- Gap backlog: `TASKS.md`  
- Decisions: `CONTEXT.md`  
- Agent rules: `AGENTS.md`  
- Session checkpoint: `PROGRESS.md`

Last updated: 2026-07-19
