# Split-Signal

A research-backed **Split Likelihood Index** for US stocks: a calibrated
0–100 score for *"how likely is this company to execute a forward stock
split within the next 12 months?"* — built on 20 years of data
(5,613 tickers, 7,316 split events, SEC EDGAR fundamentals).

## What it is — and what it is NOT

- **It predicts the split event.** Holdout-validated (2019+, untouched by
  training): AUC 0.740, 3.8× top-decile lift; AAPL 2020, NVDA 2021/2024,
  TSLA 2020/2022, GOOGL/AMZN 2022 all scored ≥90th percentile at 6/3/1
  months before execution using only then-knowable data.
- **It is NOT a buy signal.** The Phase A research
  ([docs/METHODOLOGY.md](docs/METHODOLOGY.md)) found the median splitter
  *underperforms* SPY after splitting, and the pre-split profile adds no
  return edge over plain momentum. The CLI prints momentum context
  separately and never blends it into the index.
- Known model limits: it cannot know policy ("Berkshire never splits" —
  BRK-B scores 85 anyway); absolute probabilities overstate ~2× in the
  current low-split era (rankings are unaffected); survivorship and
  execution-date caveats in [docs/DATA_QUALITY.md](docs/DATA_QUALITY.md).

**Research tool, not financial advice.**

## Usage

```bash
uv sync                                  # set up
uv run split-signal score AAPL NVDA COST # score tickers (fetches on demand)
uv run split-signal scan --watchlist my_tickers.txt
uv run split-signal ingest               # (re)build the full data cache
```

Example output:

```
NVDA — Split Likelihood Index: 97/100 (≈8.8% chance of a forward split within 12m)
  momentum context (separate; NOT split-alpha): 1y return +24.5%
  top drivers (log-odds): log_price +0.67 | recent_split +0.60 | ...
```

## How it works

Quarterly point-in-time features (distance from all-time high — the
strongest predictor, as-traded price level, split history, momentum,
volatility, liquidity) feed a plain-numpy logistic model trained on
2006–2017 with outcomes through 2018; 2019+ was held out for validation.
Every feature takes an explicit `as_of` date and is invariance-tested
against lookahead. Full methodology, research scripts (jupytext percent
format, `notebooks/`), and honest negative results are in `docs/`.

## Development

```bash
uv run pytest          # 91 tests, no network
uv run ruff check .
uv run python notebooks/09_likelihood_model.py   # retrain (rebuilds panel)
uv run python notebooks/10_validation.py         # re-validate
```
