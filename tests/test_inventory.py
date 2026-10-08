from pathlib import Path

import numpy as np
import pytest

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.inventory import (
    InventoryConstraint,
    inventory_cells,
    inventory_coverage,
    inventory_from_mpd,
    overuse,
    usage,
    utilization,
)
from brickwfc.bricks.parts import PLATE_FILES, PLATES, PlacedPart, Shape, extract_parts, part_tileset
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.support import is_stable
from brickwfc.experiments.inventory import grid_for, main as experiment_main
from brickwfc.tileset import Tileset
from brickwfc.wfc import Wave, attempt_rng, run, solve_attempt

RED, BLUE = colors_by_name(["red", "blue"])

MPD = """0 FILE main.ldr
1 4 0 0 0 1 0 0 0 1 0 0 0 1 sub.ldr
1 1 100 -24 0 0 0 1 0 1 0 -1 0 0 sub.ldr
0 NOFILE
0 FILE sub.ldr
1 16 10 -8 0 1 0 0 0 1 0 0 0 1 3023.dat
1 15 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat
1 15 0 -8 0 1 0 0 0 1 0 0 0 1 3020.dat
0 NOFILE
"""


def test_inventory_from_mpd_counts_parts_and_colors() -> None:
    inventory, unsupported, colors = inventory_from_mpd(MPD, PLATE_FILES)  # M9: the four plates only
    assert inventory == {("plate1x2", "red"): 1, ("plate1x2", "blue"): 1, ("plate2x4", "white"): 2}
    assert unsupported == {"3001.dat": 2}
    assert {c.name for c in colors} == {"red", "blue", "white"}
    assert inventory_cells(inventory) == 2 * 2 + 2 * 8
    inventory, unsupported, _ = inventory_from_mpd(MPD)  # the whole catalog: 3001 is a 2x4 brick
    assert inventory[("brick2x4", "white")] == 2 and not unsupported
    assert inventory_cells(inventory) == 2 * 2 + 2 * 8 + 2 * 8 * 3


def test_coverage_splits_orientations() -> None:
    coverage = inventory_coverage({("plate1x2", "red"): 3, ("plate2x2", "blue"): 1})
    assert coverage == {("plate1x2", "red"): 3.0, ("plate1x2_r90", "red"): 3.0, ("plate2x2", "blue"): 4.0}


def test_usage_overuse_utilization() -> None:
    placed = [PlacedPart(Shape(PLATES["plate1x1"], False), RED, 0, x, 0) for x in range(3)]
    inventory = {("plate1x1", "red"): 2, ("plate2x4", "blue"): 2}
    assert usage(placed) == {("plate1x1", "red"): 3}
    assert overuse(placed, inventory) == {("plate1x1", "red"): 1}
    assert utilization(placed, inventory) == pytest.approx(2 / 4)


def small_set() -> tuple[dict, object]:
    inventory = {("plate1x1", "red"): 3, ("plate1x2", "blue"): 2, ("plate2x2", "red"): 1}
    parts = part_tileset(list(PLATES.values()), [RED, BLUE], empty_weight=2.0, coverage=inventory_coverage(inventory))
    return inventory, parts


def test_inventory_constraint_never_overuses() -> None:
    inventory, parts = small_set()
    constraints = [SupportConstraint(parts), InventoryConstraint(parts, inventory)]
    for seed in range(20):
        result = run(parts.tileset, (3, 4, 4), seed, constraints=constraints, max_backtracks=200)
        assert result.grid is not None
        placed, errors = extract_parts(result.grid, parts)
        assert errors == []
        assert overuse(placed, inventory) == {}
        assert is_stable(placed, parts.solid[result.grid])


def test_inventory_constraint_detects_overuse() -> None:
    parts = part_tileset([PLATES["plate1x1"]], [RED])
    constraint = InventoryConstraint(parts, {("plate1x1", "red"): 1})
    wave = Wave(parts.tileset, (1, 1, 2), [constraint])
    red = parts.tileset.index("plate1x1_x0z0_red")
    wave.assign((0, 0, 0), red)
    wave.assign((0, 0, 1), red)
    assert constraint.prune(wave, {(0, 0, 0), (0, 0, 1)}) is None


def test_exhausted_part_is_pruned_everywhere() -> None:
    parts = part_tileset([PLATES["plate1x1"]], [RED])
    constraint = InventoryConstraint(parts, {("plate1x1", "red"): 1})
    wave = Wave(parts.tileset, (1, 1, 3), [constraint])
    red = parts.tileset.index("plate1x1_x0z0_red")
    wave.assign((0, 0, 0), red)
    assert wave.settle([(0, 0, 0)])
    assert not wave.domain[0, 0, 1:, red].any()  # the only red 1x1 is used up


def test_bottom_up_respects_inventory() -> None:
    inventory, parts = small_set()
    builder = BottomUpBuilder(parts)
    for seed in range(20):
        grid = builder.build((3, 4, 4), np.random.default_rng(seed), inventory)
        placed, errors = extract_parts(grid, parts)
        assert errors == [] and overuse(placed, inventory) == {}


def test_backtracking_rescues_attempts_that_restarts_cannot(three_coloring: Tileset) -> None:
    rescued = 0
    for seed in range(30):
        plain = solve_attempt(three_coloring, (16, 16), attempt_rng(seed, 0))
        if plain.grid is not None:
            continue
        backtracked = solve_attempt(three_coloring, (16, 16), attempt_rng(seed, 0), max_backtracks=500)
        if backtracked.grid is not None:
            rescued += 1
            assert backtracked.backtracks > 0
    assert rescued > 0


def test_grid_for_scales_with_inventory() -> None:
    assert grid_for({("plate2x4", "red"): 6}, height=6, room=1.5) == (6, 4, 4)  # 48 cells * 1.5 / 6 = 12 -> 4x4


def test_experiment_cli_offline(tmp_path: Path) -> None:
    data = tmp_path / "omr"
    data.mkdir()
    (data / "fake-1.mpd").write_text(MPD)
    args = ["--sets", "fake-1", "--data", str(data), "--seeds", "2", "--out", str(tmp_path / "m9")]
    assert experiment_main(args) == 0
    text = (tmp_path / "m9" / "results.md").read_text()
    for condition in ("A_filter", "B_inventory", "D_bottom_up"):
        assert condition in text
