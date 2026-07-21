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
| Session hours | `test_hours.py` (RTH gate) |
| Paper-execute CLI gates | `test_paper_execute_cli.py` (confirm=2, RTH block=3, RTH ok) |
| Quote monitor | `test_monitor.py` (poll, moves, clamp, no-execute) |
| Agents | `test_agents.py` (incl. ScoreResult + gather context regressions) |
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
