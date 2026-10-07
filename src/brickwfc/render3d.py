"""Isometric preview of a 3D voxel build (a quick look without opening an LDraw viewer)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from brickwfc.tileset import RGB

# Face shades for a light from above/front-left.
TOP_SHADE, EAST_SHADE, SOUTH_SHADE = 1.0, 0.78, 0.62
PLATE_ASPECT = 8 / 20  # plate height / stud width


def shade(rgb: RGB, factor: float) -> RGB:
    return tuple(int(round(c * factor)) for c in rgb)


def render_voxels(filled: np.ndarray, colors: np.ndarray, stud: int = 14, background: RGB = (255, 255, 255)) -> Image.Image:
    """Draw a (Y, Z, X) build seen from above its south-east corner.

    ``colors`` is (Y, Z, X, 3) uint8. Only exposed faces are drawn, back to front, and each
    exposed top face gets a stud.
    """
    ny, nz, nx = filled.shape
    half = stud / 2
    rise = stud * PLATE_ASPECT * 1.2  # screen height of one plate layer

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

    def exposed(y: int, z: int, x: int) -> bool:
        return not (y < ny and z < nz and x < nx) or not filled[y, z, x]

    # Painter's order: cells nearer the viewer (larger x + z + y) are drawn later.
    for y, z, x in sorted(zip(*np.nonzero(filled)), key=lambda c: (sum(c), c[0])):
        base: RGB = tuple(int(v) for v in colors[y, z, x])
        line = shade(base, 0.45)
        faces = []
        if exposed(y, z, x + 1):
            faces.append((EAST_SHADE, [(x + 1, z, y), (x + 1, z + 1, y), (x + 1, z + 1, y + 1), (x + 1, z, y + 1)]))
        if exposed(y, z + 1, x):
            faces.append((SOUTH_SHADE, [(x, z + 1, y), (x + 1, z + 1, y), (x + 1, z + 1, y + 1), (x, z + 1, y + 1)]))
        if exposed(y + 1, z, x):
            faces.append((TOP_SHADE, [(x, z, y + 1), (x + 1, z, y + 1), (x + 1, z + 1, y + 1), (x, z + 1, y + 1)]))
        for factor, quad in faces:
            draw.polygon([screen(*p) for p in quad], fill=shade(base, factor), outline=line)
        if exposed(y + 1, z, x):
            cx, cy = screen(x + 0.5, z + 0.5, y + 1)
            rx, ry, lift = stud * 0.38, half * 0.38, rise * 0.25
            draw.ellipse([cx - rx, cy - ry - lift, cx + rx, cy + ry - lift], fill=shade(base, 0.9), outline=line)
    return image


def save_voxels_png(filled: np.ndarray, colors: np.ndarray, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    render_voxels(filled, colors).save(path)
