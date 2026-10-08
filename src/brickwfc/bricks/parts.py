"""Multi-cell parts as WFC tiles (M5, M8).

A part occupies a box of cells: a rectangle of stud cells, ``height`` plate layers tall (plates and
tiles 1, bricks 3). Each cell of a placed part holds the tile (shape, offset inside the part, color),
where a *shape* is a part in one orientation. Adjacency rules make parts whole: if a tile's neighbor
in direction d lies inside its part, that neighbor must be exactly the matching tile of the same part;
otherwise the neighbor must also sit on a part face (or be empty). Border masks keep parts inside the
grid. Tiles have no studs, so the cell above a tile must be empty.

Grids are indexed (y, z, x), as in ``tileset.GRID3D``.
"""

from __future__ import annotations

from dataclasses import dataclass
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
Kind = Literal["plate", "brick", "tile"]


@dataclass(frozen=True)
class Part:
    """A part type. ``width`` x ``depth`` studs along LDraw X x Z in its default orientation,
    ``height`` plate layers tall; ``studs`` is False for tiles (smooth top)."""

    name: str
    ldraw: str
    width: int
    depth: int
    height: int = 1
    studs: bool = True
    kind: Kind = "plate"


HEIGHTS: dict[Kind, int] = {"plate": 1, "brick": 3, "tile": 1}


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
)
CATALOG: dict[str, Part] = {p.name: p for p in _PLAIN + _LOOKALIKES}
BY_FILE: dict[str, Part] = {p.ldraw: p for p in CATALOG.values()}

# M4-M11 used these four plates only; experiments that reproduce those tables still do.
PLATES: dict[str, Part] = {name: CATALOG[name] for name in ("plate1x1", "plate1x2", "plate2x2", "plate2x4")}
PLATE_FILES: dict[str, Part] = {p.ldraw: p for p in PLATES.values()}


def family(kind: Kind, lookalikes: bool = False) -> list[Part]:
    """Every catalog part of one kind (plain ones only, unless ``lookalikes``)."""
    return [p for p in CATALOG.values() if p.kind == kind and (lookalikes or p in _PLAIN)]


@dataclass(frozen=True)
class Shape:
    """A part in one orientation, with its footprint along the grid's x and z axes."""

    part: Part
    rotated: bool

    @property
    def size_x(self) -> int:
        return self.part.depth if self.rotated else self.part.width

    @property
    def size_z(self) -> int:
        return self.part.width if self.rotated else self.part.depth

    @property
    def size_y(self) -> int:
        return self.part.height

    @property
    def cells(self) -> int:
        return self.size_x * self.size_y * self.size_z

    @property
    def name(self) -> str:
        return f"{self.part.name}{'_r90' if self.rotated else ''}"


def shapes_of(parts: Sequence[Part]) -> list[Shape]:
    """Every distinct orientation of each part (square parts have one)."""
    shapes = []
    for part in parts:
        shapes.append(Shape(part, rotated=False))
        if part.width != part.depth:
            shapes.append(Shape(part, rotated=True))
    return shapes


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
    def stud_top(self) -> bool:
        """A cell on the part's top layer that carries a stud (something may click onto it)."""
        return self.shape is not None and self.offset_y == self.shape.size_y - 1 and self.shape.part.studs

    def inside(self, dx: int, dz: int, dy: int = 0) -> bool:
        """Whether the cell at (dx, dz, dy) from this one belongs to the same part."""
        if self.shape is None:
            return False
        x, z, y = self.offset_x + dx, self.offset_z + dz, self.offset_y + dy
        return 0 <= x < self.shape.size_x and 0 <= z < self.shape.size_z and 0 <= y < self.shape.size_y

    def footprint(self) -> list[tuple[int, int]]:
        """(dz, dx) offsets from this cell to every cell of its part's layer, itself included."""
        if self.shape is None:
            return []
        return [
            (z - self.offset_z, x - self.offset_x) for z in range(self.shape.size_z) for x in range(self.shape.size_x)
        ]


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
            for z in range(shape.size_z):
                for x in range(shape.size_x):
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
    On top of that, nothing may sit on a tile (the studless top of a part). Rules are symmetric.
    """
    solid = np.array([i.solid for i in infos])
    shape_ids: dict[Shape, int] = {}
    shape_id = np.array([shape_ids.setdefault(i.shape, len(shape_ids)) if i.solid else -1 for i in infos])
    color_ids: dict[str, int] = {}
    color_id = np.array([color_ids.setdefault(i.color.name, len(color_ids)) if i.solid else -1 for i in infos])
    offset = np.array([(i.offset_y, i.offset_z, i.offset_x) for i in infos])
    size = np.array([(i.shape.size_y, i.shape.size_z, i.shape.size_x) if i.solid else (1, 1, 1) for i in infos])
    same_part = solid[:, None] & (shape_id[:, None] == shape_id[None, :]) & (color_id[:, None] == color_id[None, :])

    count = len(infos)
    compat = np.ones((len(GRID3D.directions), count, count), dtype=bool)
    border = np.ones((len(GRID3D.directions), count), dtype=bool)
    for d, step in enumerate(GRID3D.offsets):
        step = np.array(step)
        continues = solid & np.all((offset + step >= 0) & (offset + step < size), axis=1)
        continues_back = solid & np.all((offset - step >= 0) & (offset - step < size), axis=1)
        next_tile = same_part & np.all(offset[None, :, :] == offset[:, None, :] + step, axis=2)
        compat[d] = np.where(continues[:, None], next_tile, ~continues_back[None, :])
        border[d] = ~continues

    studless_top = np.array([i.solid and i.offset_y == i.shape.size_y - 1 and not i.shape.part.studs for i in infos])
    compat[UP] &= ~np.outer(studless_top, solid)
    compat[DOWN] &= ~np.outer(solid, studless_top)
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
            for dz in range(self.shape.size_z)
            for dx in range(self.shape.size_x)
        ]

    def bottom_cells(self) -> list[tuple[int, int, int]]:
        """(y, z, x) of the cells on the part's bottom layer."""
        return [cell for cell in self.cells() if cell[0] == self.layer]

    def top_cells(self) -> list[tuple[int, int, int]]:
        """(y, z, x) of the cells on the part's top layer."""
        return [cell for cell in self.cells() if cell[0] == self.top]

    def placement(self) -> Placement:
        """LDraw placement: origin at the center of the part's top face."""
        center_x = self.x + (self.shape.size_x - 1) / 2
        center_z = self.z + (self.shape.size_z - 1) / 2
        rotation = ROTATE_Y_90 if self.shape.rotated else IDENTITY
        top = self.layer + self.shape.size_y
        return Placement(self.color.ldraw, stud_position(center_x, center_z, top), rotation, self.shape.part.ldraw)


def extract_parts(grid: np.ndarray, parts: PartSet) -> tuple[list[PlacedPart], list[str]]:
    """Decode a solved (Y, Z, X) grid into placed parts.

    Returns ``(placed, errors)``; ``errors`` lists every incomplete part, cell not covered by
    exactly one complete part, and part resting on a tile, so an empty list means every part is
    whole and nothing sits on a studless top.
    """
    placed: list[PlacedPart] = []
    errors: list[str] = []
    covered = np.zeros(grid.shape, dtype=np.int64)
    for y, z, x in zip(*np.nonzero(parts.solid[grid])):
        info = parts.infos[grid[y, z, x]]
        if (info.offset_x, info.offset_y, info.offset_z) != (0, 0, 0):
            continue
        part = PlacedPart(info.shape, info.color, int(y), int(x), int(z))
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
        if not part.shape.part.studs and part.top + 1 < grid.shape[0]:
            if any(solid[y + 1, z, x] for y, z, x in part.top_cells()):
                errors.append(f"something sits on the {part.shape.name} at {(part.layer, part.z, part.x)}")
    return placed, errors
