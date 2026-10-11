"""M12c colour coherence of a build's skin (bricks/coherence.py) on synthetic builds."""

from collections import Counter

import numpy as np
import pytest

from brickwfc.bricks.coherence import coherence, shuffled, visible_pairs
from conftest import BLUE, RED, WHITE, piece


def slab(colors) -> list:
    """Two layers of 2 x 4 plates covering 4 x 8 studs; ``colors(y, x, z)`` picks each plate's colour."""
    return [piece("plate2x4", y, x, z, colors(y, x, z)) for y in (0, 1) for x in (0, 4) for z in (0, 2)]


def test_one_colour_is_fully_coherent() -> None:
    c = coherence(slab(lambda y, x, z: RED))
    assert c.same_color == 1.0 and c.colors_per_window == 1.0 and c.largest_region == 1.0 and c.skin_colors == 1
    assert c.seams > 0 and c.top_windows > 0 and c.side_windows == 0  # sides are 2 plates tall: no 4 x 4 window


def test_a_checkerboard_of_parts_is_not() -> None:
    mottle = coherence(slab(lambda y, x, z: RED if (y + x // 4 + z // 2) % 2 else BLUE))
    layered = coherence(slab(lambda y, x, z: RED if y else BLUE))  # a blue base under a red top
    assert mottle.same_color == 0.0 and layered.same_color == pytest.approx(8 / 12)  # 4 + 4 in-layer, 4 across
    assert mottle.top_colors == 2.0 and layered.top_colors == 1.0
    assert mottle.largest_region < layered.largest_region < 1.0
    assert mottle.skin_colors == layered.skin_colors == 2


def test_seams_are_visible_pairs_only() -> None:
    # a 3 x 3 x 3 block of 1 x 1 plates: the centre one shows no face, so it is in no visible pair
    block = [piece("plate1x1", y, x, z, WHITE) for y in range(3) for x in range(3) for z in range(3)]
    c = coherence(block)
    assert c.skin_cells == 25  # not the centre, nor the cell under it (its only open face is on the ground)
    # top plane 12 pairs, each side 12; a pair along an edge shows on two planes: 4 top edges x 2, 4 side edges x 2
    assert c.seams == 12 + 4 * 12 - 8 - 8
    centre = next(i for i, p in enumerate(block) if (p.layer, p.x, p.z) == (1, 1, 1))
    faces = np.full((3, 3, 3), -1)
    faces[2] = np.arange(9).reshape(3, 3)  # the top faces of the top layer: 12 neighbouring pairs in the plane
    assert len(visible_pairs(faces, 0)) == 12 and centre not in {i for pair in visible_pairs(faces, 0) for i in pair}


def test_shuffled_keeps_placements_and_part_colour_counts() -> None:
    placed = slab(lambda y, x, z: RED if (y + x // 4 + z // 2) % 2 else BLUE) + [piece("plate1x2", 2, 0, 0, WHITE)]
    out = shuffled(placed, np.random.default_rng(0))
    assert [(p.shape, p.layer, p.x, p.z) for p in out] == [(p.shape, p.layer, p.x, p.z) for p in placed]
    count = lambda parts: Counter((p.shape.part.name, p.color.name) for p in parts)  # noqa: E731
    assert count(out) == count(placed) and out[-1].color == WHITE  # the only 1 x 2 keeps its colour
    assert shuffled(placed, np.random.default_rng(0)) == out  # seeded
