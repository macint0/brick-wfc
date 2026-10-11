"""Target shapes (M11): boolean (Y, Z, X) masks a build must stay inside and should fill.

``ShapeConstraint`` keeps WFC's solid tiles inside the mask; adjacency propagation then keeps whole
parts inside it too (a part's continuation tile can't sit in a cell that must stay empty).

Besides the primitives, shapes come from a top-down silhouette image (optionally with a height map),
or from a voxelized model, rescaled to a target volume (M12), or from any 3D mask (M12b: ``scaled_to``);
``preferred_colors`` reads a color image aligned with the silhouette.
"""

from __future__ import annotations

import functools
import math
from typing import Callable, Sequence

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial import ConvexHull

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


SECTION_BAND = 0.05  # thin-aware scaling: volumes within 5% of the target count as fitting


def thinnest_section(mask: Mask) -> int:
    """The smallest 4-connected region of any layer of ``mask``, in cells (0 if the mask is empty). An empty layer
    between the lowest and the highest filled layer is a section of 0 cells: the shape is cut in two there (M12b
    completeness: resampling can drop a thin post entirely, and skipping its empty layers scored that as thick)."""
    filled = np.nonzero(mask.any(axis=(1, 2)))[0]
    if len(filled) == 0 or len(filled) < filled[-1] - filled[0] + 1:
        return 0
    sizes = []
    for layer in mask[filled[0]:filled[-1] + 1]:
        labels, regions = ndimage.label(layer)
        sizes.append(int(np.bincount(labels.ravel())[1:].min()))
    return min(sizes)


def _hull_distance(points: np.ndarray, z: float, x: float) -> float:
    """Distance from (z, x) to the convex hull of ``points`` ((n, 2) of z, x; 0 inside)."""
    hull = ConvexHull(points)
    if (hull.equations @ np.array([z, x, 1.0]) <= 1e-9).all():
        return 0.0
    best = math.inf
    for a, b in points[hull.simplices]:
        t = np.clip(np.dot((z, x) - a, b - a) / np.dot(b - a, b - a), 0.0, 1.0)
        best = min(best, float(np.hypot(*((z, x) - (a + t * (b - a))))))
    return best


def overhang_moment(mask: Mask) -> float:
    """The largest moment a horizontal section of ``mask`` holds off its footprint: per layer and per piece of the
    shape at and above it (6-connected), the cells of the piece above the layer times the horizontal distance of
    their centre of mass from the convex hull of the piece's cells in the layer (0 over it). A part resting there
    holds that moment by clutch alone (M12b completeness: at 0.9 of the 5891-1 chair's volume, resampling put its
    1 x 2 post 1.2 studs off the seat's centre of mass; 47 of 50 builds needed more than real clutch). The largest
    rather than the sum, since the clutch a build needs is its worst joint's, and a post carries the same moment
    through every layer."""
    best = 0.0
    for y in np.nonzero(mask.any(axis=(1, 2)))[0]:
        pieces, _ = ndimage.label(mask[y:])
        for piece in np.unique(pieces[0][mask[y]]):
            above = np.argwhere(pieces[1:] == piece)
            if not len(above):
                continue
            zs, xs = np.nonzero(pieces[0] == piece)
            corners = np.concatenate([np.stack([zs + dz, xs + dx], axis=1) for dz in (0, 1) for dx in (0, 1)])
            lever = _hull_distance(corners.astype(float), above[:, 1].mean() + 0.5, above[:, 2].mean() + 0.5)
            best = max(best, len(above) * lever)
    return best

def fit_scale(volume: Callable[[float], int], cells: float, dims: int, steps: int = 121,
              section: Callable[[float], int] | None = None, band: float = SECTION_BAND,
              moment: Callable[[float], float] | None = None) -> float:
    """The factor ``f`` near (cells / volume(1)) ** (1 / dims) whose ``volume(f)`` is closest to ``cells``. With
    ``section`` (f -> the thinnest horizontal section of the scaled shape, ``thinnest_section``), among the factors
    whose volume is within ``band`` of ``cells`` (relative), the one with the thickest thinnest section, ties by
    the closest volume (M12b sizing: nearest-neighbour resampling thins a part unevenly, e.g. a chair's post from
    8 cells to 3 between factors 2% apart). If no factor in the band keeps the shape whole (all cut it: section
    0), the band is widened once to ``2 * band`` (M12b completeness: a chair's 2-cell post vanished at some volumes).
    Without a factor in either band, the closest volume. With ``moment`` (f -> ``overhang_moment`` of the scaled
    shape), among the thickest, the one with the smallest moment, then the closest volume (M12b completeness:
    resampling moves a thin post under or off the load it carries)."""
    estimate = (cells / volume(1.0)) ** (1 / dims)
    factors = [float(f) for f in estimate * np.exp(np.linspace(-0.3, 0.3, steps))]
    errors = [abs(volume(f) - cells) for f in factors]
    best = int(np.argmin(errors))
    if section is not None:
        sections: dict[int, int] = {}
        moments: dict[int, float] = {}

        def thickest(width: float) -> int | None:
            fitting = [i for i, error in enumerate(errors) if error <= width * cells]
            for i in fitting:
                if i not in sections:
                    sections[i] = section(factors[i])
            if moment is not None:
                thick = max((sections[i] for i in fitting), default=0)
                for i in fitting:
                    if sections[i] == thick and i not in moments:
                        moments[i] = moment(factors[i])
            return max(fitting, key=lambda i: (sections[i], -moments.get(i, 0.0), -errors[i], -i), default=None)

        found = thickest(band)
        if found is None or sections[found] == 0:
            wider = thickest(2 * band)
            if wider is not None and sections[wider] > 0:
                found = wider
        if found is not None:
            best = found
    return factors[best]


def from_heights(heights: np.ndarray, cells: float, scale_height: bool) -> tuple[Mask, float]:
    """Extruded columns scaled so the volume is about ``cells``: the footprint by ``f`` and, with
    ``scale_height``, the heights too (shape kept); else only the footprint. Returns (mask, f); the mask
    covers the whole resampled footprint (cut it with ``bounds``)."""
    def scaled_heights(f: float) -> np.ndarray:
        h = resample(heights, (f, f))
        return np.where(h > 0, np.maximum(np.round(h * f), 1), 0).astype(np.int64) if scale_height else h

    f = fit_scale(lambda f: int(scaled_heights(f).sum()), cells, 3 if scale_height else 2)
    return extrude(scaled_heights(f)), f


def model_occupancy(placed: Sequence[PlacedPart]) -> Mask:
    """The cells of a (voxelized) model's parts on the grid of its extent."""
    shape = tuple(max(c[i] for p in placed for c in p.cells()) + 1 for i in range(3))
    occupied = np.zeros(shape, dtype=bool)
    for part in placed:
        for cell in part.cells():
            occupied[cell] = True
    return occupied


def from_model(placed: Sequence[PlacedPart], cells: float, solid_columns: bool = True, shell: int = 0,
               keep_sections: bool = False) -> Mask:
    """The cells of a (voxelized) model, scaled uniformly so the volume is about ``cells``. With
    ``solid_columns``, each column is filled from the ground to its top cell first: the model's massing
    rather than its exact cells (a voxelized model keeps only the catalog parts on the stud grid, so its
    cells are a sparse, partial view)."""
    return scaled_to(model_occupancy(placed), cells, solid_columns, shell, keep_sections)


def reconnect(mask: Mask) -> tuple[Mask, int]:
    """``mask`` made one piece across faces where one empty cell per layer can join two pieces, and the cells added.

    Nearest-neighbour resampling can cut a thin diagonal feature (a chair's caster arm, whose rows touch the hub
    only at a corner) into a separate piece that connected growth cannot reach and that no build can join
    (results/m12c_stall_6378_chair.md). While the mask has more than one piece: every empty cell that touches two
    pieces across faces is a candidate; candidates in one column (z, x) joining the same two pieces form a bridge,
    added in every layer of it (a joint as tall as the contact); the bridge with the fewest cells is added, ties
    by the lowest index of its first cell. Pieces no single cell can join stay as they are. A mask that is one
    piece is returned unchanged."""
    mask = mask.copy()
    added = 0
    steps = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
    while True:
        labels, count = ndimage.label(mask)
        if count <= 1:
            return mask, added
        padded = np.pad(labels, 1)
        ny, nz, nx = mask.shape
        touched = np.stack([padded[1 + dy:1 + dy + ny, 1 + dz:1 + dz + nz, 1 + dx:1 + dx + nx]
                            for dy, dz, dx in steps])
        low = np.where(touched > 0, touched, count + 1).min(axis=0)
        high = touched.max(axis=0)
        joining = ~mask & (high > 0) & (low < high)
        if not joining.any():
            return mask, added
        bridges: dict[tuple[int, int, int, int], list[int]] = {}
        for y, z, x in np.argwhere(joining).tolist():  # in index order
            bridges.setdefault((z, x, int(low[y, z, x]), int(high[y, z, x])), []).append(y)
        (z, x, _, _), layers = min(bridges.items(), key=lambda item: (
            len(item[1]), int(np.ravel_multi_index((item[1][0], item[0][0], item[0][1]), mask.shape))))
        mask[layers, z, x] = True
        added += len(layers)


def scaled_to(occupied: Mask, cells: float, solid_columns: bool = False, shell: int = 0,
              keep_sections: bool = False) -> Mask:
    """A 3D mask in cells (1 stud x 1 stud x 1 plate), scaled uniformly so the volume is about ``cells``
    and cut to its bounds (``scale_and_join``)."""
    return scale_and_join(occupied, cells, solid_columns, shell, keep_sections)[0]


def scale_and_join(occupied: Mask, cells: float, solid_columns: bool = False, shell: int = 0,
                   keep_sections: bool = False) -> tuple[Mask, int]:
    """A 3D mask in cells (1 stud x 1 stud x 1 plate), scaled uniformly so the volume is about ``cells``
    and cut to its bounds, and the cells added to keep it one piece; with ``solid_columns``, each column filled
    from the ground to its top cell first; with ``shell`` > 0, hollowed after scaling (``hollow``), so the same
    volume makes a larger object. With ``keep_sections``, the scale keeps thin parts thick and under the load they
    carry (``fit_scale`` with ``thinnest_section`` and ``overhang_moment`` of the unhollowed shape). The scaled
    solid is joined into one piece (``reconnect``, M12c) before it is hollowed; the scale is fitted before that,
    on the resampled volume."""
    if solid_columns:
        occupied = extrude(np.round(height_map_of(occupied)).astype(np.int64))

    def at(f: float) -> Mask:
        mask = resample(occupied, (f, f, f))
        return hollow(mask, shell) if shell else mask

    # A shell's volume grows with its surface, about f ** 2.
    solid = functools.lru_cache(maxsize=None)(lambda f: resample(occupied, (f, f, f)))
    section = (lambda f: thinnest_section(solid(f))) if keep_sections else None
    moment = (lambda f: overhang_moment(solid(f))) if keep_sections else None
    f = fit_scale(lambda f: int(at(f).sum()), cells, 2 if shell else 3, section=section, moment=moment)
    mask, added = reconnect(solid(f))
    if shell:
        mask = hollow(mask, shell)
    return mask[bounds(mask)], added


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


SUPPORT_REACH = 3  # supports: overhang cells farther than this from a held cell get a column under them


def with_supports(mask: Mask, reach: int = SUPPORT_REACH, width: int = SUPPORT_WIDTH, max_height: int = 0) -> Mask:
    """``mask`` plus support columns outside it (M12b step 1d). On each layer, an overhang cell (nothing of
    the mask below it) more than ``reach`` studs (chessboard distance) from every held cell (mask below) is
    out of reach of a part cantilevered from the held cells. Columns cover them one at a time: while such a far
    cell is left, a ``width`` x ``width`` column goes under the farthest one (ties: the first in row-major order;
    clipped to the layer's overhang cells), and counts as held for the next. Each column goes down to the next
    mask cell or the ground. A small overhang (a chair's hub) gets one column under its middle, a long one (a
    large chair's caster arms, a car's floor) as many as it needs, at every scale (M12b sizing; a fixed lattice
    put 1 to 72 cells under the same chair depending on its scale). The columns are extra cells, not part of the
    object: measure fill and IoU against ``mask``. With ``max_height`` > 0, only cells with a drop of at most
    that many cells get columns: short legs under low overhangs, not towers under a table top that would use
    up the inventory."""
    result = mask.copy()
    _, nz, nx = mask.shape
    for y in range(1, mask.shape[0]):
        over = mask[y] & ~mask[y - 1]
        if not over.any():
            continue
        held = mask[y] & mask[y - 1]
        eligible = over.copy()
        if max_height:
            empty = np.cumprod(~mask[y - 1::-1], axis=0)  # cells straight below, until the mask
            eligible &= empty.sum(axis=0) <= max_height
        column = np.zeros_like(over)
        while True:
            distance = (np.full(over.shape, nz + nx) if not held.any()
                        else ndimage.distance_transform_cdt(~held, metric="chessboard"))
            far = eligible & (distance > reach)
            if not far.any():
                break
            z, x = np.unravel_index(int(np.argmax(np.where(far, distance, -1))), over.shape)
            z0, x0 = min(max(z - (width - 1) // 2, 0), nz - width), min(max(x - (width - 1) // 2, 0), nx - width)
            block = np.zeros_like(over)
            block[z0:z0 + width, x0:x0 + width] = True
            block &= over
            column |= block
            held = held | block
        if max_height:
            empty = np.cumprod(~mask[y - 1::-1], axis=0)  # cells straight below, until the mask
            column &= empty.sum(axis=0) <= max_height
        for below in range(y - 1, -1, -1):
            column = column & ~mask[below]
            if not column.any():
                break
            result[below] |= column
    return result


def unsupported_empty(filled: np.ndarray, mask: Mask) -> Mask:
    """Cells of ``mask`` the build leaves empty with nothing built directly below them (above the ground):
    the overhang loss, cells no part could rest on."""
    below = np.zeros_like(filled)
    below[1:] = filled[:-1]
    below[0] = True
    return mask & ~filled & ~below


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
