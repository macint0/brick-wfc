"""Parts inventories (M9): build only from the parts in a given set or collection.

An inventory maps (part name, color name) -> count, e.g. ("plate2x4", "red") -> 3; part names are
orientation-free (a turned 2x4 is still a 2x4) and come from ``parts.CATALOG``. ``InventoryConstraint`` enforces the counts inside
WFC propagation: once a (part, color) is used up, its tiles are removed from every undecided cell.
"""

from __future__ import annotations

from collections import Counter
from typing import Mapping

import numpy as np

from brickwfc.bricks.colors import BrickColor, color_for_code
from brickwfc.bricks.parts import BY_FILE, CATALOG, PLATE_FILES, Part, PartSet, PlacedPart, shapes_of
from brickwfc.ldraw.mpd import flatten
from brickwfc.wfc import Cell, Wave

Inventory = dict[tuple[str, str], int]  # (part name, color name) -> count


def inventory_from_mpd(text: str, known: Mapping[str, Part] = BY_FILE) -> tuple[Inventory, Counter[str], list[BrickColor]]:
    """Count the known parts (LDraw file -> part; default: the whole catalog) in an LDraw model,
    in any position or orientation.

    Returns ``(inventory, unsupported part counts, colors used)``.
    """
    inventory: Counter[tuple[str, str]] = Counter()
    unsupported: Counter[str] = Counter()
    colors: dict[str, BrickColor] = {}
    for inst in flatten(text):
        part = known.get(inst.part.lower())
        if part is None:
            unsupported[inst.part] += 1
            continue
        color = color_for_code(inst.color)
        colors[color.name] = color
        inventory[(part.name, color.name)] += 1
    return dict(inventory), unsupported, sorted(colors.values(), key=lambda c: c.ldraw)


def part_cells(part: Part) -> int:
    return part.width * part.depth * part.height


def inventory_cells(inventory: Inventory) -> int:
    """Volume of the inventory in grid cells (studs x studs x plate layers)."""
    return sum(count * part_cells(CATALOG[part]) for (part, _), count in inventory.items())


def inventory_coverage(inventory: Inventory) -> dict[tuple[str, str], float]:
    """``part_tileset`` coverage weights: each (part, color) covers cells in proportion to its count
    and volume, split evenly over the part's orientations."""
    coverage: dict[tuple[str, str], float] = {}
    for (part_name, color), count in inventory.items():
        shapes = shapes_of([CATALOG[part_name]])
        for shape in shapes:
            coverage[(shape.name, color)] = count * part_cells(CATALOG[part_name]) / len(shapes)
    return coverage


def usage(placed: list[PlacedPart]) -> Counter[tuple[str, str]]:
    return Counter((p.shape.part.name, p.color.name) for p in placed)


def overuse(placed: list[PlacedPart], inventory: Inventory) -> dict[tuple[str, str], int]:
    """(part, color) -> how many more were used than available; empty if the build fits the inventory."""
    return {key: used - inventory.get(key, 0) for key, used in usage(placed).items() if used > inventory.get(key, 0)}


def utilization(placed: list[PlacedPart], inventory: Inventory) -> float:
    """Share of the inventory's parts used, counting at most the available number of each."""
    used = usage(placed)
    total = sum(inventory.values())
    return sum(min(used[key], count) for key, count in inventory.items()) / total if total else 0.0


class InventoryConstraint:
    """Never place more of a (part, color) than the inventory holds.

    A placed part is counted by its anchor cell (offset 0, 0, 0) once that cell is fixed. Adjacency
    rules make a part's cells fix together, so a cell fixed to any tile of a part means the whole
    part, anchor included, is fixed. When a (part, color) reaches its limit, its tiles are removed
    from every undecided cell; exceeding the limit is a contradiction.
    """

    def __init__(self, parts: PartSet, inventory: Inventory) -> None:
        groups: dict[tuple[str, str], tuple[list[int], list[int]]] = {}
        for tile, info in enumerate(parts.infos):
            if not info.solid:
                continue
            anchors, tiles = groups.setdefault((info.shape.part.name, info.color.name), ([], []))
            tiles.append(tile)
            if (info.offset_x, info.offset_y, info.offset_z) == (0, 0, 0):
                anchors.append(tile)
        self.groups = [
            (key, np.array(anchors), np.array(tiles), inventory.get(key, 0)) for key, (anchors, tiles) in groups.items()
        ]

    def prune(self, wave: Wave, changed: set[Cell]) -> list[Cell] | None:
        domain = wave.domain
        fixed = domain.sum(axis=-1) == 1
        pruned: list[Cell] = []
        for _, anchors, tiles, limit in self.groups:
            used = int((domain[..., anchors].any(axis=-1) & fixed).sum())
            if used > limit:
                return None
            if used < limit:
                continue
            still_possible = ~fixed & domain[..., tiles].any(axis=-1)
            if not still_possible.any():
                continue
            group = domain[..., tiles]
            group[still_possible] = False
            domain[..., tiles] = group
            if not domain[still_possible].any(axis=-1).all():
                return None
            pruned.extend(tuple(int(i) for i in cell) for cell in np.argwhere(still_possible))
        return pruned
