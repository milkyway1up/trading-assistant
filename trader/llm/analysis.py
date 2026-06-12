"""On-demand LLM analysis of a single ticker."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import yfinance as yf
from loguru import logger

from trader.llm.client import call_claude
from trader.llm.prompts import ANALYST_SYSTEM, BATCH_RATER_SYSTEM, MOMENTUM_RATER_SYSTEM, SETUP_RATER_SYSTEM


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


def _fetch_context_light(ticker: str) -> dict[str, Any]:
    """Lightweight context for setup rating: 30d daily bars + news, no hourly."""
    yf_ticker = yf.Ticker(ticker)

    daily = yf_ticker.history(period="3mo", interval="1d", auto_adjust=False)
    daily_rows = []
    for idx, row in daily.tail(30).iterrows():
        daily_rows.append({
            "date": idx.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
        })

    news = []
    try:
        for n in (yf_ticker.news or [])[:5]:
            content = n.get("content") or n
            news.append({
                "title": content.get("title") or content.get("headline", ""),
                "publisher": (content.get("provider") or {}).get("displayName")
                              or content.get("publisher", ""),
                "published": content.get("pubDate") or content.get("providerPublishTime", ""),
            })
    except Exception as e:
        logger.debug("News fetch failed for {}: {}", ticker, e)

    info = yf_ticker.fast_info if hasattr(yf_ticker, "fast_info") else {}
    last_price = info.get("last_price") or info.get("lastPrice")

    return {
        "ticker": ticker,
        "as_of": datetime.utcnow().isoformat(),
        "last_price": float(last_price) if last_price else None,
        "daily_bars_last_30d": daily_rows,
        "news": news,
    }


def rate_setup(ticker: str, setup: dict[str, Any]) -> dict[str, Any]:
    """Quick Claude rating of a single scanner-detected setup.

    Returns {"rating": int 1-10, "reason": str}. Falls back to {"rating": None,
    "reason": <error>} if Claude returns malformed output.
    """
    ticker = ticker.upper()
    context = _fetch_context_light(ticker)
    context["setup"] = setup

    user_msg = f"Rate this setup:\n```json\n{_compact_json(context)}\n```"
    result = call_claude(
        system=SETUP_RATER_SYSTEM,
        user=user_msg,
        cache_system=True,
        json_response=True,
        max_tokens=200,
    )
    if not isinstance(result, dict):
        return {"rating": None, "reason": f"non-dict response: {result!r}"}
    rating = result.get("rating")
    try:
        rating = int(rating) if rating is not None else None
    except (TypeError, ValueError):
        rating = None
    return {"rating": rating, "reason": result.get("reason", "")}


def _fetch_context_minimal(ticker: str) -> dict[str, Any]:
    """Ultra-compact context for batch rating: last 5 bars + summary stats."""
    yf_ticker = yf.Ticker(ticker)

    daily = yf_ticker.history(period="3mo", interval="1d", auto_adjust=False)
    if daily.empty or len(daily) < 5:
        return {"ticker": ticker, "bars": [], "news": []}

    last_30 = daily.tail(30)
    last_5 = daily.tail(5)

    bars = []
    for idx, row in last_5.iterrows():
        bars.append({
            "d": idx.strftime("%m-%d"),
            "c": round(float(row["Close"]), 2),
            "v": round(float(row["Volume"]) / 1e6, 1),
        })

    avg_vol_20 = float(last_30["Volume"].mean()) if len(last_30) >= 20 else float(last_5["Volume"].mean())
    high_30 = float(last_30["High"].max())
    low_30 = float(last_30["Low"].min())
    close_30_ago = float(last_30.iloc[0]["Close"]) if len(last_30) >= 20 else float(last_5.iloc[0]["Close"])
    close_now = float(last_5.iloc[-1]["Close"])
    pct_30d = round((close_now - close_30_ago) / close_30_ago * 100, 1)

    news = []
    try:
        for n in (yf_ticker.news or [])[:3]:
            content = n.get("content") or n
            title = content.get("title") or content.get("headline", "")
            if title:
                news.append(title[:80])
    except Exception:
        pass

    return {
        "ticker": ticker,
        "price": close_now,
        "chg_30d": f"{pct_30d}%",
        "hi_30": high_30,
        "lo_30": low_30,
        "avg_vol_m": round(avg_vol_20 / 1e6, 1),
        "bars_5d": bars,
        "news": news,
    }


def rate_setups_batch(setups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rate all setups in a single Claude call. Much faster than per-setup calls.

    Uses minimal context (5 bars + stats per ticker) to keep the prompt small.
    Fetches data in parallel threads, then one Claude call for all ratings.
    """
    from concurrent.futures import ThreadPoolExecutor

    if not setups:
        return []

    def _fetch_one(s: dict) -> dict[str, Any]:
        ticker = (s.get("ticker") or "").upper()
        ctx = _fetch_context_minimal(ticker)
        ctx["setup"] = {
            k: s.get(k) for k in ("setup", "entry", "stop", "target", "risk_reward",
                                    "confidence", "reason", "side")
            if s.get(k) is not None
        }
        return ctx

    with ThreadPoolExecutor(max_workers=8) as pool:
        contexts = list(pool.map(_fetch_one, setups))

    user_msg = (
        f"Rate all {len(contexts)} setups. Return a JSON array, one object per setup, same order.\n\n"
        f"```json\n{_compact_json(contexts)}\n```"
    )

    result = call_claude(
        system=BATCH_RATER_SYSTEM,
        user=user_msg,
        cache_system=True,
        json_response=True,
        max_tokens=100 * len(setups),
    )

    if isinstance(result, list):
        ratings = []
        for i, r in enumerate(result):
            if not isinstance(r, dict):
                r = {}
            rating = r.get("rating")
            try:
                rating = int(rating) if rating is not None else None
            except (TypeError, ValueError):
                rating = None
            ratings.append({
                "ticker": r.get("ticker") or (setups[i].get("ticker") if i < len(setups) else "?"),
                "rating": rating,
                "reason": r.get("reason", ""),
            })
        return ratings

    logger.warning("Batch rater returned non-list: {}", type(result))
    return [{"ticker": s.get("ticker", "?"), "rating": None, "reason": "batch parse failed"} for s in setups]


def rate_momentum(ticker: str, social: dict[str, Any]) -> dict[str, Any]:
    """Claude rating for a socially-trending ticker, pump-risk aware.

    `social` is the row from `trader.data.trending.fetch_trending` for this ticker
    — mention count, 24h delta, source list, last_price, etc. The system prompt
    is tuned for the "is this a pump?" question rather than a swing setup.

    Returns {"rating": int 1-10 | None, "pump_risk": "low|medium|high",
    "verdict": "tradeable|watch|avoid", "reason": str}.
    """
    ticker = ticker.upper()
    context = _fetch_context_light(ticker)
    context["social"] = social

    user_msg = f"Rate this socially-trending ticker:\n```json\n{_compact_json(context)}\n```"
    result = call_claude(
        system=MOMENTUM_RATER_SYSTEM,
        user=user_msg,
        cache_system=True,
        json_response=True,
        max_tokens=250,
    )
    if not isinstance(result, dict):
        return {
            "rating": None, "pump_risk": "high", "verdict": "avoid",
            "reason": f"non-dict response: {result!r}",
        }
    rating = result.get("rating")
    try:
        rating = int(rating) if rating is not None else None
    except (TypeError, ValueError):
        rating = None
    return {
        "rating": rating,
        "pump_risk": result.get("pump_risk", "medium"),
        "verdict": result.get("verdict", "watch"),
        "reason": result.get("reason", ""),
    }


def _compact_json(obj: Any) -> str:
    import json
    return json.dumps(obj, separators=(",", ":"), default=str)
