"""Quote + bar endpoints. Falls back to yfinance when Schwab not configured."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["quotes"])

Timeframe = Literal["1m", "5m", "15m", "1h", "4h", "1d"]

# Map our timeframe → (yfinance interval, period)
_YF_PARAMS: dict[str, tuple[str, str]] = {
    "1m": ("1m", "5d"),
    "5m": ("5m", "1mo"),
    "15m": ("15m", "1mo"),
    "1h": ("60m", "3mo"),
    "4h": ("60m", "6mo"),  # yfinance has no native 4h; client can roll up
    "1d": ("1d", "2y"),
}


@router.get("/bars/{ticker}")
async def get_bars(ticker: str, timeframe: Timeframe = "1d") -> dict:
    """Return OHLCV bars for a ticker at the requested timeframe.

    Tries the configured broker's data client (Alpaca by default) → yfinance
    → deterministic mock data, so the dashboard always has something to render.
    """
    ticker = ticker.upper()
    loop = asyncio.get_running_loop()

    try:
        return await loop.run_in_executor(None, _broker_bars, ticker, timeframe)
    except Exception as e:
        broker_err = str(e)

    try:
        return await loop.run_in_executor(None, _yfinance_bars, ticker, timeframe)
    except Exception as e:
        return {
            "ticker": ticker,
            "timeframe": timeframe,
            "source": "mock",
            "error": f"broker={broker_err}; yfinance={e}",
            "bars": _mock_bars(ticker, timeframe),
        }


@router.get("/quote/{ticker}")
async def get_quote(ticker: str) -> dict:
    """Latest quote (last price + day change). Tries broker → yfinance → mock."""
    ticker = ticker.upper()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _get_quote_sync, ticker)


def _get_quote_sync(ticker: str) -> dict:
    try:
        from trader.broker.factory import get_data_client
        return get_data_client().get_quote(ticker)
    except Exception as broker_err:
        try:
            import yfinance as yf
            info = yf.Ticker(ticker).fast_info
            last = float(info.get("last_price") or info.get("lastPrice") or 0)
            prev = float(info.get("previous_close") or info.get("previousClose") or 0)
            chg = last - prev
            chg_pct = (chg / prev * 100.0) if prev else 0.0
            return {
                "ticker": ticker,
                "price": round(last, 2),
                "change": round(chg, 2),
                "change_pct": round(chg_pct, 2),
                "source": "yfinance",
                "ts": time.time(),
            }
        except Exception as yf_err:
            return _mock_quote(ticker, error=f"broker={broker_err}; yfinance={yf_err}")


def _broker_bars(ticker: str, timeframe: str) -> dict:
    from trader.broker.factory import get_data_client

    period = _YF_PARAMS[timeframe][1]  # reuse our period mapping
    df = get_data_client().get_price_history(ticker, timeframe=timeframe, period=period)
    if df.empty:
        raise ValueError(f"No bars from broker for {ticker} {timeframe}")
    return _df_to_bars_response(ticker, timeframe, df, source="broker")


def _yfinance_bars(ticker: str, timeframe: str) -> dict:
    import yfinance as yf

    interval, period = _YF_PARAMS[timeframe]
    df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
    if df.empty:
        raise ValueError(f"No data from yfinance for {ticker} {timeframe}")
    return _df_to_bars_response(ticker, timeframe, df, source="yfinance")


def _df_to_bars_response(ticker: str, timeframe: str, df, source: str) -> dict:
    bars = []
    for idx, row in df.iterrows():
        ts = int(idx.timestamp()) if hasattr(idx, "timestamp") else int(time.time())
        bars.append({
            "time": ts,
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row.get("Volume", 0) or 0),
        })
    return {
        "ticker": ticker,
        "timeframe": timeframe,
        "source": source,
        "bars": bars,
    }


def _mock_bars(ticker: str, timeframe: str) -> list[dict]:
    """Deterministic but plausible-looking mock OHLCV for offline testing."""
    import math
    import random

    seed = sum(ord(c) for c in ticker)
    rng = random.Random(seed)

    n = 200
    interval_seconds = {
        "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400,
    }[timeframe]

    end = int(time.time())
    start = end - interval_seconds * n

    base = 50 + (seed % 200)  # ticker-stable starting price
    bars = []
    price = base
    for i in range(n):
        # gentle trend + noise
        drift = math.sin(i / 20.0) * 0.5
        change_pct = rng.uniform(-1.0, 1.0) + drift
        new_price = max(1, price * (1 + change_pct / 100))
        high = max(price, new_price) * (1 + rng.uniform(0, 0.5) / 100)
        low = min(price, new_price) * (1 - rng.uniform(0, 0.5) / 100)
        bars.append({
            "time": start + i * interval_seconds,
            "open": round(price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(new_price, 2),
            "volume": int(rng.uniform(500_000, 5_000_000)),
        })
        price = new_price
    return bars


def _mock_quote(ticker: str, error: str = "") -> dict:
    bars = _mock_bars(ticker, "1d")
    last = bars[-1]["close"]
    prev = bars[-2]["close"]
    chg = last - prev
    return {
        "ticker": ticker,
        "price": round(last, 2),
        "change": round(chg, 2),
        "change_pct": round(chg / prev * 100, 2) if prev else 0.0,
        "source": "mock",
        "error": error,
        "ts": time.time(),
    }
