# Event study results: pre-split profiles vs. matched controls

Events: 1371 forward splits (2006+, plausible ratios, working set); features as_of 90d before execution; 3 controls/event (sector-matched where sector known: 22%).

| feature | pairs | event median | control median | effect |
|---|---|---|---|---|
| ret_1y | 1220 | 0.235 | 0.146 | d=0.15, win=61% |
| ret_2y | 1193 | 0.436 | 0.244 | d=0.21, win=62% |
| ret_3y | 1179 | 0.623 | 0.380 | d=0.14, win=64% |
| price_level | 1236 | 49.765 | 32.022 | d=0.17, win=69% |
| ath_drawdown | 1236 | -0.097 | -0.322 | d=0.54, win=76% |
| volatility | 1231 | 0.305 | 0.353 | d=-0.09, win=39% |
| revenue_growth | 358 | 0.066 | 0.066 | d=0.02, win=50% |
| eps_growth | 398 | 0.105 | 0.029 | d=0.06, win=54% |
| market_cap | 429 | 9057949585.243 | 11982065497.857 | d=-0.05, win=52% |
| prior_splits | 1236 | 2.000 | 1.333 | d=0.38, win=56% |
| years_since_last_split | 737 | 4.794 | 11.036 | d=-0.57, win=27% |

Interpretation notes: d = Cohen's d on paired differences; win = share of
events where the splitter exceeds its control mean. Fundamentals coverage
is thinner outside the S&P (see DATA_QUALITY.md).
