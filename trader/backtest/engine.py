"""vectorbt backtest engine wrapper. Phase 6."""
from __future__ import annotations

from typing import Callable

import pandas as pd


def run_backtest(df: pd.DataFrame, strategy_fn: Callable[[pd.DataFrame], pd.Series],
                 initial_cash: float = 10_000) -> dict:
    """Run a backtest. `strategy_fn(df) -> entries (boolean Series)`.
    Returns Sharpe / CAGR / max drawdown / equity curve.

    Wired in Phase 6.
    """
    raise NotImplementedError("vectorbt backtest engine — wired in Phase 6.")
