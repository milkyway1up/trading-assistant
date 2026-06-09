"""WebSocket endpoint for streaming live ticks + alerts to the browser.

For now: a heartbeat + simulated quote ticks so the dashboard wiring works
end-to-end before Schwab streaming is hooked up.
"""
from __future__ import annotations

import asyncio
import json
import random
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["stream"])

_clients: set[WebSocket] = set()


@router.websocket("/ws/stream")
async def stream(ws: WebSocket) -> None:
    await ws.accept()
    _clients.add(ws)
    try:
        # Greet
        await ws.send_text(json.dumps({"type": "hello", "ts": time.time()}))

        # Mock ticker update loop until Schwab is wired
        rng = random.Random()
        tickers = ["SPY", "AAPL", "NVDA", "TSLA", "MSFT"]
        prices = {t: 100 + rng.uniform(0, 200) for t in tickers}

        while True:
            await asyncio.sleep(1.5)
            t = rng.choice(tickers)
            change_pct = rng.uniform(-0.3, 0.3) / 100
            prices[t] = max(1, prices[t] * (1 + change_pct))
            await ws.send_text(json.dumps({
                "type": "tick",
                "ticker": t,
                "price": round(prices[t], 2),
                "ts": time.time(),
                "source": "mock",
            }))

    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)


async def broadcast(payload: dict) -> None:
    """Send to every connected client. Used by the alerts notifier."""
    msg = json.dumps(payload)
    dead: list[WebSocket] = []
    for c in _clients:
        try:
            await c.send_text(msg)
        except Exception:
            dead.append(c)
    for c in dead:
        _clients.discard(c)
