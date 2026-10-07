"""Judges score designs. ``Judge`` is the plug-in point for a later LLM or learned judge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from brickwfc.funnel.features import perimeter


@dataclass(frozen=True)
class Candidate:
    """A design that reached the judge, with everything a judge might look at."""

    seed: int
    grid: np.ndarray  # (H, W) tile ids
    land: np.ndarray  # (H, W) bool
    features: np.ndarray  # see features.feature_vector


class Judge(Protocol):
    def score(self, candidate: Candidate) -> float:
        """Higher is better."""
        ...


@dataclass(frozen=True)
class HeuristicJudge:
    """Prefers compact landmasses covering about ``target_land`` of the map. Scores are in [0, 1].

    - compactness: 4*sqrt(land) / perimeter, i.e. 1 for a single square island, clipped to 1;
      speckled noise has a long coastline and scores near 0.
    - balance: 1 at exactly ``target_land`` land, falling linearly to 0 at all-land or all-water.
    """

    target_land: float = 0.5
    compactness_weight: float = 0.5

    def score(self, candidate: Candidate) -> float:
        land_cells = int(candidate.land.sum())
        coast = perimeter(candidate.land)
        compactness = 1.0 if coast == 0 else min(1.0, 4 * np.sqrt(land_cells) / coast)
        fraction = land_cells / candidate.land.size
        balance = 1 - abs(fraction - self.target_land) / max(self.target_land, 1 - self.target_land)
        w = self.compactness_weight
        return float(w * compactness + (1 - w) * balance)
