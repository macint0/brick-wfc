"""M12 step 1b: tip-over check (clusters on a table) and the balanced bottom-up builder."""

import math
from collections import Counter

import numpy as np
import pytest

from brickwfc.bricks.balance import Balance, clusters, convex_hull, outside_distance
from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import CATALOG, PLATES, PlacedPart, Shape, extract_parts, part_tileset
from brickwfc.bricks.physics import required_clutch, table_clutch, tipping_clusters

RED = colors_by_name(["red"])[0]


def piece(name: str, layer: int, x: int, z: int, rotated: bool = False) -> PlacedPart:
    return PlacedPart(Shape(CATALOG[name], rotated), RED, layer, x, z)


def test_convex_hull_and_distance() -> None:
    square = [(0, 0), (2, 0), (2, 2), (0, 2), (1, 1), (1, 0)]
    hull = convex_hull(square)
    assert sorted(hull) == [(0, 0), (0, 2), (2, 0), (2, 2)]
    assert outside_distance((1, 1), hull) == pytest.approx(-1)
    assert outside_distance((3, 1), hull) == pytest.approx(1)
    assert outside_distance((2, 1), hull) == pytest.approx(0)


def test_overhang_on_a_single_stud_tips_over() -> None:
    # A 1x1 plate on the ground carrying a 2x4 plate by its corner stud: the 2x4's weight is far outside.
    tipping = [piece("plate1x1", 0, 0, 0), piece("plate2x4", 1, 0, 0)]
    assert required_clutch(tipping, (2, 2, 4)) == math.inf
    # Centre of mass x = (1 * 0.5 + 8 * 2) / 9, past the 1x1's edge at x = 1.
    [(members, distance)] = tipping_clusters(tipping)
    assert members == [0, 1] and distance == pytest.approx((0.5 + 16) / 9 - 1)
    # The same 2x4 bridging two pillars at its ends stands with no clutch at all.
    bridge = [piece("plate1x1", 0, 0, 0), piece("plate1x1", 0, 3, 0), piece("plate2x4", 1, 0, 0)]
    assert required_clutch(bridge, (2, 2, 4)) == 0.0 and tipping_clusters(bridge) == []


def test_separate_stacks_are_separate_clusters() -> None:
    placed = [piece("plate2x2", 0, 0, 0), piece("plate2x2", 1, 0, 0), piece("plate1x1", 0, 5, 0)]
    found = clusters(placed)
    assert [members for members, _ in found] == [[0, 1], [2]]
    assert all(c.stands() for _, c in found)


def test_balance_refuses_a_part_that_would_tip() -> None:
    balance = Balance()
    base = piece("plate1x1", 0, 0, 0)
    assert balance.can_add(base, set())
    balance.add(base, set())
    assert not balance.can_add(piece("plate2x4", 1, 0, 0), {0})
    assert balance.can_add(piece("plate1x1", 1, 0, 0), {0})


@pytest.fixture(scope="module")
def parts():
    return part_tileset(list(PLATES.values()) + [CATALOG["brick1x2"], CATALOG["brick2x4"]],
                        colors_by_name(["red", "blue"]), empty_weight=1.0)


def test_tipping_clusters_match_the_physics_lp(parts) -> None:
    """Finite required clutch iff no cluster tips, on random unbalanced builds."""
    tipped = 0
    for seed in range(40):
        grid = BottomUpBuilder(parts, any_offset=True).build((6, 5, 5), np.random.default_rng(seed))
        placed, errors = extract_parts(grid, parts)
        assert not errors
        infinite = math.isinf(required_clutch(placed, grid.shape))
        assert infinite == bool(tipping_clusters(placed))
        tipped += infinite
    assert tipped > 0  # the check is exercised


def test_balanced_builds_never_tip(parts) -> None:
    for seed in range(40):
        grid = BottomUpBuilder(parts, any_offset=True, balanced=True).build((6, 5, 5), np.random.default_rng(seed))
        placed, _ = extract_parts(grid, parts)
        assert placed and math.isfinite(required_clutch(placed, grid.shape))


@pytest.fixture(scope="module")
def tile_parts():
    return part_tileset(list(PLATES.values()) + [CATALOG["brick2x4"], CATALOG["tile2x2"]],
                        colors_by_name(["red", "blue"]), empty_weight=1.0)


def test_connect_pass_makes_one_piece(tile_parts) -> None:
    inventory = {("plate2x4", "red"): 6, ("plate1x2", "blue"): 10, ("brick2x4", "red"): 4, ("plate1x1", "red"): 8,
                 ("tile2x2", "blue"): 4}
    plain = BottomUpBuilder(tile_parts, any_offset=True, balanced=True, bridge=True)
    connected = BottomUpBuilder(tile_parts, any_offset=True, balanced=True, bridge=True, connect=True)
    split = 0
    for seed in range(30):
        before, _ = extract_parts(plain.build((8, 6, 6), np.random.default_rng(seed), inventory), tile_parts)
        split += len(clusters(before)) > 1
        grid = connected.build((8, 6, 6), np.random.default_rng(seed), inventory)
        placed, errors = extract_parts(grid, tile_parts)
        assert not errors  # in particular nothing rests on a tile placed under an existing part
        assert len(clusters(placed)) == 1 and math.isfinite(required_clutch(placed, grid.shape))
        used = Counter((p.shape.part.name, p.color.name) for p in placed)
        assert all(used[key] <= count for key, count in inventory.items())
    assert split > 0  # the repair pass was exercised


def test_bridge_needs_balance(tile_parts) -> None:
    with pytest.raises(ValueError):
        BottomUpBuilder(tile_parts, any_offset=True, bridge=True)


def test_table_clutch_matches_required_clutch(parts) -> None:
    for seed in range(15):
        grid = BottomUpBuilder(parts, any_offset=True).build((6, 5, 5), np.random.default_rng(seed))
        placed, _ = extract_parts(grid, parts)
        assert table_clutch(placed, grid.shape) == pytest.approx(required_clutch(placed, grid.shape), rel=1e-6, abs=1e-6)
