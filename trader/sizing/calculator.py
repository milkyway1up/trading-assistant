"""Position size calculator: shares = (equity * risk_pct) / (entry - stop)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SizingResult:
    shares: int
    dollar_risk: float
    dollar_position: float
    risk_pct_actual: float
    note: str = ""


def position_size(
    *,
    account_equity: float,
    risk_pct: float,
    entry: float,
    stop: float,
) -> SizingResult:
    """Return integer share count for the given account risk %.

    Args:
        account_equity: total account equity ($)
        risk_pct: % of equity to risk on this trade (e.g. 1.5 = 1.5%)
        entry: planned entry price
        stop: stop-loss price (must be != entry)
    """
    if entry <= 0:
        return SizingResult(0, 0, 0, 0, "Invalid entry price")
    if entry == stop:
        return SizingResult(0, 0, 0, 0, "Stop equals entry — set a real stop")

    dollar_risk_target = account_equity * (risk_pct / 100)
    per_share_risk = abs(entry - stop)
    raw_shares = dollar_risk_target / per_share_risk
    shares = int(raw_shares)  # round down — never oversized

    if shares < 1:
        return SizingResult(
            0, 0, 0, 0,
            f"Risk budget ${dollar_risk_target:.2f} too small for per-share risk "
            f"${per_share_risk:.2f}. Either widen risk %, tighten stop, or pass.",
        )

    actual_dollar_risk = shares * per_share_risk
    dollar_position = shares * entry
    risk_pct_actual = actual_dollar_risk / account_equity * 100 if account_equity else 0

    return SizingResult(
        shares=shares,
        dollar_risk=round(actual_dollar_risk, 2),
        dollar_position=round(dollar_position, 2),
        risk_pct_actual=round(risk_pct_actual, 3),
    )
