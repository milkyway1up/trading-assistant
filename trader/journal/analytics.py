"""Win rate, R-multiple, expectancy by setup type. Phase 4."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from trader.journal.db import Trade, get_session


def stats(since_days: Optional[int] = None) -> dict:
    """Compute win rate, average R, expectancy across all closed trades and per
    setup type. `since_days` filters by exit_time."""
    session = get_session()
    q = session.query(Trade).filter(Trade.exit_price.isnot(None))
    if since_days is not None:
        cutoff = datetime.utcnow() - timedelta(days=since_days)
        q = q.filter(Trade.exit_time >= cutoff)
    trades = q.all()

    if not trades:
        return {"total": 0, "by_setup": {}}

    overall = _aggregate(trades)
    by_setup: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        by_setup[t.setup_type or "uncategorized"].append(t)

    return {
        "total": len(trades),
        "overall": overall,
        "by_setup": {k: _aggregate(v) for k, v in by_setup.items()},
    }


def _aggregate(trades: list[Trade]) -> dict:
    n = len(trades)
    if not n:
        return {"count": 0}
    wins = [t for t in trades if (t.realized_pnl or 0) > 0]
    losses = [t for t in trades if (t.realized_pnl or 0) <= 0]
    total_pnl = sum((t.realized_pnl or 0) for t in trades)
    rs = [t.r_multiple for t in trades if t.r_multiple is not None]
    avg_r = sum(rs) / len(rs) if rs else 0.0
    win_rate = len(wins) / n
    avg_win = sum(t.realized_pnl for t in wins) / len(wins) if wins else 0.0
    avg_loss = sum(t.realized_pnl for t in losses) / len(losses) if losses else 0.0
    expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss
    return {
        "count": n,
        "win_rate": round(win_rate, 3),
        "avg_r": round(avg_r, 2),
        "expectancy": round(expectancy, 2),
        "total_pnl": round(total_pnl, 2),
        "wins": len(wins),
        "losses": len(losses),
    }
