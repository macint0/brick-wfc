"""Post-hoc support checks on 3D builds, used as ground truth."""

from __future__ import annotations

import numpy as np


def floating_cells(filled: np.ndarray) -> np.ndarray:
    """Cells of a (Y, Z, X) occupancy grid that are filled, above layer 0, and have nothing directly below."""
    floating = np.zeros_like(filled)
    floating[1:] = filled[1:] & ~filled[:-1]
    return floating
