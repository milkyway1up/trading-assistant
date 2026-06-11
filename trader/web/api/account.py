"""Account snapshot + positions endpoint.

Powers the dashboard's right-rail panel (settled cash, day P&L, open
positions). Returns an empty/error shape when no broker is configured so
the UI degrades gracefully instead of 500ing.
"""
from __future__ import annotations

from fastapi import APIRouter
from loguru import logger

router = APIRouter(tags=["account"])


@router.get("/account")
async def get_account() -> dict:
    """Live account snapshot + open positions from the configured broker."""
    try:
        from trader.broker.factory import get_broker
        broker = get_broker()
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "account": None,
            "positions": [],
        }

    try:
        account = broker.get_account()
    except Exception as e:
        logger.warning("get_account failed: {}", e)
        return {
            "connected": False,
            "error": f"Account fetch failed: {e}",
            "account": None,
            "positions": [],
        }

    try:
        positions = broker.get_positions()
    except Exception as e:
        logger.warning("get_positions failed: {}", e)
        positions = []

    day_pl = sum(float(p.get("unrealized_pl") or 0) for p in positions)

    return {
        "connected": True,
        "error": None,
        "account": account,
        "positions": positions,
        "day_pl": round(day_pl, 2),
    }
