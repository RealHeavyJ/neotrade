# Questions worth asking (and features that matter)

This is a living checklist for making neotrade **smarter** — not busier.
Use it in weekly reviews and when driving the **desk** agents.

## What “Llama trains itself” really means (safe version)

| Can do (good) | Must not do |
|---------------|-------------|
| Recommend `neotrade train / eval / backtest` | Train LightGBM on agent prose or ratings |
| Propose experiments (top_n, blend, costs) | Invent gate PASS when `backtest_latest` says FAIL |
| Compare desk runs over time in `data/learning/` | Auto-execute without RTH + `--confirm` |
| Flag stale artifacts / missing weekly run | Override paper-only or live API |

**Loop:** desk → human approves experiment → train/eval/backtest → desk reads new gates → next experiment.

---

## Questions you may not know to ask

### Model & promotion
1. Did **stable_gate** pass (multi-window), or only full-sample?
2. Does the edge survive **cost stress** (10+ bps)?
3. Is last fold / last window weaker than earlier ones (regime shift)?
4. Are we beating **both** baselines, or only the easy one?
5. How many **trades** and what **turnover**? (High churn eats edge.)
6. What is calibration like — do 0.8 scores actually win ~80%?

### Portfolio construction
7. Ranked **top-N** vs current holdings: how many names would turn over?
8. Is cash drag intentional (regime risk-off) or a bug?
9. Single-name weight vs `max_position_pct` — any silent concentration?
10. Losers with large negative uPL — plan says hold or exit?
11. Growth/defensive sleeves: still meaningful under pure ranked mode?

### Data & microstructure
12. Are quotes **IEX** delayed/thin vs what we assume in BT (next-open fills)?
13. Did any symbol fail fetch (partial universe) and bias ranks?
14. Is cache stale (`max_age_hours`) while we think we’re live?
15. WS symbol limits — are we only “smart” on 4 names while book has 10?

### Process & agents
16. What did desk recommend **last three runs** — any flip-flopping?
17. Did quant’s EXPERIMENT get run, or are we ignoring the machine?
18. Is `promote_ok` from file timestamped today or weeks old?
19. Off RTH: did critic correctly block execute?
20. If I disappeared for a month, what single automated job would I want? (desk + no execute)

### Risk & psychology
21. What’s my max acceptable paper DD before I freeze trading?
22. Am I using desk to **justify** a trade I already wanted?
23. Would I take the same action if BT gate flipped to FAIL this morning?

---

## Features that improve “smarter than me” (roadmap)

| Feature | Why it helps | Status |
|---------|--------------|--------|
| Promotion gates (eval + multi-window BT) | Stops shipping lucky models | **Done** |
| Regime filter | Avoids one-size-fits-all risk | **Done** |
| Ranked top-N plan | Aligns book with scores | **Done** |
| **`neotrade desk` multi-agent** | Ops/quant/PM/critic on real packet | **Done** |
| **Experiment ledger** | Desk EXPERIMENT → before/after gates | **Done** |
| Scheduled desk script | `scripts/run_desk.sh` (no execute) | **Done** |
| Partial-fill aware plan | Matches broker working orders | **Done** |
| BT slip + 2y default (`defaults.py`) | Strict promote path without flags | **Done** |
| top_n=7 + rebal=14 under strict 2y BT | Bare promote PASS | **Done** |
| Full auto weekly: `neotrade weekly` | Cadence without babysitting | **Done (T1)** |
| Calibrate slip_bps from live paper fills | BT matches your fills | **Done (T2)** |
| Split main.py → cli/ | Maintainability | **Done (T4)** |

---

## How to use desk for improvement

```bash
# After weekly train:
neotrade eval && neotrade backtest
neotrade desk                 # or --mock-llm offline
# Read FINAL_ACTION, TRAIN_REC, EXPERIMENT, HUMAN_TODO
# Run only experiments that keep paper-only + gates honest
```

If EXPERIMENT says “try rebalance_every=7”:

```bash
neotrade desk                                    # opens ledger row automatically
# apply change, then:
neotrade train && neotrade eval && neotrade backtest
neotrade experiment complete --latest            # records pass/fail vs before
neotrade desk                                    # next recommendation
```

**That** is local-LLM-driven improvement — process control, not magic self-training.
