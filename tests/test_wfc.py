import numpy as np
import pytest

from brickwfc.tileset import Tileset
from brickwfc.wfc import Wave, adjacency_violations, attempt_rng, run, solve_attempt


# (a) every finished grid satisfies every adjacency rule
@pytest.mark.parametrize("seed", range(10))
def test_finished_grid_satisfies_rules(terrain: Tileset, seed: int) -> None:
    result = run(terrain, 24, 32, seed)
    assert result.grid is not None
    assert result.grid.shape == (24, 32)
    assert adjacency_violations(result.grid, terrain) == 0


def test_finished_grid_satisfies_rules_3coloring(three_coloring: Tileset) -> None:
    for seed in range(10):
        result = run(three_coloring, 16, 16, seed)
        assert result.grid is not None
        assert adjacency_violations(result.grid, three_coloring) == 0


def test_adjacency_violations_detects_bad_pairs(terrain: Tileset) -> None:
    water, forest = terrain.index("water"), terrain.index("forest")
    grid = np.full((3, 3), water)
    grid[1, 1] = forest  # forest touching water on all 4 sides
    assert adjacency_violations(grid, terrain) == 4


# (b) 1D sanity: collapsing cell 0 to W removes F from cell 1
def test_1d_propagation(wsf: Tileset) -> None:
    wave = Wave(wsf, 1, 3)
    wave.assign((0, 0), wsf.index("W"))
    assert wave.propagate([(0, 0)])
    np.testing.assert_array_equal(wave.domain[0, 0], [True, False, False])
    np.testing.assert_array_equal(wave.domain[0, 1], [True, True, False])  # F removed
    np.testing.assert_array_equal(wave.domain[0, 2], [True, True, True])  # F still reachable via S


def test_propagation_reports_contradiction(wsf: Tileset) -> None:
    wave = Wave(wsf, 1, 3)
    wave.assign((0, 0), wsf.index("W"))
    wave.assign((0, 2), wsf.index("F"))
    assert wave.propagate([(0, 0)])
    wave.assign((0, 1), wsf.index("F"))  # F next to W
    assert not wave.propagate([(0, 1)])


# (c) same seed -> identical output
def test_same_seed_same_output(terrain: Tileset) -> None:
    a = run(terrain, 32, 32, seed=7)
    b = run(terrain, 32, 32, seed=7)
    np.testing.assert_array_equal(a.grid, b.grid)
    assert a.stats.attempts == b.stats.attempts
    assert a.stats.cells_collapsed == b.stats.cells_collapsed


def test_different_seeds_differ(terrain: Tileset) -> None:
    assert not np.array_equal(run(terrain, 32, 32, seed=1).grid, run(terrain, 32, 32, seed=2).grid)


# (d) contradiction triggers a restart and is counted
def test_contradiction_restarts_and_is_counted(three_coloring: Tileset) -> None:
    restarted = [r for r in (run(three_coloring, 16, 16, s) for s in range(30)) if r.stats.attempts > 1]
    assert restarted, "expected at least one 16x16 3-coloring run to hit a contradiction"
    for result in restarted:
        stats = result.stats
        assert stats.success
        assert stats.contradictions == stats.attempts - 1
        # The successful grid is exactly what the last attempt's seed produces on its own...
        last = solve_attempt(three_coloring, 16, 16, attempt_rng(stats.seed, stats.attempts - 1))
        np.testing.assert_array_equal(result.grid, last.grid)
        # ...and every earlier attempt seed contradicts.
        for attempt in range(stats.attempts - 1):
            assert solve_attempt(three_coloring, 16, 16, attempt_rng(stats.seed, attempt)).grid is None


def test_unsatisfiable_exhausts_attempts() -> None:
    lonely = Tileset.from_pairs(["x"], [(0, 0, 0)], [1.0], [])  # x may not touch anything
    result = run(lonely, 2, 2, seed=0, max_attempts=5)
    assert result.grid is None
    assert not result.stats.success
    assert result.stats.attempts == 5
    assert result.stats.contradictions == 5


def test_entropy_values() -> None:
    uniform = Tileset.from_pairs(["a", "b", "c", "d"], [(0, 0, 0)] * 4, [1.0] * 4, [("a", "a")])
    wave = Wave(uniform, 1, 2)
    wave.assign((0, 1), 0)
    np.testing.assert_allclose(wave.entropy()[0], [np.log(4), 0.0], atol=1e-12)


def test_observe_picks_lowest_entropy(wsf: Tileset) -> None:
    wave = Wave(wsf, 1, 3)
    wave.domain[0, 2] = [True, True, False]  # 2 options vs 3 elsewhere
    assert wave.observe(np.random.default_rng(0)) == (0, 2)


def test_collapse_follows_weights() -> None:
    ts = Tileset.from_pairs(["a", "b"], [(0, 0, 0)] * 2, [1.0, 3.0], [("a", "a"), ("b", "b"), ("a", "b")])
    rng = np.random.default_rng(0)
    picks = [Wave(ts, 1, 1).collapse((0, 0), rng) for _ in range(4000)]
    assert np.mean(picks) == pytest.approx(0.75, abs=0.03)


def test_stats_are_populated(terrain: Tileset) -> None:
    stats = run(terrain, 8, 8, seed=3).stats
    assert stats.seed == 3
    assert stats.success
    assert 1 <= stats.cells_collapsed <= 64
    assert stats.wall_time_s > 0
