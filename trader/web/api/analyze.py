"""Claude analysis endpoint — drives the dashboard's Analyze button."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from loguru import logger

router = APIRouter(tags=["analyze"])


@router.post("/analyze/{ticker}")
async def analyze(ticker: str, with_position: bool = False) -> dict:
    """Run trader.llm.analysis.analyze_ticker and return the structured thesis."""
    from trader.llm.analysis import analyze_ticker

    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(
            None, lambda: analyze_ticker(ticker.upper(), with_position=with_position)
        )
    except Exception as e:
        logger.exception("analyze failed")
        raise HTTPException(status_code=502, detail=f"Claude analysis failed: {e}")
