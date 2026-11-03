SMURK AI — LIVE REFRESH + TRADE VAULT UPDATE

UPLOAD THESE FILES TO THE ROOT OF THE EXISTING GITHUB REPOSITORY:
- app.py (replace existing)
- paper_trader.py (replace existing)
- trade_store.py (new file)
- requirements.txt (merge these dependencies into your existing file; do not remove dependencies required by engine.py)

KEEP your existing engine.py and any other project files. This ZIP intentionally does not replace engine.py.

WHAT'S NEW
1. Auto Paper Trader now uses a timed 15-second Streamlit refresh while that page is open and the session remains active. The scan and settlement checks run again on each refresh.
2. New Trade Vault navigation page shows all saved automatic paper trades, open/settled filters, winners/losers, win rate, settled simulated P/L, and one all-time CSV export.
3. Automatic paper trades are stored in SQLite and reloaded after normal app reruns. Existing trade IDs are tracked to reduce duplicate entries after a session refresh.

IMPORTANT HOSTING / PERSISTENCE LIMITS
- SQLite saves across reruns while the same app disk remains available. Some hosted Streamlit deployments can replace local files on rebuild/restart. For durable history across redeployments, set SMURK_DB_PATH to a persistent mounted disk path or connect an external database in a future upgrade.
- Streamlit Community Cloud does not keep this scanner running after the app session/page stops. This update does NOT create an always-on background worker.
- A separate always-on worker/backend is required for scanning while the app is closed. iPhone Lock Screen Live Activities also require a native iOS component and push-notification backend; this update does not claim to provide that yet.

PAPER-TRADING SAFETY
- PAPER ONLY. No Kalshi authentication or real order placement is implemented.
- Simulated fills use the displayed ask and user-entered fee estimate; real fills can differ due to depth, latency, and slippage.
- The signal score is not a calibrated probability or proof of an edge. No profit is guaranteed. Keep real-money automation disabled until extensive testing and independent review.

REQUIREMENTS TO MERGE
streamlit>=1.32
pandas>=2.0
plotly>=5.18
streamlit-autorefresh>=1.0.1
