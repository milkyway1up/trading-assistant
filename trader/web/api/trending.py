"""Trending ticker endpoints — surfaces social-momentum names from Reddit / StockTwits."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/trending", tags=["trending"])


@router.get("")
async def get_trending(
    limit: int = Query(20, ge=1, le=50),
    include_pennies: bool = Query(True),
    include_standard: bool = Query(True),
    min_mentions: int = Query(3, ge=0, le=100),
) -> dict:
    """Return ranked trending tickers from social-momentum sources."""
    from trader.data.trending import fetch_trending

    loop = asyncio.get_running_loop()
    try:
        rows = await loop.run_in_executor(
            None,
            lambda: fetch_trending(
                limit=limit,
                include_pennies=include_pennies,
                include_standard=include_standard,
                min_mentions=min_mentions,
            ),
        )
        return {"count": len(rows), "trending": rows}
    except Exception as e:
        logger.exception("trending fetch failed")
        return {"count": 0, "trending": [], "error": str(e)}


class RateBody(BaseModel):
    ticker: str
    social: dict | None = None  # the row returned from /api/trending


@router.post("/rate")
async def rate_trending(body: RateBody) -> dict:
    """Send a single trending ticker to Claude for a pump-risk-aware rating."""
    from trader.llm.analysis import rate_momentum

    ticker = (body.ticker or "").upper().strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker required")

    social = body.social or {"ticker": ticker}
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, lambda: rate_momentum(ticker, social))
        return {"ticker": ticker, **result}
    except Exception as e:
        logger.exception("rate_momentum failed for {}", ticker)
        return {
            "ticker": ticker, "rating": None, "pump_risk": "high",
            "verdict": "avoid", "reason": f"rating failed: {e}",
        }
