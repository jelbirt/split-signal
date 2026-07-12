# Split outcomes: which splits created value?

All 1371 forward splits (2006+, working set) with forward returns
measured from the execution date; excess = splitter minus SPY over the
same window. Only fully-elapsed horizons count (no partial windows).

## Overall outcome rates

| horizon | measurable | positive abs. return | beat SPY | median abs. | mean abs. | median excess | mean excess |
|---|---|---|---|---|---|---|---|
| 1y | 1308 | 59% | 43% | +6.3% | +10.8% | -4.9% | +0.3% |
| 3y | 1193 | 60% | 43% | +10.9% | +24.1% | -10.4% | -4.0% |
| 5y | 1095 | 69% | 39% | +36.8% | +55.5% | -21.0% | -8.2% |

## Distribution: a thin tail of big winners

3y excess-vs-SPY distribution (n=1193): p10 -73%, p25 -45%, median -10%, p75 +24%, p90 +59%, mean -4%.
Share of total 3y excess dollars-of-return concentrated in the top decile of events: winners are a thin tail — top 10% of events average +134% excess while the median event lags.

## Largest 3y winners (excess vs SPY)

| ticker | split | ratio | 3y return | 3y excess |
|---|---|---|---|---|
| SITC | 2009-03-10 | 1.0666:1 | +1234% | +1131% |
| IPM | 2010-01-25 | 3:1 | +800% | +755% |
| FTAI | 2022-08-02 | 1.171:1 | +752% | +693% |
| NVDA | 2021-07-20 | 4:1 | +535% | +502% |
| GE | 2023-01-04 | 1.281:1 | +481% | +396% |
| SPHR | 2023-04-21 | 2.165:1 | +413% | +334% |
| SNFCA | 2012-01-11 | 1.05:1 | +367% | +299% |
| NFLX | 2015-07-15 | 7:1 | +303% | +262% |
| XPO | 2022-11-01 | 1.683:1 | +343% | +258% |
| DDD | 2011-05-19 | 2:1 | +306% | +257% |
| MAC | 2009-05-07 | 1.027:1 | +301% | +240% |
| ALK | 2012-03-19 | 2:1 | +297% | +239% |

## Largest 3y losers

| ticker | split | ratio | 3y return | 3y excess |
|---|---|---|---|---|
| GPUS | 2023-06-23 | 1.318:1 | -100% | -178% |
| AGEN | 2023-04-26 | 1.019:1 | -88% | -171% |
| FCUV | 2023-03-24 | 1.5:1 | -99% | -171% |
| DSS | 2023-04-27 | 1.077:1 | -86% | -166% |
| PRE | 2022-05-18 | 1.29:1 | -95% | -153% |
| TXMD | 2009-07-27 | 3:1 | -98% | -145% |
| SAFE | 2022-11-30 | 1.284:1 | -69% | -144% |
| DWSN | 2012-04-26 | 1.05:1 | -80% | -140% |
| UCB | 2009-03-09 | 1.0077:1 | -24% | -139% |
| UCB | 2008-12-08 | 1.0077:1 | -90% | -135% |
| CYH | 2016-04-22 | 1.21:1 | -85% | -132% |
| DWSN | 2018-05-11 | 1.05:1 | -68% | -130% |

## Segmentation (3y horizon)

### By split ratio

| segment | n (3y) | beat SPY (3y) | median excess (3y) | mean excess (3y) |
|---|---|---|---|---|
| <2:1 | 668 | 40% | -14.0% | -7.3% |
| 2:1 | 387 | 47% | -4.4% | -1.1% |
| 2-4:1 | 103 | 47% | -8.1% | +7.4% |
| >4:1 | 35 | 34% | -20.1% | -5.7% |

### By era

| segment | n (3y) | beat SPY (3y) | median excess (3y) | mean excess (3y) |
|---|---|---|---|---|
| 2006-2012 | 575 | 52% | +2.1% | +6.9% |
| 2013-2018 | 413 | 37% | -18.8% | -13.8% |
| 2019+ | 205 | 30% | -30.8% | -15.0% |

### By pre-split (as-traded) price level

| segment | n (3y) | beat SPY (3y) | median excess (3y) | mean excess (3y) |
|---|---|---|---|---|
| <$50 | 628 | 41% | -12.1% | -6.6% |
| $50-150 | 493 | 46% | -6.5% | -1.4% |
| $150-500 | 50 | 28% | -29.8% | -16.3% |

### By liquidity (median daily dollar volume)

| segment | n (3y) | beat SPY (3y) | median excess (3y) | mean excess (3y) |
|---|---|---|---|---|
| bottom half | 575 | 43% | -10.7% | -7.0% |
| 50th-90th pct | 488 | 44% | -7.9% | -2.5% |
| top decile | 96 | 44% | -8.4% | +8.3% |

Caveats: survivorship bias flatters absolute outcomes (delisted
splitters are missing); SPY comparison carries the usual market-regime
noise; segments are descriptive ex-post breakdowns, not trading
signals — the aggregate no-alpha verdict (METHODOLOGY.md) stands.
