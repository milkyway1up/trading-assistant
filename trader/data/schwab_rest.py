"""Schwab REST data client — /pricehistory + /quotes. Wired in Phase 1."""
from __future__ import annotations

from typing import Any, AsyncIterator

import pandas as pd

from trader.broker.base import DataClient


class SchwabRestDataClient(DataClient):
    """Concrete DataClient backed by Schwab's REST endpoints. Stub until Phase 1."""

    def get_price_history(
        self,
        ticker: str,
        *,
        timeframe: str,
        period: str,
    ) -> pd.DataFrame:
        raise NotImplementedError("Schwab /pricehistory — wired in Phase 1.")

    def get_quote(self, ticker: str) -> dict[str, Any]:
        raise NotImplementedError("Schwab /quotes — wired in Phase 1.")

    async def start_stream(self, tickers: list[str]) -> AsyncIterator[dict[str, Any]]:
        raise NotImplementedError("Schwab StreamerClient — wired in Phase 1.")
        # Hint to type-checkers that this is an async generator.
        if False:  # pragma: no cover
            yield {}
