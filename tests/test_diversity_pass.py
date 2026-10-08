"""M13: diversity pass over alt run folders (synthetic candidates.jsonl, no builds)."""

import json
from pathlib import Path

import pytest

from brickwfc.alt.candidates import Candidate
from brickwfc.experiments import diversity_pass, paper_tables
from brickwfc.experiments.diversity_pass import analyze, collect, label, read_run, run_folders
from conftest import BLUE, RED, piece


def designs() -> list[tuple]:
    """Three distinct small builds; repeats of one of them make near-duplicates."""
    tower = (piece("brick2x4", 0, 0, 0), piece("brick2x4", 3, 0, 0, BLUE))
    slab = (piece("plate2x4", 0, 0, 0), piece("plate2x4", 0, 0, 2, BLUE), piece("plate2x4", 1, 0, 1))
    corner = (piece("brick1x2", 0, 0, 0), piece("brick1x2", 0, 4, 4, BLUE), piece("plate2x4", 3, 0, 0, RED))
    return [tower, slab, corner]


def write_run(folder: Path, generator: str = "d2", connect: bool = True, finished: bool = True,
              partial_line: bool = False) -> None:
    folder.mkdir(parents=True)
    key = {"source": "tiny", "inventory": [["brick2x4", "red", 2], ["brick2x4", "blue", 2], ["plate2x4", "red", 4],
                                           ["plate2x4", "blue", 2], ["brick1x2", "red", 2], ["brick1x2", "blue", 2]],
           "grid": [6, 6, 6], "mask": None, "generator": generator, "balanced": True, "connect": connect}
    tower, slab, corner = designs()
    builds = [tower, tower, tower, slab, corner, slab, ()]  # the empty one fails "generate"
    lines = [json.dumps({"key": key})]
    for seed, placed in enumerate(builds):
        failed = () if placed else ("generate",)
        lines.append(json.dumps(Candidate(seed, placed, failed, 1.0, 0.1, 0.0, 1).to_json()))
    lines.append(json.dumps(Candidate(9, tower, ("physics",), 1.0, 0.1, 0.0, 1).to_json()))  # invalid
    text = "\n".join(lines) + "\n" + ('{"seed": 10, "fail' if partial_line else "")
    (folder / "candidates.jsonl").write_text(text, encoding="utf-8")
    if finished:
        stats = {"config": {"dedupe_threshold": 0.05, "min_size_quantile": 0.0},
                 "selected": [{"rank": 1, "seed": 0}, {"rank": 2, "seed": 3}, {"rank": 3, "seed": 4}]}
        (folder / "stats.json").write_text(json.dumps(stats), encoding="utf-8")


def test_labels() -> None:
    assert label({"generator": "d2", "balanced": True, "connect": True}) == "pipeline"
    assert label({"generator": "wfc"}) == "pipeline_wfc"
    assert label({"generator": "d2", "balanced": True, "connect": False}) == "d2_noconnect"
    assert label({"generator": "d2", "balanced": False, "connect": False}) == "d2_nobalance_noconnect"


def test_analyze_verified_and_selected(tmp_path: Path) -> None:
    write_run(tmp_path / "run", partial_line=True)
    key, candidates = read_run(tmp_path / "run" / "candidates.jsonl")
    assert key["source"] == "tiny" and len(candidates) == 8  # the incomplete last line is skipped
    row = analyze(tmp_path / "run")
    assert row["generator"] == "pipeline" and row["candidates"] == 8 and row["valid"] == 6 and row["verified"] == 6
    # Three towers, two slabs, one corner: the Hill number of group sizes (3, 2, 1).
    import math
    p = [3 / 6, 2 / 6, 1 / 6]
    assert row["effective"] == pytest.approx(math.exp(-sum(x * math.log(x) for x in p)))
    assert row["effective_share"] == pytest.approx(row["effective"] / 6)
    assert row["selected"] == 3 and row["selected_effective"] == pytest.approx(3)
    profile = row["effective_share_at"]
    assert list(profile) == ["0.05", "0.1", "0.2", "0.3", "0.5"] and profile["0.05"] == pytest.approx(row["effective_share"])
    assert all(a >= b - 1e-12 for a, b in zip(profile.values(), list(profile.values())[1:]))  # falls as t grows


def test_unfinished_run_has_no_selection(tmp_path: Path) -> None:
    write_run(tmp_path / "run", finished=False)
    row = analyze(tmp_path / "run")
    assert row["finished"] is False and "selected" not in row and row["verified"] == 6


def test_size_floor_drops_small_builds(tmp_path: Path) -> None:
    write_run(tmp_path / "run")
    stats = json.loads((tmp_path / "run" / "stats.json").read_text())
    stats["config"]["min_size_quantile"] = 0.99
    (tmp_path / "run" / "stats.json").write_text(json.dumps(stats))
    assert analyze(tmp_path / "run")["verified"] < 6


def test_pass_is_cached_and_feeds_the_paper_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_run(tmp_path / "out" / "m12_demo" / "s1" / "d2")
    write_run(tmp_path / "out" / "m12_demo" / "s1" / "d2_no_connect", connect=False)
    write_run(tmp_path / "out" / "m12_demo" / "s1" / "wfc", generator="wfc", finished=False)
    folders = run_folders(tmp_path, ["out/m12_demo/*/*"])
    assert [f.name for f in folders] == ["d2", "d2_no_connect", "wfc"]
    out = tmp_path / "results" / "m13_diversity.json"
    args = ["--base", str(tmp_path), "--roots", "out/m12_demo/*/*", "--cache", str(tmp_path / "cache.json"), "--out", str(out)]
    assert diversity_pass.main(args) == 0
    rows = json.loads(out.read_text())
    assert [r["generator"] for r in rows] == ["pipeline", "d2_noconnect", "pipeline_wfc"]
    assert rows[0]["run"] == "out/m12_demo/s1/d2"
    assert "| pipeline | 1 |" in out.with_suffix(".md").read_text(encoding="utf-8")

    calls = []
    monkeypatch.setattr(diversity_pass, "analyze", lambda folder: calls.append(folder) or {"run": "x"})
    collect(folders, tmp_path / "cache.json", tmp_path)
    assert calls == []  # nothing changed: every row from the cache
    (folders[2] / "stats.json").write_text(json.dumps({"config": {}, "selected": []}))
    collect(folders, tmp_path / "cache.json", tmp_path)
    assert calls == [folders[2]]

    data = {tag: paper_tables.load(source, tmp_path) for tag, source in paper_tables.SOURCES.items()}
    text = paper_tables.render(data)
    row = next(line for line in text.splitlines() if line.startswith("| Pipeline: D2"))
    assert f"{100 * rows[0]['effective_share']:.0f} [diversity]" in row


def test_run_without_valid_candidates(tmp_path: Path) -> None:
    folder = tmp_path / "run"
    folder.mkdir()
    key = {"source": "tiny", "inventory": [["brick2x4", "red", 2]], "grid": [6, 6, 6], "generator": "wfc"}
    failed = Candidate(0, (), ("generate",), float("nan"), 30.0, 0.0).to_json()
    lines = [json.dumps({"key": key}), json.dumps(failed)]
    (folder / "candidates.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (folder / "stats.json").write_text(json.dumps({"config": {}, "selected": []}), encoding="utf-8")
    row = analyze(folder)
    assert row["verified"] == 0 and row["effective"] == 0 and row["selected"] == 0
    assert row["effective_share"] is None and set(row["effective_share_at"].values()) == {None}  # no builds: no value
