"""Browser toast alerts via WebSocket broadcast. Phase 1."""
from __future__ import annotations

from typing import Any


async def broadcast_alert(payload: dict[str, Any]) -> None:
    """Push an alert to all connected dashboard WS clients."""
    from trader.web.api.stream import broadcast

    await broadcast({"type": "alert", **payload})
