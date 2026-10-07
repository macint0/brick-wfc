"""Read and write 2D tile grids as CSV (tile ids) or PNG (one color per tile)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

from brickwfc.tileset import RGB


def read_grid_csv(path: str | Path) -> np.ndarray:
    """Read a CSV of integer tile ids into an (H, W) int array."""
    rows = [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines()]
    grid = [[int(cell) for cell in row.split(",")] for row in rows if row]
    if not grid or any(len(row) != len(grid[0]) for row in grid):
        raise ValueError(f"{path}: CSV grid must be non-empty and rectangular")
    return np.array(grid, dtype=np.int64)


def write_grid_csv(grid: np.ndarray, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(",".join(str(int(v)) for v in row) for row in grid) + "\n", encoding="utf-8")


def detect_scale(rgb: np.ndarray) -> int:
    """Largest cell size (in pixels) consistent with an image made of uniform square cells.

    Every color change must fall on a cell boundary, so the cell size divides every change
    position as well as the image width and height.
    """
    height, width = rgb.shape[:2]
    xs = np.nonzero(np.any(rgb[:, 1:] != rgb[:, :-1], axis=(0, 2)))[0] + 1
    ys = np.nonzero(np.any(rgb[1:] != rgb[:-1], axis=(1, 2)))[0] + 1
    return math.gcd(height, width, *(int(v) for v in xs), *(int(v) for v in ys))


def read_grid_png(path: str | Path, scale: int | None = None) -> tuple[np.ndarray, list[RGB]]:
    """Read a PNG where each ``scale`` x ``scale`` block is one cell and each color is one tile.

    Returns ``(grid, palette)``: tile ids index into ``palette``, which is sorted by color so
    the result does not depend on scan order. ``scale`` is auto-detected when omitted.
    """
    rgb = np.asarray(Image.open(path).convert("RGB"))
    scale = detect_scale(rgb) if scale is None else scale
    cells = rgb[::scale, ::scale]
    if not np.array_equal(cells.repeat(scale, axis=0).repeat(scale, axis=1), rgb):
        raise ValueError(f"{path}: image is not made of uniform {scale}x{scale} cells")
    palette, ids = np.unique(cells.reshape(-1, 3), axis=0, return_inverse=True)
    grid = ids.reshape(cells.shape[:2]).astype(np.int64)
    return grid, [tuple(int(c) for c in color) for color in palette]
