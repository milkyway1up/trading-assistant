"""On-demand LLM analysis of a single ticker."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import yfinance as yf
from loguru import logger

from trader.llm.client import call_claude
from trader.llm.prompts import ANALYST_SYSTEM


def _fetch_context(ticker: str) -> dict[str, Any]:
    """Pull the data we feed to Claude for analysis."""
    yf_ticker = yf.Ticker(ticker)

    # Daily bars (last 90 trading days)
    daily = yf_ticker.history(period="6mo", interval="1d", auto_adjust=False)
    daily_rows = []
    for idx, row in daily.tail(90).iterrows():
        daily_rows.append({
            "date": idx.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
        })

    # Hourly bars (last 10 trading days)
    hourly = yf_ticker.history(period="1mo", interval="60m", auto_adjust=False)
    hourly_rows = []
    for idx, row in hourly.tail(70).iterrows():
        hourly_rows.append({
            "ts": idx.strftime("%Y-%m-%d %H:%M"),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
        })

    # News (yfinance returns a list of dicts with title, publisher, published)
    news = []
    try:
        for n in (yf_ticker.news or [])[:8]:
            content = n.get("content") or n  # newer yfinance schema
            news.append({
                "title": content.get("title") or content.get("headline", ""),
                "publisher": (content.get("provider") or {}).get("displayName")
                              or content.get("publisher", ""),
                "published": content.get("pubDate") or content.get("providerPublishTime", ""),
                "summary": content.get("summary", "")[:300],
            })
    except Exception as e:
        logger.warning("News fetch failed for {}: {}", ticker, e)

    info = yf_ticker.fast_info if hasattr(yf_ticker, "fast_info") else {}
    last_price = info.get("last_price") or info.get("lastPrice")
    market_cap = info.get("market_cap") or info.get("marketCap")

    return {
        "ticker": ticker,
        "as_of": datetime.utcnow().isoformat(),
        "last_price": float(last_price) if last_price else None,
        "market_cap": int(market_cap) if market_cap else None,
        "daily_bars_last_90d": daily_rows,
        "hourly_bars_last_10d": hourly_rows,
        "news": news,
    }


def analyze_ticker(ticker: str, with_position: bool = False) -> dict[str, Any]:
    """Generate an analyst thesis for a single ticker."""
    ticker = ticker.upper()
    logger.info("Fetching context for {}...", ticker)
    context = _fetch_context(ticker)

    if with_position:
        # Pull current broker position (Alpaca/Schwab) if one exists.
        try:
            from trader.broker.factory import get_broker
            pos = get_broker().get_position(ticker)
            if pos:
                context["current_position"] = pos
        except Exception as e:
            logger.debug("No broker position context: {}", e)

    user_msg = (
        f"Analyze the following ticker and produce a structured thesis as JSON only.\n\n"
        f"```json\n{_compact_json(context)}\n```"
    )

    result = call_claude(
        system=ANALYST_SYSTEM,
        user=user_msg,
        cache_system=True,
        json_response=True,
        max_tokens=1500,
    )

    if isinstance(result, dict):
        result.setdefault("ticker", ticker)
    return result if isinstance(result, dict) else {"ticker": ticker, "raw": result}


def _compact_json(obj: Any) -> str:
    import json
    return json.dumps(obj, separators=(",", ":"), default=str)
