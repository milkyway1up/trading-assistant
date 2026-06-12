"""Run setup detectors across the universe and rank candidates."""
from __future__ import annotations

from typing import Callable, Optional

import pandas as pd
from loguru import logger

from trader.data.yfinance_bars import get_bars as yf_get_bars
from trader.scanner.universe import universe_with_watchlist
from trader.setups import (
    bear_flag,
    breakdown,
    breakout,
    earnings_runner,
    flag,
    overbought_reversal,
    pullback,
    relative_strength,
    relative_weakness,
    reversal,
)

SetupFn = Callable[[pd.DataFrame], Optional[dict]]

_DEFAULT_SETUPS: list[tuple[str, SetupFn]] = [
    # Long setups
    ("breakout", breakout.detect),
    ("flag", flag.detect),
    ("pullback", pullback.detect),
    ("earnings_runner", earnings_runner.detect),
    ("reversal", reversal.detect),
    # Short setups
    ("breakdown", breakdown.detect),
    ("bear_flag", bear_flag.detect),
    ("overbought_reversal", overbought_reversal.detect),
]


def _lookback_to_period(days: int) -> str:
    """Translate a day-count to a yfinance-acceptable period string."""
    if days <= 31:
        return "1mo"
    if days <= 91:
        return "3mo"
    if days <= 181:
        return "6mo"
    if days <= 366:
        return "1y"
    if days <= 732:
        return "2y"
    return "5y"


def _fetch_bars(ticker: str, *, timeframe: str, period: str) -> pd.DataFrame:
    """Prefer the configured broker data client; fall back to yfinance on failure."""
    try:
        from trader.broker.factory import get_data_client
        df = get_data_client().get_price_history(ticker, timeframe=timeframe, period=period)
        if df is not None and not df.empty:
            return df
    except NotImplementedError:
        pass
    except Exception as e:
        logger.debug("Broker data fetch failed for {} ({}): {}", ticker, timeframe, e)
    return yf_get_bars(ticker, timeframe=timeframe, period=period)


def scan_ticker(ticker: str, df: pd.DataFrame,
                setups: Optional[list[tuple[str, SetupFn]]] = None,
                spy_df: Optional[pd.DataFrame] = None) -> list[dict]:
    setups = setups or _DEFAULT_SETUPS
    out: list[dict] = []
    for name, fn in setups:
        try:
            result = fn(df)
        except Exception:
            continue
        if result:
            result["ticker"] = ticker
            result.setdefault("setup", name)
            out.append(result)
    if spy_df is not None:
        try:
            rs = relative_strength.detect(df, spy_df)
            if rs:
                rs["ticker"] = ticker
                rs.setdefault("setup", "relative_strength")
                out.append(rs)
        except Exception:
            pass
        try:
            rw = relative_weakness.detect(df, spy_df)
            if rw:
                rw["ticker"] = ticker
                rw.setdefault("setup", "relative_weakness")
                out.append(rw)
        except Exception:
            pass
    return out


def run_scan(
    watchlist: Optional[list[str]] = None,
    *,
    timeframe: str = "1d",
    lookback_days: int = 250,
    setup: Optional[str] = None,
    min_confidence: float = 0.0,
) -> list[dict]:
    """Run all setup detectors across the universe; return ranked list.

    `watchlist` is unioned with the default universe. If None, pulls the
    configured watchlist from `trader.config`.
    `setup` filters to a single setup name (matches the names in `_DEFAULT_SETUPS`).
    `min_confidence` drops candidates below the threshold.
    """
    if watchlist is None:
        try:
            from trader.config import get_config
            watchlist = list(get_config().watchlist)
        except Exception:
            watchlist = []

    period = _lookback_to_period(lookback_days)
    universe = universe_with_watchlist(watchlist)

    setups = _DEFAULT_SETUPS
    if setup:
        setups = [(n, fn) for n, fn in _DEFAULT_SETUPS if n == setup]

    spy_df = _fetch_bars("SPY", timeframe=timeframe, period=period)
    if spy_df.empty:
        spy_df = None  # don't run relative_strength without a benchmark

    candidates: list[dict] = []
    for ticker in universe:
        df = _fetch_bars(ticker, timeframe=timeframe, period=period)
        if df.empty:
            continue
        for s in scan_ticker(ticker, df, setups=setups, spy_df=spy_df):
            if s.get("confidence", 0) >= min_confidence:
                candidates.append(s)

    candidates.sort(
        key=lambda s: (s.get("confidence", 0), s.get("risk_reward", 0)),
        reverse=True,
    )
    return candidates
