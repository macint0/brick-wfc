"""M12c: a scaled target cut into pieces by resampling is joined again (shapes.reconnect, scale_and_join)."""

import numpy as np
from scipy import ndimage

from brickwfc.bricks.shapes import reconnect, scale_and_join, scaled_to


def pieces(mask: np.ndarray) -> int:
    return ndimage.label(mask)[1]


def diagonal(layers: int = 1) -> np.ndarray:
    """Two cells (per layer) touching only at a corner: (z0, x0) and (z1, x1)."""
    mask = np.zeros((layers, 3, 3), dtype=bool)
    mask[:, 0, 0] = mask[:, 1, 1] = True
    return mask


def test_two_pieces_joined_by_one_cell_the_lowest_index() -> None:
    joined, added = reconnect(diagonal())
    assert pieces(diagonal()) == 2 and pieces(joined) == 1 and added == 1
    assert joined[0, 0, 1] and not joined[0, 1, 0]  # both (z0, x1) and (z1, x0) join; the lower index wins


def test_the_bridge_covers_every_layer_the_pieces_share() -> None:
    joined, added = reconnect(diagonal(layers=3))
    assert added == 3 and pieces(joined) == 1 and joined[:, 0, 1].all()


def test_the_fewest_cells_win() -> None:
    mask = diagonal(layers=3)
    mask[0, 0, 0] = mask[1, 0, 0] = False  # one piece is now a single cell at the top: one cell joins it there
    joined, added = reconnect(mask)
    assert added == 1 and pieces(joined) == 1


def test_one_piece_unchanged_and_far_pieces_left() -> None:
    solid = np.ones((2, 3, 4), dtype=bool)
    joined, added = reconnect(solid)
    assert added == 0 and joined.dtype == solid.dtype and (joined == solid).all()
    far = np.zeros((1, 1, 5), dtype=bool)
    far[0, 0, 0] = far[0, 0, 4] = True  # three cells apart: no single cell joins them
    joined, added = reconnect(far)
    assert added == 0 and (joined == far).all()


def test_several_pieces_and_determinism() -> None:
    mask = np.zeros((1, 4, 4), dtype=bool)
    mask[0, 0, 0] = mask[0, 1, 1] = mask[0, 2, 2] = mask[0, 3, 3] = True  # a diagonal of four pieces
    joined, added = reconnect(mask)
    assert pieces(joined) == 1 and added == 3
    again, _ = reconnect(mask)
    assert (again == joined).all() and not mask[0, 0, 1]  # the input is not changed


def test_scaling_a_one_piece_shape_is_unchanged_and_a_cut_one_is_joined() -> None:
    block = np.ones((4, 6, 6), dtype=bool)
    mask, added = scale_and_join(block, 1000)
    assert added == 0 and (scaled_to(block, 1000) == mask).all() and pieces(mask) == 1
    # an L of two bars meeting at a corner only: the scaled bars stay cut, and are joined
    corner = np.zeros((2, 8, 8), dtype=bool)
    corner[:, :4, 3] = True
    corner[:, 4, 4:] = True
    mask, added = scale_and_join(corner, 64)
    assert pieces(mask) == 1 and added > 0
