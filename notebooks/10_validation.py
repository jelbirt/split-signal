# %% [markdown]
# # Validate the Split Likelihood model on the untouched holdout (2019+)
#
# Three tests, all strictly point-in-time:
#   1. Lift: do top-decile scores capture far more next-12m splitters
#      than the ~decile base rate? (per holdout quarter, aggregated)
#   2. Calibration: do predicted probabilities match realized split rates
#      by score decile?
#   3. Named events: score AAPL 2020, NVDA 2021/2024, TSLA 2020/2022,
#      GOOGL 2022, AMZN 2022 at 6/3/1 months before execution — each vs
#      the same-date score distribution of the whole eligible universe.
#
# Output: docs/research/likelihood_validation.md
# Run headless: `uv run python notebooks/10_validation.py`

# %% setup
from pathlib import Path

import pandas as pd

from split_signal.data.prices import load_prices
from split_signal.data.quality import DEFAULT_LOG, append_report
from split_signal.scoring.likelihood import (
    REQUIRED_FEATURES,
    LikelihoodArtifact,
    compute_scoring_features,
    score_features,
)
from split_signal.scoring.model import rank_auc

DATA = Path("data")
HOLDOUT_START = pd.Timestamp("2019-01-01")
LIQUIDITY_FLOOR = 5e6

artifact = LikelihoodArtifact.load()
catalog = pd.read_parquet(DATA / "processed" / "splits.parquet")
panel = pd.read_parquet(DATA / "processed" / "scoring_panel.parquet")

panel = panel.replace([float("inf"), float("-inf")], pd.NA)
eligible = panel.dropna(subset=[*REQUIRED_FEATURES, "split_next_12m", "size"])
eligible = eligible[eligible["size"] >= LIQUIDITY_FLOOR]
holdout = eligible[eligible["quarter"] >= HOLDOUT_START].copy()
print(
    f"holdout rows: {len(holdout)} across "
    f"{holdout['quarter'].nunique()} quarters, "
    f"base rate {holdout['split_next_12m'].mean():.2%}"
)

# %% score the holdout
X = holdout[REQUIRED_FEATURES].to_numpy(dtype=float)
holdout["prob"] = artifact.model.predict_proba(X)
labels = holdout["split_next_12m"].to_numpy(dtype=float)
auc = rank_auc(holdout["prob"].to_numpy(), labels)
print(f"holdout AUC: {auc:.3f}")

# lift by decile (within each quarter, then pooled)
holdout["decile"] = holdout.groupby("quarter")["prob"].transform(
    lambda s: pd.qcut(s.rank(method="first"), 10, labels=False)
)
decile_rates = holdout.groupby("decile")["split_next_12m"].agg(["mean", "count"])
base_rate = float(holdout["split_next_12m"].mean())
top_decile_rate = float(decile_rates.loc[9, "mean"])
lift = top_decile_rate / base_rate if base_rate else float("nan")
capture = float(
    holdout[holdout["decile"] == 9]["split_next_12m"].sum()
    / holdout["split_next_12m"].sum()
)
print(f"top-decile split rate {top_decile_rate:.2%} vs base {base_rate:.2%} "
      f"(lift {lift:.1f}x, captures {capture:.0%} of all splitters)")

# calibration by predicted-probability decile
holdout["prob_bin"] = pd.qcut(holdout["prob"].rank(method="first"), 10, labels=False)
calibration = holdout.groupby("prob_bin").agg(
    predicted=("prob", "mean"), realized=("split_next_12m", "mean"), n=("prob", "count")
)

# %% named-event test
NAMED = [
    ("AAPL", "2020-08-31"), ("NVDA", "2021-07-20"), ("NVDA", "2024-06-10"),
    ("TSLA", "2020-08-31"), ("TSLA", "2022-08-25"),
    ("GOOGL", "2022-07-18"), ("AMZN", "2022-06-06"),
]
named_rows = []
for ticker, split_date in NAMED:
    prices = load_prices(DATA, ticker)
    for months in (12, 9, 6, 3, 1):
        as_of = pd.Timestamp(split_date) - pd.Timedelta(days=int(30.44 * months))
        features = compute_scoring_features(prices, catalog, ticker, as_of)
        try:
            result = score_features(features, artifact)
        except ValueError as exc:
            named_rows.append({"ticker": ticker, "split": split_date,
                               "months_before": months, "error": str(exc)})
            continue
        named_rows.append(
            {
                "ticker": ticker, "split": split_date, "months_before": months,
                "index": result["index"], "probability": result["probability"],
            }
        )
named = pd.DataFrame(named_rows)
print(named.to_string(index=False))

# %% write the report
lines = [
    "# Split Likelihood v1 — holdout validation (2019+)",
    "",
    f"Model trained through {artifact.trained_through}; holdout {len(holdout)} "
    f"ticker-quarters over {holdout['quarter'].nunique()} quarters; base rate "
    f"{base_rate:.2%}; liquidity floor ${LIQUIDITY_FLOOR / 1e6:.0f}M.",
    "",
    "## Discrimination and lift",
    "",
    f"- Holdout AUC: **{auc:.3f}**",
    f"- Top-decile split rate: **{top_decile_rate:.2%}** vs base {base_rate:.2%} "
    f"→ **{lift:.1f}x lift**; the top decile captures **{capture:.0%}** of all "
    "next-12m splitters.",
    "",
    "## Calibration (predicted vs realized, by decile)",
    "",
    "| decile | predicted | realized | n |",
    "|---|---|---|---|",
    *(
        f"| {int(i)} | {r.predicted:.2%} | {r.realized:.2%} | {int(r.n)} |"
        for i, r in calibration.iterrows()
    ),
    "",
    "## Named-event test (index = percentile vs reference panel)",
    "",
    "| ticker | split date | 12m | 9m | 6m | 3m | 1m before |",
    "|---|---|---|---|---|---|---|",
]
for (ticker, split_date), group in named.groupby(["ticker", "split"], sort=False):
    by_month = {int(r["months_before"]): r for _, r in group.iterrows()}
    cells = [
        (f"{int(by_month[m]['index'])}" if "index" in by_month[m]
         and pd.notna(by_month[m].get("index")) else "n/a")
        for m in (12, 9, 6, 3, 1)
    ]
    lines.append(f"| {ticker} | {split_date} | " + " | ".join(cells) + " |")
lines += [
    "",
    "Reminder: this index predicts the split EVENT only. Phase A showed the",
    "event carries no expected excess return (docs/METHODOLOGY.md).",
]
report = "\n".join(lines)
out = Path("docs/research/likelihood_validation.md")
out.write_text(report + "\n")
print(f"\nwritten: {out}")

append_report(
    DEFAULT_LOG,
    title="Likelihood v1 holdout validation",
    lines=[
        f"holdout AUC {auc:.3f}; top-decile lift {lift:.1f}x "
        f"(rate {top_decile_rate:.2%} vs base {base_rate:.2%}); "
        f"top-decile capture {capture:.0%}",
        "report: docs/research/likelihood_validation.md",
    ],
)
print("done.")
