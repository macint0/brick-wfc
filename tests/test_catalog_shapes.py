"""M12b: non-rectangular parts (corners) in the catalog: geometry against the LDraw files, integrity,
support, physics, LDraw round trips, and builds from the M8 catalog unchanged."""

import hashlib
from pathlib import Path

import numpy as np
import pytest

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.catalog_check import layout
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import (
    BY_FILE,
    CATALOG,
    DOWN,
    UP,
    PartSet,
    PlacedPart,
    Shape,
    canonical,
    extract_parts,
    part_tileset,
    shapes_of,
)
from brickwfc.bricks.physics import required_clutch, tipping_clusters
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.support import is_stable
from brickwfc.bricks.voxelize import tile_grid, voxelize
from brickwfc.ldraw.export import PLATE_LDU, STUD_LDU, write_ldr
from brickwfc.ldraw.mpd import flatten
from brickwfc.wfc import run

RED, BLUE = colors_by_name(["red", "blue"])
BUILDS = 100

# Facts read from the LDraw library's part files (resolved through their subfiles): top stud positions
# (x, z) and the body's extent along x, z and y, in LDU from the part origin (-Y up; studs not counted).
LDRAW = {
    "3020.dat": {"studs": [(x, z) for x in (-30, -10, 10, 30) for z in (-10, 10)], "x": (-40, 40), "z": (-20, 20), "y": (0, 8)},
    "3001.dat": {"studs": [(x, z) for x in (-30, -10, 10, 30) for z in (-10, 10)], "x": (-40, 40), "z": (-20, 20), "y": (0, 24)},
    "2420.dat": {"studs": [(0, 0), (20, 0), (0, 20)], "x": (-10, 30), "z": (-10, 30), "y": (0, 8)},
    "2357.dat": {"studs": [(0, 0), (20, 0), (0, 20)], "x": (-10, 30), "z": (-10, 30), "y": (0, 24)},
}


def _row(xs: tuple[int, ...], z: int = 0) -> list[tuple[int, int]]:
    return [(x, z) for x in xs]


# Slopes: studs on the back row (z = 0), body falling toward -Z; ``flat`` lists the centres of the cells
# with a flat bottom where that is not every cell (inverted slopes: the back row only).
LDRAW.update({
    "3040b.dat": {"studs": _row((0,)), "x": (-10, 10), "z": (-30, 10), "y": (0, 24)},
    "3039.dat": {"studs": _row((-10, 10)), "x": (-20, 20), "z": (-30, 10), "y": (0, 24)},
    "3038.dat": {"studs": _row((-20, 0, 20)), "x": (-30, 30), "z": (-30, 10), "y": (0, 24)},
    "3037.dat": {"studs": _row((-30, -10, 10, 30)), "x": (-40, 40), "z": (-30, 10), "y": (0, 24)},
    "4445.dat": {"studs": _row(tuple(range(-70, 71, 20))), "x": (-80, 80), "z": (-30, 10), "y": (0, 24)},
    "4286.dat": {"studs": _row((0,)), "x": (-10, 10), "z": (-50, 10), "y": (0, 24)},
    "3298.dat": {"studs": _row((-10, 10)), "x": (-20, 20), "z": (-50, 10), "y": (0, 24)},
    "3297.dat": {"studs": _row((-30, -10, 10, 30)), "x": (-40, 40), "z": (-50, 10), "y": (0, 24)},
    "30363.dat": {"studs": _row((-10, 10)), "x": (-20, 20), "z": (-70, 10), "y": (0, 24)},
    "60481a.dat": {"studs": _row((0,)), "x": (-10, 10), "z": (-30, 10), "y": (0, 48)},
    "4460a.dat": {"studs": _row((0,)), "x": (-10, 10), "z": (-30, 10), "y": (0, 72)},
    "3665a.dat": {"studs": _row((0,)) + _row((0,), -20), "x": (-10, 10), "z": (-30, 10), "y": (0, 24),
                  "flat": _row((0,))},
    "3660.dat": {"studs": _row((-10, 10)) + _row((-10, 10), -20), "x": (-20, 20), "z": (-30, 10), "y": (0, 24),
                 "flat": _row((-10, 10))},
    "3747a.dat": {"studs": _row((-10, 10)) + _row((-10, 10), -20) + _row((-10, 10), -40), "x": (-20, 20),
                  "z": (-50, 10), "y": (0, 24), "flat": _row((-10, 10))},
    "3045.dat": {"studs": [(0, 0)], "x": (-10, 30), "z": (-30, 10), "y": (0, 24)},
    "3046.dat": {"studs": [(0, -20), (0, 0), (20, 0)], "x": (-10, 30), "z": (-30, 10), "y": (0, 24)},
    "3043.dat": {"studs": [], "x": (-20, 20), "z": (-20, 20), "y": (0, 24)},
    "3042.dat": {"studs": [], "x": (-30, 30), "z": (-20, 20), "y": (0, 24)},
    "3041.dat": {"studs": [], "x": (-40, 40), "z": (-20, 20), "y": (0, 24)},
    "3044b.dat": {"studs": [], "x": (-10, 10), "z": (-20, 20), "y": (0, 24)},
    "54200.dat": {"studs": [], "x": (-10, 10), "z": (-10, 10), "y": (-16, 0)},  # origin on the bottom
    "35464.dat": {"studs": [], "x": (-10, 10), "z": (-10, 10), "y": (-16, 0)},
})


def _grid(width: int, depth: int) -> list[tuple[int, int]]:
    """Stud positions of a full ``width`` x ``depth`` rectangle centred on the origin."""
    return [(x, z) for x in range(-10 * (width - 1), 10 * width, 20) for z in range(-10 * (depth - 1), 10 * depth, 20)]


# M12d batch 1, printed by ``python -m brickwfc.ldraw.library`` (cells seated where the bottom plane covers >= 10%).
# ``lower_studs``: studs below the body's top, hidden inside the model's box (the part counts as studless there).
# ``within``: the body lies inside the model's box rather than filling it (the box is the conservative bound).
# ``ground_only``: the bottom is flat but the part takes no stud (a baseplate): no seated cells, the table only.
LDRAW.update({
    # Plate 2 x 16
    "4282.dat": {"studs": _grid(16, 2), "x": (-160, 160), "z": (-20, 20), "y": (0, 8)},
    # Plate 4 x 12
    "3029.dat": {"studs": _grid(12, 4), "x": (-120, 120), "z": (-40, 40), "y": (0, 8)},
    # Plate 6 x 12
    "3028.dat": {"studs": _grid(12, 6), "x": (-120, 120), "z": (-60, 60), "y": (0, 8)},
    # Plate 6 x 16
    "3027.dat": {"studs": _grid(16, 6), "x": (-160, 160), "z": (-60, 60), "y": (0, 8)},
    # Brick 1 x 2 x 2 without Understud
    "3245c.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 48)},
    # ~Brick 1 x 2 x 5 (Obsolete)
    "2454.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 120)},
    # Brick 1 x 1 x 3
    "14716.dat": {"studs": [(0, 0)], "x": (-10, 10), "z": (-10, 10), "y": (0, 72)},
    # Brick 1 x 1 x 5 with Hollow Stud
    "2453a.dat": {"studs": [(0, 0)], "x": (-10, 10), "z": (-10, 10), "y": (0, 120)},
    # Baseplate 16 x 32 with Square Corners; 4 LDU thick in one plate
    "3857.dat": {"studs": _grid(32, 16), "x": (-320, 320), "z": (-160, 160), "y": (0, 4), "within": True,
        "ground_only": True},
    # Baseplate 32 x 32; 4 LDU thick in one plate
    "3811.dat": {"studs": _grid(32, 32), "x": (-320, 320), "z": (-320, 320), "y": (0, 4), "within": True,
        "ground_only": True},
    # Brick 1 x 14 with Groove
    "4217.dat": {"studs": _grid(14, 1), "x": (-140, 140), "z": (-10, 10), "y": (0, 24)},
    # Brick 1 x 2 Log; log profile 9.9 LDU deep
    "30136.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-9.9, 9.9), "y": (0, 24), "within": True},
    # Brick 1 x 2 with Embossed Bricks
    "98283.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 24)},
    # Brick 1 x 4 with Embossed Bricks
    "15533.dat": {"studs": [(-30, 0), (-10, 0), (10, 0), (30, 0)], "x": (-40, 40), "z": (-10, 10), "y": (0, 24)},
    # Technic Brick 1 x 2 with Hole
    "3700.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 24)},
    # Technic Brick 1 x 1 with Hole
    "6541.dat": {"studs": [(0, 0)], "x": (-10, 10), "z": (-10, 10), "y": (0, 24)},
    # Technic Brick 1 x 2 with Axlehole with Open Sides and Stud Blocker
    "32064a.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 24)},
    # Technic Brick 1 x 2 with Reduced Axlehole
    "32064b.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 24)},
    # Cone 1 x 1 with Stop
    "59900.dat": {"studs": [(0, 0)], "x": (-10, 10), "z": (-10, 10), "y": (0, 24)},
    # Cone 1 x 1
    "4589.dat": {"studs": [(0, 0)], "x": (-10, 10), "z": (-10, 10), "y": (0, 24)},
    # Tile 1 x 1 without Groove
    "3070a.dat": {"studs": [], "x": (-10, 10), "z": (-10, 10), "y": (0, 8)},
    # Tile 1 x 1 Round with Groove
    "98138.dat": {"studs": [], "x": (-10, 10), "z": (-10, 10), "y": (0, 8)},
    # Tile 1 x 1 Corner Round
    "25269.dat": {"studs": [], "x": (-10, 10), "z": (-10, 10), "y": (0, 8)},
    # Plate 1 x 1 Round with Open Stud
    "85861.dat": {"studs": [(0, 0)], "x": (-10, 10), "z": (-10, 10), "y": (0, 8)},
    # Plate 1 x 1 with 5 Petals; petals inside the cell
    "24866.dat": {"studs": [(0, 0)], "x": (-9.9, 9.9), "z": (-9.5, 10), "y": (0, 8), "within": True},
    # Plate 1 x 2 with Round Ends and 2 Open Studs
    "35480.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 8)},
    # Panel 1 x 1 x 1 Corner with Rounded Corners
    "6231.dat": {"studs": [], "x": (-10, 10), "z": (-10, 10), "y": (0, 24)},
    # Panel 1 x 2 x 1 with Square Corners
    "4865a.dat": {"studs": [], "x": (-20, 20), "z": (-10, 10), "y": (0, 24)},
    # Panel 1 x 2 x 1 with Rounded Corners
    "4865b.dat": {"studs": [], "x": (-20, 20), "z": (-10, 10), "y": (0, 24)},
    # Panel 1 x 2 x 2 Reinforced
    "87552.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 48)},
    # Panel 1 x 2 x 2 with Hollow Studs
    "4864b.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 48)},
    # Panel 1 x 2 x 3 with Hollow Studs
    "2362b.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 72)},
    # Tile 2 x 2 Corner
    "14719.dat": {"studs": [], "x": (-10, 30), "z": (-10, 30), "y": (0, 8), "flat": [(0, 0), (0, 20), (20, 0)]},
    # Plate 3 x 3 with 2 x 2 Corner Round
    "30357.dat": {"studs": [(0, 0), (0, 20), (0, 40), (20, 0), (20, 20), (20, 40), (40, 0), (40, 20)],
        "x": (-10, 50), "z": (-10, 50), "y": (0, 8),
        "flat": [(0, 0), (0, 20), (0, 40), (20, 0), (20, 20), (20, 40), (40, 0), (40, 20)]},
    # Tile 2 x 2 Corner Round
    "27925.dat": {"studs": [], "x": (-10, 30), "z": (-30, 10), "y": (0, 8), "flat": [(0, -20), (0, 0), (20, 0)]},
    # Brick 2 x 2 Corner Round with Stud Notch
    "3063b.dat": {"studs": [(0, -20), (20, 0)], "x": (-10, 30), "z": (-30, 10), "y": (0, 24),
        "flat": [(0, -20), (0, 0), (20, 0)]},
    # Brick 2 x 2 Corner Round with Stud Notch and Reinforced Underside
    "85080.dat": {"studs": [(0, -20), (20, 0)], "x": (-10, 30), "z": (-30, 10), "y": (0, 24),
        "flat": [(0, -20), (0, 0), (20, 0)]},
    # Plate 1 x 4 with Two Studs
    "92593.dat": {"studs": [(-30, 0), (30, 0)], "x": (-40, 40), "z": (-10, 10), "y": (0, 8)},
    # Plate 1 x 4 with Two Studs and Groove
    "41740.dat": {"studs": [(-30, 0), (30, 0)], "x": (-40, 40), "z": (-10, 10), "y": (0, 8)},
    # Plate 2 x 2 with 2 Studs on One Edge
    "33909.dat": {"studs": [(-10, 10), (10, 10)], "x": (-20, 20), "z": (-20, 20), "y": (0, 8)},
    # Plate 4 x 4 with 4 Studs on One Edge
    "6179.dat": {"studs": [(-30, 30), (-10, 30), (10, 30), (30, 30)], "x": (-40, 40), "z": (-40, 40), "y": (0, 8)},
    # Plate 3 x 2 with Hole
    "3176.dat": {"studs": [(-10, -10), (-10, 10), (10, -10), (10, 10)], "x": (-20, 20), "z": (-40, 20), "y": (0, 8)},
    # Arch 1 x 4
    "3659.dat": {"studs": [(-30, 0), (-10, 0), (10, 0), (30, 0)], "x": (-40, 40), "z": (-10, 10), "y": (0, 24),
        "flat": [(-30, 0), (30, 0)]},
    # Arch 1 x 6
    "3455.dat": {"studs": [(-50, 0), (-30, 0), (-10, 0), (10, 0), (30, 0), (50, 0)], "x": (-60, 60), "z": (-10, 10),
        "y": (0, 24), "flat": [(-50, 0), (50, 0)]},
    # Arch 1 x 6 Raised
    "92950.dat": {"studs": [(-50, 0), (-30, 0), (-10, 0), (10, 0), (30, 0), (50, 0)], "x": (-60, 60), "z": (-10, 10),
        "y": (0, 24), "flat": [(-50, 0), (50, 0)]},
    # Arch 1 x 4 x 2
    "6182.dat": {"studs": [(-30, 0), (-10, 0), (10, 0), (30, 0)], "x": (-40, 40), "z": (-10, 10), "y": (0, 48),
        "flat": [(-30, 0), (30, 0)]},
    # Arch 1 x 6 x 2 with Thick Top and Reinforced Underside
    "3307.dat": {"studs": [(-50, 0), (-30, 0), (-10, 0), (10, 0), (30, 0), (50, 0)], "x": (-60, 60), "z": (-10, 10),
        "y": (0, 48), "flat": [(-50, 0), (50, 0)]},
    # Arch 1 x 3 x 2 with Curved Top
    "6005.dat": {"studs": [], "lower_studs": [(0, 0)], "x": (-10, 10), "z": (-50, 10), "y": (0, 48),
        "flat": [(0, -40)]},
    # Slope Brick 65 2 x 2 x 2 with Centre Tube
    "3678b.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-30, 10), "y": (0, 48)},
    # Slope Brick 75 2 x 2 x 3 with Solid Studs
    "3684c.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-30, 10), "y": (0, 72)},
    # Slope Brick 33 3 x 3
    "4161.dat": {"studs": [(-20, 0), (0, 0), (20, 0)], "x": (-30, 30), "z": (-50, 10), "y": (0, 24)},
    # Slope Brick 33 3 x 6
    "3939.dat": {"studs": [(-50, 0), (50, 0)], "x": (-60, 60), "z": (-50, 10), "y": (0, 24),
        "flat": [(-50, -40), (-50, -20), (-50, 0), (-30, -40), (-10, -40), (10, -40), (30, -40), (50, -40), (50, -20), (50, 0)]},
    # Slope Brick 33 3 x 3 Double Convex
    "3675.dat": {"studs": [(0, 0)], "x": (-10, 50), "z": (-50, 10), "y": (0, 24)},
    # Slope Brick 33 2 x 2 Double; 14 LDU tall in a 3-plate box
    "3300.dat": {"studs": [], "x": (-20, 20), "z": (-20, 20), "y": (10, 24), "within": True},
    # Slope Brick 33 2 x 4 Double; 14 LDU tall in a 3-plate box
    "3299.dat": {"studs": [], "x": (-40, 40), "z": (-20, 20), "y": (10, 24), "within": True},
    # Slope Brick 45 1 x 2 Triple
    "3048b.dat": {"studs": [], "x": (-20, 20), "z": (-10, 10), "y": (0, 24)},
    # Slope Brick 31 1 x 2 x 0.667; 15.6 LDU tall in 2 plates
    "85984.dat": {"studs": [], "x": (-20, 20), "z": (-10, 10), "y": (-15.6, 0), "within": True},
    # Slope Plate 45.73 2 x 1
    "92946.dat": {"studs": [], "lower_studs": [(0, 10)], "x": (-10, 10), "z": (-20, 20), "y": (-16, 8)},
    # Brick 2 x 1 x 1.333 with Curved Top
    "6091.dat": {"studs": [], "lower_studs": [(0, 0)], "x": (-10, 10), "z": (-30, 10), "y": (0, 32),
        "flat": [(0, -20)]},
    # Brick 1 x 4 x 1.333 with Curved Top
    "6191.dat": {"studs": [], "x": (-40, 40), "z": (-10, 10), "y": (0, 32)},
    # Brick 1 x 2 with Curved Top
    "37352.dat": {"studs": [], "x": (-20, 20), "z": (-10, 10), "y": (0, 24)},
    # Brick 2 x 3 with Curved Top
    "6215.dat": {"studs": [(-10, -10), (-10, 10), (10, -10), (10, 10)], "x": (-20, 40), "z": (-20, 20), "y": (0, 24)},
    # Slope Brick Curved 3 x 1
    "50950.dat": {"studs": [], "x": (-10, 10), "z": (-30, 30), "y": (0, 24), "flat": [(0, -20), (0, 0)]},
    # Slope Brick Curved 4 x 1
    "61678.dat": {"studs": [], "x": (-10, 10), "z": (-40, 40), "y": (0, 24), "flat": [(0, -30), (0, -10)]},
    # Slope Brick Curved 2 x 1
    "11477.dat": {"studs": [], "x": (-10, 10), "z": (-20, 20), "y": (-16, 0), "flat": [(0, -10)]},
    # Slope Brick Curved 2 x 2 x 0.667
    "15068.dat": {"studs": [], "x": (-20, 20), "z": (-20, 20), "y": (-16, 0), "flat": [(-10, -10), (10, -10)]},
    # Slope Brick Curved 4 x 1 Double
    "93273.dat": {"studs": [], "x": (-10, 10), "z": (-40, 40), "y": (-16, 0), "flat": [(0, -30), (0, 30)]},
    # Brick 1 x 1 x 0.667 with Curved Top
    "49307.dat": {"studs": [], "x": (-10, 10), "z": (-10, 10), "y": (-16, 0)},
})
# M12d batch 2: frames and fences. ``rise``: cells (studless on top) over which the body rises above the box by less
# than a plate (a collar); ``offgrid_studs``: studs between cell centres (not usable on the grid).
LDRAW.update({
    "60592.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 48)},
    "60593.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 72)},
    "2377.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 48)},
    "4863.dat": {"studs": [(-30, 0), (-10, 0), (10, 0), (30, 0)], "x": (-40, 40), "z": (-10, 10), "y": (0, 48)},
    "2493b.dat": {"studs": [(-30, 0), (-10, 0), (10, 0), (30, 0)], "x": (-40, 40), "z": (-10, 10), "y": (0, 120)},
    "4035.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 72)},
    "30044.dat": {"studs": [], "offgrid_studs": [(0, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 64)},
    "60594.dat": {"studs": [(-10, 0), (10, 0)], "rise": [(-30, 0), (30, 0)], "x": (-40, 40), "z": (-10, 10), "y": (-4, 72)},
    "6556.dat": {"studs": [(-10, 0), (10, 0)], "rise": [(-30, 0), (30, 0)], "x": (-40, 40), "z": (-10, 10), "y": (-4, 72)},
    "60596.dat": {"studs": [(-10, 0), (10, 0)], "rise": [(-30, 0), (30, 0)], "x": (-40, 40), "z": (-10, 10),
                  "y": (-4, 144)},
    "30179.dat": {"studs": [(-10, 0), (10, 0)], "rise": [(-30, 0), (30, 0)], "x": (-40, 40), "z": (-10, 10),
                  "y": (-4, 144)},
    "30055.dat": {"studs": [(-30, 0), (30, 0)], "x": (-40, 40), "z": (-10, 10), "y": (0, 48)},
    "3633.dat": {"studs": [], "x": (-40, 40), "z": (-10, 10), "y": (0, 24)},
    "3185.dat": {"studs": [], "x": (-40, 40), "z": (-10, 10), "y": (0, 48)},
})
# M12d batch 3: parts with keep-out cells; the box their studs and flat bottom belong to (what sticks out of it, and
# the side studs, are checked against their keep-out cells in test_keep_out).
LDRAW.update({
    "32028.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 8)},
    "4510.dat": {"studs": [(x, 0) for x in range(-70, 71, 20)], "x": (-80, 80), "z": (-10, 10), "y": (0, 8)},
    "30586.dat": {"studs": [(x, 0) for x in range(-70, 71, 20)], "x": (-80, 80), "z": (-30, 10), "y": (0, 8),
                  "flat": [(x, z) for x in range(-70, 71, 20) for z in (-20, 0)]},
    "87087.dat": {"studs": [(0, 0)], "x": (-10, 10), "z": (-10, 10), "y": (0, 24)},
    "47905.dat": {"studs": [(0, 0)], "x": (-10, 10), "z": (-10, 10), "y": (0, 24)},
    "30414.dat": {"studs": [(x, 0) for x in (-30, -10, 10, 30)], "x": (-40, 40), "z": (-10, 10), "y": (0, 24)},
    "44728.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 8)},
    "93274.dat": {"studs": [(-10, 0), (10, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 8)},
    "2921.dat": {"studs": [(0, 0)], "x": (-10, 10), "z": (-10, 10), "y": (0, 24)},
})
# M12d batch 4: jumpers; the one stud sits between the cells (off the grid), so the top counts as studless.
LDRAW.update({
    "3794a.dat": {"studs": [], "offgrid_studs": [(0, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 8)},
    "3794b.dat": {"studs": [], "offgrid_studs": [(0, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 8)},
    "15573.dat": {"studs": [], "offgrid_studs": [(0, 0)], "x": (-20, 20), "z": (-10, 10), "y": (0, 8)},
    "87580.dat": {"studs": [], "offgrid_studs": [(0, 0)], "x": (-20, 20), "z": (-20, 20), "y": (0, 8)},
})
SLOPES = [p for p in CATALOG.values() if p.kind == "slope"]
CORNERS = [CATALOG["plate2x2_corner"], CATALOG["brick2x2_corner"]]
FAMILY = CORNERS + [CATALOG[n] for n in ("plate1x1", "plate1x2", "brick1x2", "brick2x2", "tile1x1")]


def check_build(grid: np.ndarray, parts: PartSet) -> list[PlacedPart]:
    placed, errors = extract_parts(grid, parts)
    assert errors == []
    assert is_stable(placed, parts.solid[grid])
    return placed


def test_corner_has_four_orientations_of_three_cells() -> None:
    for part in CORNERS:
        shapes = shapes_of([part])
        assert [s.turn for s in shapes] == [0, 1, 2, 3]
        assert all(s.cells == 3 * part.height and (s.size_x, s.size_z) == (2, 2) for s in shapes)
        notches = {next((dz, dx) for dz in (0, 1) for dx in (0, 1) if not s.covers(dz, dx)) for s in shapes}
        assert notches == {(0, 0), (0, 1), (1, 0), (1, 1)}
    # Rectangles keep their M8 orientations and names; turning them twice gives the same shape.
    plate = CATALOG["plate2x4"]
    assert [s.name for s in shapes_of([plate])] == ["plate2x4", "plate2x4_r90"]
    assert canonical(plate, 2) == Shape(plate, 0) and canonical(plate, 3) == Shape(plate, True)
    assert [s.name for s in shapes_of([CATALOG["plate2x2"]])] == ["plate2x2"]


@pytest.mark.parametrize("file", list(LDRAW))
def test_placement_matches_the_ldraw_part(file: str) -> None:
    """Every orientation's .ldr placement puts the real part's studs on the model's stud cells and its
    body exactly over the model's cells and layers (or, ``within``, inside them)."""
    part = BY_FILE[file]
    facts = LDRAW[file]
    for shape in shapes_of([part]) + [Shape(part, turn) for turn in range(4)]:
        placed = PlacedPart(shape, RED, 2, 3, 4)
        p = placed.placement()
        r, origin = np.array(p.rotation, dtype=float).reshape(3, 3), np.array(p.position)
        def cells(points: list[tuple[int, int]]) -> set[tuple[int, int]]:
            return {tuple(np.round((r @ (x, 0, z) + origin)[[0, 2]] / STUD_LDU).astype(int)) for x, z in points}

        assert cells(facts["studs"]) == {(x, z) for _, z, x in placed.stud_cells()}, shape.name
        bottom = {(x, z) for _, z, x in placed.bottom_cells()}
        if facts.get("ground_only"):
            assert part.ground_only and placed.seated_cells() == []
            assert {(x, z) for _, z, x in PlacedPart(shape, RED, 0, 3, 4).contact_cells()} == bottom
        else:
            flat = cells(facts["flat"]) if "flat" in facts else bottom
            assert flat == {(x, z) for _, z, x in placed.seated_cells()}, shape.name
        assert cells(facts.get("lower_studs", [])) <= bottom - {(x, z) for _, z, x in placed.stud_cells()}
        for x, z in facts.get("offgrid_studs", []):  # half a stud from every cell centre along x or z
            sx, sz = (r @ (x, 0, z) + origin)[[0, 2]] / STUD_LDU
            assert sx % 1 == 0.5 or sz % 1 == 0.5, shape.name  # cell centres are at whole studs
        rise, y_facts = facts.get("rise", []), facts["y"]
        if rise:  # a collar under a plate tall, over studless top cells: nothing may be placed above those anyway
            assert cells(rise) <= bottom - {(x, z) for _, z, x in placed.stud_cells()} and -PLATE_LDU < y_facts[0] < 0
            y_facts = (0, y_facts[1])
        corners = np.array([r @ (x, 0, z) + origin for x in facts["x"] for z in facts["z"]]) / STUD_LDU
        top, low = (-(origin[1] + y) / PLATE_LDU for y in y_facts)
        box = ((placed.x - 0.5, placed.x + shape.size_x - 0.5), (placed.z - 0.5, placed.z + shape.size_z - 0.5),
               (placed.layer, placed.top + 1))
        real = ((corners[:, 0].min(), corners[:, 0].max()), (corners[:, 2].min(), corners[:, 2].max()), (low, top))
        if facts.get("within"):
            assert all(b[0] <= v[0] + 1e-9 and v[1] <= b[1] + 1e-9 for b, v in zip(box, real)), shape.name
            assert real != box  # else it is not "within"
        else:
            assert real == box, shape.name


def test_corner_integrity_rules() -> None:
    parts = part_tileset([CATALOG["plate2x2_corner"], CATALOG["plate1x1"]], [RED])
    index = {info: t for t, info in enumerate(parts.infos)}
    corner = Shape(CATALOG["plate2x2_corner"], 0)
    notch = next((dz, dx) for dz in (0, 1) for dx in (0, 1) if not corner.covers(dz, dx))
    assert len([i for i in parts.infos if i.shape == corner]) == 3
    # A 1x1 plate fits in the notch: every cell is covered once, the corner is whole.
    grid = np.full((1, 2, 2), index[parts.infos[0]])
    for dz, dx in corner.footprint:
        grid[0, dz, dx] = next(t for t, i in enumerate(parts.infos) if i.shape == corner and (i.offset_z, i.offset_x) == (dz, dx))
    grid[0, notch[0], notch[1]] = next(t for t, i in enumerate(parts.infos) if i.solid and i.shape.part.name == "plate1x1")
    placed, errors = extract_parts(grid, parts)
    assert errors == [] and sorted(p.shape.name for p in placed) == ["plate1x1", "plate2x2_corner"]


@pytest.mark.parametrize("seed_block", range(4))
def test_wfc_builds_with_corners_are_whole_and_supported(seed_block: int) -> None:
    parts = part_tileset(FAMILY, [RED], empty_weight=1.0)
    turns: set[tuple[str, int]] = set()
    for seed in range(seed_block * BUILDS // 4, (seed_block + 1) * BUILDS // 4):
        result = run(parts.tileset, (5, 4, 4), seed, constraints=[SupportConstraint(parts)], max_backtracks=500)
        assert result.grid is not None
        turns |= {(p.shape.part.name, p.shape.turn) for p in check_build(result.grid, parts) if p.shape.part in CORNERS}
    assert {t for _, t in turns} == {0, 1, 2, 3}


def test_bottom_up_builds_with_corners_are_whole_and_supported() -> None:
    parts = part_tileset(FAMILY, [RED, BLUE], empty_weight=1.0)
    for kwargs in ({}, {"any_offset": True}, {"any_offset": True, "balanced": True, "bridge": True, "connect": True}):
        builder = BottomUpBuilder(parts, **kwargs)
        turns: set[int] = set()
        for seed in range(BUILDS):
            grid = builder.build((7, 4, 4), np.random.default_rng(seed))
            placed = check_build(grid, parts)
            turns |= {p.shape.turn for p in placed if p.shape.part in CORNERS}
            if kwargs.get("balanced"):  # the balance check is exact for corners too
                assert not tipping_clusters(placed)
                assert required_clutch(placed, grid.shape) < np.inf
        assert turns == {0, 1, 2, 3}


def test_corner_physics() -> None:
    corner = PlacedPart(Shape(CATALOG["brick2x2_corner"], 0), RED, 0, 0, 0)
    (dz, dx) = next((dz, dx) for dz in (0, 1) for dx in (0, 1) if not corner.shape.covers(dz, dx))
    cx, cz = corner.centre()
    assert (cx, cz) == pytest.approx((1 + (0.5 - dx) / 3, 1 + (0.5 - dz) / 3))  # pulled away from the notch
    assert required_clutch([corner], (4, 2, 2)) == 0.0
    # A 2x2 plate on the corner brick overhangs the notch; its centre is over the L's hull: no clutch needed.
    plate = PlacedPart(Shape(CATALOG["plate2x2"]), BLUE, 3, 0, 0)
    assert required_clutch([corner, plate], (4, 2, 2)) == 0.0
    # A 1x6 plate along the full arm (the row without the notch) sticks out 4 studs: the corner brick's
    # weight keeps the build upright, but the plate needs grip to stay on.
    arm = 1 - dz
    cantilever = PlacedPart(Shape(CATALOG["plate1x6"]), BLUE, 3, 0, arm)
    assert 0 < required_clutch([corner, cantilever], (4, 2, 6)) < np.inf


def test_every_orientation_roundtrips_through_ldraw(tmp_path: Path) -> None:
    placed, x = [], 0
    for part in CORNERS + SLOPES + [CATALOG["plate2x4"], CATALOG["brick1x2"]]:
        for turn in range(4):
            shape = Shape(part, turn)
            placed.append(PlacedPart(shape, RED, turn, x, turn))
            x += shape.size_x + 1
    path = tmp_path / "turns.ldr"
    write_ldr((p.placement() for p in placed), path, "turns")
    recovered, report = voxelize(flatten(path.read_text()))
    assert report.kept == len(placed) and report.tilted == report.off_grid == report.overlapping == 0
    expected = sorted((canonical(p.shape.part, p.shape.turn).name, p.layer, p.x, p.z) for p in placed)
    assert sorted((p.shape.name, p.layer, p.x, p.z) for p in recovered) == expected


def test_catalog_check_has_every_orientation_without_overlaps() -> None:
    placed = layout()
    cells = [cell for p in placed for cell in p.cells()]
    assert len(cells) == len(set(cells))
    shown = {(p.shape.part.name, p.shape.turn) for p in placed}
    for part in CORNERS + SLOPES:
        assert {(part.name, s.turn) for s in shapes_of([part])} <= shown


# Builds from the M8 catalog are unchanged by the M12b geometry (fingerprints recorded before it).
M8_NAMES = ("plate1x2", "plate2x4", "brick1x1", "brick1x2", "brick2x4", "brick1x2_2877", "tile1x2", "tile2x2",
            "tile1x2_2412b")
M8_FINGERPRINTS = {
    "d": ["0bd1e3906fc701c6", "45bc7804d50b24d8", "f0fadc23d2b06ef9"],
    "d2": ["875e568f3723130b", "1bd0e74c558e24b2", "eb09245ebb62100b"],
    # seeds 0 and 1 changed with the _fit_key fix (M12b completeness; connect rounds only, see test_bottomup_proposal)
    "d2_connect": ["8f4e531e3e4e29ac", "10ef9c6b62d4a2e4", "5fffaad27298a09b"],
    "wfc": ["d209830a142d1936", "f6dc0023c8746426", "66bc5e512a85feed"],
}


def test_m8_builds_are_unchanged() -> None:
    parts = part_tileset([CATALOG[n] for n in M8_NAMES], [RED, BLUE], empty_weight=0.5)

    def digest(grid: np.ndarray) -> str:
        placed = check_build(grid, parts)
        text = ";".join(f"{p.shape.name},{p.color.name},{p.layer},{p.x},{p.z}" for p in placed)
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    inventory = {(n, c): 6 for n in M8_NAMES for c in ("red", "blue")}
    builders = {
        "d": BottomUpBuilder(parts),
        "d2": BottomUpBuilder(parts, any_offset=True),
        "d2_connect": BottomUpBuilder(parts, any_offset=True, balanced=True, bridge=True, connect=True, connect_rounds=3),
    }
    for name, builder in builders.items():
        assert [digest(builder.build((9, 6, 6), np.random.default_rng(s), inventory)) for s in range(3)] == M8_FINGERPRINTS[name]
    wfc = [digest(run(parts.tileset, (5, 4, 4), s, 20, [SupportConstraint(parts)]).grid) for s in range(3)]
    assert wfc == M8_FINGERPRINTS["wfc"]


# Slopes ------------------------------------------------------------------------------------------------

SLOPE_FAMILY = [CATALOG[n] for n in ("slope45_2x1", "slope45_2x2", "slope45inv_2x1", "slope45inv_2x2",
                                     "slope45convex_2x2", "slope31_1x1x2", "brick2x2_corner", "plate1x1",
                                     "plate1x2", "plate2x2", "brick1x1", "brick1x2")]
SLOPE_KINDS = {"slope45_2x1", "slope45_2x2", "slope45inv_2x1", "slope45inv_2x2", "slope45convex_2x2", "slope31_1x1x2"}


def faces_clear(placed: list[PlacedPart], shape: tuple[int, int, int]) -> bool:
    """Independent of ``extract_parts``: nothing directly above a studless top cell (a sloped face, a tile)
    or directly below an open bottom cell (an inverted slope's underside), and no cell taken twice."""
    taken: dict[tuple[int, int, int], PlacedPart] = {}
    for part in placed:
        for cell in part.cells():
            assert cell not in taken
            taken[cell] = part
    for part in placed:
        studs, seated = set(part.stud_cells()), set(part.seated_cells())
        if any((y + 1, z, x) in taken for y, z, x in part.top_cells() if (y, z, x) not in studs):
            return False
        if any((y - 1, z, x) in taken for y, z, x in part.bottom_cells() if (y, z, x) not in seated):
            return False
    return True


def test_slope_shapes() -> None:
    plain = shapes_of([CATALOG["slope45_2x2"]])
    assert [s.name for s in plain] == ["slope45_2x2", "slope45_2x2_r90", "slope45_2x2_r180", "slope45_2x2_r270"]
    # The studs (back row) face a different side in each turn; the bottom is flat everywhere.
    studded_rows = {frozenset(s.geometry.studded) for s in plain}
    assert len(studded_rows) == 4 and all(len(s.geometry.seated) == 4 for s in plain)
    inverted = Shape(CATALOG["slope45inv_2x2"])
    assert len(inverted.geometry.studded) == 4 and len(inverted.geometry.seated) == 2
    assert [s.turn for s in shapes_of([CATALOG["slope45double_2x1"]])] == [0, 1]  # a ridge: 180 degrees is the same
    assert CATALOG["slope31_1x1x2"].height == 2 and CATALOG["slope75_2x1x3"].height == 9
    assert BY_FILE["3660a.dat"] is BY_FILE["3660.dat"] and BY_FILE["3665.dat"] is CATALOG["slope45inv_2x1"]


def test_nothing_on_a_slope_face_or_under_an_inverted_slope() -> None:
    parts = part_tileset(SLOPE_FAMILY, [RED])
    slope = PlacedPart(Shape(CATALOG["slope45_2x2"]), RED, 0, 0, 0)
    stud = next(c for c in slope.stud_cells())
    face = next(c for c in slope.top_cells() if c not in slope.stud_cells())

    def errors(*placed: PlacedPart) -> list[str]:
        return extract_parts(tile_grid(list(placed), parts), parts)[1]

    on_studs = PlacedPart(Shape(CATALOG["plate1x1"]), RED, 3, stud[2], stud[1])
    on_face = PlacedPart(Shape(CATALOG["plate1x1"]), RED, 3, face[2], face[1])
    assert errors(slope, on_studs) == []
    assert any("sits on" in e for e in errors(slope, on_face))
    inverted = PlacedPart(Shape(CATALOG["slope45inv_2x1"]), RED, 3, 0, 0)
    seat = inverted.seated_cells()[0]
    hang = next(c for c in inverted.bottom_cells() if c not in inverted.seated_cells())
    under_seat = PlacedPart(Shape(CATALOG["brick1x1"]), RED, 0, seat[2], seat[1])
    under_hang = PlacedPart(Shape(CATALOG["brick1x1"]), RED, 0, hang[2], hang[1])
    assert errors(under_seat, inverted) == []
    assert any("open bottom" in e for e in errors(under_seat, under_hang, inverted))
    # Only the back row's stud holds it up: a part under the open bottom alone does not count, and is refused.
    assert not is_stable([under_hang, inverted], np.ones((6, 2, 1), dtype=bool))
    # The rules are in the tileset too: no tile above a sloped face, no solid tile below an open bottom.
    face_tile = next(t for t, i in enumerate(parts.infos) if i.studless_top and i.shape == slope.shape)
    open_tile = next(t for t, i in enumerate(parts.infos) if i.open_bottom)
    assert parts.tileset.compat[UP][face_tile].tolist() == (~parts.solid).tolist()
    assert parts.tileset.compat[DOWN][open_tile].tolist() == (~parts.solid).tolist()


@pytest.mark.parametrize("seed_block", range(4))
def test_wfc_builds_with_slopes_are_whole_and_supported(seed_block: int) -> None:
    parts = part_tileset(SLOPE_FAMILY, [RED], empty_weight=1.0)
    names: set[str] = set()
    for seed in range(seed_block * BUILDS // 4, (seed_block + 1) * BUILDS // 4):
        result = run(parts.tileset, (7, 4, 4), seed, constraints=[SupportConstraint(parts)], max_backtracks=500)
        assert result.grid is not None
        placed = check_build(result.grid, parts)
        assert faces_clear(placed, result.grid.shape)
        names |= {p.shape.part.name for p in placed}
    assert names & SLOPE_KINDS


def test_bottom_up_builds_with_slopes_are_whole_and_supported() -> None:
    parts = part_tileset(SLOPE_FAMILY, [RED, BLUE], empty_weight=1.0)
    for kwargs in ({}, {"any_offset": True}, {"any_offset": True, "balanced": True, "bridge": True, "connect": True}):
        builder = BottomUpBuilder(parts, **kwargs)
        shapes: set[tuple[str, int]] = set()
        for seed in range(BUILDS):
            grid = builder.build((10, 4, 4), np.random.default_rng(seed))
            placed = check_build(grid, parts)
            assert faces_clear(placed, grid.shape)
            shapes |= {(p.shape.part.name, p.shape.turn) for p in placed}
            if kwargs.get("balanced"):
                assert not tipping_clusters(placed)
                assert required_clutch(placed, grid.shape) < np.inf
        assert {name for name, _ in shapes} >= SLOPE_KINDS
        assert {turn for name, turn in shapes if name == "slope45_2x2"} == {0, 1, 2, 3}


def test_slope_physics() -> None:
    # A tower of two 2x2 bricks with a 2x2 slope on top stands without grip and is supported.
    tower = [PlacedPart(Shape(CATALOG["brick2x2"]), RED, 0, 0, 0), PlacedPart(Shape(CATALOG["brick2x2"]), BLUE, 3, 0, 0),
             PlacedPart(Shape(CATALOG["slope45_2x2"]), RED, 6, 0, 0)]
    filled = np.zeros((9, 2, 2), dtype=bool)
    for cell in (c for p in tower for c in p.cells()):
        filled[cell] = True
    assert is_stable(tower, filled) and required_clutch(tower, (9, 2, 2)) == 0.0
    # A 33-degree inverted slope alone on the table touches it with its back row only: it tips over.
    inverted = PlacedPart(Shape(CATALOG["slope33inv_3x2"]), RED, 0, 0, 0)
    assert tipping_clusters([inverted]) and required_clutch([inverted], (3, 3, 2)) == np.inf
    # Raised on a 1x2 brick under its back row, it hangs out 2 studs; clicked onto a baseplate, grip holds it.
    seat_z = inverted.seated_cells()[0][1]
    base = PlacedPart(Shape(CATALOG["brick1x2"]), BLUE, 0, 0, seat_z)
    raised = PlacedPart(inverted.shape, RED, 3, 0, 0)
    assert 0 < required_clutch([base, raised], (6, 3, 2), baseplate=True) < np.inf
    # A cheese slope is 2 plates tall: a plate next to it on the same brick has its top one layer lower.
    cheese = PlacedPart(Shape(CATALOG["slope31_1x1x2"]), RED, 3, 0, 0)
    assert cheese.top == 4 and required_clutch([tower[0], cheese], (9, 2, 2)) == 0.0


def test_coverage_counts_m8_and_new_parts() -> None:
    from brickwfc.experiments.coverage import set_coverage

    mpd = """0 FILE main.ldr
1 4 0 -8 0 1 0 0 0 1 0 0 0 1 3020.dat
1 4 0 -32 10 1 0 0 0 1 0 0 0 1 3039.dat
1 4 80 -24 10 1 0 0 0 1 0 0 0 1 3660a.dat
1 4 0 -40 0 1 0 0 0 1 0 0 0 1 3820.dat
0 NOFILE
"""
    row = set_coverage("fake-1", mpd, on_grid=True)
    assert (row.parts, row.catalog_m8, row.catalog) == (4, 1, 3)
    assert (row.on_grid_m8, row.on_grid) == (1, 3)


def test_learn_only_writes_versioned_fold_statistics(tmp_path: Path) -> None:
    import json

    from brickwfc.bricks.style import StyleStats
    from brickwfc.experiments.style import folds, learn_only

    sets = [f"s{i}" for i in range(8)]
    slope = PlacedPart(Shape(CATALOG["slope45_2x2"]), RED, 0, 0, 0)
    per_model = {s: StyleStats().add([slope]) for s in sets}
    assert learn_only(sets, per_model, 4, 0, "vt", "full", tmp_path) == 0
    for i, held_out in enumerate(folds(sets, 4, 0)):
        data = json.loads((tmp_path / f"style_fold{i}_vt.json").read_text(encoding="utf-8"))
        assert data["catalog"] == "m12d" and data["parts"]["slope45_2x2"] == len(sets) - len(held_out)
        assert StyleStats.load(tmp_path / f"style_fold{i}_vt.json").models == len(sets) - len(held_out)


def test_catalog_figure_counts_slopes_and_corners(tmp_path: Path) -> None:
    import json

    from brickwfc.alt.candidates import Candidate
    from brickwfc.experiments.catalog_figure import kinds

    placed = (PlacedPart(Shape(CATALOG["brick2x2"]), RED, 0, 0, 0), PlacedPart(Shape(CATALOG["slope45_2x2"]), RED, 3, 0, 0),
              PlacedPart(Shape(CATALOG["plate2x2_corner"], 2), BLUE, 0, 2, 0))
    candidate = Candidate(7, placed, (), 0.0, 1.0, 0.1, 1)
    lines = [json.dumps({"key": {}}), json.dumps(candidate.to_json())]
    (tmp_path / "candidates.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (tmp_path / "stats.json").write_text("{}", encoding="utf-8")
    assert kinds(tmp_path, 7) == {"brick": 1, "slope": 1, "corner": 1}
    # Candidates round-trip their parts' turns (0-3), so corners and slopes keep their orientation.
    assert Candidate.from_json(candidate.to_json()).placed == placed


def test_pipeline_reads_the_inventory_with_the_chosen_catalog(tmp_path: Path, capsys: pytest.CaptureFixture[str],
                                                             style_dir: tuple[Path, Path]) -> None:
    from brickwfc.alt.inputs import load_source
    from brickwfc.alt.pipeline import main

    model = tmp_path / "model.ldr"
    placed = [PlacedPart(Shape(CATALOG["brick2x2"]), RED, 0, 0, 0), PlacedPart(Shape(CATALOG["slope45_2x2"]), RED, 3, 0, 0),
              PlacedPart(Shape(CATALOG["plate2x2_corner"]), BLUE, 0, 3, 0)]
    write_ldr((p.placement() for p in placed), model, "model")
    assert set(load_source(str(model)).inventory) == {(p.shape.part.name, p.color.name) for p in placed}
    assert set(load_source(str(model), catalog="m8").inventory) == {("brick2x2", "red")}
    for catalog, recognized in (("m8", 1), ("full", 3)):
        args = [str(model), "--n", "2", "--k", "1", "--workers", "1", "--out", str(tmp_path / catalog), "--catalog", catalog,
                "--style-dir", str(style_dir[0]), "--sets-file", str(style_dir[1])]
        assert main(args) == 0
        assert f"{recognized} parts recognized" in capsys.readouterr().out


def test_preview_draws_slopes_and_leaves_other_builds_alone() -> None:
    from brickwfc.bricks.build import SLOPE_LIP, placed_colors, slope_profiles
    from brickwfc.bricks.support import studded
    from brickwfc.render3d import face_shade, render_voxels

    def picture(placed: list[PlacedPart], shape: tuple[int, int, int], cuts: bool = True) -> np.ndarray:
        filled = np.zeros(shape, dtype=bool)
        for part in placed:
            for cell in part.cells():
                filled[cell] = True
        profiles = slope_profiles(placed, shape) if cuts else None
        tops, bottoms = (None, None) if profiles is None else profiles
        return np.array(render_voxels(filled, placed_colors(placed, shape), studs=studded(placed, shape),
                                      tops=tops, bottoms=bottoms))

    # No slopes: no cuts, and full cuts draw exactly what no cuts draw.
    bricks = [PlacedPart(Shape(CATALOG["brick2x2"]), RED, 0, 0, 0), PlacedPart(Shape(CATALOG["plate2x2_corner"]), BLUE, 3, 0, 0)]
    assert slope_profiles(bricks, (4, 2, 2)) is None
    filled = np.ones((1, 2, 2), dtype=bool)
    colors = np.full((1, 2, 2, 3), 200, dtype=np.uint8)
    full = render_voxels(filled, colors, tops=np.ones((1, 2, 2, 4)), bottoms=np.zeros((1, 2, 2, 4)))
    assert (np.array(full) == np.array(render_voxels(filled, colors))).all()

    # A 45-degree 2x2 slope falling toward -z (turn 0): full height over its stud row, down to the lip at
    # its low edge; the plane crosses the three layers of the sloped row.
    slope = PlacedPart(Shape(CATALOG["slope45_2x2"]), RED, 0, 0, 0)
    tops, bottoms = slope_profiles([slope], (3, 2, 2))
    low_row = next(z for _, z, _ in slope.bottom_cells() if not slope.shape.studded(z, 0))
    assert tops[0, low_row, 0].min() == pytest.approx(SLOPE_LIP) and tops[0, low_row, 0].max() == pytest.approx(3)
    assert (tops[:, 1 - low_row] >= 1).all() and (bottoms == 0).all()  # the stud row stays full
    # Facing the viewer (falling toward +x or +z) the face is drawn; facing away it is hidden.
    assert face_shade((2.5, 0.0, 0.0, 2.5)) is not None and face_shade((0.0, 2.5, 2.5, 0.0)) is None  # 45 degrees
    # A slope that faces the viewer looks different from its box.
    toward = PlacedPart(Shape(CATALOG["slope45_2x2"], 2), RED, 0, 0, 0)
    assert not (picture([toward], (3, 2, 2)) == picture([toward], (3, 2, 2), cuts=False)).all()
    # An inverted slope's bottom rises from its flat row toward its front.
    inverted = PlacedPart(Shape(CATALOG["slope45inv_2x1"]), RED, 1, 0, 0)
    _, bottoms = slope_profiles([inverted], (4, 2, 1))
    assert bottoms[1].max() == pytest.approx(3 - SLOPE_LIP) and bottoms[1].min() == pytest.approx(0)
