"""Journal endpoints: list trades, stats, sync, annotate, grade."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

router = APIRouter(tags=["journal"])


@router.get("/journal/trades")
async def list_trades(
    setup: Optional[str] = None,
    limit: int = 200,
    closed_only: bool = False,
) -> dict:
    from trader.journal.db import Trade, get_session

    session = get_session()
    q = session.query(Trade).order_by(Trade.entry_time.desc().nullslast())
    if setup:
        q = q.filter(Trade.setup_type == setup)
    if closed_only:
        q = q.filter(Trade.exit_price.isnot(None))
    rows = q.limit(limit).all()
    return {"trades": [_trade_to_dict(t) for t in rows]}


@router.get("/journal/stats")
async def journal_stats(since_days: Optional[int] = 30) -> dict:
    from trader.journal.analytics import stats
    return stats(since_days=since_days)


class SyncRequest(BaseModel):
    since_days: int = 30


@router.post("/journal/sync")
async def journal_sync(body: SyncRequest = SyncRequest()) -> dict:
    """Pull recent broker fills into the journal."""
    try:
        from trader.journal.sync import sync_fills
        return sync_fills(since_days=body.since_days)
    except Exception as e:
        logger.exception("journal sync failed")
        raise HTTPException(status_code=502, detail=str(e))


class AnnotateRequest(BaseModel):
    setup_type: Optional[str] = None
    thesis_at_entry: Optional[str] = None
    catalysts: Optional[str] = None
    mistakes: Optional[str] = None
    exit_reason: Optional[str] = None
    notes: Optional[str] = None


@router.patch("/journal/{trade_id}")
async def annotate_trade(trade_id: int, body: AnnotateRequest) -> dict:
    from trader.journal.entry import annotate

    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return {"updated": [], "trade_id": trade_id}
    try:
        annotate(trade_id, **fields)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"updated": list(fields), "trade_id": trade_id}


@router.post("/journal/{trade_id}/grade")
async def grade_endpoint(trade_id: int) -> dict:
    """Have Claude grade a closed trade against its entry thesis."""
    from datetime import timedelta

    from trader.journal.db import Trade, get_session
    from trader.llm.grade import grade_trade

    session = get_session()
    trade = session.get(Trade, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
    if trade.exit_price is None:
        raise HTTPException(status_code=400, detail="Trade is still open")

    bars = _bars_around_trade(trade)
    payload = {
        "ticker": trade.ticker,
        "side": trade.side,
        "entry_time": trade.entry_time.isoformat() if trade.entry_time else None,
        "entry_price": trade.entry_price,
        "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
        "exit_price": trade.exit_price,
        "size": trade.quantity,
        "stop": trade.stop_price,
        "target": trade.target_price,
        "thesis_at_entry": trade.thesis_at_entry,
        "exit_reason": trade.exit_reason,
        "realized_pnl": trade.realized_pnl,
        "r_multiple": trade.r_multiple,
    }
    try:
        result = grade_trade(payload, bars)
    except Exception as e:
        logger.exception("grade failed")
        raise HTTPException(status_code=502, detail=str(e))

    if isinstance(result, dict):
        if (g := result.get("grade")):
            trade.llm_grade = g
        if (l := result.get("lesson")):
            trade.llm_lesson = l
        if (tags := result.get("tags")):
            trade.llm_tags = ",".join(tags) if isinstance(tags, list) else str(tags)
        session.commit()
    return {"trade_id": trade_id, "result": result}


def _trade_to_dict(t) -> dict[str, Any]:
    return {
        "id": t.id,
        "ticker": t.ticker,
        "side": t.side,
        "setup_type": t.setup_type,
        "quantity": t.quantity,
        "entry_time": t.entry_time.isoformat() if t.entry_time else None,
        "entry_price": t.entry_price,
        "exit_time": t.exit_time.isoformat() if t.exit_time else None,
        "exit_price": t.exit_price,
        "stop_price": t.stop_price,
        "target_price": t.target_price,
        "realized_pnl": t.realized_pnl,
        "r_multiple": t.r_multiple,
        "thesis_at_entry": t.thesis_at_entry,
        "exit_reason": t.exit_reason,
        "notes": t.notes,
        "llm_grade": t.llm_grade,
        "llm_lesson": t.llm_lesson,
        "llm_tags": t.llm_tags,
    }


def _bars_around_trade(trade) -> list[dict]:
    from datetime import timedelta

    if not trade.entry_time or not trade.exit_time:
        return []
    try:
        from trader.data.yfinance_bars import get_bars
        df = get_bars(trade.ticker, timeframe="1d", period="6mo")
        if df.empty:
            return []
        start = trade.entry_time - timedelta(days=3)
        end = trade.exit_time + timedelta(days=5)
        df = df.loc[start.replace(tzinfo=None):end.replace(tzinfo=None)] \
            if df.index.tz is None else df.loc[start:end]
        return [
            {
                "date": idx.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
            }
            for idx, row in df.iterrows()
        ]
    except Exception:
        return []
