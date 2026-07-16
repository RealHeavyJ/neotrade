# Testing - neotrade

## Approach
- Prefer automated unit/integration tests for core logic.
- Manual checks for Streamlit UI and live market-hours flows.
- Performance characterization on Neo (latency, memory) tracked here and in scripts.

## Test Suites
| Area | Status | Notes |
|------|--------|-------|
| Smoke / package version | Active | `tests/test_smoke.py` |
| Data pipeline | Not started | |
| LightGBM signals | Not started | |
| Multi-agent system | Not started | |
| Paper trading / risk rules | Not started | |
| Dashboard (manual) | Not started | |
| Neo performance | Not started | |

## How to Run
```bash
cd ~/dev/neotrade
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

## Known Failures / Flakes
- None yet.

Last updated: 2026-07-15
