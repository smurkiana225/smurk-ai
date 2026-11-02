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

def current_spread(direction):
    """Return the quoted spread for the selected binary-contract side."""
    if not market or market.get("status") != "live":
        return None
    bid_key, ask_key = (
        ("yesBidCents", "yesAskCents") if direction == "UP"
        else ("noBidCents", "noAskCents")
    )
    bid, ask = market.get(bid_key), market.get(ask_key)
    if bid is None or ask is None:
        return None
    return max(0.0, float(ask) - float(bid))


def evaluate_entry(direction, ask_cents, spread_cents, fee_cents,
                   directional_signal, min_net_upside_cents=10.0,
                   max_spread_cents=5.0):
    """Conservative quote/economics gate; not a prediction of win probability."""
    if ask_cents is None:
        return {"ok": False, "reason": "No live ask is available for this side."}
    ask = float(ask_cents)
    fee = max(0.0, float(fee_cents))
    if not 0 < ask < 100:
        return {"ok": False, "reason": "The displayed ask is outside a valid contract price."}
    gross_upside = 100.0 - ask
    net_upside = gross_upside - fee
    if directional_signal != ("BUY_UP" if direction == "UP" else "BUY_DOWN"):
        return {"ok": False, "reason": "The directional signal does not confirm this side."}
    if spread_cents is None:
        return {"ok": False, "reason": "The side's bid/ask spread is unavailable."}
    if float(spread_cents) > max_spread_cents:
        return {"ok": False, "reason": f"Spread is too wide ({float(spread_cents):.2f}¢; limit {max_spread_cents:.2f}¢)."}
    if net_upside < min_net_upside_cents:
        return {"ok": False, "reason": f"Maximum net upside is only {net_upside:.2f}¢ per contract; minimum is {min_net_upside_cents:.2f}¢."}
    return {"ok": True, "reason": "Direction, spread, and estimated payout screen passed. This is not a guarantee."}


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

def calculate_directional_scores(snapshot, indicators):
    """Rebuild the directional scores from displayed live indicators.

    This fallback prevents a missing/old cached score field from displaying
    0/7 when the underlying BTC indicators are available.
    """
    up = down = 0
    candles = pd.DataFrame(snapshot.get("candles", []))
    close = None
    if not candles.empty and "close" in candles.columns:
        candles = candles.sort_values("time")
        close = float(candles.iloc[-1]["close"])
    ema9 = indicators.get("ema9")
    ema21 = indicators.get("ema21")
    ema50 = indicators.get("ema50")
    rsi = indicators.get("rsi")
    macd_info = indicators.get("macd") or {}
    hist = macd_info.get("histogram")
    momentum = indicators.get("momentumPct")
    volume_ratio = indicators.get("volumeRatio")

    if None not in (ema9, ema21, ema50):
        if float(ema9) > float(ema21) > float(ema50):
            up += 2
        elif float(ema9) < float(ema21) < float(ema50):
            down += 2
    if close is not None and ema9 is not None:
        if close > float(ema9):
            up += 1
        elif close < float(ema9):
            down += 1
    if rsi is not None:
        if 52 <= float(rsi) <= 68:
            up += 1
        elif 32 <= float(rsi) <= 48:
            down += 1
    if hist is not None:
        if float(hist) > 0:
            up += 1
        elif float(hist) < 0:
            down += 1
    if momentum is not None:
        if float(momentum) > 0.03:
            up += 1
        elif float(momentum) < -0.03:
            down += 1
    if volume_ratio is not None and momentum is not None and float(volume_ratio) >= 1.2:
        if float(momentum) > 0:
            up += 1
        elif float(momentum) < 0:
            down += 1
    return up, down


def show_directional_scores(snapshot, market):
    indicators = snapshot.get("indicators", {})
    up = snapshot.get("upScore")
    down = snapshot.get("downScore")
    # Older cached snapshots or mismatched engine versions may omit score
    # fields. Recalculate from the live indicator values instead of showing 0/7.
    if up is None or down is None or (int(up or 0) == 0 and int(down or 0) == 0):
        up, down = calculate_directional_scores(snapshot, indicators)
    up, down = int(up or 0), int(down or 0)
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

    st.divider()
    st.subheader("Entry price & payout filter")
    st.caption("Paper-only screening. Kalshi quotes and fees can change; this does not submit orders.")
    fee_estimate = st.number_input(
        "Estimated Kalshi fee per contract (cents)",
        min_value=0.0, max_value=10.0, value=0.0, step=0.01,
        key="overview_fee_estimate"
    )
    st.caption("Enter the fee estimate applicable to your order. Zero is only a placeholder, not confirmation that fees are zero.")
    up_ask = current_ask("UP")
    down_ask = current_ask("DOWN")
    up_spread = current_spread("UP")
    down_spread = current_spread("DOWN")
    up_result = evaluate_entry("UP", up_ask, up_spread, fee_estimate, signal)
    down_result = evaluate_entry("DOWN", down_ask, down_spread, fee_estimate, signal)
    e1, e2 = st.columns(2)
    for col, label, ask_value, spread_value, result in [
        (e1, "UP / YES", up_ask, up_spread, up_result),
        (e2, "DOWN / NO", down_ask, down_spread, down_result)
    ]:
        with col:
            st.markdown(f"**{label}**")
            st.write("Ask:", cents(ask_value), "| Spread:", cents(spread_value))
            if ask_value is not None:
                gross = 100.0 - float(ask_value)
                net = gross - float(fee_estimate)
                st.write(f"Cost per contract: {float(ask_value):.2f}¢ before fees")
                st.write(f"Maximum net profit if correct: {net:.2f}¢ per contract (estimated)")
                st.write(f"Maximum loss if incorrect: {float(ask_value) + float(fee_estimate):.2f}¢ per contract (estimated)")
            if result["ok"]:
                st.success("PAPER SCREEN: PASSED")
            else:
                st.warning("PAPER SCREEN: WAIT")
            st.caption(result["reason"])
    st.info("The filter requires a matching directional signal, a known spread no wider than 5¢, and at least 10¢ estimated net upside per contract. These are conservative screening rules, not proven profitable thresholds.")

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
        spread_now = current_spread(side)
        st.write("Current side spread:", cents(spread_now))
        fee_for_screen = st.number_input(
            "Estimated fee per contract for entry screen (cents)",
            min_value=0.0, max_value=10.0, value=0.0, step=0.01,
            key="planner_fee_screen"
        )
        screen = evaluate_entry(side, live_ask, spread_now, fee_for_screen, signal)
        if screen["ok"]:
            st.success("Entry screen passed — paper analysis only.")
        else:
            st.warning("WAIT — " + screen["reason"])
        st.caption("A passed screen is not a trade instruction or a prediction of success.")
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
