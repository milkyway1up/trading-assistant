"""Cash-account settlement tracker. T+1 since 2024-05-28.

Phase 3 wires this against Schwab /accounts.
"""
from __future__ import annotations

from datetime import date, timedelta

from typing import Iterable


# US market holidays — minimal list, expand annually. For accurate settlement
# windows we should pull from a real calendar (pandas_market_calendars).
US_MARKET_HOLIDAYS: set[date] = set()


def is_business_day(d: date) -> bool:
    return d.weekday() < 5 and d not in US_MARKET_HOLIDAYS


def next_business_day(d: date, *, n: int = 1) -> date:
    out = d
    for _ in range(n):
        out = out + timedelta(days=1)
        while not is_business_day(out):
            out = out + timedelta(days=1)
    return out


def settlement_date(trade_date: date) -> date:
    """T+1 settlement: proceeds settle 1 business day after trade date."""
    return next_business_day(trade_date, n=1)


def free_riding_warning(unsettled_proceeds: float, pending_buy_value: float) -> str | None:
    """If a buy would consume unsettled funds, warn (good-faith violation territory).

    Schwab's actual rule: in a cash account, you can buy with unsettled proceeds,
    but if you SELL that new position before the original sale settles, that's a
    good-faith violation. Three of those in 12 months → 90-day cash-only restriction.
    """
    if pending_buy_value > 0 and unsettled_proceeds > 0:
        return (
            f"Buying with ${unsettled_proceeds:.2f} unsettled proceeds is OK, but you "
            f"can't sell the new position until proceeds settle without a "
            f"good-faith violation."
        )
    return None
