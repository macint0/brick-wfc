"""Voxelize real LDraw models into the M5 part/tile representation (M7).

Only parts the generator knows (``parts.CATALOG`` by default) are kept, and only when they sit on the stud
grid: rotated by a multiple of 90 degrees about the vertical axis, at stud/plate-aligned
positions. Everything else is counted in the report and ignored, so a voxelized model is a
partial view of the real one. Accessories (M12d: glass, panes, doors; no cells of their own) in a kept frame are
counted in ``report.contained``.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Mapping

import numpy as np

from brickwfc.bricks.accessories import contained
from brickwfc.bricks.colors import color_for_code
from brickwfc.bricks.parts import BY_FILE, Part, PartSet, PlacedPart, Shape, TileInfo, canonical, turn_rotation
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
    contained: int = 0  # M12d: accessories (glass, panes, doors) in a kept frame; no cells of their own


def quarter_turns(rotation: np.ndarray) -> int | None:
    """For a rotation about LDraw Y by a multiple of 90 degrees, how many quarter turns
    (``parts.turn_rotation``) it is. None for any other rotation (tilted, mirrored, upside down)."""
    r = np.asarray(rotation, dtype=float).reshape(3, 3)
    for turn in range(4):
        if np.allclose(r, np.array(turn_rotation(turn)).reshape(3, 3), atol=TOLERANCE):
            return turn
    return None


def axis_aligned_turn(rotation: np.ndarray) -> bool | None:
    """For a rotation about LDraw Y by a multiple of 90 degrees, whether local X maps onto world Z
    (a quarter turn). None for any other rotation (tilted, mirrored, upside down)."""
    turn = quarter_turns(rotation)
    return None if turn is None else turn % 2 == 1


def most_common_fraction(values: list[float]) -> float:
    """The most common fractional part of ``values`` (the model's grid offset along one axis)."""
    fractions = Counter(round(v % 1.0, 3) % 1.0 for v in values)
    return fractions.most_common(1)[0][0] if fractions else 0.0


def voxelize(instances: list[PartInstance], known: Mapping[str, Part] = BY_FILE) -> tuple[list[PlacedPart], VoxelizeReport]:
    report = VoxelizeReport(total_parts=len(instances))
    unrecognized: Counter[str] = Counter()
    # (shape, color, corner x, corner z, layer) in fractional cell units before snapping.
    candidates: list[tuple[Shape, int, float, float, float]] = []
    sources: list[int] = []  # the instance each candidate came from
    for index, inst in enumerate(instances):
        part = known.get(inst.part.lower())
        if part is None:
            report.unrecognized += 1
            unrecognized[inst.part] += 1
            continue
        turn = quarter_turns(inst.rotation)
        if turn is None:
            report.tilted += 1
            continue
        origin_x, origin_z = Shape(part, turn).geometry.origin  # from the min-corner cell, in this turn
        px, py, pz = inst.position
        corner_x = px / STUD_LDU - origin_x
        corner_z = pz / STUD_LDU - origin_z
        layer = -py / PLATE_LDU - part.origin_layer  # -Y is up
        # A turn with the same cells as an earlier one (a rectangle turned twice) is that shape.
        candidates.append((canonical(part, turn), inst.color, corner_x, corner_z, layer))
        sources.append(index)
    report.unrecognized_top = unrecognized.most_common(10)

    offsets = [most_common_fraction([c[i] for c in candidates]) for i in (2, 3, 4)]
    snapped = []
    for source, (shape, color, *coords) in zip(sources, candidates):
        cells = [v - o for v, o in zip(coords, offsets)]
        if any(abs(v - round(v)) > TOLERANCE for v in cells):
            report.off_grid += 1
            continue
        snapped.append((shape, color, *(int(round(v)) for v in cells), source))

    placed: list[PlacedPart] = []
    if snapped:
        kept_sources = []
        min_x = min(s[2] for s in snapped)
        min_z = min(s[3] for s in snapped)
        min_layer = min(s[4] for s in snapped)
        taken: set[tuple[int, int, int]] = set()
        for shape, color, x, z, layer, source in snapped:
            part = PlacedPart(shape, color_for_code(color), layer - min_layer, x - min_x, z - min_z)
            cells = part.cells()
            if taken.intersection(cells):
                report.overlapping += 1
                continue
            taken.update(cells)
            placed.append(part)
            kept_sources.append(source)
        report.contained = contained(instances, kept_sources)
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
