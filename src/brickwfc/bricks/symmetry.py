"""Mirror symmetry of target shapes and builds (M12b step 3).

A *mirror plane* is vertical, across the grid's x axis (axis 2) or z axis (axis 1), through the middle of the
mask's extent along it: cell coordinate ``c`` maps to ``total - c``, ``total`` being the sum of the lowest and
highest occupied coordinate. ``mirror_plane`` picks the axis whose reflection overlaps the mask most.

A part's mirror image is the same part, reflected: its cells reflected, and its orientation the one whose
cells, studded top cells and flat bottom cells are the reflected ones (a rectangle keeps its orientation, an L
corner or a slope facing along the axis turns). ``part_symmetry`` is the share of a build's parts whose mirror
image is also placed (a part on the plane can be its own mirror image), with or without the same color.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence

import numpy as np

from brickwfc.bricks.parts import PlacedPart, Shape, shapes_of

AXES = {1: "z", 2: "x"}
MIN_SCORE = 0.9  # a mask has a mirror plane if its reflection covers at least this share of it
# Symmetric decoding uses the best plane if its reflection covers at least this share of the target: the
# mirror image of a part is placed only where it lies inside the target, so a partly symmetric target (a
# chair's seat and back on a five-arm base, 0.7) is mirrored where it is symmetric.
DECODE_MIN_SCORE = 0.5
# A target this symmetric is made exactly symmetric (``alt.target``). A fitted threshold, with margins of about
# 0.02 on 9 (object, set) pairs (``results/m12b_symmetry_threshold.md``): after fillable sizing the car and table
# score 0.848-0.979, the chair (not symmetric: a five-arm base has no mirror plane) 0.708-0.806. It was 0.8 until
# fillable sizing lifted the 5891-1 chair to 0.806 (the step-3 comparison, ``results/m12b_skins.md``, used 0.8).
SYMMETRIZE_MIN_SCORE = 0.83


@dataclass(frozen=True)
class Plane:
    axis: int  # 1 (z) or 2 (x), in (Y, Z, X) grid indices
    total: int  # a coordinate c along ``axis`` reflects to total - c
    score: float  # |mask & reflected mask| / |mask|

    @property
    def name(self) -> str:
        return f"{AXES[self.axis]} = {self.total / 2:g}"


def reflected(mask: np.ndarray, plane: Plane) -> np.ndarray:
    """``mask`` reflected across ``plane`` (cells reflected outside the grid are dropped)."""
    n = mask.shape[plane.axis]
    index = plane.total - np.arange(n)
    inside = (index >= 0) & (index < n)
    out = np.zeros_like(mask)
    source = np.take(mask, index[inside], axis=plane.axis)
    destination = [slice(None)] * mask.ndim
    destination[plane.axis] = np.flatnonzero(inside)
    out[tuple(destination)] = source
    return out


def plane_on(mask: np.ndarray, axis: int) -> Plane:
    """The plane across ``axis`` through the middle of the mask's extent, with its overlap score."""
    occupied = np.flatnonzero(mask.any(axis=tuple(a for a in range(mask.ndim) if a != axis)))
    plane = Plane(axis, int(occupied[0] + occupied[-1]), 0.0)
    score = float((mask & reflected(mask, plane)).sum() / mask.sum())
    return Plane(axis, plane.total, score)


def best_plane(mask: np.ndarray) -> Plane:
    """The better of the two vertical planes through the middle of the mask's extent (any score)."""
    return max((plane_on(mask, axis) for axis in AXES), key=lambda p: p.score)


def mirror_plane(mask: np.ndarray, min_score: float = MIN_SCORE) -> Plane | None:
    """The best of the two vertical planes, or None if neither covers ``min_score`` of the mask."""
    if not mask.any():
        return None
    best = best_plane(mask)
    return best if best.score >= min_score else None


def _reflect_cells(cells: frozenset[tuple[int, int]], axis: int, size_z: int, size_x: int) -> frozenset:
    if axis == 2:
        return frozenset((dz, size_x - 1 - dx) for dz, dx in cells)
    return frozenset((size_z - 1 - dz, dx) for dz, dx in cells)


@lru_cache(maxsize=None)
def mirror_shape(shape: Shape, axis: int) -> Shape | None:
    """The orientation of the shape's part that is its mirror image across a plane on ``axis``, or None for
    a part with no such orientation (none in the catalog)."""
    g = shape.geometry
    want = tuple(_reflect_cells(frozenset(cells), axis, g.size_z, g.size_x)
                 for cells in (g.footprint, g.studded, g.seated))
    for other in shapes_of([shape.part]):
        h = other.geometry
        if (h.size_z, h.size_x) == (g.size_z, g.size_x) and (frozenset(h.footprint), h.studded, h.seated) == want:
            return other
    return None


def mirror_part(part: PlacedPart, plane: Plane) -> PlacedPart | None:
    """The part's mirror image across ``plane`` (same color), or None if its part has none."""
    shape = mirror_shape(part.shape, plane.axis)
    if shape is None:
        return None
    if plane.axis == 2:
        return PlacedPart(shape, part.color, part.layer, plane.total - (part.x + part.shape.size_x - 1), part.z)
    return PlacedPart(shape, part.color, part.layer, part.x, plane.total - (part.z + part.shape.size_z - 1))


def _key(part: PlacedPart, color: bool) -> tuple:
    g = part.shape.geometry
    return (part.shape.part.name, part.layer, part.x, part.z, g.footprint, g.studded,
            part.color.name if color else None)


@dataclass(frozen=True)
class Symmetry:
    parts: float  # share of parts whose mirror image (same part, any color) is placed
    parts_color: float  # ... in the same color
    cells: float  # the same as ``parts``, weighted by cells
    occupancy: float  # |filled & reflected filled| / |filled|: symmetry of the cells alone


def part_symmetry(placed: Sequence[PlacedPart], plane: Plane, shape: tuple[int, int, int]) -> Symmetry:
    if not placed:
        return Symmetry(float("nan"), float("nan"), float("nan"), float("nan"))
    keys = {color: {_key(p, color) for p in placed} for color in (False, True)}
    found = {color: [] for color in (False, True)}
    for part in placed:
        image = mirror_part(part, plane)
        for color in (False, True):
            found[color].append(image is not None and _key(image, color) in keys[color])
    cells = np.array([p.shape.cells for p in placed], dtype=float)
    filled = np.zeros(shape, dtype=bool)
    for part in placed:
        for cell in part.cells():
            filled[cell] = True
    return Symmetry(float(np.mean(found[False])), float(np.mean(found[True])),
                    float((cells * found[False]).sum() / cells.sum()),
                    float((filled & reflected(filled, plane)).sum() / filled.sum()))
