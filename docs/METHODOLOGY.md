# Split-Signal Methodology — Phase A Research Findings

**Status: complete, awaiting owner sign-off (task A8 gate).**
Study window 2006–2026; universe 5,613 cached US common stocks (S&P 500 ∪
all listed forward splitters); 1,371 forward-split events analyzed.
Full evidence: [event_study_results.md](research/event_study_results.md),
[backtest_results.md](research/backtest_results.md),
[profile_backtest_results.md](research/profile_backtest_results.md);
data caveats in [DATA_QUALITY.md](DATA_QUALITY.md).

## The three questions and their answers

### Q1. What does the pre-split profile look like? — ANSWERED, STRONG SIGNAL

Ninety days before a forward split, versus sector/size-matched non-splitting
controls (1,371 events, 3,708 controls):

| marker | evidence |
|---|---|
| **Trading near all-time high** | strongest discriminator: median 9.7% below ATH vs 32% for controls (d=0.54, 76% win rate) |
| **Serial splitter** | prior forward splits d=0.38; last split 4.8y ago vs 11y (d=−0.57) |
| **Momentum** | 1y return 23.5% vs 14.6% median (d=0.15–0.21 across 1–3y) |
| **Lower volatility** | splitters are *calmer* than peers (d=−0.09) |
| Fundamentals | revenue growth indistinguishable (d=0.02); EPS growth marginal (d=0.06) — on ~30% coverage |

**Splits are substantially predictable as events.** A company near its high,
with a split history and steady momentum, is the classic next splitter.

### Q2. Is the split itself a buy signal? — ANSWERED: NO

Forward returns from execution date, 988 train + 383 holdout events:
the **median splitter underperformed SPY at every horizon in both periods**
(holdout 3y: −30.8% median excess, 30% hit rate) and roughly matched its
momentum-matched control. Post-split drift, documented in pre-2000s
academic literature, is absent in this 2006+ sample. Means exceed medians
everywhere — a long right tail (AAPL/NVDA-class winners) hides the
typical splitter's lag. Buying *because of* a split, or to anticipate the
pop from one, is not supported.

### Q3. Does the pre-split *profile* select outperformers? — ANSWERED: NO ALPHA BEYOND MOMENTUM

Quarterly top-100 portfolios over the whole liquid universe, 1y holds,
77 cohorts: the profile composite (ATH proximity + momentum + split
history) returned **+8.7%/yr in train vs momentum-only +8.9% and SPY
+9.8%**; in holdout **+18.2% vs momentum +22.1% and SPY +16.6%**. The
split-specific tilt *subtracted* from plain momentum out-of-sample, and
survivorship bias inflates both portfolios' SPY excess. The falsifiability
clause in SPEC.md is triggered: **split-anticipation adds no measurable
return edge beyond ordinary momentum.**

## What this means for the predictability index

The honest product is a **Split Likelihood Index** — not an alpha claim:

1. **Split likelihood (0–100)** — supported by Q1. Components: ATH
   proximity, prior-split count/recency, trailing momentum, volatility,
   (price level as a secondary factor). Useful for anticipating the
   *event* — which the owner asked for — with the Q2/Q3 finding stated
   plainly alongside: the event itself carries no expected excess return.
2. **Momentum/trend context score, separately labeled** — if a
   "buy-strength" component is wanted, the evidence says plain momentum
   is that component; bundling it inside a "split index" would launder
   momentum as split-alpha. Report it as its own number.
3. Every scored ticker carries data-sufficiency flags and the standing
   disclaimer.

## Limitations (what could overturn these findings)

- **Survivorship bias**: delisted splitters (acquired or failed) are
  invisible; their absence most likely *flatters* splitter forward
  returns, so Q2's negative verdict is, if anything, understated.
- **Execution-date anchoring**: announcement-day drift (days-scale) is
  not measurable without announcement dates (8-K recovery or paid data).
  The long-hold conclusions (1y+) are unlikely to change.
- **One preregistered composite**: Q3 tested the single composite implied
  by Q1 rather than optimizing weights — deliberately, to avoid
  curve-fitting. A weight search could only produce in-sample wins that
  Q3's holdout design exists to catch.
- **Fundamentals coverage** (~30% of events, ~2009+): a fundamentals-led
  profile is untested, though Q1's near-zero revenue-growth effect gives
  it little motivation.

## Paid-data gate recommendation

**Do not purchase data now.** The negative Q2/Q3 verdicts are robust to
the known free-tier gaps (survivorship bias strengthens, not weakens,
them). Paid data (~$30/mo tier) becomes worthwhile only if the owner
wants (a) announcement-date drift studies, or (b) a survivorship-free
re-validation before trusting the momentum baseline itself.

## Recommended Phase B (owner decision)

Build the CLI scorer as: **split-likelihood index (primary) + separately
labeled momentum context + data-quality flags + disclaimer.** Drop any
implication that a high score predicts excess returns.
