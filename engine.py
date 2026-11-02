#!/usr/bin/env python3
"""
SMURK AI market-analysis engine.

Commands:
  python engine.py snapshot
  python engine.py risk   # reads a JSON risk-plan request from stdin

Uses public market-data endpoints only. It does NOT place Kalshi orders.
All timestamps are UTC. Market data and indicators are informational, not
a guarantee of direction or profitability.
"""
from __future__ import annotations

import json
import math
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

USER_AGENT = "SMURK-AI/2.0 (public market data)"
KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
TIMEOUT = 10


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _binance_candles(interval: str, limit: int = 100) -> list[dict]:
    query = urllib.parse.urlencode(
        {"symbol": "BTCUSDT", "interval": interval, "limit": limit}
    )
    rows = fetch_json(f"https://api.binance.com/api/v3/klines?{query}")
    result = []
    current_ms = int(now_utc().timestamp() * 1000)
    for row in rows:
        # Ignore the still-forming candle to avoid using incomplete data.
        if int(row[6]) > current_ms:
            continue
        result.append({
            "time": iso_utc(datetime.fromtimestamp(row[0] / 1000, timezone.utc)),
            "open": float(row[1]), "high": float(row[2]),
            "low": float(row[3]), "close": float(row[4]),
            "volume": float(row[5]),
        })
    return result


def _coinbase_candles(granularity: int = 900, limit: int = 100) -> list[dict]:
    rows = fetch_json(
        "https://api.exchange.coinbase.com/products/BTC-USD/candles?"
        + urllib.parse.urlencode({"granularity": granularity})
    )
    # Coinbase format: [time, low, high, open, close, volume], newest first.
    result = []
    for row in reversed(rows[:limit]):
        result.append({
            "time": iso_utc(datetime.fromtimestamp(row[0], timezone.utc)),
            "open": float(row[3]), "high": float(row[2]),
            "low": float(row[1]), "close": float(row[4]),
            "volume": float(row[5]),
        })
    return result


def get_btc_data() -> tuple[list[dict], float, float, str]:
    errors = []
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            candles_future = pool.submit(_binance_candles, "15m", 100)
            ticker_future = pool.submit(
                fetch_json,
                "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT",
            )
            candles = candles_future.result()
            ticker = ticker_future.result()
        if len(candles) < 55:
            raise RuntimeError("Binance returned too few completed candles")
        return candles, float(ticker["lastPrice"]), float(ticker["priceChangePercent"]), "Binance"
    except Exception as exc:
        errors.append(f"Binance: {exc}")

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            candles_future = pool.submit(_coinbase_candles, 900, 100)
            stats_future = pool.submit(
                fetch_json, "https://api.exchange.coinbase.com/products/BTC-USD/stats"
            )
            candles = candles_future.result()
            stats = stats_future.result()
        last = float(stats["last"])
        opening = float(stats["open"])
        change = ((last - opening) / opening * 100) if opening else 0.0
        if len(candles) < 55:
            raise RuntimeError("Coinbase returned too few candles")
        return candles, last, change, "Coinbase"
    except Exception as exc:
        errors.append(f"Coinbase: {exc}")

    raise RuntimeError("BTC data unavailable. " + " | ".join(errors))


def ema_series(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1.0 - alpha) * result[-1])
    return result


def rsi_value(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    window = changes[-period:]
    avg_gain = sum(max(x, 0.0) for x in window) / period
    avg_loss = sum(max(-x, 0.0) for x in window) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    if avg_gain == 0:
        return 0.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def macd(values: list[float]) -> dict:
    fast = ema_series(values, 12)
    slow = ema_series(values, 26)
    line = [a - b for a, b in zip(fast, slow)]
    signal_line = ema_series(line, 9)
    hist = line[-1] - signal_line[-1]
    return {
        "line": line[-1], "signal": signal_line[-1], "histogram": hist,
        "direction": "bullish" if hist > 0 else "bearish" if hist < 0 else "neutral",
    }


def _cents(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    # Fixed-point dollar fields are strings like "0.5300".
    return round(number * 100.0, 2)


def kalshi_market() -> dict:
    empty = {
        "status": "unavailable", "ticker": None, "title": None,
        "yesBidCents": None, "yesAskCents": None,
        "noBidCents": None, "noAskCents": None,
        "yesDepth": None, "noDepth": None, "spreadCents": None,
        "closeTime": None, "error": None,
    }
    try:
        query = urllib.parse.urlencode(
            {"series_ticker": "KXBTC15M", "status": "open", "limit": 100}
        )
        payload = fetch_json(f"{KALSHI_BASE}/markets?{query}")
        markets = payload.get("markets", []) if isinstance(payload, dict) else []
        current = now_utc()
        candidates = []
        for market in markets:
            close_text = market.get("close_time") or market.get("expected_expiration_time")
            if not close_text:
                continue
            close = datetime.fromisoformat(close_text.replace("Z", "+00:00"))
            if close >= current:
                candidates.append((close, market))
        if not candidates:
            empty["status"] = "no_market"
            return empty

        close, market = min(candidates, key=lambda item: item[0])
        ticker = market["ticker"]
        book_payload = fetch_json(
            f"{KALSHI_BASE}/markets/{urllib.parse.quote(ticker, safe='')}/orderbook"
        )
        book = book_payload.get("orderbook_fp", book_payload.get("orderbook", {}))
        yes_levels = book.get("yes_dollars", book.get("yes", [])) or []
        no_levels = book.get("no_dollars", book.get("no", [])) or []

        yes_bid = _cents(market.get("yes_bid_dollars"))
        no_bid = _cents(market.get("no_bid_dollars"))
        yes_ask = _cents(market.get("yes_ask_dollars"))
        no_ask = _cents(market.get("no_ask_dollars"))

        # Fallback to order book ladders. A bid on one side implies the
        # complementary ask on the other side, subject to the contract rules.
        if yes_bid is None and yes_levels:
            yes_bid = _cents(yes_levels[0][0])
        if no_bid is None and no_levels:
            no_bid = _cents(no_levels[0][0])
        if yes_ask is None and no_bid is not None:
            yes_ask = round(100.0 - no_bid, 2)
        if no_ask is None and yes_bid is not None:
            no_ask = round(100.0 - yes_bid, 2)

        spread = (
            round(yes_ask - yes_bid, 2)
            if yes_ask is not None and yes_bid is not None and yes_ask >= yes_bid
            else None
        )
        return {
            "status": "live", "ticker": ticker,
            "title": market.get("title") or market.get("subtitle"),
            "yesBidCents": yes_bid, "yesAskCents": yes_ask,
            "noBidCents": no_bid, "noAskCents": no_ask,
            "yesDepth": sum(float(level[1]) for level in yes_levels[:5]) if yes_levels else 0.0,
            "noDepth": sum(float(level[1]) for level in no_levels[:5]) if no_levels else 0.0,
            "spreadCents": spread, "closeTime": iso_utc(close), "error": None,
        }
    except Exception as exc:
        empty["error"] = str(exc)[:240]
        return empty


def build_signal(closes: list[float], candles: list[dict], market: dict) -> tuple[str, str, int, list[str]]:
    fast = ema_series(closes, 9)[-1]
    medium = ema_series(closes, 21)[-1]
    slow = ema_series(closes, 50)[-1]
    rsi = rsi_value(closes)
    macd_data = macd(closes)
    momentum = (closes[-1] / closes[-2] - 1.0) * 100.0 if closes[-2] else 0.0

    up = down = 0
    reasons: list[str] = []
    if fast > medium > slow:
        up += 2
        reasons.append("EMA 9 > EMA 21 > EMA 50 (bullish alignment)")
    elif fast < medium < slow:
        down += 2
        reasons.append("EMA 9 < EMA 21 < EMA 50 (bearish alignment)")
    else:
        reasons.append("EMA alignment is mixed")

    if closes[-1] > fast:
        up += 1
        reasons.append("BTC close is above EMA 9")
    elif closes[-1] < fast:
        down += 1
        reasons.append("BTC close is below EMA 9")

    if rsi is not None:
        if 52 <= rsi <= 68:
            up += 1
            reasons.append("RSI supports positive momentum")
        elif 32 <= rsi <= 48:
            down += 1
            reasons.append("RSI supports negative momentum")
        elif rsi >= 70:
            reasons.append("RSI is elevated; avoid chasing strength")
        elif rsi <= 30:
            reasons.append("RSI is depressed; downside may be extended")

    if macd_data["histogram"] > 0:
        up += 1
        reasons.append("MACD histogram is positive")
    elif macd_data["histogram"] < 0:
        down += 1
        reasons.append("MACD histogram is negative")

    if momentum > 0.03:
        up += 1
        reasons.append("Last completed 15-minute candle momentum is positive")
    elif momentum < -0.03:
        down += 1
        reasons.append("Last completed 15-minute candle momentum is negative")

    avg_volume = sum(c["volume"] for c in candles[-21:-1]) / max(1, len(candles[-21:-1]))
    volume_ratio = candles[-1]["volume"] / avg_volume if avg_volume > 0 else 0.0
    if volume_ratio >= 1.2 and momentum > 0:
        up += 1
        reasons.append("Above-average volume accompanies positive momentum")
    elif volume_ratio >= 1.2 and momentum < 0:
        down += 1
        reasons.append("Above-average volume accompanies negative momentum")
    else:
        reasons.append("Volume does not provide strong confirmation")

    # Kalshi order-book depth is contextual only; it is not treated as proof
    # of the underlying BTC direction.
    if market.get("status") == "live":
        spread = market.get("spreadCents")
        if spread is not None and spread > 10:
            reasons.append("Kalshi spread is wide; execution costs may be high")

    difference = up - down
    if up >= 5 and difference >= 3:
        signal, direction = "BUY_UP", "bullish"
    elif down >= 5 and difference <= -3:
        signal, direction = "BUY_DOWN", "bearish"
    else:
        signal, direction = "WAIT", "neutral"

    # A wide spread or missing live Kalshi market prevents an actionable
    # Kalshi entry recommendation, even if spot indicators lean one way.
    if market.get("status") != "live":
        signal = "WAIT"
        reasons.append("No verified live Kalshi market is available; no entry")
    elif market.get("spreadCents") is not None and market["spreadCents"] > 15:
        signal = "WAIT"
        reasons.append("Signal held at WAIT because the Kalshi spread exceeds 15¢")

    return signal, direction, max(up, down), reasons[:10]


def create_snapshot() -> dict:
    candles, live_price, change_24h, source = get_btc_data()
    closes = [c["close"] for c in candles]
    market = kalshi_market()
    signal, trend, strength, reasons = build_signal(closes, candles, market)
    rsi = rsi_value(closes)
    ema9 = ema_series(closes, 9)[-1]
    ema21 = ema_series(closes, 21)[-1]
    ema50 = ema_series(closes, 50)[-1]
    macd_data = macd(closes)
    average_volume = sum(c["volume"] for c in candles[-21:-1]) / max(1, len(candles[-21:-1]))
    volume_ratio = candles[-1]["volume"] / average_volume if average_volume else 0.0
    momentum = (closes[-1] / closes[-2] - 1.0) * 100.0 if closes[-2] else 0.0

    return {
        "price": live_price,
        "priceChange24h": change_24h,
        "asOf": iso_utc(now_utc()),
        "source": source,
        "dataStatus": "live",
        "candles": candles[-90:],
        "indicators": {
            "rsi": rsi, "ema9": ema9, "ema21": ema21, "ema50": ema50,
            "macd": macd_data, "volumeRatio": volume_ratio,
            "momentumPct": momentum, "trend": trend,
        },
        "signal": signal,
        # Deliberately do not manufacture a win probability from indicator votes.
        "confidence": None,
        "signalStrength": strength,
        "reasons": reasons,
        "kalshi": market,
        "tradingMode": "PAPER_ONLY",
        "liveTradingEnabled": False,
        "disclaimer": "Directional indicators are not verified win probabilities. No orders are placed.",
    }


def create_risk_plan(data: dict) -> dict:
    """Calculate Kalshi binary-contract risk, not BTC spot-price risk."""
    side = str(data.get("side", "")).upper()
    if side not in {"UP", "DOWN"}:
        raise ValueError("side must be UP or DOWN")

    contracts = int(data.get("contracts", 1))
    entry_cents = float(data["entryPriceCents"])
    exit_cents = float(data.get("plannedExitPriceCents", 100 if side == "UP" else 0))
    fee_per_contract_cents = float(data.get("feePerContractCents", 0))

    if contracts < 1:
        raise ValueError("contracts must be at least 1")
    if not (0 < entry_cents < 100 and 0 <= exit_cents <= 100):
        raise ValueError("contract prices must be between 0 and 100 cents")

    cost = contracts * entry_cents / 100.0
    gross_payout = contracts * exit_cents / 100.0
    fees = contracts * fee_per_contract_cents / 100.0
    net_pnl = gross_payout - cost - fees
    max_loss = cost + fees
    max_profit = contracts * (1.0 - entry_cents / 100.0) - fees
    return {
        "contracts": contracts,
        "entryPriceCents": round(entry_cents, 2),
        "plannedExitPriceCents": round(exit_cents, 2),
        "costBeforeFees": round(cost, 2),
        "estimatedFees": round(fees, 2),
        "maximumLossIncludingFees": round(max_loss, 2),
        "maximumProfitAtSettlementAfterFees": round(max_profit, 2),
        "plannedNetPnl": round(net_pnl, 2),
        "rewardRisk": round(net_pnl / max_loss, 3) if max_loss > 0 else None,
        "note": "Fee estimate must be supplied from the applicable Kalshi fee schedule. Actual fills can differ.",
    }


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    if command == "risk":
        result = create_risk_plan(json.load(sys.stdin))
    elif command == "snapshot":
        result = create_snapshot()
    else:
        raise ValueError("Unknown command. Use snapshot or risk.")
    print(json.dumps(result, separators=(",", ":"), allow_nan=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"error": str(exc)[:500]}), file=sys.stderr)
        sys.exit(1)
