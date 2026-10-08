"""Baseline generator: random bottom-up placement (no WFC).

Layer by layer from the ground, visit free cells in random order and, with the same per-cell solid
probability as the WFC tileset's weights, try to anchor a part there. Parts are drawn with the same
(shape, color) weights WFC uses. A part is placed only if it fits in the grid, overlaps nothing,
(above layer 0) rests on at least one stud, and does not rest on a tile, so every build satisfies
``support.is_stable`` and ``parts.extract_parts``'s integrity rules by construction. A brick placed on
layer y also fills layers y + 1 and y + 2, which are then skipped. This is the obvious alternative a reviewer would propose, so experiments compare
against it. With an inventory, a (part, color) is skipped once it is used up; with an ``allowed`` mask
(a target shape), parts must lie entirely inside it.

By default a part is tried only with its min corner on the visited cell. ``any_offset=True`` (M11)
tries every position of the part that covers the cell, in random order, so a gap can also be filled
by a part reaching into it from the left or front: a stronger baseline when packing matters.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from brickwfc.bricks.colors import BrickColor
from brickwfc.bricks.parts import PartSet, PlacedPart, Shape, TileInfo


class BottomUpBuilder:
    def __init__(self, parts: PartSet, any_offset: bool = False) -> None:
        self.parts = parts
        self.any_offset = any_offset
        self.index = {info: t for t, info in enumerate(parts.infos)}
        # Same priors as WFC: a cell's chance of holding (shape, color) is the summed weight of
        # that pair's tiles; the solid share is the solid tiles' share of all weight.
        totals: dict[tuple, float] = {}
        for info, weight in zip(parts.infos, parts.tileset.weights):
            if info.solid:
                key = (info.shape, info.color)
                totals[key] = totals.get(key, 0.0) + float(weight)
        self.choices = list(totals)
        weights = np.array([totals[k] for k in self.choices])
        self.choice_p = weights / weights.sum()
        self.solid_share = float(weights.sum() / parts.tileset.weights.sum())

    def build(
        self,
        shape: tuple[int, int, int],
        rng: np.random.Generator,
        inventory: Mapping[tuple[str, str], int] | None = None,
        allowed: np.ndarray | None = None,
    ) -> np.ndarray:
        """A (Y, Z, X) grid of tile ids; every placed part is whole, supported, within ``inventory``
        ((part name, color name) -> count) and inside ``allowed`` (bool, grid-shaped) if given."""
        remaining = dict(inventory) if inventory is not None else None
        ny, nz, nx = shape
        allowed = np.ones(shape, dtype=bool) if allowed is None else allowed
        filled = np.zeros(shape, dtype=bool)
        studs = np.zeros(shape, dtype=bool)  # cells on a part's top layer that carry a stud
        grid = np.full(shape, self.index[TileInfo(None)], dtype=np.int64)
        for y in range(ny):
            for flat in rng.permutation(nz * nx):
                z, x = divmod(int(flat), nx)
                if filled[y, z, x] or not allowed[y, z, x] or rng.random() >= self.solid_share:
                    continue
                # Try parts in weighted-random order until one fits here. Whether a part fits depends
                # only on its box, so once a box size fails here, other parts of that size are skipped.
                failed: set[tuple[int, int, int]] = set()
                for choice in rng.choice(len(self.choices), size=len(self.choices), replace=False, p=self.choice_p):
                    part_shape, color = self.choices[choice]
                    key = (part_shape.part.name, color.name)
                    if remaining is not None and remaining.get(key, 0) <= 0:
                        continue
                    box = (part_shape.size_y, part_shape.size_z, part_shape.size_x)
                    if box in failed:
                        if self.any_offset:  # draw what _place would have drawn: same seed, same build
                            rng.permutation(part_shape.size_z * part_shape.size_x)
                        continue
                    part = self._place(part_shape, color, y, z, x, filled, studs, allowed, rng)
                    if part is None:
                        failed.add(box)
                    else:
                        if remaining is not None:
                            remaining[key] -= 1
                        for cy, cz, cx in part.cells():
                            filled[cy, cz, cx] = True
                            grid[cy, cz, cx] = self.index[TileInfo(part_shape, cx - part.x, cz - part.z, color, cy - y)]
                        if part_shape.part.studs:
                            for cell in part.top_cells():
                                studs[cell] = True
                        break
        return grid

    def _place(
        self, part_shape: Shape, color: BrickColor, y: int, z: int, x: int,
        filled: np.ndarray, studs: np.ndarray, allowed: np.ndarray, rng: np.random.Generator,
    ) -> PlacedPart | None:
        """A fitting placement of the part with its bottom layer covering cell (y, z, x), or None."""
        if not self.any_offset:
            part = PlacedPart(part_shape, color, y, x, z)
            return part if self._fits(part, filled, studs, allowed) else None
        for flat in rng.permutation(part_shape.size_z * part_shape.size_x):
            dz, dx = divmod(int(flat), part_shape.size_x)
            part = PlacedPart(part_shape, color, y, x - dx, z - dz)
            if self._fits(part, filled, studs, allowed):
                return part
        return None

    @staticmethod
    def _fits(part: PlacedPart, filled: np.ndarray, studs: np.ndarray, allowed: np.ndarray) -> bool:
        y, z, x = part.layer, part.z, part.x
        sy, sz, sx = part.shape.size_y, part.shape.size_z, part.shape.size_x
        ny, nz, nx = filled.shape
        if y < 0 or z < 0 or x < 0 or y + sy > ny or z + sz > nz or x + sx > nx:
            return False
        box = (slice(y, y + sy), slice(z, z + sz), slice(x, x + sx))
        if filled[box].any() or not allowed[box].all():
            return False
        if y == 0:
            return True
        below_filled, below_studs = filled[y - 1, z : z + sz, x : x + sx], studs[y - 1, z : z + sz, x : x + sx]
        # A filled cell below without a stud is a tile's top: nothing may rest on it.
        return bool(below_studs.any()) and not (below_filled & ~below_studs).any()
