# SMURK AI — always-on background scanner (paper mode)

## What this adds
- Runs independently of Streamlit/Safari; closing your phone does not stop the worker.
- Polls the existing `engine.create_snapshot()` on a server timer.
- Stores paper entries and worker heartbeat in PostgreSQL, not the browser session.
- One paper entry per unique Kalshi ticker, configurable risk/price/spread/indicator limits.
- Logs every scan decision so a WAIT/no-entry result is explainable.

## Important
This package is **paper-only**. It does not authenticate to Kalshi, submit orders, close positions, or guarantee profit. It is not real-money automation. Do not put Kalshi API keys into this worker. The app's current signal scores are not calibrated win probabilities.

## Files to add
Put `worker.py`, `requirements-worker.txt`, and `render.yaml` in the repository root beside the existing `engine.py` and `requirements.txt`. Do not replace `app.py` or `engine.py` for this step.

Add this line to the existing `requirements.txt` as well if the Render build installs only that file:
```
psycopg[binary]>=3.2,<4
```
The worker build command also installs `requirements-worker.txt`.

## Hosting requirement
A background worker must run on an always-on server. Streamlit Community Cloud does not keep a Python process alive after the browser session closes. Render Background Workers require a paid always-on instance; a PostgreSQL database is also required for persistent history. The included `render.yaml` defines a Starter worker. Create a PostgreSQL database and set its **internal** connection URL as `DATABASE_URL` in the worker's environment. Never paste database credentials or API secrets into GitHub.

## Deploy outline
1. Commit the three files to the root of the existing GitHub repo.
2. In Render, create a PostgreSQL database in the same region as the worker.
3. Create a new Blueprint from the GitHub repo, or create a Background Worker manually using:
   - Build: `pip install -r requirements.txt && pip install -r requirements-worker.txt`
   - Start: `python worker.py`
4. Set `DATABASE_URL` to the database's internal connection string. Keep the default risk settings initially.
5. Deploy and check the worker logs for `SMURK AI background scanner started`.
6. Confirm the worker logs update every 30 seconds and the PostgreSQL tables are created.
7. Leave the worker running. You may close Safari; the server process continues.

## Defaults and safeguards
- 30-second polling (minimum 15 seconds)
- 1 paper contract per entry
- Maximum 6 paper entries per UTC day
- $3 daily simulated loss stop
- Maximum entry ask: 80 cents
- Maximum spread: 2 cents
- At least 5 indicator checks
- At least 10 cents maximum potential payout after estimated fee

The fee is an estimate and must be checked against the applicable Kalshi fee schedule. The paper fill assumes the current ask; real fills can differ. This is a screening simulation, not evidence of an edge.

## Current limitation
This worker records paper entries and status in PostgreSQL. It does not yet settle outcomes or update the Streamlit dashboard from the database. That is the next integration step after the background worker is confirmed running.
