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


def fill(filled: np.ndarray, mask: Mask) -> float:
    """Share of the shape's cells that are solid (1.0 = shape completely filled)."""
    return float((filled & mask).sum() / mask.sum())


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
