"""vectorbt-backed backtest engine.

Strategies hand back a `(entry, exit)` boolean DataFrame; this wrapper feeds
them into `vbt.Portfolio.from_signals` and returns the metrics swing-traders
actually care about (Sharpe, CAGR, max drawdown, expectancy).
"""
from __future__ import annotations

from typing import Any, Callable, Union

import pandas as pd

# A strategy is either a function returning a DataFrame with `entry`/`exit`
# columns, or one returning just an `entry` boolean Series (we'll exit on the
# next bar in that case — useful for quick smoke tests).
StrategyFn = Callable[[pd.DataFrame], Union[pd.Series, pd.DataFrame]]


def run_backtest(
    df: pd.DataFrame,
    strategy_fn: StrategyFn,
    *,
    initial_cash: float = 10_000.0,
    fees: float = 0.0,
    slippage: float = 0.0005,
    freq: str = "1D",
) -> dict[str, Any]:
    """Run a vectorbt backtest and return summary metrics + equity curve.

    Returns a dict with: total_return, cagr, sharpe, max_drawdown, win_rate,
    expectancy, trade_count, equity_curve (list of {time, value}).
    """
    import vectorbt as vbt

    if df.empty:
        raise ValueError("Cannot backtest on empty DataFrame.")

    close = df["Close"] if "Close" in df.columns else df["close"]

    sig = strategy_fn(df)
    if isinstance(sig, pd.DataFrame):
        if "entry" not in sig or "exit" not in sig:
            raise ValueError("Strategy DataFrame must have `entry` and `exit` columns.")
        entries = sig["entry"].astype(bool)
        exits = sig["exit"].astype(bool)
    else:
        # Bare entry signal — exit on the next bar.
        entries = sig.astype(bool)
        exits = entries.shift(1, fill_value=False)

    pf = vbt.Portfolio.from_signals(
        close=close,
        entries=entries,
        exits=exits,
        init_cash=initial_cash,
        fees=fees,
        slippage=slippage,
        freq=freq,
    )

    trades = pf.trades.records_readable
    win_rate = float((trades["PnL"] > 0).mean()) if len(trades) else 0.0
    avg_win = float(trades.loc[trades["PnL"] > 0, "PnL"].mean()) if (trades["PnL"] > 0).any() else 0.0
    avg_loss = float(trades.loc[trades["PnL"] <= 0, "PnL"].mean()) if (trades["PnL"] <= 0).any() else 0.0
    expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

    equity = pf.value()
    equity_curve = [
        {"time": str(idx), "value": round(float(v), 2)}
        for idx, v in equity.items()
    ]

    return {
        "total_return": round(float(pf.total_return()) * 100, 2),
        "cagr": _safe_pct(pf.annualized_return()),
        "sharpe": _safe_round(pf.sharpe_ratio()),
        "max_drawdown": _safe_pct(pf.max_drawdown()),
        "trade_count": int(len(trades)),
        "win_rate": round(win_rate * 100, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy": round(expectancy, 2),
        "final_value": round(float(pf.final_value()), 2),
        "initial_cash": initial_cash,
        "equity_curve": equity_curve,
    }


def _safe_pct(v: Any) -> float:
    try:
        return round(float(v) * 100, 2)
    except (TypeError, ValueError):
        return 0.0


def _safe_round(v: Any, places: int = 2) -> float:
    try:
        return round(float(v), places)
    except (TypeError, ValueError):
        return 0.0
