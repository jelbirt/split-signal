"""EDGAR companyfacts normalization and CIK mapping (fixtures only)."""

import json
from pathlib import Path

import pandas as pd

from split_signal.data.cik import parse_cik_map
from split_signal.data.edgar import ingest_fundamentals, normalize_companyfacts

FIXTURES = Path(__file__).parent.parent / "data" / "fixtures"


def _facts() -> dict:
    return json.loads((FIXTURES / "companyfacts_sample.json").read_text())


class TestCikMap:
    def test_parses_and_normalizes(self) -> None:
        cik_map = parse_cik_map(json.loads((FIXTURES / "company_tickers_sample.json").read_text()))
        idx = cik_map.set_index("ticker")
        assert idx.loc["AAPL", "cik"] == 320193
        assert idx.loc["BRK-B", "cik"] == 1067983


class TestNormalizeCompanyfacts:
    def test_canonical_metrics_extracted(self) -> None:
        out = normalize_companyfacts(_facts(), ticker="AAPL")
        assert set(out["metric"]) == {
            "revenue", "eps_diluted", "net_income", "shares_outstanding",
        }
        assert set(out.columns) == {
            "ticker", "cik", "metric", "period_end", "value",
            "filed", "fiscal_year", "fiscal_period", "form", "period_type",
        }

    def test_period_type_classified_by_duration(self) -> None:
        out = normalize_companyfacts(_facts(), ticker="AAPL")
        revenue = out[out["metric"] == "revenue"].set_index("value")
        assert revenue.loc[274515000000, "period_type"] == "annual"
        assert revenue.loc[59685000000, "period_type"] == "quarterly"
        assert revenue.loc[209817000000, "period_type"] == "ytd"
        assert revenue.loc[64698000000, "period_type"] == "quarterly"
        shares = out[out["metric"] == "shares_outstanding"]
        assert (shares["period_type"] == "instant").all()

    def test_annual_value_not_shadowed_by_q4_row(self) -> None:
        # The 10-K carries both the Q4 (3-month) and FY (12-month) figures
        # with the same period_end; duration classification must keep both,
        # and the annual row must be the 12-month value.
        out = normalize_companyfacts(_facts(), ticker="AAPL")
        annual = out[
            (out["metric"] == "revenue")
            & (out["period_type"] == "annual")
            & (out["period_end"] == pd.Timestamp("2020-09-26"))
        ]
        assert annual["value"].tolist() == [274515000000]

    def test_tags_merge_across_fallbacks_with_priority(self) -> None:
        out = normalize_companyfacts(_facts(), ticker="AAPL")
        annual = out[(out["metric"] == "revenue") & (out["period_type"] == "annual")]
        # Old history only exists under SalesRevenueNet: must be present.
        assert pd.Timestamp("2012-09-29") in set(annual["period_end"])
        # Where tags conflict (FY2020), the higher-priority tag's value wins.
        fy2020 = annual[annual["period_end"] == pd.Timestamp("2020-09-26")]
        assert fy2020["value"].tolist() == [274515000000]

    def test_filed_date_is_point_in_time_anchor(self) -> None:
        out = normalize_companyfacts(_facts(), ticker="AAPL")
        revenue_fy = out[(out["metric"] == "revenue") & (out["fiscal_period"] == "FY")]
        assert (revenue_fy["filed"] > revenue_fy["period_end"]).all()

    def test_duplicate_period_keeps_earliest_filing(self) -> None:
        # FY2020 revenue appears in the 2020 10-K and again (comparative) in
        # the 2021 10-K; point-in-time uses the earliest filing.
        out = normalize_companyfacts(_facts(), ticker="AAPL")
        fy2020 = out[
            (out["metric"] == "revenue")
            & (out["period_type"] == "annual")
            & (out["period_end"] == pd.Timestamp("2020-09-26"))
        ]
        assert len(fy2020) == 1
        assert fy2020.iloc[0]["filed"] == pd.Timestamp("2020-10-30")

    def test_non_periodic_forms_excluded(self) -> None:
        out = normalize_companyfacts(_facts(), ticker="AAPL")
        assert set(out["form"]) <= {"10-K", "10-Q", "20-F", "40-F"}

    def test_empty_facts_yield_empty_frame(self) -> None:
        out = normalize_companyfacts({"cik": 1, "facts": {}}, ticker="X")
        assert out.empty


class TestIngestFundamentals:
    def test_cache_first_and_failure_logging(self, tmp_path: Path) -> None:
        calls: list[int] = []

        def fake_fetch(cik: int) -> dict:
            calls.append(cik)
            if cik == 999:
                raise ConnectionError("no such company")
            return _facts()

        cik_map = pd.DataFrame(
            {"ticker": ["AAPL", "MISSING", "NOCIK"], "cik": [320193, 999, pd.NA]}
        )
        summary = ingest_fundamentals(
            ["AAPL", "MISSING", "NOCIK"], cik_map, tmp_path, fetch=fake_fetch, throttle_s=0
        )
        assert summary["fetched"] == ["AAPL"]
        assert "MISSING" in summary["failed"]
        assert "NOCIK" in summary["no_cik"]

        summary2 = ingest_fundamentals(
            ["AAPL"], cik_map, tmp_path, fetch=fake_fetch, throttle_s=0
        )
        assert summary2["skipped"] == ["AAPL"]
        assert calls.count(320193) == 1
