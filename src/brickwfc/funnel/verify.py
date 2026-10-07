"""Hard checks with signed margins: margin >= 0 passes, and its size says how comfortably."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from brickwfc.funnel.features import region_sizes


@dataclass(frozen=True)
class CheckResult:
    name: str
    margin: float

    @property
    def passed(self) -> bool:
        return self.margin >= 0


def land_connectivity(land: np.ndarray, min_fraction: float = 0.9) -> CheckResult:
    """Most land should form one connected region.

    margin = (largest land region / total land) - min_fraction. With ``min_fraction=1`` this is
    the strict "all land is one region" check. A grid with no land fails with margin -min_fraction.
    """
    sizes = region_sizes(land)
    largest_share = sizes.max() / sizes.sum() if sizes.size else 0.0
    return CheckResult("land_connectivity", float(largest_share - min_fraction))


def land_fraction(land: np.ndarray, low: float = 0.3, high: float = 0.9) -> CheckResult:
    """Land should cover between ``low`` and ``high`` of the grid. margin = distance inside the band."""
    fraction = float(land.mean())
    return CheckResult("land_fraction", min(fraction - low, high - fraction))


def verify(land: np.ndarray, min_connected: float = 0.9, land_band: tuple[float, float] = (0.3, 0.9)) -> list[CheckResult]:
    return [land_connectivity(land, min_connected), land_fraction(land, *land_band)]
