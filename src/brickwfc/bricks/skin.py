"""How clean a build's outer surface looks (M12b step 3): which parts show on the skin, and how fragmented it is.

The *skin* is every exposed cell face: a face of a filled cell whose neighbor across it is empty and connected
to the outside of the grid (an empty cell enclosed by the build, such as an unfilled pocket inside a target
shape, is not outside), except the bottom faces of the ground layer, which rest on the table. Each face
belongs to the part covering its cell. Measures:

- the share of skin faces on *small* parts (footprint of at most 2 cells: 1x1, 1x2, the 1x1 slopes), *long*
  parts (1 x n, n >= 3) and *wide* parts (at least 2 x 2 studs, a corner's L included);
- faces per visible part: skin faces / parts with at least one skin face (higher is cleaner);
- fragmentation: over every ``patch`` x ``patch`` window of one plane of skin that is skin everywhere (top
  faces of one layer; side faces of one column of cells), the mean number of distinct parts it shows. A
  window is in cells, so a side window is ``patch`` studs wide and ``patch`` plates (``patch`` / 3 bricks)
  tall. Lower is cleaner; 1 is a single part.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy import ndimage

from brickwfc.bricks.parts import PlacedPart, Shape

PATCH = 4
# Unit steps (dy, dz, dx): up, down, then the four sides.
UP_STEP, DOWN_STEP = (1, 0, 0), (-1, 0, 0)
SIDE_STEPS = ((0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
SIZE_CLASSES = ("small", "long", "wide")


def size_class(shape: Shape) -> str:
    """"small" (footprint of at most 2 cells), "wide" (at least 2 studs along both axes) or "long" (1 x n, n >= 3)."""
    if len(shape.footprint) <= 2:
        return "small"
    return "wide" if min(shape.size_x, shape.size_z) >= 2 else "long"


@dataclass(frozen=True)
class Skin:
    faces: int  # skin faces
    top_faces: int  # of which facing up
    share: dict[str, float]  # size class -> share of skin faces
    faces_per_part: float  # skin faces / parts showing at least one
    top_patch_parts: float  # mean distinct parts per full top window (nan: no window)
    top_patches: int
    side_patch_parts: float  # the same over side windows
    side_patches: int


def owners(placed: Sequence[PlacedPart], shape: tuple[int, int, int]) -> np.ndarray:
    """(Y, Z, X) index of the part covering each cell, -1 where empty."""
    owner = np.full(shape, -1, dtype=np.int64)
    for i, part in enumerate(placed):
        for cell in part.cells():
            owner[cell] = i
    return owner


def exterior(filled: np.ndarray) -> np.ndarray:
    """(Y, Z, X) bool: empty cells connected (across faces) to outside the grid."""
    padded = np.pad(~filled, 1, constant_values=True)
    labels, _ = ndimage.label(padded)
    return (labels == labels[0, 0, 0])[1:-1, 1:-1, 1:-1]


def exposed(filled: np.ndarray, outside: np.ndarray, step: tuple[int, int, int]) -> np.ndarray:
    """(Y, Z, X) bool: filled cells whose neighbor one ``step`` away is outside (or beyond the grid), except
    the ground layer's bottom faces."""
    padded = np.pad(outside, 1, constant_values=True)
    ny, nz, nx = filled.shape
    dy, dz, dx = step
    neighbor = padded[1 + dy : 1 + dy + ny, 1 + dz : 1 + dz + nz, 1 + dx : 1 + dx + nx]
    faces = filled & neighbor
    if step == DOWN_STEP:
        faces[0] = False
    return faces


def patch_parts(owner_faces: np.ndarray, axis: int, patch: int = PATCH) -> np.ndarray:
    """Distinct parts in each full ``patch`` x ``patch`` window of the planes of ``owner_faces`` (part index
    where a face is skin, -1 elsewhere) perpendicular to ``axis``; one value per full window."""
    planes = np.moveaxis(owner_faces, axis, 0)
    if planes.shape[1] < patch or planes.shape[2] < patch:
        return np.zeros(0, dtype=np.int64)
    windows = sliding_window_view(planes, (patch, patch), axis=(1, 2)).reshape(-1, patch * patch)
    windows = windows[(windows >= 0).all(axis=1)]
    if not len(windows):
        return np.zeros(0, dtype=np.int64)
    ordered = np.sort(windows, axis=1)
    return 1 + (np.diff(ordered, axis=1) != 0).sum(axis=1)


def skin(placed: Sequence[PlacedPart], shape: tuple[int, int, int] | None = None, patch: int = PATCH) -> Skin:
    """The skin measures of a build on a (Y, Z, X) grid of ``shape`` (default: the parts' extent)."""
    if shape is None:
        cells = [cell for part in placed for cell in part.cells()]
        shape = tuple(max(c[i] for c in cells) + 1 for i in range(3)) if cells else (1, 1, 1)
    owner = owners(placed, shape)
    filled = owner >= 0
    outside = exterior(filled)
    classes = np.array([SIZE_CLASSES.index(size_class(p.shape)) for p in placed], dtype=np.int64)
    counts = np.zeros(len(SIZE_CLASSES), dtype=np.int64)
    showing: set[int] = set()
    faces = top_faces = 0
    top_windows: list[np.ndarray] = []
    side_windows: list[np.ndarray] = []
    for step in (UP_STEP, DOWN_STEP, *SIDE_STEPS):
        mask = exposed(filled, outside, step)
        on = owner[mask]
        faces += len(on)
        counts += np.bincount(classes[on], minlength=len(SIZE_CLASSES))
        showing.update(np.unique(on).tolist())
        axis = int(np.flatnonzero(step)[0])
        if step == UP_STEP:
            top_faces = len(on)
            top_windows.append(patch_parts(np.where(mask, owner, -1), axis, patch))
        elif step != DOWN_STEP:
            side_windows.append(patch_parts(np.where(mask, owner, -1), axis, patch))
    tops, sides = np.concatenate(top_windows), np.concatenate(side_windows)
    share = {name: float(counts[i] / faces) if faces else float("nan") for i, name in enumerate(SIZE_CLASSES)}
    return Skin(faces, top_faces, share, faces / len(showing) if showing else float("nan"),
                float(tops.mean()) if len(tops) else float("nan"), len(tops),
                float(sides.mean()) if len(sides) else float("nan"), len(sides))
