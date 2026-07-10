"""Assemble the full point-in-time feature vector for one (ticker, as_of).

Missing inputs degrade gracefully: a feature that cannot be computed
(insufficient history, no fundamentals) is None, never a fabricated
value, so downstream analysis can weigh coverage honestly.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from split_signal.features.base import InsufficientHistoryError
from split_signal.features.fundamental import annual_metric_growth, market_cap
from split_signal.features.price import (
    annualized_volatility,
    ath_drawdown,
    trailing_return,
    true_price_level,
)
from split_signal.features.structural import prior_split_count, years_since_last_split

FEATURE_NAMES = [
    "ret_1y", "ret_2y", "ret_3y", "price_level", "ath_drawdown", "volatility",
    "revenue_growth", "eps_growth", "market_cap",
    "prior_splits", "years_since_last_split",
]


def _guarded(fn: Callable[[], float | None]) -> float | None:
    try:
        return fn()
    except (InsufficientHistoryError, KeyError, IndexError):
        return None


def compute_feature_vector(
    ticker: str,
    as_of: pd.Timestamp,
    prices: pd.DataFrame,
    fundamentals: pd.DataFrame | None,
    catalog: pd.DataFrame,
) -> dict:
    funda = fundamentals if fundamentals is not None else pd.DataFrame(
        columns=["metric", "period_end", "value", "filed", "period_type"]
    )
    return {
        "ticker": ticker,
        "as_of": as_of,
        "ret_1y": _guarded(lambda: trailing_return(prices, as_of, days=365)),
        "ret_2y": _guarded(lambda: trailing_return(prices, as_of, days=730)),
        "ret_3y": _guarded(lambda: trailing_return(prices, as_of, days=1095)),
        "price_level": _guarded(lambda: true_price_level(prices, as_of)),
        "ath_drawdown": _guarded(lambda: ath_drawdown(prices, as_of)),
        "volatility": _guarded(lambda: annualized_volatility(prices, as_of)),
        "revenue_growth": _guarded(lambda: annual_metric_growth(funda, "revenue", as_of)),
        "eps_growth": _guarded(lambda: annual_metric_growth(funda, "eps_diluted", as_of)),
        "market_cap": _guarded(lambda: market_cap(prices, funda, as_of)),
        "prior_splits": prior_split_count(catalog, ticker, as_of),
        "years_since_last_split": years_since_last_split(catalog, ticker, as_of),
    }
