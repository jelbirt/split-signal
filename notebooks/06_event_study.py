# %% [markdown]
# # Event study: what did stocks look like before forward splits?
#
# For every plausible forward split since 2006 (working set), compute the
# point-in-time feature vector 90 days before execution, alongside matched
# controls (same sector where known, no split ±2y, closest dollar-volume
# size). Output: data/processed/event_features.parquet and a results table
# in docs/research/event_study_results.md.
#
# Run headless: `uv run python notebooks/06_event_study.py`

# %% setup
from pathlib import Path

import pandas as pd

from split_signal.backtest.controls import dollar_volume_size, match_controls
from split_signal.data.edgar import fundamentals_cache_path
from split_signal.data.prices import price_cache_path
from split_signal.data.quality import DEFAULT_LOG, append_report
from split_signal.features.vector import FEATURE_NAMES, compute_feature_vector

DATA = Path("data")
AS_OF_DAYS_BEFORE = 90
N_CONTROLS = 3
STUDY_START = pd.Timestamp("2006-01-01")

universe = pd.read_parquet(DATA / "processed" / "universe.parquet").set_index("symbol")
catalog = pd.read_parquet(DATA / "processed" / "splits.parquet")
working = set(pd.read_parquet(DATA / "processed" / "working_set.parquet")["symbol"])

events = catalog[
    catalog["is_forward"]
    & catalog["ratio_plausible"]
    & (catalog["date"] >= STUDY_START)
    & catalog["ticker"].isin(working)
].reset_index(drop=True)
print(f"events under study: {len(events)}")

# %% price cache helpers (in-memory memo over the parquet cache)
# Bounded FIFO memo: dicts preserve insertion order, so evicting the first key
# drops the oldest entry. Keeps peak memory at ~_PRICES_MEMO_MAX frames.
_PRICES_MEMO_MAX = 512
_prices_memo: dict[str, pd.DataFrame | None] = {}


def prices_for(symbol: str) -> pd.DataFrame | None:
    if symbol not in _prices_memo:
        path = price_cache_path(DATA, symbol)
        if len(_prices_memo) >= _PRICES_MEMO_MAX:
            del _prices_memo[next(iter(_prices_memo))]
        _prices_memo[symbol] = pd.read_parquet(path) if path.exists() else None
    return _prices_memo[symbol]


def fundamentals_for(symbol: str) -> pd.DataFrame | None:
    path = fundamentals_cache_path(DATA, symbol)
    return pd.read_parquet(path) if path.exists() else None


# %% quarterly size panel (median trailing dollar volume per ticker/quarter)
size_panel_path = DATA / "processed" / "size_panel.parquet"
if size_panel_path.exists():
    size_panel = pd.read_parquet(size_panel_path)
else:
    print("building size panel over the cached universe ...")
    quarters = pd.date_range(STUDY_START, pd.Timestamp.now().normalize(), freq="QE")
    rows = []
    for i, symbol in enumerate(universe.index):
        path = price_cache_path(DATA, symbol)
        if not path.exists():
            continue
        prices = pd.read_parquet(path, columns=["date", "adj_close", "volume"])
        dollar = (prices["adj_close"] * prices["volume"]).rolling(90, min_periods=30).median()
        series = pd.Series(dollar.to_numpy(), index=prices["date"].to_numpy()).sort_index()
        sampled = series.reindex(quarters, method="ffill", tolerance=pd.Timedelta(days=10))
        for quarter, value in sampled.dropna().items():
            rows.append({"symbol": symbol, "quarter": quarter, "size": float(value)})
        if (i + 1) % 1000 == 0:
            print(f"  size panel: {i + 1}/{len(universe)}")
    size_panel = pd.DataFrame(rows)
    size_panel.to_parquet(size_panel_path, index=False)
print(f"size panel: {size_panel['symbol'].nunique()} tickers x quarters")

_size_by_quarter = {q: g.set_index("symbol")["size"] for q, g in size_panel.groupby("quarter")}
_quarters_index = pd.DatetimeIndex(sorted(_size_by_quarter))


def candidates_at(as_of: pd.Timestamp) -> pd.DataFrame:
    """Candidate pool with size at the last completed quarter before as_of."""
    eligible = _quarters_index[_quarters_index <= as_of]
    if len(eligible) == 0:
        return pd.DataFrame(columns=["symbol", "gics_sector", "size"])
    sizes = _size_by_quarter[eligible[-1]]
    pool = pd.DataFrame({"symbol": sizes.index, "size": sizes.to_numpy()})
    pool["gics_sector"] = pool["symbol"].map(universe["gics_sector"])
    return pool


# %% compute event + control feature vectors
records: list[dict] = []
skipped_no_history = 0

for i, event in enumerate(events.itertuples()):
    as_of = event.date - pd.Timedelta(days=AS_OF_DAYS_BEFORE)
    prices = prices_for(event.ticker)
    if prices is None or (prices["date"] <= as_of).sum() < 60:
        skipped_no_history += 1
        continue

    sector = universe["gics_sector"].get(event.ticker)
    sector = None if pd.isna(sector) else sector
    size = dollar_volume_size(prices, as_of)

    vector = compute_feature_vector(
        event.ticker, as_of, prices, fundamentals_for(event.ticker), catalog
    )
    vector.update(
        event_id=i, role="event", split_date=event.date, ratio=event.ratio,
        sector=sector, size=size, sector_matched=sector is not None,
    )
    records.append(vector)

    controls = match_controls(
        event_ticker=event.ticker, event_date=event.date, event_sector=sector,
        event_size=size, candidates=candidates_at(as_of), catalog=catalog,
        n=N_CONTROLS,
    )
    for control in controls:
        control_prices = prices_for(control)
        if control_prices is None:
            continue
        control_vector = compute_feature_vector(
            control, as_of, control_prices, fundamentals_for(control), catalog
        )
        control_vector.update(
            event_id=i, role="control", split_date=event.date, ratio=event.ratio,
            sector=sector, size=dollar_volume_size(control_prices, as_of),
            sector_matched=sector is not None,
        )
        records.append(control_vector)

    if (i + 1) % 200 == 0:
        print(f"  events: {i + 1}/{len(events)}")

features = pd.DataFrame(records)
features.to_parquet(DATA / "processed" / "event_features.parquet", index=False)
event_rows = features[features["role"] == "event"]
control_rows = features[features["role"] == "control"]
print(
    f"feature table: {len(event_rows)} events, {len(control_rows)} controls, "
    f"{skipped_no_history} events skipped (insufficient history)"
)

# %% paired comparison: event vs mean-of-controls per feature
control_means = control_rows.groupby("event_id")[FEATURE_NAMES].mean()
paired = event_rows.set_index("event_id")[FEATURE_NAMES + ["ticker", "split_date"]].join(
    control_means, rsuffix="_ctrl"
)

lines = []
for feature in FEATURE_NAMES:
    pair = paired[[feature, f"{feature}_ctrl"]].dropna()
    if len(pair) < 30:
        lines.append(f"| {feature} | n={len(pair)} | insufficient pairs | | |")
        continue
    diff = pair[feature] - pair[f"{feature}_ctrl"]
    cohens_d = float(diff.mean() / diff.std(ddof=1)) if diff.std(ddof=1) else 0.0
    win_rate = float((diff > 0).mean())
    lines.append(
        f"| {feature} | {len(pair)} | {pair[feature].median():.3f} "
        f"| {pair[f'{feature}_ctrl'].median():.3f} | d={cohens_d:.2f}, win={win_rate:.0%} |"
    )

results_md = "\n".join(
    [
        "# Event study results: pre-split profiles vs. matched controls",
        "",
        f"Events: {len(event_rows)} forward splits (2006+, plausible ratios, working set); "
        f"features as_of {AS_OF_DAYS_BEFORE}d before execution; "
        f"{N_CONTROLS} controls/event (sector-matched where sector known: "
        f"{event_rows['sector_matched'].mean():.0%}).",
        "",
        "| feature | pairs | event median | control median | effect |",
        "|---|---|---|---|---|",
        *lines,
        "",
        "Interpretation notes: d = Cohen's d on paired differences; win = share of",
        "events where the splitter exceeds its control mean. Fundamentals coverage",
        "is thinner outside the S&P (see DATA_QUALITY.md).",
    ]
)
out_md = Path("docs/research/event_study_results.md")
out_md.parent.mkdir(parents=True, exist_ok=True)
out_md.write_text(results_md + "\n")
print(results_md)

# %% log to data quality
append_report(
    DEFAULT_LOG,
    title="Event study run",
    lines=[
        f"events: {len(event_rows)}, controls: {len(control_rows)}, "
        f"skipped (history): {skipped_no_history}",
        f"sector-matched events: {event_rows['sector_matched'].mean():.0%} "
        "(sector known only for current S&P members)",
        f"fundamental-feature coverage among events: "
        f"revenue_growth {event_rows['revenue_growth'].notna().mean():.0%}, "
        f"eps_growth {event_rows['eps_growth'].notna().mean():.0%}",
    ],
)
print("done.")
