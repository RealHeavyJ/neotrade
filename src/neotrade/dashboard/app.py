"""Streamlit dashboard — local signals, paper account, agents."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from neotrade import __version__
from neotrade.agents import run_advise
from neotrade.agents.llm import MockLLM, OllamaClient, OllamaConfig
from neotrade.broker import (
    AlpacaPaperClient,
    build_trade_plan,
    default_risk_limits,
    get_session_status,
)
from neotrade.broker.alpaca import AlpacaAPIError
from neotrade.config import load_tickers_config
from neotrade.config.load import project_root
from neotrade.data import fetch_universe_quotes, load_universe_ohlcv, prices_for_plan
from neotrade.learning.policy import advice_events, policy_blurb, record_advice_run
from neotrade.logging_config import get_logger, setup_logging
from neotrade.signals import SignalModel, score_universe

DEFAULT_MODEL = project_root() / "models" / "signal.txt"
setup_logging()
log = get_logger("dashboard")


@st.cache_data(ttl=300, show_spinner=False)
def load_signals_cached(model_path: str, buy_th: float, sell_th: float) -> pd.DataFrame:
    cfg = load_tickers_config()
    path = Path(model_path)
    if not path.is_file():
        return pd.DataFrame()
    model = SignalModel.load(path)
    bars = load_universe_ohlcv(cfg, force_refresh=False, root=project_root())
    scored = score_universe(model, bars.frames, buy_threshold=buy_th, sell_threshold=sell_th)
    sleeves = {t.symbol: t.sleeve for t in cfg.tickers}
    return pd.DataFrame(
        [
            {
                "symbol": r.symbol,
                "proba": r.proba,
                "side": r.side,
                "as_of": r.as_of,
                "sleeve": sleeves.get(r.symbol, ""),
            }
            for r in scored.rows
        ]
    )


def page_overview() -> None:
    st.subheader("System status")
    session = get_session_status()
    col1, col2, col3, col4, col5 = st.columns(5)
    ollama = OllamaClient()
    ollama_ok = ollama.ping()
    model_ok = DEFAULT_MODEL.is_file()
    with col1:
        st.metric("LightGBM model", "ready" if model_ok else "missing")
    with col2:
        st.metric("Ollama", "up" if ollama_ok else "down")
    with col3:
        st.metric("LLM model", ollama.config.model if ollama_ok else "—")
    with col4:
        st.metric("Data", "Alpaca MD")
    with col5:
        st.metric("Session", session.label)
    st.caption(f"neotrade v{__version__} · local-only agents · paper Alpaca · RTH execute only")
    if session.allow_execute:
        st.success(session.summary_line())
    else:
        st.warning(session.summary_line())
        if session.next_rth_open_et is not None:
            st.caption(f"Next RTH open (ET): `{session.next_rth_open_et.isoformat()}`")

    cfg = load_tickers_config()
    st.write(f"**Universe:** {cfg.universe.name} ({len(cfg.tickers)} tickers)")
    g = sum(1 for t in cfg.tickers if t.sleeve == "growth")
    d = sum(1 for t in cfg.tickers if t.sleeve == "defensive")
    st.write(
        f"Sleeves: growth={g} · defensive={d} · risk max name={cfg.risk.max_position_pct:.0%} · "
        f"bars provider=`{cfg.data.provider}`"
    )
    st.caption(
        "Quotes/monitoring anytime free Alpaca MD allows. "
        "Paper **execute** only 09:30–16:00 ET weekdays (no pre/after-hours)."
    )


def page_quotes() -> None:
    st.subheader("Live quotes (Alpaca market data)")
    st.caption(
        "REST latest trade/quote · IEX free/paper · monitor only (execute still RTH-gated). "
        "CLI: `neotrade monitor --interval 15` · live WS: `neotrade stream --seconds 60 -v`"
    )
    session = get_session_status()
    st.caption(session.summary_line())
    auto = st.checkbox("Auto-refresh (Streamlit)", value=False)
    interval = st.slider("Refresh every (seconds)", min_value=5, max_value=120, value=15, step=5)
    if st.button("Refresh quotes", type="primary"):
        st.session_state.pop("quotes_df", None)
    try:
        snap = fetch_universe_quotes(prefer_alpaca=True, fallback_cache=True)
    except (RuntimeError, OSError, ValueError) as exc:
        log.error("quotes page failed: %s", exc)
        st.error(str(exc))
        return
    df = pd.DataFrame([r.to_dict() for r in snap.rows])
    st.write(f"Feed: `{snap.feed or 'n/a'}` · priced={df['price'].notna().sum()}/{len(df)}")
    st.dataframe(df, use_container_width=True, hide_index=True)
    if snap.errors:
        with st.expander("Errors / notes"):
            for e in snap.errors:
                st.text(e)
    if auto:
        import time as _time

        _time.sleep(float(interval))
        st.rerun()


def page_signals() -> None:
    st.subheader("Signals")
    cfg = load_tickers_config()
    risk = default_risk_limits(cfg)
    buy_th = st.sidebar.slider("Buy threshold", 0.5, 0.7, float(risk.buy_threshold), 0.01)
    sell_th = st.sidebar.slider("Sell threshold", 0.3, 0.5, float(risk.sell_threshold), 0.01)
    if st.button("Refresh signals", type="primary"):
        load_signals_cached.clear()
    if not DEFAULT_MODEL.is_file():
        st.warning("No model at models/signal.txt — run `neotrade train`")
        return
    with st.spinner("Scoring universe…"):
        df = load_signals_cached(str(DEFAULT_MODEL), buy_th, sell_th)
    if df.empty:
        st.error("No signals produced")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    buys = df[df["side"] == "buy"]
    st.caption(f"Buys: {len(buys)} · Holds: {(df['side']=='hold').sum()} · Sells: {(df['side']=='sell').sum()}")
    if not buys.empty:
        st.bar_chart(buys.set_index("symbol")["proba"])


def page_account() -> None:
    st.subheader("Alpaca paper")
    session = get_session_status()
    if session.allow_execute:
        st.success(session.summary_line())
    else:
        st.warning(session.summary_line())
    try:
        client = AlpacaPaperClient()
        acct = client.get_account()
        positions = client.list_positions()
        orders = client.list_orders(status="open", limit=50)
    except (RuntimeError, AlpacaAPIError, OSError) as exc:
        log.error("account page failed: %s", exc)
        st.error(str(exc))
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Equity", f"${acct.equity:,.2f}")
    c2.metric("Cash", f"${acct.cash:,.2f}")
    c3.metric("Buying power", f"${acct.buying_power:,.2f}")
    st.write(f"Status: `{acct.status}` · blocked={acct.trading_blocked or acct.account_blocked}")

    if positions:
        st.write("**Positions**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "symbol": p.symbol,
                        "qty": p.qty,
                        "mv": p.market_value,
                        "price": p.current_price,
                        "upl": p.unrealized_pl,
                    }
                    for p in positions
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No open positions")

    if orders:
        st.write("**Open orders**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "symbol": o.get("symbol"),
                        "side": o.get("side"),
                        "qty": o.get("qty"),
                        "status": o.get("status"),
                        "filled": o.get("filled_qty"),
                    }
                    for o in orders
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
        if not positions:
            st.caption("Day market orders often stay accepted until the next US regular session.")


def page_plan() -> None:
    st.subheader("Paper plan (dry-run)")
    st.caption("Does not submit orders. Use CLI `neotrade paper-execute --confirm` during RTH only.")
    session = get_session_status()
    if not session.allow_execute:
        st.warning(session.summary_line() + " — execute would be blocked.")
    else:
        st.info(session.summary_line())
    if not DEFAULT_MODEL.is_file():
        st.warning("Train a model first")
        return
    try:
        cfg = load_tickers_config()
        risk = default_risk_limits(cfg)
        model = SignalModel.load(DEFAULT_MODEL)
        bars = load_universe_ohlcv(cfg, force_refresh=False, root=project_root())
        scored = score_universe(
            model,
            bars.frames,
            buy_threshold=risk.buy_threshold,
            sell_threshold=risk.sell_threshold,
        )
        client = AlpacaPaperClient()
        acct = client.get_account()
        positions = client.list_positions()
        plan = build_trade_plan(
            signals=scored.rows,
            account=acct,
            positions=positions,
            cfg=cfg,
            risk=risk,
            prices=prices_for_plan(cfg, frames=bars.frames),
        )
    except (RuntimeError, OSError, ValueError, FileNotFoundError, AlpacaAPIError) as exc:
        log.error("plan page failed: %s", exc)
        st.error(str(exc))
        return
    for line in plan.summary_lines():
        st.text(line)


def page_advise() -> None:
    st.subheader("Local agents (Ollama)")
    st.caption(policy_blurb())
    use_mock = st.checkbox("Use mock LLM (offline)", value=False)
    no_account = st.checkbox("Skip Alpaca context", value=False)
    llm_model = st.text_input("Ollama model", value=OllamaConfig.from_env().model)
    if st.button("Run advise", type="primary"):
        if not DEFAULT_MODEL.is_file():
            st.error("models/signal.txt missing — run neotrade train")
            return
        if use_mock:
            llm = MockLLM()
        else:
            cfg = OllamaConfig.from_env()
            cfg = OllamaConfig(
                host=cfg.host,
                model=llm_model,
                temperature=cfg.temperature,
                timeout=cfg.timeout,
            )
            llm = OllamaClient(cfg)
            if not llm.ping():
                st.error("Ollama not reachable — brew services start ollama")
                return
        with st.spinner("Running LangGraph agents locally…"):
            try:
                report = run_advise(
                    model_path=DEFAULT_MODEL,
                    include_account=not no_account,
                    llm=llm,
                )
            except (RuntimeError, OSError, ValueError, FileNotFoundError) as exc:
                log.error("advise page failed: %s", exc)
                st.error(str(exc))
                return
        st.session_state["last_advice_report"] = report
        try:
            path = record_advice_run(report, source="dashboard", notes="auto from dashboard advise")
            st.session_state["last_advice_log"] = str(path)
        except (OSError, ValueError) as exc:
            log.warning("dashboard advice log skipped: %s", exc)
        log.info("dashboard advise stance=%s", report.stance)

    report = st.session_state.get("last_advice_report")
    if report is not None:
        st.code(report.render(), language=None)
        if getattr(report, "errors", None):
            st.warning("; ".join(report.errors))
        st.subheader("Rate this advice (journal only)")
        st.caption("1 = poor · 5 = excellent. Does **not** retrain LightGBM.")
        rating = st.slider("Quality rating", min_value=1, max_value=5, value=3)
        notes = st.text_input("Notes (optional)", value="")
        if st.button("Save rating"):
            try:
                path = record_advice_run(
                    report,
                    source="dashboard",
                    rating=int(rating),
                    notes=notes or "dashboard rating",
                )
                st.success(f"Saved rating to {path}")
            except (OSError, ValueError) as exc:
                st.error(str(exc))
        if st.session_state.get("last_advice_log"):
            st.caption(f"Last auto-log: `{st.session_state['last_advice_log']}`")

    recent = advice_events(limit=8)
    if recent:
        st.subheader("Recent advice log")
        st.dataframe(
            [
                {
                    "ts": r.get("ts", "")[:19],
                    "kind": r.get("kind"),
                    "source": (r.get("payload") or {}).get("source"),
                    "stance": (r.get("payload") or {}).get("stance"),
                    "rating": (r.get("payload") or {}).get("rating"),
                    "picks": ",".join((r.get("payload") or {}).get("top_picks") or [])[:40],
                }
                for r in reversed(recent)
            ],
            use_container_width=True,
            hide_index=True,
        )


def page_bench() -> None:
    st.subheader("Local model efficiency")
    st.caption("Benchmarks Ollama latency/memory and LightGBM score speed on this machine.")
    if st.button("Run bench now"):
        from neotrade.perf.bench import run_full_bench

        with st.spinner("Benchmarking…"):
            report = run_full_bench()
        st.json(report.to_dict())
        for line in report.summary_lines():
            st.text(line)
    st.markdown(
        """
**Tuning tips (8GB Neo)**
- Prefer `llama3.2:3b` (or `1b` if memory tight)
- Keep one Ollama model loaded; avoid parallel large jobs
- LightGBM already uses `n_jobs=1` for memory
- Re-train weekly: `neotrade train` after `neotrade fetch`
- Review `data/learning/` logs to track advice quality over time
"""
    )


def main() -> None:
    st.set_page_config(page_title="neotrade", page_icon="📈", layout="wide")
    st.title("neotrade")
    st.caption("Local paper-trading decision support · MacBook Neo")
    page = st.sidebar.radio(
        "Page",
        ["Overview", "Quotes", "Signals", "Account", "Plan", "Advise", "Bench"],
    )
    if page == "Overview":
        page_overview()
    elif page == "Quotes":
        page_quotes()
    elif page == "Signals":
        page_signals()
    elif page == "Account":
        page_account()
    elif page == "Plan":
        page_plan()
    elif page == "Advise":
        page_advise()
    else:
        page_bench()


if __name__ == "__main__":
    main()
