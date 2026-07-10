# Backtest results: forward returns after forward splits

Excess = splitter return minus baseline return over the same window,
from the split execution date. Baselines: SPY buy-and-hold;
mean of sector/size-matched controls; the momentum-closest control
(isolates the split from its price run-up).
Horizons requiring unelapsed future data are excluded, never partial.

## Train (988 events, 2006-2018)

| comparison | n | median excess | mean excess | hit rate |
|---|---|---|---|---|
| 1y vs spy | 988 | -3.9% | +2.9% | 44% |
| 1y vs controls | 854 | -2.6% | -2.7% | 47% |
| 1y vs momo | 847 | +0.2% | -1.3% | 50% |
| 3y vs spy | 988 | -6.4% | -1.7% | 46% |
| 3y vs controls | 854 | -5.2% | -17.4% | 46% |
| 3y vs momo | 847 | -3.0% | -13.8% | 48% |
| 5y vs spy | 988 | -17.0% | -5.0% | 41% |
| 5y vs controls | 854 | -11.5% | -21.3% | 45% |
| 5y vs momo | 847 | -3.0% | -11.5% | 49% |

## Holdout (383 events, 2019+)

| comparison | n | median excess | mean excess | hit rate |
|---|---|---|---|---|
| 1y vs spy | 320 | -10.5% | -7.7% | 40% |
| 1y vs controls | 319 | -1.3% | -3.5% | 49% |
| 1y vs momo | 313 | +3.5% | -1.6% | 53% |
| 3y vs spy | 205 | -30.8% | -15.0% | 30% |
| 3y vs controls | 205 | -5.1% | +5.2% | 48% |
| 3y vs momo | 201 | +14.3% | +10.8% | 58% |
| 5y vs spy | 107 | -79.2% | -37.9% | 26% |
| 5y vs controls | 107 | -27.7% | -5.6% | 40% |
| 5y vs momo | 105 | -1.7% | +16.7% | 50% |

Caveats: survivorship bias (delisted splitters absent — excess vs
controls is the more robust comparison since controls share the bias);
execution-date anchoring; see DATA_QUALITY.md.
