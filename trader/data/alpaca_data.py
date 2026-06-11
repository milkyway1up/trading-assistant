"""Alpaca market-data client.

Pulls historical bars + latest quotes from Alpaca's data API and exposes a
real-time tick stream over WebSocket. Defaults to the IEX feed (free tier);
set feed=DataFeed.SIP in requests if you have a paid data subscription.

Docs: https://alpaca.markets/docs/api-references/market-data-api/
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

import pandas as pd
from loguru import logger

from trader.broker.base import DataClient


# Map our timeframe strings → (alpaca-py TimeFrame, default lookback)
_TIMEFRAME_LOOKBACK: dict[str, tuple[int, str]] = {
    "1m": (1, "Minute"),
    "5m": (5, "Minute"),
    "15m": (15, "Minute"),
    "1h": (1, "Hour"),
    "4h": (4, "Hour"),
    "1d": (1, "Day"),
}


def _period_to_start(period: str, end: datetime) -> datetime:
    """Translate '2y'/'6mo'/'1mo'/'5d' style strings to a start datetime."""
    p = period.strip().lower()
    if p.endswith("y"):
        days = int(float(p[:-1]) * 365)
    elif p.endswith("mo"):
        days = int(float(p[:-2]) * 30)
    elif p.endswith("w"):
        days = int(float(p[:-1]) * 7)
    elif p.endswith("d"):
        days = int(float(p[:-1]))
    elif p.endswith("h"):
        return end - timedelta(hours=int(float(p[:-1])))
    else:
        days = 365
    return end - timedelta(days=days)


class AlpacaDataClient(DataClient):
    def __init__(self, api_key: str, secret_key: str) -> None:
        if not api_key or not secret_key:
            raise ValueError("Alpaca API key/secret missing.")
        from alpaca.data.historical import StockHistoricalDataClient

        self._api_key = api_key
        self._secret_key = secret_key
        self._client = StockHistoricalDataClient(api_key, secret_key)

    # ── Bars ──────────────────────────────────────────────────────
    def get_price_history(
        self,
        ticker: str,
        *,
        timeframe: str,
        period: str,
    ) -> pd.DataFrame:
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        if timeframe not in _TIMEFRAME_LOOKBACK:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        amount, unit = _TIMEFRAME_LOOKBACK[timeframe]
        tf = TimeFrame(amount=amount, unit=getattr(TimeFrameUnit, unit))

        end = datetime.now(timezone.utc)
        start = _period_to_start(period, end)

        req = StockBarsRequest(
            symbol_or_symbols=ticker.upper(),
            timeframe=tf,
            start=start,
            end=end,
            feed=DataFeed.IEX,
        )
        bars = self._client.get_stock_bars(req)
        df = bars.df  # MultiIndex (symbol, timestamp)
        if df.empty:
            return pd.DataFrame()

        # Drop the symbol level — we always request a single ticker here.
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(ticker.upper(), level=0)

        # Standardize column names to match yfinance shape used elsewhere.
        df = df.rename(columns={
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume",
        })
        return df[["Open", "High", "Low", "Close", "Volume"]]

    # ── Quote ─────────────────────────────────────────────────────
    def get_quote(self, ticker: str) -> dict[str, Any]:
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockLatestQuoteRequest, StockLatestTradeRequest

        ticker = ticker.upper()
        try:
            trade_resp = self._client.get_stock_latest_trade(
                StockLatestTradeRequest(symbol_or_symbols=ticker, feed=DataFeed.IEX)
            )
            last = float(trade_resp[ticker].price)
        except Exception as e:
            logger.warning("Alpaca latest trade failed for {}: {}", ticker, e)
            last = 0.0

        # Previous close: need a daily bar lookback
        try:
            df = self.get_price_history(ticker, timeframe="1d", period="5d")
            prev = float(df["Close"].iloc[-2]) if len(df) >= 2 else last
        except Exception:
            prev = last

        chg = last - prev
        chg_pct = (chg / prev * 100.0) if prev else 0.0

        return {
            "ticker": ticker,
            "price": round(last, 2),
            "change": round(chg, 2),
            "change_pct": round(chg_pct, 2),
            "source": "alpaca",
            "ts": time.time(),
        }

    # ── Stream ────────────────────────────────────────────────────
    async def start_stream(self, tickers: list[str]) -> AsyncIterator[dict[str, Any]]:
        """Stream trade ticks for `tickers` as broker-neutral dicts.

        Uses a queue + the SDK's callback API to bridge into an async iterator.
        """
        from alpaca.data.live import StockDataStream

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        async def _on_trade(trade: Any) -> None:
            await queue.put({
                "type": "tick",
                "ticker": str(trade.symbol).upper(),
                "price": float(trade.price),
                "ts": trade.timestamp.timestamp() if hasattr(trade.timestamp, "timestamp")
                       else time.time(),
                "source": "alpaca",
            })

        from alpaca.data.enums import DataFeed

        stream = StockDataStream(self._api_key, self._secret_key, feed=DataFeed.IEX)
        stream.subscribe_trades(_on_trade, *[t.upper() for t in tickers])

        # Run the SDK's blocking event loop on a background task. The SDK
        # exposes both `run` (sync) and `_run_forever` (async) — we use the
        # async path to share our loop.
        async def _run() -> None:
            try:
                await stream._run_forever()  # type: ignore[attr-defined]
            except Exception as e:
                logger.error("Alpaca stream error: {}", e)
                await queue.put({"type": "error", "error": str(e), "ts": time.time()})

        task = loop.create_task(_run())

        try:
            while True:
                item = await queue.get()
                yield item
        finally:
            task.cancel()
            try:
                await stream.stop_ws()
            except Exception:
                pass
