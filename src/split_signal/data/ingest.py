"""Ingestion orchestrator: universe -> prices (-> splits/fundamentals, tasks A3-A4)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from split_signal.data.prices import coverage_stats, ingest_prices
from split_signal.data.quality import DEFAULT_LOG, append_report
from split_signal.data.universe import fetch_universe, save_universe


def run_ingest(universe: str, data_dir: str) -> int:
    if universe != "sp500-plus-splitters":
        print(f"unknown universe '{universe}'")
        return 2

    universe_path = Path(data_dir) / "processed" / "universe.parquet"
    if universe_path.exists():
        frame = pd.read_parquet(universe_path)
        print(f"universe: {len(frame)} symbols (cached at {universe_path})")
    else:
        print("universe: fetching from Wikipedia + NASDAQ Trader ...")
        frame = fetch_universe()
        save_universe(frame, data_dir)
        print(f"universe: {len(frame)} symbols saved")

    symbols = frame["symbol"].tolist()
    print(f"prices: ingesting {len(symbols)} symbols (cache-first, resumable) ...")
    summary = ingest_prices(symbols, data_dir)

    stats = coverage_stats(data_dir, symbols)
    lines = [
        f"universe symbols: {len(symbols)} (S&P 500 members: {int(frame['in_sp500'].sum())})",
        f"prices fetched this run: {len(summary['fetched'])}, "
        f"already cached: {len(summary['skipped'])}, failed: {len(summary['failed'])}",
        f"coverage: {stats['cached']}/{stats['requested']} cached, "
        f"{stats['with_15y_history']} with >=15y history, "
        f"{stats['with_5y_history']} with >=5y, median {stats['median_years']}y",
    ]
    if summary["failed"]:
        sample = list(summary["failed"].items())[:10]
        lines.append("failure sample: " + "; ".join(f"{s} ({r[:60]})" for s, r in sample))

    append_report(DEFAULT_LOG, title="Price ingestion run", lines=lines)
    for line in lines:
        print(line)
    print(f"quality log updated: {DEFAULT_LOG}")
    return 0 if not summary["failed"] else 0  # failures are logged, not fatal
