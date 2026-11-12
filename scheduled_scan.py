#!/usr/bin/env python3
"""Run one SMURK public-market scan and save its output for the dashboard."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import engine

DATA_DIR = Path("data")
LATEST = DATA_DIR / "latest_snapshot.json"
HISTORY = DATA_DIR / "scan_history.jsonl"


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    scanned_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    try:
        snapshot = engine.create_snapshot()
        record = {
            "scanStatus": "success",
            "scannedAt": scanned_at,
            "snapshot": snapshot,
        }
        exit_code = 0
    except Exception as exc:
        record = {
            "scanStatus": "error",
            "scannedAt": scanned_at,
            "error": str(exc)[:500],
        }
        exit_code = 1

    serialized = json.dumps(record, separators=(",", ":"), allow_nan=False)
    LATEST.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(serialized + "\n")

    if exit_code:
        print(f"SMURK scan failed: {record['error']}", file=sys.stderr)
    else:
        snap = record["snapshot"]
        print(
            f"SMURK scan saved | BTC=${snap.get('price')} | "
            f"signal={snap.get('signal')} | market={snap.get('kalshi', {}).get('ticker')}"
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
