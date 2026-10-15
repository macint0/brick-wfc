"""M12d batch 2: frames with contained glass, panes and doors; baseplates as the whole ground."""

from pathlib import Path

import numpy as np
import pytest

from brickwfc.alt.output import step_placements, write_build
from brickwfc.bricks.accessories import ACCESSORY_FILES, COMPOSITES, FRAMES, accessories_from_csv, accessories_in, contained, fit
from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import (BASEPLATE_DROP_LDU, BY_FILE, CATALOG, PlacedPart, Shape, build_placements,
                                   part_tileset, wfc_inventory)
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.voxelize import voxelize
from brickwfc.ldraw.export import PLATE_LDU, STUD_LDU, parse_steps, write_ldr
from brickwfc.ldraw.mpd import flatten

from test_catalog_shapes import check_build

RED, WHITE = colors_by_name(["red", "white"])
TRANS_CLEAR = 47
# Body extents (min, max) in LDU of each accessory in its own coordinates, from its .dat (python -m
# brickwfc.ldraw.library; the extents of every vertex with the subfiles resolved).
BODIES = {
    "60601.dat": ((-16.5, 2, -7), (16.5, 41, -3)),  # Glass for Window 1 x 2 x 2 without Sill
    "60602.dat": ((-16.5, 2, -7), (16.5, 65, -3)),  # Glass for Window 1 x 2 x 3
    "4862.dat": ((-16, 4, -10), (16, 40, -2)),  # Glass for Window 1 x 2 x 2 Plane
    "2494.dat": ((-36, 3, -6), (36, 113, -2)),  # Glass for Window 1 x 4 x 5
    "30046.dat": ((-16.8, -20, -2), (16.8, 32.8, 2)),  # Window 1 x 2 x 2.667 Pane Lattice Diamond with Rounded Top
    "3854.dat": ((-2, -1, -34), (2, 61, 2)),  # Window 1 x 2 x 3 Pane
    "86210.dat": ((-37, -4, -4), (37, 56, 4)),  # Glass for Window 1 x 4 x 3 Opening
    "60608.dat": ((-4, -1, -32), (4, 61, 4)),  # Window 1 x 2 x 3 Pane with Thick Corner Tabs
    "60623.dat": ((-4, 3, -3), (67, 137, 3)),  # Door 1 x 4 x 6 with 4 Panes and Stud Handle
    "60616b.dat": ((-3.8, 3.2, -3.8), (67, 136.8, 3.8)),  # Door 1 x 4 x 6 Smooth with Chamfered Handle Plinth
    "60616a.dat": ((-3.8, 3.2, -3.8), (67, 136.8, 3.8)),  # Door 1 x 4 x 6 Smooth with Square Handle Plinth
    "57895.dat": ((-36.2, -1, -2), (36.2, 132.5, 2)),  # Glass for Window 1 x 4 x 6
}


def test_frames_and_accessories_are_registered() -> None:
    assert set(BODIES) == ACCESSORY_FILES
    assert all(frame in BY_FILE for frame in FRAMES) and not ACCESSORY_FILES & set(BY_FILE)
    assert BY_FILE["60592c01.dat"] is BY_FILE["60592.dat"] and BY_FILE["60593c01.dat"] is BY_FILE["60593.dat"]
    assert all(glass in ACCESSORY_FILES for glass, _ in COMPOSITES.values())
    assert list(CATALOG).index("window1x2x2_60592") > list(CATALOG).index("curved1x1x2_49307")  # after batch 1


@pytest.mark.parametrize("frame", list(FRAMES))
def test_every_slot_keeps_its_accessory_inside_the_frame(frame: str) -> None:
    """In every orientation of the frame, each slot's accessory body lies inside the frame's cells and layers."""
    part = BY_FILE[frame]
    for turn in range(4):
        placed = PlacedPart(Shape(part, turn), WHITE, 2, 3, 4)
        lo = np.array([(placed.x - 0.5) * STUD_LDU, -(placed.top + 1) * PLATE_LDU, (placed.z - 0.5) * STUD_LDU])
        hi = np.array([(placed.x + placed.shape.size_x - 0.5) * STUD_LDU, -placed.layer * PLATE_LDU,
                       (placed.z + placed.shape.size_z - 0.5) * STUD_LDU])
        for _, placement in fit([placed], {(f, TRANS_CLEAR): 9 for f in ACCESSORY_FILES}):
            r = np.array(placement.rotation, dtype=float).reshape(3, 3)
            low, high = BODIES[placement.part]
            corners = np.array([r @ (x, y, z) + placement.position for x in (low[0], high[0]) for y in (low[1], high[1])
                                for z in (low[2], high[2])])
            assert (corners >= lo - 1e-6).all() and (corners <= hi + 1e-6).all(), (frame, turn, placement.part)


def test_fit_uses_up_the_inventory_in_frame_order() -> None:
    frame = Shape(CATALOG["window1x4x2_4863"])  # two glass slots
    placed = [PlacedPart(frame, WHITE, 0, 0, 0), PlacedPart(frame, WHITE, 0, 5, 0), PlacedPart(Shape(CATALOG["brick1x2"]), RED, 0, 10, 0)]
    stock = {("4862.dat", TRANS_CLEAR): 4, ("4862.dat", 40): 1}
    fitted = fit(placed, stock)
    assert [i for i, _ in fitted] == [0, 0, 1, 1]
    assert [p.color for _, p in fitted] == [TRANS_CLEAR, TRANS_CLEAR, TRANS_CLEAR, 40]  # most left first; ties: lower code
    assert stock == {("4862.dat", TRANS_CLEAR): 4, ("4862.dat", 40): 1}  # not changed
    assert fit(placed, {}) == []
    door = PlacedPart(Shape(CATALOG["doorframe1x4x6_60596"]), WHITE, 0, 0, 0)
    assert [p.part for _, p in fit([door], {("60616b.dat", 15): 1, ("57895.dat", TRANS_CLEAR): 1})] == ["60616b.dat", "57895.dat"]


def test_accessories_are_read_from_models_and_parts_lists() -> None:
    mpd = """0 FILE main.ldr
1 15 0 -48 0 1 0 0 0 1 0 0 0 1 60592.dat
1 47 0 -48 0 1 0 0 0 1 0 0 0 1 60601.dat
1 15 100 -48 0 1 0 0 0 1 0 0 0 1 60592c01.dat
1 47 300 -48 0 1 0 0 0 1 0 0 0 1 60601.dat
0 NOFILE
"""
    instances = flatten(mpd)
    assert accessories_in(instances) == {("60601.dat", TRANS_CLEAR): 3}  # two loose + the composite's
    assert contained(instances) == 1  # the loose glass at x = 300 is in no frame; the composite's is one instance
    assert accessories_from_csv("part,color,count\n60601,47,2\n60592c01.dat,15,1\n3001,4,5\n") == {("60601.dat", 47): 3}


def test_coverage_counts_glass_in_a_frame() -> None:
    from brickwfc.experiments.coverage import set_coverage

    mpd = """0 FILE main.ldr
1 15 0 -48 0 1 0 0 0 1 0 0 0 1 60592.dat
1 47 0 -48 0 1 0 0 0 1 0 0 0 1 60601.dat
1 47 300 -48 0 1 0 0 0 1 0 0 0 1 60601.dat
0 NOFILE
"""
    row = set_coverage("fake-1", mpd, on_grid=True)
    assert (row.parts, row.catalog, row.on_grid, row.catalog_m12b) == (3, 2, 2, 0)
    assert ("(accessories outside a frame)", 1) in row.top_missing
    assert voxelize(flatten(mpd))[1].contained == 1


def test_load_source_keeps_accessories_apart(tmp_path: Path) -> None:
    from brickwfc.alt.inputs import load_source

    model = tmp_path / "model.ldr"
    model.write_text("1 15 0 -48 0 1 0 0 0 1 0 0 0 1 60592.dat\n1 47 0 -48 0 1 0 0 0 1 0 0 0 1 60601.dat\n"
                     "1 4 100 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n", encoding="utf-8")
    source = load_source(str(model))
    assert source.inventory == {("window1x2x2_60592", "white"): 1, ("brick2x4", "red"): 1} and source.ignored == {}
    assert source.accessories == {("60601.dat", TRANS_CLEAR): 1}
    assert load_source(str(model), catalog="m8").accessories == {}


def test_build_files_carry_the_glass_with_its_frame(tmp_path: Path) -> None:
    frame = PlacedPart(Shape(CATALOG["window1x2x2_60592"], 1), WHITE, 3, 2, 1)
    base = PlacedPart(Shape(CATALOG["brick2x4"]), RED, 0, 0, 0)
    steps = step_placements([base, frame], {("60601.dat", TRANS_CLEAR): 2})
    assert [[p.part for p in step] for step in steps] == [["3001.dat"], ["60592.dat", "60601.dat"]]
    glass = steps[1][1]
    assert glass.position == steps[1][0].position and glass.rotation == steps[1][0].rotation  # its slot: the frame's origin
    ldr, _ = write_build([base, frame], (9, 4, 4), tmp_path / "build", "test", {("60601.dat", TRANS_CLEAR): 2})
    assert [p.part for step in parse_steps(ldr.read_text()) for p in step] == ["3001.dat", "60592.dat", "60601.dat"]


# Baseplates: the whole ground (approved by the coordinator, 2026-10-15) -----------------------------------------


def test_a_baseplate_build_is_exported_onto_the_table(tmp_path: Path) -> None:
    plate = PlacedPart(Shape(CATALOG["baseplate16x32"]), WHITE, 0, 0, 0)
    brick = PlacedPart(Shape(CATALOG["brick2x4"]), RED, 1, 3, 2)
    out = build_placements([plate, brick])
    # The baseplate's 4 LDU body lies on the table (y = 0 at its bottom) and the brick sits on its top face.
    assert out[0].position[1] == -PLATE_LDU + BASEPLATE_DROP_LDU == -4
    assert out[1].position[1] - 3 * -PLATE_LDU == out[0].position[1]  # the brick's bottom (origin + 24) at the plate's top
    # Builds without one are exported as before.
    assert build_placements([brick]) == [brick.placement()]
    # The preview/export helpers agree, step by step.
    assert [p for step in step_placements([plate, brick]) for p in step] == out


def test_nothing_shares_the_ground_with_a_baseplate() -> None:
    parts = part_tileset([CATALOG["baseplate16x32"], CATALOG["brick2x4"], CATALOG["plate1x2"]], [RED, WHITE])
    inventory = {("baseplate16x32", "white"): 1, ("brick2x4", "red"): 10, ("plate1x2", "red"): 20}
    builder = BottomUpBuilder(parts, any_offset=True, balanced=True, holes=True, hang=True)
    used = 0
    for seed in range(8):
        grid = builder.build((6, 20, 36), np.random.default_rng(seed), inventory)
        placed = check_build(grid, parts)
        ground = [p for p in placed if p.layer == 0]
        bases = [p for p in ground if p.shape.part.ground_only]
        assert all(p.layer == 0 for p in placed if p.shape.part.ground_only)
        if bases:
            used += 1
            assert ground == bases  # the baseplate is the whole ground
    assert used  # it does get used


def test_wfc_leaves_ground_only_parts_out() -> None:
    assert not CATALOG["baseplate32x32"].wfc and CATALOG["brick2x4"].wfc
    assert wfc_inventory({("baseplate32x32", "white"): 1, ("brick2x4", "red"): 2}) == {("brick2x4", "red"): 2}
    with pytest.raises(ValueError, match="baseplate32x32"):
        SupportConstraint(part_tileset([CATALOG["baseplate32x32"], CATALOG["brick2x4"]], [RED]))
