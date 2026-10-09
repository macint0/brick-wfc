"""The connected-order arms of the completeness sweep (experiments/complete.py): configs, tip cells, report."""

import numpy as np

from brickwfc.experiments.complete import ARMS, arm_config, sweep_report, tip_cells, tips_filled_pct
from test_holes import table


def test_connected_arms_use_the_usable_targets_with_holes_and_hang() -> None:
    for arm, slack in (("connected", 1.0), ("connected90", 0.9), ("connected80", 0.8)):
        flags = ARMS[arm][1]
        assert {"--holes", "--hang"} <= set(flags) and flags[flags.index("--order") + 1] == "connected"
        config = arm_config(arm, "chair")
        assert (config.sizing, config.fill_slack) == ("usable", slack)
        # The same target as the usable arm of that slack, so the two join pair by pair.
        usable = arm_config({1.0: "usable", 0.9: "usable90", 0.8: "usable80"}[slack], "chair")
        assert (usable.sizing, usable.fill_slack) == (config.sizing, config.fill_slack)


def test_tip_cells_are_the_far_ends_of_the_low_structure() -> None:
    mask = table()  # four 2 x 2 legs, 6 tall, under a 10 x 10 top 3 thick; 9 layers, so the lowest 3 count
    tips = tip_cells(mask)
    legs = np.zeros_like(mask)
    for z in (0, 8):
        for x in (0, 8):
            legs[:3, z : z + 2, x : x + 2] = True
    assert (tips == legs).all()  # every leg cell of the lowest 3 layers: all are equally far from the centre
    filled = np.zeros_like(mask)
    filled[:3, 0:2, 0:2] = True  # one leg's foot
    assert tips_filled_pct(filled, tips) == 100 * (filled & tips).sum() / tips.sum()


def test_sweep_report_has_the_connected_columns() -> None:
    cell = {"arm": "connected80", "set": "6378-1", "object": "chair", "same_as": None, "target_cells": 1000,
            "object_cells": 990, "valid": 50, "candidates": 50, "complete": 3, "mean_fill_pct": 80.0, "mean_holes": 5.0,
            "mean_largest_hole": 10.0, "mean_surface_pct": 90.0, "s_per_candidate": 4.0, "mean_tips_pct": 70.0,
            "stalled": 2, "selected": {"fill_pct": 85.0, "holes": 4, "largest_hole": 8, "surface_pct": 93.0,
                                       "parts": 200, "utilization_pct": 90.0, "clutch": 120.0, "tips_pct": 75.0}}
    lines = sweep_report([cell]).splitlines()
    assert "tips filled % (sel / mean) | clutch (sel) | stalled |" in lines[0]
    assert lines[2].endswith("| 75 / 70 | 120 | 2 |") and "connected + usable 0.8 + hang" in lines[2]
