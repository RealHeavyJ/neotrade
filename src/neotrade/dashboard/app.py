"""Streamlit dashboard — local signals, paper account, agents."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from neotrade import __version__
from neotrade.agents import run_advise
from neotrade.agents.llm import MockLLM, OllamaClient, OllamaConfig
from neotrade.broker import AlpacaPaperClient, build_trade_plan, default_risk_limits
from neotrade.broker.alpaca import AlpacaAPIError
from neotrade.config import load_tickers_config
from neotrade.config.load import project_root
from neotrade.data import fetch_universe_quotes, load_universe_ohlcv, prices_for_plan
from neotrade.signals import SignalModel, score_universe

DEFAULT_MODEL = project_root() / "models" / "signal.txt"


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
    col1, col2, col3, col4 = st.columns(4)
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
    st.caption(f"neotrade v{__version__} · local-only agents · paper Alpaca")

    cfg = load_tickers_config()
    st.write(f"**Universe:** {cfg.universe.name} ({len(cfg.tickers)} tickers)")
    g = sum(1 for t in cfg.tickers if t.sleeve == "growth")
    d = sum(1 for t in cfg.tickers if t.sleeve == "defensive")
    st.write(
        f"Sleeves: growth={g} · defensive={d} · risk max name={cfg.risk.max_position_pct:.0%} · "
        f"bars provider=`{cfg.data.provider}`"
    )


def page_quotes() -> None:
    st.subheader("Live quotes (Alpaca market data)")
    st.caption("REST latest trade/quote · feed usually IEX on free/paper · cache fallback if needed")
    if st.button("Refresh quotes", type="primary"):
        st.session_state.pop("quotes_df", None)
    try:
        snap = fetch_universe_quotes(prefer_alpaca=True, fallback_cache=True)
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))
        return
    df = pd.DataFrame([r.to_dict() for r in snap.rows])
    st.write(f"Feed: `{snap.feed or 'n/a'}` · priced={df['price'].notna().sum()}/{len(df)}")
    st.dataframe(df, use_container_width=True, hide_index=True)
    if snap.errors:
        with st.expander("Errors / notes"):
            for e in snap.errors:
                st.text(e)


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
    try:
        client = AlpacaPaperClient()
        acct = client.get_account()
        positions = client.list_positions()
        orders = client.list_orders(status="open", limit=50)
    except (RuntimeError, AlpacaAPIError, OSError) as exc:
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
    st.caption("Does not submit orders. Use CLI `neotrade paper-execute --confirm` to trade.")
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
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))
        return
    for line in plan.summary_lines():
        st.text(line)


def page_advise() -> None:
    st.subheader("Local agents (Ollama)")
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
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))
                return
        st.code(report.render(), language=None)
        if report.errors:
            st.warning("; ".join(report.errors))


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
