"""Alpaca broker client.

Why Alpaca: API-first broker with **instant key provisioning** (no multi-day
approval). Free paper trading from minute one. Same SDK switches to live by
flipping `paper=False` once you've validated the workflow.

Docs: https://alpaca.markets/docs/api-references/trading-api/
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from loguru import logger

from trader.broker.base import BrokerClient


class AlpacaBrokerClient(BrokerClient):
    """Concrete BrokerClient backed by `alpaca-py`."""

    def __init__(self, api_key: str, secret_key: str, *, paper: bool = True) -> None:
        if not api_key or not secret_key:
            raise ValueError(
                "Alpaca API key/secret missing. Generate paper-trading keys at "
                "alpaca.markets → Paper Trading → API Keys, then paste into "
                "the Settings panel (or .env)."
            )
        from alpaca.trading.client import TradingClient

        self._paper = paper
        self._client = TradingClient(
            api_key=api_key, secret_key=secret_key, paper=paper,
        )
        logger.debug("Alpaca trading client initialized (paper={})", paper)

    # ── Account ───────────────────────────────────────────────────
    def get_account(self) -> dict[str, Any]:
        a = self._client.get_account()
        # Alpaca margin accounts have non-zero "buying_power" > "cash". For a
        # cash-style account, buying_power == cash. We surface both so the
        # risk guard can pick whichever it prefers.
        return {
            "id": str(a.id),
            "equity": float(a.equity),
            "cash": float(a.cash),
            # Alpaca clears T+0 on day-trade buying power for margin accounts;
            # for cash accounts `non_marginable_buying_power` is the closest
            # analogue to settled cash. Where unavailable, fall back to cash.
            "settled_cash": float(getattr(a, "cash", 0) or 0),
            "unsettled_cash": float(getattr(a, "pending_transfer_in", 0) or 0),
            "buying_power": float(a.buying_power),
            "account_type": "margin" if a.pattern_day_trader is not None and getattr(
                a, "trading_blocked", False) is False and float(a.equity) > 0 and float(
                a.buying_power) > float(a.cash) else "cash",
            "paper": self._paper,
            "status": str(a.status),
        }

    # ── Positions ─────────────────────────────────────────────────
    def get_positions(self) -> list[dict[str, Any]]:
        return [_position_to_dict(p) for p in self._client.get_all_positions()]

    def get_position(self, ticker: str) -> Optional[dict[str, Any]]:
        from alpaca.common.exceptions import APIError

        try:
            p = self._client.get_open_position(ticker.upper())
        except APIError as e:
            # Alpaca returns 404 when flat — translate to None.
            if "position does not exist" in str(e).lower() or "404" in str(e):
                return None
            raise
        return _position_to_dict(p)

    # ── Orders ────────────────────────────────────────────────────
    def get_open_orders(self) -> list[dict[str, Any]]:
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        req = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        return [_order_to_dict(o) for o in self._client.get_orders(filter=req)]

    def get_filled_orders(self, since: Any = None) -> list[dict[str, Any]]:
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=1)
        elif isinstance(since, datetime) and since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        req = GetOrdersRequest(status=QueryOrderStatus.CLOSED, after=since)
        # Filter to only filled (not canceled/expired) — Alpaca lumps both
        # under CLOSED.
        return [
            _order_to_dict(o)
            for o in self._client.get_orders(filter=req)
            if str(getattr(o, "status", "")).lower() == "filled"
        ]

    def place_order(self, order_spec: dict[str, Any]) -> dict[str, Any]:
        req = _spec_to_alpaca_request(order_spec)
        order = self._client.submit_order(req)
        return _order_to_dict(order)

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        self._client.cancel_order_by_id(order_id)
        return {"id": order_id, "status": "cancel_requested"}

    def replace_order(self, order_id: str, new_spec: dict[str, Any]) -> dict[str, Any]:
        from alpaca.trading.requests import ReplaceOrderRequest

        kwargs: dict[str, Any] = {}
        if (q := new_spec.get("qty")) is not None:
            kwargs["qty"] = q
        if (p := new_spec.get("limit_price")) is not None:
            kwargs["limit_price"] = p
        if (s := new_spec.get("stop_price")) is not None:
            kwargs["stop_price"] = s
        if (t := new_spec.get("tif")) is not None:
            kwargs["time_in_force"] = _tif(t)
        order = self._client.replace_order_by_id(order_id, ReplaceOrderRequest(**kwargs))
        return _order_to_dict(order)


# ─────────────────────────────────────────────────────────────────
# Mapping helpers — keep all alpaca-py-specific knowledge in here
# ─────────────────────────────────────────────────────────────────

def _position_to_dict(p: Any) -> dict[str, Any]:
    qty = float(getattr(p, "qty", 0) or 0)
    avg = float(getattr(p, "avg_entry_price", 0) or 0)
    mv = float(getattr(p, "market_value", 0) or 0)
    upl = float(getattr(p, "unrealized_pl", 0) or 0)
    upl_pct = float(getattr(p, "unrealized_plpc", 0) or 0) * 100.0
    return {
        "ticker": str(p.symbol).upper(),
        "qty": qty,
        "avg_price": avg,
        "market_value": mv,
        "unrealized_pl": upl,
        "unrealized_pl_pct": upl_pct,
        "side": str(getattr(p, "side", "long")).lower(),
    }


def _order_to_dict(o: Any) -> dict[str, Any]:
    return {
        "id": str(o.id),
        "ticker": str(getattr(o, "symbol", "")).upper(),
        "side": str(getattr(o, "side", "")).lower(),
        "qty": float(getattr(o, "qty", 0) or 0),
        "filled_qty": float(getattr(o, "filled_qty", 0) or 0),
        "type": str(getattr(o, "order_type", "")).lower(),
        "tif": str(getattr(o, "time_in_force", "")).upper(),
        "limit_price": _maybe_float(getattr(o, "limit_price", None)),
        "stop_price": _maybe_float(getattr(o, "stop_price", None)),
        "status": str(getattr(o, "status", "")).lower(),
        "submitted_at": _maybe_iso(getattr(o, "submitted_at", None)),
        "filled_at": _maybe_iso(getattr(o, "filled_at", None)),
        "filled_avg_price": _maybe_float(getattr(o, "filled_avg_price", None)),
    }


def _maybe_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _maybe_iso(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def _tif(tif: str):
    from alpaca.trading.enums import TimeInForce

    return {
        "DAY": TimeInForce.DAY,
        "GTC": TimeInForce.GTC,
        "IOC": TimeInForce.IOC,
        "FOK": TimeInForce.FOK,
    }.get(tif.upper(), TimeInForce.DAY)


def _side(side: str):
    from alpaca.trading.enums import OrderSide

    return OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL


def _spec_to_alpaca_request(spec: dict[str, Any]) -> Any:
    """Translate a broker-neutral order spec into an alpaca-py request object."""
    from alpaca.trading.requests import (
        LimitOrderRequest,
        MarketOrderRequest,
        StopLimitOrderRequest,
        StopLossRequest,
        StopOrderRequest,
        TakeProfitRequest,
    )
    from alpaca.trading.enums import OrderClass

    ticker = spec["ticker"].upper()
    side = _side(spec["side"])
    qty = spec["qty"]
    tif = _tif(spec.get("tif", "DAY"))
    otype = spec.get("type", "limit").lower()

    if otype == "market":
        return MarketOrderRequest(symbol=ticker, qty=qty, side=side, time_in_force=tif)

    if otype == "limit":
        return LimitOrderRequest(
            symbol=ticker, qty=qty, side=side, time_in_force=tif,
            limit_price=spec["limit_price"],
        )

    if otype == "stop":
        return StopOrderRequest(
            symbol=ticker, qty=qty, side=side, time_in_force=tif,
            stop_price=spec["stop_price"],
        )

    if otype == "stop_limit":
        return StopLimitOrderRequest(
            symbol=ticker, qty=qty, side=side, time_in_force=tif,
            limit_price=spec["limit_price"], stop_price=spec["stop_price"],
        )

    if otype == "bracket":
        bracket = spec.get("bracket") or {}
        if "stop_loss" not in bracket or "take_profit" not in bracket:
            raise ValueError("bracket order requires bracket.stop_loss + bracket.take_profit")
        return LimitOrderRequest(
            symbol=ticker,
            qty=qty,
            side=side,
            time_in_force=tif,
            limit_price=spec["limit_price"],
            order_class=OrderClass.BRACKET,
            stop_loss=StopLossRequest(stop_price=bracket["stop_loss"]),
            take_profit=TakeProfitRequest(limit_price=bracket["take_profit"]),
        )

    raise ValueError(f"Unsupported order type: {otype}")
