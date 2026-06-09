"""Multiplex alert delivery across audio / desktop / browser channels. Phase 1."""
from __future__ import annotations

import asyncio
from datetime import datetime

from loguru import logger

from trader.alerts import audio, browser, desktop
from trader.alerts.rules import CompiledRule, evaluate, mark_fired


async def fire(rule: CompiledRule, snapshot: dict, channels: list[str] | None = None) -> None:
    """Fire all configured channels concurrently. Channels: audio, desktop, browser."""
    channels = channels or ["audio", "desktop", "browser"]
    title = f"{rule.ticker} alert"
    msg = rule.name

    tasks = []
    if "audio" in channels:
        tasks.append(audio.speak(f"{rule.ticker}: {rule.name}"))
    if "desktop" in channels:
        tasks.append(desktop.notify(title, msg, subtitle=rule.timeframe))
    if "browser" in channels:
        tasks.append(browser.broadcast_alert({
            "rule": rule.name,
            "ticker": rule.ticker,
            "timeframe": rule.timeframe,
            "snapshot": {k: v for k, v in snapshot.items() if isinstance(v, (int, float, str))},
            "ts": datetime.utcnow().isoformat() + "Z",
        }))

    await asyncio.gather(*tasks, return_exceptions=True)
    mark_fired(rule)
    logger.info(f"Alert fired: {rule.ticker} / {rule.name}")


async def evaluate_and_fire(rules: list[CompiledRule], ticker: str, snapshot: dict) -> int:
    """Evaluate every rule for a given ticker against an indicator snapshot.
    Returns the count of rules fired."""
    fired = 0
    for rule in rules:
        if rule.ticker and rule.ticker != ticker:
            continue
        if evaluate(rule, snapshot):
            await fire(rule, snapshot)
            fired += 1
    return fired
