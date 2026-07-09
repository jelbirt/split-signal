"""Split-event catalog: extraction, classification, ratio sanity checks.

IMPORTANT source fact (verified live 2026-07-09): yfinance Close is
split-adjusted even with auto_adjust=False. So on our cached series a
REAL split shows NO ex-date discontinuity (implied ratio ~ 1.0), while a
bogus recorded split creates an artificial jump of ~ 1/ratio. Fixtures
below use adjusted-style prices accordingly.
"""

from pathlib import Path

import pandas as pd
import pytest

from split_signal.data.splits import (
    build_split_catalog,
    extract_split_events,
    implied_ratio,
    unadjusted_close,
)


def _prices(rows: list[tuple[str, float, float]]) -> pd.DataFrame:
    """rows: (date, split-adjusted close, split_ratio). Other columns filled plausibly."""
    df = pd.DataFrame(rows, columns=["date", "close", "split_ratio"])
    df["date"] = pd.to_datetime(df["date"])
    df["open"] = df["close"]
    df["high"] = df["close"] * 1.01
    df["low"] = df["close"] * 0.99
    df["adj_close"] = df["close"]
    df["volume"] = 1_000_000
    df["dividends"] = 0.0
    df["source"] = "test"
    return df


class TestExtract:
    def test_forward_split_extracted(self) -> None:
        prices = _prices([
            ("2020-08-28", 124.8, 0.0),
            ("2020-08-31", 129.0, 4.0),
            ("2020-09-01", 134.2, 0.0),
        ])
        events = extract_split_events(prices, ticker="AAPL")
        assert len(events) == 1
        event = events.iloc[0]
        assert event["ticker"] == "AAPL"
        assert event["date"] == pd.Timestamp("2020-08-31")
        assert event["ratio"] == 4.0
        assert bool(event["is_forward"]) is True

    def test_reverse_split_flagged(self) -> None:
        prices = _prices([
            ("2023-06-01", 5.00, 0.0),
            ("2023-06-02", 5.10, 0.1),
        ])
        events = extract_split_events(prices, ticker="MEME")
        assert bool(events.iloc[0]["is_forward"]) is False

    def test_multi_split_ticker_sorted(self) -> None:
        prices = _prices([
            ("2014-06-06", 92.2, 0.0),
            ("2014-06-09", 93.7, 7.0),
            ("2020-08-28", 124.8, 0.0),
            ("2020-08-31", 129.0, 4.0),
        ])
        events = extract_split_events(prices, ticker="AAPL")
        assert events["ratio"].tolist() == [7.0, 4.0]
        assert events["date"].is_monotonic_increasing

    def test_no_splits_yields_empty(self) -> None:
        events = extract_split_events(_prices([("2020-01-02", 10.0, 0.0)]), ticker="X")
        assert events.empty


class TestImpliedRatio:
    def test_adjusted_series_implies_ratio_near_one(self) -> None:
        prices = _prices([
            ("2020-08-28", 124.8, 0.0),
            ("2020-08-31", 129.0, 4.0),
        ])
        implied = implied_ratio(prices, pd.Timestamp("2020-08-31"))
        assert implied == pytest.approx(124.8 / 129.0, rel=1e-6)

    def test_first_row_split_has_no_implied_ratio(self) -> None:
        prices = _prices([("2020-08-31", 129.0, 4.0)])
        assert implied_ratio(prices, pd.Timestamp("2020-08-31")) is None


class TestUnadjustedClose:
    def test_reconstructs_true_price_before_splits(self) -> None:
        # Adjusted series around AAPL's 4:1: true pre-split price was ~499.
        prices = _prices([
            ("2020-08-28", 124.8, 0.0),
            ("2020-08-31", 129.0, 4.0),
            ("2020-09-01", 134.2, 0.0),
        ])
        true_close = unadjusted_close(prices)
        assert float(true_close.iloc[0]) == pytest.approx(499.2)
        assert float(true_close.iloc[1]) == pytest.approx(129.0)  # ex-date onward unchanged
        assert float(true_close.iloc[2]) == pytest.approx(134.2)

    def test_compounds_across_multiple_splits(self) -> None:
        # Only splits strictly AFTER a bar apply to it; an ex-date bar does
        # not carry its own ratio.
        prices = _prices([
            ("2014-06-06", 92.2, 0.0),
            ("2014-06-09", 93.7, 7.0),
            ("2020-08-31", 129.0, 4.0),
        ])
        true_close = unadjusted_close(prices)
        assert float(true_close.iloc[0]) == pytest.approx(92.2 * 7.0 * 4.0)
        assert float(true_close.iloc[1]) == pytest.approx(93.7 * 4.0)
        assert float(true_close.iloc[2]) == pytest.approx(129.0)


class TestCatalog:
    def test_catalog_over_cache_dir(self, tmp_path: Path) -> None:
        cache = tmp_path / "raw" / "prices"
        cache.mkdir(parents=True)
        _prices([
            ("2020-08-28", 124.8, 0.0),
            ("2020-08-31", 129.0, 4.0),
        ]).to_parquet(cache / "AAPL.parquet", index=False)
        _prices([
            ("2022-08-24", 297.1, 0.0),
            ("2022-08-25", 296.1, 3.0),
            ("2023-06-02", 290.0, 0.1),
        ]).to_parquet(cache / "TSLA.parquet", index=False)
        _prices([("2021-01-04", 10.0, 0.0)]).to_parquet(cache / "BORE.parquet", index=False)

        catalog = build_split_catalog(tmp_path, ["AAPL", "TSLA", "BORE", "MISSING"])
        assert len(catalog) == 3
        assert set(catalog["ticker"]) == {"AAPL", "TSLA"}
        assert len(catalog[catalog["is_forward"]]) == 2
        assert catalog["ratio_plausible"].all()

    def test_bogus_split_on_adjusted_series_flagged(self, tmp_path: Path) -> None:
        cache = tmp_path / "raw" / "prices"
        cache.mkdir(parents=True)
        # A recorded 4:1 that never happened: the provider back-divided prior
        # prices anyway, creating an artificial jump (implied ~ 1/4).
        _prices([
            ("2020-08-28", 25.0, 0.0),
            ("2020-08-31", 101.0, 4.0),
        ]).to_parquet(cache / "SUS.parquet", index=False)

        catalog = build_split_catalog(tmp_path, ["SUS"])
        assert bool(catalog.iloc[0]["ratio_plausible"]) is False
