# Split Likelihood v1 — holdout validation (2019+)

Model trained through 2017-12-31; holdout 50006 ticker-quarters over 26 quarters; base rate 1.58%; liquidity floor $5M.

## Discrimination and lift

- Holdout AUC: **0.740**
- Top-decile split rate: **5.99%** vs base 1.58% → **3.8x lift**; the top decile captures **38%** of all next-12m splitters.

## Calibration (predicted vs realized, by decile)

| decile | predicted | realized | n |
|---|---|---|---|
| 0 | 0.38% | 0.30% | 5001 |
| 1 | 0.74% | 0.20% | 5001 |
| 2 | 1.14% | 0.88% | 5000 |
| 3 | 1.64% | 0.92% | 5001 |
| 4 | 2.19% | 0.90% | 5000 |
| 5 | 2.79% | 1.08% | 5001 |
| 6 | 3.47% | 1.24% | 5000 |
| 7 | 4.33% | 1.78% | 5001 |
| 8 | 5.55% | 2.68% | 5000 |
| 9 | 9.47% | 5.80% | 5001 |

## Named-event test (index = percentile vs reference panel)

| ticker | split date | 6m before | 3m before | 1m before |
|---|---|---|---|---|
| AAPL | 2020-08-31 | 90 | 94 | 97 |
| NVDA | 2021-07-20 | 98 | 99 | 100 |
| NVDA | 2024-06-10 | 100 | 100 | 100 |
| TSLA | 2020-08-31 | 91 | 100 | 100 |
| TSLA | 2022-08-25 | 95 | 92 | 95 |
| GOOGL | 2022-07-18 | 100 | 97 | 90 |
| AMZN | 2022-06-06 | 100 | 96 | 90 |

Reminder: this index predicts the split EVENT only. Phase A showed the
event carries no expected excess return (docs/METHODOLOGY.md).
