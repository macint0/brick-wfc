"""Write an .ldr that checks the part catalog's geometry by eye (M8, M12b).

    python -m brickwfc.bricks.catalog_check --out out/check/catalog_check.ldr

Every rectangular catalog part is placed twice, unrotated and turned 90 degrees, at positions computed
from its assumed footprint (``width`` studs along LDraw X), with a one-stud gap between neighbors. Open
the file in BrickLink Studio or LeoCAD: if any parts overlap or touch, that part's size or orientation in
``parts.CATALOG`` is wrong. A tower at the front (brick, plate, brick, tile) checks heights: the parts
must sit flush, with no gaps or overlaps.

Corner and slope parts (M12b) are placed in every distinct orientation, each with yellow 1x1 plates
where the model puts its cells: one in each empty cell of its bounding box (a corner's notch) must sit
flush beside the part; one on each cell the model thinks has a stud must sit on a real stud (not float
over or cut into a sloped face); and a part with an open (sloped) bottom stands one plate up, on 1x1
plates under its flat cells only, none of which may cut into the sloped underside.

M12d parts follow the same rules: arches stand one plate up on markers under their two end cells (none may cut
into the arch), parts with studs on some cells carry markers on those only, and a baseplate lies on the ground with
a marker on each stud. Window and door frames carry their glass, panes and doors in every slot
(``accessories.FRAMES``): each must sit inside its frame, nothing sticking out of the frame's box. The baseplate is not
lowered onto the table here (``parts.build_placements``): the check is about the parts relative to each other. Parts
with keep-out cells (door rails, side studs, brackets, the handle brick) are shown in all four turns; the rail, stud,
face or handle must stick out on the side the model keeps empty (the one-stud gaps around each part are empty), and
brackets float four plates up so their face does not reach into the ground.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from brickwfc.bricks.accessories import ACCESSORY_FILES, fit
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import CATALOG, Part, PlacedPart, Shape, shapes_of
from brickwfc.ldraw.export import write_ldr

ROW_WIDTH = 40  # studs before starting a new row


def orientations(part: Part) -> list[Shape]:
    """Rectangular parts unrotated and turned (as in M8); other parts (and parts with keep-out cells) in each distinct
    orientation."""
    if Shape(part).rectangular and not part.keep_out:
        return [Shape(part, 0), Shape(part, 1)]
    return shapes_of([part])


def with_markers(shape: Shape, x: int, z: int) -> list[PlacedPart]:
    """A non-rectangular shape with its min corner at (x, z), plus yellow 1x1 plates where the model puts
    its cells (see the module docstring)."""
    red, yellow = colors_by_name(["red", "yellow"])
    marker = Shape(CATALOG["plate1x1"])
    layer = 1 if len(shape.geometry.seated) < len(shape.footprint) and not shape.part.ground_only else 0
    placed = [PlacedPart(shape, red, layer, x, z)]
    for dz in range(shape.size_z):
        for dx in range(shape.size_x):
            if not shape.covers(dz, dx):
                placed.append(PlacedPart(marker, yellow, layer, x + dx, z + dz))
            elif shape.studded(dz, dx):
                placed.append(PlacedPart(marker, yellow, layer + shape.size_y, x + dx, z + dz))
            if layer and shape.covers(dz, dx) and shape.seated(dz, dx):
                placed.append(PlacedPart(marker, yellow, 0, x + dx, z + dz))
    return placed


def layout() -> list[PlacedPart]:
    """Each part in its orientations, packed in rows along x with one stud between parts."""
    red, blue, yellow = colors_by_name(["red", "blue", "yellow"])
    placed: list[PlacedPart] = []
    x = z = row_depth = 0
    for part in CATALOG.values():
        shapes = orientations(part)
        need = sum(s.size_x for s in shapes) + len(shapes) - 1
        if x and x + need > ROW_WIDTH:
            x, z, row_depth = 0, z + row_depth + 1, 0
        for i, shape in enumerate(shapes):
            if shape.rectangular:
                # a bracket's face hangs below its plate: raised so that it clears the ground (it floats in the file)
                layer = max([0] + [-first for _, _, first, _ in shape.geometry.keep_out])
                placed.append(PlacedPart(shape, red if i % 2 == 0 else blue, layer, x, z))
            else:
                placed += with_markers(shape, x, z)
            x += shape.size_x + 1
            row_depth = max(row_depth, shape.size_z)
    # Height tower in front of the rows: brick (3 layers), plate (1), brick (3), tile (1).
    z_front = -3
    layer = 0
    for name, color in (("brick2x4", red), ("plate2x4", blue), ("brick2x4", yellow), ("tile2x4", red)):
        part = PlacedPart(Shape(CATALOG[name], False), color, layer, 0, z_front)
        placed.append(part)
        layer = part.top + 1
    return placed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.bricks.catalog_check", description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("out/check/catalog_check.ldr"))
    args = parser.parse_args(argv)
    placed = layout()
    trans_clear = 47
    glass = [placement for _, placement in fit(placed, {(file, trans_clear): len(placed) for file in ACCESSORY_FILES})]
    write_ldr([p.placement() for p in placed] + glass, args.out, "brickwfc part catalog check")
    print(f"wrote {args.out}: {len(CATALOG)} parts in all their orientations, with markers, + a height tower")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
