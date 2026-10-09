"""M12b sizing: slopes count by what they can fill; thin target columns get parts set aside or are visited first."""

import numpy as np
import pytest

from brickwfc.bricks.bottomup import BottomUpBuilder, sections
from brickwfc.bricks.inventory import fillable_cells, inventory_cells, part_cells, target_volume
from brickwfc.bricks.parts import CATALOG, extract_parts, part_tileset
from conftest import RED

NAMES = ("plate1x1", "plate2x2", "brick1x1", "brick1x8", "tile1x1", "slope45_2x2")


@pytest.fixture(scope="module")
def parts():
    return part_tileset([CATALOG[n] for n in NAMES], [RED], empty_weight=0.1)


def test_fillable_cells() -> None:
    assert fillable_cells(CATALOG["slope45_2x4"]) == 4  # its back row of studs, one layer
    assert fillable_cells(CATALOG["slope45inv_2x2"]) == 4  # studs on every cell
    assert fillable_cells(CATALOG["slope45double_2x2"]) == 0  # a ridge: no stud
    for name in ("brick2x4", "plate1x2", "tile1x1", "brick2x2_corner"):
        assert fillable_cells(CATALOG[name]) == part_cells(CATALOG[name])
    inventory = {("slope45_2x4", "red"): 3, ("brick2x2", "red"): 2}
    assert target_volume(inventory, "box") == inventory_cells(inventory) == 3 * 24 + 2 * 12
    assert target_volume(inventory) == 3 * 4 + 2 * 12
    with pytest.raises(ValueError):
        target_volume(inventory, "studs")


def table(height: int = 8) -> np.ndarray:
    """A 6 x 6 base, two layers, under a 1 x 1 post."""
    mask = np.zeros((height, 6, 6), dtype=bool)
    mask[:2] = True
    mask[2:, 2, 2] = True
    return mask


def test_sections() -> None:
    mask = table()
    mask[0, 5, :] = False
    mask[0, 4, :] = False  # a gap row: layer 0 splits into a 4 x 6 region and nothing else
    got = sections(mask)
    assert got[0, 0, 0] == 24 and got[1, 0, 0] == 36 and got[3, 2, 2] == 1
    assert got[0, 5, 0] == 0 and (got[2:][~mask[2:]] == 0).all()


def test_reserve_only_fitting_studded_parts(parts) -> None:
    builder = BottomUpBuilder(parts, any_offset=True, thin=1)
    mask = table()
    thin = (sections(mask) > 0) & (sections(mask) <= 1)
    inventory = {("plate1x1", "red"): 20, ("brick1x1", "red"): 4, ("brick1x8", "red"): 9, ("tile1x1", "red"): 9,
                 ("slope45_2x2", "red"): 9, ("plate2x2", "red"): 9}
    reserved = builder._reserve(thin, inventory)
    assert set(reserved) == {("plate1x1", "red"), ("brick1x1", "red")}  # no tile, slope or part too wide
    # 6 thin cells, 32 cells of fitting parts: 6/32 of each count, rounded up.
    assert reserved == {("plate1x1", "red"): 4, ("brick1x1", "red"): 1}


def test_reserve_keeps_parts_for_the_post(parts) -> None:
    mask = table(height=10)
    inventory = {("plate1x1", "red"): 40, ("plate2x2", "red"): 6}  # 64 cells: the base (72) can use up every 1 x 1
    post = {}
    for thin in (0, 1):
        builder = BottomUpBuilder(parts, any_offset=True, thin=thin)
        heights = []
        for seed in range(10):
            grid = builder.build(mask.shape, np.random.default_rng(seed), inventory=inventory, allowed=mask)
            placed, errors = extract_parts(grid, parts)
            assert not errors and all(mask[c] for p in placed for c in p.cells())
            used = {}
            for p in placed:
                used[(p.shape.part.name, p.color.name)] = used.get((p.shape.part.name, p.color.name), 0) + 1
            assert all(used[k] <= inventory[k] for k in used)
            filled = np.zeros(mask.shape, dtype=bool)
            for p in placed:
                for c in p.cells():
                    filled[c] = True
            heights.append(int(filled[2:, 2, 2].sum()))
        post[thin] = heights
    assert sum(post[1]) > sum(post[0])


def test_thin_order_visits_small_sections_first(parts) -> None:
    mask = table()
    for seed in range(5):
        a = BottomUpBuilder(parts, any_offset=True, order="thin").build(mask.shape, np.random.default_rng(seed),
                                                                          allowed=mask)
        assert not extract_parts(a, parts)[1]
    with pytest.raises(ValueError):
        BottomUpBuilder(parts, order="spiral")
