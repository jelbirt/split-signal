"""Shared point-in-time filters for feature computation."""

from __future__ import annotations

import pandas as pd


class InsufficientHistoryError(ValueError):
    """Raised when a feature lacks the history it needs at `as_of`."""


def known_bars(prices: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Price bars knowable at as_of (date <= as_of), sorted by date."""
    bars = prices.loc[prices["date"] <= as_of].sort_values("date")
    if bars.empty:
        raise InsufficientHistoryError(f"no price bars on or before {as_of.date()}")
    return bars


def known_filings(fundamentals: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Fundamental rows whose filing was public at as_of (filed <= as_of)."""
    return fundamentals.loc[fundamentals["filed"] <= as_of]
