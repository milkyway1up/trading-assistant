"""In-memory rolling window per ticker + tick pub/sub bus. Phase 1."""
from __future__ import annotations

from collections import defaultdict
from typing import Any


class TickBus:
    """Simple in-process pub/sub for tick → indicator → alert pipeline."""

    def __init__(self) -> None:
        self._subscribers: list[Any] = []

    def subscribe(self, fn) -> None:
        self._subscribers.append(fn)

    async def publish(self, msg: dict) -> None:
        for fn in self._subscribers:
            try:
                await fn(msg)
            except Exception:
                pass


_bus = TickBus()
_rolling: dict[str, list[dict]] = defaultdict(list)


def get_bus() -> TickBus:
    return _bus


def append_bar(ticker: str, bar: dict, max_keep: int = 500) -> None:
    _rolling[ticker].append(bar)
    if len(_rolling[ticker]) > max_keep:
        _rolling[ticker] = _rolling[ticker][-max_keep:]


def get_bars(ticker: str) -> list[dict]:
    return list(_rolling[ticker])
