# %% [markdown]
# # Profile backtest: does the PRE-SPLIT PROFILE select outperformers?
#
# The event backtest (07) showed the split event itself is not a buy
# signal. This asks the index's real question: applied to the whole
# cached universe each quarter, does the profile that precedes splits —
# near all-time high, serial splitter, positive momentum, moderate
# volatility — select stocks that beat SPY and beat a momentum-only
# portfolio over the following year?
#
# Method: quarterly feature panel over all cached tickers; each quarter
# form equal-weight top-N portfolios (profile composite vs momentum-only)
# over a liquidity floor; measure overlapping 1y forward returns; report
# train (2006-2018) / holdout (2019+) separately.
#
# Run headless: `uv run python notebooks/08_profile_backtest.py`

# %% setup
from pathlib import Path

import numpy as np
import pandas as pd

from split_signal.data.prices import load_prices, price_cache_path
from split_signal.data.quality import DEFAULT_LOG, append_report

DATA = Path("data")
TRAIN_END = pd.Timestamp("2018-12-31")
TOP_N = 100
LIQUIDITY_FLOOR = 5e6  # median daily dollar volume
FWD_TOL = pd.Timedelta(days=15)

universe = pd.read_parquet(DATA / "processed" / "universe.parquet")
catalog = pd.read_parquet(DATA / "processed" / "splits.parquet")
size_panel = pd.read_parquet(DATA / "processed" / "size_panel.parquet")
quarters = pd.DatetimeIndex(sorted(size_panel["quarter"].unique()))
formation_quarters = quarters[(quarters >= "2006-06-30") & (quarters <= "2025-06-30")]

# %% quarterly feature panel (one pass over the price cache)
panel_path = DATA / "processed" / "profile_panel.parquet"
if panel_path.exists():
    panel = pd.read_parquet(panel_path)
else:
    print("building profile panel ...")
    forward_splits = catalog[catalog["is_forward"]]
    split_dates: dict[str, np.ndarray] = {
        t: g["date"].sort_values().to_numpy() for t, g in forward_splits.groupby("ticker")
    }
    rows = []
    symbols = universe["symbol"].tolist()
    for i, symbol in enumerate(symbols):
        path = price_cache_path(DATA, symbol)
        if not path.exists():
            continue
        prices = pd.read_parquet(path, columns=["date", "adj_close"]).sort_values("date")
        series = pd.Series(
            prices["adj_close"].to_numpy(), index=prices["date"].to_numpy()
        )
        if len(series) < 300:
            continue
        at_quarter = series.reindex(quarters, method="ffill", tolerance=pd.Timedelta(days=10))
        year_ago = series.reindex(
            quarters - pd.Timedelta(days=365), method="ffill", tolerance=pd.Timedelta(days=10)
        )
        year_fwd = series.reindex(
            quarters + pd.Timedelta(days=365), method="ffill", tolerance=FWD_TOL
        )
        running_max = series.cummax().reindex(
            quarters, method="ffill", tolerance=pd.Timedelta(days=10)
        )
        last_bar = series.index[-1]
        ticker_splits = split_dates.get(symbol, np.array([], dtype="datetime64[ns]"))
        for j, quarter in enumerate(quarters):
            price_now = at_quarter.iloc[j]
            if pd.isna(price_now) or series.index[0] > quarter - pd.Timedelta(days=330):
                continue
            n_prior = int(np.searchsorted(ticker_splits, np.datetime64(quarter)))
            fwd = year_fwd.iloc[j]
            rows.append(
                {
                    "symbol": symbol,
                    "quarter": quarter,
                    "ret_1y": float(price_now / year_ago.iloc[j] - 1.0)
                    if pd.notna(year_ago.iloc[j]) else np.nan,
                    "ath_drawdown": float(price_now / running_max.iloc[j] - 1.0),
                    "prior_splits": n_prior,
                    "recent_split": bool(
                        n_prior > 0
                        and (quarter - pd.Timestamp(ticker_splits[n_prior - 1])).days
                        <= 5 * 365
                    ),
                    # fwd return only when the horizon truly elapsed (no partial windows)
                    "fwd_1y": float(fwd / price_now - 1.0)
                    if pd.notna(fwd) and last_bar >= quarter + pd.Timedelta(days=350)
                    else np.nan,
                }
            )
        if (i + 1) % 1000 == 0:
            print(f"  panel: {i + 1}/{len(symbols)}")
    panel = pd.DataFrame(rows)
    panel = panel.merge(size_panel, on=["symbol", "quarter"], how="left")
    panel.to_parquet(panel_path, index=False)
print(f"panel: {len(panel)} ticker-quarters, {panel['symbol'].nunique()} tickers")

# %% SPY forward returns per quarter
spy = load_prices(DATA, "SPY")
spy_series = pd.Series(spy["adj_close"].to_numpy(), index=spy["date"].to_numpy()).sort_index()
spy_now = spy_series.reindex(quarters, method="ffill", tolerance=pd.Timedelta(days=10))
spy_fwd = spy_series.reindex(
    quarters + pd.Timedelta(days=365), method="ffill", tolerance=FWD_TOL
)
spy_fwd_1y = pd.Series(spy_fwd.to_numpy() / spy_now.to_numpy() - 1.0, index=quarters)


# %% portfolio formation and measurement
def zscore(series: pd.Series) -> pd.Series:
    return (series - series.mean()) / series.std(ddof=0)


cohorts = []
for quarter in formation_quarters:
    q = panel[(panel["quarter"] == quarter)].dropna(subset=["ret_1y", "ath_drawdown", "size"])
    q = q[(q["size"] >= LIQUIDITY_FLOOR) & q["fwd_1y"].notna()]
    if len(q) < 300 or pd.isna(spy_fwd_1y.get(quarter)):
        continue
    # profile composite: near ATH + momentum + serial-splitter bonus
    score = (
        zscore(q["ath_drawdown"])            # closer to ATH = higher
        + zscore(q["ret_1y"].clip(-1, 3))    # momentum, winsorized
        + 0.5 * q["recent_split"].astype(float)
        + 0.25 * np.minimum(q["prior_splits"], 4)
    )
    profile = q.assign(_s=score).nlargest(TOP_N, "_s")
    momentum = q.nlargest(TOP_N, "ret_1y")
    cohorts.append(
        {
            "quarter": quarter,
            "period": "train" if quarter <= TRAIN_END else "holdout",
            "n_eligible": len(q),
            "profile_fwd": float(profile["fwd_1y"].mean()),
            "momentum_fwd": float(momentum["fwd_1y"].mean()),
            "spy_fwd": float(spy_fwd_1y[quarter]),
        }
    )

cohorts_df = pd.DataFrame(cohorts)
cohorts_df.to_parquet(DATA / "processed" / "profile_backtest.parquet", index=False)


# %% report
def block(frame: pd.DataFrame, name: str, column: str) -> str:
    excess = frame[column] - frame["spy_fwd"]
    return (
        f"| {name} | {len(frame)} | {frame[column].mean():+.1%} | {excess.mean():+.1%} "
        f"| {excess.median():+.1%} | {(excess > 0).mean():.0%} |"
    )


sections = []
for period in ["train", "holdout"]:
    frame = cohorts_df[cohorts_df["period"] == period]
    sections += [
        f"\n## {period.capitalize()} ({len(frame)} quarterly cohorts, "
        f"median eligible/quarter: {int(frame['n_eligible'].median())})\n",
        "| portfolio | cohorts | mean 1y return | mean excess vs SPY "
        "| median excess | quarters beating SPY |",
        "|---|---|---|---|---|---|",
        block(frame, f"profile top-{TOP_N}", "profile_fwd"),
        block(frame, f"momentum top-{TOP_N}", "momentum_fwd"),
        f"| SPY | {len(frame)} | {frame['spy_fwd'].mean():+.1%} | | | |",
    ]

report = "\n".join(
    [
        "# Profile backtest: quarterly top-N portfolios, 1y forward returns",
        "",
        f"Universe: all cached tickers with >= ${LIQUIDITY_FLOOR / 1e6:.0f}M median daily",
        "dollar volume at formation. Profile composite: z(ATH proximity) +",
        "z(1y momentum, winsorized) + 0.5*recent-split + 0.25*min(prior splits, 4).",
        "Overlapping quarterly cohorts (not independent samples); equal weight;",
        "no transaction costs; survivorship-biased universe (currently-listed",
        "only) — biases affect profile and momentum portfolios equally, and the",
        "SPY comparison overstates every portfolio's absolute numbers.",
        *sections,
        "",
        "Read: 'profile beats momentum' is the falsifiable claim; 'both beat",
        "SPY' is inflated by survivorship and should not be taken at face value.",
    ]
)
out = Path("docs/research/profile_backtest_results.md")
out.write_text(report + "\n")
print(report)

append_report(
    DEFAULT_LOG,
    title="Profile backtest run",
    lines=[
        f"cohorts: {len(cohorts_df)} quarters "
        f"(train {int((cohorts_df['period'] == 'train').sum())}, "
        f"holdout {int((cohorts_df['period'] == 'holdout').sum())})",
        "results: docs/research/profile_backtest_results.md",
    ],
)
print("done.")
