from pathlib import Path

import numpy as np
import pytest

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import PLATES, PartSet, extract_parts, part_tileset
from brickwfc.bricks.shapes import SHAPES, ShapeConstraint, arch, fill, mushroom, outside, pyramid
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.support import is_stable
from brickwfc.experiments.shape import main as experiment_main
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
