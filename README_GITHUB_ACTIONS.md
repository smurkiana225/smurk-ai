# SMURK AI — GitHub Actions scheduled scanner

This package adds a scheduled GitHub Actions scan to the existing `smurk-ai` repository.
It reuses the repository's existing `engine.py`; it does not replace `app.py` or `engine.py`.

## What it does
- Runs on GitHub's schedule every 5 minutes, and can also be started manually.
- Calls `engine.create_snapshot()` to fetch BTC 15-minute candles and the current public Kalshi BTC 15-minute market context.
- Saves the newest result to `data/latest_snapshot.json`.
- Appends each run to `data/scan_history.jsonl` and commits the updated data to `main`.
- Does not need Render, a Render worker, or a PostgreSQL database.

## Install from iPhone
1. In the existing GitHub repository `smurkiana225/smurk-ai`, open **Add file → Upload files**.
2. Upload `scheduled_scan.py` to the repository root.
3. Create the folder path `.github/workflows/` in GitHub (Add file → Create new file), and create `smurk-scan.yml` inside it using the exact contents of the included workflow file. Alternatively, upload the extracted `.github/workflows/smurk-scan.yml` if GitHub's upload UI preserves the folder path.
4. Commit both changes to `main`.
5. In GitHub, open **Settings → Actions → General → Workflow permissions** and select **Read and write permissions**, then Save. This allows the workflow to commit scan output.
6. Open the **Actions** tab, choose **SMURK AI scheduled scan**, and tap **Run workflow** once to test it.
7. Open the run and inspect the log. A successful run prints `SMURK scan saved`.
8. After it runs, `data/latest_snapshot.json` and `data/scan_history.jsonl` should appear in the repository.

## Important limits and trade-offs
- GitHub scheduled workflows are best-effort; they can start late, and GitHub says scheduled workflows run on the default branch. They are not a guaranteed real-time service.
- The schedule is every 5 minutes, which is the minimum GitHub Actions schedule interval.
- For a **public** repository, standard GitHub-hosted runner usage is free. For a **private** repository, usage counts against the account's included Actions minutes and billing limits. Check the repository visibility and account quota before leaving this on continuously.
- Each run writes a small data update to the repository. `scan_history.jsonl` grows over time; periodically archive or trim it if desired.
- This only creates background market scans and stores results. It does not place orders or guarantee fills or profitability.
- If the workflow cannot push, enable read/write workflow permissions as described above.
- Existing Streamlit app remains unchanged; its dashboard does not yet read `data/latest_snapshot.json`. The scan results are available in the GitHub repository until we connect the dashboard to them.
