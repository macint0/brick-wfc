# M8 — part library: plates, bricks, tiles

## What changed

- **Catalog** (`bricks/parts.py`, `CATALOG`): 63 rectangular parts.
  - 24 plates: 1×1 … 1×12, 2×2 … 2×12, 4×4 … 8×8.
  - 15 bricks: 1×1 … 1×16, 2×2 … 2×10, each **3 plate layers** tall (24 LDU).
  - 9 tiles: 1×1 … 1×8, 2×2 … 2×4, with **no studs**.
  - 15 **lookalikes**: parts that fill the same box and have the same studs as a plain part (round
    1×1 plate 6141, 1×2 brick with grille 2877, 1×1 headlight brick 4070, 1×2 grille tile 2412b, …). They
    are separate parts with their own inventory key and `.ldr` file, so a build uses the set's actual
    parts.
  - Left out on purpose: 1×2 jumper plates (3794: one centred stud, connects differently), corner
    (L-shaped) plates and bricks, slopes, Technic.
- **Integrity rules** (`parts.adjacency`, now built with numpy): a part is a box of cells, tied together
  in all 6 directions. Nothing may sit directly on a tile.
- **Support** (`support.py`, `stability.SupportConstraint`): a part must rest on at least one **stud**
  below its bottom layer. A tile's top doesn't count.
- **Physics** (`physics.py`): contacts only at a part's bottom layer; a brick weighs 3 plate cells; a
  tile can push but never grip (no clutch).
- **Bottom-up builder**: places bricks (3 layers at once), skips tile tops, and is 1.8–6× faster
  (array slicing; once a box size doesn't fit at a cell, other parts of that size are skipped). It
  produces identical builds for the same seed as before (checked: 90/90 M11 builds identical).
- **Inventory / voxelize** default to the full catalog. `PLATE_FILES` keeps the four-plate mode, which
  the M9, M11 and M7 learning code still use so their tables reproduce. `experiments/inventory.py`
  gained `--catalog full` and the D2 condition.
- **Exports**: brick origin at −24 LDU per brick (`placement` uses the part's height); tiles render
  without studs in the previews.
- `python -m brickwfc.bricks.catalog_check` writes `out/check/catalog_check.ldr`: every part, unrotated
  and turned, spaced by its assumed footprint, plus a brick/plate/brick/tile tower. **To do (Mac):** open
  it in Studio. Parts that overlap or touch, or a tower with gaps, mean a catalog size or orientation is
  wrong.

## Tests (`tests/test_bricks.py`)

- 100 WFC builds (support constraint, 4×4×5 grid) and 100 bottom-up builds (D and D2, 4×4×7) per part
  family. Every build is whole, nothing rests on a tile, and every part rests on a stud.
  - Families: **plates** (8 sizes), **bricks** (7 sizes), and **mixed** (plates + bricks + tiles +
    lookalikes).
  - There is no tiles-only family: tiles can't be stacked, and real inventories always mix kinds.
- Rule checks: brick tiles stack in order, only empty above a tile, border masks.
- Exports: brick at −24 LDU, plate on a brick at −32, right part files, `.ldr` → voxelize roundtrip.
- Physics checks, a brick counted once by the inventory, and the coverage counter.

## How much of each set can be used now

Reproduce: `python -m brickwfc.experiments.coverage --out out/m8_coverage` (raw: `m8_coverage.json`).
Share of each set's part instances that the generators can use. LDraw primitives (e.g. `4-4cyli.dat`,
from custom parts defined inside a file) are not parts and are not counted.

| set | parts | four plates % | catalog % | most common missing |
|---|---|---|---|---|
| 10018-1 | 1865 | 21 | 85 | 2357 (90), 3794b (69), 2420 (68) |
| 10170-1 | 365 | 9 | 67 | 2921 (16), 2420 (16), 4864b (16) |
| 10020-1 | 444 | 15 | 61 | 6215 (28), 4085c (18), 6091 (10) |
| 10133-1 | 419 | 14 | 60 | 30377 (14), 6091 (12), 2540 (12) |
| 10015-1 | 192 | 12 | 56 | 4036 (14), 4035 (14), 2921 (8) |
| 10014-1 | 170 | 2 | 55 | 4862 (13), 2377 (13), 2921 (10) |
| 10156-1 | 111 | 10 | 52 | 6014 (6), 6015 (6), 4085c (4) |
| 10036-1 | 166 | 8 | 49 | 3820 (6), 2357 (5), 3675 (4) |
| 10129-1 | 1454 | 9 | 49 | 30244 (62), 4274 (32), 3747a (30) |
| 10143-1 | 3457 | 5 | 49 | 3794a (271), 32064a (231), 2780 (72) |
| 10016-1 | 120 | 7 | 43 | 30565 (16), 30562 (8), 4175 (6) |
| 10159-1 | 589 | 8 | 43 | 4865a (19), 3820 (14), 4862 (12) |
| 10013-1 | 162 | 1 | 41 | 30104k02 (42), 4095 (10), 30237 (10) |
| 10019-1 | 1804 | 4 | 41 | 4286 (53), 30565 (52), 30562 (52) |
| 10158-1 | 173 | 8 | 41 | 4864b (17), 30136 (8), 3040b (8) |
| 10124-1 | 677 | 6 | 37 | 3711 (91), 6628 (24), 32293 (14) |
| 10128-1 | 338 | 8 | 37 | 4459 (18), 75535 (18), 30258 (8) |
| 10134-1 | 1491 | 4 | 36 | 72504 (112), 3794b (50), 32123b (50) |
| 10037-1 | 221 | 9 | 35 | 3742 (18), 2453a (11), 3820 (10) |
| 10017-1 | 208 | 4 | 33 | 3039 (28), 3660 (15), 6553 (12) |
| **all** | 14426 | 8 | 51 | |

The usable share goes from **8% to 51%** of all parts (33–85% per set). What remains is mostly corner plates
and bricks (2420, 2357), slopes (3039, 3040b, 3660, 4286), jumpers (3794), Technic (32064a, 2780, 3711) and
special parts.

## First builds from full inventories

With `--catalog full`, both bottom-up builders build set 10019 (746 usable parts, 8,600 cells, 12-plate
grid) with 100% valid builds and 100% of parts used, at 2 s (D) and 5 s (D2) per build. WFC does not
scale to full inventories yet: on the smallest set (10015, 247 tiles) it did not finish 2 builds in
10 minutes. M9b reports this properly.
