"""Daily price ingestion with a cache-first, resumable design.

One parquet per symbol under data/raw/prices/. Fetchers are pluggable
(name, callable) pairs tried in order — production uses yfinance with a
Stooq fallback; tests inject fakes. A symbol that fails every fetcher is
recorded in the run summary, never raised, so long scans keep going.

Raw close is kept alongside adjusted close: raw for price-level features
and split-discontinuity sanity checks, adjusted for return computations.
"""

from __future__ import annotations

import io
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import requests

STANDARD_COLUMNS = [
    "date", "open", "high", "low", "close",
    "adj_close", "volume", "dividends", "split_ratio", "source",
]

Fetcher = tuple[str, Callable[[str], pd.DataFrame]]

_STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}.us&i=d"


def normalize_price_frame(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    """Normalize a provider frame to STANDARD_COLUMNS with a tz-naive date column."""
    if frame.empty:
        raise ValueError(f"empty price frame from {source}")

    df = frame.reset_index() if not isinstance(frame.index, pd.RangeIndex) else frame.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    df = df.rename(columns={"stock_splits": "split_ratio"})

    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]
    if "dividends" not in df.columns:
        df["dividends"] = 0.0
    if "split_ratio" not in df.columns:
        df["split_ratio"] = 0.0
    df["source"] = source

    return df[STANDARD_COLUMNS].sort_values("date").reset_index(drop=True)


def fetch_yfinance(symbol: str) -> pd.DataFrame:
    import yfinance as yf

    history = yf.Ticker(symbol).history(period="max", auto_adjust=False, actions=True)
    return normalize_price_frame(history, source="yfinance")


def fetch_stooq(symbol: str, session: requests.Session | None = None) -> pd.DataFrame:
    response = (session or requests).get(
        _STOOQ_URL.format(symbol=symbol.lower().replace("-", ".")), timeout=30
    )
    response.raise_for_status()
    frame = pd.read_csv(io.StringIO(response.text))
    return normalize_price_frame(frame, source="stooq")


DEFAULT_FETCHERS: list[Fetcher] = [("yfinance", fetch_yfinance), ("stooq", fetch_stooq)]


def price_cache_path(data_dir: str | Path, symbol: str) -> Path:
    return Path(data_dir) / "raw" / "prices" / f"{symbol}.parquet"


def load_prices(data_dir: str | Path, symbol: str) -> pd.DataFrame:
    return pd.read_parquet(price_cache_path(data_dir, symbol))


def ingest_prices(
    symbols: list[str],
    data_dir: str | Path,
    fetchers: list[Fetcher] | None = None,
    throttle_s: float = 0.4,
    progress_every: int = 250,
) -> dict:
    """Fetch and cache daily prices for every symbol not already cached.

    Returns {"fetched": [...], "skipped": [...], "failed": {symbol: reason}}.
    """
    fetchers = DEFAULT_FETCHERS if fetchers is None else fetchers
    summary: dict = {"fetched": [], "skipped": [], "failed": {}}

    for i, symbol in enumerate(symbols):
        cache = price_cache_path(data_dir, symbol)
        if cache.exists():
            summary["skipped"].append(symbol)
            continue

        errors: list[str] = []
        for name, fetch in fetchers:
            try:
                frame = fetch(symbol)
            except Exception as exc:  # noqa: BLE001 — record and continue the scan
                errors.append(f"{name}: {exc}")
                continue
            cache.parent.mkdir(parents=True, exist_ok=True)
            frame.to_parquet(cache, index=False)
            summary["fetched"].append(symbol)
            break
        else:
            summary["failed"][symbol] = "; ".join(errors)

        if throttle_s:
            time.sleep(throttle_s)
        if progress_every and (i + 1) % progress_every == 0:
            done = len(summary["fetched"]) + len(summary["skipped"])
            print(f"  prices: {i + 1}/{len(symbols)} processed "
                  f"({done} ok, {len(summary['failed'])} failed)", flush=True)

    return summary


def coverage_stats(data_dir: str | Path, symbols: list[str]) -> dict:
    """Per-cache coverage: how many symbols have >=15y of history, etc."""
    years: dict[str, float] = {}
    for symbol in symbols:
        path = price_cache_path(data_dir, symbol)
        if not path.exists():
            continue
        dates = pd.read_parquet(path, columns=["date"])["date"]
        if dates.empty:
            continue
        years[symbol] = (dates.max() - dates.min()).days / 365.25

    series = pd.Series(years)
    return {
        "cached": len(series),
        "requested": len(symbols),
        "with_15y_history": int((series >= 15).sum()),
        "with_5y_history": int((series >= 5).sum()),
        "median_years": round(float(series.median()), 1) if len(series) else 0.0,
    }
