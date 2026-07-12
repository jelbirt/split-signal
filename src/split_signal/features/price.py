"""Price-based features (all as_of-anchored).

Return/volatility features use adj_close: future splits and dividends
rescale the whole adjusted series multiplicatively, so ratios — and
therefore these features — are invariant to post-as_of data.
"""

from __future__ import annotations

import math

import pandas as pd

from split_signal.data.splits import unadjusted_close
from split_signal.features.base import InsufficientHistoryError, known_bars


def trailing_return(
    prices: pd.DataFrame,
    as_of: pd.Timestamp,
    days: int = 365,
    min_coverage: float = 0.9,
) -> float:
    """Total return over the `days` calendar days ending at as_of."""
    bars = known_bars(prices, as_of)
    window_start = as_of - pd.Timedelta(days=days)
    if bars["date"].min() > as_of - pd.Timedelta(days=int(days * min_coverage)):
        raise InsufficientHistoryError(
            f"need ~{days}d of history before {as_of.date()}, "
            f"have data from {bars['date'].min().date()}"
        )
    series = bars.set_index("date")["adj_close"]
    start_value = float(series.asof(window_start))
    if not math.isfinite(start_value):
        # History passed the coverage guard but starts after window_start,
        # so asof found no bar; raising beats silently returning NaN.
        raise InsufficientHistoryError(
            f"no bar at or before window start {window_start.date()}, "
            f"have data from {bars['date'].min().date()}"
        )
    end_value = float(series.iloc[-1])
    return end_value / start_value - 1.0


def true_price_level(prices: pd.DataFrame, as_of: pd.Timestamp) -> float:
    """The price the stock actually traded at on as_of (unadjusted).

    Deliberately uses the FULL frame, including post-as_of split events:
    provider close series are back-adjusted for later splits, and undoing
    that requires the later ratios. This recovers a historical fact (the
    as-traded price) and leaks no future information into the feature.
    """
    reconstructed = unadjusted_close(prices)
    dated = pd.Series(reconstructed.to_numpy(), index=prices["date"].to_numpy()).sort_index()
    knowable = dated.loc[:as_of]
    if knowable.empty:
        raise InsufficientHistoryError(f"no price bars on or before {as_of.date()}")
    return float(knowable.iloc[-1])


def ath_drawdown(prices: pd.DataFrame, as_of: pd.Timestamp) -> float:
    """Distance from the all-time (known) high: 0.0 at the high, negative below."""
    bars = known_bars(prices, as_of)
    series = bars["adj_close"]
    return float(series.iloc[-1] / series.max() - 1.0)


def annualized_volatility(
    prices: pd.DataFrame, as_of: pd.Timestamp, days: int = 252
) -> float:
    """Annualized std of daily returns over the trailing `days` bars."""
    bars = known_bars(prices, as_of)
    if len(bars) < days // 2:
        raise InsufficientHistoryError(
            f"need >= {days // 2} bars before {as_of.date()}, have {len(bars)}"
        )
    returns = bars["adj_close"].tail(days).pct_change().dropna()
    return float(returns.std(ddof=1) * math.sqrt(252))
