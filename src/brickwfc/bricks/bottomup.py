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

Corner and slope parts (M12b): parts whose footprint is not a full box, or whose top or bottom is only
partly studded or flat, are checked cell by cell (``_fits_cells``): their seated cells need a stud below,
nothing may be above their studless top cells (a slope's face) or below their open bottom cells (an
inverted slope's underside). Rectangular parts keep the box checks, so builds from an M8 catalog are unchanged.

Speed (M12b): above the ground, a cell with no stud below within a part's reach (``_reachable``) cannot
take any part, so its placement attempts are skipped; the random draws they would have made are still made,
so builds are identical to trying them. This matters on 3D targets, whose overhangs leave many such cells.

With a ``proposal`` (M12b, ``proposal.Proposal``: a learned model of the next part in raster order), the
choice probabilities at a cell are also multiplied by the model's weights for a part starting there, raised
to ``proposal_strength``; every mask (inventory, support, balance, shape, one piece) is unchanged. The model
reads the parts in the order they are placed, so pair it with ``order="raster"`` (cells of a layer visited
by z, then x, as in its training data) rather than the default random order.

Looks (M12b step 3), both off by default (builds as before). With ``skin=True`` and a target, at a cell on the
target's outer surface (``shapes.surface``) parts are tried largest first (most cells; the sampled order breaks
ties), so the first one that fits is the largest that fits: the skin shows fewer, larger parts. With
``skin_power`` = a, the preference is soft instead: on those cells the choice weights (style included) are
multiplied by each part's cells ** a before the order is drawn, so larger parts are tried earlier but the learned
style still decides among them (a -> infinity is the hard sort). With a mirror
``plane`` passed to ``build`` (``symmetry.Plane``), every placed part is followed by its mirror image when it
fits there (every rule as for any part, balance included) and the inventory has it: in the part's color, else
in the first color of that part left (in the choices' fixed order). Both only reorder or add placements that
pass the same checks, so every guarantee stays.

Completeness (M12b holes), off by default (builds as before). With ``holes=True`` (needs ``any_offset``), a
hole-filling pass follows the main pass and each connect round, over the same layers as that pass (the last
connect round's: above the ground only, so the build stays one piece). It visits every free cell of
``allowed``, bottom layer first, and tries every part the inventory still has at every offset that covers the
cell, with no empty draw: the largest footprint first (then the most cells), so 1 x 1 plates and bricks are
left to finish holes rather than spent early; among parts of the same size, the sampled order (style,
preferred color, proposal, skin weights) decides. A part is placed if any fits, under every rule of the main
pass (inventory, support, balance, shape, open tops; mirror images with a ``plane``). Sweeps repeat until one
places nothing (a part can make another fit: a stud to rest on, a cluster that now balances), so when the pass
ends no remaining part fits at any free cell it visits.

With ``hang=True`` as well (needs ``holes``), the hole pass has a second support mode: a part is also supported
if one of its stud cells sits directly under a placed part's seated cell (a flat underside that takes a stud;
not a slope's open bottom), i.e. it hangs from the part above by the same stud joint as a part resting on it.
The main pass stays bottom-up; by the time the hole pass runs the parts above exist, so it reaches the lowest
layer of an overhang, which bottom-up cantilevering never does (it has no stud below), and its sweeps let a hung
part carry another under it. A hung part joins the cluster of the parts it hangs from for the balance check, and
the build is then supported in the sense of ``support.is_stable(hanging=True)``: every part is joined to the
ground through stud joints. Physics needs no change: the LP already lets a stud joint hold a part up (clutch).

Small parts (M12b completeness), off by default. The hole pass found most unfilled cells wanting a small plate the
main pass had used up. ``reserve_small`` keeps small parts (at most ``SMALL_CELLS`` cells: 1 x 1, 1 x 2, 1 x 3 plates,
tiles and 1 x 1 bricks, the 2 x 2 corner plate) for where nothing larger fits: at each main-pass cell they are tried
only after every larger part has failed there (under every rule, the inventory included), so a cell only a small part
fits, such as a 1-wide post, still gets one in the main pass; the hole pass is unchanged. ``small_power`` a is the soft
form: in the main pass a small part's choice weight is multiplied by (cells / (SMALL_CELLS + 1)) ** a (a 1 x 1 plate's
divided by 4 ** a), so small parts tend to come last at a cell but stay in the draw. Both act on the main pass: the
layer-by-layer one (random or raster order) and, in the connected order, the growth (its seed and its sweeps, which
order a cell's parts the same way); never on the hole pass.

Connected growth (M12b, ``order="connected"``; for target shapes). The main pass grows one piece instead of
building layer by layer: the first part goes on the ground in the largest connected region of the target's
ground layer (ties: the one nearest the centre of the target's footprint), and after it a cell is visited only
if a part covering it could join the structure: rest on a stud of it within a part's reach below, or, with
``hang``, hang from it within reach above. A part on the ground joins only by hanging (its studs under the
structure). The lowest layer with such cells comes first: its cells are visited in seeded random order, each
tried (no empty draw, the style's order among the parts), and the layer is visited again until nothing more fits
there; only then does the growth move up a layer. A placement may open cells below it (a part hanging under it)
as well as above, so after one the growth steps back down by the tallest part's height. A cell where nothing fits
is left and tried again on every later visit of its layer. So the structure spreads low first (a chair's arms,
then its feet, hung down to the ground) before it climbs. Every placement, mirror images and the hole
pass included, joins the one piece, so the connect repair has nothing to do; feet and tips are reached from the
seed along the arms (down to the ground by hanging) instead of being built as separate stacks. Without ``hang``,
nothing but the seed reaches the ground. With ``balanced``, the growth does not ask every partial build to
stand (grown from one leg, a table could never reach its other legs); it asks it of the result instead: the
build is cut back to the longest prefix of its placements that stands (every prefix is supported and one piece
by construction), and the parts cut go back to the inventory for the hole pass, which checks balance at every
placement as the main pass does.

Diagnosis (M12b completeness): a ``trace`` object set on the builder hears about every cell visit of the main pass
that places nothing (``skipped``: the solid-share draw passed the cell over; ``failed``: no part fits there) and
about every connect repair (``repaired``, with the state before it); of the hole pass it hears only when each
pass starts (``holes``, with the state then), and it gets the final state (``finished``). It must not draw from the
generator, so traced builds are identical to untraced ones. The connected order's growth is not traced.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Callable, Mapping

import numpy as np
from scipy import ndimage

from brickwfc.bricks.balance import Balance, clusters
from brickwfc.bricks.colors import BrickColor
from brickwfc.bricks.parts import PartSet, PlacedPart, Shape, TileInfo
from brickwfc.bricks.shapes import surface
from brickwfc.bricks.symmetry import Plane, mirror_part

if TYPE_CHECKING:
    from brickwfc.bricks.proposal import Proposal, Session
    from brickwfc.bricks.style import StyleBias

PREFERRED_BOOST = 1e6  # weight factor for parts of a cell's preferred color: in practice, tried first
SMALL_CELLS = 3  # small_reserve / small_power: parts of at most this many cells (see the module docstring)


class BottomUpBuilder:
    def __init__(self, parts: PartSet, any_offset: bool = False, style: StyleBias | None = None,
                 balanced: bool = False, bridge: bool = False, connect: bool = False,
                 connect_rounds: int = 1, open_tops: bool = False, order: str = "random",
                 proposal: Proposal | None = None, proposal_strength: float = 1.0, skin: bool = False,
                 skin_power: float | None = None, holes: bool = False, hang: bool = False,
                 small_reserve: bool = False, small_power: float | None = None) -> None:
        if bridge and not (balanced and any_offset):
            raise ValueError("bridge needs balanced=True and any_offset=True")
        if holes and not any_offset:
            raise ValueError("holes needs any_offset=True")
        if hang and not holes:
            raise ValueError("hang needs holes=True")
        if small_reserve and small_power is not None:
            raise ValueError("small_reserve and small_power are alternatives")
        if order not in ("random", "raster", "connected"):
            raise ValueError(f"order must be 'random', 'raster' or 'connected', not {order!r}")
        self.order = order
        self.skin = skin
        self.skin_power = skin_power  # None: hard largest-first sort on the skin; a: weights x cells ** a
        self.holes = holes
        self.hang = hang  # holes: parts may also hang from a part above by their studs
        self.small_reserve = small_reserve  # main pass: small parts only where no larger part fits
        self.small_power = small_power  # main pass: small parts' weights x (cells / (SMALL_CELLS + 1)) ** this
        self.proposal = proposal
        self.proposal_strength = proposal_strength
        self.parts = parts
        self.open_tops = open_tops
        self._studless: dict[Shape, np.ndarray] = {}
        self.any_offset = any_offset
        self.style = style
        self.balanced = balanced
        self.bridge = bridge
        self.connect = connect
        self.connect_rounds = connect_rounds
        self.trace = None  # diagnosis hooks (see the module docstring); None: no tracing
        self.index = {info: t for t, info in enumerate(parts.infos)}
        # Largest part footprint side: a part covering a cell reaches at most this - 1 cells away from it.
        self.reach = max(max(info.shape.size_z, info.shape.size_x) for info in parts.infos if info.solid)
        shapes = {info.shape for info in parts.infos if info.solid}
        self.cell_masks = {shape: _CellMasks(shape) for shape in shapes if not shape.rectangular}
        self.open_bottoms = any(len(shape.geometry.seated) < len(shape.footprint) for shape in shapes)
        self.heights = sorted({shape.size_y for shape in shapes})
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
        self.choice_cells = np.array([shape.cells for shape, _ in self.choices])
        self.skin_weights = None if skin_power is None else self.choice_cells.astype(float) ** skin_power
        self.choice_small = self.choice_cells <= SMALL_CELLS
        self.small_weights = None if small_power is None else np.where(
            self.choice_small, (self.choice_cells / (SMALL_CELLS + 1)) ** small_power, 1.0)
        # Hole pass order: largest footprint first, then most cells (a 1 x 1 brick before a 1 x 1 plate).
        self.choice_size = np.array([len(shape.footprint) * 1000 + shape.cells for shape, _ in self.choices])
        self.shape_colors: dict[Shape, list[BrickColor]] = {}  # colors each shape has tiles in, in choice order
        for shape, color in self.choices:
            self.shape_colors.setdefault(shape, []).append(color)
        self.solid_share = float(weights.sum() / parts.tileset.weights.sum())
        if style is not None:
            from brickwfc.bricks.style import TYPE_INDEX

            self.choice_types = np.array([TYPE_INDEX[shape.part.name] for shape, _ in self.choices])
            self.choice_colors = np.array([style.color_id(color.name) for _, color in self.choices])
        if proposal is not None:
            self.choice_tokens = proposal.choice_tokens(self.choices)

    def build(
        self,
        shape: tuple[int, int, int],
        rng: np.random.Generator,
        inventory: Mapping[tuple[str, str], int] | None = None,
        allowed: np.ndarray | None = None,
        preferred: np.ndarray | None = None,
        plane: Plane | None = None,
    ) -> np.ndarray:
        """A (Y, Z, X) grid of tile ids; every placed part is whole, supported, within ``inventory``
        ((part name, color name) -> count) and inside ``allowed`` (bool, grid-shaped) if given.
        ``preferred`` (Z, X) color names, "" for none, reorders the parts tried at each cell; ``plane``: place
        each part's mirror image with it where possible."""
        target = allowed
        allowed = np.ones(shape, dtype=bool) if allowed is None else allowed
        skin = surface(target) if self.skin and target is not None else None
        state = self._new_state(shape, inventory, target, skin, plane)
        if self.order == "connected":
            state = self._grow(state, rng, allowed, preferred, target)
        else:
            self._fill(state, range(shape[0]), rng, allowed, preferred)
        if self.holes:
            self._fill_holes(state, range(shape[0]), rng, allowed, preferred)
        for round_ in range(self.connect_rounds if self.connect else 0):
            found = clusters(state.placed)
            if len(found) <= 1:
                break
            # Keep the largest cluster and return the others' parts to the inventory. Earlier rounds place
            # them again anywhere (they may join the kept cluster); the last round only above the ground,
            # where each part rests on (so joins) the kept cluster.
            if self.trace is not None:
                self.trace.repaired(state)
            keep = set(found[0][0])
            returned = Counter((p.shape.part.name, p.color.name) for i, p in enumerate(state.placed) if i not in keep)
            remaining = None if state.remaining is None else dict(Counter(state.remaining) + returned)
            kept = sorted((state.placed[i] for i in keep), key=lambda p: p.layer)
            state = self._new_state(shape, None, target, skin, plane)
            for part in kept:  # already counted against the inventory
                self._put(state, part)
            state.remaining = remaining
            last = round_ == self.connect_rounds - 1
            layers = range(1 if last else 0, shape[0])
            self._fill(state, layers, rng, allowed, preferred)
            if self.holes:
                self._fill_holes(state, layers, rng, allowed, preferred)
        if self.trace is not None:
            self.trace.finished(state)
        return state.grid

    def _new_state(self, shape: tuple[int, int, int], inventory: Mapping[tuple[str, str], int] | None,
                   target: np.ndarray | None, skin: np.ndarray | None, plane: Plane | None) -> "_State":
        state = _State(shape, self.index[TileInfo(None)], inventory, self.balanced)
        state.session = None if self.proposal is None else self.proposal.session(shape, target)
        state.skin, state.plane = skin, plane
        return state

    def _fill(self, state: "_State", layers: range, rng: np.random.Generator, allowed: np.ndarray,
              preferred: np.ndarray | None) -> None:
        """One bottom-up pass over ``layers``: visit free cells in random order and place a part at some."""
        _, nz, nx = state.filled.shape
        remaining = state.remaining
        for y in layers:
            # Parts placed on layer y never add studs to layer y - 1, so this holds for the whole layer.
            reachable = self._reachable(state.studs, y)
            open_bottom = state.open_bottom if self.open_bottoms else None
            fit_map = _FitMap(state.filled, state.studs, allowed, y, self._studless_top if self.open_tops else None,
                              open_bottom)
            for flat in rng.permutation(nz * nx) if self.order == "random" else range(nz * nx):
                z, x = divmod(int(flat), nx)
                if state.filled[y, z, x] or not allowed[y, z, x]:
                    continue
                if rng.random() >= self.solid_share:
                    if self.trace is not None:
                        self.trace.skipped(state, y, z, x)
                    continue
                # Try parts in weighted-random order until one fits here. Whether a part fits depends
                # only on its _fit_key, so once one fails here, other parts with that key are skipped.
                failed: set[tuple[int, int, int]] = set()
                p = self._cell_p(state, y, z, x, preferred, bool(reachable[z, x]))
                if self.small_weights is not None:  # soft: small parts tend to come last
                    p = p * self.small_weights
                    p = p / p.sum()
                on_skin = state.skin is not None and bool(state.skin[y, z, x])
                order = rng.choice(len(self.choices), size=len(self.choices), replace=False, p=p)
                if on_skin and self.skin_weights is None:  # hard: largest first on the skin
                    order = order[np.argsort(-self.choice_cells[order], kind="stable")]
                if self.small_reserve:  # small parts only after every larger one failed here
                    order = order[np.argsort(self.choice_small[order], kind="stable")]
                for choice in order:
                    part_shape, color = self.choices[choice]
                    key = (part_shape.part.name, color.name)
                    if remaining is not None and remaining.get(key, 0) <= 0:
                        continue
                    box = _fit_key(part_shape)
                    if box in failed or not reachable[z, x]:
                        if self.any_offset:  # draw what _place would have drawn: same seed, same build
                            rng.permutation(len(part_shape.footprint))
                        continue
                    part = self._place(part_shape, color, y, z, x, state.filled, state.studs, allowed, rng,
                                       state.owner, state.balance, fit_map, state.open_bottom)
                    if part is None:
                        failed.add(box)
                    else:
                        self._put(state, part)
                        if state.plane is not None:
                            self._put_mirror(state, part, allowed)
                        fit_map.reset()
                        break
                else:
                    if self.trace is not None:
                        self.trace.failed(self, state, allowed, reachable, y, z, x)

    def _cell_p(self, state: "_State", y: int, z: int, x: int, preferred: np.ndarray | None,
                reachable: bool) -> np.ndarray:
        """Choice probabilities at cell (y, z, x): base weights, times the style's ratios, the preferred color's
        boost, the proposal's weights (where some part can rest) and the soft skin weights."""
        p = self.choice_p if self.style is None else self._styled_p(state.owner, state.placed, y, z, x)
        if preferred is not None and preferred[z, x]:
            p = p * np.where(self.choice_color_names == preferred[z, x], PREFERRED_BOOST, 1.0)
            p = p / p.sum()
        if state.session is not None and reachable:
            p = self._proposed_p(p, state.session, y, z, x)
        if state.skin is not None and state.skin[y, z, x] and self.skin_weights is not None:
            p = p * self.skin_weights  # soft: larger parts weigh more on the skin
            p = p / p.sum()
        return p

    def _fill_holes(self, state: "_State", layers: range, rng: np.random.Generator, allowed: np.ndarray,
                    preferred: np.ndarray | None) -> None:
        """The hole-filling pass (see the module docstring): sweeps over ``layers`` until one places nothing."""
        if self.trace is not None:
            self.trace.holes(state)
        self._sweeps(state, layers, rng, allowed, preferred, True, self.order == "connected")

    def _grow(self, state: "_State", rng: np.random.Generator, allowed: np.ndarray, preferred: np.ndarray | None,
              target: np.ndarray | None) -> "_State":
        """The connected growth order's main pass (see the module docstring): a seed part on the ground, sweeps
        over joinable cells until one places nothing, then (``balanced``) the longest prefix that stands."""
        balance, state.balance = state.balance, None  # checked on the result, below
        self._grow_from_seed(state, rng, allowed, preferred)
        if balance is None:
            return state
        keep = self._standing_prefix(state.placed, allowed.shape)
        returned = Counter((p.shape.part.name, p.color.name) for p in state.placed[keep:])
        remaining = None if state.remaining is None else dict(Counter(state.remaining) + returned)
        kept = state.placed[:keep]
        state = self._new_state(allowed.shape, None, target, state.skin, state.plane)
        for part in kept:  # already counted against the inventory
            self._put(state, part, self._links(part, state.owner))
        state.remaining = remaining
        return state

    def _standing_prefix(self, placed: list[PlacedPart], shape: tuple[int, int, int]) -> int:
        """The length of the longest prefix of ``placed`` (one piece at every length) that stands on a table."""
        balance, owner, keep = Balance(), np.full(shape, -1, dtype=np.int64), 0
        for i, part in enumerate(placed):
            balance.add(part, self._links(part, owner))
            for cell in part.cells():
                owner[cell] = i
            if all(cluster.stands() for cluster in balance.clusters.values()):
                keep = i + 1
        return keep

    def _grow_from_seed(self, state: "_State", rng: np.random.Generator, allowed: np.ndarray,
                        preferred: np.ndarray | None) -> None:
        labels, count = ndimage.label(allowed[0])
        if not count:
            return
        sizes = np.bincount(labels.ravel())[1:]
        footprint = np.argwhere(allowed.any(axis=0)).mean(axis=0)

        def rank(region: int) -> tuple[int, float]:  # largest, then nearest the footprint's centre
            centre = np.argwhere(labels == region).mean(axis=0)
            return int(sizes[region - 1]), -float(np.hypot(*(centre - footprint)))

        region = max(range(1, count + 1), key=rank)
        cells = np.argwhere(labels == region)
        cells = cells[rng.permutation(len(cells))]
        open_bottom = state.open_bottom if self.open_bottoms else None
        fit_map = _FitMap(state.filled, state.studs, allowed, 0, self._studless_top if self.open_tops else None,
                          open_bottom, state.open_bottom if self.hang else None)
        for z, x in cells.tolist():
            if self._try_cell(state, 0, z, x, rng, allowed, preferred, fit_map, False, False):
                break
        else:
            return
        drop = max(self.heights) if self.hang else 0
        y = 0
        while y < allowed.shape[0]:
            if state.remaining is not None and not any(n > 0 for n in state.remaining.values()):
                return
            if self._sweep_layer(state, y, rng, allowed, preferred, False, True):
                y = max(0, y - drop)  # visit this layer again, and the layers a part could now hang into
            else:
                y += 1

    def _sweeps(self, state: "_State", layers: range, rng: np.random.Generator, allowed: np.ndarray,
                preferred: np.ndarray | None, largest_first: bool, joined: bool) -> None:
        """Sweeps over the free cells of ``allowed`` in ``layers`` that a part could reach (rest on a stud within
        reach below, hang within reach above with ``hang``), bottom layer first, trying every visited cell, until
        one places nothing. ``largest_first``: the hole pass's part order; ``joined``: every part must join the
        structure (a part on the ground only by hanging)."""
        changed = True
        while changed:
            changed = False
            for y in layers:
                if state.remaining is not None and not any(n > 0 for n in state.remaining.values()):
                    return
                if self._sweep_layer(state, y, rng, allowed, preferred, largest_first, joined):
                    changed = True

    def _sweep_layer(self, state: "_State", y: int, rng: np.random.Generator, allowed: np.ndarray,
                     preferred: np.ndarray | None, largest_first: bool, joined: bool) -> bool:
        """One visit of layer ``y``'s reachable free cells (``_sweeps``); whether it placed a part."""
        reachable = self._reachable(state.studs, y)
        if joined and y == 0:  # the ground joins nothing
            reachable = np.zeros_like(reachable)
        if self.hang:
            reachable = reachable | self._hang_reachable(state, y)
        cells = np.argwhere(allowed[y] & ~state.filled[y] & reachable)
        if not len(cells):
            return False
        if self.order != "raster":
            cells = cells[rng.permutation(len(cells))]
        open_bottom = state.open_bottom if self.open_bottoms else None
        fit_map = _FitMap(state.filled, state.studs, allowed, y, self._studless_top if self.open_tops else None,
                          open_bottom, state.open_bottom if self.hang else None)
        placed = False
        for z, x in cells.tolist():
            if state.filled[y, z, x]:  # taken by a part placed at a cell visited earlier
                continue
            if self._try_cell(state, y, z, x, rng, allowed, preferred, fit_map, largest_first, joined):
                placed = True
        return placed

    def _try_cell(self, state: "_State", y: int, z: int, x: int, rng: np.random.Generator, allowed: np.ndarray,
                  preferred: np.ndarray | None, fit_map: "_FitMap", largest_first: bool, joined: bool) -> bool:
        """Place the first part that fits covering free cell (y, z, x), in the sampled order; whether one was placed.
        ``largest_first`` (the hole pass): sorted largest first. Otherwise (connected growth, the main pass) as in
        ``_fill``: the skin's hard sort where it applies, and the small-part options."""
        p = self._cell_p(state, y, z, x, preferred, True)
        if not largest_first and self.small_weights is not None:  # soft: small parts tend to come last
            p = p * self.small_weights
            p = p / p.sum()
        order = rng.choice(len(self.choices), size=len(self.choices), replace=False, p=p)
        if largest_first:
            order = order[np.argsort(-self.choice_size[order], kind="stable")]
        else:
            if state.skin is not None and state.skin[y, z, x] and self.skin_weights is None:
                order = order[np.argsort(-self.choice_cells[order], kind="stable")]
            if self.small_reserve:  # small parts only after every larger one failed here
                order = order[np.argsort(self.choice_small[order], kind="stable")]
        failed: set = set()
        for choice in order:
            part_shape, color = self.choices[choice]
            if state.remaining is not None and state.remaining.get((part_shape.part.name, color.name), 0) <= 0:
                continue
            box = _fit_key(part_shape)
            if box in failed:
                continue
            part = self._place(part_shape, color, y, z, x, state.filled, state.studs, allowed, rng,
                               state.owner, state.balance, fit_map, state.open_bottom,
                               state.open_bottom if self.hang else None, joined)
            if part is None:
                failed.add(box)
                continue
            self._put(state, part, self._links(part, state.owner) if self.hang else None)
            if state.plane is not None:  # in the connected order every mirror image joins too (the seed's)
                self._put_mirror(state, part, allowed, self.hang, joined or self.order == "connected")
            fit_map.reset()
            return True
        return False

    def _hang_reachable(self, state: "_State", y: int) -> np.ndarray:
        """(Z, X): cells of layer ``y`` that some part covering them could hang from a part above from."""
        ny = state.filled.shape[0]
        takes = np.zeros(state.filled.shape[1:], dtype=bool)
        for height in self.heights:
            if y + height < ny:
                takes |= state.filled[y + height] & ~state.open_bottom[y + height]
        return ndimage.maximum_filter(takes, size=2 * self.reach - 1, mode="constant", cval=False)

    def _links(self, part: PlacedPart, owner: np.ndarray) -> set[int]:
        """Indices of the parts ``part`` is joined to by studs: the ones below it and the ones above its studs."""
        ny = owner.shape[0]
        above = {int(owner[y + 1, z, x]) for y, z, x in part.stud_cells() if y + 1 < ny} - {-1}
        return self._below(part, owner) | above

    def _put(self, state: "_State", part: PlacedPart, links: set[int] | None = None) -> None:
        """Record a placed part in every structure of ``state``; ``links``: the parts it joins for the balance
        check (default: the ones below it)."""
        key = (part.shape.part.name, part.color.name)
        if state.remaining is not None:
            state.remaining[key] -= 1
        for cy, cz, cx in part.cells():
            state.filled[cy, cz, cx] = True
            state.owner[cy, cz, cx] = len(state.placed)
            state.grid[cy, cz, cx] = self.index[TileInfo(part.shape, cx - part.x, cz - part.z, part.color, cy - part.layer)]
        for cell in part.stud_cells():
            state.studs[cell] = True
        for cell in set(part.bottom_cells()) - set(part.seated_cells()):
            state.open_bottom[cell] = True
        if state.balance is not None:
            state.balance.add(part, self._below(part, state.owner) if links is None else links)
        state.placed.append(part)
        if state.session is not None:
            state.session.add(part)

    def _put_mirror(self, state: "_State", part: PlacedPart, allowed: np.ndarray, hang: bool = False,
                    joined: bool = False) -> None:
        """Place ``part``'s mirror image across ``state.plane`` if it fits and the inventory has it."""
        image = mirror_part(part, state.plane)
        if image is None or image == part:
            return
        colors = self.shape_colors.get(image.shape, [])
        left = [c for c in sorted(colors, key=lambda c: c != part.color)  # the part's own color first
                if state.remaining is None or state.remaining.get((image.shape.part.name, c.name), 0) > 0]
        if not left:
            return
        image = PlacedPart(image.shape, left[0], image.layer, image.x, image.z)
        if self._fits_now(image, state, allowed, hang, joined):  # whether a part fits does not depend on its color
            self._put(state, image, self._links(image, state.owner) if hang else None)

    def _fits_now(self, part: PlacedPart, state: "_State", allowed: np.ndarray, hang: bool = False,
                  joined: bool = False) -> bool:
        """Every check ``_place`` makes, for this exact placement (``hang``: as in the hole pass with ``hang``;
        ``joined``: a part on the ground must hang from the structure, as in the connected order)."""
        open_bottom = state.open_bottom if self.open_bottoms else None
        hang_bottom = state.open_bottom if hang else None
        cells = self.cell_masks.get(part.shape)
        if cells is not None:
            fits = self._fits_cells(part, cells, state.filled, state.studs, allowed, open_bottom, self.open_tops,
                                    hang_bottom)
        else:
            studless = self._studless_top(part.shape) if self.open_tops else None
            fits = self._fits(part, state.filled, state.studs, allowed, studless, open_bottom, hang_bottom)
        if not fits:
            return False
        links = self._links(part, state.owner) if hang else self._below(part, state.owner)
        if joined and part.layer == 0 and not links:
            return False
        return state.balance is None or state.balance.can_add(part, links)

    def _proposed_p(self, p: np.ndarray, session: Session, y: int, z: int, x: int) -> np.ndarray:
        """Choice probabilities ``p`` times the proposal's weights (normalized, floored so that every choice
        stays possible) raised to ``proposal_strength``."""
        q = session.weights(y, z, x, *self.choice_tokens)
        q = q / q.sum() + 1e-6
        weights = p * q**self.proposal_strength
        return weights / weights.sum()

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
        open_bottom: np.ndarray | None = None, hang_bottom: np.ndarray | None = None, joined: bool = False,
    ) -> PlacedPart | None:
        """A fitting placement of the part with its bottom layer covering cell (y, z, x), or None.
        ``fit_map`` (the current layer's, up to date) answers ``_fits`` by lookup for rectangular parts;
        other parts are checked cell by cell (``_fits_cells``). ``hang_bottom`` (the build's open bottoms): the
        part may also hang from a part above (see the module docstring); ``joined``: a part on the ground must
        hang from the structure (the connected order)."""
        open_bottom = open_bottom if self.open_bottoms else None
        cells = self.cell_masks.get(part_shape)
        valid = None if fit_map is None or cells is not None else fit_map.corners(part_shape)

        def links(part: PlacedPart) -> set[int]:
            return self._below(part, owner) if hang_bottom is None else self._links(part, owner)

        def ok(part: PlacedPart) -> bool:
            if cells is not None:
                fits = self._fits_cells(part, cells, filled, studs, allowed, open_bottom, self.open_tops, hang_bottom)
            elif valid is None:
                studless = self._studless_top(part.shape) if self.open_tops else None
                fits = self._fits(part, filled, studs, allowed, studless, open_bottom, hang_bottom)
            else:
                fits = 0 <= part.z < valid.shape[0] and 0 <= part.x < valid.shape[1] and bool(valid[part.z, part.x])
            if not fits:
                return False
            if joined and part.layer == 0 and not links(part):
                return False
            return balance is None or balance.can_add(part, links(part))

        if not self.any_offset:
            part = PlacedPart(part_shape, color, y, x, z)
            return part if ok(part) else None
        best, best_joined = None, -1
        order = rng.permutation(len(part_shape.footprint))
        if valid is not None:  # keep the offsets that fit, in the same order (a rectangle: footprint = box)
            corner_z, corner_x = z - order // part_shape.size_x, x - order % part_shape.size_x
            inside = (corner_z >= 0) & (corner_x >= 0) & (corner_z < valid.shape[0]) & (corner_x < valid.shape[1])
            fits = np.zeros(len(order), dtype=bool)
            fits[inside] = valid[corner_z[inside], corner_x[inside]]
            order = order[fits]
        for flat in order:
            dz, dx = part_shape.footprint[int(flat)]  # row-major: divmod(flat, size_x) for a rectangle
            part = PlacedPart(part_shape, color, y, x - dx, z - dz)
            if not ok(part):
                continue
            if not self.bridge or balance is None:  # no clusters to join while connected growth defers balance
                return part
            count = len({balance.root(i) for i in links(part)})
            if count > best_joined:
                best, best_joined = part, count
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
        if not part.shape.rectangular:
            return {int(owner[y - 1, z, x]) for y, z, x in part.seated_cells()} - {-1}
        y, z, x = part.layer, part.z, part.x
        return set(np.unique(owner[y - 1, z : z + part.shape.size_z, x : x + part.shape.size_x]).tolist()) - {-1}

    def _studless_top(self, shape: Shape) -> np.ndarray:
        """(size_z, size_x) bool: the shape's top-layer cells without a stud (a corner's notch is no cell)."""
        if shape not in self._studless:
            top = shape.size_y - 1
            self._studless[shape] = np.array(
                [[shape.covers(dz, dx) and not TileInfo(shape, dx, dz, None, top).stud_top
                  for dx in range(shape.size_x)]
                 for dz in range(shape.size_z)], dtype=bool)
        return self._studless[shape]

    @staticmethod
    def _fits(part: PlacedPart, filled: np.ndarray, studs: np.ndarray, allowed: np.ndarray,
              studless: np.ndarray | None = None, open_bottom: np.ndarray | None = None,
              hang_bottom: np.ndarray | None = None) -> bool:
        """Whether the part can go here; with ``studless`` (its studless top cells, ``open_tops``), those
        cells must also have no allowed cell directly above; with ``open_bottom`` (the build's inverted-slope
        undersides), no top cell may be right under one; with ``hang_bottom`` (the build's open bottoms, always
        given), a studded part with no stud below may hang from a part's flat underside right above its top."""
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
        # Nor right under an inverted slope's open bottom (checked only when the tileset has such parts).
        if open_bottom is not None and y + sy < ny and open_bottom[y + sy, z : z + sz, x : x + sx].any():
            return False
        if y == 0:
            return True
        below_filled, below_studs = filled[y - 1, z : z + sz, x : x + sx], studs[y - 1, z : z + sz, x : x + sx]
        # A filled cell below without a stud is a tile's top: nothing may rest on it.
        if (below_filled & ~below_studs).any():
            return False
        if below_studs.any():
            return True
        return (hang_bottom is not None and part.shape.part.studs and y + sy < ny
                and bool((filled[y + sy, z : z + sz, x : x + sx] & ~hang_bottom[y + sy, z : z + sz, x : x + sx]).any()))

    @staticmethod
    def _fits_cells(part: PlacedPart, masks: "_CellMasks", filled: np.ndarray, studs: np.ndarray,
                    allowed: np.ndarray, open_bottom: np.ndarray | None, open_tops: bool = False,
                    hang_bottom: np.ndarray | None = None) -> bool:
        """``_fits`` cell by cell, for a part that is not a full box with uniform faces (corners, slopes);
        ``open_tops`` and ``hang_bottom`` as in ``_fits`` (it hangs by its studded top cells)."""
        y, z, x = part.layer, part.z, part.x
        sy = part.shape.size_y
        ny, nz, nx = filled.shape
        if y < 0 or z < 0 or x < 0 or y + sy > ny or z + part.shape.size_z > nz or x + part.shape.size_x > nx:
            return False
        zz, xx = z + masks.dz, x + masks.dx
        if filled[y : y + sy, zz, xx].any() or not allowed[y : y + sy, zz, xx].all():
            return False
        if open_tops and y + sy < ny and (allowed[y + sy, zz, xx] & ~masks.studded).any():
            return False
        if y + sy < ny:  # only the connect pass can put a part under existing ones
            above = filled[y + sy, zz, xx]
            if (above & ~masks.studded).any() or (open_bottom is not None and open_bottom[y + sy, zz, xx].any()):
                return False
        if y == 0:
            return True
        below_filled, below_studs = filled[y - 1, zz, xx], studs[y - 1, zz, xx]
        if (below_filled & ~masks.seated).any():  # nothing under an open bottom
            return False
        # Seated cells rest on studs (at least one) or on nothing, never on a studless top.
        if (below_filled & ~below_studs).any():
            return False
        if (below_studs & masks.seated).any():
            return True
        return (hang_bottom is not None and y + sy < ny
                and bool((filled[y + sy, zz, xx] & ~hang_bottom[y + sy, zz, xx] & masks.studded).any()))


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
                 studless_top: Callable[[Shape], np.ndarray] | None = None,
                 open_bottom: np.ndarray | None = None, hang_bottom: np.ndarray | None = None) -> None:
        self.filled, self.studs, self.allowed, self.y = filled, studs, allowed, y
        self.studless_top = studless_top  # open_tops: a shape's studless top cells
        self.open_bottom = open_bottom  # M12b: inverted slopes' open bottoms (None: no such parts)
        self.hang_bottom = hang_bottom  # hole pass with hang: the open bottoms (studded parts may hang)
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
        # Nor right under an inverted slope's open bottom.
        if self.open_bottom is not None and y + sy < ny:
            fits &= _window_sums(self.open_bottom[y + sy], sz, sx) == 0
        if y > 0:
            # A stud below somewhere (or, hanging, a flat underside right above), and no tile top (a filled
            # cell below without a stud).
            supported = _window_sums(studs[y - 1], sz, sx) > 0
            if self.hang_bottom is not None and studded and y + sy < ny:
                supported |= _window_sums(filled[y + sy] & ~self.hang_bottom[y + sy], sz, sx) > 0
            fits &= supported
            fits &= _window_sums(filled[y - 1] & ~studs[y - 1], sz, sx) == 0
        return fits


class _State:
    """A build in progress."""

    def __init__(self, shape: tuple[int, int, int], empty_tile: int, inventory: Mapping[tuple[str, str], int] | None,
                 balanced: bool) -> None:
        self.remaining = dict(inventory) if inventory is not None else None
        self.filled = np.zeros(shape, dtype=bool)
        self.studs = np.zeros(shape, dtype=bool)  # cells on a part's top layer that carry a stud
        self.open_bottom = np.zeros(shape, dtype=bool)  # a part's bottom cells that are not flat (nothing below)
        self.owner = np.full(shape, -1, dtype=np.int64)  # index into ``placed``
        self.placed: list[PlacedPart] = []
        self.balance = Balance() if balanced else None
        self.grid = np.full(shape, empty_tile, dtype=np.int64)
        self.session: Session | None = None  # the proposal model's view of this build
        self.skin: np.ndarray | None = None  # skin=True: the target's outer surface cells
        self.plane: Plane | None = None  # symmetric decoding: the mirror plane


def _fit_key(shape: Shape) -> tuple:
    """What decides whether a part fits at a cell: its box and whether it has studs for a rectangular part (so
    once one part fails there, others of the same key are skipped), its cells and their faces otherwise. The studs
    count since open tops (M12b 1d): a tile may not sit under a target cell where a plate of its box may (before M12b
    completeness the key was the box alone, so a failed tile made the builder skip the plate)."""
    box = (shape.size_y, shape.size_z, shape.size_x)
    if shape.rectangular:
        return (*box, shape.part.studs)
    g = shape.geometry
    return box, g.footprint, g.studded, g.seated


class _CellMasks:
    """A shape's footprint as index arrays, with its studded top cells and seated bottom cells as masks."""

    def __init__(self, shape: Shape) -> None:
        self.dz = np.array([dz for dz, _ in shape.footprint])
        self.dx = np.array([dx for _, dx in shape.footprint])
        self.studded = np.array([shape.studded(dz, dx) for dz, dx in shape.footprint])
        self.seated = np.array([shape.seated(dz, dx) for dz, dx in shape.footprint])
