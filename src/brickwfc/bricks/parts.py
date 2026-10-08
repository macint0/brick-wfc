"""Multi-cell parts as WFC tiles (M5, M8, M12b).

A part occupies a set of stud cells (its *footprint*: a rectangle for most parts, an L for corner
parts), ``height`` plate layers tall (plates and tiles 1, bricks and most slopes 3). Each cell of a
placed part holds the tile (shape, offset inside the part's bounding box, color), where a *shape* is a
part in one of its (up to 4) orientations. Adjacency rules make parts whole: if a tile's neighbor in
direction d lies inside its part, that neighbor must be exactly the matching tile of the same part;
otherwise the neighbor must also sit on a part face (or be empty). Border masks keep parts inside the
grid.

Per cell, a part's top may carry a stud or not (a tile's top, a slope's sloped face), and its bottom
may be flat ("seated": it can rest on a stud) or not (an inverted slope's sloped underside). Nothing
may be directly above a studless top cell or directly below an unseated bottom cell, and a part is
supported by studs under its seated cells only. A slope is modelled as its full bounding box, so the
space above its sloped face is unusable (conservative: a real part could overhang it).

Grids are indexed (y, z, x), as in ``tileset.GRID3D``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, Mapping, Sequence

import numpy as np

from brickwfc.bricks.colors import BrickColor
from brickwfc.ldraw.export import IDENTITY, Placement, stud_position
from brickwfc.tileset import GRID3D, Tileset

EMPTY = "empty"
EMPTY_DISPLAY_COLOR = (255, 255, 255)
UP, DOWN = GRID3D.directions.index("U"), GRID3D.directions.index("D")
HORIZONTAL = tuple(d for d, offset in enumerate(GRID3D.offsets) if offset[0] == 0)
ROTATE_Y_90 = (0, 0, 1, 0, 1, 0, -1, 0, 0)  # maps LDraw +X onto +Z

Support = Literal["none", "cell"]
Kind = Literal["plate", "brick", "tile", "slope"]
Cells = tuple[tuple[float, float], ...]  # stud-cell centres (x, z) in studs along LDraw X, Z from the part origin


@dataclass(frozen=True)
class Part:
    """A part type. ``width`` x ``depth`` studs along LDraw X x Z in its default orientation (its
    bounding box), ``height`` plate layers tall; ``studs`` is False for parts without any stud (tiles).

    Rectangular parts leave the geometry fields at None: the footprint is the full ``width`` x ``depth``
    rectangle centred on the LDraw origin, every top cell has a stud (if ``studs``) and every bottom cell
    is flat. Other parts list their ``cells`` (stud-cell centres from the origin, as in the part's .dat
    file), the cells with a stud on top (``stud_cells``) and the cells with a flat bottom
    (``seated_cells``). ``origin_top``: the origin is on the top face (most parts), else on the bottom.
    ``aliases``: older LDraw file names of the same part ("~Moved to" files) that models still use.
    """

    name: str
    ldraw: str
    width: int
    depth: int
    height: int = 1
    studs: bool = True
    kind: Kind = "plate"
    cells: Cells | None = None
    stud_cells: Cells | None = None
    seated_cells: Cells | None = None
    origin_top: bool = True
    aliases: tuple[str, ...] = ()

    @property
    def footprint_cells(self) -> Cells:
        if self.cells is not None:
            return self.cells
        return tuple((x - (self.width - 1) / 2, z - (self.depth - 1) / 2)
                     for z in range(self.depth) for x in range(self.width))

    @property
    def studded_cells(self) -> Cells:
        if self.stud_cells is not None:
            return self.stud_cells
        return self.footprint_cells if self.studs else ()

    @property
    def flat_bottom_cells(self) -> Cells:
        return self.footprint_cells if self.seated_cells is None else self.seated_cells


HEIGHTS: dict[Kind, int] = {"plate": 1, "brick": 3, "tile": 1, "slope": 3}


def _family(kind: Kind, spec: str, suffix: bool = False) -> list[Part]:
    """Parts from ``"file:DEPTHxWIDTH ..."``; LDraw parts are long along X, so width >= depth.
    With ``suffix``, the file name is appended to the part name (lookalikes of a plain part)."""
    parts = []
    for item in spec.split():
        file, size = item.split(":")
        depth, width = (int(v) for v in size.split("x"))
        name = f"{kind}{depth}x{width}" + (f"_{file}" if suffix else "")
        parts.append(Part(name, f"{file}.dat", width, depth, HEIGHTS[kind], kind != "tile", kind))
    return parts


# Rectangular plates, bricks and tiles in common sizes (M8).
_PLAIN = (
    _family("plate", "3024:1x1 3023:1x2 3623:1x3 3710:1x4 3666:1x6 3460:1x8 4477:1x10 60479:1x12 "
                     "3022:2x2 3021:2x3 3020:2x4 3795:2x6 3034:2x8 3832:2x10 2445:2x12 "
                     "3031:4x4 3032:4x6 3035:4x8 3030:4x10 3958:6x6 3036:6x8 3033:6x10 3456:6x14 41539:8x8")
    + _family("brick", "3005:1x1 3004:1x2 3622:1x3 3010:1x4 3009:1x6 3008:1x8 6111:1x10 6112:1x12 2465:1x16 "
                       "3003:2x2 3002:2x3 3001:2x4 2456:2x6 3007:2x8 3006:2x10")
    + _family("tile", "3070b:1x1 3069b:1x2 63864:1x3 2431:1x4 6636:1x6 4162:1x8 3068b:2x2 26603:2x3 87079:2x4")
)
# Lookalikes: other parts that fill the same box and have the same studs (round 1x1 plates, a brick
# with a grille, a tile with a clip, ...). They connect like the plain part, so they are kept as
# their own parts (and exported with their own files) rather than ignored.
_LOOKALIKES = (
    _family("plate", "6141:1x1 4073:1x1 4032a:2x2 4032b:2x2", suffix=True)
    + _family("brick", "3062a:1x1 3062b:1x1 4070:1x1 3065:1x2 2877:1x2 3066:1x4 3941:2x2 6143:2x2", suffix=True)
    + _family("tile", "2555:1x1 2412a:1x2 2412b:1x2", suffix=True)
    + _family("brick", "4216:1x2", suffix=True)  # M12b: brick with groove
)


def _corner(kind: Kind, file: str) -> Part:
    """A 2x2 corner part (an L of 3 cells). Its origin is on the corner stud; the arms run along +X and +Z."""
    return Part(f"{kind}2x2_corner", f"{file}.dat", 2, 2, HEIGHTS[kind], True, kind, cells=((0, 0), (1, 0), (0, 1)))


# Non-rectangular parts (M12b), after the M8 ones so that style statistics keep their part indices.
_CORNERS = [_corner("plate", "2420"), _corner("brick", "2357")]
CATALOG: dict[str, Part] = {p.name: p for p in _PLAIN + _LOOKALIKES + _CORNERS}
BY_FILE: dict[str, Part] = {file: p for p in CATALOG.values() for file in (p.ldraw, *p.aliases)}

# M4-M11 used these four plates only; experiments that reproduce those tables still do.
PLATES: dict[str, Part] = {name: CATALOG[name] for name in ("plate1x1", "plate1x2", "plate2x2", "plate2x4")}
PLATE_FILES: dict[str, Part] = {p.ldraw: p for p in PLATES.values()}


def family(kind: Kind, lookalikes: bool = False) -> list[Part]:
    """Every catalog part of one kind (plain ones only, unless ``lookalikes``)."""
    return [p for p in CATALOG.values() if p.kind == kind and (lookalikes or p in _PLAIN)]


def turn_rotation(turn: int) -> tuple[int, ...]:
    """LDraw rotation of ``turn`` quarter turns about the vertical axis (``ROTATE_Y_90`` applied ``turn`` times)."""
    step = np.array(ROTATE_Y_90).reshape(3, 3)
    return tuple(int(v) for v in np.linalg.matrix_power(step, turn % 4).ravel())


Offsets = tuple[tuple[int, int], ...]  # (dz, dx) cells from a shape's bounding-box min corner


@dataclass(frozen=True)
class Geometry:
    """A part's cells in one orientation."""

    footprint: Offsets  # every cell of one layer, row-major (by dz, then dx)
    studded: frozenset[tuple[int, int]]  # top cells with a stud
    seated: frozenset[tuple[int, int]]  # bottom cells with a flat underside
    origin: tuple[float, float]  # (x, z) of the LDraw origin from the min-corner cell's centre, in studs
    size_x: int
    size_z: int


@lru_cache(maxsize=None)
def geometry(part: Part, turn: int) -> Geometry:
    """The part's cells turned by ``turn`` quarter turns (the rotation of its LDraw placement) and
    shifted so that its bounding box starts at (0, 0)."""
    r = np.array(turn_rotation(turn)).reshape(3, 3)

    def turned(cells: Cells) -> list[tuple[float, float]]:
        return [(r[0, 0] * x + r[0, 2] * z, r[2, 0] * x + r[2, 2] * z) for x, z in cells]

    world = turned(part.footprint_cells)
    min_x, min_z = min(x for x, _ in world), min(z for _, z in world)

    def offsets(cells: Cells) -> list[tuple[int, int]]:
        return [(int(round(z - min_z)), int(round(x - min_x))) for x, z in turned(cells)]

    footprint = tuple(sorted(offsets(part.footprint_cells)))
    return Geometry(
        footprint, frozenset(offsets(part.studded_cells)), frozenset(offsets(part.flat_bottom_cells)),
        (float(-min_x), float(-min_z)), 1 + max(dx for _, dx in footprint), 1 + max(dz for dz, _ in footprint),
    )


TURN_SUFFIX = ("", "_r90", "_r180", "_r270")


@dataclass(frozen=True)
class Shape:
    """A part in one orientation: ``turn`` quarter turns about the vertical axis (True/False mean 1/0).
    Sizes are those of its bounding box along the grid's x and z axes."""

    part: Part
    turn: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "turn", int(self.turn) % 4)

    @property
    def geometry(self) -> Geometry:
        return geometry(self.part, self.turn)

    @property
    def rotated(self) -> bool:
        """Turned by an odd number of quarter turns (a rectangle's long side along z)."""
        return self.turn % 2 == 1

    @property
    def size_x(self) -> int:
        return self.geometry.size_x

    @property
    def size_z(self) -> int:
        return self.geometry.size_z

    @property
    def size_y(self) -> int:
        return self.part.height

    @property
    def footprint(self) -> Offsets:
        """(dz, dx) of every cell of one layer from the bounding box's min corner, row-major."""
        return self.geometry.footprint

    @property
    def rectangular(self) -> bool:
        """A full box whose top cells all have studs (or none do) and whose bottom is flat (the M8 parts)."""
        g = self.geometry
        return (len(g.footprint) == g.size_x * g.size_z and len(g.seated) == len(g.footprint)
                and len(g.studded) in (0, len(g.footprint)))

    @property
    def cells(self) -> int:
        return len(self.footprint) * self.size_y

    @property
    def name(self) -> str:
        return f"{self.part.name}{TURN_SUFFIX[self.turn]}"

    def covers(self, dz: int, dx: int) -> bool:
        return (dz, dx) in self.geometry.footprint

    def studded(self, dz: int, dx: int) -> bool:
        """Whether the top of cell (dz, dx) carries a stud."""
        return (dz, dx) in self.geometry.studded

    def seated(self, dz: int, dx: int) -> bool:
        """Whether the bottom of cell (dz, dx) is flat (it can rest on a stud)."""
        return (dz, dx) in self.geometry.seated


def _same_cells(a: Shape, b: Shape) -> bool:
    ga, gb = a.geometry, b.geometry
    return (ga.footprint, ga.studded, ga.seated) == (gb.footprint, gb.studded, gb.seated)


def shapes_of(parts: Sequence[Part]) -> list[Shape]:
    """Every distinct orientation of each part: 1 for a square, 2 for a rectangle, up to 4 otherwise.
    Turns that give the same cells as an earlier one (a rectangle turned twice) are left out."""
    shapes = []
    for part in parts:
        mine: list[Shape] = []
        for turn in range(4):
            shape = Shape(part, turn)
            if not any(_same_cells(shape, s) for s in mine):
                mine.append(shape)
        shapes += mine
    return shapes


def canonical(part: Part, turn: int) -> Shape:
    """The shape of ``part`` turned by ``turn`` quarter turns, as listed by ``shapes_of``."""
    return next(s for s in shapes_of([part]) if _same_cells(s, Shape(part, turn)))


@dataclass(frozen=True)
class TileInfo:
    """What a tile means: one cell of a part, or empty space."""

    shape: Shape | None  # None for empty
    offset_x: int = 0
    offset_z: int = 0
    color: BrickColor | None = None
    offset_y: int = 0  # layer inside the part (0 = bottom)

    @property
    def solid(self) -> bool:
        return self.shape is not None

    @property
    def bottom(self) -> bool:
        """A cell on the part's bottom layer (the one that rests on what is below)."""
        return self.shape is not None and self.offset_y == 0

    @property
    def top(self) -> bool:
        """A cell on the part's top layer."""
        return self.shape is not None and self.offset_y == self.shape.size_y - 1

    @property
    def stud_top(self) -> bool:
        """A cell on the part's top layer that carries a stud (something may click onto it)."""
        return self.top and self.shape.studded(self.offset_z, self.offset_x)

    @property
    def studless_top(self) -> bool:
        """A top cell without a stud (a tile, a slope's sloped face): nothing may be directly above it."""
        return self.top and not self.shape.studded(self.offset_z, self.offset_x)

    @property
    def open_bottom(self) -> bool:
        """A bottom cell that is not flat (an inverted slope's underside): nothing may be directly below it."""
        return self.bottom and not self.shape.seated(self.offset_z, self.offset_x)

    def inside(self, dx: int, dz: int, dy: int = 0) -> bool:
        """Whether the cell at (dx, dz, dy) from this one belongs to the same part."""
        if self.shape is None:
            return False
        y = self.offset_y + dy
        return 0 <= y < self.shape.size_y and self.shape.covers(self.offset_z + dz, self.offset_x + dx)

    def footprint(self) -> list[tuple[int, int]]:
        """(dz, dx) offsets from this cell to every cell of its part's layer, itself included."""
        if self.shape is None:
            return []
        return [(z - self.offset_z, x - self.offset_x) for z, x in self.shape.footprint]

    def seats(self) -> list[tuple[int, int]]:
        """(dz, dx) offsets from this cell to every flat-bottomed cell of its part (those it can rest on studs with)."""
        if self.shape is None:
            return []
        return [(z - self.offset_z, x - self.offset_x) for z, x in self.shape.footprint if self.shape.seated(z, x)]


@dataclass(frozen=True, eq=False)
class PartSet:
    tileset: Tileset
    infos: tuple[TileInfo, ...]

    @property
    def solid(self) -> np.ndarray:
        """(T,) bool: which tiles are part of a part."""
        return np.array([info.solid for info in self.infos])

    @property
    def bottom(self) -> np.ndarray:
        """(T,) bool: tiles on a part's bottom layer."""
        return np.array([info.bottom for info in self.infos])

    @property
    def stud_top(self) -> np.ndarray:
        """(T,) bool: tiles on a part's top layer with a stud."""
        return np.array([info.stud_top for info in self.infos])


def part_tileset(
    parts: Sequence[Part],
    colors: Sequence[BrickColor],
    empty_weight: float = 1.0,
    support: Support = "none",
    coverage: Mapping[tuple[str, str], float] | None = None,
) -> PartSet:
    """Tiles for every (shape, offset, color) plus empty.

    Weights: by default each part type gets the same total weight, split evenly over its
    orientations, cells, and colors, so part types cover a similar share of cells.
    ``coverage`` instead maps (shape name, color name) to a target share of cells (e.g. learned
    from real sets, M7); pairs missing from it get no tiles. Either way the solid tiles' weights
    sum to ``len(parts)``, so ``empty_weight`` means the same thing in both modes.
    ``support="cell"`` adds M4's local rule: no solid cell directly above an empty one.
    """
    shapes = shapes_of(parts)
    tile_specs: list[tuple[Shape, BrickColor, float]] = []  # weight per tile of each (shape, color)
    for shape in shapes:
        orientations = sum(1 for s in shapes if s.part == shape.part)
        for color in colors:
            if coverage is None:
                tile_specs.append((shape, color, 1.0 / (orientations * shape.cells * len(colors))))
            elif coverage.get((shape.name, color.name), 0) > 0:
                tile_specs.append((shape, color, coverage[(shape.name, color.name)] / shape.cells))
    total = sum(w * s.cells for s, _, w in tile_specs)

    infos: list[TileInfo] = [TileInfo(None)]
    weights: list[float] = [empty_weight]
    for shape, color, weight in tile_specs:
        for y in range(shape.size_y):
            for z, x in shape.footprint:
                infos.append(TileInfo(shape, x, z, color, y))
                weights.append(weight * len(parts) / total)

    compat, border = adjacency(infos)
    solid = np.array([info.solid for info in infos])
    if support == "cell":
        compat[DOWN] &= ~np.outer(solid, ~solid)
        compat[UP] &= ~np.outer(~solid, solid)

    names = [EMPTY] + [tile_name(i) for i in infos[1:]]
    display = [EMPTY_DISPLAY_COLOR] + [i.color.rgb for i in infos[1:]]
    tileset = Tileset(tuple(names), tuple(display), np.array(weights), compat, GRID3D, border)
    return PartSet(tileset, tuple(infos))


def tile_name(info: TileInfo) -> str:
    layer = f"y{info.offset_y}" if info.shape.size_y > 1 else ""
    return f"{info.shape.name}_x{info.offset_x}{layer}z{info.offset_z}_{info.color.name}"


def adjacency(infos: Sequence[TileInfo]) -> tuple[np.ndarray, np.ndarray]:
    """Integrity rules ``compat`` (D, T, T) and border masks (D, T) for the tiles ``infos``.

    In direction d: a tile whose part continues there needs exactly the next tile of the same part;
    otherwise the neighbor must not belong to a part that continues back (or it would be cut off).
    On top of that, nothing may sit on a studless top cell (a tile, a slope's face) or be directly below
    an unseated bottom cell (an inverted slope's underside). Rules are symmetric.
    """
    solid = np.array([i.solid for i in infos])
    shape_ids: dict[Shape, int] = {}
    shape_id = np.array([shape_ids.setdefault(i.shape, len(shape_ids)) if i.solid else -1 for i in infos])
    color_ids: dict[str, int] = {}
    color_id = np.array([color_ids.setdefault(i.color.name, len(color_ids)) if i.solid else -1 for i in infos])
    offset = np.array([(i.offset_y, i.offset_z, i.offset_x) for i in infos])
    same_part = solid[:, None] & (shape_id[:, None] == shape_id[None, :]) & (color_id[:, None] == color_id[None, :])

    count = len(infos)
    compat = np.ones((len(GRID3D.directions), count, count), dtype=bool)
    border = np.ones((len(GRID3D.directions), count), dtype=bool)
    for d, (dy, dz, dx) in enumerate(GRID3D.offsets):
        continues = np.array([i.inside(dx, dz, dy) for i in infos], dtype=bool)
        continues_back = np.array([i.inside(-dx, -dz, -dy) for i in infos], dtype=bool)
        next_tile = same_part & np.all(offset[None, :, :] == offset[:, None, :] + np.array((dy, dz, dx)), axis=2)
        compat[d] = np.where(continues[:, None], next_tile, ~continues_back[None, :])
        border[d] = ~continues

    studless_top = np.array([i.studless_top for i in infos], dtype=bool)
    compat[UP] &= ~np.outer(studless_top, solid)
    compat[DOWN] &= ~np.outer(solid, studless_top)
    open_bottom = np.array([i.open_bottom for i in infos], dtype=bool)
    compat[DOWN] &= ~np.outer(open_bottom, solid)
    compat[UP] &= ~np.outer(solid, open_bottom)
    return compat, border


@dataclass(frozen=True)
class PlacedPart:
    shape: Shape
    color: BrickColor
    layer: int  # bottom layer
    x: int  # min-corner cell
    z: int

    @property
    def top(self) -> int:
        """The part's top layer."""
        return self.layer + self.shape.size_y - 1

    def cells(self) -> list[tuple[int, int, int]]:
        """(y, z, x) of every cell the part covers."""
        return [
            (self.layer + dy, self.z + dz, self.x + dx)
            for dy in range(self.shape.size_y)
            for dz, dx in self.shape.footprint
        ]

    def bottom_cells(self) -> list[tuple[int, int, int]]:
        """(y, z, x) of the cells on the part's bottom layer."""
        return [(self.layer, self.z + dz, self.x + dx) for dz, dx in self.shape.footprint]

    def top_cells(self) -> list[tuple[int, int, int]]:
        """(y, z, x) of the cells on the part's top layer."""
        return [(self.top, self.z + dz, self.x + dx) for dz, dx in self.shape.footprint]

    def seated_cells(self) -> list[tuple[int, int, int]]:
        """(y, z, x) of the bottom cells with a flat underside: the ones that rest on studs below."""
        return [(self.layer, self.z + dz, self.x + dx) for dz, dx in self.shape.footprint if self.shape.seated(dz, dx)]

    def stud_cells(self) -> list[tuple[int, int, int]]:
        """(y, z, x) of the top cells that carry a stud."""
        return [(self.top, self.z + dz, self.x + dx) for dz, dx in self.shape.footprint if self.shape.studded(dz, dx)]

    def centre(self) -> tuple[float, float]:
        """(x, z) of the footprint's centroid, in studs from the grid's corner (cell (x, z) spans [x, x + 1])."""
        footprint = self.shape.footprint
        return (self.x + sum(dx for _, dx in footprint) / len(footprint) + 0.5,
                self.z + sum(dz for dz, _ in footprint) / len(footprint) + 0.5)

    def placement(self) -> Placement:
        """LDraw placement: the part's origin (on its top face for most parts) turned with the part."""
        origin_x, origin_z = self.shape.geometry.origin
        rotation = turn_rotation(self.shape.turn) if self.shape.turn else IDENTITY
        height = self.layer + self.shape.size_y if self.shape.part.origin_top else self.layer
        position = stud_position(self.x + origin_x, self.z + origin_z, height)
        return Placement(self.color.ldraw, position, rotation, self.shape.part.ldraw)


def extract_parts(grid: np.ndarray, parts: PartSet) -> tuple[list[PlacedPart], list[str]]:
    """Decode a solved (Y, Z, X) grid into placed parts.

    Returns ``(placed, errors)``; ``errors`` lists every incomplete part, cell not covered by
    exactly one complete part, part resting on a studless top and part right under an unseated
    bottom, so an empty list means every part is whole and those faces are clear.
    """
    placed: list[PlacedPart] = []
    errors: list[str] = []
    covered = np.zeros(grid.shape, dtype=np.int64)
    for y, z, x in zip(*np.nonzero(parts.solid[grid])):
        info = parts.infos[grid[y, z, x]]
        anchor_z, anchor_x = info.shape.footprint[0]  # (0, 0) unless the part's min corner is a notch
        if (info.offset_x, info.offset_y, info.offset_z) != (anchor_x, 0, anchor_z):
            continue
        part = PlacedPart(info.shape, info.color, int(y), int(x) - anchor_x, int(z) - anchor_z)
        missing = []
        for cell in part.cells():
            inside = all(0 <= c < n for c, n in zip(cell, grid.shape))
            expected = TileInfo(info.shape, cell[2] - part.x, cell[1] - part.z, info.color, cell[0] - part.layer)
            if not inside or parts.infos[grid[cell]] != expected:
                missing.append(cell)
        if missing:
            errors.append(f"{info.shape.name} at {(y, z, x)} is incomplete at {missing}")
            continue
        placed.append(part)
        for cell in part.cells():
            covered[cell] += 1
    solid = parts.solid[grid]
    for cell in zip(*np.nonzero(solid & (covered != 1))):
        errors.append(f"cell {tuple(int(c) for c in cell)} covered by {covered[cell]} complete parts")
    for part in placed:
        studs = set(part.stud_cells())
        if part.top + 1 < grid.shape[0]:
            if any(solid[y + 1, z, x] for y, z, x in part.top_cells() if (y, z, x) not in studs):
                errors.append(f"something sits on the {part.shape.name} at {(part.layer, part.z, part.x)}")
        seated = set(part.seated_cells())
        if part.layer > 0 and any(solid[y - 1, z, x] for y, z, x in part.bottom_cells() if (y, z, x) not in seated):
            errors.append(f"something is under the open bottom of the {part.shape.name} at {(part.layer, part.z, part.x)}")
    return placed, errors
