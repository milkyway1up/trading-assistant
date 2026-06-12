"""Backtest endpoints."""
from __future__ import annotations

import asyncio
import importlib
import pkgutil
from typing import Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

router = APIRouter(tags=["backtest"])


@router.get("/backtest/strategies")
async def list_strategies() -> dict:
    """Discover available strategies in trader.backtest.strategies."""
    import trader.backtest.strategies as pkg

    names = []
    for mod_info in pkgutil.iter_modules(pkg.__path__):
        if not mod_info.name.startswith("_"):
            names.append(mod_info.name)
    return {"strategies": sorted(names)}


class BacktestRequest(BaseModel):
    strategy: str
    ticker: str = "SPY"
    period: str = "5y"
    initial_cash: float = 10_000.0


@router.post("/backtest/run")
async def run(req: BacktestRequest) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run_sync, req)


def _run_sync(req: BacktestRequest) -> dict:
    from trader.backtest.engine import run_backtest
    from trader.data.yfinance_bars import get_bars

    try:
        module = importlib.import_module(f"trader.backtest.strategies.{req.strategy}")
    except ImportError as e:
        raise HTTPException(status_code=404, detail=f"Strategy not found: {e}")

    strategy_fn = getattr(module, "signals", None) or getattr(module, "strategy", None)
    if strategy_fn is None:
        raise HTTPException(
            status_code=400,
            detail="Strategy module needs a `signals(df)` or `strategy(df)` function.",
        )

    df = get_bars(req.ticker.upper(), timeframe="1d", period=req.period)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No bars for {req.ticker}")

    try:
        result = run_backtest(df, strategy_fn, initial_cash=req.initial_cash)
    except Exception as e:
        logger.exception("backtest failed")
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "strategy": req.strategy,
        "ticker": req.ticker.upper(),
        "period": req.period,
        **result,
    }
