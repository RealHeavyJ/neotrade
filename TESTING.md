# Testing - neotrade

## Run
```bash
source .venv/bin/activate
pytest -q
```
Last full run (2026-07-19): **35 passed**.

## Suites
| Area | Files |
|------|--------|
| Smoke | `test_smoke.py` |
| Config | `test_config.py` (22 tickers, sleeves, provider auto) |
| Cache / fetch | `test_cache.py`, `test_fetch.py` |
| Alpaca MD | `test_alpaca_md.py` |
| Signals | `test_features.py`, `test_model.py` |
| Broker / risk | `test_broker_plan.py`, `test_credentials.py` |
| Agents | `test_agents.py` |
| Bench / learning | `test_bench.py`, `test_learning.py` |
| Dashboard | manual: `neotrade dashboard` |

## Manual smoke
```bash
neotrade quotes && neotrade account && neotrade bench
```

## Env notes
- LightGBM needs libomp (installed/verified)  
- Live Alpaca/Ollama tests are CLI manual, not CI defaults  

Last updated: 2026-07-19
