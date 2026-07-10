"""Fundamental features anchored to SEC filing dates (all as_of-anchored)."""

from __future__ import annotations

import pandas as pd

from split_signal.features.base import InsufficientHistoryError, known_filings
from split_signal.features.price import true_price_level


def annual_metric_growth(
    fundamentals: pd.DataFrame,
    metric: str,
    as_of: pd.Timestamp,
    periods: int = 1,
) -> float:
    """Growth of the latest known annual `metric` vs. `periods` years earlier."""
    annual = known_filings(fundamentals, as_of)
    annual = annual[
        (annual["metric"] == metric) & (annual["period_type"] == "annual")
    ].sort_values("period_end")
    if len(annual) < periods + 1:
        raise InsufficientHistoryError(
            f"need {periods + 1} annual {metric} filings known at {as_of.date()}, "
            f"have {len(annual)}"
        )
    latest = float(annual["value"].iloc[-1])
    prior = float(annual["value"].iloc[-1 - periods])
    if prior == 0:
        raise InsufficientHistoryError(f"zero base value for {metric} growth")
    return latest / prior - 1.0


def shares_outstanding_at(fundamentals: pd.DataFrame, as_of: pd.Timestamp) -> float:
    """Most recently filed shares-outstanding figure known at as_of."""
    shares = known_filings(fundamentals, as_of)
    shares = shares[shares["metric"] == "shares_outstanding"].sort_values("filed")
    if shares.empty:
        raise InsufficientHistoryError(f"no shares-outstanding filing known at {as_of.date()}")
    return float(shares["value"].iloc[-1])


def market_cap(
    prices: pd.DataFrame, fundamentals: pd.DataFrame, as_of: pd.Timestamp
) -> float:
    """Shares outstanding x as-traded price, split-consistent.

    The shares figure is dated at its report date; any split between that
    date and as_of changed the share count, so the count is scaled by the
    intervening split ratios before multiplying by the as-traded price.
    """
    shares_rows = known_filings(fundamentals, as_of)
    shares_rows = shares_rows[shares_rows["metric"] == "shares_outstanding"].sort_values("filed")
    if shares_rows.empty:
        raise InsufficientHistoryError(f"no shares-outstanding filing known at {as_of.date()}")
    shares = float(shares_rows["value"].iloc[-1])
    reported = shares_rows["period_end"].iloc[-1]

    intervening = prices[
        (prices["date"] > reported) & (prices["date"] <= as_of) & (prices["split_ratio"] > 0)
    ]
    for ratio in intervening["split_ratio"]:
        shares *= float(ratio)

    return shares * true_price_level(prices, as_of)
