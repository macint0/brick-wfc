"""Render a 2D tile grid to an image."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from brickwfc.tileset import Tileset


def render(grid: np.ndarray, tileset: Tileset, scale: int = 8) -> Image.Image:
    """Draw each cell as a ``scale`` x ``scale`` square in its tile's color."""
    if scale < 1:
        raise ValueError(f"scale must be >= 1, got {scale}")
    palette = np.array(tileset.colors, dtype=np.uint8)
    rgb = palette[grid].repeat(scale, axis=0).repeat(scale, axis=1)
    return Image.fromarray(rgb)


def save_png(grid: np.ndarray, tileset: Tileset, path: str | Path, scale: int = 8) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    render(grid, tileset, scale).save(path)


def contact_sheet(
    images: list[Image.Image],
    columns: int,
    gap: int = 8,
    background: tuple[int, int, int] = (255, 255, 255),
) -> Image.Image:
    """Lay images out on a grid, row-major, each slot sized to the largest image."""
    if not images:
        raise ValueError("contact_sheet needs at least one image")
    cell_w = max(img.width for img in images)
    cell_h = max(img.height for img in images)
    rows = -(-len(images) // columns)
    sheet = Image.new(
        "RGB", (columns * cell_w + (columns - 1) * gap, rows * cell_h + (rows - 1) * gap), background
    )
    for i, img in enumerate(images):
        row, col = divmod(i, columns)
        sheet.paste(img, (col * (cell_w + gap), row * (cell_h + gap)))
    return sheet
