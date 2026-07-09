# Implementation Plan: Split-Signal

Source of truth: [SPEC.md](../SPEC.md). This plan covers Phase A (research) end-to-end and Phase B (tool) at milestone level; Phase B tasks get refined after the Phase A methodology gate, since the scoring formula depends on research results.

## Components & dependency order

```
A0 Scaffolding
 └─ A1 Universe construction ──────────────┐
     └─ A2 Price ingestion + caching ───┐  │
         ├─ A3 Split-event catalog      │  │   (A3, A4 parallel after A2)
         └─ A4 Fundamentals (EDGAR)     │  │
             └─ A5 Feature engineering ─┴──┘
                 ├─ A6 Event study (pre-split profiles vs. controls)
                 └─ A7 Backtest (forward returns, train/holdout, baselines)
                     └─ A8 METHODOLOGY.md + data-quality decision gate
                         └─ [HUMAN GATE: methodology sign-off]
                             └─ B1 Scoring engine → B2 CLI → B3 polish/ship
```

### A0 — Scaffolding
`uv`-managed package (`src/split_signal/`), pyproject with pandas/numpy/yfinance/matplotlib/jupyter/pytest/ruff, `.gitignore` (data/raw, data/processed, notebook outputs, .venv), CLI stub with `ingest`/`score`/`scan` subcommands, empty test suite green.

### A1 — Universe construction
Two ticker sets, merged:
1. **S&P 500**: current constituents (Wikipedia table — free, permissively licensed) plus best-effort historical membership from free GitHub datasets; where history is unavailable, log the survivorship gap in DATA_QUALITY.md rather than pretending.
2. **Splitters**: official NASDAQ Trader symbol directories (nasdaqlisted.txt / otherlisted.txt — free, official) give the full active US-listed universe; split history per ticker comes from yfinance in A3. Delisted splitters we can't see get quantified as a known gap.

Output: `data/processed/universe.parquet` (ticker, name, exchange, source flags).

### A2 — Price ingestion + caching
Daily OHLCV + adjusted close, max history, via yfinance with polite throttling; one parquet per ticker under `data/raw/prices/`; cache-first and resumable (re-run skips completed tickers); Stooq CSV fallback for tickers yfinance fails on. Writes a coverage report (per-ticker start date, gap days, failures) → DATA_QUALITY.md. This is the long-running step (potentially ~6–10k tickers for the splitter scan; run in background, possibly overnight).

**Scope control:** full-universe scan is only needed once to *find* splitters; full price history is then kept for (S&P 500 ∪ splitters), and non-splitting non-S&P tickers are dropped to keep the working set tractable.

### A3 — Split-event catalog
Extract split events (date, ratio) from yfinance actions for the working set; classify forward vs. reverse; handle multi-split tickers; sanity-check ratios against price discontinuities (a 4:1 split should show a ~75% raw-price drop on the ex-date). Output: `data/processed/splits.parquet` + counts by year/exchange in DATA_QUALITY.md. Execution-date anchored (announcement dates deferred per spec Open Question 1).

### A4 — Fundamentals (SEC EDGAR)
`companyfacts` XBRL API: revenue, EPS, net income, shares outstanding, with **filing dates** (the point-in-time anchor — a Q4 number is only "known" as of its filing date). CIK↔ticker mapping from SEC's public file. Cache raw JSON per company; normalize to `data/processed/fundamentals.parquet`.

### A5 — Feature engineering
Point-in-time-safe feature functions in `src/split_signal/features/`: trailing 1y/2y/3y total return, share-price level, distance from all-time high, revenue/EPS growth (filing-date lagged), market-cap trajectory, volatility, prior-split count, sector. Every function takes an `as_of` date and hard-fails on post-`as_of` data. **Fully unit-tested against fixtures — this is the correctness core.**

### A6 — Event study
For each forward split: features `as_of` ~90 days pre-execution; matched controls (same sector, similar market cap, same date, no split within ±2y). Compare distributions; identify which features actually separate splitters from controls. Notebook-driven, promoted logic in `src/`.

### A7 — Backtest
The money question: on train years (2006–2018), define "split-profile" portfolios from A6's discriminating features; measure 1y/3y/5y forward returns vs. SPY and vs. a momentum-only baseline; validate on holdout (2019–2025). Also measure post-split-execution drift directly. Report hit rates, excess returns, and drawdowns — honestly, including a negative result.

### A8 — Methodology synthesis + gates
Write `docs/METHODOLOGY.md` (indicator set, weights, evidence, limitations). Review DATA_QUALITY.md totals → paid-data decision gate. **Human sign-off required before Phase B.**

### B1–B3 — Tool (refined post-gate)
B1: scoring engine encoding the validated formula (0–100, component breakdown, data-sufficiency checks). B2: `score`/`scan` CLI with on-demand ingestion for unseen tickers, quality flags, disclaimer. B3: test/docs polish, README.

## Parallelism

- A3 and A4 run in parallel once A2's cache exists.
- A6 and A7 share A5's features; A6 informs A7's portfolio definitions, so mostly sequential.
- Notebook exploration can overlap with the next module's scaffolding.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| yfinance rate-limiting / breakage on a ~10k-ticker scan | throttle + resumable cache; Stooq fallback; scan runs in background over hours, not in-session |
| Survivorship bias (delisted splitters invisible) | quantify the gap (splits/year should be roughly stable — a droop in early years reveals missing names); state impact in METHODOLOGY.md; paid-data gate if it undermines conclusions |
| Lookahead bias | `as_of` discipline enforced in code + dedicated tests; fundamentals anchored to filing dates |
| Execution-date vs. announcement-date anchoring | 90-day pre-execution feature window largely predates typical announcement lead (~1–3 months); documented limitation; revisit if drift analysis needs precision |
| Free fundamentals gaps (pre-2009 XBRL is thin) | fundamentals features apply where available; price-based features carry earlier years; coverage logged |
| Curve-fitting | strict train/holdout split; small indicator count; baselines required |

## Verification checkpoints

1. **After A2:** coverage report reviewed — % of universe with ≥15y history.
2. **After A3:** split counts/year pass the smell test vs. known history (e.g., visible split waves in the 2010s–2020s; AAPL 2014/2020, NVDA 2021/2024, TSLA 2020/2022 present).
3. **After A5:** feature test suite green, incl. lookahead-guard tests.
4. **After A8:** human methodology gate.
5. **After B2:** `score AAPL NVDA COST` end-to-end on a cold cache, reproducible on warm cache.
