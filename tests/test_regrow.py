"""M12c: connected growth that stalls is started again from the next ground region (BottomUpBuilder(regrow=True))."""

import numpy as np
import pytest

from brickwfc.alt.pipeline import main
from brickwfc.bricks.bottomup import REGROW_FILL, BottomUpBuilder
from brickwfc.bricks.parts import CATALOG, part_tileset
from conftest import BLUE, RED
from test_holes import NAMES, check, inventory, table


@pytest.fixture(scope="module")
def parts():
    return part_tileset([CATALOG[n] for n in NAMES], [RED, BLUE], empty_weight=0.05)


def table_and_pillar() -> np.ndarray:
    """``table()`` (2 x 2 legs) with a separate 3 x 3 pillar beside it: the pillar is the largest ground region, so
    the growth seeds there, and nothing joins it to the table."""
    mask = np.zeros((9, 10, 14), dtype=bool)
    mask[:, :, :10] = table()
    mask[:2, :3, 11:14] = True
    return mask


def builder(parts, regrow: bool) -> BottomUpBuilder:
    return BottomUpBuilder(parts, any_offset=True, balanced=True, bridge=True, open_tops=True, order="connected",
                           holes=True, hang=True, regrow=regrow)


def cover(grid: np.ndarray, parts, mask: np.ndarray) -> float:
    return float(parts.solid[grid][mask].mean())


def test_a_stalled_growth_is_grown_again_from_the_next_region(parts) -> None:
    mask, stock = table_and_pillar(), inventory(12)
    for seed in range(3):
        plain = builder(parts, False).build(mask.shape, np.random.default_rng(seed), stock, mask)
        assert cover(plain, parts, mask) < REGROW_FILL  # the seed is on the pillar: the table is never reached
        assert not parts.solid[plain][:, :, :10].any()
        grid = builder(parts, True).build(mask.shape, np.random.default_rng(seed), stock, mask)
        check(grid, parts, mask, stock, hanging=True)
        assert cover(grid, parts, mask) > REGROW_FILL and parts.solid[grid][:, :, :10].any()  # grown from a leg


def test_a_growth_that_does_not_stall_is_unchanged(parts) -> None:
    mask, stock = table(), inventory(12)
    for seed in range(3):
        plain = builder(parts, False).build(mask.shape, np.random.default_rng(seed), stock, mask)
        assert cover(plain, parts, mask) >= REGROW_FILL
        assert (builder(parts, True).build(mask.shape, np.random.default_rng(seed), stock, mask) == plain).all()


def test_regrow_is_deterministic(parts) -> None:
    mask, stock = table_and_pillar(), inventory(12)
    a = builder(parts, True).build(mask.shape, np.random.default_rng(5), stock, mask)
    b = builder(parts, True).build(mask.shape, np.random.default_rng(5), stock, mask)
    assert (a == b).all()


def test_regrow_goes_with_the_connected_order() -> None:
    with pytest.raises(SystemExit):
        main(["6372-1", "--regrow"])


def test_regrow_arms_are_creserve_with_the_flag() -> None:
    from brickwfc.experiments.complete import ARMS, COMPARE, REGROW_COMPARE, arm_config

    for base, arm in REGROW_COMPARE:
        assert ARMS[arm][1] == ARMS[base][1] + ["--regrow"] and (base, arm) in COMPARE
        assert arm_config(arm, "chair").fill_slack == arm_config(base, "chair").fill_slack
