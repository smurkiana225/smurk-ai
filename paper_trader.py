"""Automatic paper-trade helper for SMURK AI. Public data only; no order execution."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import urllib.request
import urllib.parse

BASE = "https://api.elections.kalshi.com/trade-api/v2"

def _get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "SMURK-AI-paper/1.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode("utf-8"))

def make_trade(ticker, side, ask_cents, contracts, fee_cents, btc_price, signal, agreement, close_time, title=None):
    return {
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker, "title": title or "", "side": side,
        "ask_cents": round(float(ask_cents), 2), "contracts": int(contracts),
        "fee_cents": round(float(fee_cents), 4),
        "btc_price": btc_price, "signal": signal, "agreement": int(agreement),
        "close_time": close_time, "status": "OPEN", "settlement": None,
        "net_pnl_dollars": None,
        "note": "Simulated at displayed ask; excludes slippage. Fee is user estimate."
    }

def resolve_trades(trades):
    """Resolve only when Kalshi's public market endpoint reports a final result."""
    updated = []
    for original in trades:
        trade = dict(original)
        if trade.get("status") != "OPEN":
            updated.append(trade)
            continue
        try:
            ticker = urllib.parse.quote(str(trade["ticker"]), safe="")
            payload = _get(f"{BASE}/markets/{ticker}")
            market = payload.get("market", payload)
            status = str(market.get("status", "")).lower()
            result = str(market.get("result", "")).lower()
            if status in {"settled", "finalized"} and result in {"yes", "no"}:
                won = (result == "yes" and trade["side"] == "UP") or (result == "no" and trade["side"] == "DOWN")
                entry = float(trade["ask_cents"]) / 100.0
                fee = float(trade.get("fee_cents", 0)) / 100.0
                qty = int(trade.get("contracts", 1))
                pnl = ((1.0 - entry) if won else -entry) * qty - fee * qty
                trade.update({
                    "status": "SETTLED", "settlement": result.upper(),
                    "net_pnl_dollars": round(pnl, 4),
                    "settled_at": datetime.now(timezone.utc).isoformat()
                })
        except Exception as exc:
            trade["resolution_check"] = f"Pending/unavailable: {str(exc)[:120]}"
        updated.append(trade)
    return updated
