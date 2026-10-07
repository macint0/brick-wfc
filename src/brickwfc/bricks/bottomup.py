"""Baseline generator: random bottom-up placement (no WFC).

Layer by layer from the ground, visit free cells in random order and, with the same per-cell solid
probability as the WFC tileset's weights, try to anchor a part there. Parts are drawn with the same
(shape, color) weights WFC uses. A part is placed only if it fits in the grid, overlaps nothing, and
(above layer 0) rests on at least one solid cell, so every build satisfies ``support.is_stable`` by
construction. This is the obvious alternative a reviewer would propose, so experiments compare
against it. With an inventory, a (part, color) is skipped once it is used up.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from brickwfc.bricks.parts import PartSet, PlacedPart, TileInfo


class BottomUpBuilder:
    def __init__(self, parts: PartSet) -> None:
        self.parts = parts
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
    ) -> np.ndarray:
        """A (Y, Z, X) grid of tile ids; every placed part is whole, supported, and within ``inventory``
        ((part name, color name) -> count) if one is given."""
        remaining = dict(inventory) if inventory is not None else None
        ny, nz, nx = shape
        filled = np.zeros(shape, dtype=bool)
        grid = np.full(shape, self.index[TileInfo(None)], dtype=np.int64)
        for y in range(ny):
            for flat in rng.permutation(nz * nx):
                z, x = divmod(int(flat), nx)
                if filled[y, z, x] or rng.random() >= self.solid_share:
                    continue
                # Try parts in weighted-random order until one fits here.
                for choice in rng.choice(len(self.choices), size=len(self.choices), replace=False, p=self.choice_p):
                    part_shape, color = self.choices[choice]
                    key = (part_shape.part.name, color.name)
                    if remaining is not None and remaining.get(key, 0) <= 0:
                        continue
                    part = PlacedPart(part_shape, color, y, x, z)
                    if self._fits(part, filled):
                        if remaining is not None:
                            remaining[key] -= 1
                        for cy, cz, cx in part.cells():
                            filled[cy, cz, cx] = True
                            grid[cy, cz, cx] = self.index[TileInfo(part_shape, cx - x, cz - z, color)]
                        break
        return grid

    @staticmethod
    def _fits(part: PlacedPart, filled: np.ndarray) -> bool:
        cells = part.cells()
        if not all(0 <= c < n for cell in cells for c, n in zip(cell, filled.shape)):
            return False
        if any(filled[cell] for cell in cells):
            return False
        return part.layer == 0 or any(filled[y - 1, z, x] for y, z, x in cells)
