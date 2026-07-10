"""Backtest mechanics: forward returns, horizon integrity, momentum matching."""

import numpy as np
import pandas as pd
import pytest

from split_signal.backtest.engine import forward_return, momentum_closest_control


def _prices(start: str, periods: int, values: np.ndarray) -> pd.DataFrame:
    df = pd.DataFrame(
        {"date": pd.date_range(start, periods=periods, freq="D"), "close": values}
    )
    df["adj_close"] = df["close"]
    df["open"] = df["high"] = df["low"] = df["close"]
    df["volume"] = 1_000_000
    df["dividends"] = 0.0
    df["split_ratio"] = 0.0
    df["source"] = "test"
    return df


class TestForwardReturn:
    def test_known_answer(self) -> None:
        prices = _prices("2020-01-01", 400, np.linspace(100.0, 200.0, 400))
        start = pd.Timestamp("2020-01-01")
        result = forward_return(prices, start, horizon_days=365)
        series = prices.set_index("date")["adj_close"]
        expected = float(
            series.asof(start + pd.Timedelta(days=365)) / series.asof(start) - 1.0
        )
        assert result == pytest.approx(expected)

    def test_unelapsed_horizon_returns_none(self) -> None:
        prices = _prices("2020-01-01", 100, np.full(100, 50.0))
        assert forward_return(prices, pd.Timestamp("2020-01-01"), horizon_days=365) is None

    def test_start_before_data_returns_none(self) -> None:
        prices = _prices("2020-01-01", 400, np.full(400, 50.0))
        assert forward_return(prices, pd.Timestamp("2019-01-01"), horizon_days=30) is None

    def test_uses_only_window_data(self) -> None:
        # Identical windows, wildly different data after the horizon:
        # results must match (no peeking past the horizon end).
        base = np.linspace(100.0, 150.0, 500)
        crash = base.copy()
        crash[400:] = 1.0
        a = forward_return(
            _prices("2020-01-01", 500, base), pd.Timestamp("2020-01-05"), horizon_days=300
        )
        b = forward_return(
            _prices("2020-01-01", 500, crash), pd.Timestamp("2020-01-05"), horizon_days=300
        )
        assert a == pytest.approx(b)


class TestMomentumClosestControl:
    def test_picks_closest_trailing_return(self) -> None:
        controls = pd.DataFrame(
            {"ticker": ["A", "B", "C"], "ret_1y": [0.10, 0.48, 0.90]}
        )
        assert momentum_closest_control(controls, event_ret_1y=0.50) == "B"

    def test_ignores_missing_momentum(self) -> None:
        controls = pd.DataFrame(
            {"ticker": ["A", "B"], "ret_1y": [None, 0.20]}
        )
        assert momentum_closest_control(controls, event_ret_1y=0.9) == "B"

    def test_none_when_no_candidates(self) -> None:
        controls = pd.DataFrame({"ticker": [], "ret_1y": []})
        assert momentum_closest_control(controls, event_ret_1y=0.5) is None
        controls_nan = pd.DataFrame({"ticker": ["A"], "ret_1y": [None]})
        assert momentum_closest_control(controls_nan, event_ret_1y=0.5) is None
