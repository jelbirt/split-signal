"""SEC EDGAR companyfacts ingestion (free, official XBRL API).

Point-in-time discipline: every value carries its `filed` date — the
first date the market could have known the number. Comparative re-
statements in later filings are dropped (earliest filing wins).

Disk note: raw companyfacts JSON runs multi-MB per company, so the
resumable per-ticker cache stores the *normalized* extract as parquet
under data/raw/edgar/ instead of raw JSON (same skip-if-present resume
semantics at ~1000x less disk).

SEC fair-access: <=10 requests/second; we default well under that.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import requests

from split_signal.data.universe import USER_AGENT

COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# canonical metric -> (taxonomy, [tags in priority order])
_METRIC_TAGS: dict[str, tuple[str, list[str]]] = {
    "revenue": (
        "us-gaap",
        [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ],
    ),
    "eps_diluted": ("us-gaap", ["EarningsPerShareDiluted", "EarningsPerShareBasic"]),
    "net_income": ("us-gaap", ["NetIncomeLoss"]),
    "shares_outstanding": ("dei", ["EntityCommonStockSharesOutstanding"]),
}

_PERIODIC_FORMS = {"10-K", "10-Q", "20-F", "40-F"}

FUNDAMENTALS_COLUMNS = [
    "ticker", "cik", "metric", "period_end", "value",
    "filed", "fiscal_year", "fiscal_period", "form", "period_type",
]


def _classify_period(start: str | None, end: str) -> str:
    """Duration class: instant (no start), quarterly (~3mo), annual (~12mo), ytd (rest).

    Needed because a 10-K reports both the Q4 (3-month) and FY (12-month)
    figures with the same period_end and fp=FY — duration is the only
    reliable discriminator.
    """
    if start is None:
        return "instant"
    days = (pd.Timestamp(end) - pd.Timestamp(start)).days
    if days > 300:
        return "annual"
    if 60 <= days <= 120:
        return "quarterly"
    return "ytd"


def normalize_companyfacts(payload: dict, ticker: str) -> pd.DataFrame:
    cik = int(payload.get("cik", 0))
    rows: list[dict] = []
    for metric, (taxonomy, tags) in _METRIC_TAGS.items():
        section = payload.get("facts", {}).get(taxonomy, {})
        # merge ALL candidate tags (older filings often use retired tags);
        # priority breaks ties where tags overlap for the same period
        for priority, tag in enumerate(tags):
            units = section.get(tag, {}).get("units", {})
            if not units:
                continue
            for entry in next(iter(units.values())):
                if entry.get("form") not in _PERIODIC_FORMS:
                    continue
                rows.append(
                    {
                        "ticker": ticker,
                        "cik": cik,
                        "metric": metric,
                        "period_end": entry["end"],
                        "value": entry["val"],
                        "filed": entry["filed"],
                        "fiscal_year": entry.get("fy"),
                        "fiscal_period": entry.get("fp"),
                        "form": entry["form"],
                        "period_type": _classify_period(entry.get("start"), entry["end"]),
                        "_priority": priority,
                    }
                )

    if not rows:
        return pd.DataFrame(columns=FUNDAMENTALS_COLUMNS)

    out = pd.DataFrame(rows)
    out["period_end"] = pd.to_datetime(out["period_end"])
    out["filed"] = pd.to_datetime(out["filed"])
    # point-in-time: for each (metric, period_end, period_type) keep the
    # highest-priority tag, then the earliest filing (comparative
    # restatements in later filings are dropped)
    out = (
        out.sort_values(["_priority", "filed"])
        .drop_duplicates(subset=["metric", "period_end", "period_type"], keep="first")
        .sort_values(["metric", "period_end"])
        .reset_index(drop=True)
    )
    return out[FUNDAMENTALS_COLUMNS]


def fetch_companyfacts(cik: int, session: requests.Session | None = None) -> dict:
    session = session or requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    response = session.get(COMPANYFACTS_URL.format(cik=cik), timeout=30)
    response.raise_for_status()
    return response.json()


def fundamentals_cache_path(data_dir: str | Path, ticker: str) -> Path:
    return Path(data_dir) / "raw" / "edgar" / f"{ticker}.parquet"


def ingest_fundamentals(
    symbols: list[str],
    cik_map: pd.DataFrame,
    data_dir: str | Path,
    fetch: Callable[[int], dict] | None = None,
    throttle_s: float = 0.15,
    progress_every: int = 250,
) -> dict:
    """Fetch + normalize companyfacts for every symbol not already cached.

    Returns {"fetched": [...], "skipped": [...], "no_cik": [...], "failed": {sym: reason}}.
    """
    fetch = fetch or fetch_companyfacts
    ciks = cik_map.set_index("ticker")["cik"]
    summary: dict = {"fetched": [], "skipped": [], "no_cik": [], "failed": {}}

    for i, symbol in enumerate(symbols):
        cache = fundamentals_cache_path(data_dir, symbol)
        if cache.exists():
            summary["skipped"].append(symbol)
            continue
        cik = ciks.get(symbol)
        if pd.isna(cik):
            summary["no_cik"].append(symbol)
            continue
        try:
            frame = normalize_companyfacts(fetch(int(cik)), ticker=symbol)
        except Exception as exc:  # noqa: BLE001 — record and continue the scan
            summary["failed"][symbol] = str(exc)
            continue
        cache.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(cache, index=False)
        summary["fetched"].append(symbol)

        if throttle_s:
            time.sleep(throttle_s)
        if progress_every and (i + 1) % progress_every == 0:
            print(f"  fundamentals: {i + 1}/{len(symbols)} processed", flush=True)

    return summary


def load_fundamentals(data_dir: str | Path, ticker: str) -> pd.DataFrame:
    return pd.read_parquet(fundamentals_cache_path(data_dir, ticker))
