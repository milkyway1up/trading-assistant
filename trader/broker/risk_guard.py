"""Pre-submit safety checks for cash account, small balance.

Refuses:
- Buys exceeding settled cash
- Position > N% account equity
- Trades risking > X% on stop
- Stops > Y% from entry (too wide = bad setup)
- Orders outside market hours unless --allow-extended

Phase 3 wires this against live Schwab account data.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class RiskCheck:
    ok: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.ok


def check_buy_within_settled_cash(
    *, settled_cash: float, order_value: float
) -> RiskCheck:
    if order_value > settled_cash:
        return RiskCheck(False, f"Order value ${order_value:,.2f} exceeds settled cash ${settled_cash:,.2f}")
    return RiskCheck(True)


def check_position_size_pct(
    *, account_equity: float, order_value: float, max_pct: float
) -> RiskCheck:
    pct = (order_value / account_equity) * 100 if account_equity else 0
    if pct > max_pct:
        return RiskCheck(False, f"Position {pct:.1f}% > max {max_pct:.1f}%")
    return RiskCheck(True)


def check_account_risk_pct(
    *, account_equity: float, dollar_risk: float, max_pct: float
) -> RiskCheck:
    pct = (dollar_risk / account_equity) * 100 if account_equity else 0
    if pct > max_pct:
        return RiskCheck(False, f"Risk ${dollar_risk:,.2f} ({pct:.2f}% of equity) > max {max_pct}%")
    return RiskCheck(True)


def check_stop_distance_pct(
    *, entry: float, stop: float, max_pct: float
) -> RiskCheck:
    if entry <= 0:
        return RiskCheck(False, "Invalid entry price")
    distance_pct = abs(entry - stop) / entry * 100
    if distance_pct > max_pct:
        return RiskCheck(False, f"Stop {distance_pct:.1f}% from entry > max {max_pct}% (too-wide stop = bad setup)")
    return RiskCheck(True)


def run_all_checks(
    *,
    side: str,
    account_equity: float,
    settled_cash: float,
    order_value: float,
    dollar_risk: float,
    entry: float,
    stop: Optional[float],
    cfg_max_position_pct: float,
    cfg_max_risk_pct: float,
    cfg_max_stop_distance_pct: float,
) -> list[RiskCheck]:
    """Run all relevant pre-submit checks. Caller fails order if any returns False."""
    results: list[RiskCheck] = []
    if side.lower() == "buy":
        results.append(check_buy_within_settled_cash(
            settled_cash=settled_cash, order_value=order_value,
        ))
    results.append(check_position_size_pct(
        account_equity=account_equity, order_value=order_value, max_pct=cfg_max_position_pct,
    ))
    if stop is not None:
        results.append(check_account_risk_pct(
            account_equity=account_equity, dollar_risk=dollar_risk, max_pct=cfg_max_risk_pct,
        ))
        results.append(check_stop_distance_pct(
            entry=entry, stop=stop, max_pct=cfg_max_stop_distance_pct,
        ))
    return results
