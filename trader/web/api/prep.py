"""Weekly prep document endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from loguru import logger

from trader.config import prep_dir

router = APIRouter(tags=["prep"])


@router.get("/prep")
async def list_prep() -> dict:
    """Return all prep markdown docs sorted newest first."""
    try:
        docs = sorted(
            (p.name for p in prep_dir().glob("*.md")),
            reverse=True,
        )
        return {"docs": list(docs)}
    except Exception as e:
        return {"docs": [], "error": str(e)}


@router.get("/prep/{name}")
async def get_prep(name: str) -> dict:
    """Return raw markdown for a single prep doc."""
    if "/" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid name")
    path = prep_dir() / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return {"name": name, "markdown": path.read_text()}


@router.post("/prep")
async def generate_prep() -> dict:
    """Run the weekly prep generator. Blocks until Claude responds (~30s)."""
    try:
        from trader.llm.prep import generate_weekly_prep
        path = generate_weekly_prep()
        return {"name": path.name, "path": str(path)}
    except Exception as e:
        logger.exception("prep generation failed")
        raise HTTPException(status_code=502, detail=f"Prep generation failed: {e}")
