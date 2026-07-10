# Data Quality Log

Running log of coverage, gaps, and known limitations per SPEC.md's free-data
decision gate. Every ingestion run appends a dated section below.

## Standing limitations (free-data tier)

1. **Survivorship bias (universe).** The universe is built from *currently
   listed* symbols (NASDAQ Trader directories) + *current* S&P 500 members.
   Companies that split and were later delisted/acquired (e.g., acquired
   post-split) are invisible. Detection heuristic: forward-split counts per
   year should be roughly comparable across the study window — a droop in
   early years relative to known market history indicates missing names.
   Impact is quantified in the event-study phase and reported in
   METHODOLOGY.md.
2. **Execution dates, not announcement dates (splits).** yfinance provides
   split execution dates only. Feature windows are anchored ≥90 days before
   execution to largely predate typical announcement lead times (~1–3
   months). Revisit if post-announcement drift needs precise measurement.
3. **Pre-2009 fundamentals are thin.** SEC XBRL companyfacts coverage starts
   ~2009. Earlier study years lean on price-based features; fundamental
   feature coverage per year is logged by the ingestion runs below.
4. **yfinance Close is split-adjusted** (verified live 2026-07-09: implied
   ex-date ratios ~1.0 on AAPL/NVDA/TSLA/GE/BRK-B, even with
   `auto_adjust=False`; only dividends distinguish Close from Adj Close).
   True as-traded share prices are reconstructed via
   `splits.unadjusted_close` (close × product of later split ratios).
   Ratio plausibility on adjusted series: implied ratio should be ~1.0;
   large deviations flag bogus recorded splits. Bogus ratios below ~1.35
   are indistinguishable from market noise — accepted limitation.
5. **Historical S&P 500 membership** is not reliably available free; the
   S&P flag reflects *current* membership. Backtests therefore treat the
   S&P flag as descriptive metadata, not a point-in-time selection filter.

## Ingestion runs

(appended automatically by `split-signal ingest`)

## 2026-07-09 23:13 UTC — Price ingestion run

- universe symbols: 5628 (S&P 500 members: 503)
- prices fetched this run: 5608, already cached: 5, failed: 15
- coverage: 5613/5628 cached, 2557 with >=15y history, 4205 with >=5y, median 12.5y
- failure sample: AESP (yfinance: empty price frame from yfinance; stooq: 404 Client); ALPX (yfinance: empty price frame from yfinance; stooq: 404 Client); BAC-L (yfinance: empty price frame from yfinance; stooq: 404 Client); EPR-E (yfinance: empty price frame from yfinance; stooq: 404 Client); GAB-H (yfinance: empty price frame from yfinance; stooq: 404 Client); GS-D (yfinance: empty price frame from yfinance; stooq: 404 Client); MBGL (yfinance: empty price frame from yfinance; stooq: 404 Client); MER-K (yfinance: empty price frame from yfinance; stooq: 404 Client); MFP (yfinance: empty price frame from yfinance; stooq: 404 Client); MS-A (yfinance: empty price frame from yfinance; stooq: 404 Client)

## 2026-07-10 00:57 UTC — Split catalog build

- split events: 7316 total (4924 forward, 2392 reverse)
- implausible ratios flagged: 349
- forward splits per year since 2006: {2006: 177, 2007: 131, 2008: 54, 2009: 47, 2010: 48, 2011: 63, 2012: 62, 2013: 89, 2014: 106, 2015: 61, 2016: 54, 2017: 64, 2018: 55, 2019: 34, 2020: 42, 2021: 56, 2022: 51, 2023: 46, 2024: 62, 2025: 69, 2026: 34}
- working set (S&P 500 union 2006+ forward splitters): 1132 tickers
