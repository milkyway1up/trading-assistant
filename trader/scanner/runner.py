"""Run setup detectors across the universe and rank candidates. Phase 2."""
from __future__ import annotations

from typing import Callable, Optional

import pandas as pd

from trader.data.yfinance_bars import get_bars
from trader.scanner.universe import universe_with_watchlist
from trader.setups import breakout, earnings_runner, flag, pullback, relative_strength, reversal

SetupFn = Callable[[pd.DataFrame], Optional[dict]]

_DEFAULT_SETUPS: list[tuple[str, SetupFn]] = [
    ("breakout", breakout.detect),
    ("flag", flag.detect),
    ("pullback", pullback.detect),
    ("earnings_runner", earnings_runner.detect),
    ("reversal", reversal.detect),
]


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
            out.append(result)
    if spy_df is not None:
        try:
            rs = relative_strength.detect(df, spy_df)
            if rs:
                rs["ticker"] = ticker
                out.append(rs)
        except Exception:
            pass
    return out


def run_scan(watchlist: list[str], timeframe: str = "1d", lookback_days: int = 250) -> list[dict]:
    """Run all setup detectors against the universe; return ranked list."""
    universe = universe_with_watchlist(watchlist)
    spy_df = get_bars("SPY", period=f"{lookback_days}d", interval=timeframe)
    candidates: list[dict] = []
    for ticker in universe:
        try:
            df = get_bars(ticker, period=f"{lookback_days}d", interval=timeframe)
        except Exception:
            continue
        if df.empty:
            continue
        for setup in scan_ticker(ticker, df, spy_df=spy_df):
            candidates.append(setup)

    candidates.sort(
        key=lambda s: (s.get("confidence", 0), s.get("risk_reward", 0)),
        reverse=True,
    )
    return candidates
