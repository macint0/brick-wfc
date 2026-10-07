"""Turn a solved 3D part grid into LDraw files and preview images."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from brickwfc.bricks.parts import PartSet, PlacedPart
from brickwfc.ldraw.export import write_ldr
from brickwfc.render3d import save_voxels_png


def part_colors(grid: np.ndarray, placed: list[PlacedPart], parts: PartSet) -> np.ndarray:
    """(Y, Z, X, 3) display colors, with a slight per-part brightness change so neighboring
    parts of the same color stay distinguishable in the preview."""
    colors = np.array(parts.tileset.colors, dtype=np.float64)[grid]
    for i, part in enumerate(placed):
        factor = (1.0, 0.9, 0.95, 0.85)[i % 4]
        for cell in part.cells():
            colors[cell] *= factor
    return colors.round().astype(np.uint8)


def export_build(grid: np.ndarray, placed: list[PlacedPart], parts: PartSet, ldr_path: Path, png_path: Path | None, title: str) -> None:
    write_ldr((p.placement() for p in sorted(placed, key=lambda p: (p.layer, p.z, p.x))), ldr_path, title)
    if png_path is not None:
        save_voxels_png(parts.solid[grid], part_colors(grid, placed, parts), png_path)
