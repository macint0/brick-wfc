"""Diversity of a set of designs (M13): mean pairwise distance and the effective number of distinct designs.

Both work on feature vectors (``alt.features.feature_vector`` for 3D builds, ``funnel.features`` in 2D).
Feature vectors are only comparable within one run (one inventory, one grid): their length and meaning
depend on both, so diversity is computed per run and never pooled across runs.

**Mean pairwise distance** is the mean L2 distance over all pairs: easy to read, but one far outlier raises
it as much as many moderately different designs do, and it does not count how many designs are distinct.

**Effective number of designs** is the similarity-sensitive diversity of order 1 of Leinster and Cobbold
(Ecology 2012), with every design weighted equally:

    D = exp(-(1/N) sum_i log((1/N) sum_j Z_ij))

where Z_ij in [0, 1] is the similarity of designs i and j (Z_ii = 1). With ``kernel="threshold"`` (the
default), Z_ij = 1 if their distance is below ``threshold`` and 0 otherwise: the same notion of "the same
design" that ``funnel.dedupe`` uses, so the dedupe threshold is the natural value. We use it rather than
the entropy of a soft clustering because it needs no clustering algorithm, number of clusters or seed, and
it reduces to what one expects: N designs that are all distinct give N, N identical ones give 1, and designs
that fall into well-separated groups (closer than the threshold within a group, farther between groups) give
the Hill number exp(H) of the group sizes, k for k equal groups. ``kernel="exp"`` uses Z_ij = exp(-d_ij /
threshold) instead, which changes smoothly with the features (no jump when a pair crosses the threshold) at
the price of a less literal reading.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

Kernel = Literal["threshold", "exp"]


def pairwise_distances(features: np.ndarray) -> np.ndarray:
    """(N, N) L2 distances between the rows of ``features`` (N, F)."""
    features = np.asarray(features, dtype=float)
    squared = (features**2).sum(axis=1)
    d2 = squared[:, None] + squared[None, :] - 2 * features @ features.T
    d = np.sqrt(np.maximum(d2, 0.0))
    np.fill_diagonal(d, 0.0)
    return d


def mean_pairwise_distance(features: np.ndarray) -> float:
    """Mean L2 distance over all pairs of rows; 0 for fewer than two designs."""
    n = len(features)
    if n < 2:
        return 0.0
    return float(pairwise_distances(features)[np.triu_indices(n, 1)].mean())


def similarity(distances: np.ndarray, threshold: float, kernel: Kernel = "threshold") -> np.ndarray:
    if threshold <= 0:
        raise ValueError(f"threshold must be > 0, got {threshold}")
    if kernel == "threshold":
        z = (distances < threshold).astype(float)
    elif kernel == "exp":
        z = np.exp(-distances / threshold)
    else:
        raise ValueError(f"unknown kernel {kernel!r}")
    np.fill_diagonal(z, 1.0)
    return z


def effective_number(features: np.ndarray, threshold: float, kernel: Kernel = "threshold") -> float:
    """Leinster-Cobbold diversity of order 1 (see the module docstring); 0 for no designs."""
    n = len(features)
    if n == 0:
        return 0.0
    z = similarity(pairwise_distances(features), threshold, kernel)
    return float(np.exp(-np.log(z.mean(axis=1)).mean()))


@dataclass(frozen=True)
class Diversity:
    designs: int
    mean_distance: float
    effective: float  # effective number of distinct designs
    effective_share: float  # effective / designs (1 = all distinct)


def diversity(features: np.ndarray, threshold: float, kernel: Kernel = "threshold") -> Diversity:
    n = len(features)
    effective = effective_number(features, threshold, kernel)
    return Diversity(n, mean_pairwise_distance(features), effective, effective / n if n else 0.0)
