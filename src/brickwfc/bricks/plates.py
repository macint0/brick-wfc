"""3D tileset of 1x1 plates (M4): each cell is empty or one 1x1 plate of some color.

Grids are indexed (y, z, x) with y the plate layer (see ``tileset.GRID3D``). The support rule
"a plate above layer 0 needs a plate directly below it" is local, so it is expressed purely as a
vertical adjacency rule: nothing in the grid sits below layer 0, so the ground supports it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from brickwfc.bricks.colors import BrickColor
from brickwfc.tileset import GRID3D, Tileset

EMPTY = "empty"
EMPTY_DISPLAY_COLOR = (255, 255, 255)
UP, DOWN = GRID3D.directions.index("U"), GRID3D.directions.index("D")


@dataclass(frozen=True, eq=False)
class PlateSet:
    """A 3D tileset plus what each tile means physically."""

    tileset: Tileset
    ldraw_colors: tuple[int | None, ...]  # per tile; None for empty

    @property
    def solid(self) -> np.ndarray:
        """(T,) bool: which tiles are a plate rather than empty space."""
        return np.array([c is not None for c in self.ldraw_colors])


def plate_tileset(colors: Sequence[BrickColor], empty_weight: float = 4.0, plate_weight: float = 1.0) -> PlateSet:
    """Empty + one 1x1 plate per color. Horizontally anything may touch; vertically a plate
    may not sit on empty space."""
    names = [EMPTY] + [f"plate1x1_{c.name}" for c in colors]
    display = [EMPTY_DISPLAY_COLOR] + [c.rgb for c in colors]
    weights = [empty_weight] + [plate_weight] * len(colors)
    solid = np.array([False] + [True] * len(colors))

    compat = np.ones((len(GRID3D.directions), len(names), len(names)), dtype=bool)
    compat[DOWN] = ~np.outer(solid, ~solid)  # below a plate: no empty
    compat[UP] = ~np.outer(~solid, solid)  # above empty: no plate
    tileset = Tileset(tuple(names), tuple(display), np.array(weights), compat, GRID3D)
    return PlateSet(tileset, (None,) + tuple(c.ldraw for c in colors))
