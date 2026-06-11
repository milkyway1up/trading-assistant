"""WebSocket endpoint for streaming live ticks + alerts to the browser.

If the configured broker has working credentials we run ONE shared Alpaca
stream and fan ticks out to every connected browser tab.  Alpaca's free tier
allows only 1 concurrent WebSocket — this avoids "connection limit exceeded".

Without broker keys we emit a deterministic mock loop so the dashboard wiring
works end-to-end.
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

# Shared broker stream state
_broker_task: asyncio.Task | None = None
_broker_queue: asyncio.Queue[dict] | None = None
_broker_available: bool | None = None  # None = not yet probed


async def _start_shared_broker_stream(tickers: list[str]) -> bool:
    """Start the single shared Alpaca stream if not already running.
    Returns True if a broker stream is available."""
    global _broker_task, _broker_queue, _broker_available

    if _broker_available is False:
        return False

    if _broker_task is not None and not _broker_task.done():
        return True

    try:
        from trader.broker.factory import get_data_client
        client = get_data_client()
    except Exception as e:
        logger.debug("Broker stream unavailable, using mock: {}", e)
        _broker_available = False
        return False

    _broker_queue = asyncio.Queue()

    async def _run() -> None:
        global _broker_available
        try:
            async for tick in client.start_stream(tickers):
                if _broker_queue is not None:
                    await _broker_queue.put(tick)
        except NotImplementedError:
            _broker_available = False
        except Exception as e:
            logger.warning("Broker stream stopped: {}", e)
            _broker_available = False

    _broker_task = asyncio.get_running_loop().create_task(_run())
    _broker_available = True
    return True


async def _fan_out(ws: WebSocket) -> None:
    """Read from the shared broker queue and forward to this client."""
    while True:
        tick = await _broker_queue.get()
        try:
            await ws.send_text(json.dumps(tick))
        except Exception:
            return
        # Also broadcast to any other clients that joined after
        await _broadcast_tick(tick, exclude=ws)


async def _broadcast_tick(tick: dict, exclude: WebSocket | None = None) -> None:
    """Send a tick to all connected clients except the one already served."""
    msg = json.dumps(tick)
    dead: list[WebSocket] = []
    for c in _clients:
        if c is exclude:
            continue
        try:
            await c.send_text(msg)
        except Exception:
            dead.append(c)
    for c in dead:
        _clients.discard(c)


@router.websocket("/ws/stream")
async def stream(ws: WebSocket) -> None:
    await ws.accept()
    _clients.add(ws)
    try:
        await ws.send_text(json.dumps({"type": "hello", "ts": time.time()}))

        cfg = get_config()
        watchlist = cfg.watchlist or ["SPY", "AAPL", "NVDA", "TSLA", "MSFT"]

        if await _start_shared_broker_stream(watchlist):
            await _fan_out(ws)
        else:
            await _mock_stream(ws, watchlist)

    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)


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
