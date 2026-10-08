"""Write an .ldr that checks the part catalog's geometry by eye (M8).

    python -m brickwfc.bricks.catalog_check --out out/check/catalog_check.ldr

Every catalog part is placed twice, unrotated and turned 90 degrees, at positions computed from its
assumed footprint (``width`` studs along LDraw X), with a one-stud gap between neighbors. Open the
file in BrickLink Studio or LeoCAD: if any parts overlap or touch, that part's size or orientation in
``parts.CATALOG`` is wrong. A tower at the front (brick, plate, brick, tile) checks heights: the
parts must sit flush, with no gaps or overlaps.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import CATALOG, PlacedPart, Shape
from brickwfc.ldraw.export import write_ldr

ROW_WIDTH = 40  # studs before starting a new row


def layout() -> list[PlacedPart]:
    """Each part unrotated then turned, packed in rows along x with one stud between parts."""
    red, blue, yellow = colors_by_name(["red", "blue", "yellow"])
    placed: list[PlacedPart] = []
    x = z = row_depth = 0
    for part in CATALOG.values():
        flat, turned = Shape(part, False), Shape(part, True)
        need = flat.size_x + 1 + turned.size_x
        if x and x + need > ROW_WIDTH:
            x, z, row_depth = 0, z + row_depth + 1, 0
        placed.append(PlacedPart(flat, red, 0, x, z))
        placed.append(PlacedPart(turned, blue, 0, x + flat.size_x + 1, z))
        x += need + 1
        row_depth = max(row_depth, flat.size_z, turned.size_z)
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
    write_ldr((p.placement() for p in placed), args.out, "brickwfc part catalog check")
    print(f"wrote {args.out}: {len(CATALOG)} parts x 2 orientations + a height tower")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
