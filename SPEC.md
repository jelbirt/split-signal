# Spec: Split-Signal — Stock Split Predictability Index

## Objective

Develop a **data-backed methodology** for identifying US stocks that are strong long-term buy candidates, with particular attention to stocks whose profile historically preceded value-generating (forward) stock splits — then encode that methodology in a **Python scoring tool** that produces a "predictability index" for any queried ticker.

### Framing (agreed up front)

A stock split does not create fundamental value; it is a *symptom* of sustained price appreciation and a *signal* of management confidence (academic literature documents modest post-split-announcement drift). Therefore the research question is:

> **What measurable characteristics — fundamental, price-based, and structural — did stocks exhibit in the 1–3 years *before* announcing a forward split, and did those characteristics also predict continued outperformance for long-term holders?**

The split is a predictable *event* and a candidate *signal component*, not the mechanism of return. Reverse splits are included in the dataset as a (likely negative) signal.

### Falsifiability requirement

The research must report what the data actually shows. If split-preceding profiles carry **no predictive alpha** beyond plain momentum/fundamentals, the methodology document says so, and the index is built on whatever *does* predict forward returns — with split likelihood reported as a separate component. A negative result is a valid, useful outcome.

### Two phases

- **Phase A — Research.** Assemble a 15–20 year dataset (prices, split events, fundamentals) for the universe below. Catalog every forward split; characterize the pre-split profile; backtest candidate indicators against forward returns with strict point-in-time discipline. Deliverable: `docs/METHODOLOGY.md` — the validated indicator set, weights, backtest evidence, and limitations.
- **Phase B — Tool.** A Python CLI that applies the validated methodology: `split-signal score AAPL NVDA COST` → per-ticker index (0–100) with component breakdown; plus a `scan` mode over a watchlist/universe. Human makes all buy decisions.

### User & success picture

Single user (the project owner), personal decision-support for long-term buy-and-hold selection. Success = a written methodology whose backtest holds up out-of-sample, and a tool that ranks queried tickers by that methodology in seconds with transparent reasoning.

## Tech Stack

- **Python 3.11+**, managed with `uv` (env + lockfile)
- **Research:** pandas, numpy, matplotlib, Jupyter (notebooks in `notebooks/`)
- **Data:** `yfinance` (prices, split history, basic fundamentals — primary), Stooq CSV endpoints (price backup), SEC EDGAR XBRL "companyfacts" API (deep fundamentals — free, official)
- **Tool:** plain Python package with a CLI (`argparse` or `typer`), no web service in scope
- **Quality:** pytest, ruff

### Data budget: free-first with a monitored gate

Start with free sources only. **Every ingestion run logs coverage and quality gaps** (missing tickers, missing years, suspect prices, unavailable delisted names) to `docs/DATA_QUALITY.md`. If research conclusions become gated on data we can't get free (chiefly: delisted tickers / survivorship bias, point-in-time fundamentals), that is raised explicitly as a **decision gate** for a paid tier — not silently worked around.

## Commands

```
Setup:   uv sync
Test:    uv run pytest
Lint:    uv run ruff check --fix . && uv run ruff format .
Research:uv run jupyter lab
Ingest:  uv run split-signal ingest --universe sp500-plus-splitters
Score:   uv run split-signal score AAPL NVDA COST
Scan:    uv run split-signal scan --watchlist watchlists/default.txt
```

(`ingest`/`score`/`scan` are Phase A/B deliverables; they exist as stubs until built.)

## Project Structure

```
SPEC.md               → this document
data/raw/             → cached API pulls (gitignored; cache-first, re-runnable)
data/processed/       → cleaned parquet datasets (gitignored)
data/fixtures/        → tiny frozen CSV samples for tests (committed)
notebooks/            → numbered research notebooks (01_universe.ipynb, ...)
src/split_signal/     → the package
  data/               →   ingestion + caching (yfinance, EDGAR, Stooq)
  features/           →   indicator computation (point-in-time safe)
  backtest/           →   event study + forward-return backtesting
  scoring/            →   the predictability index (Phase B)
  cli.py              →   CLI entry point
tests/                → pytest suites (no network — fixtures only)
docs/METHODOLOGY.md   → the research deliverable (living)
docs/DATA_QUALITY.md  → coverage/gap log per ingestion run
tasks/                → plan.md, todo.md (per /plan convention)
```

### Universe

Current + historical S&P 500 constituents **plus** all US-listed stocks with a forward split in the last 20 years (2006–2026). Reverse splits within the universe are kept and flagged. Known limitation: free sources under-cover delisted names; the gap is measured and logged, not ignored.

## Code Style

Typed, small, functional-leaning modules; pandas for tabular work; dataclasses for domain objects. Example of target style:

```python
from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class SplitEvent:
    ticker: str
    announced: date | None  # announcement date if recoverable, else None
    executed: date
    ratio: float  # 4.0 for 4-for-1; < 1.0 indicates a reverse split

    @property
    def is_forward(self) -> bool:
        return self.ratio > 1.0


def pre_event_return(prices: pd.Series, event_date: date, window_days: int = 365) -> float:
    """Total return over the window ending the day BEFORE event_date.

    Uses only data strictly prior to the event (point-in-time safe).
    """
    window = prices.loc[: pd.Timestamp(event_date) - pd.Timedelta(days=1)].tail(window_days)
    if len(window) < window_days // 2:
        raise ValueError(f"insufficient history before {event_date}")
    return float(window.iloc[-1] / window.iloc[0] - 1.0)
```

Conventions: `snake_case`, type hints everywhere, docstrings state point-in-time assumptions, no bare `except`, ruff-clean. Notebooks may be exploratory, but any logic promoted into `src/` gets tests.

## Testing Strategy

- **Framework:** pytest; tests live in `tests/`, mirroring `src/split_signal/`.
- **No network in tests.** All tests run against small committed fixtures in `data/fixtures/`.
- **What gets tested:** feature/indicator math (known-answer tests), split-event parsing (incl. reverse splits and multi-split tickers), backtest mechanics (especially **lookahead-bias guards** — a feature computed at time T must fail loudly if fed data after T), scoring formula, CLI output shape.
- **Coverage expectation:** all of `features/`, `backtest/`, `scoring/` covered; ingestion covered via fixture-replay; notebooks exempt.
- **Research validation ≠ unit tests:** backtests use a train/holdout time split (e.g., fit on 2006–2018, validate on 2019–2025) and benchmark against SPY buy-and-hold.

## Boundaries

- **Always:**
  - Cache every API response locally; respect rate limits; ingestion must be resumable.
  - Enforce point-in-time discipline in every feature and backtest (no lookahead, no survivorship hand-waving — gaps get logged).
  - Update `docs/DATA_QUALITY.md` on every ingestion run.
  - Run `pytest` + `ruff` before any commit; propose commits and wait for approval (never auto-commit).
  - Present all results with limitations stated; tool output carries a "research tool, not financial advice" disclaimer.
- **Ask first:**
  - Any paid data subscription or API key sign-up (the data decision gate).
  - Adding heavy dependencies (scipy, sklearn, backtrader, etc.) or expanding the universe.
  - Changing the methodology after Phase A sign-off; publishing the repo publicly.
- **Never:**
  - Connect to a brokerage, place/automate trades, or build toward automated execution. *(Scope note: the owner may pursue brokerage integration / trade automation as a separate future project with its own spec; it is deliberately excluded from this one, so don't design for it here.)*
  - Commit API keys, raw data dumps, or notebook output containing large data blobs.
  - Report backtest results without survivorship/lookahead caveats attached.
  - Scrape sources against their terms of service.

## Success Criteria

Phase A (research) is done when:
1. Dataset: ≥ 95% price-history coverage of the defined universe, and a split-event catalog with (at minimum) execution dates and ratios for all forward splits 2006–2026 in-universe.
2. An event study quantifies the pre-split profile (price run-up, price level, EPS/revenue growth, momentum, market-cap trajectory, prior splits, sector) vs. matched non-split controls.
3. A backtest with a train/holdout time split answers: *do split-preceding profiles predict superior 1y/3y/5y forward returns vs. SPY and vs. momentum-only baselines?* — with a clearly stated yes/no/partial.
4. `docs/METHODOLOGY.md` documents the final indicator set, weights, evidence, and limitations — honest enough that a skeptic could re-run it.

Phase B (tool) is done when:
5. *(Reframed 2026-07-10 after Phase A findings, owner-approved.)* The index is a **Split Likelihood Index**: a calibrated 0–100 likelihood that the stock executes a forward split within the next 12 months — with momentum context reported separately and **no expected-return claims**.
6. **Historical point-in-time validation passes:** a model trained only on ≤2018 data, evaluated on 2019+ quarters, shows strong lift (top-decile scores capture a large multiple of chance-rate splitters) and scores known holdout splits (e.g., AAPL 2020, NVDA 2021/2024, TSLA 2020/2022) highly at 6/3/1 months before execution using only data knowable then. Results published in docs/research/.
7. `split-signal score <TICKERS...>` returns, in under ~30s per ticker (cold cache), the likelihood index with per-component breakdown and data-quality flags.
8. Scores are reproducible from cached data; the tool refuses (with a clear message) rather than silently scoring a ticker with insufficient history.
9. Test suite green; ruff clean.

## Open Questions

1. **Split announcement dates** — yfinance provides execution dates only. Announcement-date recovery (press releases / EDGAR 8-Ks) is more work; do we need announcement-level precision in v1, or is execution-date-anchored analysis acceptable to start? (Proposed: start with execution dates, flag as a known limitation.)
2. **Paid data gate** — revisit after first `DATA_QUALITY.md` report quantifies what free sources actually miss.
3. **Rebalancing cadence for the index** — score-on-demand only, or periodic re-scoring of a watchlist (could later feed Ticker Sentinel)?
4. **Historical S&P 500 membership** — free constituent-history sources are patchy; fallback is "current members + all splitters," which biases toward survivors. Quantify the impact in Phase A.
