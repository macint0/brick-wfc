"""M12b: with a target shape, the funnel fails low-fill builds and selects by judge and fill."""

import math

import numpy as np

from brickwfc.alt.candidates import Candidate, Context
from brickwfc.alt.pipeline import AltConfig, run_funnel, standardized
from brickwfc.bricks.style import StyleStats
from conftest import BLUE, RED, piece, tiny_model

GRID = (2, 4, 8)


def layer(y: int, color=RED) -> list:
    """Four 2x4 plates covering a whole 4 x 8 layer."""
    return [piece("plate2x4", y, x, z, color) for x in (0, 4) for z in (0, 2)]


def candidate(seed: int, placed: list) -> Candidate:
    return Candidate(seed, tuple(placed), (), 1.0, 0.0, 0.0, 1)


def setup(mask: bool = True):
    stats = StyleStats().add(tiny_model())
    context = Context({}, (RED, BLUE), stats, GRID, np.ones(GRID, dtype=bool) if mask else None, None, 0.05)
    full = candidate(0, layer(0) + layer(1, BLUE))  # fills the shape
    half = candidate(1, layer(0))  # half of it
    stub = candidate(2, [piece("plate1x2", 0), piece("plate1x2", 1, color=BLUE)])  # 4 of 64 cells
    more = [candidate(3 + i, layer(0) + [piece("plate2x4", 1, 0, 0, BLUE)] * (i % 2)) for i in range(4)]
    return stats, context, [full, half, stub, *more]


def test_low_fill_builds_fail_with_a_target() -> None:
    stats, context, candidates = setup()
    report = run_funnel(candidates, context, stats, AltConfig(k=8, min_size_quantile=0.0, dedupe_threshold=0.0), 0.0)
    assert report.check_failures.get("low_fill") == 1  # the stub: 4/64 < 0.5 x the 90th percentile
    assert 2 not in {s.candidate.seed for s in report.selected}
    report = run_funnel(candidates, context, stats,
                        AltConfig(k=8, min_size_quantile=0.0, dedupe_threshold=0.0, fill_floor=0.0), 0.0)
    assert "low_fill" not in report.check_failures


def test_no_fill_floor_without_a_target() -> None:
    stats, context, candidates = setup(mask=False)
    report = run_funnel(candidates, context, stats, AltConfig(k=8, min_size_quantile=0.0, dedupe_threshold=0.0), 0.0)
    assert "low_fill" not in report.check_failures


def test_fill_weight_moves_the_full_build_up() -> None:
    stats, context, candidates = setup()
    config = dict(k=1, min_size_quantile=0.0, dedupe_threshold=0.0, fill_floor=0.0, diversity=0.0)
    judge_only = run_funnel(candidates, context, stats, AltConfig(fill_weight=0.0, **config), 0.0)
    best_judge = max(judge_only.selected, key=lambda s: s.judge)
    assert judge_only.selected[0] is best_judge  # weight 0: the old, judge-only order
    heavy = run_funnel(candidates, context, stats, AltConfig(fill_weight=100.0, **config), 0.0)
    assert heavy.selected[0].candidate.seed == 0  # fill dominates: the build that fills the shape


def test_standardized() -> None:
    assert np.allclose(standardized(np.array([1.0, 3.0])), [-1.0, 1.0])
    assert np.allclose(standardized(np.array([2.0, 2.0])), [0.0, 0.0]) and not math.isnan(standardized(np.ones(3))[0])


def test_min_fill_fails_a_run_where_every_build_stalls() -> None:
    # The fill floor is relative to the run's 90th percentile, so stubs alone pass it; --min-fill is absolute.
    stats, context, _ = setup()
    stubs = [candidate(i, [piece("plate1x2", 0), piece("plate1x2", 1, color=BLUE)]) for i in range(3)]
    config = dict(k=2, min_size_quantile=0.0, dedupe_threshold=0.0)
    relative = run_funnel(stubs, context, stats, AltConfig(**config), 0.0)
    assert "low_fill" not in relative.check_failures and relative.selected  # 4 / 64 cells, every one "valid"
    absolute = run_funnel(stubs, context, stats, AltConfig(min_fill=0.5, **config), 0.0)
    assert absolute.check_failures["low_fill"] == 3 and not absolute.selected
    _, _, candidates = setup()
    kept = run_funnel(candidates, context, stats, AltConfig(min_fill=0.5, k=8, min_size_quantile=0.0,
                                                            dedupe_threshold=0.0), 0.0)
    assert kept.check_failures["low_fill"] == 1  # only the stub; the half-filled build is at the floor
