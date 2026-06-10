"""Schwab WebSocket streamer — kept as a separate module for the live tick path.

The factory currently returns `SchwabRestDataClient` which inlines its own
`start_stream` stub; if/when the streaming wiring lands in Phase 1 it can be
moved here and `SchwabRestDataClient.start_stream` can delegate.
"""
from __future__ import annotations


async def start_stream(tickers: list[str]) -> None:
    raise NotImplementedError("Schwab StreamerClient — wired in Phase 1.")
