"""Split-event catalog built from cached price history.

Events come from the `split_ratio` column of the per-symbol price cache
(yfinance "Stock Splits" actions).

SOURCE FACT (verified live 2026-07-09, see DATA_QUALITY.md): yfinance's
Close is split-adjusted even with auto_adjust=False (Adj Close further
adjusts dividends). Consequences:

1. Ratio validation: a REAL recorded split shows NO ex-date discontinuity
   in our cached close (implied ratio ~ 1.0, within ordinary daily-move
   noise). A BOGUS recorded split creates an artificial jump of ~1/ratio,
   because the provider back-divided prices for a split that never
   happened. `ratio_plausible` flags events whose implied ratio strays
   far from 1.0. (Small bogus ratios < ~1.35 are indistinguishable from
   market noise — accepted limitation.)
2. True historical share price (for price-level features) must be
   reconstructed: unadjusted_close(t) = close(t) * prod(ratios of splits
   dated strictly after t). See `unadjusted_close`.

Anchor caveat (SPEC.md open question 1): dates here are *execution*
(ex-date), not announcement dates.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from split_signal.data.prices import price_cache_path

# implied ratio (prior close / ex close) on an adjusted series should be ~1.0;
# the band allows for an ordinary same-day market move.
_PLAUSIBILITY_BAND = (0.75, 1.35)

CATALOG_COLUMNS = ["ticker", "date", "ratio", "is_forward", "implied_ratio", "ratio_plausible"]


def extract_split_events(prices: pd.DataFrame, ticker: str) -> pd.DataFrame:
    events = prices.loc[prices["split_ratio"] > 0, ["date", "split_ratio"]].copy()
    events = events.rename(columns={"split_ratio": "ratio"})
    events.insert(0, "ticker", ticker)
    events["is_forward"] = events["ratio"] > 1.0
    return events.sort_values("date").reset_index(drop=True)


def implied_ratio(prices: pd.DataFrame, event_date: pd.Timestamp) -> float | None:
    """prior raw close / ex-date raw close; None when there is no prior bar."""
    dated = prices.sort_values("date").reset_index(drop=True)
    matches = dated.index[dated["date"] == event_date]
    if len(matches) == 0 or matches[0] == 0:
        return None
    position = matches[0]
    prior_close = float(dated.loc[position - 1, "close"])
    ex_close = float(dated.loc[position, "close"])
    if ex_close <= 0:
        return None
    return prior_close / ex_close


def unadjusted_close(prices: pd.DataFrame) -> pd.Series:
    """Reconstruct the true (as-traded) close from a split-adjusted series.

    Each bar's close is multiplied by the product of all split ratios dated
    strictly after that bar. Indexed like the input frame.
    """
    dated = prices.sort_values("date")
    ratios = dated["split_ratio"].where(dated["split_ratio"] > 0, 1.0)
    # cumulative product of ratios from the end, excluding the bar's own ratio
    multiplier = ratios[::-1].cumprod()[::-1] / ratios
    return (dated["close"] * multiplier).reindex(prices.index)


def _plausible(implied: float | None) -> bool:
    if implied is None:
        return True  # cannot verify; do not condemn
    low, high = _PLAUSIBILITY_BAND
    return low <= implied <= high


def build_split_catalog(data_dir: str | Path, symbols: list[str]) -> pd.DataFrame:
    """Extract and validate split events for every cached symbol."""
    frames: list[pd.DataFrame] = []
    for symbol in symbols:
        path = price_cache_path(data_dir, symbol)
        if not path.exists():
            continue
        prices = pd.read_parquet(path, columns=["date", "close", "split_ratio"])
        events = extract_split_events(prices, ticker=symbol)
        if events.empty:
            continue
        events["implied_ratio"] = events["date"].map(lambda d, p=prices: implied_ratio(p, d))
        events["ratio_plausible"] = events["implied_ratio"].map(_plausible)
        frames.append(events)

    if not frames:
        return pd.DataFrame(columns=CATALOG_COLUMNS)
    return pd.concat(frames, ignore_index=True)[CATALOG_COLUMNS]


def save_split_catalog(catalog: pd.DataFrame, data_dir: str | Path) -> Path:
    out_path = Path(data_dir) / "processed" / "splits.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    catalog.to_parquet(out_path, index=False)
    return out_path


def catalog_summary(catalog: pd.DataFrame) -> list[str]:
    """Human-readable lines for DATA_QUALITY.md."""
    if catalog.empty:
        return ["split catalog: EMPTY"]
    forward = catalog[catalog["is_forward"]]
    by_year = forward.groupby(forward["date"].dt.year).size()
    recent = {int(y): int(n) for y, n in by_year.items() if y >= 2006}
    return [
        f"split events: {len(catalog)} total "
        f"({len(forward)} forward, {len(catalog) - len(forward)} reverse)",
        f"implausible ratios flagged: {int((~catalog['ratio_plausible']).sum())}",
        f"forward splits per year since 2006: {recent}",
    ]
