"""20-day / 52-week breakout with volume confirmation. Phase 2."""
from __future__ import annotations

from typing import Optional

import pandas as pd


def detect(df: pd.DataFrame) -> Optional[dict]:
    """Return a setup dict if today closes above 20-day high with > 1.3× avg volume."""
    if df.empty or len(df) < 21:
        return None
    last = df.iloc[-1]
    prior_20 = df.iloc[-21:-1]
    prior_high = float(prior_20["High"].max())
    avg_vol_20 = float(prior_20["Volume"].mean())

    if float(last["Close"]) > prior_high and float(last["Volume"]) > avg_vol_20 * 1.3:
        entry = float(last["Close"])
        # Stop = below the breakout level (recent pivot low or prior_high - 1 ATR)
        recent_low = float(prior_20["Low"].tail(5).min())
        stop = max(recent_low, entry * 0.96)
        target = entry * 1.08  # ~8% — typical first leg
        rr = (target - entry) / (entry - stop) if entry > stop else 0
        return {
            "setup": "breakout",
            "ticker": "?",
            "entry": round(entry, 2),
            "stop": round(stop, 2),
            "target": round(target, 2),
            "risk_reward": round(rr, 2),
            "confidence": min(1.0, 0.5 + (float(last["Volume"]) / avg_vol_20 - 1.3) * 0.2),
            "reason": f"Closed above 20-day high {prior_high:.2f} on {last['Volume']/avg_vol_20:.1f}× avg volume",
        }
    return None
