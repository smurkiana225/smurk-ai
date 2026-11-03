SMURK AI AUTOMATIC PAPER TRADER

Upload app.py and paper_trader.py to the ROOT of the existing smurk-ai GitHub repository, replacing app.py and adding paper_trader.py. Do not delete engine.py or requirements.txt.

WHAT IT DOES
- Adds an Auto Paper Trader page.
- While the page is open and the Streamlit session remains active, each app refresh can scan the current BTC 15-minute Kalshi market.
- Records at most one simulated entry per market ticker.
- Simulates fills at the displayed ask, tracks estimated fees, and checks Kalshi's public market endpoint for final YES/NO settlement.
- Includes configurable contract count, fee estimate, maximum ask, maximum spread, indicator agreement threshold, daily trade limit, and daily simulated loss stop.
- CSV export preserves a copy of results.

IMPORTANT LIMITATIONS
- PAPER ONLY. It does not authenticate to Kalshi or submit/cancel orders.
- Streamlit Community Cloud is not a continuously running background worker. Scanning only occurs while the app page/session is active and refreshed; closing the app, sleeping the phone, or losing the session stops scanning.
- The paper journal is held in the Streamlit session and may be lost if the session restarts. Download the CSV regularly.
- Simulated fills at the displayed ask may differ from real fills due to latency, depth, and slippage.
- A signal score is not a calibrated probability. The default filters are experimental and do not establish a profitable edge. No profit is guaranteed.
- Keep real-money automation disabled until extensive out-of-sample testing and a separate security-reviewed execution service exist.
