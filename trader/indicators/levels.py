"""Support / resistance + pivot point detection. Phase 1."""
from __future__ import annotations

import pandas as pd


def recent_swing_highs(df: pd.DataFrame, lookback: int = 5, n: int = 5) -> list[float]:
    """Naive swing-high detector: a bar is a swing high if it's the max of
    `lookback` bars on both sides. Returns the most recent N."""
    if df.empty or "High" not in df:
        return []
    highs = df["High"].to_numpy()
    out: list[float] = []
    for i in range(lookback, len(highs) - lookback):
        window = highs[i - lookback : i + lookback + 1]
        if highs[i] == window.max():
            out.append(float(highs[i]))
    return out[-n:]


def recent_swing_lows(df: pd.DataFrame, lookback: int = 5, n: int = 5) -> list[float]:
    if df.empty or "Low" not in df:
        return []
    lows = df["Low"].to_numpy()
    out: list[float] = []
    for i in range(lookback, len(lows) - lookback):
        window = lows[i - lookback : i + lookback + 1]
        if lows[i] == window.min():
            out.append(float(lows[i]))
    return out[-n:]
