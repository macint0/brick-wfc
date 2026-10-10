"""M12b completeness: metrics and the builder trace (causes of unfilled target cells)."""

import numpy as np
import pytest

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import CATALOG, PLATES, part_tileset
from brickwfc.bricks.shapes import mushroom
from brickwfc.experiments.complete import (CAUSES, FINAL_CAUSES, Trace, completeness, complete, final_causes,
                                           holes_of)


def test_completeness_metrics() -> None:
    mask = np.zeros((3, 4, 4), dtype=bool)
    mask[:, 1:3, 1:3] = True  # 12 cells, all on the surface
    filled = mask.copy()
    filled[0, 1, 1] = filled[2, 2, 2] = filled[2, 2, 1] = False
    row = completeness(filled, mask)
    assert row["holes"] == 2 and row["largest_hole"] == 2 and row["unfilled"] == 3
    assert row["fill_pct"] == 100 * 9 / 12 and row["surface_pct"] == 100 * 9 / 12
    assert row["unfilled_on_surface_pct"] == 100
    assert complete(completeness(mask, mask)) and not complete(row)


def test_trace_keeps_builds_and_gives_every_unfilled_cell_a_cause() -> None:
    parts = part_tileset(list(PLATES.values()) + [CATALOG["brick2x4"], CATALOG["tile2x2"]],
                         colors_by_name(["red", "blue"]), empty_weight=0.3)
    inventory = {("plate2x4", "red"): 6, ("plate1x2", "blue"): 10, ("brick2x4", "red"): 3, ("plate1x1", "red"): 6,
                 ("tile2x2", "blue"): 4}
    mask = mushroom(6, 8, 8)
    seen = set()
    for seed in range(8):
        builder = BottomUpBuilder(parts, any_offset=True, balanced=True, bridge=True, connect=True, connect_rounds=4,
                                  open_tops=True)
        plain = builder.build(mask.shape, np.random.default_rng(seed), inventory, mask)
        filled = parts.solid[plain]
        trace = Trace(mask & ~filled)
        builder.trace = trace
        traced = builder.build(mask.shape, np.random.default_rng(seed), inventory, mask)
        assert np.array_equal(plain, traced)
        cause, _ = trace.causes(filled)
        assert np.array_equal(cause >= 0, mask & ~filled)
        found = {CAUSES[i] for i in np.unique(cause[cause >= 0])}
        assert not found & {"unvisited", "missed"}
        seen |= found
    assert {"inventory", "support", "skipped"} <= seen


@pytest.mark.parametrize("holes", [False, True])
def test_failed_tile_does_not_block_plate_of_same_box(holes: bool) -> None:
    """Under open tops a 1 x 1 tile may not sit under a target cell, a 1 x 1 plate may: the tile failing there must
    not make the builder skip the plate (both have box 1 x 1 x 1). The main pass is checked with every cell visited,
    the hole pass with (almost) none visited by the main pass."""
    parts = part_tileset([CATALOG["plate1x1"], CATALOG["tile1x1"]], colors_by_name(["red"]),
                         empty_weight=1e6 if holes else 1e-9)
    inventory = {("plate1x1", "red"): 1, ("tile1x1", "red"): 1}
    mask = np.ones((2, 1, 1), dtype=bool)  # a 2-cell column: the bottom cell has a target cell above it
    builder = BottomUpBuilder(parts, any_offset=True, open_tops=True, holes=holes)
    for seed in range(20):
        grid = builder.build(mask.shape, np.random.default_rng(seed), inventory, mask)
        assert parts.solid[grid].all(), seed  # plate below, tile on top


def test_final_causes_after_the_hole_pass() -> None:
    """With the hole pass and hanging support, the trace's final state is the build's, every unfilled target cell
    gets a cause, and none is a cell where a part still fits (the pass ends when nothing fits)."""
    parts = part_tileset(list(PLATES.values()) + [CATALOG["brick2x4"], CATALOG["tile2x2"]],
                         colors_by_name(["red", "blue"]), empty_weight=0.3)
    inventory = {("plate2x4", "red"): 6, ("plate1x2", "blue"): 10, ("brick2x4", "red"): 3, ("plate1x1", "red"): 6,
                 ("tile2x2", "blue"): 4}
    mask = mushroom(6, 8, 8)
    seen = set()
    for seed in range(4):
        builder = BottomUpBuilder(parts, any_offset=True, balanced=True, bridge=True, connect=True, connect_rounds=4,
                                  open_tops=True, holes=True, hang=True)
        plain = builder.build(mask.shape, np.random.default_rng(seed), inventory, mask)
        filled = parts.solid[plain]
        trace = Trace(mask & ~filled)
        builder.trace = trace
        assert np.array_equal(plain, builder.build(mask.shape, np.random.default_rng(seed), inventory, mask))
        assert np.array_equal(trace.final.filled, filled) and trace.at_holes is not None
        cause, wanted = final_causes(builder, trace, mask)
        assert np.array_equal(cause >= 0, mask & ~filled)
        found = {FINAL_CAUSES[i] for i in np.unique(cause[cause >= 0])}
        assert "missed" not in found
        seen |= found
        assert set(wanted) == {tuple(c) for c in np.argwhere(cause == FINAL_CAUSES.index("inventory")).tolist()}
        assert all(names for names in wanted.values())  # an inventory cell names the used-up parts that fit
        bins, small = holes_of(filled, mask, cause, trace.at_holes, trace.final.remaining, wanted)
        assert sum(b["cells"] for b in bins) == int((mask & ~filled).sum())
        for hole in small:
            assert hole["size"] <= 4 and len(hole["causes"]) == hole["size"]
            assert not hole["fitting"] or "plate1x1" in hole["fitting"]  # a plate 1 x 1 fits any free cell
    assert seen


class _HoleStart:
    """A builder trace that records the inventory left when each hole pass starts (the last one wins)."""

    def __init__(self) -> None:
        self.at_holes: dict | None = None

    def skipped(self, *args) -> None:
        pass

    def failed(self, *args) -> None:
        pass

    def repaired(self, *args) -> None:
        pass

    def holes(self, state) -> None:
        self.at_holes = dict(state.remaining)

    def finished(self, *args) -> None:
        pass


def _small_left(**options) -> int:
    """Small parts left when the hole pass starts, summed over seeds: a 6 x 6 plate layer from 2 x 2 and 1 x 1 plates."""
    parts = part_tileset([CATALOG["plate2x2"], CATALOG["plate1x1"]], colors_by_name(["red"]), empty_weight=1e-9)
    inventory = {("plate2x2", "red"): 9, ("plate1x1", "red"): 12}
    mask = np.ones((1, 6, 6), dtype=bool)
    left = 0
    for seed in range(10):
        builder = BottomUpBuilder(parts, any_offset=True, holes=True, **options)
        builder.trace = _HoleStart()
        builder.build(mask.shape, np.random.default_rng(seed), inventory, mask)
        left += builder.trace.at_holes[("plate1x1", "red")]
    return left


def test_small_parts_kept_for_the_hole_pass() -> None:
    """--reserve-small and --small-last keep more 1 x 1 plates for the hole pass than the plain main pass does."""
    plain = _small_left()
    assert _small_left(small_reserve=True) > plain
    assert _small_left(small_power=2.0) > plain


def test_reserve_small_still_builds_a_thin_post() -> None:
    """A cell only a small part fits (a 1 x 1 post under a 4 x 4 top) still gets one in the main pass: without it the
    top has nothing to rest on (no hole pass here)."""
    parts = part_tileset([CATALOG["plate1x1"], CATALOG["plate2x2"], CATALOG["brick2x2"]], colors_by_name(["red"]),
                         empty_weight=1e-9)
    inventory = {("plate1x1", "red"): 8, ("plate2x2", "red"): 8, ("brick2x2", "red"): 4}
    mask = np.zeros((7, 4, 4), dtype=bool)
    mask[:6, 1, 1] = True  # the post
    mask[6] = True  # the top
    for seed in range(5):
        builder = BottomUpBuilder(parts, any_offset=True, small_reserve=True)
        grid = builder.build(mask.shape, np.random.default_rng(seed), inventory, mask)
        assert parts.solid[grid][:6, 1, 1].all() and parts.solid[grid][6].any(), seed


def test_small_weights() -> None:
    parts = part_tileset([CATALOG["plate1x1"], CATALOG["plate1x3"], CATALOG["plate2x2"]], colors_by_name(["red"]))
    builder = BottomUpBuilder(parts, any_offset=True, small_power=2.0)
    factor = {shape.part.name: w for (shape, _), w in zip(builder.choices, builder.small_weights)}
    assert factor == pytest.approx({"plate1x1": 1 / 16, "plate1x3": 9 / 16, "plate2x2": 1.0})
    with pytest.raises(ValueError):
        BottomUpBuilder(parts, any_offset=True, small_reserve=True, small_power=1.0)
