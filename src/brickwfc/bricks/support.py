"""Post-hoc support checks on 3D builds. These are the ground truth the generators are scored against."""

from __future__ import annotations

import numpy as np

from brickwfc.bricks.parts import PlacedPart


def floating_cells(filled: np.ndarray) -> np.ndarray:
    """Cells of a (Y, Z, X) occupancy grid that are filled, above layer 0, and have nothing directly below."""
    floating = np.zeros_like(filled)
    floating[1:] = filled[1:] & ~filled[:-1]
    return floating


def unsupported_parts(placed: list[PlacedPart], filled: np.ndarray) -> list[PlacedPart]:
    """Parts above layer 0 that overlap no filled cell directly below any of their studs.

    If no part is unsupported, every part rests on the ground or on a part below it, so by
    induction every part is connected to the ground.
    """
    return [p for p in placed if p.layer > 0 and not any(filled[y - 1, z, x] for y, z, x in p.cells())]


def overhanging_parts(placed: list[PlacedPart], filled: np.ndarray) -> list[PlacedPart]:
    """Parts above layer 0 with at least one stud over empty space (supported or not)."""
    return [p for p in placed if p.layer > 0 and any(not filled[y - 1, z, x] for y, z, x in p.cells())]


def is_stable(placed: list[PlacedPart], filled: np.ndarray) -> bool:
    return not unsupported_parts(placed, filled)
