"""The connected-order arms of the completeness sweep (experiments/complete.py): configs, tip cells, report."""

import numpy as np
import pytest

from brickwfc.experiments.complete import (
    ARMS, arm_config, compare_report, main, sweep_report, tip_cells, tips_filled_pct, top_layer,
)
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


def test_command_line_parses(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_:
        main(["--help"])
    assert exit_.value.code == 0 and "--arms" in capsys.readouterr().out


def test_connected_small_part_arms_match_their_random_order_twins() -> None:
    for arm, twin in (("creserve", "reserve"), ("csmall1", "small1"), ("csmall2", "small2"),
                      ("creserve80", "reserve80"), ("csmall1_80", "small1_80"), ("csmall2_80", "small2_80")):
        flags = ARMS[arm][1]
        assert flags[flags.index("--order") + 1] == "connected"
        assert [f for f in flags if f not in ("--order", "connected")] == ARMS[twin][1]  # the same options otherwise


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
    assert "tips filled % (sel / mean) | clutch (sel) | stalled (top layers) |" in lines[0]
    assert lines[2].endswith("| 75 / 70 | 120 | 2 |") and "connected + usable 0.8 + hang" in lines[2]


def test_sweep_report_lists_the_stalled_seeds_top_layers() -> None:
    cell = {"arm": "connected", "set": "5891-1", "object": "chair", "same_as": None, "target_cells": 1000,
            "object_cells": 990, "valid": 50, "candidates": 50, "complete": 0, "mean_fill_pct": 80.0, "mean_holes": 5.0,
            "mean_largest_hole": 10.0, "mean_surface_pct": 90.0, "s_per_candidate": 4.0, "mean_tips_pct": 70.0,
            "stalled": 7, "stall_tops": [[9, 6], [11, 1]]}
    assert sweep_report([cell]).splitlines()[2].endswith("| 7 (9: 6, 11) |")


def test_top_layer_is_the_highest_cell_of_any_part() -> None:
    from brickwfc.bricks.parts import CATALOG, PlacedPart, Shape
    from conftest import RED

    brick = PlacedPart(Shape(CATALOG["brick2x4"]), RED, 2, 0, 0)  # a brick is 3 layers
    plate = PlacedPart(Shape(CATALOG["plate2x4"]), RED, 1, 0, 0)
    assert top_layer([plate]) == 1 and top_layer([plate, brick]) == 4 and top_layer([]) == -1


def test_compare_report_marks_each_difference_by_its_direction() -> None:
    def cell(arm: str, fill: float, holes: int, largest: int, valid: int, seconds: float) -> dict:
        return {"arm": arm, "set": "6378-1", "object": "table", "valid": valid, "s_per_candidate": seconds,
                "stalled": 0, "selected": {"fill_pct": fill, "holes": holes, "largest_hole": largest,
                                           "surface_pct": 90.0, "tips_pct": 50.0, "complete": False}}

    text = compare_report([cell("usable", 80.0, 10, 30, 50, 5.0), cell("connected", 85.0, 12, 30, 49, 4.0)])
    row = text.splitlines()[2]
    assert "| usable + hang -> connected + usable + hang |" in row  # the arms' titles
    assert "80.0 -> 85.0 +" in row and "10 -> 12 -" in row and "30 -> 30 =" in row and "50 -> 49 -" in row
    assert "5.0 -> 4.0 +" in row and row.endswith("| 2 / 2 |")
    assert compare_report([cell("usable", 80.0, 10, 30, 50, 5.0)]) == ""  # no pair: no table
