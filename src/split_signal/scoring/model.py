"""Plain-numpy logistic regression (no heavy ML dependencies).

Features are standardized internally; weights are reported in
standardized units so per-feature log-odds contributions are comparable.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def rank_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """AUC via the rank-sum identity (ties get average rank)."""
    scores = np.asarray(scores, dtype=float)
    labels = np.asarray(labels, dtype=float)
    n_pos = labels.sum()
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = scores.argsort(kind="mergesort")
    sorted_scores = scores[order]
    # average ranks for ties, vectorized: each run of equal sorted values
    # spans 1-based ranks (start+1 .. end), whose mean is (start+end+1)/2.
    boundaries = np.flatnonzero(np.diff(sorted_scores)) + 1
    starts = np.concatenate(([0], boundaries))
    ends = np.concatenate((boundaries, [len(scores)]))
    ranks = np.empty(len(scores))
    ranks[order] = np.repeat((starts + ends + 1) / 2.0, ends - starts)
    return float((ranks[labels == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


@dataclass
class LogisticModel:
    feature_names: list[str]
    mu: np.ndarray
    sigma: np.ndarray
    weights: np.ndarray  # standardized-space coefficients
    bias: float

    @classmethod
    def fit(
        cls,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str],
        l2: float = 1e-3,
        lr: float = 0.5,
        iters: int = 4000,
    ) -> LogisticModel:
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        mu = X.mean(axis=0)
        sigma = X.std(axis=0)
        sigma[sigma == 0] = 1.0
        Z = (X - mu) / sigma

        weights = np.zeros(Z.shape[1])
        bias = 0.0
        n = len(y)
        for _ in range(iters):
            p = _sigmoid(Z @ weights + bias)
            error = p - y
            weights -= lr * (Z.T @ error / n + l2 * weights)
            bias -= lr * float(error.mean())
        return cls(feature_names=list(feature_names), mu=mu, sigma=sigma,
                   weights=weights, bias=bias)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        Z = (np.asarray(X, dtype=float) - self.mu) / self.sigma
        return _sigmoid(Z @ self.weights + self.bias)

    def contributions(self, x: np.ndarray) -> dict[str, float]:
        """Per-feature log-odds contribution for a single observation."""
        z = (np.asarray(x, dtype=float) - self.mu) / self.sigma
        return {
            name: float(weight * value)
            for name, weight, value in zip(self.feature_names, self.weights, z, strict=True)
        }

    def to_dict(self) -> dict:
        return {
            "feature_names": self.feature_names,
            "mu": self.mu.tolist(),
            "sigma": self.sigma.tolist(),
            "weights": self.weights.tolist(),
            "bias": self.bias,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> LogisticModel:
        return cls(
            feature_names=list(payload["feature_names"]),
            mu=np.asarray(payload["mu"], dtype=float),
            sigma=np.asarray(payload["sigma"], dtype=float),
            weights=np.asarray(payload["weights"], dtype=float),
            bias=float(payload["bias"]),
        )
