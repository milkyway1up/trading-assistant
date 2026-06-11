"""Pull broker fills into the journal and FIFO-pair entries with exits.

Provider-agnostic: works with whatever `BrokerClient` the factory returns
(Alpaca today, Schwab once approved). The CLI's `trader journal sync` calls
`sync_fills`; the legacy name `sync_from_schwab` is kept as a thin alias.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from loguru import logger

from trader.journal.db import Trade, get_session


def sync_fills(*, since_days: int = 30) -> dict[str, int]:
    """Pull recent filled orders from the configured broker and upsert into Trade rows.

    Pairs buy fills with subsequent sell fills FIFO per ticker. Computes
    realized P&L and R-multiple where stop info is available. Returns a
    summary dict: {"new_entries": ..., "matched_exits": ..., "skipped": ...}.
    """
    from trader.broker.factory import get_broker

    broker = get_broker()
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    fills = broker.get_filled_orders(since=since)

    summary = {"new_entries": 0, "matched_exits": 0, "skipped": 0}
    session = get_session()

    # Sort fills oldest → newest for stable FIFO pairing.
    fills.sort(key=lambda f: f.get("filled_at") or f.get("submitted_at") or "")

    # Existing order IDs already journaled — skip them on re-sync.
    existing_ids = {
        row[0] for row in session.query(Trade.schwab_order_id).filter(
            Trade.schwab_order_id.isnot(None)
        ).all()
    }

    # Open buy positions per ticker (FIFO queue of Trade rows awaiting exits).
    open_buys: dict[str, deque[Trade]] = {}
    for t in session.query(Trade).filter(
        Trade.exit_price.is_(None), Trade.side == "buy",
    ).all():
        open_buys.setdefault(t.ticker, deque()).append(t)

    for f in fills:
        oid = str(f.get("id") or "")
        if oid and oid in existing_ids:
            summary["skipped"] += 1
            continue

        ticker = (f.get("ticker") or "").upper()
        side = (f.get("side") or "").lower()
        qty = int(float(f.get("filled_qty") or f.get("qty") or 0))
        price = _maybe_float(f.get("filled_avg_price") or f.get("limit_price"))
        ts = _parse_ts(f.get("filled_at") or f.get("submitted_at"))

        if not ticker or qty <= 0 or price is None:
            summary["skipped"] += 1
            continue

        if side == "buy":
            trade = Trade(
                schwab_order_id=oid or None,
                ticker=ticker,
                side="buy",
                quantity=qty,
                entry_price=price,
                entry_time=ts,
            )
            session.add(trade)
            session.flush()
            open_buys.setdefault(ticker, deque()).append(trade)
            summary["new_entries"] += 1
            continue

        if side == "sell":
            queue = open_buys.get(ticker)
            remaining = qty
            while queue and remaining > 0:
                buy = queue[0]
                buy_qty = int(buy.quantity or 0)
                fill_qty = min(buy_qty, remaining)

                if fill_qty >= buy_qty:
                    _close_trade_row(buy, exit_price=price, exit_time=ts, qty=buy_qty)
                    queue.popleft()
                    remaining -= buy_qty
                else:
                    # Partial close: split the row — close `fill_qty`, keep remainder open.
                    closed = Trade(
                        schwab_order_id=buy.schwab_order_id,
                        ticker=buy.ticker,
                        side=buy.side,
                        quantity=fill_qty,
                        entry_price=buy.entry_price,
                        entry_time=buy.entry_time,
                        stop_price=buy.stop_price,
                        target_price=buy.target_price,
                        thesis_at_entry=buy.thesis_at_entry,
                    )
                    session.add(closed)
                    session.flush()
                    _close_trade_row(closed, exit_price=price, exit_time=ts, qty=fill_qty)
                    buy.quantity = buy_qty - fill_qty
                    remaining = 0

                summary["matched_exits"] += 1

            if remaining > 0:
                logger.warning(
                    "Sell {} {} of {} has no matching open buy — recording stub close.",
                    remaining, ticker, qty,
                )
                # Record as a standalone short-flat sell so it isn't lost.
                stub = Trade(
                    schwab_order_id=oid or None,
                    ticker=ticker,
                    side="sell",
                    quantity=remaining,
                    exit_price=price,
                    exit_time=ts,
                    exit_reason="unmatched_sell",
                )
                session.add(stub)
                summary["skipped"] += 1

    session.commit()
    return summary


def sync_from_schwab() -> int:
    """Backwards-compat wrapper for the original name. Returns new entry count."""
    result = sync_fills()
    return result.get("new_entries", 0)


def _close_trade_row(row: Trade, *, exit_price: float, exit_time: Optional[datetime], qty: int) -> None:
    row.exit_price = exit_price
    row.exit_time = exit_time
    if row.entry_price is not None:
        row.realized_pnl = (exit_price - row.entry_price) * qty
        if row.stop_price is not None:
            per_share_risk = abs(row.entry_price - row.stop_price)
            if per_share_risk > 0:
                row.r_multiple = row.realized_pnl / (per_share_risk * qty)
        if row.risk_dollars and row.r_multiple is None:
            row.r_multiple = row.realized_pnl / row.risk_dollars


def _maybe_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_ts(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None
