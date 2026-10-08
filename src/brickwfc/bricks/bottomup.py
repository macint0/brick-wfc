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

With a ``style`` (M10, ``style.StyleBias``), the order in which parts are tried at a cell is drawn
from the base weights times the learned likelihood ratio of each part next to the part below the
cell and the parts beside it. Without one, builds are exactly as before.

With ``balanced=True`` (M12), a part is also refused if it would tip its cluster of stud-connected parts
over on a table (``balance.Balance``), so every build needs only finite clutch
(``physics.required_clutch``). Off by default, which reproduces the M9b-M11 tables.

With ``preferred`` colors (M12: a (Z, X) array of color names from a color image, "" for none), parts
of the cell's preferred color are tried first; if none of them fits or is left, the sampler's own order
follows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

import numpy as np

from brickwfc.bricks.balance import Balance
from brickwfc.bricks.colors import BrickColor
from brickwfc.bricks.parts import PartSet, PlacedPart, Shape, TileInfo

if TYPE_CHECKING:
    from brickwfc.bricks.style import StyleBias

PREFERRED_BOOST = 1e6  # weight factor for parts of a cell's preferred color: in practice, tried first


class BottomUpBuilder:
    def __init__(self, parts: PartSet, any_offset: bool = False, style: StyleBias | None = None,
                 balanced: bool = False) -> None:
        self.parts = parts
        self.any_offset = any_offset
        self.style = style
        self.balanced = balanced
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
        self.choice_color_names = np.array([color.name for _, color in self.choices])
        self.solid_share = float(weights.sum() / parts.tileset.weights.sum())
        if style is not None:
            from brickwfc.bricks.style import TYPE_INDEX

            self.choice_types = np.array([TYPE_INDEX[shape.part.name] for shape, _ in self.choices])
            self.choice_colors = np.array([style.color_id(color.name) for _, color in self.choices])

    def build(
        self,
        shape: tuple[int, int, int],
        rng: np.random.Generator,
        inventory: Mapping[tuple[str, str], int] | None = None,
        allowed: np.ndarray | None = None,
        preferred: np.ndarray | None = None,
    ) -> np.ndarray:
        """A (Y, Z, X) grid of tile ids; every placed part is whole, supported, within ``inventory``
        ((part name, color name) -> count) and inside ``allowed`` (bool, grid-shaped) if given.
        ``preferred`` (Z, X) color names, "" for none, reorders the parts tried at each cell."""
        remaining = dict(inventory) if inventory is not None else None
        ny, nz, nx = shape
        allowed = np.ones(shape, dtype=bool) if allowed is None else allowed
        filled = np.zeros(shape, dtype=bool)
        studs = np.zeros(shape, dtype=bool)  # cells on a part's top layer that carry a stud
        owner = np.full(shape, -1, dtype=np.int64)  # index into ``placed``
        placed: list[PlacedPart] = []
        balance = Balance() if self.balanced else None
        grid = np.full(shape, self.index[TileInfo(None)], dtype=np.int64)
        for y in range(ny):
            for flat in rng.permutation(nz * nx):
                z, x = divmod(int(flat), nx)
                if filled[y, z, x] or not allowed[y, z, x] or rng.random() >= self.solid_share:
                    continue
                # Try parts in weighted-random order until one fits here. Whether a part fits depends
                # only on its box, so once a box size fails here, other parts of that size are skipped.
                failed: set[tuple[int, int, int]] = set()
                p = self.choice_p if self.style is None else self._styled_p(owner, placed, y, z, x)
                if preferred is not None and preferred[z, x]:
                    p = p * np.where(self.choice_color_names == preferred[z, x], PREFERRED_BOOST, 1.0)
                    p = p / p.sum()
                for choice in rng.choice(len(self.choices), size=len(self.choices), replace=False, p=p):
                    part_shape, color = self.choices[choice]
                    key = (part_shape.part.name, color.name)
                    if remaining is not None and remaining.get(key, 0) <= 0:
                        continue
                    box = (part_shape.size_y, part_shape.size_z, part_shape.size_x)
                    if box in failed:
                        if self.any_offset:  # draw what _place would have drawn: same seed, same build
                            rng.permutation(part_shape.size_z * part_shape.size_x)
                        continue
                    part = self._place(part_shape, color, y, z, x, filled, studs, allowed, rng, owner, balance)
                    if part is None:
                        failed.add(box)
                    else:
                        if remaining is not None:
                            remaining[key] -= 1
                        for cy, cz, cx in part.cells():
                            filled[cy, cz, cx] = True
                            owner[cy, cz, cx] = len(placed)
                            grid[cy, cz, cx] = self.index[TileInfo(part_shape, cx - part.x, cz - part.z, color, cy - y)]
                        if part_shape.part.studs:
                            for cell in part.top_cells():
                                studs[cell] = True
                        if balance is not None:
                            balance.add(part, self._below(part, owner))
                        placed.append(part)
                        break
        return grid

    def _styled_p(self, owner: np.ndarray, placed: list[PlacedPart], y: int, z: int, x: int) -> np.ndarray:
        """Choice probabilities at cell (y, z, x): base weights times the style's likelihood ratios for
        the part below the cell and the parts beside it."""
        _, nz, nx = owner.shape
        context: list[tuple[int, PlacedPart]] = []
        if y > 0 and owner[y - 1, z, x] >= 0:
            context.append((0, placed[owner[y - 1, z, x]]))
        beside = {int(owner[y, z + dz, x + dx]) for dz, dx in ((0, -1), (0, 1), (-1, 0), (1, 0))
                  if 0 <= z + dz < nz and 0 <= x + dx < nx} - {-1}
        context += [(1, placed[i]) for i in sorted(beside)]
        if not context:
            return self.choice_p
        weights = self.choice_p * self.style.for_choices(context, self.choice_types, self.choice_colors)
        return weights / weights.sum()

    def _place(
        self, part_shape: Shape, color: BrickColor, y: int, z: int, x: int,
        filled: np.ndarray, studs: np.ndarray, allowed: np.ndarray, rng: np.random.Generator,
        owner: np.ndarray | None = None, balance: Balance | None = None,
    ) -> PlacedPart | None:
        """A fitting placement of the part with its bottom layer covering cell (y, z, x), or None."""
        def ok(part: PlacedPart) -> bool:
            return self._fits(part, filled, studs, allowed) and (
                balance is None or balance.can_add(part, self._below(part, owner)))

        if not self.any_offset:
            part = PlacedPart(part_shape, color, y, x, z)
            return part if ok(part) else None
        for flat in rng.permutation(part_shape.size_z * part_shape.size_x):
            dz, dx = divmod(int(flat), part_shape.size_x)
            part = PlacedPart(part_shape, color, y, x - dx, z - dz)
            if ok(part):
                return part
        return None

    @staticmethod
    def _below(part: PlacedPart, owner: np.ndarray) -> set[int]:
        """Indices of the parts directly under the part's bottom layer."""
        if part.layer == 0:
            return set()
        y, z, x = part.layer, part.z, part.x
        return set(np.unique(owner[y - 1, z : z + part.shape.size_z, x : x + part.shape.size_x]).tolist()) - {-1}

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
