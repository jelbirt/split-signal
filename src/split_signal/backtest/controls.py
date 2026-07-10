"""Matched-control selection for the split event study.

For each forward split, controls are non-splitting peers observed at the
same date: same GICS sector (where known), no forward split of their own
within ±window years, closest in size. Size uses the median trailing
dollar-volume proxy, which is invariant to split adjustment and exists
for every ticker with prices (fundamentals are not required to match).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def had_split_within(
    catalog: pd.DataFrame, ticker: str, date: pd.Timestamp, years: int = 2
) -> bool:
    window = pd.Timedelta(days=int(365.25 * years))
    events = catalog[
        (catalog["ticker"] == ticker)
        & (catalog["is_forward"])
        & (catalog["date"] >= date - window)
        & (catalog["date"] <= date + window)
    ]
    return not events.empty


def dollar_volume_size(prices: pd.DataFrame, as_of: pd.Timestamp, days: int = 90) -> float:
    """Median daily dollar volume over the trailing window (split-invariant)."""
    bars = prices.loc[prices["date"] <= as_of].tail(days)
    if bars.empty:
        return float("nan")
    return float((bars["adj_close"] * bars["volume"]).median())


def match_controls(
    event_ticker: str,
    event_date: pd.Timestamp,
    event_sector: str | None,
    event_size: float,
    candidates: pd.DataFrame,
    catalog: pd.DataFrame,
    n: int = 3,
    split_window_years: int = 2,
) -> list[str]:
    """Return up to n control symbols for one event.

    `candidates` must carry symbol, gics_sector, and size (same-date proxy).
    """
    pool = candidates[candidates["symbol"] != event_ticker]
    if event_sector is not None:
        pool = pool[pool["gics_sector"] == event_sector]
    pool = pool[pool["size"].notna() & (pool["size"] > 0)]
    pool = pool[
        ~pool["symbol"].map(
            lambda s: had_split_within(catalog, s, event_date, years=split_window_years)
        )
    ]
    if pool.empty:
        return []

    distance = (np.log(pool["size"]) - np.log(event_size)).abs()
    return pool.assign(_d=distance).sort_values("_d")["symbol"].head(n).tolist()
