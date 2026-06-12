"""Bear flag continuation pattern — sharp drop, tight consolidation, break lower."""
from __future__ import annotations

from typing import Optional

import pandas as pd


def detect(df: pd.DataFrame) -> Optional[dict]:
    """Detect a bear flag: sharp drop (pole) followed by 3-7 day tight consolidation
    on declining volume, then a break below the lower consolidation bound."""
    if df.empty or len(df) < 30:
        return None

    last = df.iloc[-1]
    consolidation = df.iloc[-7:-1]
    pre_pole = df.iloc[-30:-10]
    pole = df.iloc[-10:-7]

    pole_drop = (float(pole["Open"].iloc[0]) - float(pole["Close"].iloc[-1])) / float(pole["Open"].iloc[0])
    if pole_drop < 0.08:
        return None

    cons_high = float(consolidation["High"].max())
    cons_low = float(consolidation["Low"].min())
    cons_range_pct = (cons_high - cons_low) / cons_high
    if cons_range_pct > 0.08:
        return None

    avg_pre_vol = float(pre_pole["Volume"].mean())
    avg_cons_vol = float(consolidation["Volume"].mean())
    if avg_cons_vol >= avg_pre_vol:
        return None

    if float(last["Close"]) >= cons_low:
        return None

    entry = float(last["Close"])
    stop = cons_high
    target = entry - (stop - entry) * 2.5
    rr = (entry - target) / (stop - entry) if stop > entry else 0
    return {
        "setup": "bear_flag",
        "side": "sell",
        "ticker": "?",
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "risk_reward": round(rr, 2),
        "confidence": min(1.0, 0.55 + pole_drop),
        "reason": f"Bear flag breakdown: {pole_drop*100:.1f}% pole, "
                  f"{cons_range_pct*100:.1f}% tight consolidation",
    }
