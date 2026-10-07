"""Near-duplicate removal in feature space."""

from __future__ import annotations

import numpy as np


def dedupe(features: np.ndarray, threshold: float) -> list[int]:
    """Greedy, in input order: keep a design unless it lies within ``threshold`` (L2) of one already kept.

    ``features`` has shape (N, F). Returns the kept row indices.
    """
    kept: list[int] = []
    for i, f in enumerate(features):
        if not kept or np.linalg.norm(features[kept] - f, axis=1).min() >= threshold:
            kept.append(i)
    return kept
