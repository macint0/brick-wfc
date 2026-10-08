"""M10: learned style statistics, judge, distance, and style-biased generation."""

import json
from pathlib import Path

import numpy as np
import pytest

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import CATALOG, PlacedPart, Shape, extract_parts, part_tileset
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.style import (
    TYPE_INDEX,
    TYPES,
    StyleBias,
    StyleStats,
    contacts,
    distance,
    events,
    js_divergence,
    judge,
    learn,
    matched_divergence,
    merged,
    size_matched,
    subsample,
)
from brickwfc.bricks.support import is_stable
from brickwfc.experiments.style import folds, main as style_main
from brickwfc.ldraw.export import write_ldr
from brickwfc.wfc import run

RED, BLUE = colors_by_name(["red", "blue"])


def piece(name: str, layer: int, x: int = 0, z: int = 0, color=RED) -> PlacedPart:
    return PlacedPart(Shape(CATALOG[name], False), color, layer, x, z)


def wall(color_top=RED) -> list[PlacedPart]:
    """Two 1x2 bricks side by side, a 1x4 plate bridging them, a 1x2 tile on top of the plate."""
    return [piece("brick1x2", 0, 0), piece("brick1x2", 0, 2, color=BLUE), piece("plate1x4", 3, 0, color=color_top),
            piece("tile1x2", 4, 1, color=color_top)]


def test_contacts() -> None:
    found = contacts(wall())
    assert found.vertical == [(0, 2), (1, 2), (2, 3)]
    assert found.horizontal == [(0, 1)]
    assert found.supports == [2, 1]  # the plate bridges two bricks; the tile rests on the plate


def test_learn_counts_and_roundtrip(tmp_path: Path) -> None:
    stats = learn([wall(), wall()])
    t = TYPE_INDEX
    assert stats.models == 2 and stats.parts.sum() == 8
    assert stats.vertical[t["brick1x2"], t["plate1x4"]] == 4 and stats.vertical[t["plate1x4"], t["tile1x2"]] == 2
    assert stats.horizontal[t["brick1x2"], t["brick1x2"]] == 4  # one pair per model, counted both ways
    assert stats.same_color.tolist() == [[4, 6], [0, 2]]  # vertical: red-red twice per model; beside: red-blue
    assert stats.supports.tolist() == [2, 2, 0]
    stats.save(tmp_path / "s.json")
    loaded = StyleStats.load(tmp_path / "s.json")
    for key in ("parts", "vertical", "horizontal", "same_color", "supports"):
        assert np.array_equal(getattr(loaded, key), getattr(stats, key))
    assert loaded.colors == stats.colors and loaded.models == 2


def test_judge_prefers_the_learned_arrangement() -> None:
    stats = learn([wall()] * 5)
    # Same parts, other arrangement: tile on a brick, plate not bridging, other colors.
    other = [piece("brick1x2", 0, 0), piece("brick1x2", 0, 2, color=BLUE), piece("tile1x2", 3, 0, color=BLUE),
             piece("plate1x4", 3, 2, color=RED)]
    assert judge(wall(), stats).total > judge(other, stats).total
    score = judge(wall(), stats)
    assert score.events == 3 + 1 + 4 + 2 and score.total == 0.0 and score.likelihood < 0  # same statistics


def test_judge_is_not_won_by_repeating_one_contact() -> None:
    # "Real" builds: varied bottom-up builds from mixed parts; learn from all but the last one.
    names = ("brick1x2", "brick2x4", "plate1x4", "plate2x2", "tile1x2")
    parts = part_tileset([CATALOG[n] for n in names], [RED, BLUE], empty_weight=0.5)
    builder = BottomUpBuilder(parts, any_offset=True)
    builds = [extract_parts(builder.build((9, 6, 6), np.random.default_rng(seed)), parts)[0] for seed in range(9)]
    stats = learn(builds[:-1])
    held_out = judge(builds[-1], stats)
    # The most common part-on-same-part contact, repeated: a tower of one part type in one color.
    stacked = int(np.argmax(np.diag(stats.vertical)))
    height = CATALOG[TYPES[stacked]].height
    tower = [piece(TYPES[stacked], height * i) for i in range(20)]
    sheet = [piece("plate2x2", 0, 2 * i, 2 * j) for i in range(5) for j in range(5)]
    for degenerate in (tower, sheet):
        score = judge(degenerate, stats)
        assert score.total < held_out.total
    assert judge(tower, stats).likelihood > held_out.likelihood  # why the likelihood alone is not the judge


def test_distance() -> None:
    recolored = wall()
    recolored[3] = piece("tile1x2", 4, 1, color=BLUE)  # tile no longer matches the plate below it
    a, b = StyleStats().add(wall()), StyleStats().add(recolored)
    assert distance(a, a)["mean"] == 0.0
    d = distance(a, b)
    assert d == distance(b, a) and 0 < d["mean"] <= 1
    assert d["vertical_js"] == 0 and d["color_gap_vertical"] > 0  # same parts on same parts, other colors
    assert js_divergence([1, 0], [0, 1]) == pytest.approx(1.0) and js_divergence([2, 2], [1, 1]) == 0.0


def test_bias_favors_learned_neighbors() -> None:
    stats = learn([wall()] * 5)
    parts = part_tileset([CATALOG[n] for n in ("plate1x4", "tile1x2")], [RED, BLUE])
    bias = StyleBias(stats, parts)
    types = np.array([TYPE_INDEX["plate1x4"], TYPE_INDEX["tile1x2"]])
    colors = np.array([bias.color_id("red")] * 2)
    on_brick = bias.for_choices([(0, piece("brick1x2", 0))], types, colors)
    assert on_brick[0] > on_brick[1]  # plates, not tiles, sit on bricks
    on_plate = bias.for_choices([(0, piece("plate1x4", 3))], types, colors)
    assert on_plate[1] > on_plate[0]
    assert np.allclose(StyleBias(stats, parts, strength=0).for_choices([(0, piece("brick1x2", 0))], types, colors), 1)


def test_styled_generators_build_valid_reproducible_builds() -> None:
    stats = learn([wall()] * 5)
    parts = part_tileset([CATALOG[n] for n in ("brick1x2", "plate1x4", "tile1x2")], [RED, BLUE], empty_weight=1.0)
    bias = StyleBias(stats, parts)
    builder = BottomUpBuilder(parts, any_offset=True, style=bias)
    for seed in range(5):
        grid = builder.build((7, 4, 4), np.random.default_rng(seed))
        assert np.array_equal(grid, builder.build((7, 4, 4), np.random.default_rng(seed)))
        placed, errors = extract_parts(grid, parts)
        assert errors == [] and is_stable(placed, parts.solid[grid])
    for seed in range(3):
        result = run(parts.tileset, (7, 4, 4), seed, constraints=[SupportConstraint(parts)], max_backtracks=500,
                     bias=bias.for_tiles)
        assert result.grid is not None
        again = run(parts.tileset, (7, 4, 4), seed, constraints=[SupportConstraint(parts)], max_backtracks=500,
                    bias=bias.for_tiles)
        assert np.array_equal(result.grid, again.grid)
        placed, errors = extract_parts(result.grid, parts)
        assert errors == [] and is_stable(placed, parts.solid[result.grid])


def test_folds_cover_every_set_once() -> None:
    sets = [f"{i}-1" for i in range(10)]
    split = folds(sets, 4, seed=0)
    assert sorted(s for fold in split for s in fold) == sorted(sets) and len(split) == 4
    assert split == folds(sets, 4, seed=0)


def test_style_experiment_cli_offline(tmp_path: Path) -> None:
    data = tmp_path / "omr"
    sets = []
    for i in range(4):  # four small "real sets": generated walls in different colors
        parts = part_tileset([CATALOG[n] for n in ("brick1x2", "plate1x4", "tile1x2")], [RED, BLUE], empty_weight=0.5)
        grid = BottomUpBuilder(parts, any_offset=True).build((7, 4, 4), np.random.default_rng(i))
        placed, _ = extract_parts(grid, parts)
        write_ldr((p.placement() for p in placed), data / f"fake{i}-1.mpd", f"fake {i}")
        sets.append(f"fake{i}-1")
    (tmp_path / "sets.json").write_text(json.dumps({"selected": sets}))
    out = tmp_path / "m10"
    common = ["--sets-file", str(tmp_path / "sets.json"), "--data", str(data), "--folds", "2", "--seeds", "2",
              "--wfc-seeds", "1", "--height", "6", "--time-limit", "30"]
    args = common + ["--workers", "1", "--out", str(out)]
    assert style_main(args) == 0
    # Two worker processes give the same results as one (only wall times differ).
    assert style_main(common + ["--workers", "2", "--wfc-workers", "1", "--out", str(tmp_path / "m10_parallel")]) == 0

    def without_times(path: Path) -> list[dict]:
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        return [{k: v for k, v in row.items() if k != "wall_time_s"} for row in rows]

    assert without_times(out / "runs.jsonl") == without_times(tmp_path / "m10_parallel" / "runs.jsonl")
    summaries = json.loads((out / "summary.json").read_text())
    assert len(summaries) == 4 * 3 * 3  # sets x conditions x styles
    assert all(s["status"] == "ok" for s in summaries)
    assert all(s["overuse"] == 0 for s in summaries if s["condition"] == "D2_inventory")
    text = (out / "results.md").read_text(encoding="utf-8")
    assert "D2_inventory" in text and "Judge sanity check" in text and "tower of 20 2x4 bricks" in text
    assert "Spearman" in text and "size-matched" in text
    assert style_main(args) == 0  # resumes without rerunning
    assert len(json.loads((out / "summary.json").read_text())) == len(summaries)


def test_events_subsample_and_matched_divergence() -> None:
    names = ("brick1x2", "brick2x4", "plate1x4", "plate2x2", "tile1x2")
    parts = part_tileset([CATALOG[n] for n in names], [RED, BLUE], empty_weight=0.5)
    builder = BottomUpBuilder(parts, any_offset=True)
    builds = [extract_parts(builder.build((9, 6, 6), np.random.default_rng(seed)), parts)[0] for seed in range(6)]
    stats = merged([StyleStats().add(b) for b in builds[:-1]])
    assert np.array_equal(stats.vertical, learn(builds[:-1]).vertical) and stats.models == 5
    found = events(builds[-1])
    assert found.count == judge(builds[-1], stats).events
    assert np.array_equal(StyleStats().add_events(found).vertical, StyleStats().add(builds[-1]).vertical)
    half = subsample(found, found.count // 2, np.random.default_rng(0))
    assert abs(half.count - found.count // 2) <= 3 and len(half.supports) < len(found.supports)
    assert subsample(found, found.count + 10, np.random.default_rng(0)) is found
    full = matched_divergence(found, found.count, stats, np.random.default_rng(0), draws=2)
    assert full == pytest.approx(judge(builds[-1], stats).divergence)
    small = matched_divergence(found, 30, stats, np.random.default_rng(0), draws=5)
    assert small > full  # fewer events: noisier statistics, larger divergence


def test_size_matched_subsamples_the_larger_side() -> None:
    names = ("brick1x2", "brick2x4", "plate1x4", "plate2x2", "tile1x2")
    parts = part_tileset([CATALOG[n] for n in names], [RED, BLUE], empty_weight=0.5)
    builder = BottomUpBuilder(parts, any_offset=True)
    big, small = (extract_parts(builder.build(shape, np.random.default_rng(1)), parts)[0] for shape in ((9, 8, 8), (6, 4, 4)))
    stats = learn([extract_parts(builder.build((9, 6, 6), np.random.default_rng(s)), parts)[0] for s in range(2, 6)])
    big_events, small_events = events(big), events(small)
    assert big_events.count > small_events.count
    for build, real in ((big_events, small_events), (small_events, big_events)):
        build_judge, real_judge, size = size_matched(build, real, stats, np.random.default_rng(0))
        assert size == small_events.count
    # The smaller side is judged whole; the larger side is subsampled (so its judge drops toward the noise level).
    build_judge, real_judge, _ = size_matched(small_events, big_events, stats, np.random.default_rng(0))
    assert build_judge == pytest.approx(-judge(small, stats).divergence)
    assert real_judge < -judge(big, stats).divergence
