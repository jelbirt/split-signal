# %% [markdown]
# # Backtest: do pre-split profiles predict forward outperformance?
#
# Three comparisons per split event, at 1y/3y/5y horizons from the split
# execution date:
#   1. splitter vs SPY (post-split drift, benchmark-relative)
#   2. splitter vs mean of sector/size-matched controls (profile effect)
#   3. splitter vs its momentum-closest control (does the split add
#      anything beyond the run-up itself?)
# Train (2006-2018) and holdout (2019+) are reported separately.
#
# Run headless: `uv run python notebooks/07_backtest.py`
# Requires: notebooks/06_event_study.py output (event_features.parquet).

# %% setup
from pathlib import Path

import pandas as pd

from split_signal.backtest.engine import forward_return, momentum_closest_control
from split_signal.data.prices import ingest_prices, load_prices, price_cache_path
from split_signal.data.quality import DEFAULT_LOG, append_report

DATA = Path("data")
HORIZONS = {"1y": 365, "3y": 1095, "5y": 1826}
TRAIN_END = pd.Timestamp("2018-12-31")

features = pd.read_parquet(DATA / "processed" / "event_features.parquet")
events = features[features["role"] == "event"].set_index("event_id")
controls = features[features["role"] == "control"]

ingest_prices(["SPY"], DATA)  # benchmark (cache-first; no-op when cached)
spy = load_prices(DATA, "SPY")

_prices_memo: dict[str, pd.DataFrame | None] = {}


def prices_for(symbol: str) -> pd.DataFrame | None:
    if symbol not in _prices_memo:
        path = price_cache_path(DATA, symbol)
        _prices_memo[symbol] = pd.read_parquet(path) if path.exists() else None
    return _prices_memo[symbol]


# %% per-event forward returns
rows = []
for event_id, event in events.iterrows():
    prices = prices_for(event["ticker"])
    if prices is None:
        continue
    event_controls = controls[controls["event_id"] == event_id]
    momo_ticker = (
        momentum_closest_control(event_controls, event["ret_1y"])
        if pd.notna(event["ret_1y"]) and not event_controls.empty
        else None
    )
    start = event["split_date"]
    row = {
        "event_id": event_id,
        "ticker": event["ticker"],
        "split_date": start,
        "period": "train" if start <= TRAIN_END else "holdout",
    }
    for label, days in HORIZONS.items():
        row[f"event_{label}"] = forward_return(prices, start, days)
        row[f"spy_{label}"] = forward_return(spy, start, days)
        control_returns = [
            r for c in event_controls["ticker"]
            if (cp := prices_for(c)) is not None
            and (r := forward_return(cp, start, days)) is not None
        ]
        row[f"controls_{label}"] = (
            sum(control_returns) / len(control_returns) if control_returns else None
        )
        if momo_ticker and (mp := prices_for(momo_ticker)) is not None:
            row[f"momo_{label}"] = forward_return(mp, start, days)
        else:
            row[f"momo_{label}"] = None
    rows.append(row)

results = pd.DataFrame(rows)
results.to_parquet(DATA / "processed" / "backtest_results.parquet", index=False)
print(f"events with forward returns: {len(results)}")


# %% aggregate
def agg_block(frame: pd.DataFrame, label: str, baseline: str) -> str | None:
    pairs = frame[[f"event_{label}", f"{baseline}_{label}"]].dropna()
    if len(pairs) < 20:
        return None
    excess = pairs[f"event_{label}"] - pairs[f"{baseline}_{label}"]
    return (
        f"| {label} vs {baseline} | {len(pairs)} | {excess.median():+.1%} "
        f"| {excess.mean():+.1%} | {(excess > 0).mean():.0%} |"
    )


sections = []
for period in ["train", "holdout"]:
    frame = results[results["period"] == period]
    sections += [
        f"\n## {period.capitalize()} ({len(frame)} events, "
        f"{'2006-2018' if period == 'train' else '2019+'})\n",
        "| comparison | n | median excess | mean excess | hit rate |",
        "|---|---|---|---|---|",
    ]
    for label in HORIZONS:
        for baseline in ["spy", "controls", "momo"]:
            line = agg_block(frame, label, baseline)
            if line:
                sections.append(line)

report = "\n".join(
    [
        "# Backtest results: forward returns after forward splits",
        "",
        "Excess = splitter return minus baseline return over the same window,",
        "from the split execution date. Baselines: SPY buy-and-hold;",
        "mean of sector/size-matched controls; the momentum-closest control",
        "(isolates the split from its price run-up).",
        "Horizons requiring unelapsed future data are excluded, never partial.",
        *sections,
        "",
        "Caveats: survivorship bias (delisted splitters absent — excess vs",
        "controls is the more robust comparison since controls share the bias);",
        "execution-date anchoring; see DATA_QUALITY.md.",
    ]
)
out = Path("docs/research/backtest_results.md")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(report + "\n")
print(report)

# %% quality log
append_report(
    DEFAULT_LOG,
    title="Backtest run",
    lines=[
        f"events measured: {len(results)} "
        f"(train {int((results['period'] == 'train').sum())}, "
        f"holdout {int((results['period'] == 'holdout').sum())})",
        "results: docs/research/backtest_results.md",
    ],
)
print("done.")
