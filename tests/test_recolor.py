"""M12c recolouring within part types (bricks/recolor.py) and the pipeline's --recolor (after select)."""

from collections import Counter

import numpy as np
import pytest

from brickwfc.alt.candidates import Candidate, Context
from brickwfc.alt.pipeline import FunnelReport, Selected, recolor_selected
from brickwfc.bricks.coherence import coherence
from brickwfc.bricks.recolor import WINDOW_WEIGHT, recolor, score, skin_structure
from conftest import BLUE, RED, WHITE, piece

GRID = (2, 4, 8)


def checkerboard() -> list:
    """Two layers of four 2 x 4 plates over 4 x 8 studs, red and blue alternating: no seam shares a colour."""
    return [piece("plate2x4", y, x, z, RED if (y + x // 4 + z // 2) % 2 else BLUE)
            for y in (0, 1) for x in (0, 4) for z in (0, 2)]


def count(parts) -> Counter:
    return Counter((p.shape.part.name, p.color.name) for p in parts)


def where(parts) -> list:
    return [(p.shape, p.layer, p.x, p.z) for p in parts]


def test_the_known_optimum_of_a_checkerboard() -> None:
    # Four red and four blue plates of one type: the best skin is one colour per layer (8 of 12 visible pairs share a
    # colour, every top window one colour); splitting by halves gives 8 of 12 too but two-colour top windows.
    for seed in range(10):  # halves are a local optimum two swaps away; annealing keeps the best colouring seen
        done = recolor(checkerboard(), GRID, np.random.default_rng([seed, 7]))
        assert done.before.same_color == 0.0 and done.before.top_colors == 2.0
        assert done.after.same_color == pytest.approx(8 / 12) and done.after.top_colors == 1.0
        assert len({p.color for p in done.placed if p.layer == 1}) == 1 and done.swaps > 0


def test_an_off_colour_goes_inside() -> None:
    # A 3 x 3 x 3 block of 1 x 1 plates, one of them red on the top face: two cells show nothing (the centre and the
    # one under it), so the red one can go there and the skin becomes one colour.
    block = [piece("plate1x1", y, x, z, RED if (y, x, z) == (2, 1, 1) else WHITE)
             for y in range(3) for x in range(3) for z in range(3)]
    done = recolor(block, (3, 3, 3), np.random.default_rng(0))
    assert done.before.skin_colors == 2 and done.after.skin_colors == 1 and done.after.same_color == 1.0
    red = next(p for p in done.placed if p.color == RED)
    assert (red.layer, red.x, red.z) in {(1, 1, 1), (0, 1, 1)}


def test_placements_and_counts_are_kept_and_one_colour_types_are_fixed() -> None:
    placed = checkerboard() + [piece("plate1x2", 2, 0, 0, WHITE), piece("plate1x2", 2, 0, 1, WHITE)]
    done = recolor(placed, (3, 4, 8), np.random.default_rng(1))
    assert where(done.placed) == where(placed) and count(done.placed) == count(placed)
    assert all(p.color == WHITE for p in done.placed[-2:])  # a type in one colour cannot change
    assert done.movable_parts == 8 and 0 < done.fixed_skin_share < 1


def test_deterministic_and_the_score_is_the_coherence_metrics() -> None:
    placed = checkerboard()
    a = recolor(placed, GRID, np.random.default_rng(5))
    b = recolor(placed, GRID, np.random.default_rng(5))
    assert a.placed == b.placed and a.swaps == b.swaps
    pairs, windows, _ = skin_structure(a.placed, GRID)
    names = sorted({p.color.name for p in a.placed})
    colors = [names.index(p.color.name) for p in a.placed]
    after = coherence(a.placed, GRID)
    assert score(colors, pairs, windows) == pytest.approx(after.same_color - WINDOW_WEIGHT * after.colors_per_window)


def test_recolor_selected_keeps_the_judge_and_the_placements() -> None:
    candidate = Candidate(3, tuple(checkerboard()), (), 1.0, 0.0, 0.0, 1)
    report = FunnelReport(1, [], {}, 0, 0, [Selected(candidate, -0.3, True)], [candidate])
    context = Context({}, (RED, BLUE), None, GRID, np.ones(GRID, dtype=bool), None, 0.05)
    out = recolor_selected(report, context).selected[0]
    assert out.judge == -0.3 and out.complete and out.candidate.seed == 3
    assert where(out.candidate.placed) == where(candidate.placed) and count(out.candidate.placed) == count(candidate.placed)
    assert out.recolored["seams_pct_before"] == 0.0 and out.recolored["seams_pct_after"] == pytest.approx(100 * 8 / 12)
    assert recolor_selected(report, context).selected[0].candidate == out.candidate  # seeded by the build's seed
    assert out.recolored["colors_per_window_after"] == 1.0
