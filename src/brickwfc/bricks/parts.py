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

from dataclasses import dataclass, replace
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
    (``seated_cells``). ``origin_top``: the origin is on the top face (most parts), else on the bottom;
    ``origin_plates`` (M12d), when set, puts it that many plates above the bottom instead (a part whose box is
    taller than the face its origin is on).
    ``aliases``: older LDraw file names of the same part ("~Moved to" files) that models still use.
    ``sloped_rows``: for a slope falling toward its local -Z, how many rows (from the low end) its sloped face
    covers: its top for a plain slope, its bottom for an inverted one (the parts with ``seated_cells``). Only
    the preview draws it (``build.slope_profiles``); the model treats the part as its box.
    ``ground_only`` (M12d, baseplates): the part cannot rest on studs (``seated_cells`` is empty), so it only goes on
    the ground, where its whole bottom touches the table (``PlacedPart.contact_cells``).
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
    sloped_rows: int = 0
    ground_only: bool = False
    origin_plates: int | None = None

    def __hash__(self) -> int:
        # Equal parts have the same name and file; hashing every field (a baseplate's 512 cells, three times) on each
        # cached ``geometry`` lookup dominated build time (M12d).
        return hash((self.name, self.ldraw))

    @property
    def origin_layer(self) -> int:
        """Plates from the bottom of the part's box up to its LDraw origin."""
        if self.origin_plates is not None:
            return self.origin_plates
        return self.height if self.origin_top else 0

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
)


def _corner(kind: Kind, file: str) -> Part:
    """A 2x2 corner part (an L of 3 cells). Its origin is on the corner stud; the arms run along +X and +Z."""
    return Part(f"{kind}2x2_corner", f"{file}.dat", 2, 2, HEIGHTS[kind], True, kind, cells=((0, 0), (1, 0), (0, 1)))


def _slope(name: str, file: str, width: int, depth: int, stud_rows: int = 1, height: int = 3,
           inverted: bool = False, aliases: tuple[str, ...] = ()) -> Part:
    """A slope ``depth`` studs along its fall (LDraw -Z) and ``width`` across (X). As in its .dat file, the
    origin is on the top face over the back row (z = 0) and the slope runs toward -Z. A plain slope has
    studs on its ``stud_rows`` back rows and a flat bottom; an inverted one has studs everywhere and a flat
    bottom under its back row only."""
    cells = tuple((x - (width - 1) / 2, -z) for z in range(depth) for x in range(width))
    back = tuple(c for c in cells if c[1] > -stud_rows)
    return Part(name, f"{file}.dat", width, depth, height, True, "slope", cells,
                stud_cells=cells if inverted else back, seated_cells=back if inverted else None,
                aliases=tuple(f"{a}.dat" for a in aliases), sloped_rows=depth - (1 if inverted else stud_rows))


def _roof(name: str, file: str, width: int, depth: int, height: int = 3, origin_top: bool = True,
          aliases: tuple[str, ...] = ()) -> Part:
    """A slope with no stud at all (a ridge or a 1x1 cheese slope): a studless box, centred on its origin."""
    return Part(name, f"{file}.dat", width, depth, height, False, "slope", origin_top=origin_top,
                aliases=tuple(f"{a}.dat" for a in aliases))


# Non-rectangular parts (M12b), after the M8 ones so that style statistics keep their part indices.
# Geometry (cells, studs, flat bottoms, origin, height) read from the LDraw library's .dat files.
_M12B_LOOKALIKES = _family("brick", "4216:1x2", suffix=True)  # brick with groove
_CORNERS = [_corner("plate", "2420"), _corner("brick", "2357")]
_CORNERS[0] = replace(_CORNERS[0], aliases=("63325.dat",))  # M12d: 63325 is an alias file of 2420
_SLOPES = [
    _slope("slope45_2x1", "3040b", 1, 2),
    _slope("slope45_2x2", "3039", 2, 2),
    _slope("slope45_2x3", "3038", 3, 2),
    _slope("slope45_2x4", "3037", 4, 2),
    _slope("slope45_2x8", "4445", 8, 2),
    _slope("slope33_3x1", "4286", 1, 3),
    _slope("slope33_3x2", "3298", 2, 3),
    _slope("slope33_3x4", "3297", 4, 3),
    _slope("slope18_4x2", "30363", 2, 4),
    _slope("slope65_2x1x2", "60481a", 1, 2, height=6, aliases=("60481",)),
    _slope("slope75_2x1x3", "4460a", 1, 2, height=9, aliases=("4460",)),
    _slope("slope45inv_2x1", "3665a", 1, 2, inverted=True, aliases=("3665", "3665b")),  # 3665b: M12d
    _slope("slope45inv_2x2", "3660", 2, 2, inverted=True, aliases=("3660a",)),
    _slope("slope33inv_3x2", "3747a", 2, 3, inverted=True),
    # Corner slopes: 2x2 with one stud (convex) or three (concave); the sloped cells are studless.
    Part("slope45convex_2x2", "3045.dat", 2, 2, 3, True, "slope", ((0, 0), (1, 0), (0, -1), (1, -1)),
         stud_cells=((0, 0),)),
    Part("slope45concave_2x2", "3046.dat", 2, 2, 3, True, "slope", ((0, 0), (1, 0), (0, -1), (1, -1)),
         stud_cells=((0, 0), (1, 0), (0, -1))),
    _roof("slope45double_2x2", "3043", 2, 2),
    _roof("slope45double_2x3", "3042", 3, 2),
    _roof("slope45double_2x4", "3041", 4, 2),
    _roof("slope45double_2x1", "3044b", 1, 2, aliases=("3044",)),
    _roof("slope31_1x1x2", "54200", 1, 1, height=2, origin_top=False),  # "cheese slope"; origin on its bottom
    _roof("slope45double_1x1x2", "35464", 1, 1, height=2, origin_top=False),
]


def _mapped(name: str, file: str, kind: Kind, height: int, rows: Sequence[str], first: tuple[float, float],
            origin_top: bool = True, origin_plates: int | None = None, aliases: tuple[str, ...] = ()) -> Part:
    """A part from its cell map, as ``ldraw.library`` prints it: one string per row of cells along LDraw +Z, one
    character per cell along +X, starting at the cell centred on ``first`` (x, z) studs from the origin.
    ``S``: a stud on top and a flat bottom; ``s``: a stud, bottom not flat; ``#``: flat bottom, no stud; ``.``: in
    the footprint, neither; a space: not in the footprint. Width and depth are the map's."""
    cells, studs, seats = [], [], []
    for j, row in enumerate(rows):
        for i, char in enumerate(row):
            if char == " ":
                continue
            cell = (first[0] + i, first[1] + j)
            cells.append(cell)
            if char in "Ss":
                studs.append(cell)
            if char in "S#":
                seats.append(cell)
    return Part(name, f"{file}.dat", max(len(r) for r in rows), len(rows), height, bool(studs), kind, tuple(cells),
                stud_cells=tuple(studs), seated_cells=tuple(seats), origin_top=origin_top, origin_plates=origin_plates,
                aliases=tuple(f"{a}.dat" for a in aliases))


def _box(name: str, file: str, kind: Kind, width: int, depth: int, height: int, studs: bool = True,
         aliases: tuple[str, ...] = ()) -> Part:
    """A rectangular part of any height (studs on every top cell, or none; flat bottom), centred on its origin."""
    return Part(name, f"{file}.dat", width, depth, height, studs, kind, aliases=tuple(f"{a}.dat" for a in aliases))


def _baseplate(name: str, file: str, width: int, depth: int) -> Part:
    """A baseplate: 4 LDU thick, modelled as one plate (the box holds the part); it lies on the table and takes no
    stud (``ground_only``: no seated cells)."""
    cells = tuple((x - (width - 1) / 2, z - (depth - 1) / 2) for z in range(depth) for x in range(width))
    return Part(name, f"{file}.dat", width, depth, 1, True, "plate", cells, stud_cells=cells, seated_cells=(),
                ground_only=True)


# M12d batch 1: parts the existing mechanisms describe, appended so that earlier parts keep their style indices.
# Geometry from the parts' .dat files (``ldraw.library``; facts in tests/test_catalog_shapes.py). A cell is seated
# where the bottom plane covers at least 10% of it (rounded corners leave slivers below that). A stud a plate or
# more below the box's top (6091, 6005, 92946) is hidden inside the box: the part counts as studless there.
_M12D_PLAIN = (
    _family("plate", "4282:2x16 3029:4x12 3028:6x12 3027:6x16")
    + [_box("brick1x2x2", "3245c", "brick", 2, 1, 6, aliases=("3245a",)),
       _box("brick1x2x5", "2454", "brick", 2, 1, 15),
       _box("brick1x1x3", "14716", "brick", 1, 1, 9),
       _box("brick1x1x5", "2453a", "brick", 1, 1, 15, aliases=("2453",)),
       _baseplate("baseplate16x32", "3857", 32, 16),
       _baseplate("baseplate32x32", "3811", 32, 32)]
)
_M12D_LOOKALIKES = (
    _family("brick", "4217:1x14 30136:1x2 98283:1x2 15533:1x4 3700:1x2 6541:1x1 32064a:1x2 32064b:1x2 "
                     "59900:1x1 4589:1x1", suffix=True)
    + _family("tile", "3070a:1x1 98138:1x1 25269:1x1", suffix=True)
    + _family("plate", "85861:1x1 24866:1x1 35480:1x2", suffix=True)
    + [_box("panel1x1x1_6231", "6231", "brick", 1, 1, 3, studs=False),
       _box("panel1x2x1_4865a", "4865a", "brick", 2, 1, 3, studs=False),
       _box("panel1x2x1_4865b", "4865b", "brick", 2, 1, 3, studs=False),
       _box("panel1x2x2_87552", "87552", "brick", 2, 1, 6),
       _box("panel1x2x2_4864b", "4864b", "brick", 2, 1, 6),
       _box("panel1x2x3_2362b", "2362b", "brick", 2, 1, 9)]
)
_M12D_CELLS = [
    # corners and round corners (the box is kept where the real part is rounded off)
    Part("tile2x2_corner", "14719.dat", 2, 2, 1, False, "tile", cells=((0, 0), (1, 0), (0, 1))),
    _mapped("plate3x3_round_corner", "30357", "plate", 1, ["SSS", "SSS", "SS."], (0, 0)),
    _mapped("tile2x2_round_corner", "27925", "tile", 1, ["#.", "##"], (0, -1)),
    _mapped("brick2x2_round_corner", "3063b", "brick", 3, ["S.", "#S"], (0, -1)),
    _mapped("brick2x2_round_corner_85080", "85080", "brick", 3, ["S.", "#S"], (0, -1)),
    # plates with studs on some cells only
    _mapped("plate1x4_2studs", "92593", "plate", 1, ["S##S"], (-1.5, 0)),
    _mapped("plate1x4_2studs_41740", "41740", "plate", 1, ["S##S"], (-1.5, 0)),
    _mapped("plate2x2_2studs", "33909", "plate", 1, ["##", "SS"], (-0.5, -0.5)),
    _mapped("plate4x4_4studs", "6179", "plate", 1, ["####", "####", "####", "SSSS"], (-1.5, -1.5)),
    _mapped("plate2x3_hole", "3176", "plate", 1, ["##", "SS", "SS"], (-0.5, -1.5)),
    # arches: seated at their ends only (the box stays full)
    _mapped("arch1x4", "3659", "brick", 3, ["SssS"], (-1.5, 0)),
    _mapped("arch1x6", "3455", "brick", 3, ["SssssS"], (-2.5, 0)),
    _mapped("arch1x6_raised", "92950", "brick", 3, ["SssssS"], (-2.5, 0)),
    _mapped("arch1x4x2", "6182", "brick", 6, ["SssS"], (-1.5, 0)),
    _mapped("arch1x6x2", "3307", "brick", 6, ["SssssS"], (-2.5, 0)),
    _mapped("arch1x3x2_curved", "6005", "slope", 6, ["#", ".", "."], (0, -2)),
]
_M12D_SLOPES = [
    _slope("slope65_2x2x2", "3678b", 2, 2, height=6, aliases=("3678a",)),
    _slope("slope75_2x2x3", "3684c", 2, 2, height=9),
    _slope("slope33_3x3", "4161", 3, 3),
    _mapped("slope33_3x6", "3939", "slope", 3, ["######", "#....#", "S....S"], (-2.5, -2)),
    _mapped("slope33convex_3x3", "3675", "slope", 3, ["###", "###", "S##"], (0, -2)),
    _roof("slope33double_2x2", "3300", 2, 2),
    _roof("slope33double_2x4", "3299", 4, 2),
    _roof("slope45triple_1x2", "3048b", 2, 1),
    _roof("slope31_1x2x2", "85984", 2, 1, height=2, origin_top=False),
    _mapped("slope45_2x1_cutout", "92946", "slope", 3, ["#", "#"], (0, -0.5), origin_plates=1),
    # curved bricks and slopes: studless boxes
    _mapped("curved1x2x4_6091", "6091", "slope", 4, ["#", "."], (0, -1)),
    _roof("curved1x4x4_6191", "6191", 4, 1, height=4),
    _roof("curved1x2_37352", "37352", 2, 1),
    _mapped("curved2x3_6215", "6215", "brick", 3, ["SS#", "SS#"], (-0.5, -0.5)),
    _mapped("curved3x1", "50950", "slope", 3, ["#", "#", "."], (0, -1)),
    _mapped("curved4x1", "61678", "slope", 3, ["#", "#", ".", "."], (0, -1.5)),
    _mapped("curved2x1", "11477", "slope", 2, ["#", "."], (0, -0.5), origin_top=False),
    _mapped("curved2x2x2", "15068", "slope", 2, ["##", ".."], (-0.5, -0.5), origin_top=False),
    _mapped("curved4x1_double", "93273", "slope", 2, ["#", ".", ".", "#"], (0, -1.5), origin_top=False),
    _roof("curved1x1x2_49307", "49307", 1, 1, height=2, origin_top=False),
]
M12D_BATCH1 = _M12D_PLAIN + _M12D_LOOKALIKES + _M12D_CELLS + _M12D_SLOPES
CATALOG: dict[str, Part] = {p.name: p for p in _PLAIN + _LOOKALIKES + _M12B_LOOKALIKES + _CORNERS + _SLOPES + M12D_BATCH1}
BY_FILE: dict[str, Part] = {file: p for p in CATALOG.values() for file in (p.ldraw, *p.aliases)}
# The M8 catalog (before corners and slopes) and the M12b one (before M12d), for before/after comparisons.
M8_FILES: dict[str, Part] = {p.ldraw: p for p in _PLAIN + _LOOKALIKES}
M12B_FILES: dict[str, Part] = {file: p for p in _PLAIN + _LOOKALIKES + _M12B_LOOKALIKES + _CORNERS + _SLOPES
                               for file in (p.ldraw, *p.aliases) if file not in ("3665b.dat", "63325.dat")}

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
        (float(-min_x) + 0.0, float(-min_z) + 0.0), 1 + max(dx for _, dx in footprint), 1 + max(dz for dz, _ in footprint),
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

    def contact_cells(self) -> list[tuple[int, int, int]]:
        """(y, z, x) of the bottom cells that bear on what is below: the seated cells, and on the ground a
        ground-only part's whole bottom (a baseplate lies flat on the table)."""
        if self.shape.part.ground_only and self.layer == 0:
            return self.bottom_cells()
        return self.seated_cells()

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
        height = self.layer + self.shape.part.origin_layer
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
