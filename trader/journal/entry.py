"""Manual journal entry helpers. Phase 4."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from trader.journal.db import Trade, get_session


def add_trade(*, ticker: str, side: str, quantity: int,
              entry_price: float, entry_time: Optional[datetime] = None,
              setup_type: Optional[str] = None,
              stop_price: Optional[float] = None,
              target_price: Optional[float] = None,
              thesis_at_entry: Optional[str] = None,
              schwab_order_id: Optional[str] = None) -> int:
    session = get_session()
    trade = Trade(
        ticker=ticker.upper(),
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        entry_time=entry_time or datetime.utcnow(),
        setup_type=setup_type,
        stop_price=stop_price,
        target_price=target_price,
        thesis_at_entry=thesis_at_entry,
        schwab_order_id=schwab_order_id,
    )
    if stop_price is not None and entry_price is not None:
        trade.risk_dollars = (entry_price - stop_price) * quantity
    session.add(trade)
    session.commit()
    return trade.id


def annotate(trade_id: int, **fields) -> None:
    session = get_session()
    trade = session.get(Trade, trade_id)
    if trade is None:
        raise ValueError(f"Trade {trade_id} not found")
    for k, v in fields.items():
        if hasattr(trade, k):
            setattr(trade, k, v)
    session.commit()


def close_trade(trade_id: int, exit_price: float,
                exit_time: Optional[datetime] = None,
                exit_reason: Optional[str] = None) -> None:
    session = get_session()
    trade = session.get(Trade, trade_id)
    if trade is None:
        raise ValueError(f"Trade {trade_id} not found")
    trade.exit_price = exit_price
    trade.exit_time = exit_time or datetime.utcnow()
    trade.exit_reason = exit_reason
    if trade.entry_price and trade.quantity:
        trade.realized_pnl = (exit_price - trade.entry_price) * trade.quantity
        if trade.risk_dollars:
            trade.r_multiple = trade.realized_pnl / trade.risk_dollars
    session.commit()
