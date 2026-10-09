"""Post-hoc support checks on 3D builds. These are the ground truth the generators are scored against.

A part rests on what is directly below its bottom layer. It is supported if at least one cell below
its seated (flat-bottomed) cells holds a stud: the top of a plate or brick (a tile's top and a slope's
face are smooth and hold nothing).

With ``hanging=True`` (builds of the hole pass with ``hang``, M12b), a part may also hang from a part above by a
stud joint (its stud right under the other's seated cell): a part is supported if stud joints, followed in
either direction, join it to a part standing on the ground.
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
        for cell in part.stud_cells():
            studs[cell] = True
    return studs


def unsupported_parts(placed: list[PlacedPart], filled: np.ndarray, hanging: bool = False) -> list[PlacedPart]:
    """Parts above layer 0 with no stud directly below any seated cell of their bottom layer.

    If no part is unsupported, every part rests on the ground or on a part below it, so by
    induction every part is connected to the ground. With ``hanging``: the parts not joined to a part on
    the ground through stud joints (``stud_joints``).
    """
    studs = studded(placed, filled.shape)
    if not hanging:
        return [p for p in placed if p.layer > 0 and not any(studs[y - 1, z, x] for y, z, x in p.seated_cells())]
    neighbours: list[list[int]] = [[] for _ in placed]
    for upper, lower in stud_joints(placed):
        neighbours[upper].append(lower)
        neighbours[lower].append(upper)
    grounded = [i for i, p in enumerate(placed) if p.layer == 0]
    reached = set(grounded)
    while grounded:
        for j in neighbours[grounded.pop()]:
            if j not in reached:
                reached.add(j)
                grounded.append(j)
    return [p for i, p in enumerate(placed) if i not in reached]


def stud_joints(placed: list[PlacedPart]) -> set[tuple[int, int]]:
    """(upper, lower) indices into ``placed``: a seated cell of ``upper`` sits on a stud of ``lower``."""
    stud_owner = {cell: i for i, p in enumerate(placed) for cell in p.stud_cells()}
    return {(i, stud_owner[(y - 1, z, x)]) for i, p in enumerate(placed) for y, z, x in p.seated_cells()
            if (y - 1, z, x) in stud_owner}


def overhanging_parts(placed: list[PlacedPart], filled: np.ndarray) -> list[PlacedPart]:
    """Parts above layer 0 with at least one bottom cell over empty space (supported or not)."""
    return [p for p in placed if p.layer > 0 and any(not filled[y - 1, z, x] for y, z, x in p.bottom_cells())]


def is_stable(placed: list[PlacedPart], filled: np.ndarray, hanging: bool = False) -> bool:
    return not unsupported_parts(placed, filled, hanging)
