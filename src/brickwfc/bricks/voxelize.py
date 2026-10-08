"""Voxelize real LDraw models into the M5 part/tile representation (M7).

Only parts the generator knows (``parts.CATALOG`` by default) are kept, and only when they sit on the stud
grid: rotated by a multiple of 90 degrees about the vertical axis, at stud/plate-aligned
positions. Everything else is counted in the report and ignored, so a voxelized model is a
partial view of the real one.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Mapping

import numpy as np

from brickwfc.bricks.colors import color_for_code
from brickwfc.bricks.parts import BY_FILE, Part, PartSet, PlacedPart, Shape, TileInfo
from brickwfc.ldraw.export import PLATE_LDU, STUD_LDU
from brickwfc.ldraw.mpd import PartInstance

TOLERANCE = 1e-3


@dataclass
class VoxelizeReport:
    total_parts: int = 0
    unrecognized: int = 0  # not one of the generator's parts
    tilted: int = 0  # not a 90-degree rotation about the vertical axis
    off_grid: int = 0  # not aligned to the stud/plate grid
    overlapping: int = 0  # cells already taken by an earlier part
    kept: int = 0
    unrecognized_top: list[tuple[str, int]] = field(default_factory=list)


def axis_aligned_turn(rotation: np.ndarray) -> bool | None:
    """For a rotation about LDraw Y by a multiple of 90 degrees, whether local X maps onto world Z
    (a quarter turn). None for any other rotation (tilted, mirrored, upside down)."""
    r = np.asarray(rotation)
    if not np.allclose(np.abs(r), np.round(np.abs(r)), atol=TOLERANCE):
        return None
    if not (np.isclose(r[1, 1], 1, atol=TOLERANCE) and np.isclose(abs(np.linalg.det(r)), 1, atol=TOLERANCE)):
        return None
    if np.linalg.det(r) < 0:
        return None
    return bool(np.isclose(abs(r[2, 0]), 1, atol=TOLERANCE))


def most_common_fraction(values: list[float]) -> float:
    """The most common fractional part of ``values`` (the model's grid offset along one axis)."""
    fractions = Counter(round(v % 1.0, 3) % 1.0 for v in values)
    return fractions.most_common(1)[0][0] if fractions else 0.0


def voxelize(instances: list[PartInstance], known: Mapping[str, Part] = BY_FILE) -> tuple[list[PlacedPart], VoxelizeReport]:
    report = VoxelizeReport(total_parts=len(instances))
    unrecognized: Counter[str] = Counter()
    # (shape, color, corner x, corner z, layer) in fractional cell units before snapping.
    candidates: list[tuple[Shape, int, float, float, float]] = []
    for inst in instances:
        part = known.get(inst.part.lower())
        if part is None:
            report.unrecognized += 1
            unrecognized[inst.part] += 1
            continue
        turned = axis_aligned_turn(inst.rotation)
        if turned is None:
            report.tilted += 1
            continue
        shape = Shape(part, rotated=turned and part.width != part.depth)  # a turned square is the same shape
        px, py, pz = inst.position
        corner_x = px / STUD_LDU - (shape.size_x - 1) / 2
        corner_z = pz / STUD_LDU - (shape.size_z - 1) / 2
        layer = -py / PLATE_LDU - part.height  # the part's origin is its top face; -Y is up
        candidates.append((shape, inst.color, corner_x, corner_z, layer))
    report.unrecognized_top = unrecognized.most_common(10)

    offsets = [most_common_fraction([c[i] for c in candidates]) for i in (2, 3, 4)]
    snapped = []
    for shape, color, *coords in candidates:
        cells = [v - o for v, o in zip(coords, offsets)]
        if any(abs(v - round(v)) > TOLERANCE for v in cells):
            report.off_grid += 1
            continue
        snapped.append((shape, color, *(int(round(v)) for v in cells)))

    placed: list[PlacedPart] = []
    if snapped:
        min_x = min(s[2] for s in snapped)
        min_z = min(s[3] for s in snapped)
        min_layer = min(s[4] for s in snapped)
        taken: set[tuple[int, int, int]] = set()
        for shape, color, x, z, layer in snapped:
            part = PlacedPart(shape, color_for_code(color), layer - min_layer, x - min_x, z - min_z)
            cells = part.cells()
            if taken.intersection(cells):
                report.overlapping += 1
                continue
            taken.update(cells)
            placed.append(part)
    report.kept = len(placed)
    return placed, report


def grid_shape(placed: list[PlacedPart]) -> tuple[int, int, int]:
    """(Y, Z, X) extent of a voxelized model."""
    cells = [cell for part in placed for cell in part.cells()]
    return tuple(max(c[i] for c in cells) + 1 for i in range(3))


def tile_grid(placed: list[PlacedPart], parts: PartSet) -> np.ndarray:
    """The M5 tile representation of placed parts: a (Y, Z, X) grid of tile ids, empty elsewhere.

    Every (shape, color) present must have tiles in ``parts``.
    """
    index = {info: t for t, info in enumerate(parts.infos)}
    grid = np.full(grid_shape(placed), index[TileInfo(None)], dtype=np.int64)
    for part in placed:
        for y, z, x in part.cells():
            grid[y, z, x] = index[TileInfo(part.shape, x - part.x, z - part.z, part.color, y - part.layer)]
    return grid
