"""Universe construction: parsers and merge logic (fixtures only, no network)."""

from pathlib import Path

import pytest

from split_signal.data.universe import (
    build_universe,
    normalize_symbol,
    parse_nasdaq_listed,
    parse_other_listed,
    parse_sp500_html,
)

FIXTURES = Path(__file__).parent.parent / "data" / "fixtures"


@pytest.fixture
def nasdaq_df():
    return parse_nasdaq_listed((FIXTURES / "nasdaqlisted_sample.txt").read_text())


@pytest.fixture
def other_df():
    return parse_other_listed((FIXTURES / "otherlisted_sample.txt").read_text())


@pytest.fixture
def sp500_df():
    return parse_sp500_html((FIXTURES / "sp500_sample.html").read_text())


class TestNormalizeSymbol:
    def test_class_shares_use_dash(self) -> None:
        assert normalize_symbol("BRK.B") == "BRK-B"
        assert normalize_symbol("BF.B") == "BF-B"

    def test_plain_symbols_pass_through(self) -> None:
        assert normalize_symbol(" AAPL ") == "AAPL"


class TestParseNasdaqListed:
    def test_keeps_common_stock(self, nasdaq_df) -> None:
        assert {"AAPL", "NVDA"} <= set(nasdaq_df["symbol"])

    def test_excludes_test_issues_etfs_and_footer(self, nasdaq_df) -> None:
        assert "ZAZZT" not in set(nasdaq_df["symbol"])  # test issue
        assert "QQQ" not in set(nasdaq_df["symbol"])  # ETF
        assert not nasdaq_df["symbol"].str.contains("File Creation", case=False).any()

    def test_excludes_preferred_and_warrants_by_name(self, nasdaq_df) -> None:
        assert "ABCDP" not in set(nasdaq_df["symbol"])
        assert "ACMEW" not in set(nasdaq_df["symbol"])

    def test_rows_with_missing_symbol_dropped(self, nasdaq_df) -> None:
        assert nasdaq_df["symbol"].notna().all()

    def test_exchange_labelled(self, nasdaq_df) -> None:
        assert (nasdaq_df["exchange"] == "NASDAQ").all()


class TestParseOtherListed:
    def test_keeps_common_stock_with_mapped_exchange(self, other_df) -> None:
        row = other_df.set_index("symbol").loc["A"]
        assert row["exchange"] == "NYSE"

    def test_normalizes_class_share_symbols(self, other_df) -> None:
        assert "BRK-B" in set(other_df["symbol"])

    def test_excludes_etfs_test_issues_and_units(self, other_df) -> None:
        symbols = set(other_df["symbol"])
        assert "SPY" not in symbols
        assert "ZTST" not in symbols
        assert not any(s.startswith("ACME") for s in symbols)


class TestParseSp500:
    def test_extracts_constituents_table_not_changes_table(self, sp500_df) -> None:
        assert set(sp500_df["symbol"]) == {"AAPL", "BF-B", "NVDA"}

    def test_carries_sector_and_cik(self, sp500_df) -> None:
        row = sp500_df.set_index("symbol").loc["NVDA"]
        assert row["gics_sector"] == "Information Technology"
        assert row["cik"] == 1045810


class TestBuildUniverse:
    def test_merges_and_flags_sp500(self, nasdaq_df, other_df, sp500_df) -> None:
        universe = build_universe(sp500=sp500_df, listed=[nasdaq_df, other_df])
        idx = universe.set_index("symbol")
        assert bool(idx.loc["AAPL", "in_sp500"]) is True
        assert bool(idx.loc["GE", "in_sp500"]) is False

    def test_sp500_members_missing_from_listings_still_included(
        self, nasdaq_df, other_df, sp500_df
    ) -> None:
        universe = build_universe(sp500=sp500_df, listed=[nasdaq_df, other_df])
        assert "BF-B" in set(universe["symbol"])  # in S&P table, not in listing fixtures

    def test_no_duplicate_symbols(self, nasdaq_df, other_df, sp500_df) -> None:
        universe = build_universe(sp500=sp500_df, listed=[nasdaq_df, other_df])
        assert universe["symbol"].is_unique
