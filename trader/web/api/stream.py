"""WebSocket endpoint for streaming live ticks + alerts to the browser.

If the configured broker has working credentials we forward its real tick
stream. Otherwise we emit a deterministic mock loop so the dashboard wiring
works end-to-end without needing keys.
"""
from __future__ import annotations

import asyncio
import json
import random
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from trader.config import get_config

router = APIRouter(tags=["stream"])

_clients: set[WebSocket] = set()


@router.websocket("/ws/stream")
async def stream(ws: WebSocket) -> None:
    await ws.accept()
    _clients.add(ws)
    try:
        await ws.send_text(json.dumps({"type": "hello", "ts": time.time()}))

        cfg = get_config()
        watchlist = cfg.watchlist or ["SPY", "AAPL", "NVDA", "TSLA", "MSFT"]

        if await _try_broker_stream(ws, watchlist):
            return

        # Fallback: deterministic mock loop so the UI is never silent.
        await _mock_stream(ws, watchlist)

    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)


async def _try_broker_stream(ws: WebSocket, tickers: list[str]) -> bool:
    """Try to forward the broker's tick stream. Return True if it ran (the
    websocket has been served) or False if we should fall back."""
    try:
        from trader.broker.factory import get_data_client

        client = get_data_client()
    except Exception as e:
        logger.debug("Broker stream unavailable, using mock: {}", e)
        return False

    try:
        async for tick in client.start_stream(tickers):
            await ws.send_text(json.dumps(tick))
    except WebSocketDisconnect:
        raise
    except NotImplementedError:
        return False
    except Exception as e:
        logger.warning("Broker stream errored, falling back to mock: {}", e)
        return False
    return True


async def _mock_stream(ws: WebSocket, tickers: list[str]) -> None:
    rng = random.Random()
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
