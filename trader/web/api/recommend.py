"""Claude-recommended order endpoint — runs analyze_ticker and returns order-ready fields."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from loguru import logger

router = APIRouter(tags=["recommend"])


@router.post("/recommend/{ticker}")
async def recommend_order(ticker: str) -> dict:
    """Run Claude analysis and surface entry/stop/target in a shape the order
    ticket can pre-fill. The full analysis is included for context display."""
    from trader.llm.analysis import analyze_ticker

    loop = asyncio.get_running_loop()
    try:
        analysis = await loop.run_in_executor(
            None, lambda: analyze_ticker(ticker.upper(), with_position=False)
        )
    except Exception as e:
        logger.exception("recommend failed")
        raise HTTPException(status_code=502, detail=f"Claude analysis failed: {e}")

    if not isinstance(analysis, dict):
        raise HTTPException(status_code=502, detail="Claude returned non-dict analysis")

    bias = (analysis.get("bias") or analysis.get("trend") or "").lower()
    side = "sell" if "down" in bias or "bear" in bias or "short" in bias else "buy"

    entry = analysis.get("ideal_entry")
    if entry is None:
        # ideal_entry sometimes comes back as a string range like "245-247"; try
        # to pull a midpoint, otherwise leave blank.
        ez = analysis.get("entry_zone")
        if isinstance(ez, (int, float)):
            entry = ez
        elif isinstance(ez, str):
            try:
                parts = [float(p) for p in ez.replace("$", "").replace(",", "").split("-")]
                if parts:
                    entry = sum(parts) / len(parts)
            except ValueError:
                entry = None

    return {
        "ticker": ticker.upper(),
        "side": side,
        "entry": entry,
        "stop": analysis.get("stop") or analysis.get("stop_level"),
        "target": analysis.get("target"),
        "risk_reward": analysis.get("risk_reward"),
        "confidence": analysis.get("confidence"),
        "thesis": analysis.get("thesis"),
        "time_horizon_days": analysis.get("time_horizon_days"),
        "suggested_size_pct": analysis.get("suggested_size_pct"),
        "bias": analysis.get("bias") or analysis.get("trend"),
        "full_analysis": analysis,
    }
