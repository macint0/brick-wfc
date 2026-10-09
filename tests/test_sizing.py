"""M12b sizing: slopes count by what they can fill toward a target's volume."""

import numpy as np
import pytest

from brickwfc.bricks.inventory import fillable_cells, fits_inside, inventory_cells, part_cells, target_volume, unusable
from brickwfc.bricks.parts import CATALOG
from brickwfc.bricks.shapes import SECTION_BAND, scaled_to, thinnest_section


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



def test_keep_sections_keeps_thin_parts_thick() -> None:
    occupied = np.zeros((21, 12, 12), dtype=bool)  # a stool: a base, a 3 x 3 post, a seat; scaled down below
    occupied[:3] = True
    occupied[3:18, 4:7, 4:7] = True
    occupied[18:] = True
    thicker = 0
    for cells in range(300, 1000, 10):
        plain = scaled_to(occupied, cells)
        kept = scaled_to(occupied, cells, keep_sections=True)
        assert thinnest_section(kept) >= thinnest_section(plain)
        assert abs(int(kept.sum()) - cells) <= max(SECTION_BAND * cells, abs(int(plain.sum()) - cells))
        thicker += thinnest_section(kept) > thinnest_section(plain)
    assert thicker  # nearest-neighbour scaling thins the post at some volumes; the kept scale avoids it


def test_usable_parts_fit_somewhere_inside() -> None:
    lane = np.ones((1, 2, 5), dtype=bool)  # one plate layer, 2 x 5 studs
    assert fits_inside(CATALOG["plate2x4"], lane) and fits_inside(CATALOG["plate2x4"], lane.transpose(0, 2, 1))
    assert not fits_inside(CATALOG["plate2x6"], lane) and not fits_inside(CATALOG["brick1x2"], lane)  # too long, tall
    ell = np.zeros((3, 4, 4), dtype=bool)
    ell[:, :, 0] = ell[:, 0, :] = True  # two 1-wide walls meeting at a corner
    assert fits_inside(CATALOG["brick1x4"], ell) and not fits_inside(CATALOG["brick2x2"], ell)
    assert fits_inside(CATALOG["brick2x2_corner"], np.ones((3, 2, 2), dtype=bool))
    inventory = {("plate6x14", "red"): 2, ("plate6x14", "blue"): 1, ("plate1x1", "red"): 9}
    assert unusable(inventory, np.ones((4, 12, 13), dtype=bool)) == {"plate6x14": 3}
    assert unusable(inventory, np.ones((1, 14, 6), dtype=bool)) == {}
    assert target_volume(inventory, "usable") == target_volume(inventory)  # the parts are left out by the pipeline


def test_usable_sizing_leaves_out_parts_that_fit_nowhere_and_settles() -> None:
    from types import SimpleNamespace

    from brickwfc.alt.pipeline import AltConfig, sized_target
    from brickwfc.bricks.colors import colors_by_name

    source = SimpleNamespace(inventory={("plate6x14", "red"): 1, ("plate1x1", "red"): 60},
                             colors=tuple(colors_by_name(["red"])))
    full, info = sized_target(source, AltConfig(shape="pyramid"))
    assert info == {"volume": 84 + 60} and not fits_inside(CATALOG["plate6x14"], full.mask)
    usable, info = sized_target(source, AltConfig(shape="pyramid", sizing="usable"))
    assert info == {"volume": 60, "left_out": {"plate6x14": 1}, "left_out_cells": 84, "rounds": 2, "settled": True}
    assert usable.mask.sum() < full.mask.sum()
    smaller, _ = sized_target(source, AltConfig(shape="pyramid", sizing="usable", fill_slack=0.5))
    assert smaller.mask.sum() < usable.mask.sum()
    with pytest.raises(ValueError):
        sized_target(source, AltConfig(shape="pyramid", fill_slack=0))
