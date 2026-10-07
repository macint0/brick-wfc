import json
from pathlib import Path

import numpy as np
import pytest

from brickwfc.funnel.dedupe import dedupe
from brickwfc.funnel.features import feature_vector, label_regions, perimeter, region_sizes
from brickwfc.funnel.judge import Candidate, HeuristicJudge
from brickwfc.funnel.pipeline import FunnelConfig, main, run_funnel
from brickwfc.funnel.select import select
from brickwfc.funnel.verify import land_connectivity, land_fraction, verify
from brickwfc.tileset import Tileset

from conftest import EXAMPLES


def mask(rows: list[str]) -> np.ndarray:
    return np.array([[c == "#" for c in row] for row in rows])


def candidate(land: np.ndarray, seed: int = 0) -> Candidate:
    grid = land.astype(np.int64)
    return Candidate(seed, grid, land, feature_vector(grid, land, 2))


def test_label_regions_four_connected() -> None:
    land = mask(["##..", "#..#", "..##", "#..."])
    labels, count = label_regions(land)
    assert count == 3  # diagonal contact does not connect
    assert sorted(region_sizes(land).tolist()) == [1, 3, 3]
    assert (labels > 0).sum() == land.sum()


def test_perimeter_excludes_grid_border() -> None:
    assert perimeter(mask(["....", ".##.", ".##.", "...."])) == 8
    assert perimeter(mask(["####", "####"])) == 0


def test_land_connectivity_margin() -> None:
    assert land_connectivity(mask(["##..", "##.."]), min_fraction=1.0).margin == pytest.approx(0.0)
    split = land_connectivity(mask(["###.#"]), min_fraction=1.0)
    assert split.margin == pytest.approx(0.75 - 1.0) and not split.passed
    assert not land_connectivity(mask(["...."])).passed


def test_land_fraction_margin() -> None:
    assert land_fraction(mask(["##.."]), 0.3, 0.9).margin == pytest.approx(0.2)
    assert not land_fraction(mask(["...."]), 0.3, 0.9).passed
    assert not land_fraction(mask(["####"]), 0.3, 0.9).passed


def test_verify_runs_all_checks() -> None:
    assert [c.name for c in verify(mask(["##.."]))] == ["land_connectivity", "land_fraction"]


def test_dedupe_drops_near_duplicates_in_order() -> None:
    features = np.array([[0.0, 0.0], [0.01, 0.0], [1.0, 0.0], [0.0, 0.02], [1.0, 0.04]])
    assert dedupe(features, threshold=0.05) == [0, 2]
    assert dedupe(features, threshold=0.0) == [0, 1, 2, 3, 4]


def test_select_trades_score_for_diversity() -> None:
    scores = np.array([1.0, 0.99, 0.5])
    features = np.array([[0.0], [0.0], [1.0]])  # 0 and 1 are identical designs
    assert select(scores, features, k=2, diversity=0.0) == [0, 1]
    assert select(scores, features, k=2, diversity=1.0) == [0, 2]
    assert select(scores, features, k=10) == [0, 2, 1]


def test_heuristic_judge_prefers_compact_balanced_land() -> None:
    judge = HeuristicJudge()
    island = np.zeros((8, 8), dtype=bool)
    island[2:6, 2:6] = True
    island[1:7, 3:5] = True
    checker = (np.indices((8, 8)).sum(axis=0) % 2).astype(bool)
    island_score, checker_score = judge.score(candidate(island)), judge.score(candidate(checker))
    assert 0 <= checker_score < island_score <= 1


def small_config(**overrides: object) -> FunnelConfig:
    base = dict(n=30, width=12, height=12, k=5, min_connected=0.8)
    return FunnelConfig(**{**base, **overrides})


def test_funnel_stage_counts_shrink(terrain: Tileset) -> None:
    result = run_funnel(terrain, small_config())
    survivors = [s.survivors for s in result.stats.stages]
    assert [s.stage for s in result.stats.stages] == ["generate", "verify", "dedupe", "judge", "select"]
    assert result.stats.requested >= survivors[0]
    assert all(a >= b for a, b in zip(survivors, survivors[1:]))
    assert len(result.selected) == survivors[-1] <= 5
    for c in result.selected:
        assert all(check.passed for check in verify(c.land, 0.8))


def test_funnel_is_deterministic(terrain: Tileset) -> None:
    a = run_funnel(terrain, small_config())
    b = run_funnel(terrain, small_config())
    assert a.stats.selected_seeds == b.stats.selected_seeds


def test_custom_judge_plugs_in(terrain: Tileset) -> None:
    class EvenSeedJudge:
        def score(self, c: Candidate) -> float:
            return 10.0 if c.seed % 2 == 0 else 0.0

    result = run_funnel(terrain, small_config(k=3, diversity=0.0), judge=EvenSeedJudge())
    assert result.selected and all(c.seed % 2 == 0 for c in result.selected)


def test_funnel_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = ["--tiles", str(EXAMPLES / "terrain.json"), "--n", "20", "--size", "10x10", "--k", "4",
            "--min-connected", "0.7", "--out", str(tmp_path)]
    assert main(args) == 0
    out = capsys.readouterr().out
    for stage in ["requested", "generate", "verify", "dedupe", "judge", "select"]:
        assert stage in out
    report = json.loads((tmp_path / "stats.json").read_text())
    assert report["requested"] == 20 and report["config"]["k"] == 4
    assert (tmp_path / "selected.png").exists()
