"""Likelihood model: logistic fit, calibration, artifact roundtrip, scoring."""

import numpy as np
import pytest

from split_signal.scoring.likelihood import (
    REQUIRED_FEATURES,
    LikelihoodArtifact,
    score_features,
)
from split_signal.scoring.model import LogisticModel, rank_auc


def _synthetic(n: int = 4000, seed: int = 3):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 3))
    logits = 1.6 * X[:, 0] - 0.8 * X[:, 1] + 0.0 * X[:, 2] - 2.0
    y = (rng.uniform(size=n) < 1 / (1 + np.exp(-logits))).astype(float)
    return X, y


class TestLogisticModel:
    def test_recovers_signs_and_separates(self) -> None:
        X, y = _synthetic()
        model = LogisticModel.fit(X, y, feature_names=["a", "b", "c"])
        assert model.weights[0] > 0.5
        assert model.weights[1] < -0.2
        assert abs(model.weights[2]) < 0.15
        assert rank_auc(model.predict_proba(X), y) > 0.75

    def test_predict_monotone_in_positive_feature(self) -> None:
        X, y = _synthetic()
        model = LogisticModel.fit(X, y, feature_names=["a", "b", "c"])
        lo = model.predict_proba(np.array([[-2.0, 0.0, 0.0]]))[0]
        hi = model.predict_proba(np.array([[2.0, 0.0, 0.0]]))[0]
        assert hi > lo

    def test_serialization_roundtrip(self) -> None:
        X, y = _synthetic()
        model = LogisticModel.fit(X, y, feature_names=["a", "b", "c"])
        clone = LogisticModel.from_dict(model.to_dict())
        np.testing.assert_allclose(
            model.predict_proba(X[:50]), clone.predict_proba(X[:50])
        )


class TestRankAuc:
    def test_perfect_and_random(self) -> None:
        labels = np.array([0, 0, 1, 1], dtype=float)
        assert rank_auc(np.array([0.1, 0.2, 0.8, 0.9]), labels) == pytest.approx(1.0)
        assert rank_auc(np.array([0.9, 0.8, 0.2, 0.1]), labels) == pytest.approx(0.0)
        assert rank_auc(np.array([0.5, 0.5, 0.5, 0.5]), labels) == pytest.approx(0.5)

    def test_ties_match_reference_implementation(self) -> None:
        def reference_auc(scores: np.ndarray, labels: np.ndarray) -> float:
            n_pos = labels.sum()
            n_neg = len(labels) - n_pos
            order = scores.argsort(kind="mergesort")
            ranks = np.empty(len(scores))
            ranks[order] = np.arange(1, len(scores) + 1)
            for value in np.unique(scores):
                mask = scores == value
                if mask.sum() > 1:
                    ranks[mask] = ranks[mask].mean()
            return float(
                (ranks[labels == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
            )

        rng = np.random.default_rng(11)
        # heavy ties (few distinct values) alongside continuous scores
        tied = rng.integers(0, 10, size=2000).astype(float)
        continuous = rng.normal(size=2000)
        labels = (rng.uniform(size=2000) < 0.3).astype(float)
        for scores in (tied, continuous):
            assert rank_auc(scores, labels) == reference_auc(scores, labels)


class TestArtifactScoring:
    @pytest.fixture
    def artifact(self) -> LikelihoodArtifact:
        X, y = _synthetic()
        names = REQUIRED_FEATURES[:3]
        model = LogisticModel.fit(X, y, feature_names=list(names))
        probs = model.predict_proba(X)
        return LikelihoodArtifact(
            version="test",
            trained_through="2017-12-31",
            model=model,
            prob_quantiles=np.quantile(probs, np.linspace(0, 1, 101)).tolist(),
        )

    def test_score_returns_index_probability_components(self, artifact) -> None:
        features = dict.fromkeys(artifact.model.feature_names, 0.5)
        result = score_features(features, artifact)
        assert 0 <= result["index"] <= 100
        assert 0.0 < result["probability"] < 1.0
        assert set(result["components"]) == set(artifact.model.feature_names)

    def test_higher_positive_feature_higher_index(self, artifact) -> None:
        name = artifact.model.feature_names[0]  # positive-weight feature
        base = dict.fromkeys(artifact.model.feature_names, 0.0)
        low = score_features({**base, name: -2.0}, artifact)
        high = score_features({**base, name: 2.0}, artifact)
        assert high["index"] >= low["index"]
        assert high["probability"] > low["probability"]

    def test_missing_required_feature_rejected(self, artifact) -> None:
        features = dict.fromkeys(artifact.model.feature_names, 0.5)
        features[artifact.model.feature_names[0]] = None
        with pytest.raises(ValueError, match="missing"):
            score_features(features, artifact)

    def test_nan_feature_rejected(self, artifact) -> None:
        # NaN must be treated as missing, not scored into a NaN probability
        # with a fabricated index of 100.
        features = dict.fromkeys(artifact.model.feature_names, 0.5)
        features[artifact.model.feature_names[0]] = float("nan")
        with pytest.raises(ValueError, match="missing"):
            score_features(features, artifact)

    def test_inf_feature_rejected(self, artifact) -> None:
        features = dict.fromkeys(artifact.model.feature_names, 0.5)
        features[artifact.model.feature_names[0]] = float("inf")
        with pytest.raises(ValueError, match="missing"):
            score_features(features, artifact)

    def test_artifact_json_roundtrip(self, artifact, tmp_path) -> None:
        path = tmp_path / "artifact.json"
        artifact.save(path)
        loaded = LikelihoodArtifact.load(path)
        features = dict.fromkeys(artifact.model.feature_names, 1.0)
        assert score_features(features, loaded) == score_features(features, artifact)
