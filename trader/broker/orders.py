"""Broker-neutral order builders.

Each helper returns a dict in the shape documented on `BrokerClient.place_order`.
The concrete client (Alpaca, Schwab) translates to its native SDK types.

Bracket orders are the workhorse for swing trades: entry + OCO stop + target,
so you can walk away from the screen.
"""
from __future__ import annotations

from typing import Any


def market(ticker: str, side: str, qty: int, *, tif: str = "DAY") -> dict[str, Any]:
    return {
        "ticker": ticker.upper(),
        "side": side.lower(),
        "qty": qty,
        "type": "market",
        "tif": tif,
        "limit_price": None,
        "stop_price": None,
        "bracket": None,
    }


def limit(
    ticker: str, side: str, qty: int, limit_price: float, *, tif: str = "DAY",
) -> dict[str, Any]:
    return {
        "ticker": ticker.upper(),
        "side": side.lower(),
        "qty": qty,
        "type": "limit",
        "tif": tif,
        "limit_price": limit_price,
        "stop_price": None,
        "bracket": None,
    }


def stop(
    ticker: str, side: str, qty: int, stop_price: float, *, tif: str = "DAY",
) -> dict[str, Any]:
    return {
        "ticker": ticker.upper(),
        "side": side.lower(),
        "qty": qty,
        "type": "stop",
        "tif": tif,
        "limit_price": None,
        "stop_price": stop_price,
        "bracket": None,
    }


def stop_limit(
    ticker: str, side: str, qty: int, stop_price: float, limit_price: float,
    *, tif: str = "DAY",
) -> dict[str, Any]:
    return {
        "ticker": ticker.upper(),
        "side": side.lower(),
        "qty": qty,
        "type": "stop_limit",
        "tif": tif,
        "limit_price": limit_price,
        "stop_price": stop_price,
        "bracket": None,
    }


def bracket(
    ticker: str,
    side: str,
    qty: int,
    entry_limit: float,
    stop_loss: float,
    take_profit: float,
    *,
    tif: str = "DAY",
) -> dict[str, Any]:
    """OCO bracket: entry limit + stop-loss + take-profit. Critical for swing trades."""
    return {
        "ticker": ticker.upper(),
        "side": side.lower(),
        "qty": qty,
        "type": "bracket",
        "tif": tif,
        "limit_price": entry_limit,
        "stop_price": None,
        "bracket": {
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        },
    }
