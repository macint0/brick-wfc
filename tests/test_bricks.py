"""M8: bricks (3 plate layers tall), tiles (no studs) and the full part catalog."""

from pathlib import Path

import numpy as np
import pytest

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.build import export_build
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.inventory import InventoryConstraint, inventory_from_mpd, overuse, usage
from brickwfc.bricks.parts import (
    BY_FILE,
    CATALOG,
    DOWN,
    M12D_BATCH1,
    UP,
    Part,
    PartSet,
    PlacedPart,
    Shape,
    TileInfo,
    extract_parts,
    family,
    part_tileset,
)
from brickwfc.bricks.physics import required_clutch
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.support import is_stable, unsupported_parts
from brickwfc.bricks.voxelize import voxelize
from brickwfc.experiments.coverage import main as coverage_main, set_coverage
from brickwfc.ldraw.export import BRICK_LDU, PLATE_LDU, parse_ldr
from brickwfc.ldraw.mpd import flatten
from brickwfc.wfc import run

RED, BLUE = colors_by_name(["red", "blue"])
BUILDS = 100


def fits(part: Part, side: int) -> bool:
    return part.width <= side and part.depth <= side


# Part families for the integrity tests. Real inventories mix families (tiles alone can't stack),
# so the third family mixes all three kinds plus lookalikes.
FAMILIES = {
    "plates": [p for p in family("plate") if fits(p, 4)],
    "bricks": [p for p in family("brick") if fits(p, 4)],
    "mixed": [CATALOG[n] for n in ("plate1x2", "plate2x4", "brick1x1", "brick1x2", "brick2x4", "brick1x2_2877",
                                   "tile1x2", "tile2x2", "tile1x2_2412b")],
}


def piece(name: str, layer: int, x: int = 0, z: int = 0, rotated: bool = False, color=RED) -> PlacedPart:
    return PlacedPart(Shape(CATALOG[name], rotated), color, layer, x, z)


def test_catalog() -> None:
    assert len({p.ldraw for p in CATALOG.values()}) == len(CATALOG)
    for part in CATALOG.values():
        if part.kind == "slope":  # M12b: long along their fall (LDraw Z); see test_catalog_shapes
            continue
        if part in M12D_BATCH1:  # M12d: tall bricks, studless panels, arches; checked against their .dat facts
            continue
        assert part.width >= part.depth  # LDraw parts are long along X
        assert part.height == {"plate": 1, "brick": 3, "tile": 1}[part.kind]
        assert part.studs == (part.kind != "tile")
    assert BY_FILE["3001.dat"] == CATALOG["brick2x4"] and BY_FILE["3069b.dat"] == CATALOG["tile1x2"]
    assert BY_FILE["2877.dat"].kind == "brick" and BY_FILE["6141.dat"].name == "plate1x1_6141"


def test_brick_tiles_stack_vertically() -> None:
    parts = part_tileset([CATALOG["brick1x1"]], [RED])
    index = {info: t for t, info in enumerate(parts.infos)}
    shape = Shape(CATALOG["brick1x1"], False)
    bottom, middle, top = (index[TileInfo(shape, 0, 0, RED, y)] for y in range(3))
    allowed_above = np.flatnonzero(parts.tileset.compat[UP, bottom])
    assert list(allowed_above) == [middle]
    assert parts.tileset.compat[UP, top, bottom] and parts.tileset.compat[UP, top, 0]  # a new brick or empty
    assert not parts.tileset.compat[UP, top, middle]  # never the middle of another brick
    border = parts.tileset.border
    assert not border[UP, bottom] and not border[DOWN, middle] and border[UP, top] and border[DOWN, bottom]


def test_nothing_sits_on_a_tile() -> None:
    parts = part_tileset([CATALOG["tile1x1"], CATALOG["plate1x1"]], [RED])
    index = {info: t for t, info in enumerate(parts.infos)}
    tile = index[TileInfo(Shape(CATALOG["tile1x1"], False), 0, 0, RED)]
    plate = index[TileInfo(Shape(CATALOG["plate1x1"], False), 0, 0, RED)]
    compat = parts.tileset.compat
    assert list(np.flatnonzero(compat[UP, tile])) == [0]  # only empty above a tile
    assert compat[UP, plate, tile] and not compat[DOWN, plate, tile]


def test_placement_heights_and_files() -> None:
    brick = piece("brick2x4", 0).placement()
    assert brick.part == "3001.dat" and brick.position == (30, -BRICK_LDU, 10)
    plate = piece("plate1x2", 3).placement()  # on top of the brick
    assert plate.position[1] == -(BRICK_LDU + PLATE_LDU)
    tile = piece("tile1x2", 0, rotated=True).placement()
    assert tile.part == "3069b.dat" and tile.position == (0, -PLATE_LDU, 10)


def test_support_needs_a_stud() -> None:
    placed = [piece("brick1x2", 0), piece("tile1x2", 3), piece("plate1x1", 4)]  # plate rests on a tile only
    filled = np.zeros((5, 1, 2), dtype=bool)
    for part in placed:
        for cell in part.cells():
            filled[cell] = True
    assert unsupported_parts(placed, filled) == [placed[2]]
    assert unsupported_parts(placed[:2], filled) == []


def test_extract_parts_flags_parts_on_tiles() -> None:
    parts = part_tileset([CATALOG["tile1x1"], CATALOG["brick1x1"]], [RED])
    index = {info: t for t, info in enumerate(parts.infos)}
    grid = np.zeros((4, 1, 1), dtype=np.int64)
    grid[0, 0, 0] = index[TileInfo(Shape(CATALOG["tile1x1"], False), color=RED)]
    for y in range(3):
        grid[1 + y, 0, 0] = index[TileInfo(Shape(CATALOG["brick1x1"], False), color=RED, offset_y=y)]
    placed, errors = extract_parts(grid, parts)
    assert len(placed) == 2 and len(errors) == 1 and "sits on" in errors[0]
    grid[2, 0, 0] = 0  # brick broken in the middle
    _, errors = extract_parts(grid, parts)
    assert any("incomplete" in e for e in errors)


def check_build(grid: np.ndarray, parts: PartSet) -> list[PlacedPart]:
    placed, errors = extract_parts(grid, parts)
    assert errors == []
    assert is_stable(placed, parts.solid[grid])
    return placed


@pytest.mark.parametrize("name", list(FAMILIES))
def test_wfc_builds_are_whole_and_supported(name: str) -> None:
    parts = part_tileset(FAMILIES[name], [RED], empty_weight=1.0)  # one color keeps 100 builds quick
    kinds: set[str] = set()
    for seed in range(BUILDS):
        result = run(parts.tileset, (5, 4, 4), seed, constraints=[SupportConstraint(parts)], max_backtracks=500)
        assert result.grid is not None
        kinds |= {p.shape.part.kind for p in check_build(result.grid, parts)}
    assert kinds == {p.kind for p in FAMILIES[name]}


@pytest.mark.parametrize("name", list(FAMILIES))
def test_bottom_up_builds_are_whole_and_supported(name: str) -> None:
    parts = part_tileset(FAMILIES[name], [RED, BLUE], empty_weight=1.0)
    for any_offset in (False, True):
        builder = BottomUpBuilder(parts, any_offset=any_offset)
        kinds: set[str] = set()
        for seed in range(BUILDS):
            grid = builder.build((7, 4, 4), np.random.default_rng(seed))
            kinds |= {p.shape.part.kind for p in check_build(grid, parts)}
        assert kinds == {p.kind for p in FAMILIES[name]}


def test_physics_counts_brick_weight_and_tile_grip() -> None:
    shape = (7, 1, 7)
    assert required_clutch([piece("brick1x1", 0), piece("brick1x1", 3)], shape) == 0.0
    # A 1x4 plate held by one stud, three hanging out: the heavy brick keeps the build upright, but
    # the plate needs clutch to stay on. On a tile (no studs, no clutch) it can't stay on at all.
    on_brick = [piece("brick1x4", 0), piece("plate1x4", 3, x=3)]
    assert 0 < required_clutch(on_brick, shape) < np.inf
    on_tile = [piece("tile1x4", 0), piece("plate1x4", 1, x=3)]
    assert required_clutch(on_tile, shape) == np.inf


def test_bricks_and_tiles_roundtrip_through_ldraw(tmp_path: Path) -> None:
    parts = part_tileset(FAMILIES["mixed"], [RED, BLUE], empty_weight=1.0)
    grid = BottomUpBuilder(parts, any_offset=True).build((9, 6, 6), np.random.default_rng(1))
    placed = check_build(grid, parts)
    path = tmp_path / "build.ldr"
    export_build(grid, placed, parts, path, tmp_path / "build.png", "m8 roundtrip")
    files = {p.part for p in parse_ldr(path.read_text())}
    assert files == {p.shape.part.ldraw for p in placed}
    recovered, report = voxelize(flatten(path.read_text()))
    assert report.kept == len(placed) and report.off_grid == report.overlapping == 0

    def key(p: PlacedPart) -> tuple:
        return (p.shape.name, p.color.name, p.layer, p.x, p.z)

    shift = (min(p.layer for p in placed), min(p.x for p in placed), min(p.z for p in placed))
    expected = sorted(key(PlacedPart(p.shape, p.color, p.layer - shift[0], p.x - shift[1], p.z - shift[2])) for p in placed)
    assert sorted(key(p) for p in recovered) == expected


def test_inventory_counts_a_brick_once() -> None:
    mpd = "0 FILE m.ldr\n" + "".join(f"1 4 0 {-24 * (i + 1)} 0 1 0 0 0 1 0 0 0 1 3004.dat\n" for i in range(3))
    mpd += "1 1 0 -80 0 1 0 0 0 1 0 0 0 1 3069b.dat\n"
    inventory, unsupported, _ = inventory_from_mpd(mpd)
    assert inventory == {("brick1x2", "red"): 3, ("tile1x2", "blue"): 1} and not unsupported
    parts = part_tileset([CATALOG["brick1x2"], CATALOG["tile1x2"]], [RED, BLUE], empty_weight=0.2)
    constraints = [SupportConstraint(parts), InventoryConstraint(parts, inventory)]
    for seed in range(10):
        result = run(parts.tileset, (9, 3, 3), seed, constraints=constraints, max_backtracks=500)
        assert result.grid is not None
        placed = check_build(result.grid, parts)
        assert not overuse(placed, inventory) and usage(placed)[("brick1x2", "red")] >= 1


def test_coverage_counts_parts_not_primitives(tmp_path: Path) -> None:
    mpd = """0 FILE main.ldr
1 4 0 -8 0 1 0 0 0 1 0 0 0 1 3020.dat
1 4 0 -32 0 1 0 0 0 1 0 0 0 1 3001.dat
1 4 0 -40 0 1 0 0 0 1 0 0 0 1 3794b.dat
1 4 0 0 0 1 0 0 0 1 0 0 0 1 custom.dat
0 NOFILE
0 FILE custom.dat
1 16 0 0 0 1 0 0 0 1 0 0 0 1 4-4cyli.dat
1 16 0 0 0 1 0 0 0 1 0 0 0 1 stud.dat
0 NOFILE
"""
    row = set_coverage("fake-1", mpd)
    assert (row.parts, row.primitives, row.plates4, row.catalog) == (3, 2, 1, 2)
    assert row.top_missing == [("3794b.dat", 1)]
    data = tmp_path / "omr"
    data.mkdir()
    (data / "fake-1.mpd").write_text(mpd)
    assert coverage_main(["--sets", "fake-1", "--data", str(data), "--out", str(tmp_path / "cov")]) == 0
    assert "| fake-1 | 3 | 33 | 67 |" in (tmp_path / "cov" / "coverage.md").read_text(encoding="utf-8")
