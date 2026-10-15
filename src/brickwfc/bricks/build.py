"""Turn a solved 3D part grid into LDraw files and preview images."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from brickwfc.bricks.parts import PartSet, PlacedPart, build_placements, turn_rotation
from brickwfc.bricks.support import studded
from brickwfc.ldraw.export import write_ldr
from brickwfc.render3d import save_voxels_png

SLOPE_LIP = 0.5  # plates: the vertical edge a slope's face ends on (4 LDU in the 45 and 33 degree .dat files)
CORNERS = ((0, 0), (1, 0), (1, 1), (0, 1))  # (x, z) of a cell's corners, in the order render3d expects


def placed_colors(placed: list[PlacedPart], shape: tuple[int, int, int]) -> np.ndarray:
    """(Y, Z, X, 3) display colors, with a slight per-part brightness change so neighboring
    parts of the same color stay distinguishable in the preview."""
    colors = np.zeros((*shape, 3), dtype=np.float64)
    for i, part in enumerate(placed):
        factor = (1.0, 0.9, 0.95, 0.85)[i % 4]
        for cell in part.cells():
            colors[cell] = np.array(part.color.rgb) * factor
    return colors.round().astype(np.uint8)


def slope_profiles(placed: list[PlacedPart], shape: tuple[int, int, int]) -> tuple[np.ndarray, np.ndarray] | None:
    """``render3d`` cell cuts (tops, bottoms: (Y, Z, X, 4) heights of the cutting planes at each cell's
    corners, in plates from the cell's bottom) that draw slopes (parts with ``sloped_rows``) with their sloped
    face, or None if the build has none.

    A plain slope's top falls linearly from its full height where its studded rows end to ``SLOPE_LIP``
    at its low edge; an inverted slope's bottom rises from 0 where its flat row ends to ``SLOPE_LIP`` below
    its top. Each corner's height comes from its position in the part's own frame (the inverse of its turn).
    """
    slopes = [p for p in placed if p.shape.part.sloped_rows]
    if not slopes:
        return None
    tops, bottoms = np.ones((*shape, 4)), np.zeros((*shape, 4))
    for part in slopes:
        spec = part.shape.part
        r = np.array(turn_rotation(part.shape.turn)).reshape(3, 3)
        origin_x, origin_z = part.shape.geometry.origin
        # Cell (x, z) spans [x, x + 1]; its centre, where the part's cell coordinates point, is at x + 0.5.
        ox, oz = part.x + origin_x + 0.5, part.z + origin_z + 0.5
        high, low = -(spec.depth - spec.sloped_rows) + 0.5, -spec.depth + 0.5  # local z of the face's edges
        for _, z, x in part.bottom_cells():
            for i, (cx, cz) in enumerate(CORNERS):
                wx, wz = x + cx - ox, z + cz - oz
                local_z = r[0, 2] * wx + r[2, 2] * wz  # the inverse turn (R transposed), z row
                along = float(np.clip((local_z - low) / (high - low), 0.0, 1.0))  # 1 at the high edge
                for dy in range(spec.height):
                    y = part.layer + dy
                    if spec.seated_cells is None:
                        tops[y, z, x, i] = SLOPE_LIP + (spec.height - SLOPE_LIP) * along - dy
                    else:
                        bottoms[y, z, x, i] = (spec.height - SLOPE_LIP) * (1 - along) - dy
    return tops, bottoms


def save_preview(placed: list[PlacedPart], shape: tuple[int, int, int], png_path: Path) -> None:
    """Isometric preview of placed parts in a grid of ``shape``; slopes are drawn with their sloped face."""
    filled = np.zeros(shape, dtype=bool)
    for part in placed:
        for cell in part.cells():
            filled[cell] = True
    profiles = slope_profiles(placed, shape)
    tops, bottoms = (None, None) if profiles is None else profiles
    save_voxels_png(filled, placed_colors(placed, shape), png_path, studded(placed, shape), tops, bottoms)


def export_build(grid: np.ndarray, placed: list[PlacedPart], parts: PartSet, ldr_path: Path, png_path: Path | None, title: str) -> None:
    write_ldr(build_placements(sorted(placed, key=lambda p: (p.layer, p.z, p.x))), ldr_path, title)
    if png_path is not None:
        save_preview(placed, grid.shape, png_path)
