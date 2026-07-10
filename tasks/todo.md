# Task List: Split-Signal — Phase A

Per [plan.md](plan.md). One task per focused session; each ≤ ~5 files. Phase B tasks get written after the A8 methodology gate.

- [x] **A0. Scaffold project**
  - Acceptance: `uv sync` works; `uv run split-signal --help` shows ingest/score/scan stubs; `uv run pytest` and `uv run ruff check .` pass on empty suite; data dirs gitignored.
  - Verify: run all four commands.
  - Files: pyproject.toml, .gitignore, src/split_signal/{__init__,cli}.py, tests/test_cli.py

- [x] **A1. Build universe** *(2026-07-09: 5,628 symbols, 503 S&P members)*
  - Acceptance: `universe.parquet` with S&P 500 current members + full active US-listed symbol directory, source-flagged; survivorship gap noted in docs/DATA_QUALITY.md.
  - Verify: unit tests on parsers (fixtures); spot-check ~500 S&P rows, ~8–11k total symbols.
  - Files: src/split_signal/data/universe.py, tests/test_universe.py, data/fixtures/*, docs/DATA_QUALITY.md

- [x] **A2. Price ingestion (cache-first, resumable)**
  - Acceptance: `split-signal ingest` pulls daily adjusted OHLCV per ticker to data/raw/prices/, skips already-cached tickers, throttles, logs failures; coverage report appended to DATA_QUALITY.md; Stooq fallback wired.
  - Verify: fixture-replay unit tests; live smoke on ~20 tickers; then full background run.
  - Files: src/split_signal/data/{prices,stooq}.py, src/split_signal/data/quality.py, tests/test_prices.py

- [x] **A2b. Full-universe ingestion run + working-set reduction** *(2026-07-09: 5,613/5,628 cached, 2,557 with >=15y)*
  - Acceptance: background run complete; working set = S&P 500 ∪ splitters retained; coverage stats (≥15y history %) reviewed. ← checkpoint 1
  - Verify: DATA_QUALITY.md numbers reviewed with owner.
  - Files: data/* (generated), docs/DATA_QUALITY.md

- [x] **A3. Split-event catalog** *(2026-07-09: 7,316 events, 4,924 forward; checkpoint 2 passed)*
  - Acceptance: splits.parquet (ticker, date, ratio, forward/reverse) for working set; ratio sanity-check vs. ex-date price discontinuity; per-year counts in DATA_QUALITY.md; AAPL/NVDA/TSLA known splits all present. ← checkpoint 2
  - Verify: unit tests incl. multi-split + reverse-split fixtures; known-splits assertion list.
  - Files: src/split_signal/data/splits.py, tests/test_splits.py, docs/DATA_QUALITY.md

- [x] **A4. Fundamentals via SEC EDGAR** *(code done; working-set ingestion run follows A2b)*
  - Acceptance: companyfacts cached per CIK; fundamentals.parquet with revenue/EPS/net income/shares + filing dates; CIK↔ticker map; coverage-by-year logged.
  - Verify: unit tests on XBRL normalization fixtures; spot-check AAPL revenue vs. known figures.
  - Files: src/split_signal/data/{edgar,cik}.py, tests/test_edgar.py

- [x] **A5. Point-in-time feature library**
  - Acceptance: features (trailing returns, price level, ATH distance, growth rates, mcap trajectory, volatility, prior splits, sector) each take `as_of` and raise on post-`as_of` data; lookahead-guard tests pass. ← checkpoint 3
  - Verify: `uv run pytest tests/test_features.py` — known-answer + guard tests.
  - Files: src/split_signal/features/{price,fundamental,structural}.py, tests/test_features.py

- [x] **A6. Event study** *(2026-07-10: 1,371 events; ATH-proximity d=0.54, serial-splitter d=0.38, momentum d~0.2, fundamentals ~0)*
  - Acceptance: notebook + promoted module comparing pre-split feature distributions vs. matched controls; discriminating features identified with effect sizes.
  - Verify: control-matching unit tests; notebook re-runs clean top-to-bottom.
  - Files: notebooks/06_event_study.ipynb, src/split_signal/backtest/controls.py, tests/test_controls.py

- [x] **A7. Forward-return backtest** *(2026-07-10: splitters no alpha post-split; profile adds nothing over momentum)*
  - Acceptance: train (2006–2018) / holdout (2019–2025) results for split-profile portfolios: 1y/3y/5y returns vs. SPY and momentum baseline; post-split drift measured; honest verdict stated.
  - Verify: backtest-mechanics unit tests (no-lookahead portfolio formation); notebook re-runs clean.
  - Files: notebooks/07_backtest.ipynb, src/split_signal/backtest/{engine,baselines}.py, tests/test_backtest.py

- [x] **A8. Methodology synthesis + gates** *(2026-07-10: METHODOLOGY.md written; owner APPROVED reframe to Split Likelihood Index)*
  - Acceptance: docs/METHODOLOGY.md complete (indicators, weights, evidence, limitations); paid-data recommendation made from DATA_QUALITY.md totals; owner sign-off requested. ← checkpoint 4, HUMAN GATE
  - Verify: owner review.
  - Files: docs/METHODOLOGY.md, tasks/todo.md (Phase B tasks added after gate)

# Phase B — Split Likelihood Index (owner-approved 2026-07-10)

- [x] **B1. Likelihood model** *(2026-07-10: train AUC 0.719)*
  - Acceptance: logistic model (plain numpy — no heavy deps) on the quarterly panel; label = forward split within next 12 months; features from Q1 findings (ATH proximity, prior splits count/recency, momentum, volatility, price level, liquidity); trained on ≤2018 quarters only; calibrated probability → 0–100 index; model artifact + coefficients saved and versioned.
  - Verify: unit tests (training convergence on synthetic data, calibration monotonicity, as_of discipline via panel reuse); coefficients sane (ATH proximity positive, etc.).
  - Files: src/split_signal/scoring/{model,likelihood}.py, tests/test_scoring.py, notebooks/09_likelihood_model.py

- [x] **B2. Historical point-in-time validation** *(2026-07-10: PASSED — AUC 0.740, lift 3.8x, all named events >=90th pct)*
  - Acceptance: 2019+ holdout evaluation: lift chart (top-decile capture vs chance), precision@K, calibration table; named-event test — AAPL 2020, NVDA 2021/2024, TSLA 2020/2022, GOOGL/AMZN 2022 scored at 6/3/1 months pre-execution with only then-knowable data, reported vs. matched non-splitter percentiles; honest write-up to docs/research/likelihood_validation.md. ← HUMAN CHECKPOINT: owner reviews validation before CLI ships
  - Verify: notebook re-runs clean; validation doc reviewed.
  - Files: notebooks/10_validation.py, docs/research/likelihood_validation.md

- [x] **B3. Scoring CLI** *(2026-07-10: live-verified on AAPL/NVDA/COST/BRK-B)*
  - Acceptance: `split-signal score TICKERS...` → likelihood 0–100, component breakdown, separately labeled momentum context, data-sufficiency flags, disclaimer; on-demand cache refresh for unseen tickers; `scan --watchlist` works; refuses insufficient-history tickers with a clear message.
  - Verify: CLI tests (fixtures); live smoke on 5 tickers incl. one thin-history name.
  - Files: src/split_signal/scoring/score.py, src/split_signal/cli.py, tests/test_cli.py

- [x] **B4. Ship polish** *(2026-07-10)*
  - Acceptance: README (what it is, what it is NOT — no alpha claims), METHODOLOGY.md updated with B2 results; full suite + lint green; SPEC.md success criteria checked off.
  - Verify: fresh-clone dry run of README instructions.
  - Files: README.md, docs/METHODOLOGY.md, SPEC.md
