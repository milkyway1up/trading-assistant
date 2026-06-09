"""Relative strength vs SPY: outperformer over the last 20 days. Phase 2."""
from __future__ import annotations

from typing import Optional

import pandas as pd


def detect(df: pd.DataFrame, spy_df: Optional[pd.DataFrame] = None,
           lookback: int = 20, min_outperf: float = 0.05) -> Optional[dict]:
    """Flag the ticker if it has outperformed SPY by >= min_outperf over the lookback
    window AND is making a new 20-day high."""
    if df.empty or len(df) < lookback + 1:
        return None
    if spy_df is None or spy_df.empty or len(spy_df) < lookback + 1:
        return None

    ticker_ret = (float(df.iloc[-1]["Close"]) - float(df.iloc[-lookback - 1]["Close"])) / float(df.iloc[-lookback - 1]["Close"])
    spy_ret = (float(spy_df.iloc[-1]["Close"]) - float(spy_df.iloc[-lookback - 1]["Close"])) / float(spy_df.iloc[-lookback - 1]["Close"])
    outperf = ticker_ret - spy_ret

    if outperf < min_outperf:
        return None

    last_close = float(df.iloc[-1]["Close"])
    prior_high = float(df.iloc[-lookback - 1:-1]["High"].max())
    if last_close < prior_high:
        return None

    entry = last_close
    recent_low = float(df.iloc[-10:]["Low"].min())
    stop = max(recent_low, entry * 0.93)
    target = entry * 1.10
    rr = (target - entry) / (entry - stop) if entry > stop else 0
    return {
        "setup": "relative_strength",
        "ticker": "?",
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "risk_reward": round(rr, 2),
        "confidence": min(1.0, 0.55 + outperf * 2),
        "reason": f"Outperformed SPY by {outperf*100:.1f}% over {lookback}d, at new {lookback}d high",
    }
