"""M12b: non-rectangular parts (corners) in the catalog: geometry against the LDraw files, integrity,
support, physics, LDraw round trips, and builds from the M8 catalog unchanged."""

import hashlib
from pathlib import Path

import numpy as np
import pytest

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.catalog_check import layout
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import (
    BY_FILE,
    CATALOG,
    PartSet,
    PlacedPart,
    Shape,
    canonical,
    extract_parts,
    part_tileset,
    shapes_of,
)
from brickwfc.bricks.physics import required_clutch, tipping_clusters
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.support import is_stable
from brickwfc.bricks.voxelize import voxelize
from brickwfc.ldraw.export import PLATE_LDU, STUD_LDU, write_ldr
from brickwfc.ldraw.mpd import flatten
from brickwfc.wfc import run

RED, BLUE = colors_by_name(["red", "blue"])
BUILDS = 100

# Facts read from the LDraw library's part files (resolved through their subfiles): top stud positions
# (x, z) and the body's extent along x, z and y, in LDU from the part origin (-Y up; studs not counted).
LDRAW = {
    "3020.dat": {"studs": [(x, z) for x in (-30, -10, 10, 30) for z in (-10, 10)], "x": (-40, 40), "z": (-20, 20), "y": (0, 8)},
    "3001.dat": {"studs": [(x, z) for x in (-30, -10, 10, 30) for z in (-10, 10)], "x": (-40, 40), "z": (-20, 20), "y": (0, 24)},
    "2420.dat": {"studs": [(0, 0), (20, 0), (0, 20)], "x": (-10, 30), "z": (-10, 30), "y": (0, 8)},
    "2357.dat": {"studs": [(0, 0), (20, 0), (0, 20)], "x": (-10, 30), "z": (-10, 30), "y": (0, 24)},
}
CORNERS = [CATALOG["plate2x2_corner"], CATALOG["brick2x2_corner"]]
FAMILY = CORNERS + [CATALOG[n] for n in ("plate1x1", "plate1x2", "brick1x2", "brick2x2", "tile1x1")]


def check_build(grid: np.ndarray, parts: PartSet) -> list[PlacedPart]:
    placed, errors = extract_parts(grid, parts)
    assert errors == []
    assert is_stable(placed, parts.solid[grid])
    return placed


def test_corner_has_four_orientations_of_three_cells() -> None:
    for part in CORNERS:
        shapes = shapes_of([part])
        assert [s.turn for s in shapes] == [0, 1, 2, 3]
        assert all(s.cells == 3 * part.height and (s.size_x, s.size_z) == (2, 2) for s in shapes)
        notches = {next((dz, dx) for dz in (0, 1) for dx in (0, 1) if not s.covers(dz, dx)) for s in shapes}
        assert notches == {(0, 0), (0, 1), (1, 0), (1, 1)}
    # Rectangles keep their M8 orientations and names; turning them twice gives the same shape.
    plate = CATALOG["plate2x4"]
    assert [s.name for s in shapes_of([plate])] == ["plate2x4", "plate2x4_r90"]
    assert canonical(plate, 2) == Shape(plate, 0) and canonical(plate, 3) == Shape(plate, True)
    assert [s.name for s in shapes_of([CATALOG["plate2x2"]])] == ["plate2x2"]


@pytest.mark.parametrize("file", list(LDRAW))
def test_placement_matches_the_ldraw_part(file: str) -> None:
    """Every orientation's .ldr placement puts the real part's studs on the model's stud cells and its
    body exactly over the model's cells and layers."""
    part = BY_FILE[file]
    facts = LDRAW[file]
    for shape in shapes_of([part]) + [Shape(part, turn) for turn in range(4)]:
        placed = PlacedPart(shape, RED, 2, 3, 4)
        p = placed.placement()
        r, origin = np.array(p.rotation, dtype=float).reshape(3, 3), np.array(p.position)
        studs = {tuple(np.round((r @ (x, 0, z) + origin)[[0, 2]] / STUD_LDU).astype(int)) for x, z in facts["studs"]}
        assert studs == {(x, z) for _, z, x in placed.stud_cells()}, shape.name
        corners = np.array([r @ (x, 0, z) + origin for x in facts["x"] for z in facts["z"]])
        assert corners[:, 0].min() / STUD_LDU == placed.x - 0.5 and corners[:, 0].max() / STUD_LDU == placed.x + shape.size_x - 0.5
        assert corners[:, 2].min() / STUD_LDU == placed.z - 0.5 and corners[:, 2].max() / STUD_LDU == placed.z + shape.size_z - 0.5
        top, bottom = (origin[1] + y for y in facts["y"])
        assert (-top / PLATE_LDU, -bottom / PLATE_LDU) == (placed.top + 1, placed.layer)


def test_corner_integrity_rules() -> None:
    parts = part_tileset([CATALOG["plate2x2_corner"], CATALOG["plate1x1"]], [RED])
    index = {info: t for t, info in enumerate(parts.infos)}
    corner = Shape(CATALOG["plate2x2_corner"], 0)
    notch = next((dz, dx) for dz in (0, 1) for dx in (0, 1) if not corner.covers(dz, dx))
    assert len([i for i in parts.infos if i.shape == corner]) == 3
    # A 1x1 plate fits in the notch: every cell is covered once, the corner is whole.
    grid = np.full((1, 2, 2), index[parts.infos[0]])
    for dz, dx in corner.footprint:
        grid[0, dz, dx] = next(t for t, i in enumerate(parts.infos) if i.shape == corner and (i.offset_z, i.offset_x) == (dz, dx))
    grid[0, notch[0], notch[1]] = next(t for t, i in enumerate(parts.infos) if i.solid and i.shape.part.name == "plate1x1")
    placed, errors = extract_parts(grid, parts)
    assert errors == [] and sorted(p.shape.name for p in placed) == ["plate1x1", "plate2x2_corner"]


@pytest.mark.parametrize("seed_block", range(4))
def test_wfc_builds_with_corners_are_whole_and_supported(seed_block: int) -> None:
    parts = part_tileset(FAMILY, [RED], empty_weight=1.0)
    turns: set[tuple[str, int]] = set()
    for seed in range(seed_block * BUILDS // 4, (seed_block + 1) * BUILDS // 4):
        result = run(parts.tileset, (5, 4, 4), seed, constraints=[SupportConstraint(parts)], max_backtracks=500)
        assert result.grid is not None
        turns |= {(p.shape.part.name, p.shape.turn) for p in check_build(result.grid, parts) if p.shape.part in CORNERS}
    assert {t for _, t in turns} == {0, 1, 2, 3}


def test_bottom_up_builds_with_corners_are_whole_and_supported() -> None:
    parts = part_tileset(FAMILY, [RED, BLUE], empty_weight=1.0)
    for kwargs in ({}, {"any_offset": True}, {"any_offset": True, "balanced": True, "bridge": True, "connect": True}):
        builder = BottomUpBuilder(parts, **kwargs)
        turns: set[int] = set()
        for seed in range(BUILDS):
            grid = builder.build((7, 4, 4), np.random.default_rng(seed))
            placed = check_build(grid, parts)
            turns |= {p.shape.turn for p in placed if p.shape.part in CORNERS}
            if kwargs.get("balanced"):  # the balance check is exact for corners too
                assert not tipping_clusters(placed)
                assert required_clutch(placed, grid.shape) < np.inf
        assert turns == {0, 1, 2, 3}


def test_corner_physics() -> None:
    corner = PlacedPart(Shape(CATALOG["brick2x2_corner"], 0), RED, 0, 0, 0)
    (dz, dx) = next((dz, dx) for dz in (0, 1) for dx in (0, 1) if not corner.shape.covers(dz, dx))
    cx, cz = corner.centre()
    assert (cx, cz) == pytest.approx((1 + (0.5 - dx) / 3, 1 + (0.5 - dz) / 3))  # pulled away from the notch
    assert required_clutch([corner], (4, 2, 2)) == 0.0
    # A 2x2 plate on the corner brick overhangs the notch; its centre is over the L's hull: no clutch needed.
    plate = PlacedPart(Shape(CATALOG["plate2x2"]), BLUE, 3, 0, 0)
    assert required_clutch([corner, plate], (4, 2, 2)) == 0.0
    # A 1x6 plate along the full arm (the row without the notch) sticks out 4 studs: the corner brick's
    # weight keeps the build upright, but the plate needs grip to stay on.
    arm = 1 - dz
    cantilever = PlacedPart(Shape(CATALOG["plate1x6"]), BLUE, 3, 0, arm)
    assert 0 < required_clutch([corner, cantilever], (4, 2, 6)) < np.inf


def test_every_orientation_roundtrips_through_ldraw(tmp_path: Path) -> None:
    placed, x = [], 0
    for part in CORNERS + [CATALOG["plate2x4"], CATALOG["brick1x2"]]:
        for turn in range(4):
            shape = Shape(part, turn)
            placed.append(PlacedPart(shape, RED, turn, x, turn))
            x += shape.size_x + 1
    path = tmp_path / "turns.ldr"
    write_ldr((p.placement() for p in placed), path, "turns")
    recovered, report = voxelize(flatten(path.read_text()))
    assert report.kept == len(placed) and report.tilted == report.off_grid == report.overlapping == 0
    expected = sorted((canonical(p.shape.part, p.shape.turn).name, p.layer, p.x, p.z) for p in placed)
    assert sorted((p.shape.name, p.layer, p.x, p.z) for p in recovered) == expected


def test_catalog_check_has_every_orientation_without_overlaps() -> None:
    placed = layout()
    cells = [cell for p in placed for cell in p.cells()]
    assert len(cells) == len(set(cells))
    shown = {(p.shape.part.name, p.shape.turn) for p in placed}
    for part in CORNERS:
        assert {(part.name, t) for t in range(4)} <= shown


# Builds from the M8 catalog are unchanged by the M12b geometry (fingerprints recorded before it).
M8_NAMES = ("plate1x2", "plate2x4", "brick1x1", "brick1x2", "brick2x4", "brick1x2_2877", "tile1x2", "tile2x2",
            "tile1x2_2412b")
M8_FINGERPRINTS = {
    "d": ["0bd1e3906fc701c6", "45bc7804d50b24d8", "f0fadc23d2b06ef9"],
    "d2": ["875e568f3723130b", "1bd0e74c558e24b2", "eb09245ebb62100b"],
    "d2_connect": ["caa951dc119cbf5e", "43a519186e5b143d", "5fffaad27298a09b"],
    "wfc": ["d209830a142d1936", "f6dc0023c8746426", "66bc5e512a85feed"],
}


def test_m8_builds_are_unchanged() -> None:
    parts = part_tileset([CATALOG[n] for n in M8_NAMES], [RED, BLUE], empty_weight=0.5)

    def digest(grid: np.ndarray) -> str:
        placed = check_build(grid, parts)
        text = ";".join(f"{p.shape.name},{p.color.name},{p.layer},{p.x},{p.z}" for p in placed)
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    inventory = {(n, c): 6 for n in M8_NAMES for c in ("red", "blue")}
    builders = {
        "d": BottomUpBuilder(parts),
        "d2": BottomUpBuilder(parts, any_offset=True),
        "d2_connect": BottomUpBuilder(parts, any_offset=True, balanced=True, bridge=True, connect=True, connect_rounds=3),
    }
    for name, builder in builders.items():
        assert [digest(builder.build((9, 6, 6), np.random.default_rng(s), inventory)) for s in range(3)] == M8_FINGERPRINTS[name]
    wfc = [digest(run(parts.tileset, (5, 4, 4), s, 20, [SupportConstraint(parts)]).grid) for s in range(3)]
    assert wfc == M8_FINGERPRINTS["wfc"]
