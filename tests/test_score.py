"""score_ticker backend: cache use, refusals, formatting (no network)."""

import numpy as np
import pandas as pd
import pytest

from split_signal.scoring.likelihood import REQUIRED_FEATURES, LikelihoodArtifact
from split_signal.scoring.model import LogisticModel
from split_signal.scoring.score import ScoreRefusal, format_score, score_ticker

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


def _cache_prices(tmp_path, ticker: str, periods: int = 1200) -> None:
    dates = pd.date_range(end="2020-08-01", periods=periods, freq="D")
    df = pd.DataFrame({"date": dates, "close": np.linspace(50.0, 150.0, periods)})
    df["adj_close"] = df["close"]
    df["open"] = df["high"] = df["low"] = df["close"]
    df["volume"] = 1_000_000
    df["dividends"] = 0.0
    df["split_ratio"] = 0.0
    if periods > 200:
        df.loc[df.index[-200], "split_ratio"] = 2.0
    df["source"] = "test"
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


def test_format_mentions_momentum_separately(tmp_path, artifact) -> None:
    _cache_prices(tmp_path, "ACME")
    score = score_ticker(tmp_path, "ACME", artifact=artifact, max_age_days=NEVER_STALE)
    text = format_score(score)
    assert "Split Likelihood Index" in text
    assert "momentum context" in text
    assert "NOT split-alpha" in text
