"""Diversity-aware top-k selection."""

from __future__ import annotations

import numpy as np


def select(scores: np.ndarray, features: np.ndarray, k: int, diversity: float = 1.0) -> list[int]:
    """Greedily pick up to ``k`` indices maximizing ``score + diversity * min_distance_to_selected``.

    The first pick is simply the best score. Ties go to the lower index, so selection is deterministic.
    """
    selected: list[int] = []
    min_dist = np.full(len(scores), np.inf)
    available = np.ones(len(scores), dtype=bool)
    for _ in range(min(k, len(scores))):
        bonus = diversity * np.where(np.isinf(min_dist), 0.0, min_dist)
        objective = np.where(available, scores + bonus, -np.inf)
        best = int(np.argmax(objective))
        selected.append(best)
        available[best] = False
        min_dist = np.minimum(min_dist, np.linalg.norm(features - features[best], axis=1))
    return selected
