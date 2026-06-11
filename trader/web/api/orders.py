"""Order ticket endpoints: preview, submit, list, cancel.

Mirrors the `trader order` CLI: factory → sizing → risk_guard → place_order
→ journal log. The UI calls /preview to render risk+sizing math without
side effects, then /submit to actually place.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

router = APIRouter(tags=["orders"])


class OrderRequest(BaseModel):
    ticker: str
    side: str  # buy | sell
    entry: float
    stop: Optional[float] = None
    target: Optional[float] = None
    risk_pct: Optional[float] = None  # if qty is None, sized from this
    qty: Optional[int] = None
    type: str = "limit"  # limit | bracket | market


@router.post("/orders/preview")
async def preview_order(req: OrderRequest) -> dict:
    """Compute sizing + run risk-guard checks. No order is placed."""
    return _build_preview(req)


@router.post("/orders/submit")
async def submit_order(req: OrderRequest) -> dict:
    """Submit the order after a fresh preview. Refuses if risk-guard blocks."""
    preview = _build_preview(req)
    if not preview["ok"]:
        raise HTTPException(status_code=400, detail=preview)

    from trader.broker import orders as order_builders
    from trader.broker.factory import get_broker

    spec = _build_spec(req, preview["qty"], order_builders)

    try:
        broker = get_broker()
        result = broker.place_order(spec)
    except Exception as e:
        logger.exception("place_order failed")
        raise HTTPException(status_code=502, detail=f"Broker rejected order: {e}")

    # Journal it.
    trade_id = None
    try:
        from trader.journal.entry import add_trade
        trade_id = add_trade(
            ticker=req.ticker.upper(),
            side=req.side.lower(),
            quantity=preview["qty"],
            entry_price=req.entry,
            stop_price=req.stop,
            target_price=req.target,
            schwab_order_id=str(result.get("id") or "") or None,
        )
    except Exception as e:
        logger.warning("Journal log failed: {}", e)

    return {
        "ok": True,
        "order": result,
        "preview": preview,
        "trade_id": trade_id,
    }


@router.get("/orders/open")
async def open_orders() -> dict:
    try:
        from trader.broker.factory import get_broker
        return {"orders": get_broker().get_open_orders()}
    except Exception as e:
        return {"orders": [], "error": str(e)}


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str) -> dict:
    try:
        from trader.broker.factory import get_broker
        return get_broker().cancel_order(order_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _build_preview(req: OrderRequest) -> dict[str, Any]:
    from trader.broker.factory import get_broker
    from trader.broker.risk_guard import run_all_checks
    from trader.config import get_config
    from trader.sizing.calculator import position_size

    cfg = get_config()
    side = req.side.lower()
    if side not in {"buy", "sell"}:
        return _error("Invalid side; use buy or sell.")
    if req.type not in {"market", "limit", "bracket"}:
        return _error(f"Unsupported order type '{req.type}'.")
    if req.type == "bracket" and (req.stop is None or req.target is None):
        return _error("bracket orders require both stop and target.")

    try:
        account = get_broker().get_account()
    except Exception as e:
        return _error(f"Broker unavailable: {e}")

    equity = float(account.get("equity") or 0)
    settled_cash = float(account.get("settled_cash") or account.get("cash") or 0)

    # Sizing
    if req.qty is None:
        if req.stop is None:
            return _error("Need stop to compute size from risk_pct, or pass qty.")
        risk = req.risk_pct if req.risk_pct is not None else cfg.risk.default_risk_pct
        sized = position_size(
            account_equity=equity, risk_pct=risk,
            entry=req.entry, stop=req.stop,
        )
        if sized.shares < 1:
            return _error(sized.note)
        qty = sized.shares
        dollar_risk = sized.dollar_risk
    else:
        qty = req.qty
        dollar_risk = abs(req.entry - req.stop) * qty if req.stop is not None else 0.0

    order_value = qty * req.entry

    checks = run_all_checks(
        side=side,
        account_equity=equity,
        settled_cash=settled_cash,
        order_value=order_value,
        dollar_risk=dollar_risk,
        entry=req.entry,
        stop=req.stop,
        cfg_max_position_pct=cfg.risk.max_position_pct,
        cfg_max_risk_pct=cfg.risk.max_risk_per_trade_pct,
        cfg_max_stop_distance_pct=cfg.risk.max_stop_distance_pct,
    )
    failures = [c.reason for c in checks if not c.ok]

    rr = (
        abs(req.target - req.entry) / abs(req.entry - req.stop)
        if (req.stop and req.target) else None
    )

    return {
        "ok": not failures,
        "qty": qty,
        "order_value": round(order_value, 2),
        "dollar_risk": round(dollar_risk, 2),
        "risk_pct_actual": round(dollar_risk / equity * 100, 3) if equity else 0,
        "position_pct": round(order_value / equity * 100, 2) if equity else 0,
        "risk_reward": round(rr, 2) if rr else None,
        "equity": round(equity, 2),
        "settled_cash": round(settled_cash, 2),
        "failures": failures,
    }


def _build_spec(req: OrderRequest, qty: int, order_builders) -> dict[str, Any]:
    if req.type == "market":
        return order_builders.market(req.ticker, req.side, qty)
    if req.type == "bracket":
        return order_builders.bracket(req.ticker, req.side, qty, req.entry, req.stop, req.target)
    return order_builders.limit(req.ticker, req.side, qty, req.entry)


def _error(msg: str) -> dict:
    return {"ok": False, "failures": [msg], "qty": 0, "order_value": 0,
            "dollar_risk": 0, "risk_pct_actual": 0, "position_pct": 0,
            "risk_reward": None, "equity": 0, "settled_cash": 0}
