# SMURK AI — rebuilt starter app

A mobile-friendly Streamlit dashboard for BTC 15-minute technical analysis,
Kalshi public-market context, a binary-contract risk calculator, and a
session-based paper journal.

## Run locally
```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Deploy free (subject to provider limits)
Push this folder to a GitHub repository, then deploy `app.py` with Streamlit
Community Cloud. The app uses public endpoints and does not need API keys.

## Safety and limitations
- This is a signal/research and paper-trading tool, not financial advice.
- Directional indicator scores are not verified win probabilities.
- Kalshi public market discovery can fail or change; the dashboard reports
  unavailable data rather than inventing quotes.
- Real-money Kalshi order placement is NOT implemented.
- Paper journal currently lives in the browser session and may reset.
- Public API availability and free hosting uptime are not guaranteed.
