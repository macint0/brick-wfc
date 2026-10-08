"""Isometric preview of a 3D voxel build (a quick look without opening an LDraw viewer)."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw

from brickwfc.tileset import RGB

# Face shades for a light from above/front-left.
TOP_SHADE, EAST_SHADE, SOUTH_SHADE = 1.0, 0.78, 0.62
PLATE_ASPECT = 8 / 20  # plate height / stud width
RISE = PLATE_ASPECT * 1.2  # screen height of one plate layer, in stud widths
# A sloped top (M12b) is shaded by how much it turns toward the light, which comes from above the east side.
LIGHT = np.array([0.5, 1.0, 0.25]) / np.linalg.norm([0.5, 1.0, 0.25])  # (x, up, z), stud units
# Toward the viewer, who sees the build from above its south-east corner: (x, up, z) in stud units.
VIEW = np.array([1.0, PLATE_ASPECT / RISE, 1.0])
SQUARE = ((0, 0), (1, 0), (1, 1), (0, 1))  # a cell's corners (x, z), the order of ``tops``/``bottoms``

Point = tuple[float, float, float]  # (u, v, value): position in a cell's square, a plane's height there


def shade(rgb: RGB, factor: float) -> RGB:
    return tuple(int(round(c * factor)) for c in rgb)


def face_shade(t: Sequence[float]) -> float | None:
    """Shade, relative to a flat top, of a plane with heights ``t`` (plates) at a cell's corners; None if it
    turns away from the viewer (it is then hidden by the part)."""
    gx = (t[1] - t[0]) * PLATE_ASPECT  # rise per stud along x, in studs
    gz = (t[3] - t[0]) * PLATE_ASPECT
    normal = np.array([-gx, 1.0, -gz])
    normal /= np.linalg.norm(normal)
    if normal @ VIEW <= 0:
        return None
    return float(np.clip((normal @ LIGHT) / LIGHT[1], 0.5, 1.15))


def clip(polygon: list[Point], keep_above: float | None = None, keep_below: float | None = None) -> list[Point]:
    """Sutherland-Hodgman: the part of a convex polygon where the (linear) value is >= ``keep_above`` or
    <= ``keep_below``."""
    def inside(p: Point) -> bool:
        return p[2] >= keep_above if keep_above is not None else p[2] <= keep_below

    level = keep_above if keep_above is not None else keep_below
    out: list[Point] = []
    for i, p in enumerate(polygon):
        q = polygon[(i + 1) % len(polygon)]
        if inside(p):
            out.append(p)
        if inside(p) != inside(q):
            s = (level - p[2]) / (q[2] - p[2])
            out.append((p[0] + s * (q[0] - p[0]), p[1] + s * (q[1] - p[1]), level))
    return out


def profile(a: float, b: float, extra: Sequence[float] = ()) -> list[float]:
    """Positions along an edge (0..1) where a linear value from ``a`` to ``b`` crosses 0 or 1, plus the ends."""
    points = {0.0, 1.0, *extra}
    for level in (0.0, 1.0):
        if (a - level) * (b - level) < 0:
            points.add((level - a) / (b - a))
    return sorted(points)


def area(points: Sequence[tuple[float, float]]) -> float:
    """Area of a polygon (shoelace)."""
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, [*points[1:], points[0]]))) / 2


def render_voxels(
    filled: np.ndarray, colors: np.ndarray, stud: int = 14, background: RGB = (255, 255, 255),
    studs: np.ndarray | None = None, tops: np.ndarray | None = None, bottoms: np.ndarray | None = None,
) -> Image.Image:
    """Draw a (Y, Z, X) build seen from above its south-east corner.

    ``colors`` is (Y, Z, X, 3) uint8. Only exposed faces are drawn, back to front, and each
    exposed top face gets a stud, except where ``studs`` (Y, Z, X bool, if given) is False (tiles).

    ``tops`` and ``bottoms`` (Y, Z, X, 4, if given; M12b) cut cells along a slope: the heights, in plates from
    the cell's bottom, of a plane above (tops) or below (bottoms) which the cell is empty, at its corners
    (x, z), (x + 1, z), (x + 1, z + 1), (x, z + 1). Values may lie outside 0..1 (the plane passes above or
    below the cell); a full cell has top 1 and bottom 0. A cut cell's sloped top is drawn as a shaded face
    (if it faces the viewer) and its sides follow the planes. Without them every cell is a full box.
    """
    ny, nz, nx = filled.shape
    half = stud / 2
    rise = stud * RISE
    one, zero = (1.0, 1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 0.0)

    def project(x: float, z: float, y: float) -> tuple[float, float]:
        return ((x - z) * stud, (x + z) * half - y * rise)

    # Canvas bounds from the projected corners of the whole grid.
    corners = [project(x, z, y) for x in (0, nx) for z in (0, nz) for y in (0, ny + 1)]
    min_x = min(p[0] for p in corners) - stud
    min_y = min(p[1] for p in corners) - stud
    width = int(max(p[0] for p in corners) - min_x + stud)
    height = int(max(p[1] for p in corners) - min_y + stud)
    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)

    def screen(x: float, z: float, y: float) -> tuple[float, float]:
        sx, sy = project(x, z, y)
        return (sx - min_x, sy - min_y)

    def planes(y: int, z: int, x: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
        t = one if tops is None else tuple(float(v) for v in tops[y, z, x])
        b = zero if bottoms is None else tuple(float(v) for v in bottoms[y, z, x])
        return t, b

    def opens(y: int, z: int, x: int, side: Sequence[int]) -> bool:
        """Whether cell (y, z, x) leaves open its side face made of the corners ``side`` (so the neighbor's
        face toward it shows)."""
        if not (y < ny and z < nz and x < nx) or not filled[y, z, x]:
            return True
        t, b = planes(y, z, x)
        return any(t[i] < 1 for i in side) or any(b[i] > 0 for i in side)

    def opens_below(y: int, z: int, x: int) -> bool:
        """Whether cell (y, z, x) leaves open its bottom face (so the top of the cell below shows)."""
        if not (y < ny and z < nz and x < nx) or not filled[y, z, x]:
            return True
        t, b = planes(y, z, x)
        return max(b) > 0 or max(t) <= 0

    def side_face(x: float, z: float, along_x: bool, t: tuple, b: tuple, i: int, j: int, y: int) -> list:
        """The (x, z, y) outline of a cell's vertical face from corner i to corner j, between its planes."""
        cuts = profile(t[i], t[j]) + profile(b[i], b[j])
        s_values = sorted(set(cuts))

        def at(values: tuple, s: float) -> float:
            return min(1.0, max(0.0, values[i] + s * (values[j] - values[i])))

        def point(s: float, h: float) -> tuple[float, float, float]:
            return (x + s, z, y + h) if along_x else (x, z + s, y + h)

        # Keep the stretch where the face has thickness (and its end points): elsewhere along the edge the
        # cell is empty, and a zero-thickness stretch would draw as a line in the air.
        thick = [at(t, s) - at(b, s) > 1e-9 for s in s_values]
        keep = [s for i, s in enumerate(s_values)
                if thick[i] or (i > 0 and thick[i - 1]) or (i + 1 < len(thick) and thick[i + 1])]
        if not any(thick):
            return []
        return [point(s, at(b, s)) for s in keep] + [point(s, at(t, s)) for s in reversed(keep)]

    # Painter's order: cells nearer the viewer (larger x + z + y) are drawn later.
    for y, z, x in sorted(zip(*np.nonzero(filled)), key=lambda c: (sum(c), c[0])):
        base: RGB = tuple(int(v) for v in colors[y, z, x])
        line = shade(base, 0.45)
        t, b = planes(y, z, x)
        if max(t) <= 0 or min(b) >= 1 or all(ti <= bi for ti, bi in zip(t, b)):
            continue  # cut away entirely
        cut = min(t) < 1 or max(b) > 0  # the planes pass through the cell
        faces = []
        if opens(y, z, x + 1, (0, 3)):
            faces.append((EAST_SHADE, side_face(x + 1, z, False, t, b, 1, 2, y)))
        if opens(y, z + 1, x, (0, 1)):
            faces.append((SOUTH_SHADE, side_face(x, z + 1, True, t, b, 3, 2, y)))
        if not cut:
            if opens_below(y + 1, z, x):
                faces.append((TOP_SHADE, [(x, z, y + 1), (x + 1, z, y + 1), (x + 1, z + 1, y + 1), (x, z + 1, y + 1)]))
        else:
            square = [(u, v, t[k]) for k, (u, v) in enumerate(SQUARE)]
            # The part of the top the plane passes above is flat at 1. Only an empty cell above can show it: a
            # cut cell above belongs to the same part and covers it (nothing else may sit under a slope).
            if not (y + 1 < ny and filled[y + 1, z, x]):
                flat = clip(square, keep_above=1.0)
                if len(flat) >= 3:
                    faces.append((TOP_SHADE, [(x + u, z + v, y + 1) for u, v, _ in flat]))
            if min(t) < 1:  # the sloped part of the top
                sloped = clip(clip(square, keep_above=0.0), keep_below=1.0)
                factor = face_shade(t)
                if len(sloped) >= 3 and factor is not None:
                    faces.append((factor, [(x + u, z + v, y + h) for u, v, h in sloped]))
        for factor, outline in faces:
            points = [screen(*p) for p in outline]
            if len(points) >= 3 and area(points) > 0.5:  # skip faces a slope squeezed to a line
                draw.polygon(points, fill=shade(base, factor), outline=line)
        if not cut and opens_below(y + 1, z, x) and (studs is None or studs[y, z, x]):
            cx, cy = screen(x + 0.5, z + 0.5, y + 1)
            rx, ry, lift = stud * 0.38, half * 0.38, rise * 0.25
            draw.ellipse([cx - rx, cy - ry - lift, cx + rx, cy + ry - lift], fill=shade(base, 0.9), outline=line)
    return image


def save_voxels_png(filled: np.ndarray, colors: np.ndarray, path: str | Path, studs: np.ndarray | None = None,
                    tops: np.ndarray | None = None, bottoms: np.ndarray | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    render_voxels(filled, colors, studs=studs, tops=tops, bottoms=bottoms).save(path)
