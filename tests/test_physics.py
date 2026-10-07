import math

import numpy as np
import pytest

from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import PLATES, PlacedPart, Shape, extract_parts, part_tileset
from brickwfc.bricks.physics import is_physically_stable, required_clutch
from brickwfc.bricks.support import is_stable
from brickwfc.wfc import run

RED = colors_by_name(["red"])[0]


def plate(name: str, layer: int, x: int, z: int, rotated: bool = False) -> PlacedPart:
    return PlacedPart(Shape(PLATES[name], rotated), RED, layer, x, z)


def test_resting_and_stacked_parts_need_no_clutch() -> None:
    assert required_clutch([plate("plate2x4", 0, 0, 0)], (1, 2, 4)) == 0.0
    assert required_clutch([plate("plate2x4", 0, 0, 0), plate("plate2x4", 1, 0, 0)], (2, 2, 4)) == 0.0


def test_bridge_over_two_pillars_needs_no_clutch() -> None:
    placed = [plate("plate1x1", 0, 0, 0), plate("plate1x1", 0, 3, 0), plate("plate1x2", 0, 0, 1), plate("plate2x4", 1, 0, 0)]
    assert required_clutch(placed, (2, 2, 4)) == 0.0


def test_floating_part_cannot_stand() -> None:
    assert required_clutch([plate("plate1x1", 1, 0, 0)], (2, 1, 1)) == math.inf


def test_build_that_tips_over_its_ground_contact_cannot_stand() -> None:
    # A 2x4 balanced on one corner 1x1: the whole thing's centre of mass is outside its ground contact,
    # and the ground can only push, so no clutch can hold it. The simple rule still accepts it.
    placed = [plate("plate1x1", 0, 0, 0), plate("plate2x4", 1, 0, 0)]
    assert is_stable(placed, np.ones((2, 2, 4), dtype=bool))
    assert required_clutch(placed, (2, 2, 4)) == math.inf


def test_cantilever_needs_clutch() -> None:
    # On a wide base, a 2x4 held by a single corner stud: clutch must resist the overturning moment.
    # Torque about the far edge of the supporting cell is 8 weights x 1 stud; the stud ring's pull
    # points sit 0.2 and 0.8 studs from that edge (2 each): 2t(0.8 + 0.2) = 8 -> t = 4 per point,
    # 16 per stud.
    placed = [plate("plate2x4", 0, 0, 0), plate("plate1x1", 1, 0, 0), plate("plate2x4", 2, 0, 0)]
    assert required_clutch(placed, (3, 2, 4)) == pytest.approx(16.0)
    assert is_physically_stable(placed, (3, 2, 4), clutch=20)
    assert not is_physically_stable(placed, (3, 2, 4), clutch=10)


def test_centred_support_needs_less_clutch_than_corner_support() -> None:
    corner = [plate("plate2x4", 0, 0, 0), plate("plate1x1", 1, 0, 0), plate("plate2x4", 2, 0, 0)]
    centred = [plate("plate2x4", 0, 0, 0), plate("plate1x2", 1, 1, 0), plate("plate2x4", 2, 0, 0)]
    assert required_clutch(centred, (3, 2, 4)) < required_clutch(corner, (3, 2, 4))


def test_per_cell_rule_builds_need_no_clutch() -> None:
    parts = part_tileset(list(PLATES.values()), colors_by_name(["red", "blue"]), support="cell")
    for seed in range(10):
        grid = run(parts.tileset, (3, 5, 5), seed).grid
        placed, _ = extract_parts(grid, parts)
        assert required_clutch(placed, grid.shape) == 0.0  # every stud rests on something


def test_baseplate_holds_down_a_build_that_would_tip_over() -> None:
    placed = [plate("plate1x1", 0, 0, 0), plate("plate2x4", 1, 0, 0)]
    assert required_clutch(placed, (2, 2, 4)) == math.inf
    held = required_clutch(placed, (2, 2, 4), baseplate=True)
    assert math.isfinite(held) and held > 0
