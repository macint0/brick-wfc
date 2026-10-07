"""Multi-cell parts as WFC tiles (M5).

A part occupies a rectangle of stud cells on one plate layer. Each cell of a placed part holds
the tile (shape, offset inside the part, color), where a *shape* is a part in one orientation.
Horizontal adjacency rules make parts whole: if a tile's neighbor in direction d lies inside its
part, that neighbor must be exactly the matching tile of the same part; otherwise the neighbor
must also sit on a part edge (or be empty). Border masks keep parts inside the grid.

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


@dataclass(frozen=True)
class Part:
    """A part type. ``width`` x ``depth`` studs along LDraw X x Z in its default orientation."""

    name: str
    ldraw: str
    width: int
    depth: int


PLATES: dict[str, Part] = {
    p.name: p
    for p in [
        Part("plate1x1", "3024.dat", 1, 1),
        Part("plate1x2", "3023.dat", 2, 1),
        Part("plate2x2", "3022.dat", 2, 2),
        Part("plate2x4", "3020.dat", 4, 2),
    ]
}


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

    @property
    def solid(self) -> bool:
        return self.shape is not None

    def inside(self, dx: int, dz: int) -> bool:
        """Whether the cell at (dx, dz) from this one belongs to the same part."""
        if self.shape is None:
            return False
        x, z = self.offset_x + dx, self.offset_z + dz
        return 0 <= x < self.shape.size_x and 0 <= z < self.shape.size_z

    def footprint(self) -> list[tuple[int, int]]:
        """(dz, dx) offsets from this cell to every cell of its part, itself included."""
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
        """(T,) bool: which tiles are part of a plate."""
        return np.array([info.solid for info in self.infos])


def part_tileset(
    parts: Sequence[Part],
    colors: Sequence[BrickColor],
    empty_weight: float = 1.0,
    support: Support = "none",
    coverage: Mapping[tuple[str, str], float] | None = None,
) -> PartSet:
    """Tiles for every (shape, offset, color) plus empty.

    Weights: by default each part type gets the same total weight, split evenly over its
    orientations, offsets, and colors, so part types cover a similar share of cells.
    ``coverage`` instead maps (shape name, color name) to a target share of cells (e.g. learned
    from real sets, M7); pairs missing from it get no tiles. Either way the solid tiles' weights
    sum to ``len(parts)``, so ``empty_weight`` means the same thing in both modes.
    ``support="cell"`` adds M4's local rule: no solid cell directly above an empty one.
    """
    shapes = shapes_of(parts)
    tile_specs: list[tuple[Shape, BrickColor, float]] = []  # weight per tile of each (shape, color)
    for shape in shapes:
        area = shape.size_x * shape.size_z
        orientations = sum(1 for s in shapes if s.part == shape.part)
        for color in colors:
            if coverage is None:
                tile_specs.append((shape, color, 1.0 / (orientations * area * len(colors))))
            elif coverage.get((shape.name, color.name), 0) > 0:
                tile_specs.append((shape, color, coverage[(shape.name, color.name)] / area))
    total = sum(w * s.size_x * s.size_z for s, _, w in tile_specs)

    infos: list[TileInfo] = [TileInfo(None)]
    weights: list[float] = [empty_weight]
    for shape, color, weight in tile_specs:
        for z in range(shape.size_z):
            for x in range(shape.size_x):
                infos.append(TileInfo(shape, x, z, color))
                weights.append(weight * len(parts) / total)

    count = len(infos)
    compat = np.ones((len(GRID3D.directions), count, count), dtype=bool)
    border = np.ones((len(GRID3D.directions), count), dtype=bool)
    for d in HORIZONTAL:
        _, dz, dx = GRID3D.offsets[d]
        for a, info_a in enumerate(infos):
            border[d, a] = not info_a.inside(dx, dz)
            for b, info_b in enumerate(infos):
                if info_a.inside(dx, dz):
                    compat[d, a, b] = (
                        info_b.shape == info_a.shape
                        and info_b.color == info_a.color
                        and (info_b.offset_x, info_b.offset_z) == (info_a.offset_x + dx, info_a.offset_z + dz)
                    )
                else:
                    compat[d, a, b] = not info_b.inside(-dx, -dz)

    if support == "cell":
        solid = np.array([info.solid for info in infos])
        compat[DOWN] = ~np.outer(solid, ~solid)
        compat[UP] = ~np.outer(~solid, solid)

    names = [EMPTY] + [f"{i.shape.name}_x{i.offset_x}z{i.offset_z}_{i.color.name}" for i in infos[1:]]
    display = [EMPTY_DISPLAY_COLOR] + [i.color.rgb for i in infos[1:]]
    tileset = Tileset(tuple(names), tuple(display), np.array(weights), compat, GRID3D, border)
    return PartSet(tileset, tuple(infos))


@dataclass(frozen=True)
class PlacedPart:
    shape: Shape
    color: BrickColor
    layer: int
    x: int  # min-corner cell
    z: int

    def cells(self) -> list[tuple[int, int, int]]:
        """(y, z, x) of every cell the part covers."""
        return [
            (self.layer, self.z + dz, self.x + dx) for dz in range(self.shape.size_z) for dx in range(self.shape.size_x)
        ]

    def placement(self) -> Placement:
        """LDraw placement: origin at the center of the part's top face."""
        center_x = self.x + (self.shape.size_x - 1) / 2
        center_z = self.z + (self.shape.size_z - 1) / 2
        rotation = ROTATE_Y_90 if self.shape.rotated else IDENTITY
        return Placement(self.color.ldraw, stud_position(center_x, center_z, self.layer + 1), rotation, self.shape.part.ldraw)


def extract_parts(grid: np.ndarray, parts: PartSet) -> tuple[list[PlacedPart], list[str]]:
    """Decode a solved (Y, Z, X) grid into placed parts.

    Returns ``(placed, errors)``; ``errors`` lists every incomplete part or cell not covered by
    exactly one complete part, so an empty list means every part is whole.
    """
    placed: list[PlacedPart] = []
    errors: list[str] = []
    covered = np.zeros(grid.shape, dtype=np.int64)
    for y, z, x in zip(*np.nonzero(parts.solid[grid])):
        info = parts.infos[grid[y, z, x]]
        if (info.offset_x, info.offset_z) != (0, 0):
            continue
        part = PlacedPart(info.shape, info.color, int(y), int(x), int(z))
        missing = []
        for cell in part.cells():
            inside = all(0 <= c < n for c, n in zip(cell, grid.shape))
            expected = TileInfo(info.shape, cell[2] - part.x, cell[1] - part.z, info.color)
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
    return placed, errors
