"""Overbought rejection in downtrend — bearish counterpart to reversal."""
from __future__ import annotations

from typing import Optional

import pandas as pd

from trader.indicators.compute import add_indicators


def detect(df: pd.DataFrame) -> Optional[dict]:
    """Detect an overbought rejection in a downtrend: RSI > 65, EMA50 < EMA200,
    today closes below yesterday's low (first sign of rejection)."""
    if df.empty or len(df) < 210:
        return None

    enriched = add_indicators(df)
    last = enriched.iloc[-1]
    prev = enriched.iloc[-2]

    rsi = last.get("rsi_14")
    ema_50 = last.get("ema_50")
    ema_200 = last.get("ema_200")
    atr = last.get("atr_14")
    close = float(last["Close"])

    for v in (rsi, ema_50, ema_200, atr):
        if v is None or v != v:
            return None

    if rsi <= 65:
        return None
    if ema_50 >= ema_200:
        return None  # need a downtrend
    if close >= float(prev["Low"]):
        return None

    entry = close
    stop = float(df.iloc[-10:]["High"].max())
    if stop <= entry:
        return None
    target = entry - (stop - entry) * 1.8
    rr = (entry - target) / (stop - entry)
    return {
        "setup": "overbought_reversal",
        "side": "sell",
        "ticker": "?",
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "risk_reward": round(rr, 2),
        "confidence": 0.55 + (rsi - 65) * 0.01,
        "reason": f"Overbought rejection in downtrend, RSI {rsi:.0f}, EMA50 < EMA200",
    }
