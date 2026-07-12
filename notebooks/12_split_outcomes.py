# %% [markdown]
# # Which splits created value? Outcome breakdown of 1,371 forward splits
#
# The aggregate verdict (07_backtest) was that the MEDIAN splitter lags
# SPY. This breaks the population apart: outcome rates by horizon, the
# distribution's skew, named winners/losers, and segmentation by split
# ratio, era, pre-split price, and liquidity — to characterize the
# subpopulation where splits coincided with real value creation.
#
# Run headless: `uv run python notebooks/12_split_outcomes.py`
# Requires: 07_backtest output (backtest_results.parquet) and
# 06_event_study output (event_features.parquet).

# %% setup
from pathlib import Path

import numpy as np
import pandas as pd

from split_signal.data.quality import DEFAULT_LOG, append_report

DATA = Path("data")
HORIZONS = ["1y", "3y", "5y"]

results = pd.read_parquet(DATA / "processed" / "backtest_results.parquet")
features = pd.read_parquet(DATA / "processed" / "event_features.parquet")
catalog = pd.read_parquet(DATA / "processed" / "splits.parquet")

events = features[features["role"] == "event"][
    ["event_id", "ticker", "split_date", "ratio", "price_level", "size", "volatility"]
]
table = results.merge(events, on=["event_id", "ticker", "split_date"], how="left")
for h in HORIZONS:
    table[f"excess_{h}"] = table[f"event_{h}"] - table[f"spy_{h}"]
print(f"events with outcomes: {len(table)}")

# %% overall outcome rates
overall_lines = [
    "| horizon | measurable | positive abs. return | beat SPY | median abs. | mean abs. "
    "| median excess | mean excess |",
    "|---|---|---|---|---|---|---|---|",
]
for h in HORIZONS:
    sub = table.dropna(subset=[f"event_{h}", f"spy_{h}"])
    overall_lines.append(
        f"| {h} | {len(sub)} | {(sub[f'event_{h}'] > 0).mean():.0%} "
        f"| {(sub[f'excess_{h}'] > 0).mean():.0%} "
        f"| {sub[f'event_{h}'].median():+.1%} | {sub[f'event_{h}'].mean():+.1%} "
        f"| {sub[f'excess_{h}'].median():+.1%} | {sub[f'excess_{h}'].mean():+.1%} |"
    )

# %% distribution shape (3y excess)
d3 = table.dropna(subset=["excess_3y"])["excess_3y"]
dist_lines = [
    f"3y excess-vs-SPY distribution (n={len(d3)}): "
    f"p10 {d3.quantile(0.10):+.0%}, p25 {d3.quantile(0.25):+.0%}, "
    f"median {d3.median():+.0%}, p75 {d3.quantile(0.75):+.0%}, "
    f"p90 {d3.quantile(0.90):+.0%}, mean {d3.mean():+.0%}.",
    f"Share of total 3y excess dollars-of-return concentrated in the top decile of "
    f"events: winners are a thin tail — top 10% of events average "
    f"{d3[d3 >= d3.quantile(0.9)].mean():+.0%} excess while the median event lags.",
]

# %% named winners and losers (3y excess, measurable events)
named = table.dropna(subset=["excess_3y"]).copy()
named["split_date_str"] = pd.to_datetime(named["split_date"]).dt.date.astype(str)
winners = named.nlargest(12, "excess_3y")
losers = named.nsmallest(12, "excess_3y")


def name_rows(frame: pd.DataFrame) -> list[str]:
    return [
        f"| {r.ticker} | {r.split_date_str} | {r.ratio:g}:1 "
        f"| {r.event_3y:+.0%} | {r.excess_3y:+.0%} |"
        for r in frame.itertuples()
    ]


# %% segmentation helper
def segment_block(frame: pd.DataFrame, column: str, title: str) -> list[str]:
    lines = [
        f"\n### By {title}\n",
        "| segment | n (3y) | beat SPY (3y) | median excess (3y) | mean excess (3y) |",
        "|---|---|---|---|---|",
    ]
    sub = frame.dropna(subset=["excess_3y", column])
    for segment, group in sub.groupby(column, observed=True):
        if len(group) < 25:
            continue
        lines.append(
            f"| {segment} | {len(group)} | {(group['excess_3y'] > 0).mean():.0%} "
            f"| {group['excess_3y'].median():+.1%} | {group['excess_3y'].mean():+.1%} |"
        )
    return lines


table["ratio_bucket"] = pd.cut(
    table["ratio"], bins=[1.0, 1.99, 2.0, 4.0, 100.0],
    labels=["<2:1", "2:1", "2-4:1", ">4:1"],
)
table["era"] = pd.cut(
    pd.to_datetime(table["split_date"]).dt.year,
    bins=[2005, 2012, 2018, 2026], labels=["2006-2012", "2013-2018", "2019+"],
)
table["price_bucket"] = pd.cut(
    table["price_level"], bins=[0, 50, 150, 500, 1e9],
    labels=["<$50", "$50-150", "$150-500", ">$500"],
)
size_valid = table["size"].dropna()
table["liquidity"] = pd.cut(
    table["size"],
    bins=[0, size_valid.quantile(0.5), size_valid.quantile(0.9), np.inf],
    labels=["bottom half", "50th-90th pct", "top decile"],
)

# %% assemble report
report_lines = [
    "# Split outcomes: which splits created value?",
    "",
    f"All {len(table)} forward splits (2006+, working set) with forward returns",
    "measured from the execution date; excess = splitter minus SPY over the",
    "same window. Only fully-elapsed horizons count (no partial windows).",
    "",
    "## Overall outcome rates",
    "",
    *overall_lines,
    "",
    "## Distribution: a thin tail of big winners",
    "",
    *dist_lines,
    "",
    "## Largest 3y winners (excess vs SPY)",
    "",
    "| ticker | split | ratio | 3y return | 3y excess |",
    "|---|---|---|---|---|",
    *name_rows(winners),
    "",
    "## Largest 3y losers",
    "",
    "| ticker | split | ratio | 3y return | 3y excess |",
    "|---|---|---|---|---|",
    *name_rows(losers),
    "",
    "## Segmentation (3y horizon)",
    *segment_block(table, "ratio_bucket", "split ratio"),
    *segment_block(table, "era", "era"),
    *segment_block(table, "price_bucket", "pre-split (as-traded) price level"),
    *segment_block(table, "liquidity", "liquidity (median daily dollar volume)"),
    "",
    "Caveats: survivorship bias flatters absolute outcomes (delisted",
    "splitters are missing); SPY comparison carries the usual market-regime",
    "noise; segments are descriptive ex-post breakdowns, not trading",
    "signals — the aggregate no-alpha verdict (METHODOLOGY.md) stands.",
]
report = "\n".join(report_lines)
out = Path("docs/research/split_outcomes.md")
out.write_text(report + "\n")
print(report)

append_report(
    DEFAULT_LOG,
    title="Split-outcome breakdown",
    lines=[f"events: {len(table)}; report: docs/research/split_outcomes.md"],
)
print("done.")
