"""Turn a solved 3D plate grid into LDraw placements and preview images (M4)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from brickwfc.bricks.plates import PlateSet
from brickwfc.ldraw.export import IDENTITY, Placement, stud_position, write_ldr
from brickwfc.render3d import save_voxels_png

PLATE_1X1 = "3024.dat"


def plate_placements(grid: np.ndarray, plates: PlateSet) -> list[Placement]:
    """One 1x1 plate per solid cell of a (Y, Z, X) grid, bottom layer first."""
    placements = []
    for y, z, x in zip(*np.nonzero(plates.solid[grid])):
        color = plates.ldraw_colors[grid[y, z, x]]
        placements.append(Placement(color, stud_position(x, z, layer_top=y + 1), IDENTITY, PLATE_1X1))
    return placements


def export_plates(grid: np.ndarray, plates: PlateSet, ldr_path: Path, png_path: Path | None, title: str) -> None:
    write_ldr(plate_placements(grid, plates), ldr_path, title)
    if png_path is not None:
        colors = np.array(plates.tileset.colors, dtype=np.uint8)[grid]
        save_voxels_png(plates.solid[grid], colors, png_path)
