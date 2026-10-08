"""Target shapes (M11): boolean (Y, Z, X) masks a build must stay inside and should fill.

``ShapeConstraint`` keeps WFC's solid tiles inside the mask; adjacency propagation then keeps whole
parts inside it too (a part's continuation tile can't sit in a cell that must stay empty).

Besides the primitives, shapes come from a top-down silhouette image (optionally with a height map),
or from a voxelized model, rescaled to a target volume (M12), or from any 3D mask (M12b: ``scaled_to``);
``preferred_colors`` reads a color image aligned with the silhouette.
"""

from __future__ import annotations

from typing import Callable, Sequence

import numpy as np
from PIL import Image
from scipy import ndimage

from brickwfc.bricks.colors import BrickColor
from brickwfc.bricks.parts import PartSet, PlacedPart
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


# Shapes from images and models (M12) ------------------------------------------------------------------


def inside_pixels(image: Image.Image) -> np.ndarray:
    """(rows, columns) bool: the opaque pixels of an image with transparency, else the dark ones
    (luminance < 128, a dark silhouette on a light background)."""
    if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
        alpha = np.asarray(image.convert("RGBA"))[..., 3]
        if (alpha < 255).any():
            return alpha >= 128
    return np.asarray(image.convert("L")) < 128


def column_heights(silhouette: Image.Image, heights: Image.Image | None = None, height: int = 6) -> np.ndarray:
    """(Z, X) column heights in plates from a top-down silhouette (one pixel per stud, rows along z):
    ``height`` everywhere inside it, or the grey value of ``heights`` (same size; at least 1 inside)."""
    inside = inside_pixels(silhouette)
    if heights is None:
        return np.where(inside, height, 0)
    grey = np.asarray(heights.convert("L")).astype(np.int64)
    if grey.shape != inside.shape:
        raise ValueError(f"height map is {grey.shape[::-1]} pixels, silhouette {inside.shape[::-1]}")
    return np.where(inside, np.maximum(grey, 1), 0)


def height_map_of(mask: Mask) -> np.ndarray:
    """(Z, X) number of layers from the ground to each column's top cell (0 for an empty column)."""
    ny = mask.shape[0]
    return np.where(mask.any(axis=0), ny - np.argmax(mask[::-1], axis=0), 0)


def extrude(heights: np.ndarray) -> Mask:
    """Mask of columns standing on the ground, ``heights`` (Z, X) plates tall."""
    layers = np.arange(max(int(heights.max()), 1))[:, None, None]
    return layers < heights[None]


def resample(array: np.ndarray, factors: tuple[float, ...]) -> np.ndarray:
    """Nearest-neighbor rescale of ``array``'s leading axes by ``factors`` (each axis at least 1 long)."""
    for axis, factor in enumerate(factors):
        n = array.shape[axis]
        size = max(1, round(n * factor))
        index = np.minimum((np.arange(size) / factor).astype(np.int64), n - 1)
        array = np.take(array, index, axis=axis)
    return array


def bounds(mask: Mask) -> tuple[slice, slice, slice]:
    """Layers 0 .. top filled layer (layer 0 stays the ground), and the z and x range of the filled cells."""
    ys, zs, xs = (np.nonzero(mask.any(axis=other))[0] for other in ((1, 2), (0, 2), (0, 1)))
    return slice(0, ys.max() + 1), slice(zs.min(), zs.max() + 1), slice(xs.min(), xs.max() + 1)


def fit_scale(volume: Callable[[float], int], cells: float, dims: int, steps: int = 121) -> float:
    """The factor ``f`` near (cells / volume(1)) ** (1 / dims) whose ``volume(f)`` is closest to ``cells``."""
    estimate = (cells / volume(1.0)) ** (1 / dims)
    factors = estimate * np.exp(np.linspace(-0.3, 0.3, steps))
    errors = [abs(volume(float(f)) - cells) for f in factors]
    return float(factors[int(np.argmin(errors))])


def from_heights(heights: np.ndarray, cells: float, scale_height: bool) -> tuple[Mask, float]:
    """Extruded columns scaled so the volume is about ``cells``: the footprint by ``f`` and, with
    ``scale_height``, the heights too (shape kept); else only the footprint. Returns (mask, f); the mask
    covers the whole resampled footprint (cut it with ``bounds``)."""
    def scaled_heights(f: float) -> np.ndarray:
        h = resample(heights, (f, f))
        return np.where(h > 0, np.maximum(np.round(h * f), 1), 0).astype(np.int64) if scale_height else h

    f = fit_scale(lambda f: int(scaled_heights(f).sum()), cells, 3 if scale_height else 2)
    return extrude(scaled_heights(f)), f


def from_model(placed: Sequence[PlacedPart], cells: float, solid_columns: bool = True, shell: int = 0) -> Mask:
    """The cells of a (voxelized) model, scaled uniformly so the volume is about ``cells``. With
    ``solid_columns``, each column is filled from the ground to its top cell first: the model's massing
    rather than its exact cells (a voxelized model keeps only the catalog parts on the stud grid, so its
    cells are a sparse, partial view)."""
    shape = tuple(max(c[i] for p in placed for c in p.cells()) + 1 for i in range(3))
    occupied = np.zeros(shape, dtype=bool)
    for part in placed:
        for cell in part.cells():
            occupied[cell] = True
    return scaled_to(occupied, cells, solid_columns, shell)


def scaled_to(occupied: Mask, cells: float, solid_columns: bool = False, shell: int = 0) -> Mask:
    """A 3D mask in cells (1 stud x 1 stud x 1 plate), scaled uniformly so the volume is about ``cells``
    and cut to its bounds; with ``solid_columns``, each column filled from the ground to its top cell first;
    with ``shell`` > 0, hollowed after scaling (``hollow``), so the same volume makes a larger object."""
    if solid_columns:
        occupied = extrude(np.round(height_map_of(occupied)).astype(np.int64))

    def at(f: float) -> Mask:
        mask = resample(occupied, (f, f, f))
        return hollow(mask, shell) if shell else mask

    # A shell's volume grows with its surface, about f ** 2.
    f = fit_scale(lambda f: int(at(f).sum()), cells, 2 if shell else 3)
    mask = at(f)
    return mask[bounds(mask)]


SUPPORT_PERIOD, SUPPORT_WIDTH = 4, 2  # hollow: 2 x 2-stud pillars every 4 studs


def hollow(mask: Mask, thickness: int, period: int = SUPPORT_PERIOD, width: int = SUPPORT_WIDTH) -> Mask:
    """The shell of ``mask`` (its cells within ``thickness`` face steps of the outside or the grid's
    border) plus internal supports: under every shell cell over the hollow interior, on a lattice of
    ``width`` x ``width``-stud pillars every ``period`` studs, a column down through the interior to the
    next shell cell or the ground. Between pillars the shell spans ``period - width`` studs."""
    interior = ndimage.binary_erosion(mask, iterations=thickness) if thickness > 0 else np.zeros_like(mask)
    result = mask & ~interior
    _, nz, nx = mask.shape
    lattice = (np.arange(nz)[:, None] % period < width) & (np.arange(nx)[None, :] % period < width)
    for y in range(mask.shape[0] - 1, 0, -1):
        result[y - 1] |= result[y] & interior[y - 1] & lattice
    return result


def preferred_colors(image: Image.Image, colors: Sequence[BrickColor]) -> np.ndarray:
    """(Z, X) name of the color in ``colors`` nearest (RGB distance) to each pixel; "" where transparent."""
    rgba = np.asarray(image.convert("RGBA")).astype(np.float64)
    palette = np.array([c.rgb for c in colors], dtype=np.float64)
    nearest = np.argmin(((rgba[..., None, :3] - palette) ** 2).sum(axis=-1), axis=-1)
    names = np.array([c.name for c in colors], dtype=object)[nearest]
    return np.where(rgba[..., 3] >= 128, names, "")


def surface(mask: Mask) -> Mask:
    """The cells of ``mask`` on its outer surface: next to the outside (or the grid's border) across a face.
    Enclosed voids (a hollowed shape's inside) do not count as outside."""
    solid = ndimage.binary_fill_holes(mask)
    return mask & ~ndimage.binary_erosion(solid)


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
