"""Weekly market prep document generator."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import yfinance as yf
from loguru import logger

from trader.config import get_config, prep_dir
from trader.llm.client import call_claude
from trader.llm.prompts import PREP_SYSTEM


def generate_weekly_prep(output_path: Optional[Path] = None) -> Path:
    """Generate a markdown prep doc and save to prep/YYYY-MM-DD.md."""
    cfg = get_config()
    watchlist = cfg.watchlist or ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]

    monday = _next_monday()

    # Quick top-of-watchlist snapshot
    snapshots = []
    for t in watchlist[:15]:
        try:
            yt = yf.Ticker(t)
            hist = yt.history(period="2mo", interval="1d", auto_adjust=False)
            if hist.empty:
                continue
            last = float(hist["Close"].iloc[-1])
            ago_5 = float(hist["Close"].iloc[-6]) if len(hist) >= 6 else last
            ago_20 = float(hist["Close"].iloc[-21]) if len(hist) >= 21 else last
            snapshots.append({
                "ticker": t,
                "last": round(last, 2),
                "5d_change_pct": round((last - ago_5) / ago_5 * 100, 2),
                "20d_change_pct": round((last - ago_20) / ago_20 * 100, 2),
            })
        except Exception as e:
            logger.debug("Snapshot failed for {}: {}", t, e)

    # Earnings — yfinance has limited coverage; populate what we can
    earnings = []
    for t in watchlist[:15]:
        try:
            cal = yf.Ticker(t).calendar
            if cal is not None and not (hasattr(cal, "empty") and cal.empty):
                # cal can be a dict (newer yfinance) or DataFrame (older)
                if isinstance(cal, dict):
                    next_earnings = cal.get("Earnings Date")
                    if next_earnings:
                        # Often a list of datetimes
                        edate = next_earnings[0] if isinstance(next_earnings, list) else next_earnings
                        earnings.append({"ticker": t, "date": str(edate)[:10]})
        except Exception:
            pass

    # Setups — Phase 2 will populate; for v1 skeleton, leave empty.
    top_setups: list[dict[str, Any]] = []

    # Open positions — Phase 3 will populate from Schwab; empty for now.
    open_positions: list[dict[str, Any]] = []

    # Journal stats — Phase 4 will populate; empty for now.
    journal_stats: dict[str, Any] = {
        "trade_count_30d": 0,
        "win_rate": None,
        "avg_r": None,
        "note": "Journal stats unavailable until Phase 4 is wired.",
    }

    context = {
        "week_starting": monday.isoformat(),
        "watchlist_snapshots": snapshots,
        "top_setups": top_setups,
        "earnings_this_week": earnings,
        "macro_events": _placeholder_macro(),
        "open_positions": open_positions,
        "journal_stats_30d": journal_stats,
    }

    user_msg = (
        f"Produce the weekly prep markdown doc for the week starting {monday}. "
        f"Use this context (JSON):\n\n```json\n{_compact_json(context)}\n```"
    )

    md = call_claude(
        system=PREP_SYSTEM,
        user=user_msg,
        cache_system=True,
        json_response=False,
        max_tokens=4000,
    )

    out = output_path or (prep_dir() / f"{monday.isoformat()}.md")
    out.write_text(md if isinstance(md, str) else str(md))
    return out


def _next_monday(today: Optional[date] = None) -> date:
    today = today or date.today()
    days_ahead = (7 - today.weekday()) % 7  # Monday = 0
    if days_ahead == 0:
        # If it's Monday, the prep is for *today*'s week
        return today
    return today + timedelta(days=days_ahead)


def _placeholder_macro() -> list[dict[str, str]]:
    """Phase-2+ this from a calendar feed (FRED, ForexFactory). For now empty."""
    return [{"note": "Macro calendar not yet wired — verify Fed/CPI dates manually."}]


def _compact_json(obj: Any) -> str:
    import json
    return json.dumps(obj, separators=(",", ":"), default=str)
