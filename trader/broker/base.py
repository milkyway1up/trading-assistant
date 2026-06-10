"""Abstract base classes for broker + market-data clients.

Concrete implementations (Alpaca today, Schwab once the app is approved) plug
into the factory in `trader.broker.factory`. Every concrete client maps its
native response shape to the broker-neutral dicts documented below so the
rest of the app — UI, journal, LLM, risk guard — never has to branch on
provider.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional

import pandas as pd


class BrokerClient(ABC):
    """Account state + order routing.

    All return values are **broker-neutral dicts**. Concrete clients are
    responsible for converting native SDK responses to these shapes.
    """

    # ── Account ───────────────────────────────────────────────────
    @abstractmethod
    def get_account(self) -> dict[str, Any]:
        """Return account snapshot.

        Required keys:
            equity         : float — total account value (cash + positions MV)
            cash           : float — total cash balance
            settled_cash   : float — cash usable for new buys today
            unsettled_cash : float — proceeds awaiting T+1 settlement (Schwab)
            buying_power   : float — broker's reported buying power
            account_type   : str   — "cash" or "margin"
        """

    # ── Positions ─────────────────────────────────────────────────
    @abstractmethod
    def get_positions(self) -> list[dict[str, Any]]:
        """All open positions.

        Each row:
            ticker, qty, avg_price, market_value, unrealized_pl, unrealized_pl_pct
        """

    @abstractmethod
    def get_position(self, ticker: str) -> Optional[dict[str, Any]]:
        """Single-ticker position lookup; None if flat."""

    # ── Orders ────────────────────────────────────────────────────
    @abstractmethod
    def get_open_orders(self) -> list[dict[str, Any]]:
        """Working orders (new / accepted / partially_filled)."""

    @abstractmethod
    def get_filled_orders(self, since: Any = None) -> list[dict[str, Any]]:
        """Filled orders since `since` (datetime or None=today)."""

    @abstractmethod
    def place_order(self, order_spec: dict[str, Any]) -> dict[str, Any]:
        """Submit an order using the broker-neutral spec from `trader.broker.orders`.

        Spec shape:
            {
              "ticker": "AAPL",
              "side":   "buy" | "sell",
              "qty":    int,
              "type":   "market" | "limit" | "stop" | "stop_limit" | "bracket",
              "tif":    "DAY" | "GTC",
              "limit_price": float | None,
              "stop_price":  float | None,
              "bracket": {                  # only for type=bracket
                  "stop_loss":   float,
                  "take_profit": float,
              } | None,
            }
        """

    @abstractmethod
    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel a working order."""

    @abstractmethod
    def replace_order(self, order_id: str, new_spec: dict[str, Any]) -> dict[str, Any]:
        """Replace (re-price/re-size) a working order."""


class DataClient(ABC):
    """Historical bars + real-time quotes + tick streaming."""

    @abstractmethod
    def get_price_history(
        self,
        ticker: str,
        *,
        timeframe: str,
        period: str,
    ) -> pd.DataFrame:
        """OHLCV DataFrame indexed by timestamp.

        `timeframe`: one of "1m", "5m", "15m", "1h", "4h", "1d".
        `period`:    free-form lookback (e.g. "2y", "6mo", "1mo"). Concrete
                     clients translate to their native param names.
        Columns: Open, High, Low, Close, Volume.
        """

    @abstractmethod
    def get_quote(self, ticker: str) -> dict[str, Any]:
        """Latest quote: {ticker, price, change, change_pct, volume, ts}."""

    @abstractmethod
    async def start_stream(self, tickers: list[str]) -> AsyncIterator[dict[str, Any]]:
        """Async iterator of tick events:
            {"type": "tick", "ticker": str, "price": float, "ts": float}
        Implementations should reconnect on transient failures.
        """
