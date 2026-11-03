"""Persistent paper-trade storage for SMURK AI.

Uses SQLite on the app host. Set SMURK_DB_PATH to a persistent mounted disk
path on hosts that support one. Streamlit Community Cloud local storage can be
replaced during redeploy/restart; use an external database for durable history.
"""
from __future__ import annotations
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = os.environ.get("SMURK_DB_PATH", "smurk_ai_trades.sqlite3")


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS trades (
        trade_id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL,
        opened_at TEXT NOT NULL,
        status TEXT NOT NULL,
        payload TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_opened ON trades(opened_at)")
    conn.commit()
    return conn


def save_trades(trades):
    if not trades:
        return
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for trade in trades:
        item = dict(trade)
        trade_id = str(item.get("trade_id") or f"{item.get('ticker','')}_{item.get('opened_at','')}")
        item["trade_id"] = trade_id
        rows.append((trade_id, str(item.get("ticker", "")), str(item.get("opened_at", now)),
                     str(item.get("status", "OPEN")), json.dumps(item), now))
    with _connect() as conn:
        conn.executemany("""INSERT INTO trades(trade_id,ticker,opened_at,status,payload,updated_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(trade_id) DO UPDATE SET
            status=excluded.status,payload=excluded.payload,updated_at=excluded.updated_at""", rows)


def load_trades():
    with _connect() as conn:
        rows = conn.execute("SELECT payload FROM trades ORDER BY opened_at DESC").fetchall()
    result = []
    for (payload,) in rows:
        try:
            result.append(json.loads(payload))
        except (TypeError, json.JSONDecodeError):
            continue
    return result


def clear_trades():
    with _connect() as conn:
        conn.execute("DELETE FROM trades")
        conn.commit()
