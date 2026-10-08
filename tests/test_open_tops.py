"""M12b: the builder's per-layer fit maps agree with _fits; open tops keep studless tops off target cells."""

import numpy as np
import pytest

from brickwfc.bricks.bottomup import BottomUpBuilder, _FitMap
from brickwfc.bricks.parts import CATALOG, PlacedPart, Shape, extract_parts, part_tileset, shapes_of
from conftest import BLUE, RED

NAMES = ("plate1x1", "plate1x2", "plate2x2", "brick1x2", "brick2x2", "tile1x1", "tile1x2", "tile2x2")


@pytest.fixture(scope="module")
def parts():
    return part_tileset([CATALOG[n] for n in NAMES], [RED, BLUE], empty_weight=0.1)


@pytest.mark.parametrize("open_tops", [False, True])
def test_fit_map_agrees_with_fits(parts, open_tops: bool) -> None:
    builder = BottomUpBuilder(parts, any_offset=True, open_tops=open_tops)
    rng = np.random.default_rng(3)
    shape = (7, 6, 7)
    for trial in range(20):
        filled = rng.random(shape) < 0.3
        studs = filled & (rng.random(shape) < 0.7)
        allowed = rng.random(shape) < 0.85
        y = int(rng.integers(0, shape[0]))
        fit_map = _FitMap(filled, studs, allowed, y, builder._studless_top if open_tops else None)
        for part_shape in shapes_of([CATALOG[n] for n in NAMES]):
            valid = fit_map.corners(part_shape)
            for z in range(-1, shape[1]):
                for x in range(-1, shape[2]):
                    part = PlacedPart(part_shape, RED, y, x, z)
                    studless = builder._studless_top(part_shape) if open_tops else None
                    expected = BottomUpBuilder._fits(part, filled, studs, allowed, studless)
                    got = 0 <= z < valid.shape[0] and 0 <= x < valid.shape[1] and bool(valid[z, x])
                    assert got == expected, (trial, part_shape.name, y, z, x)


def test_studless_top_cells(parts) -> None:
    builder = BottomUpBuilder(parts)
    assert builder._studless_top(Shape(CATALOG["tile1x2"], False)).all()
    assert not builder._studless_top(Shape(CATALOG["brick2x2"], False)).any()
    assert builder._studless_top(Shape(CATALOG["tile1x2"], True)).shape == (2, 1)


def test_open_tops_keep_tiles_off_thin_columns(parts) -> None:
    allowed = np.zeros((12, 6, 6), dtype=bool)
    allowed[:3] = True  # a base
    allowed[3:, 2:4, 2:4] = True  # a 2 x 2 column on it
    reached = {}
    for open_tops in (False, True):
        builder = BottomUpBuilder(parts, any_offset=True, open_tops=open_tops)
        tops = []
        for seed in range(12):
            grid = builder.build(allowed.shape, np.random.default_rng(seed), allowed=allowed)
            placed, errors = extract_parts(grid, parts)
            assert not errors and all(allowed[c] for p in placed for c in p.cells())
            if open_tops:  # no studless top cell under a target cell
                for p in placed:
                    if not p.shape.part.studs:
                        for y, z, x in p.top_cells():
                            assert y + 1 == allowed.shape[0] or not allowed[y + 1, z, x]
            tops.append(max(p.top for p in placed))
        reached[open_tops] = sum(top == allowed.shape[0] - 1 for top in tops)
    assert reached[True] >= reached[False] and reached[True] >= 9
