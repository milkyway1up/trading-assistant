"""Setup scanner endpoints — surfaces ranked candidates from `trader.scanner`."""
from __future__ import annotations

import asyncio
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
    from functools import partial

    from trader.scanner.runner import run_scan

    loop = asyncio.get_running_loop()
    try:
        results = await loop.run_in_executor(
            None,
            partial(run_scan, timeframe=timeframe, lookback_days=lookback_days,
                    setup=setup, min_confidence=min_confidence),
        )
        return {"count": len(results), "setups": results[:top]}
    except Exception as e:
        logger.exception("Scanner failed")
        return {"count": 0, "setups": [], "error": str(e)}


@router.post("/setups/rate")
async def rate_setups(top: int = Query(50, ge=1, le=50)) -> dict:
    """Rate all setups in a single batched Claude call.

    Fetches price context in parallel threads, then sends one prompt to Claude
    with all setups. Much faster than per-setup calls (~5s vs ~60s for 15 setups).
    """
    from trader.llm.analysis import rate_setups_batch
    from trader.scanner.runner import run_scan

    loop = asyncio.get_running_loop()

    try:
        candidates = list(await loop.run_in_executor(None, run_scan))[:top]
    except Exception as e:
        logger.exception("Scanner failed in rate_setups")
        return {"rated": [], "error": f"scanner: {e}"}

    try:
        ratings = await loop.run_in_executor(None, rate_setups_batch, candidates)
    except Exception as e:
        logger.exception("Batch rating failed")
        return {"rated": [], "error": f"rating: {e}"}

    rating_by_ticker: dict[str, dict] = {}
    for r in ratings:
        rating_by_ticker[r.get("ticker", "")] = r

    for s in candidates:
        r = rating_by_ticker.get(s.get("ticker", ""))
        if r:
            s["claude_rating"] = r.get("rating")
            s["claude_reason"] = r.get("reason", "")
        else:
            s["claude_rating"] = None
            s["claude_reason"] = "not in batch response"

    candidates.sort(
        key=lambda s: (s.get("claude_rating") or 0, s.get("confidence") or 0),
        reverse=True,
    )
    return {"rated": candidates, "count": len(candidates)}
