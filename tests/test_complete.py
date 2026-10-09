"""M12b completeness: metrics and the builder trace (causes of unfilled target cells)."""

import numpy as np

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import CATALOG, PLATES, part_tileset
from brickwfc.bricks.shapes import mushroom
from brickwfc.experiments.complete import CAUSES, Trace, completeness, complete


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
