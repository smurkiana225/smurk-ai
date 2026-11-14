import streamlit as st
import pandas as pd
from datetime import datetime, timezone
import engine
import json
from pathlib import Path

st.set_page_config(page_title="SMURK AI", page_icon="₿", layout="wide")

# ---------- Styling ----------
st.markdown("""
<style>
.stApp {background:#090d16;color:#f4f6fb;}
.block-container {padding-top:1.2rem;max-width:1400px;}
[data-testid="stMetric"] {background:#121a29;border:1px solid #263247;padding:14px;border-radius:12px;}
section[data-testid="stSidebar"] {background:#101827;}
.small {color:#9ba9bd;font-size:.88rem;}
div[data-testid="stAlert"] {border-radius:12px;}
</style>
""", unsafe_allow_html=True)

st.title("₿ SMURK AI")
st.caption("Bitcoin 15-minute market analysis • Kalshi public-market context • Paper trading")

# ---------- Sidebar / refresh ----------
with st.sidebar:
    st.subheader("SMURK AI")
    page = st.radio(
        "Navigation",
        ["Overview", "Background Scanner", "Technical Analysis", "Kalshi Market", "Trade Planner", "Paper Journal", "Settings"]
    )
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
    st.info("Try Refresh market data. SMURK AI does not substitute simulated prices when a provider is unavailable.")
    st.stop()

ind = snapshot["indicators"]
market = snapshot["kalshi"]
signal = snapshot["signal"]

st.caption(
    f"Data: {snapshot.get('source', 'Unknown')} • "
    f"Updated: {snapshot.get('asOf', 'Unknown')} • "
    f"Status: {snapshot.get('dataStatus', 'Unknown')}"
)

# ---------- Small helpers ----------
def money(value):
    return "—" if value is None else f"${float(value):,.2f}"

def cents(value):
    return "—" if value is None else f"{float(value):.2f}¢"

def current_ask(direction):
    if not market or market.get("status") != "live":
        return None
    key = "yesAskCents" if direction == "UP" else "noAskCents"
    value = market.get(key)
    return None if value is None else float(value)

def market_countdown(close_time):
    if not close_time:
        return None
    try:
        end = pd.to_datetime(close_time, utc=True).to_pydatetime()
        now = datetime.now(timezone.utc)
        seconds = max(0, int((end - now).total_seconds()))
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except Exception:
        return None

# ---------- GitHub Actions background scans ----------
def read_background_data():
    root = Path(__file__).resolve().parent / "data"
    latest, history = None, []
    try:
        latest = json.loads((root / "latest_snapshot.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    try:
        for line in (root / "scan_history.jsonl").read_text(encoding="utf-8").splitlines()[-200:]:
            try:
                history.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass
    return latest, history

def unwrap_scan(record):
    if not isinstance(record, dict):
        return {}
    for key in ("snapshot", "data", "result"):
        if isinstance(record.get(key), dict) and "signal" in record[key]:
            return record[key]
    return record

# ---------- Overview ----------
if page == "Background Scanner":
    st.subheader("Scheduled background scans")
    latest, history = read_background_data()
    if latest is None:
        st.warning("No saved scan file found yet at data/latest_snapshot.json. Check GitHub Actions' latest successful run.")
    else:
        scan = unwrap_scan(latest)
        scan_time = (latest.get("scannedAt") or latest.get("timestamp") or latest.get("asOf")
                     or scan.get("asOf") or "Not recorded")
        st.write("**Last recorded scan:**", scan_time)
        a, b, c = st.columns(3)
        a.metric("BTC / USD", money(scan.get("price")))
        b.metric("Saved signal", str(scan.get("signal", "Unavailable")).replace("_", " "))
        c.metric("Kalshi ticker", str((scan.get("kalshi") or {}).get("ticker") or "Unavailable"))
        if latest.get("error"):
            st.warning(str(latest["error"]))
        for reason in scan.get("reasons", []):
            st.write("• " + str(reason))
    st.subheader("Recent scan history")
    if history:
        rows = []
        for record in reversed(history):
            snap = unwrap_scan(record)
            rows.append({
                "Scanned at (UTC)": record.get("scannedAt") or record.get("timestamp") or snap.get("asOf"),
                "BTC price": snap.get("price"),
                "Signal": snap.get("signal"),
                "Kalshi ticker": (snap.get("kalshi") or {}).get("ticker"),
                "Error": record.get("error"),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download scan history CSV", df.to_csv(index=False).encode("utf-8"),
                           file_name="smurk_scan_history.csv", mime="text/csv")
    else:
        st.info("No scan history found yet at data/scan_history.jsonl.")
    st.caption("Background scans are produced by GitHub Actions even when the app is closed. GitHub's scheduled runs can be delayed.")

elif page == "Overview":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BTC / USD", money(snapshot.get("price")), f'{snapshot.get("priceChange24h", 0):+.2f}% (24h)')
    c2.metric("Directional signal", str(signal).replace("_", " "))
    c3.metric("RSI (14)", "N/A" if ind.get("rsi") is None else f'{ind["rsi"]:.1f}')
    c4.metric("Trend", str(ind.get("trend", "Unknown")).title())

    st.subheader("15-minute Bitcoin candles")
    candles = pd.DataFrame(snapshot.get("candles", []))
    if not candles.empty and {"time", "close"}.issubset(candles.columns):
        candles["time"] = pd.to_datetime(candles["time"], utc=True)
        candles = candles.sort_values("time").set_index("time")
        st.line_chart(candles["close"], height=300)
    else:
        st.info("Candle data is not available right now.")

    st.subheader("Signal assessment")
    if signal == "BUY_UP":
        st.success("BUY UP signal — bullish indicator conditions. Research only; not a guaranteed outcome.")
    elif signal == "BUY_DOWN":
        st.error("BUY DOWN signal — bearish indicator conditions. Research only; not a guaranteed outcome.")
    else:
        st.warning("WAIT — current conditions do not meet the strategy's confirmation rules.")

    checks = snapshot.get("checks")
    if isinstance(checks, dict):
        passed = sum(bool(v) for v in checks.values())
        st.write(f"**Indicator checks:** {passed} of {len(checks)}")
    for reason in snapshot.get("reasons", []):
        st.write("• " + str(reason))
    st.caption(snapshot.get("disclaimer", "Signals are research indicators, not verified win probabilities."))

# ---------- Technical analysis ----------
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

    candles = pd.DataFrame(snapshot.get("candles", []))
    if not candles.empty and {"time", "close"}.issubset(candles.columns):
        candles["time"] = pd.to_datetime(candles["time"], utc=True)
        st.line_chart(candles.sort_values("time").set_index("time")["close"])

# ---------- Kalshi market ----------
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
        st.caption("Quotes can change quickly. Confirm the exact market, price, and order book in Kalshi before making any decision.")

# ---------- Trade planner ----------
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
    st.caption("Enter the applicable Kalshi fee estimate yourself; zero is not a confirmation that a trade is fee-free.")

    if st.button("Calculate contract risk", type="primary"):
        plan = engine.create_risk_plan({
            "side": side,
            "contracts": int(contracts),
            "entryPriceCents": float(entry),
            "plannedExitPriceCents": float(exit_price),
            "feePerContractCents": float(fees)
        })
        a, b, c = st.columns(3)
        a.metric("Cost before fees", money(plan.get("costBeforeFees")))
        b.metric("Maximum loss incl. fees", money(plan.get("maximumLossIncludingFees")))
        c.metric("Planned net P/L", money(plan.get("plannedNetPnl")))
        st.json(plan)

# ---------- Paper journal ----------
elif page == "Paper Journal":
    st.subheader("Paper-trading journal")
    if "journal" not in st.session_state:
        st.session_state.journal = []

    with st.form("paper_trade"):
        direction = st.selectbox("Direction", ["UP", "DOWN"])
        live_ask = current_ask(direction)
        default_journal_entry = 50.0 if live_ask is None else min(99.0, max(1.0, live_ask))
        if live_ask is not None:
            st.caption(f"Current {direction} ask: {live_ask:.2f}¢")
        entry_cents = st.number_input(
            "Entry price (cents)", min_value=1.0, max_value=99.0,
            value=float(default_journal_entry), step=0.5
        )
        quantity = st.number_input("Contracts", min_value=1, max_value=10000, value=1, step=1)
        note = st.text_input("Notes")
        submitted = st.form_submit_button("Record paper trade")

    if submitted:
        st.session_state.journal.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "direction": direction,
            "entry_cents": float(entry_cents),
            "contracts": int(quantity),
            "status": "OPEN",
            "notes": note
        })
        st.success("Paper trade recorded in this session.")

    if st.session_state.journal:
        journal_df = pd.DataFrame(st.session_state.journal)
        st.dataframe(journal_df, use_container_width=True)
        csv_data = journal_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download paper journal CSV",
            data=csv_data,
            file_name="smurk_ai_paper_journal.csv",
            mime="text/csv"
        )
        if st.button("Clear paper journal"):
            st.session_state.journal = []
            st.rerun()
    else:
        st.info("No paper trades recorded yet.")

    st.caption("The journal is held in the current app session. Download the CSV regularly to keep a permanent copy.")

# ---------- Settings ----------
else:
    st.subheader("Settings")
    st.write("**Trading mode:** PAPER ONLY")
    st.write("**Live order placement:** Not implemented and disabled.")
    st.write("**Market refresh:** 15-second cache; use Refresh market data for an immediate request.")
    st.write("**Journal storage:** Current app session; export CSV to keep a copy.")
    st.write("**Data providers:** Binance with Coinbase fallback; Kalshi public market endpoints.")
    st.warning("Never enter Kalshi API secrets into this app. Authenticated order placement is not included.")
    st.caption("Directional signals are not verified win probabilities and do not guarantee profit.")
