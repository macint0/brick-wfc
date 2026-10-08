from pathlib import Path

import numpy as np
import pytest

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.inventory import InventoryConstraint, inventory_cells, inventory_coverage, overuse
from brickwfc.bricks.parts import PLATES, PartSet, extract_parts, part_tileset, shapes_of
from brickwfc.bricks.shapes import (
    MIN_SIDE,
    SHAPES,
    ShapeConstraint,
    arch,
    fill,
    iou,
    mushroom,
    outside,
    pyramid,
    scaled,
    sized_for,
)
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.support import is_stable
from brickwfc.experiments.shape import main as experiment_main
from brickwfc.experiments.shape_inventory import main as shape_inventory_main
from brickwfc.wfc import run


@pytest.fixture(scope="module")
def parts() -> PartSet:
    return part_tileset(list(PLATES.values()), colors_by_name(["red", "blue"]), empty_weight=0.2)


def test_shape_masks() -> None:
    p = pyramid(3, 6, 6)
    assert p[0].sum() == 36 and p[1].sum() == 16 and p[2].sum() == 4
    a = arch(4, 2, 6)
    assert a[0].sum() == 2 * 2 * 2 and a[3].all()  # two 2x2-footprint pillars, full span on top
    m = mushroom(4, 6, 6)
    assert m[0].sum() == 4 and m[3].all()
    for make in SHAPES.values():
        assert make(4, 6, 6).shape == (4, 6, 6)


def test_fill_and_outside() -> None:
    mask = np.zeros((1, 1, 4), dtype=bool)
    mask[0, 0, :2] = True
    filled = np.array([[[True, False, True, False]]])
    assert fill(filled, mask) == 0.5 and outside(filled, mask) == 1


@pytest.mark.parametrize("name", ["pyramid", "arch", "mushroom"])
def test_wfc_stays_inside_shape(parts: PartSet, name: str) -> None:
    mask = SHAPES[name](4, 6, 6)
    constraints = [SupportConstraint(parts), ShapeConstraint(parts, mask)]
    for seed in range(5):
        result = run(parts.tileset, mask.shape, seed, constraints=constraints, max_backtracks=500)
        assert result.grid is not None
        placed, errors = extract_parts(result.grid, parts)
        filled = parts.solid[result.grid]
        assert errors == [] and outside(filled, mask) == 0 and is_stable(placed, filled)
        assert fill(filled, mask) > 0.5


@pytest.mark.parametrize("name", ["pyramid", "arch", "mushroom"])
def test_bottom_up_stays_inside_shape(parts: PartSet, name: str) -> None:
    mask = SHAPES[name](4, 6, 6)
    builder = BottomUpBuilder(parts)
    for seed in range(5):
        grid = builder.build(mask.shape, np.random.default_rng(seed), allowed=mask)
        placed, errors = extract_parts(grid, parts)
        filled = parts.solid[grid]
        assert errors == [] and outside(filled, mask) == 0 and is_stable(placed, filled)


def test_experiment_cli(tmp_path: Path) -> None:
    args = ["--shapes", "pyramid", "--size", "4x4x3", "--seeds", "2", "--out", str(tmp_path)]
    assert experiment_main(args) == 0
    text = (tmp_path / "results.md").read_text()
    assert "B_wfc" in text and "D_bottom_up" in text


def test_iou() -> None:
    mask = np.zeros((1, 1, 4), dtype=bool)
    mask[0, 0, :2] = True
    assert iou(np.array([[[True, False, True, False]]]), mask) == pytest.approx(1 / 3)
    assert iou(mask.copy(), mask) == 1.0


@pytest.mark.parametrize("name", list(SHAPES))
def test_sized_for_matches_volume_and_keeps_character(name: str) -> None:
    for cells in (150, 300, 600):
        mask = sized_for(name, cells)
        assert mask.shape[1] == mask.shape[2] >= MIN_SIDE[name]
        assert abs(mask.sum() - cells) / cells <= 0.1
    small = sized_for(name, 10)  # too small for the shape: smallest one, larger than asked
    assert small.shape[1] == MIN_SIDE[name] and small.sum() > 10
    big = scaled(name, 6, 12)
    if name == "arch":
        assert not big[0, :, 3:-3].any() and big[-1].all()
    if name == "mushroom":
        assert big[0].sum() == 9 and big[-1].all()  # stem 12 // 4 = 3 studs wide
    if name == "ring":
        assert not big[:, 2:-2, 2:-2].any()


def test_bottom_up_any_offset_reaches_into_gaps(parts: PartSet) -> None:
    # Row of 3 cells, the first one taken: a 1x2 plate anchored at the last cell would stick out of
    # the grid, but with any offset it can cover cells 1-2.
    filled = np.zeros((1, 1, 3), dtype=bool)
    filled[0, 0, 0] = True
    allowed = np.ones_like(filled)
    plate = next(s for s in shapes_of([PLATES["plate1x2"]]) if s.size_x == 2)
    red = colors_by_name(["red"])[0]
    rng = np.random.default_rng(0)
    studs = np.zeros_like(filled)
    assert BottomUpBuilder(parts)._place(plate, red, 0, 0, 2, filled, studs, allowed, rng) is None
    part = BottomUpBuilder(parts, any_offset=True)._place(plate, red, 0, 0, 2, filled, studs, allowed, rng)
    assert part is not None and part.cells() == [(0, 0, 1), (0, 0, 2)]


@pytest.mark.parametrize("name", list(SHAPES))
def test_bottom_up_any_offset_builds_valid_shapes(name: str) -> None:
    inventory = {("plate2x4", "red"): 6, ("plate2x2", "blue"): 6, ("plate1x2", "red"): 8, ("plate1x1", "blue"): 4}
    parts = part_tileset(list(PLATES.values()), colors_by_name(["red", "blue"]), 0.2, coverage=inventory_coverage(inventory))
    mask = sized_for(name, inventory_cells(inventory))
    builder = BottomUpBuilder(parts, any_offset=True)
    for seed in range(10):
        grid = builder.build(mask.shape, np.random.default_rng(seed), inventory, allowed=mask)
        assert np.array_equal(grid, builder.build(mask.shape, np.random.default_rng(seed), inventory, allowed=mask))
        placed, errors = extract_parts(grid, parts)
        filled = parts.solid[grid]
        assert errors == [] and outside(filled, mask) == 0 and is_stable(placed, filled)
        assert not overuse(placed, inventory) and fill(filled, mask) > 0.3


def test_wfc_shape_and_inventory_together() -> None:
    inventory = {("plate2x4", "red"): 3, ("plate2x2", "blue"): 4, ("plate1x2", "red"): 6, ("plate1x1", "blue"): 4}
    parts = part_tileset(list(PLATES.values()), colors_by_name(["red", "blue"]), 0.2, coverage=inventory_coverage(inventory))
    mask = sized_for("arch", inventory_cells(inventory))
    constraints = [SupportConstraint(parts), ShapeConstraint(parts, mask), InventoryConstraint(parts, inventory)]
    for seed in range(3):
        result = run(parts.tileset, mask.shape, seed, constraints=constraints, max_backtracks=1000)
        assert result.grid is not None
        placed, errors = extract_parts(result.grid, parts)
        filled = parts.solid[result.grid]
        assert errors == [] and outside(filled, mask) == 0 and is_stable(placed, filled)
        assert not overuse(placed, inventory)


SET_MPD = """0 FILE main.ldr
1 4 0 0 0 1 0 0 0 1 0 0 0 1 3020.dat
1 4 0 -8 0 1 0 0 0 1 0 0 0 1 3020.dat
1 1 0 -16 0 1 0 0 0 1 0 0 0 1 3022.dat
1 1 0 -24 0 1 0 0 0 1 0 0 0 1 3022.dat
1 4 0 -32 0 1 0 0 0 1 0 0 0 1 3023.dat
1 4 0 -40 0 1 0 0 0 1 0 0 0 1 3023.dat
1 1 0 -48 0 1 0 0 0 1 0 0 0 1 3024.dat
1 1 0 -56 0 1 0 0 0 1 0 0 0 1 3024.dat
0 NOFILE
"""


def test_shape_inventory_experiment_cli_offline(tmp_path: Path) -> None:
    data = tmp_path / "omr"
    data.mkdir()
    (data / "fake-1.mpd").write_text(SET_MPD)
    out = tmp_path / "m11"
    args = ["--sets", "fake-1", "--data", str(data), "--shapes", "block", "pyramid", "--seeds", "2",
            "--export", "1", "--out", str(out)]
    assert shape_inventory_main(args) == 0
    text = (out / "results.md").read_text()
    for condition in ("B_wfc", "D_bottom_up", "D2_bottom_up_any_offset"):
        assert condition in text
    assert len(list((out / "builds").glob("*.ldr"))) == 2 * 3
    lines = (out / "runs.jsonl").read_text().splitlines()
    assert len(lines) == 2 * 3 * 2
    assert shape_inventory_main(args) == 0  # resumes: nothing is rerun
    assert len((out / "runs.jsonl").read_text().splitlines()) == len(lines)
