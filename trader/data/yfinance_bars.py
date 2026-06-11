"""yfinance historical bars — backstop for when no broker is configured.

The primary data path is `trader.broker.factory.get_data_client()`; this
module is only used as a fallback (and by the scanner when the broker
data path 404s on a less-liquid ticker).
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf
from loguru import logger

# Map our internal timeframes → yfinance (interval, default period).
_YF_INTERVALS: dict[str, tuple[str, str]] = {
    "1m": ("1m", "5d"),
    "5m": ("5m", "1mo"),
    "15m": ("15m", "1mo"),
    "1h": ("60m", "3mo"),
    "4h": ("60m", "6mo"),
    "1d": ("1d", "2y"),
}


def fetch_bars(
    ticker: str,
    *,
    period: str = "2y",
    interval: str = "1d",
) -> pd.DataFrame:
    """Pull bars from yfinance directly. Returns an empty DF on failure."""
    try:
        df = yf.Ticker(ticker).history(
            period=period, interval=interval, auto_adjust=False,
        )
        return df
    except Exception as e:
        logger.warning(
            "yfinance fetch failed for {} {}/{}: {}", ticker, period, interval, e,
        )
        return pd.DataFrame()


def get_bars(
    ticker: str,
    *,
    timeframe: str = "1d",
    period: str | None = None,
) -> pd.DataFrame:
    """Wrapper that takes our internal timeframe codes (1m/5m/15m/1h/4h/1d).

    Used by the scanner so it doesn't have to know about yfinance's interval
    syntax.
    """
    if timeframe not in _YF_INTERVALS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    interval, default_period = _YF_INTERVALS[timeframe]
    return fetch_bars(ticker, period=period or default_period, interval=interval)
