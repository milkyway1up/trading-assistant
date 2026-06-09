"""Schwab REST: /pricehistory, /quotes. Phase 1."""
from __future__ import annotations

import pandas as pd


def get_price_history(
    ticker: str,
    *,
    period_type: str = "year",
    period: int = 2,
    frequency_type: str = "daily",
    frequency: int = 1,
) -> pd.DataFrame:
    raise NotImplementedError("Schwab /pricehistory — wired in Phase 1.")


def get_quote(ticker: str) -> dict:
    raise NotImplementedError("Schwab /quotes — wired in Phase 1.")
