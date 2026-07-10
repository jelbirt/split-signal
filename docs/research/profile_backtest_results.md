# Profile backtest: quarterly top-N portfolios, 1y forward returns

Universe: all cached tickers with >= $5M median daily
dollar volume at formation. Profile composite: z(ATH proximity) +
z(1y momentum, winsorized) + 0.5*recent-split + 0.25*min(prior splits, 4).
Overlapping quarterly cohorts (not independent samples); equal weight;
no transaction costs; survivorship-biased universe (currently-listed
only) — biases affect profile and momentum portfolios equally, and the
SPY comparison overstates every portfolio's absolute numbers.

## Train (51 quarterly cohorts, median eligible/quarter: 971)

| portfolio | cohorts | mean 1y return | mean excess vs SPY | median excess | quarters beating SPY |
|---|---|---|---|---|---|
| profile top-100 | 51 | +8.7% | -1.1% | -1.7% | 43% |
| momentum top-100 | 51 | +8.9% | -0.9% | -1.5% | 47% |
| SPY | 51 | +9.8% | | | |

## Holdout (26 quarterly cohorts, median eligible/quarter: 1988)

| portfolio | cohorts | mean 1y return | mean excess vs SPY | median excess | quarters beating SPY |
|---|---|---|---|---|---|
| profile top-100 | 26 | +18.2% | +1.6% | +3.1% | 58% |
| momentum top-100 | 26 | +22.1% | +5.5% | +10.7% | 58% |
| SPY | 26 | +16.6% | | | |

Read: 'profile beats momentum' is the falsifiable claim; 'both beat
SPY' is inflated by survivorship and should not be taken at face value.
