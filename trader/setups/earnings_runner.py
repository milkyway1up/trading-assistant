"""Post-earnings continuation: gap up >5% on earnings day, day-1 close green,
scan for day-2/3 follow-through. Phase 2."""
from __future__ import annotations

from typing import Optional

import pandas as pd


def detect(df: pd.DataFrame, earnings_date_idx: Optional[int] = None) -> Optional[dict]:
    """Detect post-earnings runner. If `earnings_date_idx` is provided as a positional
    index into df, evaluate days +1 and +2 after that bar. Otherwise look for a recent
    >5% gap up with green close in the last 4 bars."""
    if df.empty or len(df) < 5:
        return None

    if earnings_date_idx is None:
        for i in range(len(df) - 4, len(df) - 1):
            if i <= 0:
                continue
            prev_close = float(df.iloc[i - 1]["Close"])
            o = float(df.iloc[i]["Open"])
            c = float(df.iloc[i]["Close"])
            if (o - prev_close) / prev_close > 0.05 and c > o:
                earnings_date_idx = i
                break

    if earnings_date_idx is None:
        return None

    days_since = len(df) - 1 - earnings_date_idx
    if days_since < 1 or days_since > 3:
        return None

    earnings_bar = df.iloc[earnings_date_idx]
    last = df.iloc[-1]
    earnings_high = float(earnings_bar["High"])
    earnings_low = float(earnings_bar["Low"])

    if float(last["Close"]) <= earnings_high:
        return None

    entry = float(last["Close"])
    stop = earnings_low
    target = entry + (entry - stop) * 2.0
    rr = (target - entry) / (entry - stop) if entry > stop else 0
    return {
        "setup": "earnings_runner",
        "ticker": "?",
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "risk_reward": round(rr, 2),
        "confidence": 0.6,
        "reason": f"Post-earnings continuation, day +{days_since}, breaking earnings-day high {earnings_high:.2f}",
    }
