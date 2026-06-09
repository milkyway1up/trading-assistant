"""EMA20 pullback swing strategy. Phase 6."""
from __future__ import annotations

import pandas as pd

from trader.indicators.compute import add_indicators


def signals(df: pd.DataFrame) -> pd.DataFrame:
    """Return DataFrame with `entry` and `exit` boolean columns.

    Entry: EMA50 > EMA200, close pulls within 1% of EMA20, RSI 40-55, today closes green.
    Exit: close < EMA50, or RSI > 75.
    """
    enriched = add_indicators(df).copy()
    enriched["uptrend"] = enriched["ema_50"] > enriched["ema_200"]
    enriched["near_ema20"] = (enriched["Close"] - enriched["ema_20"]).abs() / enriched["ema_20"] < 0.01
    enriched["rsi_band"] = enriched["rsi_14"].between(40, 55)
    enriched["green"] = enriched["Close"] > enriched["Open"]

    enriched["entry"] = (
        enriched["uptrend"] & enriched["near_ema20"] & enriched["rsi_band"] & enriched["green"]
    )
    enriched["exit"] = (enriched["Close"] < enriched["ema_50"]) | (enriched["rsi_14"] > 75)
    return enriched[["entry", "exit"]]
