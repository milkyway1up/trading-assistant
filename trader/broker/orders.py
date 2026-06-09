"""Order builders — market / limit / stop / bracket. Phase 3."""
from __future__ import annotations

from typing import Any


def market(ticker: str, side: str, qty: int) -> dict[str, Any]:
    raise NotImplementedError("Market order builder — Phase 3.")


def limit(ticker: str, side: str, qty: int, limit_price: float, tif: str = "DAY") -> dict[str, Any]:
    raise NotImplementedError("Limit order builder — Phase 3.")


def stop(ticker: str, side: str, qty: int, stop_price: float) -> dict[str, Any]:
    raise NotImplementedError("Stop order builder — Phase 3.")


def bracket(
    ticker: str,
    side: str,
    qty: int,
    entry_limit: float,
    stop_loss: float,
    take_profit: float,
) -> dict[str, Any]:
    """OCO bracket: entry + stop-loss + take-profit. Critical for swing trades."""
    raise NotImplementedError("Bracket order builder — Phase 3.")
