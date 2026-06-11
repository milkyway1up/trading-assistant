"""Trending tickers from public social-momentum sources.

Sources (all free, no auth):
- ApeWisdom — aggregates Reddit ticker mentions across WSB / r/stocks /
  r/pennystocks / r/daytrading. Returns mention counts + 24h delta.
- StockTwits trending — boolean flag if a ticker is currently trending on ST.

The output is a deduped list ranked by total Reddit mentions, with per-source
flags so the UI can show which communities are talking about the ticker.
"""
from __future__ import annotations

import ssl
from functools import lru_cache
from typing import Any, Iterable

import httpx
import truststore
import yfinance as yf
from loguru import logger

# Use the OS keychain for trust roots — Python's bundled certifi sometimes rejects
# valid public certs (e.g. "Missing Authority Key Identifier" on macOS Sequoia).
_SSL_CTX = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

APEWISDOM_URL = "https://apewisdom.io/api/v1.0/filter/{filter}/page/1"
STOCKTWITS_URL = "https://api.stocktwits.com/api/2/trending/symbols.json"

# ApeWisdom filter → short label shown in the UI badge
_REDDIT_FILTERS: dict[str, str] = {
    "wallstreetbets": "WSB",
    "stocks": "RS",         # r/stocks  (RS chosen to avoid collision with StockTwits "ST")
    "pennystocks": "PS",
    "daytrading": "DT",
}

# Tickers ApeWisdom returns that aren't actually equities (or are noise).
_TICKER_BLOCKLIST = {
    "DD", "EV", "USA", "CEO", "CFO", "USD", "AI", "ATH", "IPO", "EOD",
    "PR", "FYI", "RIP", "YOLO", "FOMO", "EPS", "ETF", "AH", "PM",
}


def _http_get_json(url: str, timeout: float = 8.0) -> dict[str, Any] | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; trading-assistant/0.1)",
        "Accept": "application/json",
    }
    try:
        r = httpx.get(url, timeout=timeout, headers=headers, verify=_SSL_CTX, follow_redirects=True)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning("trending fetch failed for {}: {}", url, e)
        return None


def _fetch_apewisdom(filter_name: str, limit: int = 50) -> list[dict[str, Any]]:
    data = _http_get_json(APEWISDOM_URL.format(filter=filter_name))
    if not data:
        return []
    out: list[dict[str, Any]] = []
    for r in (data.get("results") or [])[:limit]:
        ticker = (r.get("ticker") or "").upper().strip()
        if not ticker or ticker in _TICKER_BLOCKLIST:
            continue
        out.append({
            "ticker": ticker,
            "name": r.get("name") or "",
            "mentions": int(r.get("mentions") or 0),
            "mentions_24h_ago": int(r.get("mentions_24h_ago") or 0),
            "upvotes": int(r.get("upvotes") or 0),
            "filter": filter_name,
        })
    return out


def _fetch_stocktwits_trending(limit: int = 30) -> set[str]:
    data = _http_get_json(STOCKTWITS_URL)
    if not data:
        return set()
    out: set[str] = set()
    for s in (data.get("symbols") or [])[:limit]:
        sym = (s.get("symbol") or "").upper().strip()
        # StockTwits includes crypto / forex; keep only plain tickers
        if sym and "." not in sym and "-" not in sym and sym not in _TICKER_BLOCKLIST:
            out.add(sym)
    return out


def _enrich_prices(tickers: Iterable[str]) -> dict[str, float | None]:
    tickers = list(dict.fromkeys(tickers))
    if not tickers:
        return {}
    prices: dict[str, float | None] = {t: None for t in tickers}
    # yfinance multi-ticker download — single request, much faster than per-ticker
    try:
        df = yf.download(
            tickers=" ".join(tickers),
            period="2d",
            interval="1d",
            progress=False,
            auto_adjust=False,
            threads=True,
            group_by="ticker",
        )
        if df is None or df.empty:
            return prices
        if len(tickers) == 1:
            t = tickers[0]
            if "Close" in df.columns:
                last = df["Close"].dropna()
                if len(last):
                    prices[t] = round(float(last.iloc[-1]), 4)
        else:
            for t in tickers:
                try:
                    sub = df[t]["Close"].dropna()
                    if len(sub):
                        prices[t] = round(float(sub.iloc[-1]), 4)
                except (KeyError, AttributeError):
                    continue
    except Exception as e:
        logger.warning("price enrich failed: {}", e)
    return prices


def fetch_trending(
    limit: int = 25,
    include_pennies: bool = True,
    min_mentions: int = 3,
) -> list[dict[str, Any]]:
    """Merge social-momentum sources into a single ranked ticker list.

    Returns rows shaped like:
        {
          "ticker": "GME",
          "name": "GameStop Corp.",
          "mentions": 482,
          "mentions_24h_ago": 311,
          "delta_pct": 55,
          "sources": ["WSB", "PS"],
          "stocktwits_trending": true,
          "last_price": 21.43,
          "is_penny": false
        }
    """
    merged: dict[str, dict[str, Any]] = {}
    for filt, label in _REDDIT_FILTERS.items():
        for row in _fetch_apewisdom(filt):
            t = row["ticker"]
            entry = merged.setdefault(t, {
                "ticker": t,
                "name": row["name"],
                "mentions": 0,
                "mentions_24h_ago": 0,
                "upvotes": 0,
                "sources": [],
            })
            # Use the largest single-subreddit count as the canonical mention number
            # (summing double-counts since posts can cross-post). Track all sources.
            entry["mentions"] = max(entry["mentions"], row["mentions"])
            entry["mentions_24h_ago"] = max(entry["mentions_24h_ago"], row["mentions_24h_ago"])
            entry["upvotes"] = max(entry["upvotes"], row["upvotes"])
            if label not in entry["sources"]:
                entry["sources"].append(label)
            if row["name"] and not entry["name"]:
                entry["name"] = row["name"]

    st_trending = _fetch_stocktwits_trending()
    for t in st_trending:
        entry = merged.setdefault(t, {
            "ticker": t, "name": "", "mentions": 0, "mentions_24h_ago": 0,
            "upvotes": 0, "sources": [],
        })
        entry["stocktwits_trending"] = True
    for entry in merged.values():
        entry.setdefault("stocktwits_trending", entry["ticker"] in st_trending)
        prev = entry["mentions_24h_ago"]
        cur = entry["mentions"]
        entry["delta_pct"] = round(((cur - prev) / prev) * 100) if prev else None

    rows = [r for r in merged.values() if r["mentions"] >= min_mentions or r.get("stocktwits_trending")]
    rows.sort(
        key=lambda r: (r["mentions"], 1 if r.get("stocktwits_trending") else 0),
        reverse=True,
    )
    rows = rows[: max(limit * 2, limit + 5)]  # over-fetch so the price filter has room

    prices = _enrich_prices(r["ticker"] for r in rows)
    out: list[dict[str, Any]] = []
    for r in rows:
        price = prices.get(r["ticker"])
        r["last_price"] = price
        r["is_penny"] = (price is not None and price < 5.0)
        if not include_pennies and r["is_penny"]:
            continue
        out.append(r)
        if len(out) >= limit:
            break
    return out


@lru_cache(maxsize=1)
def _filters_label_map() -> dict[str, str]:
    return dict(_REDDIT_FILTERS)
