"""Exit-grading: Claude grades a closed trade against its entry thesis."""
from __future__ import annotations

from typing import Any

from trader.llm.client import call_claude
from trader.llm.prompts import GRADE_SYSTEM


def grade_trade(trade: dict[str, Any], post_entry_bars: list[dict]) -> dict[str, Any]:
    """Grade a closed trade.

    Args:
        trade: dict with keys ticker, side, entry_time, entry_price, exit_time,
               exit_price, size, stop, target, thesis_at_entry, exit_reason.
        post_entry_bars: list of daily bars from entry_time to exit_time + 5.
    """
    user_msg = (
        f"Grade this trade. Thesis at entry, the actual entry/exit, and the price "
        f"action between (and shortly after) the trade are below.\n\n"
        f"```json\n{_compact_json({'trade': trade, 'bars': post_entry_bars})}\n```\n\n"
        f"Return JSON only."
    )

    return call_claude(
        system=GRADE_SYSTEM,
        user=user_msg,
        cache_system=True,
        json_response=True,
        max_tokens=800,
    )


def _compact_json(obj: Any) -> str:
    import json
    return json.dumps(obj, separators=(",", ":"), default=str)
