"""Schwab broker client wrapper — accounts, positions, orders, transactions.

Wired in Phase 1+ once the developer.schwab.com app is approved. Until then
every method raises NotImplementedError so the factory can return a working
client object that fails loudly only when an unfinished method is touched.
"""
from __future__ import annotations

from typing import Any, Optional

from trader.broker.base import BrokerClient


class SchwabBrokerClient(BrokerClient):
    """Concrete BrokerClient backed by schwab-py. Stub until Phase 1."""

    def __init__(self) -> None:
        # The real wiring will load schwab-py + Schwab tokens here.
        pass

    def get_account(self) -> dict[str, Any]:
        raise NotImplementedError("Schwab account client — wired in Phase 1.")

    def get_positions(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Schwab positions — wired in Phase 1.")

    def get_position(self, ticker: str) -> Optional[dict[str, Any]]:
        raise NotImplementedError("Schwab single-position lookup — wired in Phase 1.")

    def get_open_orders(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Schwab open orders — wired in Phase 3.")

    def get_filled_orders(self, since: Any = None) -> list[dict[str, Any]]:
        raise NotImplementedError("Schwab filled orders — wired in Phase 3/4.")

    def place_order(self, order_spec: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Place order — wired in Phase 3.")

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        raise NotImplementedError("Cancel order — wired in Phase 3.")

    def replace_order(self, order_id: str, new_spec: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Replace order — wired in Phase 3.")
