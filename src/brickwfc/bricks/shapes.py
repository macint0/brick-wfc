"""Target shapes (M11): boolean (Y, Z, X) masks a build must stay inside and should fill.

``ShapeConstraint`` keeps WFC's solid tiles inside the mask; adjacency propagation then keeps whole
parts inside it too (a part's continuation tile can't sit in a cell that must stay empty).
"""

from __future__ import annotations

import numpy as np

from brickwfc.bricks.parts import PartSet
from brickwfc.wfc import Cell, Wave

Mask = np.ndarray  # (Y, Z, X) bool


def block(ny: int, nz: int, nx: int) -> Mask:
    """Solid box filling the whole grid."""
    return np.ones((ny, nz, nx), dtype=bool)


def pyramid(ny: int, nz: int, nx: int) -> Mask:
    """Stepped pyramid: each layer shrinks by one stud on every side."""
    mask = np.zeros((ny, nz, nx), dtype=bool)
    for y in range(ny):
        if y < nz - y and y < nx - y:
            mask[y, y : nz - y, y : nx - y] = True
    return mask


def arch(ny: int, nz: int, nx: int, pillar: int = 2, span_layers: int = 2) -> Mask:
    """Two pillars at the x ends, joined by a span over the top ``span_layers`` layers."""
    mask = np.zeros((ny, nz, nx), dtype=bool)
    mask[:, :, :pillar] = True
    mask[:, :, nx - pillar :] = True
    mask[ny - span_layers :] = True
    return mask


def mushroom(ny: int, nz: int, nx: int, stem: int = 2, cap_layers: int = 2) -> Mask:
    """A ``stem`` x ``stem`` column in the middle with a full-width cap on top (large overhang)."""
    mask = np.zeros((ny, nz, nx), dtype=bool)
    z0, x0 = (nz - stem) // 2, (nx - stem) // 2
    mask[:, z0 : z0 + stem, x0 : x0 + stem] = True
    mask[ny - cap_layers :] = True
    return mask


def ring(ny: int, nz: int, nx: int, wall: int = 2) -> Mask:
    """Hollow square tower with walls ``wall`` studs thick."""
    mask = np.ones((ny, nz, nx), dtype=bool)
    mask[:, wall : nz - wall, wall : nx - wall] = False
    return mask


SHAPES = {f.__name__: f for f in (block, pyramid, arch, mushroom, ring)}


def scaled(name: str, ny: int, side: int) -> Mask:
    """Shape ``name`` on a ``side`` x ``side`` footprint; pillars and stems grow with the footprint
    (a quarter of its side, at least 2 studs), so an 8-stud footprint matches the defaults."""
    thick = max(2, side // 4)
    if name == "arch":
        return arch(ny, side, side, pillar=thick)
    if name == "mushroom":
        return mushroom(ny, side, side, stem=thick)
    return SHAPES[name](ny, side, side)


# Smallest footprint at which each scaled shape keeps its character (a gap under the arch, an
# overhang around the stem, a hole in the ring, more than one pyramid step).
MIN_SIDE = {"block": 2, "pyramid": 4, "arch": 6, "mushroom": 6, "ring": 6}


def sized_for(
    name: str, cells: float, heights: range = range(3, 9), preferred_height: int = 6, tolerance: float = 0.1
) -> Mask:
    """A ``scaled`` shape with volume close to ``cells``, over square footprints from ``MIN_SIDE`` up
    and the given heights (in plates). Among shapes within ``tolerance`` of ``cells`` (relative), the
    one closest to ``preferred_height`` wins, then the closest volume; if none is that close, the
    closest volume wins. A tiny ``cells`` gets the smallest shape, larger than asked."""
    best: tuple[bool, int, float, Mask] | None = None
    for ny in heights:
        side = MIN_SIDE[name]
        while True:
            mask = scaled(name, ny, side)
            error = abs(int(mask.sum()) - cells) / cells
            key = (error > tolerance, abs(ny - preferred_height) if error <= tolerance else 0, error)
            if best is None or key < best[:3]:
                best = (*key, mask)
            if mask.sum() >= cells:
                break
            side += 1
    return best[3]


def fill(filled: np.ndarray, mask: Mask) -> float:
    """Share of the shape's cells that are solid (1.0 = shape completely filled)."""
    return float((filled & mask).sum() / mask.sum())


def iou(filled: np.ndarray, mask: Mask) -> float:
    """Intersection over union of the solid cells and the shape (equals ``fill`` when nothing is outside)."""
    return float((filled & mask).sum() / (filled | mask).sum())


def outside(filled: np.ndarray, mask: Mask) -> int:
    """Number of solid cells outside the shape (0 for a valid build)."""
    return int((filled & ~mask).sum())


class ShapeConstraint:
    """Cells outside the mask may only be empty."""

    def __init__(self, parts: PartSet, mask: Mask) -> None:
        self.solid = parts.solid
        self.outside = ~mask

    def prune(self, wave: Wave, changed: set[Cell]) -> list[Cell] | None:
        domain = wave.domain
        offending = self.outside & (domain & self.solid).any(axis=-1)
        if not offending.any():
            return []
        domain[offending] &= ~self.solid
        if not domain[offending].any(axis=-1).all():
            return None
        return [tuple(int(i) for i in cell) for cell in np.argwhere(offending)]
