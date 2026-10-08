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
(``physics.required_clutch``). Off by default, which reproduces the M9b-M11 tables. With ``bridge=True``
as well, a part tries all its offsets at the visited cell and takes the one resting on the most distinct
clusters (ties: the first in random order), so separate stacks get joined into one piece where possible.
With ``connect=True``, a repair pass makes the build one piece: the largest cluster is kept, the other
clusters' parts go back to the inventory and are placed again on layers above the ground only, where every
part rests on (so joins) the kept cluster. With ``connect_rounds`` > 1, earlier rounds place the returned
parts anywhere (they may join the kept cluster or each other) and keep the largest cluster again, so less
of the inventory is lost on wide, low shapes where a build splits into many clusters.

With ``preferred`` colors (M12: a (Z, X) array of color names from a color image, "" for none), parts
of the cell's preferred color are tried first; if none of them fits or is left, the sampler's own order
follows.

With ``open_tops=True`` (M12b step 1d, for target shapes), a part's studless top cells (``TileInfo.stud_top``
false: a tile's top) may only sit where ``allowed`` is empty directly above. Nothing can rest on them, so
elsewhere they would make the target cells above unfillable; a thin column capped by a few tiles dies. The
rule removes only such placements, so every guarantee stays. Off by default (builds as before).

Speed (M12b): above the ground, a cell with no stud below within a part's reach (``_reachable``) cannot
take any part, so its placement attempts are skipped; the random draws they would have made are still made,
so builds are identical to trying them. This matters on 3D targets, whose overhangs leave many such cells.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Callable, Mapping

import numpy as np
from scipy import ndimage

from brickwfc.bricks.balance import Balance, clusters
from brickwfc.bricks.colors import BrickColor
from brickwfc.bricks.parts import PartSet, PlacedPart, Shape, TileInfo

if TYPE_CHECKING:
    from brickwfc.bricks.style import StyleBias

PREFERRED_BOOST = 1e6  # weight factor for parts of a cell's preferred color: in practice, tried first


class BottomUpBuilder:
    def __init__(self, parts: PartSet, any_offset: bool = False, style: StyleBias | None = None,
                 balanced: bool = False, bridge: bool = False, connect: bool = False,
                 connect_rounds: int = 1, open_tops: bool = False) -> None:
        if bridge and not (balanced and any_offset):
            raise ValueError("bridge needs balanced=True and any_offset=True")
        self.parts = parts
        self.open_tops = open_tops
        self._studless: dict[Shape, np.ndarray] = {}
        self.any_offset = any_offset
        self.style = style
        self.balanced = balanced
        self.bridge = bridge
        self.connect = connect
        self.connect_rounds = connect_rounds
        self.index = {info: t for t, info in enumerate(parts.infos)}
        # Largest part footprint side: a part covering a cell reaches at most this - 1 cells away from it.
        self.reach = max(max(info.shape.size_z, info.shape.size_x) for info in parts.infos if info.solid)
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
        allowed = np.ones(shape, dtype=bool) if allowed is None else allowed
        state = _State(shape, self.index[TileInfo(None)], inventory, self.balanced)
        self._fill(state, range(shape[0]), rng, allowed, preferred)
        for round_ in range(self.connect_rounds if self.connect else 0):
            found = clusters(state.placed)
            if len(found) <= 1:
                break
            # Keep the largest cluster and return the others' parts to the inventory. Earlier rounds place
            # them again anywhere (they may join the kept cluster); the last round only above the ground,
            # where each part rests on (so joins) the kept cluster.
            keep = set(found[0][0])
            returned = Counter((p.shape.part.name, p.color.name) for i, p in enumerate(state.placed) if i not in keep)
            remaining = None if state.remaining is None else dict(Counter(state.remaining) + returned)
            kept = sorted((state.placed[i] for i in keep), key=lambda p: p.layer)
            state = _State(shape, self.index[TileInfo(None)], None, self.balanced)
            for part in kept:  # already counted against the inventory
                self._put(state, part)
            state.remaining = remaining
            last = round_ == self.connect_rounds - 1
            self._fill(state, range(1 if last else 0, shape[0]), rng, allowed, preferred)
        return state.grid

    def _fill(self, state: "_State", layers: range, rng: np.random.Generator, allowed: np.ndarray,
              preferred: np.ndarray | None) -> None:
        """One bottom-up pass over ``layers``: visit free cells in random order and place a part at some."""
        _, nz, nx = state.filled.shape
        remaining = state.remaining
        for y in layers:
            # Parts placed on layer y never add studs to layer y - 1, so this holds for the whole layer.
            reachable = self._reachable(state.studs, y)
            fit_map = _FitMap(state.filled, state.studs, allowed, y, self._studless_top if self.open_tops else None)
            for flat in rng.permutation(nz * nx):
                z, x = divmod(int(flat), nx)
                if state.filled[y, z, x] or not allowed[y, z, x] or rng.random() >= self.solid_share:
                    continue
                # Try parts in weighted-random order until one fits here. Whether a part fits depends
                # only on its box, so once a box size fails here, other parts of that size are skipped.
                failed: set[tuple[int, int, int]] = set()
                p = self.choice_p if self.style is None else self._styled_p(state.owner, state.placed, y, z, x)
                if preferred is not None and preferred[z, x]:
                    p = p * np.where(self.choice_color_names == preferred[z, x], PREFERRED_BOOST, 1.0)
                    p = p / p.sum()
                for choice in rng.choice(len(self.choices), size=len(self.choices), replace=False, p=p):
                    part_shape, color = self.choices[choice]
                    key = (part_shape.part.name, color.name)
                    if remaining is not None and remaining.get(key, 0) <= 0:
                        continue
                    box = (part_shape.size_y, part_shape.size_z, part_shape.size_x)
                    if box in failed or not reachable[z, x]:
                        if self.any_offset:  # draw what _place would have drawn: same seed, same build
                            rng.permutation(part_shape.size_z * part_shape.size_x)
                        continue
                    part = self._place(part_shape, color, y, z, x, state.filled, state.studs, allowed, rng,
                                       state.owner, state.balance, fit_map)
                    if part is None:
                        failed.add(box)
                    else:
                        self._put(state, part)
                        fit_map.reset()
                        break

    def _put(self, state: "_State", part: PlacedPart) -> None:
        """Record a placed part in every structure of ``state``."""
        key = (part.shape.part.name, part.color.name)
        if state.remaining is not None:
            state.remaining[key] -= 1
        for cy, cz, cx in part.cells():
            state.filled[cy, cz, cx] = True
            state.owner[cy, cz, cx] = len(state.placed)
            state.grid[cy, cz, cx] = self.index[TileInfo(part.shape, cx - part.x, cz - part.z, part.color, cy - part.layer)]
        if part.shape.part.studs:
            for cell in part.top_cells():
                state.studs[cell] = True
        if state.balance is not None:
            state.balance.add(part, self._below(part, state.owner))
        state.placed.append(part)

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
        owner: np.ndarray | None = None, balance: Balance | None = None, fit_map: "_FitMap | None" = None,
    ) -> PlacedPart | None:
        """A fitting placement of the part with its bottom layer covering cell (y, z, x), or None.
        ``fit_map`` (the current layer's, up to date) answers ``_fits`` by lookup."""
        valid = None if fit_map is None else fit_map.corners(part_shape)

        def ok(part: PlacedPart) -> bool:
            if valid is None:
                studless = self._studless_top(part.shape) if self.open_tops else None
                fits = self._fits(part, filled, studs, allowed, studless)
            else:
                fits = 0 <= part.z < valid.shape[0] and 0 <= part.x < valid.shape[1] and bool(valid[part.z, part.x])
            return fits and (balance is None or balance.can_add(part, self._below(part, owner)))

        if not self.any_offset:
            part = PlacedPart(part_shape, color, y, x, z)
            return part if ok(part) else None
        best, best_joined = None, -1
        order = rng.permutation(part_shape.size_z * part_shape.size_x)
        if valid is not None:  # keep the offsets that fit, in the same order
            corner_z, corner_x = z - order // part_shape.size_x, x - order % part_shape.size_x
            inside = (corner_z >= 0) & (corner_x >= 0) & (corner_z < valid.shape[0]) & (corner_x < valid.shape[1])
            fits = np.zeros(len(order), dtype=bool)
            fits[inside] = valid[corner_z[inside], corner_x[inside]]
            order = order[fits]
        for flat in order:
            dz, dx = divmod(int(flat), part_shape.size_x)
            part = PlacedPart(part_shape, color, y, x - dx, z - dz)
            if not ok(part):
                continue
            if not self.bridge:
                return part
            joined = len({balance.root(i) for i in self._below(part, owner)})
            if joined > best_joined:
                best, best_joined = part, joined
        return best

    def _reachable(self, studs: np.ndarray, y: int) -> np.ndarray:
        """(Z, X): cells of layer ``y`` that some part covering them could rest on a stud from. False
        means no part fits there at all (above the ground every part needs a stud under its footprint)."""
        if y == 0:
            return np.ones(studs.shape[1:], dtype=bool)
        size = 2 * self.reach - 1
        return ndimage.maximum_filter(studs[y - 1], size=size, mode="constant", cval=False)

    @staticmethod
    def _below(part: PlacedPart, owner: np.ndarray) -> set[int]:
        """Indices of the parts directly under the part's bottom layer."""
        if part.layer == 0:
            return set()
        y, z, x = part.layer, part.z, part.x
        return set(np.unique(owner[y - 1, z : z + part.shape.size_z, x : x + part.shape.size_x]).tolist()) - {-1}

    def _studless_top(self, shape: Shape) -> np.ndarray:
        """(size_z, size_x) bool: the shape's top-layer cells without a stud."""
        if shape not in self._studless:
            top = shape.size_y - 1
            self._studless[shape] = np.array(
                [[not TileInfo(shape, dx, dz, None, top).stud_top for dx in range(shape.size_x)]
                 for dz in range(shape.size_z)], dtype=bool)
        return self._studless[shape]

    @staticmethod
    def _fits(part: PlacedPart, filled: np.ndarray, studs: np.ndarray, allowed: np.ndarray,
              studless: np.ndarray | None = None) -> bool:
        """Whether the part can go here; with ``studless`` (its studless top cells, ``open_tops``), those
        cells must also have no allowed cell directly above."""
        y, z, x = part.layer, part.z, part.x
        sy, sz, sx = part.shape.size_y, part.shape.size_z, part.shape.size_x
        ny, nz, nx = filled.shape
        if y < 0 or z < 0 or x < 0 or y + sy > ny or z + sz > nz or x + sx > nx:
            return False
        box = (slice(y, y + sy), slice(z, z + sz), slice(x, x + sx))
        if filled[box].any() or not allowed[box].all():
            return False
        # Nothing may rest on a tile; only the connect pass can put a part under existing ones.
        if not part.shape.part.studs and y + sy < ny and filled[y + sy, z : z + sz, x : x + sx].any():
            return False
        if studless is not None and y + sy < ny and (studless & allowed[y + sy, z : z + sz, x : x + sx]).any():
            return False
        if y == 0:
            return True
        below_filled, below_studs = filled[y - 1, z : z + sz, x : x + sx], studs[y - 1, z : z + sz, x : x + sx]
        # A filled cell below without a stud is a tile's top: nothing may rest on it.
        return bool(below_studs.any()) and not (below_filled & ~below_studs).any()


def _window_sums(cells: np.ndarray, sz: int, sx: int) -> np.ndarray:
    """(Z - sz + 1, X - sx + 1): number of True cells in the sz x sx window at each min corner."""
    total = np.zeros((cells.shape[0] + 1, cells.shape[1] + 1), dtype=np.int64)
    total[1:, 1:] = cells.cumsum(axis=0).cumsum(axis=1)
    return total[sz:, sx:] - total[:-sz, sx:] - total[sz:, :-sx] + total[:-sz, :-sx]


class _FitMap:
    """``BottomUpBuilder._fits`` for every min corner on layer ``y`` at once, per part box: computed when a
    box is first asked for and kept until ``reset`` (call it after every placement; within a layer's pass only
    placements change ``filled``, and nothing changes ``studs`` below the layer or ``allowed``)."""

    def __init__(self, filled: np.ndarray, studs: np.ndarray, allowed: np.ndarray, y: int,
                 studless_top: Callable[[Shape], np.ndarray] | None = None) -> None:
        self.filled, self.studs, self.allowed, self.y = filled, studs, allowed, y
        self.studless_top = studless_top  # open_tops: a shape's studless top cells
        self.maps: dict[tuple, np.ndarray] = {}

    def reset(self) -> None:
        self.maps.clear()

    def corners(self, shape: Shape) -> np.ndarray:
        """(Z, X) bool, indexed by a placement's min corner (z, x): it fits (may be empty or smaller than
        the layer; corners outside it do not fit)."""
        sy, sz, sx, studded = shape.size_y, shape.size_z, shape.size_x, shape.part.studs
        studless = None if self.studless_top is None else self.studless_top(shape)
        key = (sy, sz, sx, studded, None if studless is None else studless.tobytes())
        if key not in self.maps:
            self.maps[key] = self._compute(sy, sz, sx, studded, studless)
        return self.maps[key]

    def _compute(self, sy: int, sz: int, sx: int, studded: bool, studless: np.ndarray | None) -> np.ndarray:
        filled, studs, y = self.filled, self.studs, self.y
        ny, nz, nx = filled.shape
        if y + sy > ny or sz > nz or sx > nx:
            return np.zeros((0, 0), dtype=bool)
        blocked = (filled[y : y + sy] | ~self.allowed[y : y + sy]).any(axis=0)
        fits = _window_sums(blocked, sz, sx) == 0
        # Nothing may rest on a tile; only the connect pass can put a part under existing ones.
        if not studded and y + sy < ny:
            fits &= _window_sums(filled[y + sy], sz, sx) == 0
        if studless is not None and studless.any() and y + sy < ny:
            # open_tops: no studless top cell under an allowed cell.
            above = self.allowed[y + sy]
            for dz, dx in np.argwhere(studless):
                fits &= ~above[dz : dz + nz - sz + 1, dx : dx + nx - sx + 1]
        if y > 0:
            # A stud below somewhere, and no tile top (a filled cell below without a stud).
            fits &= _window_sums(studs[y - 1], sz, sx) > 0
            fits &= _window_sums(filled[y - 1] & ~studs[y - 1], sz, sx) == 0
        return fits


class _State:
    """A build in progress."""

    def __init__(self, shape: tuple[int, int, int], empty_tile: int, inventory: Mapping[tuple[str, str], int] | None,
                 balanced: bool) -> None:
        self.remaining = dict(inventory) if inventory is not None else None
        self.filled = np.zeros(shape, dtype=bool)
        self.studs = np.zeros(shape, dtype=bool)  # cells on a part's top layer that carry a stud
        self.owner = np.full(shape, -1, dtype=np.int64)  # index into ``placed``
        self.placed: list[PlacedPart] = []
        self.balance = Balance() if balanced else None
        self.grid = np.full(shape, empty_tile, dtype=np.int64)
