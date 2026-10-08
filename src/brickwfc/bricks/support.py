"""Post-hoc support checks on 3D builds. These are the ground truth the generators are scored against.

A part rests on what is directly below its bottom layer. It is supported if at least one cell below
its bottom holds a stud: the top of a plate or brick (a tile's top is smooth and holds nothing).
"""

from __future__ import annotations

import numpy as np

from brickwfc.bricks.parts import PlacedPart


def floating_cells(filled: np.ndarray) -> np.ndarray:
    """Cells of a (Y, Z, X) occupancy grid that are filled, above layer 0, and have nothing directly below."""
    floating = np.zeros_like(filled)
    floating[1:] = filled[1:] & ~filled[:-1]
    return floating


def studded(placed: list[PlacedPart], shape: tuple[int, ...]) -> np.ndarray:
    """(Y, Z, X) bool: cells on a part's top layer that carry a stud."""
    studs = np.zeros(shape, dtype=bool)
    for part in placed:
        if part.shape.part.studs:
            for cell in part.top_cells():
                studs[cell] = True
    return studs


def unsupported_parts(placed: list[PlacedPart], filled: np.ndarray) -> list[PlacedPart]:
    """Parts above layer 0 with no stud directly below any cell of their bottom layer.

    If no part is unsupported, every part rests on the ground or on a part below it, so by
    induction every part is connected to the ground.
    """
    studs = studded(placed, filled.shape)
    return [p for p in placed if p.layer > 0 and not any(studs[y - 1, z, x] for y, z, x in p.bottom_cells())]


def overhanging_parts(placed: list[PlacedPart], filled: np.ndarray) -> list[PlacedPart]:
    """Parts above layer 0 with at least one bottom cell over empty space (supported or not)."""
    return [p for p in placed if p.layer > 0 and any(not filled[y - 1, z, x] for y, z, x in p.bottom_cells())]


def is_stable(placed: list[PlacedPart], filled: np.ndarray) -> bool:
    return not unsupported_parts(placed, filled)
