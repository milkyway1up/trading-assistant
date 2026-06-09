"""Pull Schwab transactions and pair entries with exits in the journal. Phase 4."""
from __future__ import annotations


def sync_from_schwab() -> int:
    """Pull /accounts/{accountId}/transactions, upsert into Trade rows, pair
    buys with sells (FIFO per ticker), compute realized P&L + R-multiple.
    Returns the count of newly synced trades.

    Wired in Phase 4.
    """
    raise NotImplementedError("Schwab transactions sync — wired in Phase 4.")
