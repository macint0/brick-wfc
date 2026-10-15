"""Contained accessories (M12d): the glass, panes and doors that sit inside a window or door frame.

An accessory has no cells of its own: the frame's box (``parts.CATALOG``) already holds it, so it never changes
whether or where anything fits. It goes into one of its frame's *slots*: a pose relative to the frame's LDraw
placement, the one real models use most (``results/m12d_catalog.md``; every slot's accessory lies inside its frame's
box, ``tests/test_accessories.py``). So accessories are fitted after a build is made (``fit``): each placed frame, in
placement order, fills its slots from what the inventory has left, and the build's .ldr carries them with the frame.

Inventories hold them apart from the catalog parts, as ``(LDraw file, LDraw color code) -> count`` (glass is
trans-clear, which the palette has no name for). A composite file of frame + glass (``60592c01``) is read as its frame
(an alias in the catalog) plus the glass it contains (``COMPOSITES``). In a real model an accessory counts as recognized
when a recognized frame's box holds its origin (``contained``).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np

from brickwfc.bricks.parts import BY_FILE, PlacedPart, turn_rotation
from brickwfc.ldraw.export import PLATE_LDU, STUD_LDU, Placement
from brickwfc.ldraw.mpd import PartInstance

Accessories = dict[tuple[str, int], int]  # (LDraw file, LDraw color code) -> count
IDENTITY = turn_rotation(0)
TOLERANCE_LDU = 1.0


@dataclass(frozen=True)
class Slot:
    """Where an accessory goes in its frame: any one of ``files``, at ``position`` (LDU) with ``rotation``, both in
    the frame's own LDraw coordinates."""

    files: tuple[str, ...]
    position: tuple[float, float, float]
    rotation: tuple[int, ...] = IDENTITY


# Frame file -> its slots, in the order they are filled. Poses: the most common relative placement in the 93 OMR
# models (scratch measurement, see results/m12d_catalog.md); turn 1 / turn 3 are a pane hinged on the right / left.
FRAMES: dict[str, tuple[Slot, ...]] = {
    "60592.dat": (Slot(("60601.dat",), (0, 0, 0)),),
    "60593.dat": (Slot(("60602.dat",), (0, 0, 0)),),
    "2377.dat": (Slot(("4862.dat",), (0, 0, 0)),),
    "4863.dat": (Slot(("4862.dat",), (-20, 0, 0)), Slot(("4862.dat",), (20, 0, 0))),
    "2493b.dat": (Slot(("2494.dat",), (0, 0, 0)),),
    "30044.dat": (Slot(("30046.dat",), (0, 24, -5)),),
    "6556.dat": (Slot(("3854.dat",), (-34, 4, 3), turn_rotation(3)), Slot(("3854.dat",), (34, 4, 4), turn_rotation(1))),
    "60594.dat": (Slot(("86210.dat",), (0, 8, 4)), Slot(("60608.dat",), (-32, 4, 4), turn_rotation(3)),
                  Slot(("60608.dat",), (32, 4, 4), turn_rotation(1))),
    "60596.dat": (Slot(("60623.dat", "60616b.dat", "60616a.dat"), (-32, 0, 5)), Slot(("57895.dat",), (0, 4, 5))),
    "30179.dat": (Slot(("57895.dat",), (0, 4, 5)),),
}
ACCESSORY_FILES: frozenset[str] = frozenset(f for slots in FRAMES.values() for slot in slots for f in slot.files)
# Composite files (frame + glass in one file): the accessory inside and its color (from the composite's .dat).
COMPOSITES: dict[str, tuple[str, int]] = {"60592c01.dat": ("60601.dat", 47), "60593c01.dat": ("60602.dat", 47)}


def accessories_from_csv(text: str) -> Accessories:
    """The accessories in a parts list (``inventory.inventory_from_csv``'s format; other rows are skipped there)."""
    found: Counter[tuple[str, int]] = Counter()
    for line in text.splitlines():
        fields = [f.strip() for f in line.split("#")[0].split(",")]
        if len(fields) != 3 or not fields[2].isdigit():
            continue
        file = fields[0].lower() if fields[0].lower().endswith(".dat") else f"{fields[0].lower()}.dat"
        code = int(fields[1], 16) if fields[1].lower().startswith("0x") else int(fields[1])
        if file in ACCESSORY_FILES:
            found[(file, code)] += int(fields[2])
        elif file in COMPOSITES:
            found[COMPOSITES[file]] += int(fields[2])
    return {key: n for key, n in found.items() if n}


def accessories_in(instances: Iterable[PartInstance]) -> Accessories:
    """The accessories in a model: accessory files, and the glass inside composite frames."""
    found: Counter[tuple[str, int]] = Counter()
    for inst in instances:
        name = inst.part.lower()
        if name in ACCESSORY_FILES:
            found[(name, inst.color)] += 1
        elif name in COMPOSITES:
            found[COMPOSITES[name]] += 1
    return dict(found)


def fit(placed: Sequence[PlacedPart], accessories: Mapping[tuple[str, int], int]) -> list[tuple[int, Placement]]:
    """Accessories for a build: every placed frame, in order, fills each slot with the first of the slot's files the
    inventory still has (the color with the most left, ties by code). Returns (index of the frame in ``placed``,
    placement), using up the inventory as it goes (a copy; ``accessories`` is not changed)."""
    left = Counter(accessories)
    fitted: list[tuple[int, Placement]] = []
    for i, part in enumerate(placed):
        for slot in FRAMES.get(part.shape.part.ldraw, ()):
            for file in slot.files:
                colors = sorted((code for (f, code), n in left.items() if f == file and n > 0), key=lambda c: (-left[(file, c)], c))
                if colors:
                    left[(file, colors[0])] -= 1
                    fitted.append((i, slot_placement(part.placement(), slot, file, colors[0])))
                    break
    return fitted


def slot_placement(frame: Placement, slot: Slot, file: str, color: int) -> Placement:
    """The accessory's LDraw placement in ``slot`` of a frame placed at ``frame``."""
    r = np.array(frame.rotation, dtype=float).reshape(3, 3)
    position = np.array(frame.position) + r @ np.array(slot.position, dtype=float)
    rotation = r @ np.array(slot.rotation, dtype=float).reshape(3, 3)
    return Placement(color, tuple(float(v) + 0.0 for v in position), tuple(int(round(v)) for v in rotation.ravel()), file)


def contained(instances: Sequence[PartInstance], frames: Iterable[int] | None = None) -> int:
    """How many accessory instances lie in a frame: their origin inside the box of a catalog frame instance
    (``frames``: indices into ``instances`` to consider, e.g. the ones a voxelizer kept; default every instance).
    Each frame holds at most as many as it has slots; a composite frame's own glass takes one of them."""
    boxes: list[tuple[PartInstance, np.ndarray, np.ndarray]] = []
    room: list[int] = []
    for i in range(len(instances)) if frames is None else frames:
        name = instances[i].part.lower()
        part = BY_FILE.get(name)
        if part is None or part.ldraw not in FRAMES:
            continue
        cells = np.array(part.footprint_cells) * STUD_LDU
        bottom = part.origin_layer * PLATE_LDU  # LDraw -Y is up: the box spans bottom - height ... bottom
        low = np.array([cells[:, 0].min() - STUD_LDU / 2, bottom - part.height * PLATE_LDU,
                        cells[:, 1].min() - STUD_LDU / 2]) - TOLERANCE_LDU
        high = np.array([cells[:, 0].max() + STUD_LDU / 2, bottom, cells[:, 1].max() + STUD_LDU / 2]) + TOLERANCE_LDU
        boxes.append((instances[i], low, high))
        room.append(len(FRAMES[part.ldraw]) - (name in COMPOSITES))
    count = 0
    for inst in instances:
        if inst.part.lower() not in ACCESSORY_FILES:
            continue
        for j, (frame, low, high) in enumerate(boxes):
            local = frame.rotation.T @ (inst.position - frame.position)
            if room[j] > 0 and np.all(local >= low) and np.all(local <= high):
                room[j] -= 1
                count += 1
                break
    return count
