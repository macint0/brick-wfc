"""The size arms of the completeness sweep (experiments/complete.py): configs, rows, the largest complete slack."""

import math

from brickwfc.experiments.complete import (
    ARMS, COMPARE, SIZE_COMPARE, SIZE_FAMILIES, arm_config, compare_report, size_report, size_rows, size_rules,
)


def test_size_arms_are_creserve_and_the_default_at_each_slack() -> None:
    for (arm, slack), (control, control_slack) in zip(SIZE_FAMILIES["creserve"], SIZE_FAMILIES["usable"]):
        assert slack == control_slack
        assert (arm_config(arm, "car").sizing, arm_config(arm, "car").fill_slack) == ("usable", slack)
        assert (arm_config(control, "car").sizing, arm_config(control, "car").fill_slack) == ("usable", slack)
        flags = ARMS[arm][1]
        assert flags[flags.index("--order") + 1] == "connected" and "--reserve-small" in flags
        # creserve is the control with the two options added: the same target, the same seeds
        assert [f for f in flags if f not in ("--order", "connected", "--reserve-small")] == ARMS[control][1]


def test_size_compare_pairs_are_in_compare_once() -> None:
    assert all(pair in COMPARE for pair in SIZE_COMPARE)
    assert len(set(COMPARE)) == len(COMPARE)
    assert ("usable70", "creserve70") in SIZE_COMPARE and ("creserve70", "creserve60") in SIZE_COMPARE


def cell(arm: str, complete_seeds: list[int], selected_complete: bool, obj: str = "chair",
         set_number: str = "5891-1") -> dict:
    fill, hole, surface = (98.5, 3, 98.4) if selected_complete else (93.0, 20, 91.0)
    return {"arm": arm, "object": obj, "set": set_number, "target_cells": 2000, "valid": 45, "candidates": 50,
            "mean_fill_pct": 85.0, "mean_largest_hole": 40.0, "mean_surface_pct": 84.0,
            "mean_largest_surface_hole": 30.0, "complete": len(complete_seeds), "complete_seeds": complete_seeds,
            "complete_surface": len(complete_seeds), "complete_surface_seeds": complete_seeds, "s_per_candidate": 12.5,
            "stalled": 0,
            "selected": {"seed": 7, "fill_pct": fill, "holes": 3, "largest_hole": hole, "surface_pct": surface,
                         "largest_surface_hole": hole, "tips_pct": 90.0, "complete": selected_complete,
                         "complete_surface": selected_complete}}


def test_size_rows_follow_the_families_largest_slack_first() -> None:
    cells = [cell("creserve60", [1, 2], True), cell("creserve", [], False), cell("usable70", [], False),
             cell("creserve80", [5], False), cell("connected", [], False)]  # connected is no size arm
    rows = size_rows(cells)
    assert [(r["family"], r["slack"]) for r in rows] == [("creserve", 1.0), ("creserve", 0.8), ("creserve", 0.6),
                                                         ("usable", 0.7)]
    six = rows[2]
    assert six["arm"] == "creserve60" and six["complete"] == 2 and six["complete_seeds"] == [1, 2]
    assert six["selected_complete"] and six["selected_fill_pct"] == 98.5 and six["selected_largest_hole"] == 3
    assert not rows[1]["selected_complete"]  # one candidate complete, the selected build not


def test_selected_complete_is_the_bar_not_a_stored_flag() -> None:
    near = cell("creserve80", [], True)
    near["selected"]["largest_hole"] = 7  # a 7-cell hole misses the bar whatever the flag says
    assert not size_rows([near])[0]["selected_complete"]


def test_size_rules_take_the_largest_complete_slack() -> None:
    rows = size_rows([cell("creserve", [], False), cell("creserve90", [], False), cell("creserve80", [1], False),
                      cell("creserve70", [3, 4], True), cell("creserve60", [8], True),
                      cell("usable", [], False, set_number="4956-1"), cell("usable60", [], False, set_number="4956-1")])
    rules = {(r["set"], r["family"]): r for r in size_rules(rows)}
    chair = rules[("5891-1", "creserve")]
    assert chair["any_complete"] == 0.8 and chair["selected_complete"] == 0.7
    assert chair["complete_by_slack"] == {1.0: 0, 0.9: 0, 0.8: 1, 0.7: 2, 0.6: 1}
    other = rules[("4956-1", "usable")]
    assert other["any_complete"] is None and other["selected_complete"] is None and other["slacks"] == [1.0, 0.6]


def test_size_report_tables() -> None:
    rows = size_rows([cell("creserve80", [1], False), cell("creserve70", [3, 4], True)])
    lines = size_report(rows).splitlines()
    assert lines[0].startswith("| object | set | family | slack | target cells | valid |")
    assert lines[2] == ("| chair | 5891-1 | creserve | 0.8 | 2000 | 45/50 | 85.0 | 40 | 84.0 | 30 | 93.0 | 20 | 91.0 | "
                        "20 | no / no | 1 / 1 | 12.5 |")
    assert lines[3].startswith("| chair | 5891-1 | creserve | 0.7 |") and "| yes / yes | 2 / 2 | 12.5 |" in lines[3]
    assert "candidates meeting the volume bar (0.8 / 0.7) | candidates meeting the surface bar |" in lines[5]
    assert lines[7] == "| chair | 5891-1 | creserve | 0.8 / 0.8 | 0.7 / 0.7 | 1 / 2 | 1 / 2 |"
    # a pair with no complete candidate at any slack, and one missing a slack
    lines = size_report(size_rows([cell("usable", [], False), cell("creserve60", [], False, set_number="6378-1"),
                                   cell("creserve", [], False, set_number="6378-1")])).splitlines()
    assert "| chair | 6378-1 | creserve | none / none | none / none | 0 / 0 | 0 / 0 |" in lines  # slacks 1.0 / 0.6
    assert "| chair | 5891-1 | usable | none / none | none / none | 0 / - | 0 / - |" in lines


def test_size_report_without_a_selected_build() -> None:
    empty = cell("creserve60", [], False)
    del empty["selected"]
    empty["valid"], empty["mean_fill_pct"] = 0, math.nan
    row = size_rows([empty])[0]
    assert not row["selected_complete"] and row["selected_largest_hole"] is None
    assert "| 0/50 | nan |" in size_report([row])


def test_size_compare_joins_creserve_across_slacks() -> None:
    text = compare_report([cell("creserve80", [1], False), cell("creserve70", [3, 4], True)], SIZE_COMPARE)
    row = text.splitlines()[2]
    assert "connected + reserve-small, 0.8 -> connected + reserve-small, 0.7" in row
    assert "93.0 -> 98.5 +" in row and "20 -> 3 +" in row and "| 0 / 0 -> 1 / 1 |" in row
