"""M12b holes: the hole-filling pass of the bottom-up builder (with and without hanging parts), the support
check and physics of hung parts, and the completeness metrics."""

from collections import Counter

import numpy as np
import pytest

from brickwfc.alt.features import completeness, exposed
from brickwfc.bricks.balance import clusters
from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.parts import CATALOG, PlacedPart, Shape, extract_parts, part_tileset
from brickwfc.bricks.physics import required_clutch, table_clutch
from brickwfc.bricks.shapes import fill
from brickwfc.bricks.support import is_stable, stud_joints
from brickwfc.bricks.symmetry import mirror_plane
from conftest import BLUE, RED

NAMES = ("plate1x1", "plate1x2", "plate2x2", "plate2x4", "brick1x1", "brick1x2", "brick2x2", "brick2x4",
         "plate2x2_corner", "slope45_2x2", "tile1x2")


@pytest.fixture(scope="module")
def parts():
    return part_tileset([CATALOG[n] for n in NAMES], [RED, BLUE], empty_weight=0.05)


def target() -> np.ndarray:
    """A stepped block with a thin post on top, on a 10-wide grid."""
    mask = np.zeros((9, 6, 10), dtype=bool)
    mask[:6, :, 1:9] = True
    mask[6:, 0:3, 3:7] = True
    mask[6:, 4, 8] = True
    return mask


def table() -> np.ndarray:
    """Four 2 x 2 legs, 6 plates tall, under a 10 x 10 top 3 plates thick: bottom-up, the top's underside is
    reached only by cantilevering from the legs."""
    mask = np.zeros((9, 10, 10), dtype=bool)
    for z in (0, 8):
        for x in (0, 8):
            mask[:6, z : z + 2, x : x + 2] = True
    mask[6:] = True
    return mask


def inventory(count: int) -> dict:
    return {(n, c.name): count for n in NAMES for c in (RED, BLUE)}


def check(grid: np.ndarray, parts, allowed: np.ndarray, stock: dict | None = None,
          hanging: bool = False) -> list[PlacedPart]:
    placed, errors = extract_parts(grid, parts)
    assert not errors
    assert all(allowed[c] for p in placed for c in p.cells())
    assert is_stable(placed, parts.solid[grid], hanging)
    if stock is not None:
        used = Counter((p.shape.part.name, p.color.name) for p in placed)
        assert all(n <= stock.get(k, 0) for k, n in used.items())
    return placed


def filled_share(grid: np.ndarray, parts, mask: np.ndarray) -> float:
    return fill(parts.solid[grid], mask)


def fitting_parts(builder: BottomUpBuilder, placed: list[PlacedPart], mask: np.ndarray, stock: dict) -> list:
    """Every placement of a part the inventory still has that would fit (or hang, with the builder's ``hang``),
    covering an empty target cell, in the finished build (rebuilt from its parts, lowest first)."""
    state = builder._new_state(mask.shape, stock, mask, None, None)
    for part in sorted(placed, key=lambda p: p.layer):
        builder._put(state, part, builder._links(part, state.owner) if builder.hang else None)
    found = []
    for y, z, x in np.argwhere(mask & ~state.filled).tolist():
        for shape, color in builder.choices:
            if state.remaining.get((shape.part.name, color.name), 0) <= 0:
                continue
            for dz, dx in shape.footprint:
                part = PlacedPart(shape, color, y, x - dx, z - dz)
                if builder._fits_now(part, state, mask, builder.hang):
                    found.append(part)
    return found


def test_holes_off_by_default_and_need_their_options(parts) -> None:
    builder = BottomUpBuilder(parts)
    assert not builder.holes and not builder.hang
    with pytest.raises(ValueError):
        BottomUpBuilder(parts, holes=True)
    with pytest.raises(ValueError):
        BottomUpBuilder(parts, any_offset=True, hang=True)


def test_hole_pass_only_adds_parts_and_keeps_the_rules(parts) -> None:
    # Without the connect pass, the main pass draws the same numbers with or without holes, so the hole pass
    # can only add parts to the same build.
    mask, stock = target(), inventory(8)
    plain = BottomUpBuilder(parts, any_offset=True, balanced=True, open_tops=True)
    holes = BottomUpBuilder(parts, any_offset=True, balanced=True, open_tops=True, holes=True)
    for seed in range(6):
        a = plain.build(mask.shape, np.random.default_rng(seed), stock, mask)
        b = holes.build(mask.shape, np.random.default_rng(seed), stock, mask)
        assert set(check(a, parts, mask, stock)) <= set(check(b, parts, mask, stock))


def test_no_part_fits_any_hole_after_the_pass(parts) -> None:
    mask, stock = target(), inventory(5)
    builder = BottomUpBuilder(parts, any_offset=True, balanced=True, open_tops=True, holes=True)
    for seed in range(4):
        placed = check(builder.build(mask.shape, np.random.default_rng(seed), stock, mask), parts, mask, stock)
        assert fitting_parts(builder, placed, mask, stock) == []


def test_hole_pass_is_deterministic(parts) -> None:
    mask = table()
    builder = BottomUpBuilder(parts, any_offset=True, balanced=True, bridge=True, connect=True, connect_rounds=3,
                              open_tops=True, holes=True, hang=True)
    for seed in range(3):
        a = builder.build(mask.shape, np.random.default_rng(seed), inventory(6), mask)
        b = builder.build(mask.shape, np.random.default_rng(seed), inventory(6), mask)
        assert (a == b).all()


def test_holes_with_connect_stay_one_piece(parts) -> None:
    mask, stock = target(), inventory(8)
    builder = BottomUpBuilder(parts, any_offset=True, balanced=True, bridge=True, connect=True, connect_rounds=3,
                              open_tops=True, holes=True)
    for seed in range(6):
        grid = builder.build(mask.shape, np.random.default_rng(seed), stock, mask)
        assert len(clusters(check(grid, parts, mask, stock))) == 1


def test_hanging_fills_the_underside_of_a_table_top(parts) -> None:
    mask, stock = table(), inventory(12)
    kwargs = dict(any_offset=True, balanced=True, bridge=True, connect=True, connect_rounds=3, open_tops=True)
    builders = (BottomUpBuilder(parts, **kwargs), BottomUpBuilder(parts, holes=True, **kwargs),
                BottomUpBuilder(parts, holes=True, hang=True, **kwargs))
    hung = 0
    for seed in range(4):
        a, b, c = (builder.build(mask.shape, np.random.default_rng(seed), stock, mask) for builder in builders)
        check(a, parts, mask, stock)
        check(b, parts, mask, stock)
        placed = check(c, parts, mask, stock, hanging=True)
        assert len(clusters(placed)) == 1 and np.isfinite(table_clutch(placed, mask.shape))
        hung += not is_stable(placed, parts.solid[c])  # some part hangs (no stud below it)
        underside = [parts.solid[g][6].mean() for g in (a, b, c)]
        assert underside[2] > 0.8 > max(underside[:2])
        assert filled_share(c, parts, mask) > max(filled_share(a, parts, mask), filled_share(b, parts, mask))
    assert hung == 4


def test_no_part_fits_or_hangs_anywhere_after_the_pass(parts) -> None:
    mask, stock = table(), inventory(4)
    builder = BottomUpBuilder(parts, any_offset=True, balanced=True, open_tops=True, holes=True, hang=True)
    for seed in range(2):
        placed = check(builder.build(mask.shape, np.random.default_rng(seed), stock, mask), parts, mask, stock,
                       hanging=True)
        assert fitting_parts(builder, placed, mask, stock) == []


def test_holes_with_a_mirror_plane_and_a_short_inventory(parts) -> None:
    mask = target()
    mask[6:, 4, 8] = False  # symmetric across x = 4.5 again
    stock = {("brick2x2", "red"): 3, ("plate1x2", "blue"): 5, ("plate1x1", "red"): 2}
    for hang in (False, True):
        builder = BottomUpBuilder(parts, any_offset=True, balanced=True, open_tops=True, holes=True, hang=hang)
        for seed in range(4):
            grid = builder.build(mask.shape, np.random.default_rng(seed), stock, mask, plane=mirror_plane(mask))
            placed = check(grid, parts, mask, stock, hanging=hang)
            assert fitting_parts(builder, placed, mask, stock) == []


def test_support_and_physics_of_a_hung_part() -> None:
    # A 2 x 2 brick column, a 2 x 4 plate on it reaching out by two studs, a 1 x 2 plate hung under the reach.
    column = PlacedPart(Shape(CATALOG["brick2x2"]), RED, 0, 0, 0)
    top = PlacedPart(Shape(CATALOG["plate2x4"]), RED, 3, 0, 0)
    hung = PlacedPart(Shape(CATALOG["plate1x2"]), BLUE, 2, 2, 0)
    placed = [column, top, hung]
    assert all(cell[2] < 4 and cell[1] < 2 for p in placed for cell in p.cells())
    filled = np.zeros((4, 2, 4), dtype=bool)
    for part in placed:
        for cell in part.cells():
            filled[cell] = True
    assert stud_joints(placed) == {(1, 0), (1, 2)}
    assert not is_stable(placed, filled) and is_stable(placed, filled, hanging=True)
    clutch = required_clutch(placed, filled.shape)
    assert 0 < clutch < 1111  # the hung plate is held by its studs in the top's underside
    floating = [column, hung]  # without the top, the hung plate has nothing to hang from
    assert not is_stable(floating, filled, hanging=True) and required_clutch(floating, filled.shape) == np.inf
    pair = [top, hung]  # joined to each other but not to the ground
    assert not is_stable(pair, filled, hanging=True)


def test_completeness_counts_holes_and_the_outer_surface() -> None:
    mask = np.ones((3, 3, 3), dtype=bool)
    filled = mask.copy()
    filled[1, 1, 1] = False  # inside: a hole, not on the surface
    filled[0, 0, 0] = False  # a corner on the ground: a hole on the surface
    # Exposed: all but the centre and the cell under it (its bottom face is on the ground).
    assert exposed(mask).sum() == 25 and not exposed(mask)[0, 1, 1]
    done = completeness(filled, mask)
    assert (done.holes, done.largest_hole) == (2, 1) and done.surface == pytest.approx(24 / 25)
    filled[1, 0, 0] = filled[2, 0, 0] = False  # the corner hole grows up the edge
    done = completeness(filled, mask)
    assert (done.holes, done.largest_hole) == (2, 3)
    assert completeness(mask, mask) == type(done)(0, 0, 1.0)
