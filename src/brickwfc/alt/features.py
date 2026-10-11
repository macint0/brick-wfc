"""Feature vectors of 3D builds for dedupe and diversity-aware selection.

Builds of one inventory that use (nearly) all of it have nearly the same part and color histograms, so
those alone barely tell builds apart; the per-layer fill and a coarse top-view height map describe the
overall form. Every entry is in [0, 1].

Completeness of a build against its target (M12b holes; reported, not part of the feature vector): the holes
(connected components, across faces, of target cells left empty: how many, and the largest), the surface
completeness (the filled share of the target cells with a face open to the outside; the faces on the ground
do not count, since a build stands on them) and the largest surface hole (the largest such component among the
empty exposed cells alone: what can be seen from outside; interior cells are invisible).

The bar a complete build meets (``Bar``, M12c; cf's working bar, 2026-10-10): by volume, fill >= 97%, no hole over
4 cells and >= 98% of the surface filled; by surface, only the surface share and the largest surface hole count.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy import ndimage

from brickwfc.bricks.parts import PlacedPart
from brickwfc.bricks.shapes import Mask, height_map_of, surface
from brickwfc.bricks.style import TYPE_INDEX, TYPES

HEIGHT_MAP_BLOCKS = 4  # the top view is pooled into at most 4 x 4 blocks


def occupancy(placed: Sequence[PlacedPart], shape: tuple[int, int, int]) -> np.ndarray:
    filled = np.zeros(shape, dtype=bool)
    for part in placed:
        for cell in part.cells():
            filled[cell] = True
    return filled


def height_map(filled: np.ndarray) -> np.ndarray:
    """(Z, X) height of each column's top filled cell (0 = empty column), as a share of the grid height."""
    return height_map_of(filled) / filled.shape[0]


def pooled(values: np.ndarray, blocks: int) -> np.ndarray:
    """Mean of ``values`` (Z, X) over a grid of at most ``blocks`` x ``blocks`` blocks, flattened."""
    rows = np.array_split(values, min(blocks, values.shape[0]), axis=0)
    return np.array([block.mean() for row in rows for block in np.array_split(row, min(blocks, row.shape[1]), axis=1)])


def feature_vector(placed: Sequence[PlacedPart], shape: tuple[int, int, int], colors: Sequence[str]) -> np.ndarray:
    """[per-layer fill (Y), part-type shares (len(TYPES)), color shares (len(colors)), pooled height map]."""
    filled = occupancy(placed, shape)
    layer_fill = filled.mean(axis=(1, 2))
    count = max(len(placed), 1)
    types = np.bincount([TYPE_INDEX[p.shape.part.name] for p in placed], minlength=len(TYPES)) / count
    color_index = {name: i for i, name in enumerate(colors)}
    color_shares = np.bincount([color_index[p.color.name] for p in placed], minlength=len(colors)) / count
    return np.concatenate([layer_fill, types, color_shares, pooled(height_map(filled), HEIGHT_MAP_BLOCKS)])


@dataclass(frozen=True)
class Completeness:
    holes: int  # connected components (across faces) of empty target cells
    largest_hole: int  # cells of the largest one (0: none)
    surface: float  # filled share of the target's exposed cells (1.0: the outside is complete)
    largest_surface_hole: int = 0  # cells of the largest component of empty exposed cells (0: none)


def exposed(mask: Mask) -> Mask:
    """The target cells with a face open to the outside (``shapes.surface``), not counting the faces on the
    ground: the target stands on a solid layer below the grid."""
    ground = np.ones((1, *mask.shape[1:]), dtype=bool)
    return surface(np.concatenate([ground, mask]))[1:]


def largest_component(cells: np.ndarray) -> int:
    """Cells of the largest connected component (across faces) of ``cells`` (0: none)."""
    labels, count = ndimage.label(cells)
    return int(np.bincount(labels.ravel())[1:].max()) if count else 0


def completeness(filled: np.ndarray, mask: Mask) -> Completeness:
    """How complete a build (``filled``, grid-shaped) is against its target ``mask``."""
    missing = mask & ~filled
    labels, count = ndimage.label(missing)
    largest = int(np.bincount(labels.ravel())[1:].max()) if count else 0
    outer = exposed(mask)
    share = float((filled & outer).sum() / outer.sum()) if outer.any() else 1.0
    return Completeness(int(count), largest, share, largest_component(missing & outer))


BARS = ("volume", "surface")


@dataclass(frozen=True)
class Bar:
    """When a build counts as complete. ``volume``: fill, largest hole and surface share; ``surface``: the surface
    share and the largest surface hole only (interior cells are invisible)."""
    fill: float = 0.97  # share of the target's cells filled (volume bar only)
    largest_hole: int = 4  # cells; the largest hole (volume) or largest surface hole (surface)
    surface: float = 0.98  # filled share of the exposed cells
    mode: str = "volume"

    def __post_init__(self) -> None:
        if self.mode not in BARS:
            raise ValueError(f"bar mode must be one of {BARS}, not {self.mode!r}")

    def met(self, done: Completeness, filled_share: float) -> bool:
        if self.mode == "surface":
            return done.surface >= self.surface and done.largest_surface_hole <= self.largest_hole
        return filled_share >= self.fill and done.largest_hole <= self.largest_hole and done.surface >= self.surface

    def describe(self) -> str:
        if self.mode == "surface":
            return f"surface bar: surface >= {100 * self.surface:g}%, largest surface hole <= {self.largest_hole}"
        return (f"volume bar: fill >= {100 * self.fill:g}%, largest hole <= {self.largest_hole}, "
                f"surface >= {100 * self.surface:g}%")
