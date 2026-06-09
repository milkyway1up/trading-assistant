"""YAML alert rule DSL → predicate evaluator. Phase 1."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

# Allowed identifiers in rule expressions — anything else parses as a syntax error.
_ALLOWED_NAMES = {
    "price", "open", "high", "low", "close", "volume",
    "rsi_14", "ema_20", "ema_50", "ema_200", "atr_14",
    "macd", "macd_signal",
    "and", "or", "not", "True", "False", "None",
    "abs", "min", "max",
}

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


@dataclass
class CompiledRule:
    name: str
    ticker: str
    timeframe: str
    expression: str
    cooldown_hours: float
    last_fired: datetime | None = None

    def is_in_cooldown(self, now: datetime | None = None) -> bool:
        if self.last_fired is None:
            return False
        now = now or datetime.utcnow()
        return now - self.last_fired < timedelta(hours=self.cooldown_hours)


def _validate_expression(expr: str) -> None:
    for tok in _TOKEN_RE.findall(expr):
        if tok in _ALLOWED_NAMES:
            continue
        if tok.replace("_", "").isdigit():
            continue
        raise ValueError(f"Disallowed identifier in alert rule: {tok!r}")


def compile_rule(raw: dict) -> CompiledRule:
    name = raw["name"]
    expr = raw["when"]
    _validate_expression(expr)
    return CompiledRule(
        name=name,
        ticker=raw.get("ticker", ""),
        timeframe=raw.get("timeframe", "daily"),
        expression=expr,
        cooldown_hours=float(raw.get("cooldown_hours", 24)),
    )


def evaluate(rule: CompiledRule, snapshot: dict[str, Any]) -> bool:
    """Evaluate a compiled rule against an indicator snapshot. Returns False on
    missing keys (not raises) so partial data doesn't spam alerts."""
    if rule.is_in_cooldown():
        return False
    namespace = {k: snapshot.get(k) for k in _ALLOWED_NAMES if k in snapshot}
    namespace.update({"abs": abs, "min": min, "max": max})
    try:
        return bool(eval(rule.expression, {"__builtins__": {}}, namespace))
    except (TypeError, KeyError):
        return False


def mark_fired(rule: CompiledRule, when: datetime | None = None) -> None:
    rule.last_fired = when or datetime.utcnow()
