"""Indicator computation via pandas-ta. Phase 1 wires this end-to-end."""
from __future__ import annotations

import pandas as pd

try:
    import pandas_ta as ta
    _PTA_AVAILABLE = True
except ImportError:
    _PTA_AVAILABLE = False


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add RSI(14), EMA(20/50/200), ATR(14), MACD, Bollinger to a bars DataFrame.

    Expects columns: Open, High, Low, Close, Volume.
    """
    if not _PTA_AVAILABLE or df.empty:
        return df

    out = df.copy()
    out["rsi_14"] = ta.rsi(out["Close"], length=14)
    out["ema_20"] = ta.ema(out["Close"], length=20)
    out["ema_50"] = ta.ema(out["Close"], length=50)
    out["ema_200"] = ta.ema(out["Close"], length=200)
    out["atr_14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)

    macd = ta.macd(out["Close"], fast=12, slow=26, signal=9)
    if macd is not None and not macd.empty:
        out["macd"] = macd.iloc[:, 0]
        out["macd_signal"] = macd.iloc[:, 2] if macd.shape[1] >= 3 else None

    return out


def latest_indicator_snapshot(df: pd.DataFrame) -> dict:
    """Returns the last row of indicator values as a dict (for alert rule eval)."""
    if df.empty:
        return {}
    enriched = add_indicators(df)
    last = enriched.iloc[-1]
    return {
        "price": float(last.get("Close", 0)),
        "open": float(last.get("Open", 0)),
        "high": float(last.get("High", 0)),
        "low": float(last.get("Low", 0)),
        "close": float(last.get("Close", 0)),
        "volume": float(last.get("Volume", 0)),
        "rsi_14": float(last.get("rsi_14", 0)) if last.get("rsi_14") == last.get("rsi_14") else None,
        "ema_20": float(last.get("ema_20", 0)) if last.get("ema_20") == last.get("ema_20") else None,
        "ema_50": float(last.get("ema_50", 0)) if last.get("ema_50") == last.get("ema_50") else None,
        "ema_200": float(last.get("ema_200", 0)) if last.get("ema_200") == last.get("ema_200") else None,
        "atr_14": float(last.get("atr_14", 0)) if last.get("atr_14") == last.get("atr_14") else None,
        "macd": float(last.get("macd", 0)) if last.get("macd") == last.get("macd") else None,
        "macd_signal": float(last.get("macd_signal", 0)) if last.get("macd_signal") == last.get("macd_signal") else None,
    }
