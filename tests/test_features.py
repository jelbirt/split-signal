"""Point-in-time feature library: known-answer tests + lookahead guards.

The invariance tests are the heart of this suite: any feature computed
as_of time T must be unchanged by appending post-T data — including the
realistic case where a future split makes the provider rescale the
entire historical close series.
"""

import numpy as np
import pandas as pd
import pytest

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

AS_OF = pd.Timestamp("2020-08-01")


def _price_frame(dates: pd.DatetimeIndex, close: np.ndarray, splits: dict | None = None):
    df = pd.DataFrame({"date": dates, "close": close})
    df["adj_close"] = df["close"]
    df["open"] = df["high"] = df["low"] = df["close"]
    df["volume"] = 1_000_000
    df["dividends"] = 0.0
    df["split_ratio"] = 0.0
    for day, ratio in (splits or {}).items():
        df.loc[df["date"] == pd.Timestamp(day), "split_ratio"] = ratio
    df["source"] = "test"
    return df


@pytest.fixture
def linear_prices():
    """730 daily bars ending 2020-08-01, adj_close rising 100 -> 200 linearly."""
    dates = pd.date_range(end=AS_OF, periods=730, freq="D")
    return _price_frame(dates, np.linspace(100.0, 200.0, 730))


class TestTrailingReturn:
    def test_known_answer_on_linear_series(self, linear_prices) -> None:
        result = trailing_return(linear_prices, as_of=AS_OF, days=365)
        start_value = float(
            linear_prices.set_index("date")["adj_close"].loc[AS_OF - pd.Timedelta(days=365)]
        )
        assert result == pytest.approx(200.0 / start_value - 1.0)

    def test_insufficient_history_raises(self, linear_prices) -> None:
        with pytest.raises(InsufficientHistoryError):
            trailing_return(linear_prices, as_of=AS_OF, days=3 * 365)

    def test_invariant_to_future_data(self, linear_prices) -> None:
        before = trailing_return(linear_prices, as_of=AS_OF, days=365)
        future = _price_frame(
            pd.date_range(AS_OF + pd.Timedelta(days=1), periods=200, freq="D"),
            np.full(200, 55.5),
        )
        extended = pd.concat([linear_prices, future], ignore_index=True)
        assert trailing_return(extended, as_of=AS_OF, days=365) == pytest.approx(before)

    def test_invariant_to_future_split_rescale(self, linear_prices) -> None:
        before = trailing_return(linear_prices, as_of=AS_OF, days=365)
        # A later 4:1 split makes the provider divide ALL history by 4.
        rescaled = linear_prices.copy()
        rescaled[["close", "adj_close"]] /= 4.0
        future = _price_frame(
            pd.date_range(AS_OF + pd.Timedelta(days=1), periods=30, freq="D"),
            np.full(30, 50.0),
            splits={str((AS_OF + pd.Timedelta(days=10)).date()): 4.0},
        )
        extended = pd.concat([rescaled, future], ignore_index=True)
        assert trailing_return(extended, as_of=AS_OF, days=365) == pytest.approx(before)


class TestPriceLevelAndDrawdown:
    def test_true_price_reconstructed_through_future_split(self) -> None:
        dates = pd.date_range("2020-08-28", periods=3, freq="D")
        frame = _price_frame(
            dates, np.array([124.8, 129.0, 134.2]), splits={"2020-08-29": 4.0}
        )
        # as_of the day BEFORE the split the stock actually traded ~499.
        assert true_price_level(frame, as_of=pd.Timestamp("2020-08-28")) == pytest.approx(499.2)
        assert true_price_level(frame, as_of=pd.Timestamp("2020-08-30")) == pytest.approx(134.2)

    def test_ath_drawdown_zero_at_high_negative_after(self) -> None:
        dates = pd.date_range(end=AS_OF, periods=100, freq="D")
        close = np.concatenate([np.linspace(50, 100, 60), np.linspace(100, 80, 40)])
        frame = _price_frame(dates, close)
        assert ath_drawdown(frame, as_of=dates[59]) == pytest.approx(0.0)
        assert ath_drawdown(frame, as_of=AS_OF) == pytest.approx(80.0 / 100.0 - 1.0)


class TestVolatility:
    def test_constant_return_series_has_zero_vol(self) -> None:
        dates = pd.date_range(end=AS_OF, periods=300, freq="D")
        frame = _price_frame(dates, 100.0 * 1.001 ** np.arange(300))
        assert annualized_volatility(frame, as_of=AS_OF, days=252) == pytest.approx(0.0, abs=1e-9)

    def test_volatile_series_positive(self) -> None:
        dates = pd.date_range(end=AS_OF, periods=300, freq="D")
        rng = np.random.default_rng(7)
        frame = _price_frame(dates, 100.0 * np.cumprod(1 + rng.normal(0, 0.02, 300)))
        assert annualized_volatility(frame, as_of=AS_OF, days=252) > 0.1


@pytest.fixture
def fundamentals():
    rows = [
        ("revenue", "2018-09-29", 240e9, "2018-11-05", "annual"),
        ("revenue", "2019-09-28", 260e9, "2019-10-31", "annual"),
        ("revenue", "2020-09-26", 274.5e9, "2020-10-30", "annual"),
        ("eps_diluted", "2019-09-28", 2.97, "2019-10-31", "annual"),
        ("eps_diluted", "2020-09-26", 3.28, "2020-10-30", "annual"),
        ("shares_outstanding", "2020-07-17", 4.275e9, "2020-07-31", "instant"),
        ("shares_outstanding", "2020-10-16", 17.0e9, "2020-10-30", "instant"),
    ]
    df = pd.DataFrame(rows, columns=["metric", "period_end", "value", "filed", "period_type"])
    df["period_end"] = pd.to_datetime(df["period_end"])
    df["filed"] = pd.to_datetime(df["filed"])
    df["ticker"] = "AAPL"
    df["cik"] = 320193
    df["fiscal_year"] = df["period_end"].dt.year
    df["fiscal_period"] = "FY"
    df["form"] = "10-K"
    return df


class TestFundamentalFeatures:
    def test_growth_uses_only_filings_known_at_as_of(self, fundamentals) -> None:
        # 2020-11-15: FY2020 (filed 10-30) is known -> 274.5/260.
        assert annual_metric_growth(
            fundamentals, "revenue", as_of=pd.Timestamp("2020-11-15")
        ) == pytest.approx(274.5 / 260.0 - 1.0)
        # 2020-10-15: FY2020 not yet filed -> FY2019/FY2018.
        assert annual_metric_growth(
            fundamentals, "revenue", as_of=pd.Timestamp("2020-10-15")
        ) == pytest.approx(260.0 / 240.0 - 1.0)

    def test_growth_insufficient_periods_raises(self, fundamentals) -> None:
        with pytest.raises(InsufficientHistoryError):
            annual_metric_growth(fundamentals, "revenue", as_of=pd.Timestamp("2019-01-01"))

    def test_shares_outstanding_uses_latest_known_filing(self, fundamentals) -> None:
        assert shares_outstanding_at(
            fundamentals, as_of=pd.Timestamp("2020-08-15")
        ) == pytest.approx(4.275e9)
        assert shares_outstanding_at(
            fundamentals, as_of=pd.Timestamp("2020-11-15")
        ) == pytest.approx(17.0e9)

    def test_market_cap_adjusts_shares_for_split_after_report(self, fundamentals) -> None:
        # Shares reported 2020-07-17 (pre-split); as_of 2020-09-01 is after
        # the 4:1. True price then was the adjusted close (129 * post-split
        # ratios = none) and shares must be scaled x4.
        dates = pd.date_range("2020-08-28", periods=5, freq="D")
        prices = _price_frame(
            dates, np.array([124.8, 129.0, 134.2, 131.0, 129.5]),
            splits={"2020-08-31": 4.0},
        )
        result = market_cap(prices, fundamentals, as_of=pd.Timestamp("2020-09-01"))
        assert result == pytest.approx(4.275e9 * 4.0 * 129.5)


class TestStructuralFeatures:
    @pytest.fixture
    def catalog(self):
        return pd.DataFrame(
            {
                "ticker": ["AAPL", "AAPL", "GE"],
                "date": pd.to_datetime(["2014-06-09", "2020-08-31", "2021-08-02"]),
                "ratio": [7.0, 4.0, 0.125],
                "is_forward": [True, True, False],
            }
        )

    def test_prior_forward_split_count(self, catalog) -> None:
        assert prior_split_count(catalog, "AAPL", as_of=pd.Timestamp("2015-01-01")) == 1
        assert prior_split_count(catalog, "AAPL", as_of=pd.Timestamp("2021-01-01")) == 2
        assert prior_split_count(catalog, "AAPL", as_of=pd.Timestamp("2014-06-09")) == 0
        # reverse splits never count
        assert prior_split_count(catalog, "GE", as_of=pd.Timestamp("2022-01-01")) == 0

    def test_years_since_last_split(self, catalog) -> None:
        result = years_since_last_split(catalog, "AAPL", as_of=pd.Timestamp("2021-08-31"))
        assert result == pytest.approx(1.0, abs=0.01)
        assert years_since_last_split(catalog, "TSLA", as_of=pd.Timestamp("2021-08-31")) is None
