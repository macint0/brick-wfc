"""M12b: the connected growth order of the bottom-up builder (one piece by construction)."""

import numpy as np
import pytest

from brickwfc.bricks.balance import clusters
from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.parts import CATALOG, part_tileset
from brickwfc.bricks.physics import table_clutch
from brickwfc.bricks.symmetry import mirror_plane
from conftest import BLUE, RED
from test_holes import NAMES, check, inventory, table


@pytest.fixture(scope="module")
def parts():
    return part_tileset([CATALOG[n] for n in NAMES], [RED, BLUE], empty_weight=0.05)


def legs_on_the_ground(grid: np.ndarray, parts) -> int:
    """How many of the table's four legs have a part on the ground."""
    ground = parts.solid[grid][0]
    return sum(bool(ground[z : z + 2, x : x + 2].any()) for z in (0, 8) for x in (0, 8))


def test_connected_order_is_accepted_and_off_by_default(parts) -> None:
    assert BottomUpBuilder(parts).order == "random"
    BottomUpBuilder(parts, any_offset=True, order="connected")
    with pytest.raises(ValueError):
        BottomUpBuilder(parts, order="spiral")


def test_connected_growth_is_one_piece_without_the_repair(parts) -> None:
    # No connect pass at all: the growth itself keeps the build one piece, and with hang it reaches every leg
    # from the seed and hangs it down to the ground.
    mask, stock = table(), inventory(12)
    builder = BottomUpBuilder(parts, any_offset=True, balanced=True, bridge=True, open_tops=True, order="connected",
                              holes=True, hang=True)
    for seed in range(4):
        grid = builder.build(mask.shape, np.random.default_rng(seed), stock, mask)
        placed = check(grid, parts, mask, stock, hanging=True)
        assert len(clusters(placed)) == 1 and np.isfinite(table_clutch(placed, mask.shape))
        # The seed's leg plus at least two reached from it (three stand; a fourth can end a plate short of the
        # ground when the inventory has no plate of the leg's size left).
        assert legs_on_the_ground(grid, parts) >= 3
        assert parts.solid[grid][mask].mean() > 0.8


def test_without_hang_only_the_seed_reaches_the_ground(parts) -> None:
    mask, stock = table(), inventory(12)
    builder = BottomUpBuilder(parts, any_offset=True, balanced=True, open_tops=True, order="connected")
    for seed in range(3):
        grid = builder.build(mask.shape, np.random.default_rng(seed), stock, mask)
        placed = check(grid, parts, mask, stock)
        assert len(clusters(placed)) == 1
        assert sum(p.layer == 0 for p in placed) == 1


def test_connected_growth_is_deterministic(parts) -> None:
    mask = table()
    builder = BottomUpBuilder(parts, any_offset=True, balanced=True, bridge=True, connect=True, open_tops=True,
                              order="connected", holes=True, hang=True)
    for seed in range(2):
        a = builder.build(mask.shape, np.random.default_rng(seed), inventory(8), mask)
        b = builder.build(mask.shape, np.random.default_rng(seed), inventory(8), mask)
        assert (a == b).all()


def test_connected_growth_with_a_mirror_plane_and_a_short_inventory(parts) -> None:
    mask = table()
    stock = {("brick2x2", "red"): 6, ("plate2x4", "blue"): 8, ("plate1x2", "red"): 10, ("plate1x1", "blue"): 6}
    builder = BottomUpBuilder(parts, any_offset=True, balanced=True, open_tops=True, order="connected", holes=True,
                              hang=True)
    for seed in range(3):
        grid = builder.build(mask.shape, np.random.default_rng(seed), stock, mask, plane=mirror_plane(mask))
        assert len(clusters(check(grid, parts, mask, stock, hanging=True))) == 1


class _FirstHoles:
    """A builder trace that records the inventory left when the first hole pass starts."""

    def __init__(self) -> None:
        self.at_holes: dict | None = None

    def skipped(self, *args) -> None:
        pass

    def failed(self, *args) -> None:
        pass

    def repaired(self, *args) -> None:
        pass

    def holes(self, state) -> None:
        if self.at_holes is None:
            self.at_holes = dict(state.remaining)

    def finished(self, state) -> None:
        pass


def _small_left_after_growth(**options) -> int:
    """1 x 1 plates left when the hole pass starts after connected growth, summed over seeds: three 6 x 6 plate
    layers from 2 x 2 and 1 x 1 plates."""
    parts = part_tileset([CATALOG["plate2x2"], CATALOG["plate1x1"]], [RED], empty_weight=1e-9)
    mask = np.ones((3, 6, 6), dtype=bool)
    stock = {("plate2x2", "red"): 27, ("plate1x1", "red"): 36}
    left = 0
    for seed in range(10):
        builder = BottomUpBuilder(parts, any_offset=True, holes=True, hang=True, order="connected", **options)
        builder.trace = _FirstHoles()
        builder.build(mask.shape, np.random.default_rng(seed), stock, mask)
        left += builder.trace.at_holes[("plate1x1", "red")]
    return left


def test_small_part_options_act_on_connected_growth() -> None:
    """--reserve-small and --small-last apply to the growth (its main pass) as they do to the layer-by-layer one."""
    plain = _small_left_after_growth()
    assert _small_left_after_growth(small_reserve=True) > plain
    assert _small_left_after_growth(small_power=2.0) > plain


def test_connected_growth_with_reserve_still_builds_a_thin_post() -> None:
    """The seed and the growth up a 1 x 1 post use the small parts it needs: only they fit there."""
    parts = part_tileset([CATALOG["plate1x1"], CATALOG["plate2x2"], CATALOG["brick2x2"]], [RED], empty_weight=1e-9)
    stock = {("plate1x1", "red"): 8, ("plate2x2", "red"): 8, ("brick2x2", "red"): 4}
    mask = np.zeros((7, 4, 4), dtype=bool)
    mask[:6, 1, 1] = True  # the post
    mask[6] = True  # the top
    for seed in range(5):
        builder = BottomUpBuilder(parts, any_offset=True, order="connected", small_reserve=True)
        grid = builder.build(mask.shape, np.random.default_rng(seed), stock, mask)
        assert parts.solid[grid][:6, 1, 1].all() and parts.solid[grid][6].any(), seed
