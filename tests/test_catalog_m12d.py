"""M12d: the catalog extended to the real sets' parts (geometry facts: test_catalog_shapes.LDRAW)."""

from pathlib import Path

import numpy as np
import pytest

from brickwfc.bricks.balance import ground_corners
from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.catalog_check import layout
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import BY_FILE, CATALOG, M12D_BATCH1, PlacedPart, Shape, canonical, extract_parts, part_tileset, shapes_of
from brickwfc.bricks.physics import required_clutch, tipping_clusters
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.support import is_stable
from brickwfc.bricks.voxelize import tile_grid, voxelize
from brickwfc.ldraw.export import write_ldr
from brickwfc.ldraw.mpd import flatten
from brickwfc.wfc import run

from test_catalog_shapes import LDRAW, check_build, faces_clear

RED, BLUE = colors_by_name(["red", "blue"])
BUILDS = 60
# A mix of the new mechanisms: an arch, a round corner, studs on some cells, a cutout slope (origin inside its
# box), curved studless parts (origin on the bottom), a tall brick, a lookalike, plus plain parts to build on.
FAMILY = [CATALOG[n] for n in ("arch1x4", "brick2x2_round_corner", "plate1x4_2studs", "slope45_2x1_cutout",
                               "curved2x1", "curved3x1", "brick1x2x2", "brick1x2_30136", "plate1x1", "plate1x2",
                               "brick1x1", "brick1x2", "plate2x2")]
NEW = {"arch1x4", "brick2x2_round_corner", "plate1x4_2studs", "slope45_2x1_cutout", "curved2x1", "curved3x1",
       "brick1x2x2", "brick1x2_30136"}


def test_every_new_part_has_ldraw_facts_and_comes_after_the_old_ones() -> None:
    names = list(CATALOG)
    assert names.index(M12D_BATCH1[0].name) == 88  # earlier parts keep their style indices
    assert {p.ldraw for p in M12D_BATCH1} <= set(LDRAW)
    assert BY_FILE["3665b.dat"] is CATALOG["slope45inv_2x1"] and BY_FILE["63325.dat"] is CATALOG["plate2x2_corner"]
    assert BY_FILE["3678a.dat"] is CATALOG["slope65_2x2x2"] and BY_FILE["2453.dat"] is CATALOG["brick1x1x5"]


def test_baseplate_is_ground_only() -> None:
    plate = CATALOG["baseplate16x32"]
    assert plate.ground_only and Shape(plate).geometry.seated == frozenset()
    on_table = PlacedPart(Shape(plate), BLUE, 0, 0, 0)
    brick = PlacedPart(Shape(CATALOG["brick2x4"]), RED, 1, 3, 2)
    # On the table its whole bottom bears: it stands, and carries a brick, without any grip.
    assert len(on_table.contact_cells()) == 512 and len(ground_corners(on_table)) == 4 * 512
    filled = np.zeros((4, 16, 32), dtype=bool)
    for cell in on_table.cells() + brick.cells():
        filled[cell] = True
    assert is_stable([on_table, brick], filled) and required_clutch([on_table, brick], filled.shape) == 0.0
    # Above the ground it rests on nothing (no seated cell), so it is never supported there.
    raised = PlacedPart(Shape(plate), BLUE, 3, 0, 0)
    under = PlacedPart(Shape(CATALOG["brick2x4"]), RED, 0, 0, 0)
    assert raised.contact_cells() == [] and not is_stable([under, raised], np.ones((4, 16, 32), dtype=bool))
    # Clicked onto a baseplate in physics' sense, a baseplate part still has no grip (it lies on, never clicks).
    alone = PlacedPart(Shape(CATALOG["baseplate32x32"]), BLUE, 0, 0, 0)
    assert required_clutch([alone], (1, 32, 32), baseplate=True) == 0.0


def test_builders_put_a_baseplate_on_the_ground_only() -> None:
    parts = part_tileset([CATALOG["baseplate16x32"], CATALOG["brick2x4"], CATALOG["plate1x2"]], [RED, BLUE])
    inventory = {("baseplate16x32", "blue"): 2, ("brick2x4", "red"): 10, ("plate1x2", "red"): 20}
    builder = BottomUpBuilder(parts, any_offset=True, balanced=True, holes=True)
    for seed in range(20):  # until a build places one (each build is checked on the way)
        placed = check_build(builder.build((6, 16, 32), np.random.default_rng(seed), inventory), parts)
        layers = {p.layer for p in placed if p.shape.part.ground_only}
        assert layers <= {0}
        if layers:
            break
    else:
        pytest.fail("no build placed the baseplate")


def test_nothing_under_an_arch_span() -> None:
    parts = part_tileset([CATALOG["arch1x4"], CATALOG["brick1x1"]], [RED])
    arch = PlacedPart(Shape(CATALOG["arch1x4"]), RED, 3, 0, 0)
    legs = [PlacedPart(Shape(CATALOG["brick1x1"]), RED, 0, x, 0) for x in (0, 3)]
    middle = PlacedPart(Shape(CATALOG["brick1x1"]), RED, 0, 1, 0)

    def errors(*placed: PlacedPart) -> list[str]:
        return extract_parts(tile_grid(list(placed), parts), parts)[1]

    assert errors(arch, *legs) == []
    assert any("open bottom" in e for e in errors(arch, *legs, middle))
    # On one leg only it hangs 3 studs out: it stands only by grip (or tips without the leg's clutch).
    filled = np.zeros((6, 1, 4), dtype=bool)
    for cell in arch.cells() + legs[0].cells():
        filled[cell] = True
    assert is_stable([legs[0], arch], filled)
    assert tipping_clusters([legs[0], arch])


@pytest.mark.parametrize("seed_block", range(3))
def test_wfc_builds_with_new_parts_are_whole_and_supported(seed_block: int) -> None:
    parts = part_tileset(FAMILY, [RED], empty_weight=1.0)
    names: set[str] = set()
    for seed in range(seed_block * BUILDS // 3, (seed_block + 1) * BUILDS // 3):
        result = run(parts.tileset, (7, 4, 5), seed, constraints=[SupportConstraint(parts)], max_backtracks=500)
        assert result.grid is not None
        placed = check_build(result.grid, parts)
        assert faces_clear(placed, result.grid.shape)
        names |= {p.shape.part.name for p in placed}
    assert names & NEW


def test_bottom_up_builds_with_new_parts_are_whole_and_supported() -> None:
    parts = part_tileset(FAMILY, [RED, BLUE], empty_weight=1.0)
    for kwargs in ({}, {"any_offset": True}, {"any_offset": True, "balanced": True, "bridge": True, "connect": True},
                   {"any_offset": True, "balanced": True, "holes": True, "hang": True}):
        builder = BottomUpBuilder(parts, **kwargs)
        names: set[str] = set()
        for seed in range(BUILDS):
            grid = builder.build((10, 5, 5), np.random.default_rng(seed))
            placed, errors = extract_parts(grid, parts)
            assert errors == []
            # with hang, a part may hang from the one above by its studs (support in that sense)
            assert is_stable(placed, parts.solid[grid], hanging=bool(kwargs.get("hang")))
            assert faces_clear(placed, grid.shape)
            names |= {p.shape.part.name for p in placed}
            if kwargs.get("balanced"):
                assert not tipping_clusters(placed)
                assert required_clutch(placed, grid.shape) < np.inf
        assert names >= NEW, NEW - names


def test_every_new_orientation_roundtrips_through_ldraw(tmp_path: Path) -> None:
    placed, x = [], 0
    for part in M12D_BATCH1:
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


def test_catalog_check_shows_every_new_orientation() -> None:
    placed = layout()
    cells = [cell for p in placed for cell in p.cells()]
    assert len(cells) == len(set(cells))
    shown = {(p.shape.part.name, p.shape.turn) for p in placed}
    for part in M12D_BATCH1:
        turns = {s.turn for s in shapes_of([part])} if not Shape(part).rectangular else {0, 1}
        assert {(part.name, t) for t in turns} <= shown, part.name


def test_coverage_counts_new_parts() -> None:
    from brickwfc.experiments.coverage import set_coverage

    mpd = """0 FILE main.ldr
1 4 0 -8 0 1 0 0 0 1 0 0 0 1 3020.dat
1 4 0 -32 10 1 0 0 0 1 0 0 0 1 3659.dat
1 4 70 -32 10 1 0 0 0 1 0 0 0 1 6091.dat
1 4 0 -40 0 1 0 0 0 1 0 0 0 1 3794b.dat
0 NOFILE
"""
    row = set_coverage("fake-1", mpd, on_grid=True)
    assert (row.parts, row.catalog_m8, row.catalog_m12b, row.catalog) == (4, 1, 1, 3)
    assert (row.on_grid_m8, row.on_grid_m12b, row.on_grid) == (1, 1, 3)
