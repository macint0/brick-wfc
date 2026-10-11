"""M12c: hollow targets judged on the surface (experiments/complete.py arms and bar-aware reports) and the re-rank
driver's checks (experiments/select.py); synthetic rows only."""

import numpy as np

from brickwfc.experiments.complete import (
    ARMS, COMPARE, HOLLOW_ARMS, HOLLOW_COMPARE, arm_config, complete, compare_report, completeness, size_report, size_rows,
    size_rules, sweep_report,
)
from brickwfc.experiments.select import stored_rule, table


def test_hollow_arms_are_creserve_with_a_shell_at_the_solids_scale_and_the_surface_bar() -> None:
    assert set(HOLLOW_ARMS) <= set(ARMS)
    for hollow, base, slack, thickness in (("hollow1", "creserve", 1.0, 1), ("hollow2", "creserve", 1.0, 2),
                                           ("hollow1_80", "creserve80", 0.8, 1), ("hollow2_80", "creserve80", 0.8, 2)):
        assert ARMS[hollow][1] == ARMS[base][1] + ["--hollow", str(thickness), "--hollow-scale", "solid", "--bar",
                                                   "surface"]
        config = arm_config(hollow, "chair")
        assert (config.hollow, config.hollow_scale, config.bar, config.fill_slack, config.sizing) == (
            thickness, "solid", "surface", slack, "usable")
        assert (arm_config(base, "chair").hollow, arm_config(base, "chair").bar) == (0, "volume")
        assert (base, hollow) in HOLLOW_COMPARE and (base, hollow) in COMPARE
    assert len(set(COMPARE)) == len(COMPARE)


def test_completeness_rows_carry_the_largest_surface_hole() -> None:
    mask = np.ones((4, 5, 5), dtype=bool)
    filled = mask.copy()
    filled[1:3, 1:4, 1:4] = False  # an 18-cell cavity inside
    filled[3, 0, 0] = False  # a corner on top
    row = completeness(filled, mask)
    assert (row["largest_hole"], row["largest_surface_hole"]) == (18, 1)


def row(fill: float, hole: int, surface: float, surface_hole: int) -> dict:
    return {"fill_pct": fill, "largest_hole": hole, "surface_pct": surface, "largest_surface_hole": surface_hole}


def test_the_two_bars_on_rows() -> None:
    inside = row(90.0, 30, 98.5, 2)  # the missing cells are inside: complete only on the surface
    assert not complete(inside) and complete(inside, "surface")
    assert complete(row(97.0, 4, 98.0, 4)) and complete(row(97.0, 4, 98.0, 4), "surface")  # the thresholds count
    assert not complete(row(99.0, 3, 97.9, 0), "surface") and not complete(row(99.0, 3, 98.5, 5), "surface")


def cell(arm: str, volume: list[int], surface: list[int], selected: tuple[bool, bool]) -> dict:
    sel = row(98.5, 3, 98.4, 2) if selected[0] else row(90.0, 30, 98.4, 2) if selected[1] else row(90.0, 30, 91.0, 20)
    return {"arm": arm, "object": "chair", "set": "5891-1", "same_as": None, "target_cells": 2000,
            "object_cells": 1990, "valid": 45, "candidates": 50, "mean_fill_pct": 85.0, "mean_holes": 5.0,
            "mean_largest_hole": 40.0, "mean_surface_pct": 84.0, "mean_largest_surface_hole": 25.0,
            "mean_tips_pct": 70.0, "complete": len(volume), "complete_seeds": volume,
            "complete_surface": len(surface), "complete_surface_seeds": surface, "s_per_candidate": 12.5,
            "stalled": 0, "selected": sel | {"seed": 7, "holes": 3, "parts": 300, "utilization_pct": 80.0,
                                              "clutch": 200.0, "judge": -0.3, "tips_pct": 90.0,
                                              "complete": selected[0], "complete_surface": selected[1]}}


def test_sweep_report_counts_both_bars() -> None:
    line = sweep_report([cell("hollow1", [], [3, 9, 12], (False, True))]).splitlines()
    assert "complete (vol / surf) | selected complete (vol / surf) |" in line[0]
    assert "| 45/50 | 0 / 3 | no / yes | 90.0 / 85.0 |" in line[2] and "| 2 / 25 |" in line[2]


def test_compare_report_shows_both_bars() -> None:
    text = compare_report([cell("creserve", [], [], (False, False)), cell("hollow1", [], [3], (False, True))],
                          HOLLOW_COMPARE)
    line = text.splitlines()[2]
    assert "| connected + reserve-small -> connected + reserve-small, hollow 1 at the solid's scale, surface bar |" in line
    assert "| 0 / 0 -> 0 / 1 |" in line and "20 -> 2 +" in line  # the largest surface hole, smaller is better


def test_size_rules_per_bar() -> None:
    rows = size_rows([cell("creserve", [], [4], (False, True)), cell("creserve80", [1], [1, 2], (True, True))])
    rule = size_rules(rows)[0]
    assert (rule["any_complete"], rule["any_complete_surface"]) == (0.8, 1.0)
    assert (rule["selected_complete"], rule["selected_complete_surface"]) == (0.8, 1.0)
    assert rule["complete_surface_by_slack"] == {1.0: 1, 0.8: 2}
    assert "| chair | 5891-1 | creserve | 0.8 / 1.0 | 0.8 / 1.0 | 0 / 1 | 1 / 2 |" in size_report(rows).splitlines()


def test_select_checks_a_run_with_the_rule_it_was_selected_by() -> None:
    assert stored_rule({"fill_weight": 1.0}) == {"complete_first": False}  # a run from before complete-first
    assert stored_rule({"complete_first": True, "bar": "surface"}) == {"complete_first": True}
    assert stored_rule({"complete_first": False}) == {"complete_first": False}


def test_select_table_without_a_selection() -> None:
    selected = {"seed": 1, "judge": -0.35, "complete": True, "fill_pct": 98.7, "largest_hole": 4, "surface_pct": 98.3,
                "largest_surface_hole": 4, "unique": 34, "complete_unique": 1}
    cells = [{"arm": "creserve60", "object": "chair", "set": "5891-1", "old": None, "volume": None, "surface": None},
             {"arm": "creserve80", "object": "chair", "set": "5891-1", "old": selected, "volume": selected,
              "surface": selected}]
    lines = table(cells).splitlines()
    assert lines[2].startswith("| creserve60 | chair | 5891-1 | 0 | 0 / 0 | - | no selection |")
    assert "| 34 | 1 / 1 | 1 | 98.7 / 4 / 98.3 / 4 | -0.350 | yes |" in lines[3]


def test_target_hash_tells_targets_apart() -> None:
    from brickwfc.experiments.complete import target_hash

    box = np.ones((3, 4, 4), dtype=bool)
    other = box.copy()
    other[1, 1, 1] = False
    assert target_hash(box) == target_hash(box.copy()) != target_hash(other)
    assert target_hash(np.ones((4, 3, 4), dtype=bool)) != target_hash(box)  # same cells, another shape


def test_compare_report_says_whether_the_targets_are_the_same() -> None:
    base, hollowed = cell("creserve", [], [], (False, False)), cell("hollow1", [], [3], (False, True))
    assert "| base -> arm | same target |" in compare_report([base, hollowed], HOLLOW_COMPARE).splitlines()[0]
    assert " | - | " in compare_report([base, hollowed], HOLLOW_COMPARE).splitlines()[2]  # unknown
    base["target_hash"], hollowed["target_hash"] = "a", "b"
    assert "surface bar | no | " in compare_report([base, hollowed], HOLLOW_COMPARE).splitlines()[2]
    hollowed["target_hash"] = "a"
    assert "surface bar | yes | " in compare_report([base, hollowed], HOLLOW_COMPARE).splitlines()[2]


def test_hollow_sizing_report() -> None:
    from brickwfc.experiments.complete import hollow_sizing_report

    shell = {"thickness": 1, "cells": 600, "solid_cells": 1000, "kept_pct": 60.0, "exposed": 500, "enclosed": True,
             "budget_cells": 1000, "spare_cells": 400, "spare_pct": 40.0, "fit_nowhere": {"brick2x4": 2},
             "fit_nowhere_cells": 48}
    cells = [{"object": "car", "set": "6378-1", "slack": 1.0, "solid_cells": 1000, "solid_exposed": 500,
              "shells": [shell]}]
    assert hollow_sizing_report(cells).splitlines()[2] == (
        "| car | 6378-1 | 1.0 | 1000 | 500 | 1000 | 1 | 600 (60) | 500 | yes | 400 (40) | 48 (brick2x4 x2) |")
