# Feature request review (agent template)

Agents use this when the human proposes features or process changes.  
**Goal:** maximize long-term paper performance and honest gates — not feature count.

## Template (keep short)

### 1. Restate
One sentence: what they asked for.

### 2. Goal alignment
| Lens | Verdict |
|------|---------|
| Improves **promote honesty** / BT-eval rigor? | yes / no / weak |
| Improves **paper ops** decisions? | yes / no / weak |
| Fits **Neo 8GB local** + paper-only? | yes / no |
| Risk of **busywork** or score theater? | low / med / high |

### 3. What you may be missing
3–7 bullets: risks, confounds, simpler path, trading/ML traps, ops cost.

### 4. Alternatives
- **Do nothing / wait** if …
- **Smaller slice** if …
- **Different problem** if the real need is X

### 5. Recommendation
**now | later (track id) | reshape | never** + one-line why.

### 6. If later
Point at `TASKS.md` / design doc; do **not** start coding unless asked.

---

## Project north star (use when scoring ideas)

1. **Honest edge** — bare `backtest` + `eval` gates; no soft promote.  
2. **Paper discipline** — RTH, `--confirm`, open-order awareness.  
3. **Local & simple** — Ollama optional; Neo RAM/disk limits.  
4. **Learn from numbers** — epochs/fills/BT diffs; never train on prose.  
5. **One open experiment** — finish before starting another.  
6. **Score non-regression** — hold ≥ floor; prefer raise overall.

## Anti-patterns to call out

- Building infra before the log/epoch pain is real  
- Resetting paper without a snapshot/diff story  
- “Maturity score” that becomes a vanity metric  
- More agents/tools that don’t change promote or book outcomes  
- Optimizing for dashboard beauty over gate pass rate  
