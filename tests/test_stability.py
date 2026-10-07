from pathlib import Path

import numpy as np
import pytest

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import PLATES, PartSet, PlacedPart, Shape, extract_parts, part_tileset
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.support import is_stable, overhanging_parts, unsupported_parts
from brickwfc.experiments.stability import main as experiment_main
from brickwfc.wfc import Wave, run

RED = colors_by_name(["red"])[0]


@pytest.fixture(scope="module")
def free_parts() -> PartSet:
    return part_tileset(list(PLATES.values()), colors_by_name(["red", "blue"]), support="none")


def plate(name: str, layer: int, x: int, z: int, rotated: bool = False) -> PlacedPart:
    return PlacedPart(Shape(PLATES[name], rotated), RED, layer, x, z)


def occupancy(placed: list[PlacedPart], shape: tuple[int, int, int]) -> np.ndarray:
    filled = np.zeros(shape, dtype=bool)
    for p in placed:
        for cell in p.cells():
            filled[cell] = True
    return filled


def test_verifier_accepts_part_held_by_one_stud() -> None:
    placed = [plate("plate1x1", 0, 0, 0), plate("plate2x4", 1, 0, 0)]  # 2x4 bridged by a single stud
    filled = occupancy(placed, (2, 2, 4))
    assert is_stable(placed, filled)
    assert overhanging_parts(placed, filled) == [placed[1]]


def test_verifier_rejects_floating_part() -> None:
    placed = [plate("plate1x1", 0, 0, 0), plate("plate1x2", 1, 2, 0)]
    filled = occupancy(placed, (2, 1, 4))
    assert unsupported_parts(placed, filled) == [placed[1]]


def test_prune_removes_unsupportable_tiles(free_parts: PartSet) -> None:
    constraint = SupportConstraint(free_parts)
    wave = Wave(free_parts.tileset, (2, 1, 4), [constraint])
    empty = free_parts.tileset.index("empty")
    for x in range(4):
        wave.assign((0, 0, x), empty)  # nothing on layer 0
    assert wave.settle([(0, 0, x) for x in range(4)])
    # With an empty layer 0, nothing on layer 1 can be supported.
    assert not (wave.domain[1] & free_parts.solid).any()


def test_force_makes_last_supporter_solid(free_parts: PartSet) -> None:
    constraint = SupportConstraint(free_parts)
    wave = Wave(free_parts.tileset, (2, 1, 2), [constraint])
    names = free_parts.tileset.names
    empty = names.index("empty")
    wave.assign((0, 0, 0), empty)
    assert wave.settle([(0, 0, 0)])
    # A 1x2 on layer 1 over x=0..1: only the cell below x=1 can hold it up, so it must be solid.
    wave.assign((1, 0, 0), names.index("plate1x2_x0z0_red"))
    assert wave.settle([(1, 0, 0)])
    assert not wave.domain[0, 0, 1, empty]
    assert wave.domain[0, 0, 1][free_parts.solid].any()


def test_stability_aware_builds_are_always_stable(free_parts: PartSet) -> None:
    constraint = SupportConstraint(free_parts)
    with_overhang = 0
    for seed in range(40):
        result = run(free_parts.tileset, (4, 5, 5), seed, constraints=[constraint])
        assert result.grid is not None
        placed, errors = extract_parts(result.grid, free_parts)
        filled = free_parts.solid[result.grid]
        assert errors == []
        assert is_stable(placed, filled), f"seed {seed}: {unsupported_parts(placed, filled)}"
        with_overhang += bool(overhanging_parts(placed, filled))
    assert with_overhang > 0  # stability-aware, not just the per-cell rule in disguise


def test_plain_wfc_produces_unstable_builds(free_parts: PartSet) -> None:
    unstable = 0
    for seed in range(10):
        grid = run(free_parts.tileset, (4, 5, 5), seed).grid
        placed, _ = extract_parts(grid, free_parts)
        unstable += not is_stable(placed, free_parts.solid[grid])
    assert unstable > 0  # otherwise the A vs B comparison would be vacuous


def test_constraint_is_deterministic(free_parts: PartSet) -> None:
    constraint = SupportConstraint(free_parts)
    a = run(free_parts.tileset, (3, 4, 4), 5, constraints=[constraint]).grid
    b = run(free_parts.tileset, (3, 4, 4), 5, constraints=[constraint]).grid
    np.testing.assert_array_equal(a, b)


def test_experiment_cli(tmp_path: Path) -> None:
    assert experiment_main(["--seeds", "3", "--sizes", "3x3x2", "--out", str(tmp_path)]) == 0
    table = (tmp_path / "results.md").read_text()
    for condition in ("A_plain", "B_aware", "C_per_cell", "D_bottom_up"):
        assert condition in table
    assert len((tmp_path / "runs.jsonl").read_text().splitlines()) == 12
    # A second invocation resumes: everything is already done, so nothing is re-run or duplicated.
    assert experiment_main(["--seeds", "3", "--sizes", "3x3x2", "--out", str(tmp_path)]) == 0
    assert len((tmp_path / "runs.jsonl").read_text().splitlines()) == 12


def test_bottom_up_builds_are_whole_and_stable(free_parts: PartSet) -> None:
    builder = BottomUpBuilder(free_parts)
    for seed in range(30):
        grid = builder.build((4, 5, 5), np.random.default_rng(seed))
        placed, errors = extract_parts(grid, free_parts)
        assert errors == []
        assert is_stable(placed, free_parts.solid[grid])
    a = builder.build((3, 4, 4), np.random.default_rng(1))
    np.testing.assert_array_equal(a, builder.build((3, 4, 4), np.random.default_rng(1)))
