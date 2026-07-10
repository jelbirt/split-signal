# %% [markdown]
# # Train the Split Likelihood model (v1)
#
# Builds a quarterly scoring panel (features must mirror
# split_signal.scoring.likelihood.compute_scoring_features), labels each
# ticker-quarter with "forward split within the next 12 months", trains
# a plain-numpy logistic model on quarters <= 2017-12-31 (outcome windows
# end <= 2018 — the 2019+ holdout is untouched), and saves the artifact
# to src/split_signal/scoring/likelihood_v1.json.
#
# Run headless: `uv run python notebooks/09_likelihood_model.py`

# %% setup
import math
from pathlib import Path

import numpy as np
import pandas as pd

from split_signal.data.prices import price_cache_path
from split_signal.data.quality import DEFAULT_LOG, append_report
from split_signal.data.splits import unadjusted_close
from split_signal.scoring.likelihood import REQUIRED_FEATURES, LikelihoodArtifact
from split_signal.scoring.model import LogisticModel, rank_auc

DATA = Path("data")
TRAIN_END = pd.Timestamp("2017-12-31")  # labels observed through 2018-12-31
LIQUIDITY_FLOOR = 5e6
ARTIFACT_PATH = Path("src/split_signal/scoring/likelihood_v1.json")

universe = pd.read_parquet(DATA / "processed" / "universe.parquet")
catalog = pd.read_parquet(DATA / "processed" / "splits.parquet")
quarters = pd.date_range("2006-06-30", pd.Timestamp.now().normalize(), freq="QE")

# %% build the scoring panel (one pass over the price cache)
panel_path = DATA / "processed" / "scoring_panel.parquet"
if panel_path.exists():
    panel = pd.read_parquet(panel_path)
else:
    print("building scoring panel ...")
    forward_splits = catalog[catalog["is_forward"]]
    split_dates = {
        t: g["date"].sort_values().to_numpy() for t, g in forward_splits.groupby("ticker")
    }
    q_tol = pd.Timedelta(days=10)
    rows = []
    symbols = universe["symbol"].tolist()
    for i, symbol in enumerate(symbols):
        path = price_cache_path(DATA, symbol)
        if not path.exists():
            continue
        prices = pd.read_parquet(
            path, columns=["date", "close", "adj_close", "volume", "split_ratio"]
        ).sort_values("date")
        if len(prices) < 300:
            continue
        dates = prices["date"].to_numpy()
        adj = pd.Series(prices["adj_close"].to_numpy(), index=dates)
        true_close = pd.Series(unadjusted_close(prices).to_numpy(), index=dates)
        dollar = pd.Series(
            (prices["adj_close"] * prices["volume"]).rolling(90, min_periods=30)
            .median().to_numpy(),
            index=dates,
        )
        vol = pd.Series(
            (prices["adj_close"].pct_change().rolling(252, min_periods=126)
             .std() * math.sqrt(252)).to_numpy(),
            index=dates,
        )
        at_q = adj.reindex(quarters, method="ffill", tolerance=q_tol)
        year_ago = adj.reindex(quarters - pd.Timedelta(days=365), method="ffill",
                               tolerance=q_tol)
        run_max = adj.cummax().reindex(quarters, method="ffill", tolerance=q_tol)
        price_q = true_close.reindex(quarters, method="ffill", tolerance=q_tol)
        size_q = dollar.reindex(quarters, method="ffill", tolerance=q_tol)
        vol_q = vol.reindex(quarters, method="ffill", tolerance=q_tol)
        first_bar, last_bar = adj.index[0], adj.index[-1]
        ticker_splits = split_dates.get(symbol, np.array([], dtype="datetime64[ns]"))
        for j, quarter in enumerate(quarters):
            if pd.isna(at_q.iloc[j]) or first_bar > quarter - pd.Timedelta(days=330):
                continue
            n_prior = int(np.searchsorted(ticker_splits, np.datetime64(quarter)))
            last_split_age = (
                (quarter - pd.Timestamp(ticker_splits[n_prior - 1])).days / 365.25
                if n_prior else None
            )
            n_by_label_end = int(
                np.searchsorted(
                    ticker_splits, np.datetime64(quarter + pd.Timedelta(days=365))
                )
            )
            rows.append(
                {
                    "symbol": symbol,
                    "quarter": quarter,
                    "ath_drawdown": float(at_q.iloc[j] / run_max.iloc[j] - 1.0),
                    "ret_1y": float(at_q.iloc[j] / year_ago.iloc[j] - 1.0)
                    if pd.notna(year_ago.iloc[j]) and year_ago.iloc[j] > 0 else None,
                    "log_price": float(np.log(price_q.iloc[j]))
                    if pd.notna(price_q.iloc[j]) and price_q.iloc[j] > 0 else None,
                    "volatility": float(vol_q.iloc[j]) if pd.notna(vol_q.iloc[j]) else None,
                    "log_size": float(np.log(size_q.iloc[j]))
                    if pd.notna(size_q.iloc[j]) and size_q.iloc[j] > 0 else None,
                    "prior_splits": float(min(n_prior, 4)),
                    "recent_split": 1.0
                    if last_split_age is not None and last_split_age <= 5.0 else 0.0,
                    "size": float(size_q.iloc[j]) if pd.notna(size_q.iloc[j]) else None,
                    # label valid only if history covers the full 12m window
                    "split_next_12m": float(n_by_label_end > n_prior)
                    if last_bar >= quarter + pd.Timedelta(days=350) else None,
                }
            )
        if (i + 1) % 1000 == 0:
            print(f"  panel: {i + 1}/{len(symbols)}")
    panel = pd.DataFrame(rows)
    panel.to_parquet(panel_path, index=False)
print(f"scoring panel: {len(panel)} ticker-quarters")

# %% train
panel = panel.replace([np.inf, -np.inf], np.nan)  # belt-and-braces vs bad quotes
eligible = panel.dropna(subset=[*REQUIRED_FEATURES, "split_next_12m", "size"])
eligible = eligible[eligible["size"] >= LIQUIDITY_FLOOR]
train = eligible[eligible["quarter"] <= TRAIN_END]
print(
    f"train rows: {len(train)} ({train['split_next_12m'].mean():.2%} positive), "
    f"eligible total: {len(eligible)}"
)

X = train[REQUIRED_FEATURES].to_numpy(dtype=float)
y = train["split_next_12m"].to_numpy(dtype=float)
model = LogisticModel.fit(X, y, feature_names=REQUIRED_FEATURES)
train_probs = model.predict_proba(X)
print(f"train AUC: {rank_auc(train_probs, y):.3f}")
print("standardized coefficients:")
for name, weight in zip(REQUIRED_FEATURES, model.weights, strict=True):
    print(f"  {name:>18}: {weight:+.3f}")

# %% save artifact (reference quantiles from the train distribution)
artifact = LikelihoodArtifact(
    version="v1",
    trained_through=str(TRAIN_END.date()),
    model=model,
    prob_quantiles=np.quantile(train_probs, np.linspace(0, 1, 101)).tolist(),
)
artifact.save(ARTIFACT_PATH)
print(f"artifact saved: {ARTIFACT_PATH}")

append_report(
    DEFAULT_LOG,
    title="Likelihood model v1 trained",
    lines=[
        f"train rows: {len(train)} (quarters <= {TRAIN_END.date()}, "
        f"base rate {train['split_next_12m'].mean():.2%})",
        f"train AUC: {rank_auc(train_probs, y):.3f}",
        f"artifact: {ARTIFACT_PATH}",
    ],
)
print("done.")
