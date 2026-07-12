# %% [markdown]
# # Horizon decay: how far ahead does the split signal reach?
#
# Phase B validated a 12-month prediction horizon (the label design).
# This experiment retrains the same model with 12/18/24/36-month labels
# and measures holdout discrimination per horizon — the decay curve.
#
# Discipline per horizon H: training quarters end H months before the
# 2019-01-01 holdout start (outcome windows never touch the holdout),
# and a row's label is only valid when that symbol's price history
# fully covers quarter + H (no partially-elapsed windows).
#
# No new data needed: features come from the existing scoring panel,
# labels from the split catalog, coverage from the price cache.
#
# Run headless: `uv run python notebooks/11_horizon_decay.py`

# %% setup
from pathlib import Path

import numpy as np
import pandas as pd

from split_signal.data.prices import price_cache_path
from split_signal.data.quality import DEFAULT_LOG, append_report
from split_signal.scoring.likelihood import REQUIRED_FEATURES
from split_signal.scoring.model import LogisticModel, rank_auc

DATA = Path("data")
HORIZONS_MONTHS = [12, 18, 24, 36, 48, 60]
HOLDOUT_START = pd.Timestamp("2019-01-01")
LIQUIDITY_FLOOR = 5e6
DAYS_PER_MONTH = 30.44

panel = pd.read_parquet(DATA / "processed" / "scoring_panel.parquet")
panel = panel.replace([np.inf, -np.inf], np.nan)
panel = panel.dropna(subset=[*REQUIRED_FEATURES, "size"])
panel = panel[panel["size"] >= LIQUIDITY_FLOOR].copy()
catalog = pd.read_parquet(DATA / "processed" / "splits.parquet")
print(f"eligible ticker-quarters: {len(panel)}")

# %% per-symbol split dates and price-coverage end
forward = catalog[catalog["is_forward"]]
split_dates = {t: g["date"].sort_values().to_numpy() for t, g in forward.groupby("ticker")}

coverage_path = DATA / "processed" / "last_bar_by_symbol.parquet"
if coverage_path.exists():
    last_bar = pd.read_parquet(coverage_path).set_index("symbol")["last_bar"]
else:
    print("collecting last-bar dates from the price cache ...")
    rows = []
    for i, symbol in enumerate(panel["symbol"].unique()):
        path = price_cache_path(DATA, symbol)
        if not path.exists():
            continue
        dates = pd.read_parquet(path, columns=["date"])["date"]
        rows.append({"symbol": symbol, "last_bar": dates.max()})
        if (i + 1) % 1000 == 0:
            print(f"  coverage: {i + 1}")
    frame = pd.DataFrame(rows)
    frame.to_parquet(coverage_path, index=False)
    last_bar = frame.set_index("symbol")["last_bar"]
panel["last_bar"] = panel["symbol"].map(last_bar)
panel = panel.dropna(subset=["last_bar"])

# %% relabel, retrain, evaluate per horizon
EMPTY = np.array([], dtype="datetime64[ns]")


def label_for_horizon(frame: pd.DataFrame, horizon_days: int) -> pd.Series:
    """1.0 if a forward split lands in (quarter, quarter+H]; NaN if unobservable."""
    labels = np.full(len(frame), np.nan)
    offset = pd.Timedelta(days=horizon_days)
    slack = pd.Timedelta(days=15)
    for symbol, group in frame.groupby("symbol"):
        dates = split_dates.get(symbol, EMPTY)
        quarters = group["quarter"].to_numpy()
        observable = group["last_bar"].to_numpy() >= (quarters + offset - slack)
        n_prior = np.searchsorted(dates, quarters)
        n_by_end = np.searchsorted(dates, quarters + np.timedelta64(horizon_days, "D"))
        values = (n_by_end > n_prior).astype(float)
        values[~observable] = np.nan
        labels[frame.index.get_indexer(group.index)] = values
    return pd.Series(labels, index=frame.index)


results = []
for months in HORIZONS_MONTHS:
    horizon_days = int(DAYS_PER_MONTH * months)
    labeled = panel.copy()
    labeled["label"] = label_for_horizon(labeled, horizon_days)
    labeled = labeled.dropna(subset=["label"])

    train_end = HOLDOUT_START - pd.Timedelta(days=horizon_days)
    train = labeled[labeled["quarter"] <= train_end]
    holdout = labeled[labeled["quarter"] >= HOLDOUT_START]
    if len(train) < 5000 or holdout["label"].sum() < 30:
        print(f"{months}m: insufficient sample (train {len(train)}, "
              f"holdout positives {int(holdout['label'].sum())}) — skipped")
        continue

    model = LogisticModel.fit(
        train[REQUIRED_FEATURES].to_numpy(dtype=float),
        train["label"].to_numpy(dtype=float),
        feature_names=REQUIRED_FEATURES,
    )
    probs = model.predict_proba(holdout[REQUIRED_FEATURES].to_numpy(dtype=float))
    labels_h = holdout["label"].to_numpy(dtype=float)
    auc = rank_auc(probs, labels_h)

    decile_cut = np.quantile(probs, 0.9)
    top = labels_h[probs >= decile_cut]
    base = float(labels_h.mean())
    top_rate = float(top.mean())
    results.append(
        {
            "horizon_months": months,
            "train_rows": len(train),
            "train_end": str(train_end.date()),
            "holdout_rows": len(holdout),
            "holdout_quarters": int(holdout["quarter"].nunique()),
            "base_rate": base,
            "auc": round(float(auc), 3),
            "top_decile_rate": top_rate,
            "lift": round(top_rate / base, 1) if base else float("nan"),
            "capture": round(float(top.sum() / labels_h.sum()), 2),
        }
    )
    print(f"{months}m: AUC {auc:.3f}, lift {top_rate / base:.1f}x "
          f"(train {len(train)}, holdout {len(holdout)})")

table = pd.DataFrame(results)

# %% report
lines = [
    "# Horizon decay: signal strength vs. prediction horizon",
    "",
    "Same features and model as Split Likelihood v1; only the label window",
    "changes. Train always ends one full label-window before the 2019+",
    "holdout; labels require fully-elapsed windows (no partial credit).",
    "",
    "| horizon | holdout AUC | top-decile lift | capture | base rate "
    "| train rows | holdout rows (quarters) |",
    "|---|---|---|---|---|---|---|",
]
for r in table.to_dict("records"):
    lines.append(
        f"| {r['horizon_months']}m | {r['auc']:.3f} | {r['lift']}x "
        f"| {r['capture']:.0%} | {r['base_rate']:.2%} | {r['train_rows']:,} "
        f"| {r['holdout_rows']:,} ({r['holdout_quarters']}) |"
    )
lines += [
    "",
    "Reading: AUC measures ranking quality at each horizon; lift is how much",
    "denser splitters are in the top decile than in the population. Longer",
    "horizons mechanically raise the base rate (more time for a split to",
    "happen), so lift compresses even where AUC holds — compare both.",
    "Survivorship caveat applies equally at every horizon (DATA_QUALITY.md).",
]
report = "\n".join(lines)
out = Path("docs/research/horizon_decay.md")
out.write_text(report + "\n")
print("\n" + report)

append_report(
    DEFAULT_LOG,
    title="Horizon-decay experiment",
    lines=[
        "; ".join(
            f"{r['horizon_months']}m AUC {r['auc']:.3f} lift {r['lift']}x"
            for r in table.to_dict("records")
        ),
        "report: docs/research/horizon_decay.md",
    ],
)
print("done.")
