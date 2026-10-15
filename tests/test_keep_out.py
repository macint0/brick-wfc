"""M12d batch 3: parts with keep-out cells (door rails, side studs, brackets, a handle)."""

import math
from pathlib import Path

import numpy as np
import pytest

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.catalog_check import layout
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import (BY_FILE, CATALOG, M12D_KEEP_OUT, PlacedPart, Shape, canonical, extract_parts,
                                   part_tileset, shapes_of, wfc_inventory)
from brickwfc.bricks.physics import required_clutch, tipping_clusters
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.support import is_stable
from brickwfc.bricks.voxelize import tile_grid, voxelize
from brickwfc.ldraw.export import PLATE_LDU, STUD_LDU, write_ldr
from brickwfc.ldraw.mpd import flatten

from test_catalog_shapes import LDRAW

RED, BLUE = colors_by_name(["red", "blue"])
BUILDS = 40

# From the .dat files (python -m brickwfc.ldraw.library, resolved through the subfiles): the box the studs and the flat
# bottom belong to, as in the LDRAW table, and ``beyond``: (x, y, z) extents in LDU of the geometry outside that box,
# side studs included (a stud is 4 LDU long, radius 6). ``side_studs``: (position, direction) of each stud on a side.
KEEP_OUT_FACTS = {
    # Plate 1 x 2 with Door Rail
    "32028.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 8),
                  "beyond": [((-20, 20), (0, 8), (-19, -10))]},
    # Plate 1 x 8 with Door Rail
    "4510.dat": {"studs": [(x, 0) for x in range(-70, 71, 20)], "x": (-80, 80), "z": (-10, 10), "y": (0, 8),
                 "beyond": [((-80, 80), (0, 8), (-19, -10))]},
    # Plate 2 x 8 with Door Rail: studs on one row, the rail beyond the other, rising 4 LDU above the top
    "30586.dat": {"studs": [(x, 0) for x in range(-70, 71, 20)], "x": (-80, 80), "z": (-30, 10), "y": (0, 8),
                  "flat": [(x, z) for x in range(-70, 71, 20) for z in (-20, 0)], "beyond": [((-80, 80), (-4, 4), (-32, -30))]},
    # Brick 1 x 1 with Stud on 1 Side
    "87087.dat": {"studs": [(0, 0)], "x": (-10, 10), "z": (-10, 10), "y": (0, 24), "beyond": [((-6, 6), (4, 16), (-14, -10))],
                  "side_studs": [((0, 10, -10), (0, 0, -1))]},
    # Brick 1 x 1 with Studs on Two Opposite Sides
    "47905.dat": {"studs": [(0, 0)], "x": (-10, 10), "z": (-10, 10), "y": (0, 24),
                  "beyond": [((-6, 6), (4, 16), (-14, -10)), ((-6, 6), (4, 16), (10, 14))],
                  "side_studs": [((0, 10, -10), (0, 0, -1)), ((0, 10, 10), (0, 0, 1))]},
    # Brick 1 x 4 with Studs on Side
    "30414.dat": {"studs": [(x, 0) for x in (-30, -10, 10, 30)], "x": (-40, 40), "z": (-10, 10), "y": (0, 24),
                  "beyond": [((-36, 36), (4, 16), (-14, -10))],
                  "side_studs": [((x, 10, -10), (0, 0, -1)) for x in (-30, -10, 10, 30)]},
    # Bracket 1 x 2 - 2 x 2 Down: a 1 x 2 plate, its face hanging 32 LDU below it in front
    "44728.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 8), "beyond": [((-20, 20), (0, 40), (-18, -10))],
                  "side_studs": [((x, y, -14), (0, 0, -1)) for x in (-10, 10) for y in (10, 30)]},
    # Bracket 1 x 2 - 2 x 4: the face is 4 studs wide
    "93274.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 8), "beyond": [((-40, 40), (0, 40), (-18, -10))],
                  "side_studs": [((x, y, -14), (0, 0, -1)) for x in (-30, -10, 10, 30) for y in (10, 30)]},
    # Brick 1 x 1 with Handle
    "2921.dat": {"studs": [(0, 0)], "x": (-10, 10), "z": (-10, 10), "y": (0, 24), "beyond": [((-4, 4), (0, 24), (-24, -10))]},
}


def test_the_box_facts_are_the_placement_tests() -> None:
    """The boxes (studs, extents, flat bottom) are checked in every turn by test_catalog_shapes, from the same facts."""
    for file, facts in KEEP_OUT_FACTS.items():
        assert LDRAW[file] == {k: v for k, v in facts.items() if k not in ("beyond", "side_studs")}


def test_every_keep_out_part_has_facts() -> None:
    assert {p.ldraw for p in M12D_KEEP_OUT} == set(KEEP_OUT_FACTS)
    assert all(not p.wfc for p in M12D_KEEP_OUT)


@pytest.mark.parametrize("file", list(KEEP_OUT_FACTS))
def test_keep_out_holds_what_sticks_out(file: str) -> None:
    """In every turn, each cell (and layer) that the geometry outside the part's box overlaps is a keep-out cell. (The
    box itself is checked by test_catalog_shapes.test_placement_matches_the_ldraw_part.)"""
    part = BY_FILE[file]
    for turn in range(4):
        placed = PlacedPart(Shape(part, turn), RED, 5, 3, 4)
        p = placed.placement()
        r, origin = np.array(p.rotation, dtype=float).reshape(3, 3), np.array(p.position)
        keep = set(placed.keep_out_cells())
        for xs, ys, zs in KEEP_OUT_FACTS[file]["beyond"]:
            corners = np.array([r @ (x, y, z) + origin for x in xs for y in ys for z in zs])
            lo, hi = corners.min(axis=0), corners.max(axis=0)
            cells_x = range(math.ceil(lo[0] / STUD_LDU - 0.5 + 1e-9), math.floor(hi[0] / STUD_LDU + 0.5 - 1e-9) + 1)
            cells_z = range(math.ceil(lo[2] / STUD_LDU - 0.5 + 1e-9), math.floor(hi[2] / STUD_LDU + 0.5 - 1e-9) + 1)
            layers = range(math.floor(-hi[1] / PLATE_LDU + 1e-9), math.ceil(-lo[1] / PLATE_LDU - 1e-9))
            needed = {(y, z, x) for y in layers for z in cells_z for x in cells_x}
            box = set(placed.cells())
            assert needed - box <= keep, (Shape(part, turn).name, sorted(needed - box - keep))
            assert needed - box, "the protrusion should reach outside the box"


@pytest.mark.parametrize("file", [f for f, facts in KEEP_OUT_FACTS.items() if "side_studs" in facts])
def test_side_studs_are_recorded(file: str) -> None:
    part = BY_FILE[file]
    bottom = part.origin_layer * PLATE_LDU  # LDU below the origin
    recorded = sorted((x * STUD_LDU, bottom - h * PLATE_LDU, z * STUD_LDU, dx, dz) for x, z, h, dx, dz in part.side_studs)
    real = sorted((px, py, pz, dx, dz) for (px, py, pz), (dx, _, dz) in KEEP_OUT_FACTS[file]["side_studs"])
    assert np.allclose(recorded, real)


def errors(*placed: PlacedPart) -> list[str]:
    parts = part_tileset(sorted({p.shape.part for p in placed}, key=lambda q: q.name), [RED, BLUE])
    grid = tile_grid(list(placed), parts)
    return extract_parts(grid, parts)[1]


def test_nothing_goes_into_a_keep_out() -> None:
    rail = PlacedPart(Shape(CATALOG["doorrail1x2_32028"]), RED, 0, 0, 1)
    in_front = PlacedPart(Shape(CATALOG["plate1x2"]), BLUE, 0, 0, 0)  # the rail's side (z - 1)
    behind = PlacedPart(Shape(CATALOG["plate1x2"]), BLUE, 0, 0, 2)
    assert errors(rail, behind) == []
    assert any("keep-out" in e for e in errors(rail, in_front))
    # Turned twice, the rail is on the other side.
    turned = PlacedPart(Shape(CATALOG["doorrail1x2_32028"], 2), RED, 0, 0, 1)
    assert errors(turned, in_front) == [] and any("keep-out" in e for e in errors(turned, behind))
    # A bracket's face hangs four plates below it: on low layers it would reach into the ground.
    bracket = CATALOG["bracket1x2_2x2_44728"]
    assert any("keep-out" in e for e in errors(PlacedPart(Shape(bracket), RED, 3, 0, 1)))
    assert errors(PlacedPart(Shape(CATALOG["brick1x2"]), BLUE, 0, 0, 1), PlacedPart(Shape(CATALOG["brick1x2"]), BLUE, 3, 0, 1),
                  PlacedPart(Shape(bracket), RED, 6, 0, 1)) == []


FAMILY = [CATALOG[n] for n in ("doorrail1x2_32028", "brick1x1_sidestud_87087", "brick1x1_sidestuds_47905",
                               "brick1x4_sidestuds_30414", "bracket1x2_2x2_44728", "brick1x1_handle_2921",
                               "plate1x1", "plate1x2", "plate2x2", "brick1x1", "brick1x2", "brick2x2", "tile1x2")]
KEEPERS = {p.name for p in FAMILY if p.keep_out}


def test_bottom_up_builds_keep_their_keep_outs_clear() -> None:
    parts = part_tileset(FAMILY, [RED, BLUE], empty_weight=1.0)
    for kwargs in ({}, {"any_offset": True}, {"any_offset": True, "balanced": True, "bridge": True, "connect": True},
                   {"any_offset": True, "balanced": True, "holes": True, "hang": True}):
        builder = BottomUpBuilder(parts, **kwargs)
        names: set[str] = set()
        for seed in range(BUILDS):
            grid = builder.build((10, 5, 5), np.random.default_rng(seed))
            placed, problems = extract_parts(grid, parts)
            assert problems == []  # whole parts, clear faces, clear keep-outs
            assert is_stable(placed, parts.solid[grid], hanging=bool(kwargs.get("hang")))
            if kwargs.get("balanced"):
                assert not tipping_clusters(placed) and required_clutch(placed, grid.shape) < np.inf
            names |= {p.shape.part.name for p in placed}
        assert names >= KEEPERS, KEEPERS - names


def test_mirror_images_keep_their_keep_outs_clear() -> None:
    from brickwfc.bricks.symmetry import Plane, mirror_part

    parts = part_tileset(FAMILY, [RED], empty_weight=1.0)
    builder = BottomUpBuilder(parts, any_offset=True, balanced=True, holes=True)
    mirrored = set()
    for axis in (1, 2):  # z and x
        for seed in range(BUILDS // 2):
            grid = builder.build((9, 6, 6), np.random.default_rng(seed), plane=Plane(axis, 5, 1.0))
            placed, problems = extract_parts(grid, parts)
            assert problems == []
            mirrored |= {p.shape.name for p in placed if p.shape.part.keep_out}
    # a door rail's mirror across z faces the other way
    rail = PlacedPart(Shape(CATALOG["doorrail1x2_32028"]), RED, 0, 0, 1)
    image = mirror_part(rail, Plane(1, 5, 1.0))
    assert image.shape.turn == 2 and {z for _, z, _ in image.keep_out_cells()} == {5 - 0}
    assert len(mirrored) > 3


def test_wfc_refuses_keep_out_parts() -> None:
    assert wfc_inventory({("doorrail1x2_32028", "red"): 2, ("plate1x2", "red"): 1}) == {("plate1x2", "red"): 1}
    with pytest.raises(ValueError, match="doorrail1x2_32028"):
        SupportConstraint(part_tileset(FAMILY[:1] + FAMILY[-3:], [RED]))


def test_every_keep_out_orientation_roundtrips_through_ldraw(tmp_path: Path) -> None:
    placed, x = [], 0
    for part in M12D_KEEP_OUT:
        for turn in range(4):
            shape = Shape(part, turn)
            placed.append(PlacedPart(shape, RED, 4 + turn, x, turn))
            x += shape.size_x + 2
    path = tmp_path / "turns.ldr"
    write_ldr((p.placement() for p in placed), path, "turns")
    recovered, report = voxelize(flatten(path.read_text()))
    assert report.kept == len(placed) and report.tilted == report.off_grid == report.overlapping == 0
    expected = sorted((canonical(p.shape.part, p.shape.turn).name, p.layer, p.x, p.z) for p in placed)
    assert sorted((p.shape.name, p.layer + 4, p.x, p.z) for p in recovered) == expected  # lowest layer 4 -> 0


def test_catalog_check_shows_every_keep_out_turn() -> None:
    placed = layout()
    shown = {(p.shape.part.name, p.shape.turn) for p in placed}
    for part in M12D_KEEP_OUT:
        assert {(part.name, s.turn) for s in shapes_of([part])} <= shown
    cells = {cell for p in placed for cell in p.cells()}
    for p in placed:
        assert not cells & set(p.keep_out_cells()), p.shape.name
