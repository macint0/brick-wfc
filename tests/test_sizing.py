"""M12b sizing: slopes count by what they can fill toward a target's volume."""

import numpy as np
import pytest

from brickwfc.bricks.inventory import fillable_cells, inventory_cells, part_cells, target_volume
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
