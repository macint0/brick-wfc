"""The M12e training pool driver: measurement, re-releases vs alternates, thresholds, cache, CLI."""
import json
from pathlib import Path

import pytest

from brickwfc.experiments import omr_pool
from brickwfc.experiments.omr_pool import Measure, Thresholds, main, measure, model_rows, reason, select


def _model(bricks: int, unknown: int, color: int = 4) -> str:
    lines = ["0 FILE main.ldr"]
    lines += [f"1 {color} 0 {-24 * (k + 1)} 0 1 0 0 0 1 0 0 0 1 3001.dat" for k in range(bricks)]
    lines += [f"1 {color} 0 {-24 * (bricks + k + 1)} 0 1 0 0 0 1 0 0 0 1 999999.dat" for k in range(unknown)]
    return "\n".join(lines + ["0 NOFILE"]) + "\n"


INDEX = [
    {"id": 1, "number": "1-1", "name": "House", "theme": "Town", "year": 1980, "models_count": 2,
     "models": [{"name": "Main Model", "author": "a", "file": "1-1.mpd"}, {"name": "B", "author": "a", "file": "1-1_B.mpd"}]},
    {"id": 2, "number": "2-1", "name": "House again", "theme": "Town", "year": 1990, "models_count": 1,
     "models": [{"name": "Main Model", "author": "a", "file": "2-1.mpd"}]},
    {"id": 3, "number": "3-1", "name": "Robot", "theme": "Technic", "year": 1985, "models_count": 1,
     "models": [{"name": "Main Model", "author": "a", "file": "3-1.mpd"}]},
    {"id": 4, "number": "4-1", "name": "Tiny", "theme": "Town", "year": None, "models_count": 1,
     "models": [{"name": "Main Model", "author": "a", "file": "4-1.mpd"}]},
]
FILES = {"1-1.mpd": _model(3, 1), "1-1_B.mpd": _model(3, 1), "2-1.mpd": _model(3, 1), "3-1.mpd": _model(1, 3),
         "4-1.mpd": _model(1, 0, color=1)}


def _data(tmp_path: Path) -> Path:
    data = tmp_path / "omr"
    data.mkdir()
    (data / "index.json").write_text(json.dumps(INDEX), encoding="utf-8")
    for name, text in FILES.items():
        (data / name).write_text(text, encoding="utf-8")
    return data


def test_measure_counts_recognized_on_grid_and_extent() -> None:
    m = measure("1-1.mpd", _model(3, 1))
    assert (m.parts, m.recognized, m.on_grid) == (4, 3, 3)
    assert m.recognized_pct == pytest.approx(75.0) and m.on_grid_pct == pytest.approx(100.0)
    assert m.extent == (9, 2, 4) and m.fits_tokens  # three 2x4 bricks stacked: 9 plates, 2 x 4 studs
    assert m.inventory_key and m.inventory_key == measure("x", _model(3, 1)).inventory_key
    assert m.inventory_key != measure("x", _model(3, 1, color=1)).inventory_key
    assert m.shares == {"unrecognized_pct": 25.0, "off_grid_total_pct": 0.0, "tilted_pct": 0.0, "off_stud_grid_pct": 0.0,
                        "overlapping_pct": 0.0, "accessory_off_pct": 0.0, "on_grid_parts_pct": 75.0}


def test_shares_split_off_grid_parts_by_cause() -> None:
    extra = ["1 4 0 -72 0 0 1 0 -1 0 0 0 0 1 3001.dat", "1 4 10 -96 0 1 0 0 0 1 0 0 0 1 3001.dat", "0 NOFILE"]
    text = _model(2, 0).replace("0 NOFILE", "\n".join(extra))
    s = measure("x", text).shares  # a brick turned onto its side, and one half a stud off the grid
    assert (s["unrecognized_pct"], s["tilted_pct"], s["off_stud_grid_pct"], s["on_grid_parts_pct"]) == (0.0, 25.0, 25.0, 50.0)
    assert s["off_grid_total_pct"] == 50.0


def test_select_drops_rereleases_but_keeps_alternates() -> None:
    rows = model_rows(INDEX)
    assert [r["main"] for r in rows] == [True, False, True, True, True]
    assert [r["alternate_of"] for r in rows] == ["", "1-1", "", "", ""]
    measures = {name: measure(name, text) for name, text in FILES.items()}
    table = select(rows, measures, Thresholds(min_share=50, min_on_grid=50, min_grid_parts=2))
    assert [r["selected"] for r in table] == ["yes", "yes", "re-release of 1-1", "< 50% recognized", "< 2 on-grid parts"]


def test_main_writes_pool_and_report_and_reuses_the_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = _data(tmp_path)
    (data / "4-1.mpd").unlink()  # a failed download is left out and counted
    out = tmp_path / "out"
    args = ["--data", str(data), "--cache", str(out / "m.jsonl"), "--pool", str(out / "pool.json"),
            "--results", str(out / "pool.md"), "--workers", "1", "--min-grid-parts", "2", "--demo", "1-1", "9-1"]
    assert main(args) == 0
    pool = json.loads((out / "pool.json").read_text(encoding="utf-8"))
    assert pool["selected"] == ["1-1.mpd", "1-1_B.mpd"]
    assert pool["thresholds"] == {"min_share": 50.0, "min_on_grid": 50.0, "min_grid_parts": 2, "flat_plates": 9,
                                  "flat_area": 1024}
    assert pool["counts"] == {"sets": 4, "models": 5, "main": 4, "on_disk": 4, "failed": 1}
    text = (out / "pool.md").read_text(encoding="utf-8")
    assert "Pool: 2 models from 1 sets" in text and "1-1 in the pool, 9-1 not in the pool" in text
    assert "| pool (2) | 25.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 75.0% |" in text
    assert [r["alternate_of"] for r in pool["models"] if r["selected"] == "yes"] == ["", "1-1"]

    def fail(*_: object) -> None:
        raise AssertionError("measured again")

    monkeypatch.setattr(omr_pool, "measure", fail)
    assert main(args) == 0  # same catalog: everything from the cache


def test_a_catalog_change_measures_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = _data(tmp_path)
    cache = tmp_path / "m.jsonl"
    files = [data / "1-1.mpd"]
    before = omr_pool.measure_all(files, cache, workers=1, log=lambda s: None)
    monkeypatch.setattr(omr_pool, "BY_FILE", {k: v for k, v in omr_pool.BY_FILE.items() if k != "3001.dat"})
    assert omr_pool.catalog_fingerprint() != json.loads(cache.read_text(encoding="utf-8").splitlines()[0])["catalog"]
    after = omr_pool.measure_all(files, cache, workers=1, log=lambda s: None)
    assert before["1-1.mpd"].recognized == 3 and len(cache.read_text(encoding="utf-8").splitlines()) == 2
    assert after["1-1.mpd"].file == "1-1.mpd"


def test_a_flat_panel_is_not_a_build() -> None:
    row = {"set": "5-1"}
    mosaic = Measure("m.mpd", 100, 100, 100, 0, 0, 0, (8, 50, 50), "k", [])
    t = Thresholds(min_grid_parts=2)
    assert reason(row, mosaic, t, {}) == "flat panel (mosaic)"
    assert reason(row, Measure("c.mpd", 100, 100, 100, 0, 0, 0, (7, 4, 31), "k", []), t, {}) == "yes"  # a low car
    assert reason(row, Measure("b.mpd", 100, 100, 100, 0, 0, 0, (10, 50, 50), "k", []), t, {}) == "yes"
