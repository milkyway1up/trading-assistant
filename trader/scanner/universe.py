"""Trading universe: S&P 500 + NASDAQ 100 + user watchlist. Phase 2."""
from __future__ import annotations

from functools import lru_cache

# Hard-coded liquid mega-cap starter universe; replace with a maintained list
# (Wikipedia scrape or a pinned CSV) once Phase 2 is wired.
_DEFAULT_UNIVERSE: list[str] = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO",
    "AMD", "NFLX", "CRM", "ORCL", "ADBE", "QCOM", "INTC", "CSCO",
    "JPM", "V", "MA", "BAC", "WFC", "GS", "MS",
    "UNH", "JNJ", "LLY", "PFE", "MRK", "ABBV",
    "WMT", "COST", "HD", "LOW", "TGT", "MCD", "SBUX", "NKE",
    "XOM", "CVX", "COP",
    "CAT", "DE", "BA", "LMT", "RTX", "GE",
    "DIS", "T", "VZ", "CMCSA",
    "SPY", "QQQ", "IWM", "DIA",
]


@lru_cache(maxsize=1)
def default_universe() -> list[str]:
    return list(_DEFAULT_UNIVERSE)


def universe_with_watchlist(watchlist: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in default_universe() + list(watchlist):
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out
