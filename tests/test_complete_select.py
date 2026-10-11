"""M12c: the completeness bar (by volume or by surface), and selection that picks complete builds first."""

import numpy as np
import pytest

from brickwfc.alt.candidates import Candidate, Context
from brickwfc.alt.features import Bar, completeness
from brickwfc.alt.pipeline import AltConfig, events, main, run_funnel
from brickwfc.bricks.style import StyleStats
from brickwfc.funnel.select import select
from conftest import BLUE, RED, piece, tiny_model

GRID = (2, 4, 8)  # (Y, Z, X); a solid target: the cells of layer 0 with 1 <= z <= 2, 1 <= x <= 6 are not exposed
FUNNEL = dict(min_size_quantile=0.0, dedupe_threshold=0.0, fill_floor=0.0)


def candidate(seed: int, placed: list) -> Candidate:
    return Candidate(seed, tuple(placed), (), 1.0, 0.0, 0.0, 1)


def roof(skip: int = 0) -> list:
    """The 2x4 plates covering layer 1, but the last ``skip`` of them."""
    plates = [piece("plate2x4", 1, x, z, BLUE) for x in (0, 4) for z in (0, 2)]
    return plates[: len(plates) - skip]


def floor(gap: bool = False) -> list:
    """Layer 0, whole or with a 2 x 2 gap at z 1-2, x 3-4 (inside, under the roof: not exposed)."""
    if not gap:
        return [piece("plate2x4", 0, x, z) for x in (0, 4) for z in (0, 2)]
    rows = [piece("plate1x8", 0, 0, z) for z in (0, 3)]
    return rows + [piece("plate1x3", 0, x, z) for x in (0, 5) for z in (1, 2)]


def test_largest_surface_hole_counts_exposed_cells_only() -> None:
    mask = np.ones((3, 4, 4), dtype=bool)
    filled = mask.copy()
    filled[1, 1, 1] = False  # inside
    filled[1, 0, 1] = filled[1, 1, 0] = False  # two exposed cells on different sides, joined only through it
    done = completeness(filled, mask)
    assert (done.holes, done.largest_hole, done.largest_surface_hole) == (1, 3, 1)
    filled[2, 0, 1] = False  # the exposed cell above one of them: a 2-cell hole on the surface
    assert completeness(filled, mask).largest_surface_hole == 2
    assert completeness(mask, mask).largest_surface_hole == 0


def test_volume_and_surface_bars() -> None:
    mask = np.ones(GRID, dtype=bool)
    gap = np.zeros(GRID, dtype=bool)
    for part in floor(gap=True) + roof():
        for cell in part.cells():
            gap[cell] = True
    done = completeness(gap, mask)
    share = gap.sum() / mask.sum()  # 60 / 64: under the volume bar's fill
    assert (done.largest_hole, done.surface, done.largest_surface_hole) == (4, 1.0, 0)
    assert not Bar().met(done, share) and Bar(mode="surface").met(done, share)
    assert Bar(fill=0.9).met(done, share)  # the volume bar with a lower fill threshold
    assert Bar().met(completeness(mask, mask), 1.0)
    with pytest.raises(ValueError):
        Bar(mode="area")


def test_select_takes_the_higher_tier_first() -> None:
    scores = np.array([3.0, 2.0, 1.0, 0.0])
    features = np.array([[0.0], [0.0], [5.0], [9.0]])
    assert select(scores, features, k=4, diversity=0.0, tiers=np.array([0, 1, 0, 1])) == [1, 3, 0, 2]
    # diversity still counts within a tier, against every pick so far
    assert select(scores, features, k=2, diversity=1.0, tiers=np.array([1, 1, 1, 0])) == [0, 2]
    assert select(scores, features, k=4, diversity=0.0, tiers=None) == [0, 1, 2, 3]


def setup() -> tuple[StyleStats, Context]:
    stats = StyleStats().add(tiny_model())
    return stats, Context({}, (RED, BLUE), stats, GRID, np.ones(GRID, dtype=bool), None, 0.05)


def test_complete_build_with_a_lower_judge_is_selected_first() -> None:
    stats, context = setup()
    dots = [piece("plate1x1", y, x, z, RED if (x + z + y) % 2 else BLUE) for y in (0, 1) for z in range(4) for x in range(8)]
    full = candidate(0, dots)  # complete, in 1 x 1 plates: a contact pattern unlike the style's
    partial = [candidate(1 + i, floor() + roof(skip)) for i, skip in enumerate((1, 2, 3))]
    config = dict(k=4, diversity=0.0, fill_weight=0.0, **FUNNEL)  # judge only, so the complete build ranks by judge
    old = run_funnel([full, *partial], context, stats, AltConfig(complete_first=False, **config), 0.0)
    new = run_funnel([full, *partial], context, stats, AltConfig(**config), 0.0)
    assert old.selected[0].candidate.seed != 0  # precondition: an incomplete build has the best judge
    assert new.selected[0].candidate.seed == 0 and new.selected[0].judge < old.selected[0].judge
    assert [s.candidate.seed for s in new.selected[1:]] == [s.candidate.seed for s in old.selected if s.candidate.seed]
    assert [s.complete for s in new.selected] == [True, False, False, False] and new.complete == 1


def test_surface_bar_counts_an_interior_gap_as_complete() -> None:
    stats, context = setup()
    gap = candidate(0, floor(gap=True) + roof())  # 60 / 64 filled, but the 4 missing cells are inside
    top = candidate(1, floor() + roof(1))  # 56 / 64, an 8-cell hole in the top
    config = dict(k=2, diversity=0.0, fill_weight=0.0, **FUNNEL)
    volume = run_funnel([gap, top], context, stats, AltConfig(**config), 0.0)
    surface = run_funnel([gap, top], context, stats, AltConfig(bar="surface", **config), 0.0)
    assert volume.complete == 0 and surface.complete == 1
    assert surface.selected[0].candidate.seed == 0 and surface.selected[0].complete


def test_no_completeness_without_a_target() -> None:
    stats = StyleStats().add(tiny_model())
    context = Context({}, (RED, BLUE), stats, GRID, None, None, 1.0)
    report = run_funnel([candidate(0, floor()), candidate(1, floor() + roof())], context, stats,
                        AltConfig(k=2, **FUNNEL), 0.0)
    assert report.complete is None and all(s.complete is None for s in report.selected)


def test_cli_rejects_an_unknown_bar() -> None:
    with pytest.raises(SystemExit):
        main(["6372-1", "--bar", "area"])


def test_a_complete_build_is_never_too_small() -> None:
    """The verify stage's contact-event floor (the smallest 10% of builds) cut the complete 5891-1 chair, which used
    the fewest parts of its run; a build that meets the bar is exempt from the size and fill floors."""
    stats, context = setup()
    full = candidate(0, floor() + roof())  # complete, in the fewest, largest parts: the fewest contact events
    partial = [candidate(1 + i, [piece("plate1x1", y, x, z, RED if (x + z) % 2 else BLUE)
                                 for y in (0, 1) for z in range(4) for x in range(8) if (y, z) != (1, i)])
               for i in range(3)]  # 56 / 64 in 1 x 1 plates (an 8-cell hole): incomplete, many contact events
    config = dict(k=4, diversity=0.0, fill_weight=0.0, **(FUNNEL | {"min_size_quantile": 0.5}))
    counts = sorted((events(c.placed).count, c.seed) for c in (full, *partial))
    assert counts[0][1] == 0 and counts[1][0] > counts[0][0]  # precondition: the complete build is the smallest
    report = run_funnel([full, *partial], context, stats, AltConfig(**config), 0.0)
    assert not report.check_failures  # the floor (the median count) is binding only on the complete build: exempt
    assert any(s.candidate.seed == 0 for s in report.selected)
    assert report.selected[0].candidate.seed == 0 and report.selected[0].complete
