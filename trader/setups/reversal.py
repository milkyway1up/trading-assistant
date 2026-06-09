"""Mean-reversion: daily RSI < 30 on a name in long-term uptrend. Phase 2."""
from __future__ import annotations

from typing import Optional

import pandas as pd

from trader.indicators.compute import add_indicators


def detect(df: pd.DataFrame) -> Optional[dict]:
    """Detect oversold reversal in uptrend: RSI<30, price > EMA200, today closes
    above yesterday's high (first sign of bounce)."""
    if df.empty or len(df) < 210:
        return None

    enriched = add_indicators(df)
    last = enriched.iloc[-1]
    prev = enriched.iloc[-2]

    rsi = last.get("rsi_14")
    ema_200 = last.get("ema_200")
    atr = last.get("atr_14")
    close = float(last["Close"])

    for v in (rsi, ema_200, atr):
        if v is None or v != v:
            return None

    if rsi >= 35:
        return None
    if close <= ema_200:
        return None
    if close <= float(prev["High"]):
        return None

    entry = close
    stop = float(df.iloc[-10:]["Low"].min())
    target = entry + (entry - stop) * 1.8
    rr = (target - entry) / (entry - stop) if entry > stop else 0
    return {
        "setup": "reversal",
        "ticker": "?",
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "risk_reward": round(rr, 2),
        "confidence": 0.55 + (35 - rsi) * 0.01,
        "reason": f"Oversold reversal in uptrend, RSI {rsi:.0f}, price > EMA200",
    }
