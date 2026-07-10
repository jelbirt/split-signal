"""Structural features from the split-event catalog (all as_of-anchored)."""

from __future__ import annotations

import pandas as pd


def _prior_forward_splits(
    catalog: pd.DataFrame, ticker: str, as_of: pd.Timestamp
) -> pd.DataFrame:
    return catalog[
        (catalog["ticker"] == ticker)
        & (catalog["is_forward"])
        & (catalog["date"] < as_of)
    ]


def prior_split_count(catalog: pd.DataFrame, ticker: str, as_of: pd.Timestamp) -> int:
    """Forward splits the company executed strictly before as_of."""
    return len(_prior_forward_splits(catalog, ticker, as_of))


def years_since_last_split(
    catalog: pd.DataFrame, ticker: str, as_of: pd.Timestamp
) -> float | None:
    """Years since the last forward split before as_of; None if never split."""
    prior = _prior_forward_splits(catalog, ticker, as_of)
    if prior.empty:
        return None
    return float((as_of - prior["date"].max()).days / 365.25)
