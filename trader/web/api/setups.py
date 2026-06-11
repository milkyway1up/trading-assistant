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


@router.post("/setups/rate")
async def rate_setups(top: int = Query(4, ge=1, le=10)) -> dict:
    """Send the top N scanner setups to Claude for a 1-10 rating each.

    Sequential — typical run is ~10–15s for 4 setups. Returns the ratings
    sorted by Claude's rating descending, with original scanner fields preserved.
    """
    from trader.llm.analysis import rate_setup
    from trader.scanner.runner import run_scan

    try:
        candidates = list(run_scan())[:top]
    except Exception as e:
        logger.exception("Scanner failed in rate_setups")
        return {"rated": [], "error": f"scanner: {e}"}

    rated: list[dict] = []
    for s in candidates:
        ticker = s.get("ticker")
        try:
            r = rate_setup(ticker, s)
            s["claude_rating"] = r.get("rating")
            s["claude_reason"] = r.get("reason", "")
        except Exception as e:
            logger.exception("rate_setup failed for {}", ticker)
            s["claude_rating"] = None
            s["claude_reason"] = f"rating failed: {e}"
        rated.append(s)

    rated.sort(
        key=lambda s: (s.get("claude_rating") or 0, s.get("confidence") or 0),
        reverse=True,
    )
    return {"rated": rated, "count": len(rated)}
