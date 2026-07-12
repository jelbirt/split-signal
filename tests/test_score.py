"""score_ticker backend: cache use, refusals, formatting (no network)."""

import numpy as np
import pandas as pd
import pytest

from split_signal.data.prices import load_prices
from split_signal.scoring.likelihood import REQUIRED_FEATURES, LikelihoodArtifact
from split_signal.scoring.model import LogisticModel
from split_signal.scoring.score import (
    ScoreRefusal,
    ensure_fresh_prices,
    format_score,
    score_ticker,
)

NEVER_STALE = 10_000_000  # keep tests offline regardless of fixture dates


@pytest.fixture
def artifact() -> LikelihoodArtifact:
    rng = np.random.default_rng(11)
    X = rng.normal(size=(2000, len(REQUIRED_FEATURES)))
    y = (rng.uniform(size=2000) < 1 / (1 + np.exp(-(X[:, 0] - 2.5)))).astype(float)
    model = LogisticModel.fit(X, y, feature_names=list(REQUIRED_FEATURES))
    probs = model.predict_proba(X)
    return LikelihoodArtifact(
        version="test", trained_through="2017-12-31", model=model,
        prob_quantiles=np.quantile(probs, np.linspace(0, 1, 101)).tolist(),
    )


def _price_frame(periods: int, end: str | pd.Timestamp = "2020-08-01") -> pd.DataFrame:
    dates = pd.date_range(end=end, periods=periods, freq="D")
    df = pd.DataFrame({"date": dates, "close": np.linspace(50.0, 150.0, periods)})
    df["adj_close"] = df["close"]
    df["open"] = df["high"] = df["low"] = df["close"]
    df["volume"] = 1_000_000
    df["dividends"] = 0.0
    df["split_ratio"] = 0.0
    if periods > 200:
        df.loc[df.index[-200], "split_ratio"] = 2.0
    df["source"] = "test"
    return df


def _cache_prices(tmp_path, ticker: str, periods: int = 1200) -> None:
    df = _price_frame(periods)
    out = tmp_path / "raw" / "prices" / f"{ticker}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)


def test_scores_from_cache_without_network(tmp_path, artifact) -> None:
    _cache_prices(tmp_path, "ACME")
    score = score_ticker(tmp_path, "ACME", artifact=artifact, max_age_days=NEVER_STALE)
    assert 0 <= score.index <= 100
    assert 0.0 < score.probability < 1.0
    assert score.as_of == pd.Timestamp("2020-08-01")
    assert score.ticker == "ACME"


def test_insufficient_history_is_refused(tmp_path, artifact) -> None:
    _cache_prices(tmp_path, "NEWIPO", periods=90)
    with pytest.raises(ScoreRefusal, match="cannot score honestly"):
        score_ticker(tmp_path, "NEWIPO", artifact=artifact, max_age_days=NEVER_STALE)


def test_stale_cache_survives_truncated_fetch(tmp_path) -> None:
    """A stale long cache must not be clobbered by a valid-but-truncated fresh fetch."""
    _cache_prices(tmp_path, "ACME", periods=1200)  # ends 2020-08-01 → stale
    short = _price_frame(periods=30, end=pd.Timestamp.now().normalize())

    returned = ensure_fresh_prices(
        tmp_path, "ACME", max_age_days=0, fetchers=[("fake", lambda _t: short.copy())]
    )

    on_disk = load_prices(tmp_path, "ACME")
    assert len(on_disk) == 1200, "truncated fetch overwrote the cached history"
    assert on_disk["date"].max() == pd.Timestamp("2020-08-01")
    assert len(returned) == 1200  # the cached frame is what callers get back


def test_stale_cache_replaced_by_covering_fetch(tmp_path) -> None:
    _cache_prices(tmp_path, "ACME", periods=1200)  # ends 2020-08-01 → stale
    days_span = (pd.Timestamp.now().normalize() - pd.Timestamp("2020-08-01")).days
    full = _price_frame(periods=1200 + days_span, end=pd.Timestamp.now().normalize())

    returned = ensure_fresh_prices(
        tmp_path, "ACME", max_age_days=0, fetchers=[("fake", lambda _t: full.copy())]
    )

    assert len(returned) == len(full)
    assert len(load_prices(tmp_path, "ACME")) == len(full)


def test_stale_cache_returned_when_all_fetchers_fail(tmp_path) -> None:
    _cache_prices(tmp_path, "ACME", periods=1200)  # ends 2020-08-01 → stale

    def boom(_ticker: str) -> pd.DataFrame:
        raise ConnectionError("offline")

    returned = ensure_fresh_prices(tmp_path, "ACME", max_age_days=0, fetchers=[("fake", boom)])
    assert len(returned) == 1200
    assert len(load_prices(tmp_path, "ACME")) == 1200


def test_no_cache_fetch_is_written_and_returned(tmp_path) -> None:
    fresh = _price_frame(periods=300, end=pd.Timestamp.now().normalize())
    returned = ensure_fresh_prices(
        tmp_path, "ACME", max_age_days=0, fetchers=[("fake", lambda _t: fresh.copy())]
    )
    assert len(returned) == 300
    assert len(load_prices(tmp_path, "ACME")) == 300


def test_no_cache_and_all_fetchers_fail_refuses(tmp_path) -> None:
    def boom(_ticker: str) -> pd.DataFrame:
        raise ConnectionError("offline")

    with pytest.raises(ScoreRefusal, match="no price data"):
        ensure_fresh_prices(tmp_path, "ACME", max_age_days=0, fetchers=[("fake", boom)])


def test_format_mentions_momentum_separately(tmp_path, artifact) -> None:
    _cache_prices(tmp_path, "ACME")
    score = score_ticker(tmp_path, "ACME", artifact=artifact, max_age_days=NEVER_STALE)
    text = format_score(score)
    assert "Split Likelihood Index" in text
    assert "momentum context" in text
    assert "NOT split-alpha" in text
