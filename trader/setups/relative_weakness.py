"""Relative weakness vs SPY: underperformer over the last 20 days at new lows."""
from __future__ import annotations

from typing import Optional

import pandas as pd


def detect(df: pd.DataFrame, spy_df: Optional[pd.DataFrame] = None,
           lookback: int = 20, min_underperf: float = 0.05) -> Optional[dict]:
    """Flag if the ticker has underperformed SPY by >= min_underperf over the lookback
    window AND is making a new 20-day low."""
    if df.empty or len(df) < lookback + 1:
        return None
    if spy_df is None or spy_df.empty or len(spy_df) < lookback + 1:
        return None

    ticker_ret = (float(df.iloc[-1]["Close"]) - float(df.iloc[-lookback - 1]["Close"])) / float(df.iloc[-lookback - 1]["Close"])
    spy_ret = (float(spy_df.iloc[-1]["Close"]) - float(spy_df.iloc[-lookback - 1]["Close"])) / float(spy_df.iloc[-lookback - 1]["Close"])
    underperf = spy_ret - ticker_ret  # positive = SPY beat the ticker

    if underperf < min_underperf:
        return None

    last_close = float(df.iloc[-1]["Close"])
    prior_low = float(df.iloc[-lookback - 1:-1]["Low"].min())
    if last_close > prior_low:
        return None

    entry = last_close
    recent_high = float(df.iloc[-10:]["High"].max())
    stop = min(recent_high, entry * 1.07)
    if stop <= entry:
        return None
    target = entry * 0.90
    rr = (entry - target) / (stop - entry)
    return {
        "setup": "relative_weakness",
        "side": "sell",
        "ticker": "?",
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "risk_reward": round(rr, 2),
        "confidence": min(1.0, 0.55 + underperf * 2),
        "reason": f"Underperformed SPY by {underperf*100:.1f}% over {lookback}d, at new {lookback}d low",
    }
