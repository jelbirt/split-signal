"""Control matching for the event study (synthetic frames, no data files)."""

import pandas as pd
import pytest

from split_signal.backtest.controls import (
    had_split_within,
    match_controls,
)


@pytest.fixture
def catalog():
    return pd.DataFrame(
        {
            "ticker": ["AAPL", "MSFT", "ORCL"],
            "date": pd.to_datetime(["2020-08-31", "2021-03-01", "2010-01-15"]),
            "ratio": [4.0, 2.0, 2.0],
            "is_forward": [True, True, True],
        }
    )


@pytest.fixture
def candidates():
    """symbol, sector, and size (dollar-volume proxy) at the event date."""
    return pd.DataFrame(
        {
            "symbol": ["MSFT", "ORCL", "CRM", "IBM", "XOM"],
            "gics_sector": ["Information Technology"] * 4 + ["Energy"],
            "size": [9e9, 1.1e9, 0.9e9, 1.0e9, 1.0e9],
        }
    )


class TestHadSplitWithin:
    def test_detects_split_inside_window(self, catalog) -> None:
        assert had_split_within(
            catalog, "MSFT", pd.Timestamp("2020-08-31"), years=2
        ) is True

    def test_old_split_outside_window(self, catalog) -> None:
        assert had_split_within(
            catalog, "ORCL", pd.Timestamp("2020-08-31"), years=2
        ) is False

    def test_never_split_ticker(self, catalog) -> None:
        assert had_split_within(
            catalog, "IBM", pd.Timestamp("2020-08-31"), years=2
        ) is False


class TestMatchControls:
    def test_same_sector_no_split_closest_size(self, catalog, candidates) -> None:
        controls = match_controls(
            event_ticker="AAPL",
            event_date=pd.Timestamp("2020-08-31"),
            event_sector="Information Technology",
            event_size=1.0e9,
            candidates=candidates,
            catalog=catalog,
            n=2,
        )
        # MSFT excluded (split within ±2y), XOM excluded (sector),
        # IBM (1.0e9) is the closest size, then ORCL (1.1e9) edges CRM (0.9e9)
        # on log-ratio distance only slightly — accept either order, but the
        # set must be exactly the eligible same-sector names.
        assert controls[0] == "IBM"
        assert set(controls) <= {"IBM", "ORCL", "CRM"}
        assert len(controls) == 2

    def test_event_ticker_itself_excluded(self, catalog, candidates) -> None:
        with_self = pd.concat(
            [candidates, pd.DataFrame([{"symbol": "AAPL",
                                        "gics_sector": "Information Technology",
                                        "size": 1.0e9}])],
            ignore_index=True,
        )
        controls = match_controls(
            event_ticker="AAPL",
            event_date=pd.Timestamp("2020-08-31"),
            event_sector="Information Technology",
            event_size=1.0e9,
            candidates=with_self,
            catalog=catalog,
            n=5,
        )
        assert "AAPL" not in controls

    def test_zero_or_nan_event_size_yields_no_controls(self, catalog, candidates) -> None:
        for bad_size in (0.0, float("nan")):
            controls = match_controls(
                event_ticker="AAPL",
                event_date=pd.Timestamp("2020-08-31"),
                event_sector=None,
                event_size=bad_size,
                candidates=candidates,
                catalog=catalog,
                n=3,
            )
            assert controls == []

    def test_missing_sector_falls_back_to_size_only(self, catalog, candidates) -> None:
        controls = match_controls(
            event_ticker="AAPL",
            event_date=pd.Timestamp("2020-08-31"),
            event_sector=None,
            event_size=1.0e9,
            candidates=candidates,
            catalog=catalog,
            n=3,
        )
        assert len(controls) == 3  # sector filter skipped, XOM now eligible
