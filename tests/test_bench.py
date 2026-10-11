"""M12c bench: the pair lists the completeness steps run on (experiments/complete.py: load_pairs, pair_order), the bench
file, and the run-time model."""

import json
from pathlib import Path

import pytest

from brickwfc.experiments.complete import (
    OBJECTS, PAIRS, STRUCTURES, SWEEP_SETS, load_pairs, pair_order, predicted_minutes, time_model,
)

ROOT = Path(__file__).resolve().parents[1]


def write(tmp_path, data) -> Path:
    path = tmp_path / "pairs.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_the_default_is_the_nine_sweep_pairs_objects_outer() -> None:
    assert load_pairs(None) == PAIRS and len(PAIRS) == 9
    assert PAIRS[:3] == (("6378-1", "chair"), ("5891-1", "chair"), ("4956-1", "chair"))
    assert PAIRS == tuple((s, o) for o in OBJECTS for s in SWEEP_SETS)


def test_sets_and_objects_or_explicit_pairs(tmp_path) -> None:
    product = load_pairs(write(tmp_path, {"sets": ["7796-1", "6378-1"], "objects": ["sofa", "chair"]}))
    assert product == (("7796-1", "sofa"), ("6378-1", "sofa"), ("7796-1", "chair"), ("6378-1", "chair"))
    listed = load_pairs(write(tmp_path, {"pairs": [["10182-1", "vessel"], ["6378-1", "bench"]], "description": "x"}))
    assert listed == (("10182-1", "vessel"), ("6378-1", "bench"))


@pytest.mark.parametrize("data", [
    {"pairs": []},
    {"pairs": [["6378-1", "lamp"]]},  # unknown object
    {"pairs": [["chair", "6378-1"]]},  # the wrong way round
    {"pairs": [["6378-1"]]},
    {"pairs": [["6378-1", "chair"], ["6378-1", "chair"]]},
    {"pairs": [["6378-1", "chair"]], "sets": ["5891-1"], "objects": ["car"]},
])
def test_bad_pair_files_are_refused(tmp_path, data) -> None:
    with pytest.raises(ValueError):
        load_pairs(write(tmp_path, data))


def test_the_bench_file_is_nine_sets_by_six_objects_and_holds_the_sweep() -> None:
    pairs = load_pairs(ROOT / "examples" / "m12c_bench.json")
    assert len(pairs) == 54 and len({s for s, _ in pairs}) == 9 and {o for _, o in pairs} == set(STRUCTURES)
    assert set(PAIRS) <= set(pairs)
    selected = json.loads((ROOT / "results" / "sets_selection.json").read_text(encoding="utf-8"))["selected"]
    assert {s for s, _ in pairs} <= set(selected)  # bench sets are building sets with learned style


def test_pair_order_is_the_order_cells_were_built_in() -> None:
    cells = [{"set": s, "object": o, "arm": a} for s, o in (("5891-1", "car"), ("6378-1", "chair")) for a in "xy"]
    assert pair_order(cells) == [("5891-1", "car"), ("6378-1", "chair")]


def test_time_model_fits_a_power_law() -> None:
    runs = [{"target_cells": c, "cpu_s_per_candidate": 0.01 * c ** 1.5, "parallel_overhead": 1.2} for c in (1000, 2000, 4000)]
    model = time_model(runs)
    assert model["b"] == pytest.approx(1.5) and model["a"] == pytest.approx(0.01) and model["parallel_overhead"] == 1.2
    assert predicted_minutes(model, 1000, candidates=50) == pytest.approx(50 * 0.01 * 1000 ** 1.5 / 5 * 1.2 / 60)


def test_bench_report_marks_a_cut_target() -> None:
    from brickwfc.experiments.complete import bench_report

    cell = {"arm": "creserve70", "object": "chair", "set": "6378-1", "slack": 0.7, "inventory_parts": 204,
            "grid": [42, 9, 10], "target_cells": 979, "object_cells": 967, "support_cells": 12, "left_out": {},
            "left_out_cells": 0, "rounds": 1, "thinnest_section": 1, "overhang_moment": 20.0, "pieces": 2}
    model = {"a": 1e-5, "b": 2.0, "runs": 3, "cells_range": [1000, 4000], "log_residual_sd": 0.1,
             "parallel_overhead": 1.0}
    line = bench_report([cell], model, 50).splitlines()[2]
    assert "| 20 | **2** |" in line
    assert "| 20 | — |" in bench_report([cell | {"pieces": None}], model, 50).splitlines()[2]  # older dry runs
