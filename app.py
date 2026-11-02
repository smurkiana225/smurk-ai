import streamlit as st
import pandas as pd
from datetime import datetime, timezone
import engine

st.set_page_config(page_title="SMURK AI", page_icon="₿", layout="wide")

st.markdown("""
<style>
.stApp {background: #090d16; color: #f4f6fb;}
.block-container {padding-top: 1.4rem; max-width: 1400px;}
[data-testid="stMetric"] {background:#121a29; border:1px solid #263247; padding:14px; border-radius:12px;}
section[data-testid="stSidebar"] {background:#101827;}
.signal {padding:16px;border-radius:12px;background:#121a29;border:1px solid #263247;}
.small {color:#9ba9bd;font-size:0.88rem;}
</style>
""", unsafe_allow_html=True)

st.title("₿ SMURK AI")
st.caption("Bitcoin 15-minute market analysis • Kalshi public-market context • Paper trading")

with st.sidebar:
    st.subheader("SMURK AI")
    page = st.radio("Navigation", ["Overview", "Technical Analysis", "Kalshi Market", "Trade Planner", "Paper Journal", "Settings"])
    st.divider()
    st.warning("PAPER MODE ONLY — this app does not place real-money orders.")
    refresh = st.button("Refresh market data", use_container_width=True)

@st.cache_data(ttl=30, show_spinner=False)
def load_snapshot():
    return engine.create_snapshot()

if refresh:
    load_snapshot.clear()

snapshot = None
error = None
try:
    with st.spinner("Loading live BTC and Kalshi public data..."):
        snapshot = load_snapshot()
except Exception as exc:
    error = str(exc)

if error:
    st.error("Market data could not be loaded: " + error)
    st.info("Check your connection and try Refresh market data. No simulated prices are shown.")
    st.stop()

ind = snapshot["indicators"]
market = snapshot["kalshi"]
signal = snapshot["signal"]

st.caption(f"Data: {snapshot['source']} • Updated: {snapshot['asOf']} • Status: {snapshot['dataStatus']}")

if page == "Overview":
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("BTC / USD", f"${snapshot['price']:,.2f}", f"{snapshot['priceChange24h']:+.2f}% (24h)")
    c2.metric("Directional signal", signal.replace("_"," "))
    c3.metric("RSI (14)", "N/A" if ind["rsi"] is None else f"{ind['rsi']:.1f}")
    c4.metric("Trend", ind["trend"].title())
    st.subheader("15-minute Bitcoin candles")
    frame = pd.DataFrame(snapshot["candles"])
    frame["time"] = pd.to_datetime(frame["time"])
    st.line_chart(frame.set_index("time")["close"], height=300)
    st.subheader("Signal assessment")
    st.markdown('<div class="signal">', unsafe_allow_html=True)
    if signal == "BUY_UP":
        st.success("BUY UP — directional indicators are bullish. This is a research signal, not a guaranteed outcome.")
    elif signal == "BUY_DOWN":
        st.error("BUY DOWN — directional indicators are bearish. This is a research signal, not a guaranteed outcome.")
    else:
        st.warning("WAIT — conditions do not meet the strategy's confirmation rules.")
    for reason in snapshot["reasons"]:
        st.write("• " + reason)
    st.markdown("</div>", unsafe_allow_html=True)
    st.caption(snapshot["disclaimer"])

elif page == "Technical Analysis":
    st.subheader("Technical indicators")
    cols = st.columns(4)
    cols[0].metric("RSI 14", "N/A" if ind["rsi"] is None else f"{ind['rsi']:.2f}")
    cols[1].metric("EMA 9", f"${ind['ema9']:,.2f}")
    cols[2].metric("EMA 21", f"${ind['ema21']:,.2f}")
    cols[3].metric("EMA 50", f"${ind['ema50']:,.2f}")
    macd = ind["macd"]
    st.write("**MACD:**", macd["direction"], "| Histogram:", f"{macd['histogram']:.4f}")
    st.write("**15-minute momentum:**", f"{ind['momentumPct']:+.4f}%")
    st.write("**Volume vs recent average:**", f"{ind['volumeRatio']:.2f}x")
    st.write("**Trend:**", ind["trend"].title())
    st.line_chart(pd.DataFrame(snapshot["candles"]).set_index("time")["close"])

elif page == "Kalshi Market":
    st.subheader("Kalshi BTC 15-minute market")
    if market["status"] != "live":
        st.warning(f"Kalshi market unavailable: {market.get('error') or market['status']}. No quotes are fabricated.")
    else:
        st.write("**Market:**", market["title"] or market["ticker"])
        st.write("**Ticker:**", market["ticker"])
        st.write("**Closes:**", market["closeTime"])
        q1,q2,q3,q4 = st.columns(4)
        q1.metric("YES bid", "—" if market["yesBidCents"] is None else f'{market["yesBidCents"]:.2f}¢')
        q2.metric("YES ask", "—" if market["yesAskCents"] is None else f'{market["yesAskCents"]:.2f}¢')
        q3.metric("NO bid", "—" if market["noBidCents"] is None else f'{market["noBidCents"]:.2f}¢')
        q4.metric("NO ask", "—" if market["noAskCents"] is None else f'{market["noAskCents"]:.2f}¢')
        st.write("**YES spread:**", "—" if market["spreadCents"] is None else f'{market["spreadCents"]:.2f}¢')
        st.write("**Displayed order-book depth (top levels):** YES", market["yesDepth"], "| NO", market["noDepth"])
        st.caption("Public quotes can change quickly. Verify the market and order book in Kalshi before any decision.")

elif page == "Trade Planner":
    st.subheader("Kalshi binary-contract risk planner")
    st.caption("This estimates contract payout scenarios; it does not submit orders.")
    side = st.selectbox("Direction", ["UP", "DOWN"])
    contracts = st.number_input("Number of contracts", min_value=1, max_value=10000, value=1, step=1)
    entry = st.number_input("Entry price (cents)", min_value=1.0, max_value=99.0, value=50.0, step=1.0)
    exit_price = st.number_input("Planned exit price (cents)", min_value=0.0, max_value=100.0, value=60.0, step=1.0)
    fees = st.number_input("Estimated fee per contract (cents)", min_value=0.0, max_value=10.0, value=0.0, step=0.01)
    if st.button("Calculate contract risk"):
        plan = engine.create_risk_plan({
            "side": side, "contracts": int(contracts),
            "entryPriceCents": entry, "plannedExitPriceCents": exit_price,
            "feePerContractCents": fees
        })
        a,b,c = st.columns(3)
        a.metric("Cost before fees", f'${plan["costBeforeFees"]:.2f}')
        b.metric("Maximum loss incl. fees", f'${plan["maximumLossIncludingFees"]:.2f}')
        c.metric("Planned net P/L", f'${plan["plannedNetPnl"]:.2f}')
        st.json(plan)

elif page == "Paper Journal":
    st.subheader("Paper-trading journal")
    if "journal" not in st.session_state:
        st.session_state.journal = []
    with st.form("paper_trade"):
        direction = st.selectbox("Direction", ["UP", "DOWN"])
        entry_cents = st.number_input("Entry price (cents)", min_value=1.0, max_value=99.0, value=50.0)
        quantity = st.number_input("Contracts", min_value=1, value=1, step=1)
        note = st.text_input("Notes")
        submitted = st.form_submit_button("Record paper trade")
    if submitted:
        st.session_state.journal.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "direction": direction, "entry_cents": entry_cents,
            "contracts": int(quantity), "status": "OPEN", "notes": note
        })
    if st.session_state.journal:
        st.dataframe(pd.DataFrame(st.session_state.journal), use_container_width=True)
        if st.button("Clear paper journal"):
            st.session_state.journal = []
            st.rerun()
    else:
        st.info("No paper trades recorded yet. Journal is stored in this browser session.")

else:
    st.subheader("Settings")
    st.write("**Trading mode:** PAPER ONLY")
    st.write("**Live order placement:** Not implemented and disabled.")
    st.write("**Market refresh:** 30-second cache; use Refresh market data for an immediate request.")
    st.write("**Storage:** Paper journal is local to this browser session.")
    st.write("**Data providers:** Binance with Coinbase fallback; Kalshi public market endpoints.")
    st.warning("Do not enter Kalshi API secrets into this app. Authenticated order placement is not included.")
