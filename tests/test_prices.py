"""Price ingestion: normalization, cache-first behavior, fallback, quality log."""

from pathlib import Path

import pandas as pd
import pytest

from split_signal.data.prices import (
    ingest_prices,
    load_prices,
    normalize_price_frame,
    price_cache_path,
)
from split_signal.data.quality import append_report


def _yf_frame() -> pd.DataFrame:
    idx = pd.DatetimeIndex(
        ["2020-08-28 00:00:00-04:00", "2020-08-31 00:00:00-04:00"], name="Date"
    )
    return pd.DataFrame(
        {
            "Open": [126.0, 127.6],
            "High": [126.4, 131.0],
            "Low": [124.6, 126.0],
            "Close": [124.8, 129.0],
            "Adj Close": [121.5, 125.7],
            "Volume": [1_000_000, 2_000_000],
            "Dividends": [0.0, 0.0],
            "Stock Splits": [0.0, 4.0],
        },
        index=idx,
    )


def _stooq_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": ["2020-08-28", "2020-08-31"],
            "Open": [126.0, 127.6],
            "High": [126.4, 131.0],
            "Low": [124.6, 126.0],
            "Close": [124.8, 129.0],
            "Volume": [1_000_000, 2_000_000],
        }
    )


class TestNormalize:
    def test_yfinance_frame(self) -> None:
        out = normalize_price_frame(_yf_frame(), source="yfinance")
        assert list(out.columns) == [
            "date", "open", "high", "low", "close",
            "adj_close", "volume", "dividends", "split_ratio", "source",
        ]
        assert out["date"].dt.tz is None
        assert out.loc[1, "split_ratio"] == 4.0
        assert out.loc[0, "adj_close"] == 121.5

    def test_stooq_frame_fills_missing_actions(self) -> None:
        out = normalize_price_frame(_stooq_frame(), source="stooq")
        assert (out["dividends"] == 0.0).all()
        assert (out["split_ratio"] == 0.0).all()
        assert (out["adj_close"] == out["close"]).all()
        assert (out["source"] == "stooq").all()

    def test_empty_frame_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            normalize_price_frame(pd.DataFrame(), source="yfinance")


class TestIngest:
    def test_writes_cache_and_skips_on_rerun(self, tmp_path: Path) -> None:
        calls: list[str] = []

        def fake_fetch(symbol: str) -> pd.DataFrame:
            calls.append(symbol)
            return normalize_price_frame(_yf_frame(), source="yfinance")

        summary = ingest_prices(["AAPL"], tmp_path, fetchers=[("fake", fake_fetch)])
        assert summary["fetched"] == ["AAPL"]
        assert price_cache_path(tmp_path, "AAPL").exists()

        summary2 = ingest_prices(["AAPL"], tmp_path, fetchers=[("fake", fake_fetch)])
        assert summary2["skipped"] == ["AAPL"]
        assert calls == ["AAPL"]  # not fetched twice

    def test_fallback_used_when_primary_fails(self, tmp_path: Path) -> None:
        def broken(symbol: str) -> pd.DataFrame:
            raise ConnectionError("boom")

        def backup(symbol: str) -> pd.DataFrame:
            return normalize_price_frame(_stooq_frame(), source="stooq")

        summary = ingest_prices(
            ["GE"], tmp_path, fetchers=[("broken", broken), ("backup", backup)]
        )
        assert summary["fetched"] == ["GE"]
        assert load_prices(tmp_path, "GE")["source"].iloc[0] == "stooq"

    def test_total_failure_recorded_not_raised(self, tmp_path: Path) -> None:
        def broken(symbol: str) -> pd.DataFrame:
            raise ConnectionError("boom")

        summary = ingest_prices(["XXXX"], tmp_path, fetchers=[("broken", broken)])
        assert summary["failed"] == {"XXXX": "broken: boom"}
        assert not price_cache_path(tmp_path, "XXXX").exists()

    def test_roundtrip_load(self, tmp_path: Path) -> None:
        def fake_fetch(symbol: str) -> pd.DataFrame:
            return normalize_price_frame(_yf_frame(), source="yfinance")

        ingest_prices(["AAPL"], tmp_path, fetchers=[("fake", fake_fetch)])
        loaded = load_prices(tmp_path, "AAPL")
        assert len(loaded) == 2
        assert loaded["split_ratio"].max() == 4.0


class TestQualityLog:
    def test_append_creates_dated_section(self, tmp_path: Path) -> None:
        log = tmp_path / "DATA_QUALITY.md"
        log.write_text("# Data Quality Log\n")
        append_report(log, title="Price ingestion", lines=["fetched: 2", "failed: 0"])
        text = log.read_text()
        assert "## " in text and "Price ingestion" in text
        assert "- fetched: 2" in text
