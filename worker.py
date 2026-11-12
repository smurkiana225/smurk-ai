#!/usr/bin/env python3
"""
SMURK AI always-on background scanner.
Runs independently of Streamlit. PAPER MODE ONLY: never submits Kalshi orders.
Requires the existing engine.py in the same repository root.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import time
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

import engine

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("smurk-worker")

DATABASE_URL = os.environ["DATABASE_URL"]
POLL_SECONDS = max(15, int(os.getenv("POLL_SECONDS", "30")))
MAX_ENTRIES_PER_DAY = max(0, int(os.getenv("MAX_PAPER_ENTRIES_PER_DAY", "6")))
MAX_DAILY_LOSS_USD = max(0.0, float(os.getenv("MAX_DAILY_PAPER_LOSS_USD", "3")))
CONTRACTS = max(1, int(os.getenv("PAPER_CONTRACTS", "1")))
FEE_CENTS = max(0.0, float(os.getenv("ESTIMATED_FEE_CENTS", "1")))
MAX_ENTRY_ASK_CENTS = min(99.0, max(1.0, float(os.getenv("MAX_ENTRY_ASK_CENTS", "80"))))
MAX_SPREAD_CENTS = max(0.0, float(os.getenv("MAX_SPREAD_CENTS", "2")))
MIN_CHECKS = min(6, max(1, int(os.getenv("MIN_INDICATOR_CHECKS", "5"))))
MIN_REWARD_CENTS = max(0.0, float(os.getenv("MIN_MAX_PROFIT_CENTS", "10")))

_running = True

def stop(*_: Any) -> None:
    global _running
    _running = False

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)


def connect():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=10)


def init_db() -> None:
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS smurk_worker_status (
                id INTEGER PRIMARY KEY,
                state TEXT NOT NULL,
                last_scan_at TIMESTAMPTZ,
                last_message TEXT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS smurk_paper_trades (
                id BIGSERIAL PRIMARY KEY,
                ticker TEXT NOT NULL UNIQUE,
                side TEXT NOT NULL,
                entry_cents DOUBLE PRECISION NOT NULL,
                contracts INTEGER NOT NULL,
                estimated_fee_cents DOUBLE PRECISION NOT NULL,
                max_loss_usd DOUBLE PRECISION NOT NULL,
                max_profit_usd DOUBLE PRECISION NOT NULL,
                signal TEXT NOT NULL,
                up_score INTEGER,
                down_score INTEGER,
                opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                close_time TIMESTAMPTZ,
                status TEXT NOT NULL DEFAULT 'OPEN',
                settled_at TIMESTAMPTZ,
                settlement_result TEXT,
                realized_pnl_usd DOUBLE PRECISION
            )
        """)
        conn.execute("""
            INSERT INTO smurk_worker_status (id, state, last_message)
            VALUES (1, 'STARTING', 'Worker initialized')
            ON CONFLICT (id) DO NOTHING
        """)


def set_status(state: str, message: str) -> None:
    with connect() as conn:
        conn.execute("""
            INSERT INTO smurk_worker_status (id, state, last_scan_at, last_message, updated_at)
            VALUES (1, %s, NOW(), %s, NOW())
            ON CONFLICT (id) DO UPDATE SET
              state = EXCLUDED.state,
              last_scan_at = NOW(),
              last_message = EXCLUDED.last_message,
              updated_at = NOW()
        """, (state, message[:500]))


def get_daily_totals() -> tuple[int, float]:
    with connect() as conn:
        row = conn.execute("""
            SELECT COUNT(*) AS n,
                   COALESCE(SUM(GREATEST(0, -COALESCE(realized_pnl_usd, 0))), 0) AS losses
            FROM smurk_paper_trades
            WHERE opened_at >= date_trunc('day', NOW())
        """).fetchone()
    return int(row["n"]), float(row["losses"])


def has_ticker(ticker: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM smurk_paper_trades WHERE ticker = %s", (ticker,)
        ).fetchone()
    return row is not None


def indicator_checks(snapshot: dict) -> int:
    checks = snapshot.get("checks") or {}
    if isinstance(checks, dict) and checks:
        return sum(1 for v in checks.values() if bool(v))
    return int(snapshot.get("signalStrength") or 0)


def consider_snapshot(snapshot: dict) -> str:
    market = snapshot.get("kalshi") or {}
    signal = str(snapshot.get("signal") or "WAIT").upper()
    if market.get("status") != "live":
        return f"Market unavailable: {market.get('error') or market.get('status')}"
    ticker = market.get("ticker")
    if not ticker:
        return "Live market response had no ticker"
    if signal not in {"BUY_UP", "BUY_DOWN"}:
        return f"No entry: signal {signal}"
    checks = indicator_checks(snapshot)
    if checks < MIN_CHECKS:
        return f"No entry: {checks}/{MIN_CHECKS} indicator checks"
    side = "UP" if signal == "BUY_UP" else "DOWN"
    ask_key = "yesAskCents" if side == "UP" else "noAskCents"
    bid_key = "yesBidCents" if side == "UP" else "noBidCents"
    ask, bid = market.get(ask_key), market.get(bid_key)
    if ask is None or bid is None:
        return f"No entry: {side} quote incomplete"
    ask, bid = float(ask), float(bid)
    spread = ask - bid
    if not (0 < ask < 100):
        return "No entry: invalid ask"
    if ask > MAX_ENTRY_ASK_CENTS:
        return f"No entry: ask {ask:.2f}¢ exceeds limit"
    if spread < 0 or spread > MAX_SPREAD_CENTS:
        return f"No entry: spread {spread:.2f}¢ exceeds limit"
    max_profit_cents = 100 - ask - FEE_CENTS
    if max_profit_cents < MIN_REWARD_CENTS:
        return f"No entry: max payout {max_profit_cents:.2f}¢ below threshold"
    if has_ticker(ticker):
        return "No entry: this ticker was already recorded"
    count, loss_total = get_daily_totals()
    if count >= MAX_ENTRIES_PER_DAY:
        return "Daily paper-entry limit reached"
    if loss_total >= MAX_DAILY_LOSS_USD:
        return "Daily simulated loss stop reached"
    cost = CONTRACTS * ask / 100
    fees = CONTRACTS * FEE_CENTS / 100
    max_loss = cost + fees
    max_profit = CONTRACTS * (100 - ask - FEE_CENTS) / 100
    with connect() as conn:
        conn.execute("""
            INSERT INTO smurk_paper_trades
              (ticker, side, entry_cents, contracts, estimated_fee_cents,
               max_loss_usd, max_profit_usd, signal, up_score, down_score, close_time)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (ticker) DO NOTHING
        """, (
            ticker, side, ask, CONTRACTS, FEE_CENTS, max_loss, max_profit,
            signal, snapshot.get("upScore"), snapshot.get("downScore"),
            market.get("closeTime"),
        ))
    return f"PAPER ENTRY RECORDED: {side} {ticker} at {ask:.2f}¢; max loss ${max_loss:.2f}"


def main() -> None:
    init_db()
    log.info("SMURK AI background scanner started. PAPER MODE ONLY.")
    set_status("RUNNING", "Always-on scanner started; no live orders are enabled")
    while _running:
        try:
            snapshot = engine.create_snapshot()
            message = consider_snapshot(snapshot)
            log.info(message)
            set_status("RUNNING", message)
        except Exception as exc:
            log.exception("Scan failed")
            try:
                set_status("ERROR", f"{type(exc).__name__}: {exc}")
            except Exception:
                log.exception("Could not write worker status")
        # Sleep in short increments so SIGTERM can stop promptly.
        for _ in range(POLL_SECONDS):
            if not _running:
                break
            time.sleep(1)
    set_status("STOPPED", "Worker received a shutdown signal")
    log.info("SMURK AI background scanner stopped.")


if __name__ == "__main__":
    main()
