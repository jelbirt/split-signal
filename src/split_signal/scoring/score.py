"""Score tickers with the Split Likelihood Index (CLI backend).

Cache-first: unseen tickers are fetched on demand; stale caches (older
than max_age_days) are refreshed. A ticker that cannot be scored raises
ScoreRefusal with the reason — the CLI surfaces it instead of printing
a fabricated number.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from split_signal.data.prices import (
    DEFAULT_FETCHERS,
    load_prices,
    price_cache_path,
)
from split_signal.data.splits import extract_split_events
from split_signal.scoring.likelihood import (
    LikelihoodArtifact,
    compute_scoring_features,
    score_features,
)


class ScoreRefusal(ValueError):
    """Raised when a ticker cannot be scored honestly."""


@dataclass(frozen=True)
class TickerScore:
    ticker: str
    as_of: pd.Timestamp
    index: int
    probability: float
    components: dict[str, float]
    ret_1y: float | None  # momentum context — reported separately, not part of the pitch
    data_start: pd.Timestamp
    data_end: pd.Timestamp
    source: str


def ensure_fresh_prices(
    data_dir: str | Path, ticker: str, max_age_days: int = 7
) -> pd.DataFrame:
    cache = price_cache_path(data_dir, ticker)
    if cache.exists():
        prices = load_prices(data_dir, ticker)
        age = pd.Timestamp.now().normalize() - prices["date"].max()
        if age.days <= max_age_days:
            return prices
    errors: list[str] = []
    for name, fetch in DEFAULT_FETCHERS:
        try:
            prices = fetch(ticker)
        except Exception as exc:  # noqa: BLE001 — collected into the refusal
            errors.append(f"{name}: {exc}")
            continue
        cache.parent.mkdir(parents=True, exist_ok=True)
        prices.to_parquet(cache, index=False)
        return prices
    raise ScoreRefusal(f"no price data for {ticker} ({'; '.join(errors)})")


def score_ticker(
    data_dir: str | Path,
    ticker: str,
    artifact: LikelihoodArtifact | None = None,
    as_of: pd.Timestamp | None = None,
    max_age_days: int = 7,
) -> TickerScore:
    artifact = artifact or LikelihoodArtifact.load()
    prices = ensure_fresh_prices(data_dir, ticker, max_age_days=max_age_days)
    if as_of is None:
        as_of = prices["date"].max()  # last knowable bar

    catalog = extract_split_events(prices, ticker)
    features = compute_scoring_features(prices, catalog, ticker, as_of)
    try:
        result = score_features(features, artifact)
    except ValueError as exc:
        raise ScoreRefusal(f"{ticker}: cannot score honestly — {exc}") from exc

    return TickerScore(
        ticker=ticker,
        as_of=as_of,
        index=result["index"],
        probability=result["probability"],
        components=result["components"],
        ret_1y=features.get("ret_1y"),
        data_start=prices["date"].min(),
        data_end=prices["date"].max(),
        source=str(prices["source"].iloc[-1]),
    )


def format_score(score: TickerScore) -> str:
    top = sorted(score.components.items(), key=lambda kv: -abs(kv[1]))[:4]
    components = " | ".join(f"{name} {value:+.2f}" for name, value in top)
    momentum = (
        f"{score.ret_1y:+.1%}" if score.ret_1y is not None else "n/a"
    )
    return "\n".join(
        [
            f"{score.ticker} — Split Likelihood Index: {score.index}/100 "
            f"(≈{score.probability:.1%} chance of a forward split within 12m)",
            f"  momentum context (separate; NOT split-alpha): 1y return {momentum}",
            f"  top drivers (log-odds): {components}",
            f"  data: {score.data_start.date()} → {score.data_end.date()} "
            f"({score.source}), as-of {score.as_of.date()}",
        ]
    )
