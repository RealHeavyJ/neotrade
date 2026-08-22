# Operator skill track (human promote)

**Purpose:** Durable learning memory for the human operator across sessions.  
Agents: **read this file** when teaching, scoring, or planning walkthroughs.  
Update after meaningful teaching sessions (honest, like model promote — not flattery).

**Not** eng quality (`QUALITY_SCORE.md`). **Not** paper P&amp;L. This is *operator literacy*.

---

## How agents use this

1. On teaching / “where am I” / walkthrough requests → read this file first.  
2. Score with evidence from conversation + ops (commands run, questions asked, mistakes corrected).  
3. **Promote** only when gate criteria below are met (same honesty as BT stable_gate).  
4. Update **Current snapshot** + append **Score log** (short). Do not rewrite history.  
5. Prefer teaching gaps marked **weak** before advanced knobs or code experiments.

---

## Stages (career path)

| Stage | Name | Can do without hand-holding |
|-------|------|------------------------------|
| **A** | Operator | Daily/weekly loop; read account/EOD; RTH + `--confirm`; paper-only discipline |
| **B** | Model literacy | Explain label, features, horizon, train vs eval vs BT; read metrics without freezing |
| **C** | Research discipline | One-knob experiments; interpret window FAIL; keep/revert on stable_gate |
| **D** | Expert habits | Baselines first; distrust single metrics; most knobs do nothing after costs |

Sublevels: `A-` starting · `A` solid · `A+` ready for B material · same for B/C/D.

---

## Promote gates (human)

| Promote to | Must show (evidence) |
|------------|----------------------|
| **B** | Explains **label** + **features** in own words; knows train metrics ≠ promote; uses `eval`/`backtest` language once correctly |
| **C** | Runs or narrates one experiment protocol; correctly says why a window FAIL blocks promote; does not chase `--rounds` when `best_iteration` tiny |
| **D** | Repeatedly prioritizes baselines + multi-window honesty over hyperparam theater; teaches back simplifications |

**Demote / hold** if: confuses paper P&amp;L with model edge; wants live trading; trains on advise; multi-open reckless knobs.

---

## Current snapshot

| Field | Value |
|-------|--------|
| **As of** | 2026-08-22 EOD session |
| **Stage** | **B** (model literacy) |
| **Overall skill** | **7.5 / 10** (floor conceptual only — not eng score) |
| **★ NEXT SESSION START HERE** | Teach **horizon ↔ rebalance** (then learner restates in own words) |
| **Hold C until** | Narrates one-knob experiment + why window FAIL blocks promote without hints |
| **Last taught** | desk≠execute; ~14d calendar rebalance; retrain=refit; fill vs rebalance clocks; top_n=model scores |
| **Session end** | 2026-08-22 — user paused; no code changes required for restart |

### Dimension scores (0–10, honest)

| Dimension | Score | Notes |
|-----------|------:|-------|
| Paper ops loop | 8.0 | EOD + desk≠daily execute + ~14d calendar rebalance policy locked |
| Safety (paper, RTH, confirm) | 8.0 | Follows project rules in practice |
| Read BT / promote output | 8.0 | Full vs stable + W1 baselines clear in own words |
| Train knobs / early stop | 7.0 | Rounds vs early stop + best_iteration clear |
| **Label** | 8.0 | Teach + grade roles clear |
| **Features** | 7.5 | Data model uses to guess — solid |
| Horizon | 5.5 | Next lesson target |
| Eval vs train vs BT roles | 7.5 | BT = traded strategy + multi-window; train/eval distinct |
| Experiment discipline | 4.0 | Curious; not yet one-knob protocol habit |
| Trading metrics (Sharpe, DD, edge) | 5.5 | Edge/baselines used correctly; Sharpe/DD still light |

### Glossary mastery

| Term | Level | Evidence |
|------|-------|----------|
| early stopping | **strong** | 2026-08-22 |
| best_iteration | **strong** | 2026-08-22 |
| rounds vs early stop | **strong** | identical metrics explained + retained |
| horizon | **partial** | next lesson |
| label | **strong** | restated 2026-08-22 (+ relative) |
| features | **strong** | restated 2026-08-22 |
| relative vs absolute label | **partial** | relative restated; absolute not quizzed |
| equal-weight / mom baseline | **strong** | W1 both beat signal — restated |
| stable_gate / promote | **strong** | full can pass while windows fail — restated |
| top_n | **strong** | restated: model score rank, not realized past winners (≠ mom) |
| Sharpe / maxDD | **heard** | not quizzed |
| slippage / bps | **heard** | not quizzed |

---

## Score log

| Date | Overall | Stage | What changed |
|------|--------:|-------|----------------|
| 2026-08-22 | 6.2 | A+ | Track created. Ops + early-stop literacy up; label/features gated for B. |
| 2026-08-22 | 6.2 | A+ | Taught label+features+toy; scores unchanged until learner restates (no inflate). |
| 2026-08-22 | 6.8 | **B-** | Restate pass: features/label/relative/no-label-at-signal. Nuance note on label. |
| 2026-08-22 | 7.0 | B- | Nuance locked: train=patterns with answers; eval=grade unseen. BT still separate. |
| 2026-08-22 | 7.0 | B- | guide-daily/weekly queued. BT walkthrough taught; 3-check restatement → full B. |
| 2026-08-22 | 7.5 | **B** | 3-check pass: full vs windows; W1 eq+mom>sig; top_n≈rank book (score nuance noted). |
| 2026-08-22 | 7.5 | B | Ops: desk debrief only; execute rare/RTH/intentional; retrain=refit. Next=horizon↔rebalance. |
| 2026-08-22 | 7.5 | B | **Session end.** Restart: horizon↔rebalance lesson. Eng default unchanged (see PROGRESS/TASKS if coding). |

---

## Lesson queue

1. **Done:** Label + features → **B-**.  
2. **Done:** BT walkthrough + 3-check → **promoted B**.  
3. **Done (ops):** When to rebalance / desk vs execute.  
4. **Now:** Horizon ↔ rebalance (teach + own words).  
5. Later: one-knob experiment protocol; W1 case study → path to **C**.  
6. Later: Sharpe, drawdown, edge in trader English.  
7. **Between C and D (meta):** LLM skills literacy vs AGENTS.md vs desk; build only if real pain.  
8. **Later (after C):** **guide-daily** — debrief skill (account/EOD + teach); no auto-execute; CLI runs steps.  
9. **Later (after C):** **guide-weekly** — debrief after `neotrade weekly` (promote walk + skill track); does not replace weekly CLI.

---

## Session update checklist (agents)

After a teaching turn that moved understanding:

- [ ] Adjust dimension scores ± honestly  
- [ ] Glossary: weak → partial → strong only with evidence  
- [ ] Stage promote only if gates met  
- [ ] One line in Score log  
- [ ] Set **Next default lesson** to a single item  

Do not inflate scores for enthusiasm. Curiosity ≠ mastery.
