# Social module (X / FinTwit research)

Optional archive + desk context for neotrade. **Does not train LightGBM.**  
Bare `neotrade backtest` promote never depends on social data.

## Why

Collect and grade posts **now** so you have point-in-time history later.  
Train/ablate only after months of cache + IC study (Phase C — not shipped).

## Setup

1. X API bearer token in `.env` (never commit):

   ```bash
   X_BEARER_TOKEN=...
   # or TWITTER_BEARER_TOKEN=...
   ```

2. Curated handles: `config/social_accounts.yaml` (edit freely).

3. Desk surfacing (default **off**):

   ```bash
   export NEOTRADE_SOCIAL_ENABLED=1
   ```

4. Optional Ollama grading is **not** used yet (`NEOTRADE_SOCIAL_LLM` reserved; lexicon only).

## Commands

```bash
source .venv/bin/activate

# Pull cashtags for universe + sample curated accounts → data/social/posts.jsonl
neotrade social fetch
neotrade social fetch --no-accounts --symbols AAPL,NVDA --max-results 10
neotrade social fetch --max-accounts 5

neotrade social status
neotrade social summary
neotrade social summary --hours 24 --json
```

Cache lives under `data/social/` (gitignored via `/data/`).

## Desk

When `NEOTRADE_SOCIAL_ENABLED=1` and cache is fresh (≤48h), `neotrade desk` /
`gather_desk_packet` adds a **SOCIAL** block (capped lines, journal only).

## Policy

| Allowed | Forbidden |
|---------|-----------|
| JSONL archive of posts + lexicon scores | Tweet text in `neotrade train` |
| Desk / advise journal context | Execute from social signals |
| Future opt-in numeric features after ablation | Bare promote depending on social |

See `neotrade.social.policy.POLICY_SUMMARY`.

## Cadence (recommended for later training option)

- Daily (RTH-adjacent): `neotrade social fetch`
- Weekly: `neotrade social status` (disk + errors)
- Monthly: offline IC vs forward returns (not promote)
- Train experiment only after ~60+ trading days coverage

## Phase C (not built)

Opt-in `FEATURE_GROUPS["social"]`, `eval --ablate`, multi-window BT — only if IC
justifies an experiment. Still never default bare promote.
