import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timezone
import engine

st.set_page_config(page_title="SMURK AI", page_icon="₿", layout="wide")

st.markdown("""
<style>
.stApp {background:#090d16;color:#f4f6fb;}
.block-container {padding-top:1.2rem;max-width:1400px;}
[data-testid="stMetric"] {background:#121a29;border:1px solid #263247;padding:14px;border-radius:12px;}
section[data-testid="stSidebar"] {background:#101827;}
.small {color:#9ba9bd;font-size:.88rem;}
</style>
""", unsafe_allow_html=True)

st.title("₿ SMURK AI")
st.caption("Bitcoin 15-minute analysis • Kalshi public-market context • Paper trading")

with st.sidebar:
    st.subheader("SMURK AI")
    page = st.radio("Navigation", [
        "Overview", "Technical Analysis", "Kalshi Market",
        "Trade Planner", "Paper Journal", "Settings"
    ])
    st.divider()
    st.warning("PAPER MODE ONLY — no real-money orders are placed.")
    refresh = st.button("Refresh market data", use_container_width=True)

@st.cache_data(ttl=15, show_spinner=False)
def load_snapshot():
    return engine.create_snapshot()

if refresh:
    load_snapshot.clear()

try:
    with st.spinner("Loading live BTC and Kalshi public data..."):
        snapshot = load_snapshot()
except Exception as exc:
    st.error(f"Market data could not be loaded: {exc}")
    st.info("Try Refresh market data. No simulated prices are substituted.")
    st.stop()

ind = snapshot["indicators"]
market = snapshot["kalshi"]
signal = snapshot["signal"]

st.caption(
    f'Data: {snapshot.get("source", "Unknown")} • '
    f'Updated: {snapshot.get("asOf", "Unknown")} • '
    f'Status: {snapshot.get("dataStatus", "Unknown")}'
)

def money(value):
    return "—" if value is None else f"${float(value):,.2f}"

def cents(value):
    return "—" if value is None else f"{float(value):.2f}¢"

def current_ask(direction):
    if not market or market.get("status") != "live":
        return None
    value = market.get("yesAskCents" if direction == "UP" else "noAskCents")
    return None if value is None else float(value)

def market_countdown(close_time):
    if not close_time:
        return None
    try:
        end = pd.to_datetime(close_time, utc=True).to_pydatetime()
        seconds = max(0, int((end - datetime.now(timezone.utc)).total_seconds()))
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except Exception:
        return None

def candle_chart(data, height=440):
    """Plot actual OHLC candles with EMA overlays and a focused price axis."""
    frame = pd.DataFrame(data)
    needed = {"time", "open", "high", "low", "close"}
    if frame.empty or not needed.issubset(frame.columns):
        st.info("Candle data is not available right now.")
        return
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame = frame.sort_values("time").tail(64).copy()
    closes = frame["close"].astype(float)
    frame["EMA 9"] = closes.ewm(span=9, adjust=False).mean()
    frame["EMA 21"] = closes.ewm(span=21, adjust=False).mean()

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=frame["time"], open=frame["open"], high=frame["high"],
        low=frame["low"], close=frame["close"], name="BTC 15m",
        increasing_line_color="#16c784", decreasing_line_color="#ea3943"
    ))
    fig.add_trace(go.Scatter(
        x=frame["time"], y=frame["EMA 9"], mode="lines",
        name="EMA 9", line=dict(width=2)
    ))
    fig.add_trace(go.Scatter(
        x=frame["time"], y=frame["EMA 21"], mode="lines",
        name="EMA 21", line=dict(width=2)
    ))
    low = float(frame["low"].min())
    high = float(frame["high"].max())
    pad = max((high - low) * 0.12, high * 0.0005)
    fig.update_layout(
        height=height, template="plotly_dark",
        margin=dict(l=8, r=8, t=25, b=8),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.08, x=0),
        paper_bgcolor="#090d16", plot_bgcolor="#090d16",
        yaxis=dict(title="BTC price (USD)", range=[low-pad, high+pad], fixedrange=False),
        xaxis=dict(title="", rangeslider=dict(visible=False))
    )
    st.plotly_chart(fig, use_container_width=True)

def show_directional_scores(snapshot, market):
    up = int(snapshot.get("upScore", 0) or 0)
    down = int(snapshot.get("downScore", 0) or 0)
    difference = up - down
    st.subheader("Directional scoring")
    left, right = st.columns(2)
    left.metric("Bullish score", f"{up}/7", "UP")
    right.metric("Bearish score", f"{down}/7", "DOWN")
    st.write("**Score comparison**")
    st.progress(min(1.0, max(up, down) / 7))
    if difference >= 2:
        st.info(f"Current indicator bias leans UP by {difference} point(s).")
    elif difference <= -2:
        st.info(f"Current indicator bias leans DOWN by {abs(difference)} point(s).")
    else:
        st.warning("Bullish and bearish scores are close. Direction is mixed.")
    up_ask = market.get("yesAskCents") if market else None
    down_ask = market.get("noAskCents") if market else None
    a, b = st.columns(2)
    a.metric("Live UP (YES) ask", cents(up_ask))
    b.metric("Live DOWN (NO) ask", cents(down_ask))
    st.caption("Scores count indicator-rule alignment, not odds or win probability. Quotes are live only when the market provider reports them; confirm the order book before trading.")

def show_signal_meter(snapshot, indicators):
    # Prefer checks supplied by the engine. If an older cached snapshot lacks
    # them, rebuild the six transparent checks from the same snapshot data.
    checks = snapshot.get("checks") or {}
    if not isinstance(checks, dict) or not checks:
        candles = pd.DataFrame(snapshot.get("candles", []))
        rsi = indicators.get("rsi")
        ema9 = indicators.get("ema9")
        ema21 = indicators.get("ema21")
        ema50 = indicators.get("ema50")
        macd_info = indicators.get("macd") or {}
        hist = macd_info.get("histogram")
        momentum = indicators.get("momentumPct")
        volume_ratio = indicators.get("volumeRatio")
        last_close = None
        if not candles.empty and "close" in candles:
            last_close = float(candles.sort_values("time").iloc[-1]["close"])
        checks = {
            "EMA alignment": (
                ema9 is not None and ema21 is not None and ema50 is not None
                and (ema9 > ema21 > ema50 or ema9 < ema21 < ema50)
            ),
            "Price vs EMA 9": last_close is not None and ema9 is not None and last_close != float(ema9),
            "RSI momentum": rsi is not None and (32 <= float(rsi) <= 48 or 52 <= float(rsi) <= 68),
            "MACD direction": hist is not None and float(hist) != 0,
            "15m momentum": momentum is not None and abs(float(momentum)) > 0.03,
            "Volume confirmation": volume_ratio is not None and float(volume_ratio) >= 1.2,
        }
    passed = sum(bool(v) for v in checks.values())
    total = len(checks)
    st.write(f"**Indicator agreement: {passed}/{total} checks**")
    st.progress(passed / total if total else 0)
    with st.expander("See the six checks"):
        for label, result in checks.items():
            st.write(("✓ " if result else "— ") + label)
    st.caption("This measures rule agreement only. It is NOT a win probability or guarantee.")

if page == "Overview":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BTC / USD", money(snapshot.get("price")),
              f'{snapshot.get("priceChange24h", 0):+.2f}% (24h)')
    c2.metric("Directional signal", str(signal).replace("_", " "))
    c3.metric("RSI (14)", "N/A" if ind.get("rsi") is None else f'{ind["rsi"]:.1f}')
    c4.metric("Trend", str(ind.get("trend", "Unknown")).title())

    st.subheader("Bitcoin 15-minute candlestick chart")
    candle_chart(snapshot.get("candles", []))
    show_directional_scores(snapshot, market)
    st.subheader("Signal strength")
    show_signal_meter(snapshot, ind)

    st.subheader("Signal assessment")
    if signal == "BUY_UP":
        st.success("BUY UP — bullish conditions meet the current rule threshold. Confirm price, spread, and risk before any trade.")
    elif signal == "BUY_DOWN":
        st.error("BUY DOWN — bearish conditions meet the current rule threshold. Confirm price, spread, and risk before any trade.")
    else:
        st.warning("WAIT — the current conditions do not meet the strategy's confirmation rules.")
    for reason in snapshot.get("reasons", []):
        st.write("• " + str(reason))
    st.caption(snapshot.get("disclaimer", "Signals are research indicators, not verified win probabilities."))

elif page == "Technical Analysis":
    st.subheader("Technical indicators")
    cols = st.columns(4)
    cols[0].metric("RSI 14", "N/A" if ind.get("rsi") is None else f'{ind["rsi"]:.2f}')
    for col, label, key in [
        (cols[1], "EMA 9", "ema9"),
        (cols[2], "EMA 21", "ema21"),
        (cols[3], "EMA 50", "ema50")
    ]:
        col.metric(label, money(ind.get(key)))
    macd = ind.get("macd", {})
    st.write("**MACD:**", macd.get("direction", "N/A"),
             "| Histogram:", "N/A" if macd.get("histogram") is None else f'{macd["histogram"]:.4f}')
    st.write("**15-minute momentum:**",
             "N/A" if ind.get("momentumPct") is None else f'{ind["momentumPct"]:+.4f}%')
    st.write("**Volume vs recent average:**",
             "N/A" if ind.get("volumeRatio") is None else f'{ind["volumeRatio"]:.2f}x')
    st.write("**Trend:**", str(ind.get("trend", "Unknown")).title())
    candle_chart(snapshot.get("candles", []), height=520)
    show_directional_scores(snapshot, market)
    st.subheader("Indicator agreement")
    show_signal_meter(snapshot, ind)

elif page == "Kalshi Market":
    st.subheader("Kalshi BTC 15-minute market")
    if market.get("status") != "live":
        st.warning(f'Kalshi market unavailable: {market.get("error") or market.get("status")}. No quotes are fabricated.')
    else:
        st.write("**Market:**", market.get("title") or market.get("ticker", "Unknown"))
        st.write("**Ticker:**", market.get("ticker", "Unknown"))
        st.write("**Closes (UTC):**", market.get("closeTime", "Unknown"))
        countdown = market_countdown(market.get("closeTime"))
        if countdown is not None:
            st.metric("Time until market closes", countdown)
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("YES bid", cents(market.get("yesBidCents")))
        q2.metric("YES ask", cents(market.get("yesAskCents")))
        q3.metric("NO bid", cents(market.get("noBidCents")))
        q4.metric("NO ask", cents(market.get("noAskCents")))
        st.write("**YES spread:**", cents(market.get("spreadCents")))
        st.caption("Quotes can change quickly. Verify the exact contract and order book in Kalshi.")

elif page == "Trade Planner":
    st.subheader("Kalshi binary-contract risk planner")
    st.caption("Scenario calculator only. It does not submit orders.")
    side = st.selectbox("Direction", ["UP", "DOWN"])
    live_ask = current_ask(side)
    if live_ask is not None:
        st.success(f"Current {side} ask: {live_ask:.2f}¢")
        default_entry = min(99.0, max(1.0, live_ask))
    else:
        st.info("A live ask is unavailable. Enter the price you are considering manually.")
        default_entry = 50.0
    contracts = st.number_input("Number of contracts", min_value=1, max_value=10000, value=1, step=1)
    entry = st.number_input("Entry price (cents)", min_value=1.0, max_value=99.0, value=float(default_entry), step=0.5)
    exit_price = st.number_input("Planned exit price (cents)", min_value=0.0, max_value=100.0, value=60.0, step=0.5)
    fees = st.number_input("Estimated fee per contract (cents)", min_value=0.0, max_value=10.0, value=0.0, step=0.01)
    st.caption("Enter an applicable fee estimate; zero does not mean a trade is fee-free.")
    if st.button("Calculate contract risk", type="primary"):
        plan = engine.create_risk_plan({
            "side": side, "contracts": int(contracts),
            "entryPriceCents": float(entry),
            "plannedExitPriceCents": float(exit_price),
            "feePerContractCents": float(fees)
        })
        a, b, c = st.columns(3)
        a.metric("Cost before fees", money(plan.get("costBeforeFees")))
        b.metric("Maximum loss incl. fees", money(plan.get("maximumLossIncludingFees")))
        c.metric("Planned net P/L", money(plan.get("plannedNetPnl")))
        st.json(plan)

elif page == "Paper Journal":
    st.subheader("Paper-trading journal")
    if "journal" not in st.session_state:
        st.session_state.journal = []
    with st.form("paper_trade"):
        direction = st.selectbox("Direction", ["UP", "DOWN"])
        live_ask = current_ask(direction)
        default_entry = 50.0 if live_ask is None else min(99.0, max(1.0, live_ask))
        if live_ask is not None:
            st.caption(f"Current {direction} ask: {live_ask:.2f}¢")
        entry_cents = st.number_input("Entry price (cents)", min_value=1.0, max_value=99.0,
                                      value=float(default_entry), step=0.5)
        quantity = st.number_input("Contracts", min_value=1, max_value=10000, value=1, step=1)
        note = st.text_input("Notes")
        submitted = st.form_submit_button("Record paper trade")
    if submitted:
        st.session_state.journal.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "direction": direction, "entry_cents": float(entry_cents),
            "contracts": int(quantity), "status": "OPEN", "notes": note
        })
        st.success("Paper trade recorded in this session.")
    if st.session_state.journal:
        journal_df = pd.DataFrame(st.session_state.journal)
        st.dataframe(journal_df, use_container_width=True)
        st.download_button("Download paper journal CSV",
            data=journal_df.to_csv(index=False).encode("utf-8"),
            file_name="smurk_ai_paper_journal.csv", mime="text/csv")
        if st.button("Clear paper journal"):
            st.session_state.journal = []
            st.rerun()
    else:
        st.info("No paper trades recorded yet.")
    st.caption("Journal entries are session-based. Download the CSV to keep a permanent copy.")

else:
    st.subheader("Settings")
    st.write("**Trading mode:** PAPER ONLY")
    st.write("**Live order placement:** Not implemented and disabled.")
    st.write("**Market refresh:** 15-second cache; use Refresh market data for an immediate request.")
    st.write("**Journal storage:** Current app session; export CSV to keep a copy.")
    st.write("**Data providers:** Binance with Coinbase fallback; Kalshi public market endpoints.")
    st.warning("Never enter Kalshi API secrets into this app. Authenticated order placement is not included.")
    st.caption("Directional signals are not verified win probabilities and do not guarantee profit.")
