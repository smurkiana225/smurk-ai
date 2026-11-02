import streamlit as st
import pandas as pd
from datetime import datetime, timezone
import engine

st.set_page_config(page_title="SMURK AI", page_icon="₿", layout="wide")

st.markdown("""
<style>
.stApp {background:#090d16;color:#f4f6fb;}
.block-container {padding-top:1.4rem;max-width:1400px;}
[data-testid="stMetric"] {background:#121a29;border:1px solid #263247;padding:14px;border-radius:12px;}
section[data-testid="stSidebar"] {background:#101827;}
.signal {padding:16px;border-radius:12px;background:#121a29;border:1px solid #263247;}
.small {color:#9ba9bd;font-size:0.88rem;}
</style>
""", unsafe_allow_html=True)

st.title("₿ SMURK AI")
st.caption("Bitcoin 15-minute market analysis • Kalshi public-market context • Paper trading")

with st.sidebar:
    st.subheader("SMURK AI")
    page = st.radio(
        "Navigation",
        ["Overview", "Technical Analysis", "Kalshi Market",
         "Trade Planner", "Paper Journal", "Settings"]
    )
    st.divider()
    st.warning("PAPER MODE ONLY — no real-money orders.")
    refresh = st.button("Refresh market data", use_container_width=True)

@st.cache_data(ttl=30, show_spinner=False)
def load_snapshot():
    return engine.create_snapshot()

if refresh:
    load_snapshot.clear()

try:
    with st.spinner("Loading live BTC and Kalshi public data..."):
        snapshot = load_snapshot()
except Exception as exc:
    st.error("Market data could not be loaded: " + str(exc))
    st.info("Check your connection and try refreshing. No simulated prices are shown.")
    st.stop()

ind = snapshot["indicators"]
market = snapshot["kalshi"]
signal = snapshot["signal"]

st.caption(
    f"Data: {snapshot['source']} • Updated: {snapshot['asOf']} "
    f"• Status: {snapshot['dataStatus']}"
)

def countdown(close_time):
    if not close_time:
        return "Unavailable"
    try:
        end = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
        seconds = max(0, int((end - datetime.now(timezone.utc)).total_seconds()))
        minutes, secs = divmod(seconds, 60)
        return f"{minutes:02d}:{secs:02d}"
    except (ValueError, TypeError):
        return "Unavailable"

def quote_for_side(side):
    if market.get("status") != "live":
        return None
    key = "yesAskCents" if side == "UP" else "noAskCents"
    return market.get(key)

def confirmation_summary():
    checks = [
        ("EMA trend", ind["trend"].lower() == "bullish"
         if signal == "BUY_UP" else
         ind["trend"].lower() == "bearish"
         if signal == "BUY_DOWN" else False),
        ("RSI available", ind["rsi"] is not None),
        ("MACD direction", ind["macd"]["direction"].lower()
         in ["bullish", "bearish"]),
        ("Volume confirmation", ind["volumeRatio"] >= 1.0),
    ]
    passed = sum(1 for _, ok in checks if ok)
    st.write(f"**Indicator checks:** {passed} of {len(checks)}")
    for name, ok in checks:
        st.write(("✅ " if ok else "⚪ ") + name)

if page == "Overview":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BTC / USD", f"${snapshot['price']:,.2f}",
              f"{snapshot['priceChange24h']:+.2f}% (24h)")
    c2.metric("Directional signal", signal.replace("_", " "))
    c3.metric("RSI (14)", "N/A" if ind["rsi"] is None else f"{ind['rsi']:.1f}")
    c4.metric("Trend", ind["trend"].title())

    st.subheader("15-minute Bitcoin candles")
    frame = pd.DataFrame(snapshot["candles"])
    frame["time"] = pd.to_datetime(frame["time"])
    st.line_chart(frame.set_index("time")["close"], height=300)

    st.subheader("Signal assessment")
    if signal == "BUY_UP":
        st.success("BUY UP — indicators currently lean bullish.")
    elif signal == "BUY_DOWN":
        st.error("BUY DOWN — indicators currently lean bearish.")
    else:
        st.warning("WAIT — conditions do not meet confirmation rules.")

    confirmation_summary()

    for reason in snapshot["reasons"]:
        st.write("• " + reason)

    st.caption(snapshot["disclaimer"])
    st.info("Signals are research indicators, not guaranteed predictions.")

elif page == "Technical Analysis":
    st.subheader("Technical indicators")
    cols = st.columns(4)
    cols[0].metric("RSI 14", "N/A" if ind["rsi"] is None else f"{ind['rsi']:.2f}")
    cols[1].metric("EMA 9", f"${ind['ema9']:,.2f}")
    cols[2].metric("EMA 21", f"${ind['ema21']:,.2f}")
    cols[3].metric("EMA 50", f"${ind['ema50']:,.2f}")

    macd = ind["macd"]
    st.write("**MACD:**", macd["direction"],
             "| Histogram:", f"{macd['histogram']:.4f}")
    st.write("**15-minute momentum:**", f"{ind['momentumPct']:+.4f}%")
    st.write("**Volume vs recent average:**", f"{ind['volumeRatio']:.2f}x")
    st.write("**Trend:**", ind["trend"].title())
    st.line_chart(pd.DataFrame(snapshot["candles"]).set_index("time")["close"])

elif page == "Kalshi Market":
    st.subheader("Kalshi BTC 15-minute market")

    if market["status"] != "live":
        st.warning(
            f"Kalshi market unavailable: "
            f"{market.get('error') or market['status']}. "
            "No quotes are fabricated."
        )
    else:
        st.write("**Market:**", market["title"] or market["ticker"])
        st.write("**Ticker:**", market["ticker"])
        st.write("**Closes:**", market["closeTime"])

        q1, q2, q3, q4 = st.columns(4)
        q1.metric("YES bid", "—" if market["yesBidCents"] is None
                  else f'{market["yesBidCents"]:.2f}¢')
        q2.metric("YES ask", "—" if market["yesAskCents"] is None
                  else f'{market["yesAskCents"]:.2f}¢')
        q3.metric("NO bid", "—" if market["noBidCents"] is None
                  else f'{market["noBidCents"]:.2f}¢')
        q4.metric("NO ask", "—" if market["noAskCents"] is None
                  else f'{market["noAskCents"]:.2f}¢')

        st.metric("Time until market closes",
                  countdown(market["closeTime"]))

        st.write("**YES spread:**",
                 "—" if market["spreadCents"] is None
                 else f'{market["spreadCents"]:.2f}¢')

        st.caption(
            "Public quotes can change quickly. Verify the market "
            "and order book directly in Kalshi."
        )

elif page == "Trade Planner":
    st.subheader("Kalshi binary-contract risk planner")
    st.caption("This estimates contract scenarios. It does not submit orders.")

    side = st.selectbox("Direction", ["UP", "DOWN"])

    live_quote = quote_for_side(side)

    if live_quote is not None:
        st.success(f"Current {side} ask: {live_quote:.2f}¢")
        default_entry = float(live_quote)
    else:
        st.warning("Live quote unavailable. Enter your own price.")
        default_entry = 50.0

    contracts = st.number_input(
        "Number of contracts", min_value=1,
        max_value=10000, value=1, step=1
    )

    entry = st.number_input(
        "Entry price (cents)", min_value=1.0,
        max_value=99.0, value=default_entry, step=1.0,
        key="planner_entry"
    )

    exit_price = st.number_input(
        "Planned exit price (cents)", min_value=0.0,
        max_value=100.0, value=60.0, step=1.0
    )

    fees = st.number_input(
        "Estimated fee per contract (cents)",
        min_value=0.0, max_value=10.0,
        value=0.0, step=0.01
    )

    if st.button("Calculate contract risk"):
        plan = engine.create_risk_plan({
            "side": side,
            "contracts": int(contracts),
            "entryPriceCents": entry,
            "plannedExitPriceCents": exit_price,
            "feePerContractCents": fees
        })

        a, b, c = st.columns(3)
        a.metric("Cost before fees", f'${plan["costBeforeFees"]:.2f}')
        b.metric("Maximum loss incl. fees",
                 f'${plan["maximumLossIncludingFees"]:.2f}')
        c.metric("Planned net P/L", f'${plan["plannedNetPnl"]:.2f}')

        st.json(plan)

    st.caption("Fees must be checked against the applicable Kalshi fee schedule.")

elif page == "Paper Journal":
    st.subheader("Paper-trading journal")

    if "journal" not in st.session_state:
        st.session_state.journal = []

    with st.form("paper_trade"):
        direction = st.selectbox("Direction", ["UP", "DOWN"])
        live_quote = quote_for_side(direction)
        default_entry = float(live_quote) if live_quote is not None else 50.0

        entry_cents = st.number_input(
            "Entry price (cents)", min_value=1.0,
            max_value=99.0, value=default_entry
        )
        quantity = st.number_input(
            "Contracts", min_value=1, value=1, step=1
        )
        note = st.text_input("Notes")
        submitted = st.form_submit_button("Record paper trade")

    if submitted:
        st.session_state.journal.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "direction": direction,
            "entry_cents": entry_cents,
            "contracts": int(quantity),
            "status": "OPEN",
            "notes": note
        })

    if st.session_state.journal:
        journal_df = pd.DataFrame(st.session_state.journal)
        st.dataframe(journal_df, use_container_width=True)

        csv = journal_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download paper journal CSV",
            data=csv,
            file_name="smurk_ai_paper_journal.csv",
            mime="text/csv"
        )

        if st.button("Clear paper journal"):
            st.session_state.journal = []
            st.rerun()
    else:
        st.info("No paper trades recorded yet.")

    st.caption(
        "Journal is stored in the current browser session. "
        "Download the CSV to keep a permanent copy."
    )

else:
    st.subheader("Settings")
    st.write("**Trading mode:** PAPER ONLY")
    st.write("**Live order placement:** Not implemented and disabled.")
    st.write("**Market refresh:** 30-second cache.")
    st.write("**Storage:** Browser session; CSV export available.")
    st.write("**Data providers:** Binance with Coinbase fallback; Kalshi public endpoints.")
    st.warning(
        "Do not enter Kalshi API secrets into this app. "
        "Authenticated order placement is not included."
    )
