"""Forward-return measurement for the event backtest.

Horizon integrity rules:
- A forward return is only reported when the price history actually
  covers the horizon end (no partial windows — they would systematically
  favor recent winners).
- Start values use as-of semantics (last bar <= start date), and a start
  before the first bar yields None rather than silently clamping.
"""

from __future__ import annotations

import pandas as pd


def forward_return(
    prices: pd.DataFrame,
    start: pd.Timestamp,
    horizon_days: int,
    coverage: float = 0.98,
) -> float | None:
    """Total return from `start` to `start + horizon_days`, or None."""
    series = prices.sort_values("date").set_index("date")["adj_close"]
    if series.empty or start < series.index[0]:
        return None
    end = start + pd.Timedelta(days=horizon_days)
    if series.index[-1] < start + pd.Timedelta(days=int(horizon_days * coverage)):
        return None  # horizon not (fully) elapsed or ticker stopped trading
    start_value = float(series.asof(start))
    end_value = float(series.asof(end))
    if start_value <= 0:
        return None
    return end_value / start_value - 1.0


def momentum_closest_control(controls: pd.DataFrame, event_ret_1y: float) -> str | None:
    """Ticker of the control whose trailing 1y return is closest to the event's.

    Isolates the split signal from plain momentum: if splitters only win
    because they ran up, a momentum-matched peer should perform the same.
    """
    pool = controls.dropna(subset=["ret_1y"])
    if pool.empty:
        return None
    distance = (pool["ret_1y"].astype(float) - event_ret_1y).abs()
    return str(pool.loc[distance.idxmin(), "ticker"])
