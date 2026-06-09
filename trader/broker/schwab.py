"""Schwab REST client wrapper — accounts, positions, orders, transactions.

Phase 1+ implements these against schwab-py.
"""
from __future__ import annotations

from typing import Any, Optional


def get_account() -> dict[str, Any]:
    raise NotImplementedError("Schwab account client — wired in Phase 1.")


def get_positions() -> list[dict[str, Any]]:
    raise NotImplementedError("Schwab positions — wired in Phase 1.")


def get_position(ticker: str) -> Optional[dict[str, Any]]:
    """Convenience: single-ticker position lookup."""
    raise NotImplementedError("Schwab single-position lookup — wired in Phase 1.")


def get_open_orders() -> list[dict[str, Any]]:
    raise NotImplementedError("Schwab open orders — wired in Phase 3.")


def get_filled_orders(since: Any = None) -> list[dict[str, Any]]:
    raise NotImplementedError("Schwab filled orders — wired in Phase 3/4.")


def place_order(order_spec: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("Place order — wired in Phase 3.")


def cancel_order(order_id: str) -> dict[str, Any]:
    raise NotImplementedError("Cancel order — wired in Phase 3.")


def replace_order(order_id: str, new_spec: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("Replace order — wired in Phase 3.")
