"""Setup scanner endpoints — surfaces ranked candidates from `trader.scanner`."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from loguru import logger

router = APIRouter(tags=["setups"])


@router.get("/setups/today")
async def setups_today(
    timeframe: str = Query("1d"),
    lookback_days: int = Query(250, ge=30, le=1000),
    setup: Optional[str] = Query(None, description="Filter to a single setup name"),
    min_confidence: float = Query(0.5, ge=0.0, le=1.0),
    top: int = Query(20, ge=1, le=100),
) -> dict:
    """Run the scanner across the universe and return ranked setups."""
    from trader.scanner.runner import run_scan

    try:
        results = run_scan(
            timeframe=timeframe,
            lookback_days=lookback_days,
            setup=setup,
            min_confidence=min_confidence,
        )
        return {"count": len(results), "setups": results[:top]}
    except Exception as e:
        logger.exception("Scanner failed")
        return {"count": 0, "setups": [], "error": str(e)}
