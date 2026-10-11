"""How coherent a build's colours look from outside (M12c): measured on the skin (``bricks.skin``: every cell face
open to the outside of the grid, the ground layer's bottom faces excepted).

- **same-colour seams**: the visible part pairs, two different parts whose skin faces lie side by side on one face
  plane (a seam the eye sees), and the share of them whose parts share a colour. Each pair counts once, however long
  its seam. Higher is more coherent.
- **colours per window**: over every ``patch`` x ``patch`` window of one plane of skin that is skin everywhere (as
  ``skin.patch_parts``, top and side planes), the mean number of distinct colours it shows. Lower is more coherent;
  1 is a single colour.
- **largest region**: the largest set of skin cells (cells with at least one skin face) of one colour connected
  across faces, as a share of all skin cells. Higher is more coherent. It depends on size (a large build has more
  room for a large region and more cells to share it with), so compare it at similar skin sizes.

``shuffled`` permutes the colours among the parts of each part type: the inventory's (part, colour) counts and every
placement stay, so it is the space a recolouring pass could search, and a random point in it is the null baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy import ndimage

from brickwfc.bricks.parts import PlacedPart
from brickwfc.bricks.skin import DOWN_STEP, PATCH, SIDE_STEPS, UP_STEP, exposed, exterior, owners, patch_parts


@dataclass(frozen=True)
class Coherence:
    seams: int  # visible part pairs
    same_color: float  # share of them whose two parts share a colour (nan: none)
    top_windows: int
    top_colors: float  # mean distinct colours per full top window (nan: none)
    side_windows: int
    side_colors: float  # the same over side windows
    colors_per_window: float  # over top and side windows together
    skin_cells: int
    largest_region: float  # largest one-colour connected set of skin cells / skin cells (nan: no skin)
    skin_colors: int  # distinct colours on the skin


def visible_pairs(owner_faces: np.ndarray, axis: int) -> set[tuple[int, int]]:
    """Pairs (i < j) of different parts whose faces (``owner_faces``: part index where a face is skin, -1 elsewhere,
    for faces pointing along ``axis``) lie next to each other within a plane perpendicular to ``axis``."""
    pairs: set[tuple[int, int]] = set()
    for along in {0, 1, 2} - {axis}:
        a = np.moveaxis(owner_faces, along, 0)[:-1]
        b = np.moveaxis(owner_faces, along, 0)[1:]
        seam = (a >= 0) & (b >= 0) & (a != b)
        pairs.update(zip(np.minimum(a[seam], b[seam]).tolist(), np.maximum(a[seam], b[seam]).tolist()))
    return pairs


def coherence(placed: Sequence[PlacedPart], shape: tuple[int, int, int] | None = None,
              patch: int = PATCH) -> Coherence:
    """The colour coherence of a build's skin on a (Y, Z, X) grid of ``shape`` (default: the parts' extent)."""
    if shape is None:
        cells = [cell for part in placed for cell in part.cells()]
        shape = tuple(max(c[i] for c in cells) + 1 for i in range(3)) if cells else (1, 1, 1)
    owner = owners(placed, shape)
    filled = owner >= 0
    outside = exterior(filled)
    names = sorted({p.color.name for p in placed})
    part_color = np.array([names.index(p.color.name) for p in placed] + [-1], dtype=np.int64)  # [-1]: empty
    color = part_color[owner]  # owner -1 picks the trailing -1
    pairs: set[tuple[int, int]] = set()
    tops: list[np.ndarray] = []
    sides: list[np.ndarray] = []
    on_skin = np.zeros(shape, dtype=bool)
    for step in (UP_STEP, DOWN_STEP, *SIDE_STEPS):
        mask = exposed(filled, outside, step)
        on_skin |= mask
        axis = int(np.flatnonzero(step)[0])
        pairs |= visible_pairs(np.where(mask, owner, -1), axis)
        if step == UP_STEP:
            tops.append(patch_parts(np.where(mask, color, -1), axis, patch))
        elif step != DOWN_STEP:
            sides.append(patch_parts(np.where(mask, color, -1), axis, patch))
    same = [part_color[i] == part_color[j] for i, j in pairs]
    top, side = np.concatenate(tops), np.concatenate(sides)
    both = np.concatenate([top, side])
    largest = 0
    for c in range(len(names)):
        labels, count = ndimage.label(on_skin & (color == c))
        if count:
            largest = max(largest, int(np.bincount(labels.ravel())[1:].max()))
    skin_cells = int(on_skin.sum())

    def mean(values: np.ndarray) -> float:
        return float(values.mean()) if len(values) else float("nan")

    return Coherence(len(pairs), float(np.mean(same)) if same else float("nan"), len(top), mean(top), len(side),
                     mean(side), mean(both), skin_cells, largest / skin_cells if skin_cells else float("nan"),
                     len(np.unique(color[on_skin])))


def shuffled(placed: Sequence[PlacedPart], rng: np.random.Generator) -> list[PlacedPart]:
    """``placed`` with the colours permuted among the parts of each part type (every placement and every (part,
    colour) count kept)."""
    out = list(placed)
    by_type: dict[str, list[int]] = {}
    for i, part in enumerate(placed):
        by_type.setdefault(part.shape.part.name, []).append(i)
    for indices in by_type.values():
        colors = [placed[i].color for i in indices]
        for i, k in zip(indices, rng.permutation(len(indices))):
            p = placed[i]
            out[i] = PlacedPart(p.shape, colors[k], p.layer, p.x, p.z)
    return out
