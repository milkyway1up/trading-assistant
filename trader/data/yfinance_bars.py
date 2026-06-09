"""yfinance historical bars + SQLite cache. Phase 1 wraps this for UI use."""
from __future__ import annotations

from typing import Optional

import pandas as pd
import yfinance as yf
from loguru import logger


def fetch_bars(
    ticker: str,
    *,
    period: str = "2y",
    interval: str = "1d",
) -> pd.DataFrame:
    """Pull bars from yfinance. Returns an empty DF on failure."""
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
        return df
    except Exception as e:
        logger.warning("yfinance fetch failed for {} {}/{}: {}", ticker, period, interval, e)
        return pd.DataFrame()
