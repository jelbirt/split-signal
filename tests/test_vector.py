"""Feature-vector assembly: completeness and graceful degradation."""

import numpy as np
import pandas as pd

from split_signal.features.vector import FEATURE_NAMES, compute_feature_vector

AS_OF = pd.Timestamp("2020-08-01")


def _prices() -> pd.DataFrame:
    dates = pd.date_range(end=AS_OF, periods=1200, freq="D")
    df = pd.DataFrame({"date": dates, "close": np.linspace(100.0, 300.0, 1200)})
    df["adj_close"] = df["close"]
    df["open"] = df["high"] = df["low"] = df["close"]
    df["volume"] = 1_000_000
    df["dividends"] = 0.0
    df["split_ratio"] = 0.0
    df["source"] = "test"
    return df


def _catalog() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ["ACME"],
            "date": [pd.Timestamp("2018-05-01")],
            "ratio": [2.0],
            "is_forward": [True],
        }
    )


def test_vector_has_all_features_plus_keys() -> None:
    vector = compute_feature_vector("ACME", AS_OF, _prices(), None, _catalog())
    assert set(vector) == {"ticker", "as_of", *FEATURE_NAMES}


def test_price_features_computed_fundamentals_none_when_missing() -> None:
    vector = compute_feature_vector("ACME", AS_OF, _prices(), None, _catalog())
    assert vector["ret_1y"] is not None
    assert vector["prior_splits"] == 1
    assert vector["revenue_growth"] is None
    assert vector["eps_growth"] is None
    assert vector["market_cap"] is None


def test_short_history_degrades_to_none_not_error() -> None:
    short = _prices().tail(100).reset_index(drop=True)
    vector = compute_feature_vector("ACME", AS_OF, short, None, _catalog())
    assert vector["ret_3y"] is None
    assert vector["ath_drawdown"] is not None
