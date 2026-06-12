"""20-day breakdown with volume confirmation — bearish counterpart to breakout."""
from __future__ import annotations

from typing import Optional

import pandas as pd


def detect(df: pd.DataFrame) -> Optional[dict]:
    """Return a setup dict if today closes below 20-day low with > 1.3× avg volume."""
    if df.empty or len(df) < 21:
        return None
    last = df.iloc[-1]
    prior_20 = df.iloc[-21:-1]
    prior_low = float(prior_20["Low"].min())
    avg_vol_20 = float(prior_20["Volume"].mean())

    if float(last["Close"]) < prior_low and float(last["Volume"]) > avg_vol_20 * 1.3:
        entry = float(last["Close"])
        recent_high = float(prior_20["High"].tail(5).max())
        stop = min(recent_high, entry * 1.04)
        target = entry * 0.92
        rr = (entry - target) / (stop - entry) if stop > entry else 0
        return {
            "setup": "breakdown",
            "side": "sell",
            "ticker": "?",
            "entry": round(entry, 2),
            "stop": round(stop, 2),
            "target": round(target, 2),
            "risk_reward": round(rr, 2),
            "confidence": min(1.0, 0.5 + (float(last["Volume"]) / avg_vol_20 - 1.3) * 0.2),
            "reason": f"Closed below 20-day low {prior_low:.2f} on "
                      f"{last['Volume']/avg_vol_20:.1f}× avg volume",
        }
    return None
