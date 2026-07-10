"""Split Likelihood artifact and scoring.

The artifact bundles the trained logistic model with the reference
probability distribution, so a raw calibrated probability (splits are
rare — typical values are a few percent) maps onto an interpretable
0-100 percentile index: "index 92" = scores above 92% of ticker-quarters
in the reference panel.

Feature computation here must mirror the training panel exactly
(notebooks/09_likelihood_model.py builds both from the same functions).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from split_signal.backtest.controls import dollar_volume_size
from split_signal.features.base import InsufficientHistoryError
from split_signal.features.price import (
    annualized_volatility,
    ath_drawdown,
    trailing_return,
    true_price_level,
)
from split_signal.features.structural import prior_split_count, years_since_last_split

REQUIRED_FEATURES = [
    "ath_drawdown",
    "ret_1y",
    "log_price",
    "volatility",
    "log_size",
    "prior_splits",
    "recent_split",
]

RECENT_SPLIT_YEARS = 5.0
DEFAULT_ARTIFACT = Path(__file__).parent / "likelihood_v1.json"


@dataclass
class LikelihoodArtifact:
    version: str
    trained_through: str
    model: LogisticModel  # noqa: F821 — imported below to avoid cycle at type time
    prob_quantiles: list[float]

    def save(self, path: str | Path) -> None:
        payload = {
            "version": self.version,
            "trained_through": self.trained_through,
            "model": self.model.to_dict(),
            "prob_quantiles": self.prob_quantiles,
        }
        Path(path).write_text(json.dumps(payload, indent=1))

    @classmethod
    def load(cls, path: str | Path = DEFAULT_ARTIFACT) -> LikelihoodArtifact:
        from split_signal.scoring.model import LogisticModel

        payload = json.loads(Path(path).read_text())
        return cls(
            version=payload["version"],
            trained_through=payload["trained_through"],
            model=LogisticModel.from_dict(payload["model"]),
            prob_quantiles=list(payload["prob_quantiles"]),
        )


def compute_scoring_features(
    prices: pd.DataFrame,
    catalog: pd.DataFrame,
    ticker: str,
    as_of: pd.Timestamp,
) -> dict[str, float | None]:
    """The model's feature vector at as_of (point-in-time safe).

    Must stay in lockstep with the training panel construction.
    """

    def guarded(fn):
        try:
            return fn()
        except (InsufficientHistoryError, KeyError, IndexError):
            return None

    price = guarded(lambda: true_price_level(prices, as_of))
    size = dollar_volume_size(prices, as_of)
    since = years_since_last_split(catalog, ticker, as_of)
    return {
        "ath_drawdown": guarded(lambda: ath_drawdown(prices, as_of)),
        "ret_1y": guarded(lambda: trailing_return(prices, as_of, days=365)),
        "log_price": math.log(price) if price and price > 0 else None,
        "volatility": guarded(lambda: annualized_volatility(prices, as_of)),
        "log_size": math.log(size) if size and size > 0 and math.isfinite(size) else None,
        "prior_splits": float(min(prior_split_count(catalog, ticker, as_of), 4)),
        "recent_split": 1.0 if since is not None and since <= RECENT_SPLIT_YEARS else 0.0,
    }


def score_features(features: dict, artifact: LikelihoodArtifact) -> dict:
    """Score one feature dict -> {probability, index, components}.

    Raises ValueError when any model feature is missing (None) — the
    caller decides how to surface the refusal.
    """
    missing = [n for n in artifact.model.feature_names if features.get(n) is None]
    if missing:
        raise ValueError(f"missing features: {', '.join(missing)}")

    x = np.array([[float(features[n]) for n in artifact.model.feature_names]])
    probability = float(artifact.model.predict_proba(x)[0])
    index = int(np.searchsorted(artifact.prob_quantiles, probability, side="right"))
    return {
        "probability": probability,
        "index": max(0, min(100, index)),
        "components": artifact.model.contributions(x[0]),
    }
