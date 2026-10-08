"""M13: paper tables collected from summary files (synthetic files, plus a smoke run on the real ones)."""

import json
import math
from pathlib import Path

import pytest

from brickwfc.experiments import paper_tables
from brickwfc.experiments.paper_tables import (SOURCES, TIME_PER_ACCEPTED, UTILIZATION, Cell, evaluate, load, mean_of,
                                              render, show)

ROOT = Path(__file__).resolve().parents[1]


def write(root: Path, rel: str, data) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if rel.endswith(".jsonl"):
        path.write_text("".join(json.dumps(r) + "\n" for r in data), encoding="utf-8")
    else:
        path.write_text(json.dumps(data), encoding="utf-8")


M9B = [
    {"set": "a", "condition": "B_inventory", "status": "ok", "seeds": 10, "finished": 2, "timed_out": 8, "valid_pct": 20.0,
     "utilization_pct": 90.0, "physics_any_clutch_pct": 10.0, "time_per_run_s": 25.0},
    {"set": "b", "condition": "B_inventory", "status": "ok", "seeds": 10, "finished": 0, "timed_out": 10, "valid_pct": 0.0,
     "utilization_pct": 0.0, "physics_any_clutch_pct": 0.0, "time_per_run_s": 30.0},
    {"set": "c", "condition": "B_inventory", "status": "not run (memory: 2442 MB)", "seeds": 10},
    {"set": "a", "condition": "D_bottom_up", "status": "ok", "seeds": 10, "finished": 10, "timed_out": 0, "valid_pct": 100.0,
     "utilization_pct": 99.0, "physics_any_clutch_pct": 60.0, "time_per_run_s": 0.1},
]


def test_cells_aggregate_and_tag(tmp_path: Path) -> None:
    write(tmp_path, SOURCES["m9b"].paths[0], M9B)
    data = {"m9b": load(SOURCES["m9b"], tmp_path), "m10": None}
    b = {"condition": "B_inventory"}
    assert show(evaluate(Cell("m9b", b, mean_of("valid_pct")), data)) == "10.0 [m9b]"  # the not-run row is left out
    # Utilization is a mean over finished builds: the set where nothing finished does not count as 0.
    assert evaluate(Cell("m9b", b, UTILIZATION["m9b"]), data).text == "90.0"
    # 200 s of attempts for 2 valid builds.
    assert evaluate(Cell("m9b", b, TIME_PER_ACCEPTED["m9b"], "{:.0f}"), data).text == "275"
    assert evaluate(Cell("m9b", b, paper_tables.TIMEOUT_PCT["m9b"], "{:.0f}"), data).text == "90"
    assert show(evaluate(Cell("m10", {}, mean_of("valid_pct")), data)) == "pending [m10]"
    assert show(evaluate(None, data)) == "—"
    assert evaluate(Cell("m9b", {"condition": "nope"}, mean_of("valid_pct")), data).text == "—"


def test_loaders(tmp_path: Path) -> None:
    write(tmp_path, SOURCES["brickgpt"].paths[1], {"objects": [{"clutch": 3.0, "clusters": 1}, {"clutch": math.inf, "clusters": 2}],
                                                   "ours": []})
    rows = load(SOURCES["brickgpt"], tmp_path)
    assert [r["stands"] for r in rows] == [True, False]
    write(tmp_path, SOURCES["proposal"].paths[1], [{"condition": "proposal_raster", "valid": True, "utilization": 0.9,
                                                    "wall_time_s": 2.0, "matched_judge": -0.3}])
    rows = load(SOURCES["proposal"], tmp_path)
    assert evaluate(Cell("proposal", {}, mean_of("utilization", 100)), {"proposal": rows}).text == "90.0"
    assert load(SOURCES["m6"], tmp_path) is None


def test_render_marks_missing_sources_pending(tmp_path: Path) -> None:
    write(tmp_path, SOURCES["m9b"].paths[0], M9B)
    text = render({tag: load(source, tmp_path) for tag, source in SOURCES.items()})
    assert "## Main table" in text and "## Ablation" in text
    row = next(line for line in text.splitlines() if line.startswith("| WFC + constraints (B)"))
    assert "10.0 [m9b]" in row and "pending [m7]" in row and "pending [diversity]" in row
    assert "| m9b | `results/m9b_inventory_catalog_summary.json` | found |" in text
    assert "| m6 | `results/m6_stability_summary.json` | pending |" in text


def test_real_results_render(tmp_path: Path) -> None:
    out = tmp_path / "tables.md"
    assert paper_tables.main(["--root", str(ROOT), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert text.count("\n| ") > 20 and "nan" not in text.lower() and "inf" not in text.replace("info", "")
