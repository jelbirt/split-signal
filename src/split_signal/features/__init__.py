"""Point-in-time-safe feature library.

Every feature takes an explicit `as_of` timestamp and uses only data
knowable on that date (price bars dated <= as_of; filings with
filed <= as_of). See tests/test_features.py for the invariance guards.
"""

from split_signal.features.base import InsufficientHistoryError
from split_signal.features.fundamental import (
    annual_metric_growth,
    market_cap,
    shares_outstanding_at,
)
from split_signal.features.price import (
    annualized_volatility,
    ath_drawdown,
    trailing_return,
    true_price_level,
)
from split_signal.features.structural import prior_split_count, years_since_last_split

__all__ = [
    "InsufficientHistoryError",
    "annual_metric_growth",
    "annualized_volatility",
    "ath_drawdown",
    "market_cap",
    "prior_split_count",
    "shares_outstanding_at",
    "trailing_return",
    "true_price_level",
    "years_since_last_split",
]
