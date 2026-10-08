"""M13: WFC builds finished vs time budget (tiny inputs only)."""

import shutil
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from brickwfc.experiments import budget_curve
from brickwfc.experiments.budget_curve import BuildRecord, curve_rows, draw_curve, finished_share, table, time_grid


def record(generator: str, seconds: float, finished: bool = True, seed: int = 0, set_number: str = "s") -> BuildRecord:
    return BuildRecord(set_number, generator, seed, finished, seconds, finished, 0.9, 10, 2, 1, 50, 1000)


def test_finished_share_counts_runs_done_by_t() -> None:
    runs = [record("WFC_B", 10), record("WFC_B", 100), record("WFC_B", 600, finished=False)]
    assert finished_share(runs, 5) == 0 and finished_share(runs, 30) == pytest.approx(1 / 3)
    assert finished_share(runs, 600) == pytest.approx(2 / 3) and finished_share([], 1) == 0


def test_time_grid_and_curve() -> None:
    grid = time_grid(600)
    assert grid[0] == pytest.approx(0.01) and grid[-1] == pytest.approx(600, rel=0.02) and (np.diff(grid) > 0).all()
    rows = curve_rows([record("WFC_B", 50), record("D2", 0.5)], 600)
    d2 = [p for g, t, p in rows if g == "D2"]
    assert d2[0] == 0 and d2[-1] == 100 and sorted(d2) == d2


def test_table_and_png(tmp_path: Path) -> None:
    runs = [record("WFC_B", 50, seed=0), record("WFC_B", 600, False, seed=1), record("D2", 0.1)]
    text = table(runs, ["s"], [30, 120], workers=3, wfc_workers=2)
    assert "3 worker processes in all, 2 for WFC" in text
    assert "| s | WFC_B | 2 | 0/2 | 1/2 | 50.00 | 100 | 2.0 | 50 |" in text and "| s | D2 | 1 | 1/1 | 1/1 |" in text
    draw_curve(curve_rows(runs, 120), [30, 120], tmp_path / "curve.png")
    assert Image.open(tmp_path / "curve.png").size == (720, 420)


def test_cli_runs_and_resumes(tiny_ldr: Path, tmp_path: Path) -> None:
    data = tmp_path / "omr"
    data.mkdir()
    shutil.copy(tiny_ldr, data / "tiny-1.mpd")
    args = ["--sets", "tiny-1", "--data", str(data), "--seeds", "2", "--budgets", "2", "10", "--height", "6",
            "--workers", "1", "--wfc-workers", "1", "--out", str(tmp_path / "out")]
    assert budget_curve.main(args) == 0
    records = budget_curve.load_records(tmp_path / "out" / "runs.jsonl")
    assert [(r.generator, r.seed) for r in records] == [("D2", 0), ("D2", 1), ("WFC_B", 0), ("WFC_B", 1)]
    assert all(r.valid for r in records if r.finished) and all(r.finished for r in records if r.generator == "D2")
    assert budget_curve.main(args) == 0  # resumed: nothing new
    assert len(budget_curve.load_records(tmp_path / "out" / "runs.jsonl")) == 4
    assert (tmp_path / "out" / "curve.png").exists() and (tmp_path / "out" / "curve.csv").read_text().startswith("generator")
