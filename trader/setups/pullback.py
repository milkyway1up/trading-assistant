"""Uptrend pullback to EMA20/50 with RSI in 40-55 zone. Phase 2."""
from __future__ import annotations

from typing import Optional

import pandas as pd

from trader.indicators.compute import add_indicators


def detect(df: pd.DataFrame) -> Optional[dict]:
    """Detect a pullback: EMA50 > EMA200 (uptrend), price near EMA20 or EMA50,
    RSI in 40-55 (cooling but not broken). Triggers on first green bar off the EMA."""
    if df.empty or len(df) < 210:
        return None

    enriched = add_indicators(df)
    last = enriched.iloc[-1]
    prev = enriched.iloc[-2]

    ema_20 = last.get("ema_20")
    ema_50 = last.get("ema_50")
    ema_200 = last.get("ema_200")
    rsi = last.get("rsi_14")
    atr = last.get("atr_14")
    close = float(last["Close"])

    for v in (ema_20, ema_50, ema_200, rsi, atr):
        if v is None or v != v:  # NaN check
            return None

    if not (ema_50 > ema_200):
        return None
    if not (40 <= rsi <= 55):
        return None

    near_ema20 = abs(close - ema_20) / ema_20 < 0.02
    near_ema50 = abs(close - ema_50) / ema_50 < 0.02
    if not (near_ema20 or near_ema50):
        return None

    if not (close > float(prev["Close"]) and close > float(last["Open"])):
        return None

    entry = close
    stop = min(ema_50, close - 1.5 * atr)
    target = entry + (entry - stop) * 2.0
    rr = (target - entry) / (entry - stop) if entry > stop else 0
    return {
        "setup": "pullback",
        "ticker": "?",
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "risk_reward": round(rr, 2),
        "confidence": 0.6 + (50 - abs(rsi - 47.5)) * 0.005,
        "reason": f"Pullback to EMA{'20' if near_ema20 else '50'} in uptrend, RSI {rsi:.0f}",
    }
