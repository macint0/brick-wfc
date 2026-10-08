# M12b step 4 — corner and slope parts

**On main since 2ec12ce:** the 88-part catalog, the coverage files, style v2, the slope-aware preview and the
before/after figure `results/m12b_catalog_before_after.png` with its two summaries. The usable (recognized) share
rises 61% → 69% on the 28 style sets and 51% → 57% on the 20 OMR sets.

## What changed

- **Part geometry per cell** (`bricks/parts.py`). A part can now have:
  - a footprint that is any set of stud cells (an L for corners), not only a `width` × `depth` rectangle;
  - per-cell studs on top (a slope's face has none);
  - per-cell flat ("seated") bottoms (an inverted slope's underside is not flat).

  A `Shape` is a part turned by 0–3 quarter turns. The turn's cells come from the same rotation matrix as
  its `.ldr` placement. `shapes_of` drops turns that give the same cells, so rectangles keep exactly their
  M8 orientations and names; corners and slopes get `_r90`, `_r180`, `_r270`.
- **Rules**, all local, so WFC adjacency, `SupportConstraint` and the bottom-up builder share them:
  - nothing directly above a studless top cell (a tile, a slope face);
  - nothing directly below an open bottom cell (an inverted slope);
  - a part above the ground needs a stud under at least one of its seated cells.
- **Generators and checks**:
  - The bottom-up builder checks non-rectangular parts cell by cell (`_fits_cells`); rectangles keep the
    box checks and the fit map.
  - `support`, `physics` and `balance`: weight acts at the footprint's centroid; contacts are at seated
    cells only; clutch only where the lower cell carries a stud.
  - `voxelize`: reads all four quarter turns and each part's own LDraw origin.
  - `catalog_check`: shows every orientation with yellow 1×1 marker plates.
- **Catalog**: 63 → 88 parts (25 new):
  - one lookalike (4216);
  - 2 corners;
  - 22 slopes.
- **Builds from the M8 catalog are unchanged**:
  - `test_m8_builds_are_unchanged`: fingerprints of D, D2, D2+balance+bridge+connect and WFC, recorded
    before the change.
  - 18 cached alt candidates rebuild part-for-part identical on the rebased branch: `m12_2b` 6372-1 ×2,
    `m12_demo` 6378-1 d2 and wfc, 5891-1 d2_no_connect, `m12b_brickgpt` 6378-1 exact.

## The model and its simplifications

- **Geometry source.** Every new part's geometry was read from its LDraw `.dat` file, resolved through its
  subfiles: stud positions, the flat part of the bottom plane, body extents, origin.
  `tests/test_catalog_shapes.py::test_placement_matches_the_ldraw_part` checks every orientation of every
  new part against these facts. The `.ldr` placement must put the real part's studs on the model's stud
  cells, its flat bottom on the seated cells, and its body exactly over the model's cells and layers.
- **Origins.**
  - Corners: on the corner stud.
  - Slopes: on the top face over the back (studded) row, falling toward LDraw −Z.
  - Cheese slopes 54200 and 35464: on the **bottom** face (`Part.origin_top=False`).
- **A slope is its full bounding box.** The space above the sloped face is unusable: nothing may sit on it,
  as on a tile. This is conservative, since a real part may overhang a slope face. A slope's weight is
  counted as its full box.
- **Inverted slopes** rest on their back row only. Nothing may be directly under the sloped underside,
  although a real build could tuck a part partly under it.
- **Heights** are exact in plates: slopes 3 plates; 65° 2×1×2 6 plates; 75° 2×1×3 9 plates; cheese slopes 2.
- **"~Moved to" file names** map to the same part (3660a, 3665, 4460, 60481, 3044), so models using either
  name are read.

## Parts added

| part | LDraw | cells | studs on top | flat bottom | plates |
|---|---|---|---|---|---|
| brick1x2_4216 (brick with groove) | 4216 | 1×2 | all | all | 3 |
| plate2x2_corner / brick2x2_corner | 2420 / 2357 | L of 3 | all | all | 1 / 3 |
| slope45_2x1, 2x2, 2x3, 2x4, 2x8 | 3040b, 3039, 3038, 3037, 4445 | 2 deep × 1–8 | back row | all | 3 |
| slope33_3x1, 3x2, 3x4 | 4286, 3298, 3297 | 3 deep × 1–4 | back row | all | 3 |
| slope18_4x2 | 30363 | 4 deep × 2 | back row | all | 3 |
| slope65_2x1x2, slope75_2x1x3 | 60481a, 4460a | 2 deep × 1 | back row | all | 6, 9 |
| slope45inv_2x1, 2x2; slope33inv_3x2 | 3665a, 3660, 3747a | 2–3 deep × 1–2 | all | back row | 3 |
| slope45convex_2x2 / concave_2x2 | 3045 / 3046 | 2×2 | 1 / 3 cells | all | 3 |
| slope45double_2x1, 2x2, 2x3, 2x4 (ridges) | 3044b, 3043, 3042, 3041 | 2 deep × 1–4 | none | all | 3 |
| slope31_1x1x2, slope45double_1x1x2 | 54200, 35464 | 1×1 | none | all | 2 |

## Skipped, and why

| part | instances (48 sets) | why |
|---|---|---|
| 32028 plate 1×2 with door rail | 233 | Its rail sticks out 9 LDU past the 1×2 box on one side (bbox z −19..+10), so a neighbour there would overlap. Not a lookalike. |
| 3794a/b jumper plate | 535 | One centred stud: connects half a stud off the grid (left out since M8). |
| 2450 plate 3×3 without corner | — | Diagonal cut: partial cells. |
| 50950, 61678 curved slopes | 97 | Curved, thin low end; would need partial cells. |
| 30565, 3063b, 25269, 6231, 30562 (round corners, panels) | ~330 | Round or thin-walled; not stud-cell boxes. |
| 3300, 3299 (33° double) | few | Geometry resolution was incomplete when checked; not verified, so not added. |
| 4287 inverted 33° 3×1 "with notch" | few | Its studs sit at three different heights in the .dat; not a clean box. |
| 3747b (ribbed 3747a) | 0 in these sets | Would be a lookalike of 3747a; not needed yet. |

## Coverage: how much of each set can be used

Reproduce:

```
python -m brickwfc.experiments.coverage --on-grid --out out/m12b_cov_omr20
python -m brickwfc.experiments.coverage --on-grid --sets-file results/sets_selection.json --out out/m12b_cov_m10
```

Raw data: `m12b_coverage_omr20.json`, `m12b_coverage_m10.json`. Shares of each set's part instances:
- **M8 catalog / catalog**: the part is recognized (before / after M12b).
- **on grid**: the part also voxelizes onto the stud grid (right rotation and position). These are the parts
  style statistics learn from.

| set list | parts | M8 catalog % | catalog % | on grid M8 % | on grid % |
|---|---|---|---|---|---|
| 20 OMR sets (M8) | 14,426 | 51 | **57** | 22 | **25** |
| 28 M10 building sets | 25,463 | 61 | **69** | 49 | **57** |

**Recognized parts gain 6–8 points and on-grid parts 3–8.**
- The largest gains are on Creator houses: 4956-1 63 → 90%, 5891-1 60 → 84%, 4954-1 66 → 83%.
- 10017-1 doubles its recognized share (33 → 64%) but stays at 6% on grid: most of its parts are tilted or
  off grid.

New parts by instances (28 M10 sets; sets in brackets): cheese slope 54200 276 (14), 4216 221 (7), brick
corner 198 (14), plate corner 173 (14), slope 45 2×4 153 (12), 2×1 125 (18), 2×2 118 (14), inverted 2×1
114 (12), 2×3 96 (9), …; all 25 new parts together: 2,074 instances, 8% of the M10 sets' parts (859, 6%, of the
OMR 20).

What is still missing is mostly jumpers (3794), door-rail plates (32028), Technic, hinges, round and
curved parts, windows/doors and minifigure parts (3818–3820).

### 28 M10 building sets

| set | parts | four plates % | M8 catalog % | catalog % | on grid M8 % | on grid % | most common missing |
|---|---|---|---|---|---|---|---|
| 7796-1 | 56 | 11 | 88 | 100 | 88 | 100 |  |
| 4956-1 | 629 | 3 | 63 | 91 | 59 | 86 | 3854 (8), 3185 (6), 3455 (5) |
| 5891-1 | 539 | 6 | 60 | 85 | 54 | 77 | 4589 (8), 4865a (7), 60608 (6) |
| 4954-1 | 1174 | 5 | 66 | 83 | 54 | 70 | 3794a (56), 32028 (18), 3854 (16) |
| 10182-1 | 2073 | 14 | 73 | 80 | 57 | 62 | 6091 (62), 30136 (45), 2362b (20) |
| 31009-1 | 270 | 8 | 59 | 78 | 57 | 76 | 59900 (6), 60592 (5), 60601 (5) |
| 10185-1 | 2405 | 10 | 64 | 76 | 59 | 71 | 6266 (37), 2429 (34), 2430 (34) |
| 5766-1 | 360 | 6 | 56 | 74 | 51 | 68 | 49668 (15), 87087 (10), 60608 (10) |
| 5771-1 | 703 | 8 | 60 | 74 | 51 | 62 | 60592c01 (14), 32028 (9), 60478 (8) |
| 349-1 | 80 | 0 | 58 | 74 | 58 | 74 | 3069a (6), 646cc01 (3), 3185 (3) |
| 377-1 | 203 | 12 | 68 | 72 | 57 | 59 | 3641 (6), 3317 (4), 3831d01 (4) |
| 6362-1 | 139 | 6 | 59 | 70 | 45 | 55 | 3641 (4), 3359 (2), 3358 (2) |
| 6370-1 | 185 | 6 | 51 | 70 | 50 | 69 | 4079 (4), 3741ac01 (4), 3820 (4) |
| 10190-1 | 1484 | 4 | 67 | 69 | 55 | 57 | 756 (192), 3794a (25), 3854 (20) |
| 10197-1 | 2302 | 16 | 62 | 69 | 47 | 54 | 32028 (53), 3794b (52), 80 (40) |
| 6372-1 | 239 | 6 | 56 | 69 | 55 | 67 | 3742 (18), 3741 (6), 4079 (4) |
| 10218-1 | 2042 | 9 | 62 | 68 | 47 | 53 | 3794a (53), 33291 (36), 30136 (29) |
| 10224-1 | 2804 | 10 | 64 | 68 | 57 | 61 | 3794a (58), 60592 (55), 60601 (52) |
| 6363-1 | 150 | 11 | 63 | 67 | 45 | 49 | 4084 (4), 4085a (4), 4079 (2) |
| 31048-1 | 369 | 10 | 54 | 64 | 45 | 54 | 98138 (12), 30137 (8), 60608 (8) |
| 374-1 | 363 | 9 | 60 | 62 | 59 | 60 | 3641 (12), 3820 (8), 3788 (6) |
| 361-2 | 85 | 0 | 61 | 61 | 61 | 61 | 3854 (8), 3853 (4), 3865 (2) |
| 6380-1 | 333 | 10 | 54 | 59 | 35 | 39 | 2493b (10), 2494d01 (10), 3820 (10) |
| 6378-1 | 348 | 8 | 58 | 59 | 47 | 47 | 754 (41), 4624 (7), 3641 (7) |
| 6382-1 | 415 | 10 | 51 | 59 | 36 | 44 | 4218a (20), 3853 (12), 3855b (11) |
| 10243-1 | 2593 | 13 | 55 | 58 | 44 | 47 | rect3 (60), 15573 (55), 33291 (49) |
| 10264-1 | 2573 | 10 | 52 | 57 | 33 | 35 | 25269 (61), 35480 (56), 30357 (30) |
| 7743-1 | 547 | 9 | 51 | 55 | 27 | 28 | 6014 (14), 6015 (14), 6541 (10) |
| **all** | 25463 | 10 | 61 | 69 | 49 | 57 |  |

### 20 OMR sets (the M8 table, with the new columns)

| set | parts | four plates % | M8 catalog % | catalog % | on grid M8 % | on grid % | most common missing |
|---|---|---|---|---|---|---|---|
| 10018-1 | 1865 | 21 | 85 | 93 | 73 | 82 | 3794b (69), 2356 (8), 6212 (7) |
| 10170-1 | 365 | 9 | 67 | 75 | 21 | 23 | 2921 (16), 4864b (16), 2432 (8) |
| 10017-1 | 208 | 4 | 33 | 64 | 6 | 6 | 6553 (12), 32000 (8), 4175 (6) |
| 10133-1 | 419 | 14 | 60 | 62 | 26 | 26 | 30377 (14), 6091 (12), 2540 (12) |
| 10020-1 | 444 | 15 | 61 | 62 | 43 | 43 | 6215 (28), 4085c (18), 6091 (10) |
| 10129-1 | 1454 | 9 | 49 | 61 | 1 | 2 | 30244 (62), 4274 (32), 4589 (24) |
| 10014-1 | 170 | 2 | 55 | 56 | 36 | 38 | 4862 (13), 2377 (13), 2921 (10) |
| 10015-1 | 192 | 12 | 56 | 56 | 40 | 40 | 4036 (14), 4035 (14), 2921 (8) |
| 10036-1 | 166 | 8 | 49 | 55 | 36 | 40 | 3820 (6), 3675 (4), 3641 (4) |
| 10156-1 | 111 | 10 | 52 | 54 | 0 | 0 | 6014 (6), 6015 (6), 4085c (4) |
| 10019-1 | 1804 | 4 | 41 | 51 | 13 | 19 | 30565 (52), 30562 (52), 30414 (36) |
| 10143-1 | 3457 | 5 | 49 | 50 | 11 | 11 | 3794a (271), 32064a (231), 2780 (72) |
| 10159-1 | 589 | 8 | 43 | 47 | 26 | 28 | 4865a (19), 3820 (14), 4862 (12) |
| 10158-1 | 173 | 8 | 41 | 46 | 29 | 29 | 4864b (17), 30136 (8), 32083 (5) |
| 10016-1 | 120 | 7 | 43 | 45 | 9 | 11 | 30565 (16), 30562 (8), 4175 (6) |
| 10134-1 | 1491 | 4 | 36 | 44 | 2 | 2 | 72504 (112), 3794b (50), 32123b (50) |
| 10013-1 | 162 | 1 | 41 | 44 | 8 | 9 | 30104k02 (42), 4095 (10), 30237 (10) |
| 10128-1 | 338 | 8 | 37 | 41 | 29 | 33 | 4459 (18), 75535 (18), 30258 (8) |
| 10124-1 | 677 | 6 | 37 | 39 | 28 | 30 | 3711 (91), 6628 (24), 32293 (14) |
| 10037-1 | 221 | 9 | 35 | 37 | 32 | 34 | 3742 (18), 2453a (11), 3820 (10) |
| **all** | 14426 | 8 | 51 | 57 | 22 | 25 |  |

## Style statistics v2 (relearned with corners and slopes)

The M10 statistics were learned with the M8 catalog. New parts had only smoothing mass in them, so the
styled proposal tried slopes and corners rarely and late.

**Relearned:**
- Command: `python -m brickwfc.experiments.style --learn-only v2` (learning only, no CV rerun).
- Same 28 sets, same 4 folds, voxelized with the full catalog.
- Written to `results/m10_style_stats/style_fold{i}_v2.json`, each with `"catalog": "m12b"`.
- The v1 files are untouched.
- Check: the same command with `--catalog m8` reproduces the v1 files exactly (all four folds: part counts,
  contacts, colors, support counts).

**Which version is used:**
- The pipeline uses v2 by default (`alt.inputs.STYLE_VERSION`); `--style-version v1` restores M10/M12
  behaviour.
- The candidate cache key names the version, so v1 and v2 caches never mix.
- `--catalog m8` reads inventories with the M8 catalog.
- The M12 drivers (`experiments/demo.py`, `experiments/balance.py`) default to `--catalog m8
  --style-version v1`, so their tables reproduce.

Part-type mass, all 28 sets (the sum of the folds / 3, as `alt.inputs.all_from_folds`):

| statistics | parts | M8 parts | corners | 4216 | slopes | vertical contacts | horizontal contacts |
|---|---|---|---|---|---|---|---|
| v1 (M8 catalog) | 12,595 | 100% | 0 | 0 | 0 | 13,494 | 25,592 |
| v2 (M12b catalog) | 14,401 | 87.5% | 2.3% | 1.5% | 8.7% | 17,447 | 32,626 |

**Contacts:**
- In v2, new parts take 14.7% of vertical-contact ends (corners 3.4%, slopes 10.1%) and 13.4% of
  horizontal contacts.
- Vertical contacts grow 29%, because a slope or corner now joins the stack above and below it instead of
  breaking it.

**Counts:**
- The M8 parts' counts are identical in v1 and v2: adding parts does not change how the old ones voxelize.
- Most frequent new parts in v2: 4216 221, cheese slope 192, brick corner 190, slope 45 2×4 152, plate
  corner 145, slope 45 2×2 112, 2×1 107, inverted 2×1 106.

## Before/after: the spaceship demo with the new catalog

Figure: `results/m12b_catalog_before_after.png`.

**Setup:**
- Target: the M12 spaceship (silhouette + heights + colors), scaled to each set's inventory volume.
- Builder: D2 with balance, bridge and connect.
- Seeds 0–99 on both sides.
- The top-selected build per set is shown.
- Before: M8 catalog + v1 style (the M12 demo's cached candidates, which rebuild part-for-part identical).
- After: full catalog + v2 style.
- Means: `m12b_catalog_before_summary.json`, `m12b_catalog_after_summary.json`.

Reproduce (the before run reuses `out/m12_demo` caches when copied in, otherwise regenerates them):

```
python -m brickwfc.experiments.demo --sets 6378-1 5891-1 --wfc-n 0 --n 100 --out out/m12b_catalog_fig/before
python -m brickwfc.experiments.demo --sets 6378-1 5891-1 --wfc-n 0 --n 100 --catalog full --style-version v2 --out out/m12b_catalog_fig/after
python -m brickwfc.experiments.catalog_figure
```

| set | run | parts in inventory | valid % | fill % | IoU | utilization % | best build: parts, slopes, corners, fill % | s/candidate |
|---|---|---|---|---|---|---|---|---|
| 6378-1 | before | 203 | 100 | 69.9 | 0.70 | 91.6 | 193, 0, 0, 74 | 15.2 |
| 6378-1 | after | 204 | 100 | 71.1 | 0.71 | 92.7 | 194, 0, 1, 71 | 11.8 |
| 5891-1 | before | 323 | 100 | 65.1 | 0.65 | 81.2 | 279, 0, 0, 67 | 22.6 |
| 5891-1 | after | 460 | 100 | 62.5 | 0.63 | 82.6 | 382, 68, 2, 61 | 67.9 |

**5891-1 (Apple Tree House) gains 137 parts.**
- The best build uses 382 parts, 68 of them slopes: inverted 45° 2×1 23, 45° 2×2 12, concave corner slopes
  8, cheese slopes 5, …. It also uses 2 corners.
- Every build is still valid, stands on a table, and is one piece.
- Fill drops 2.6 points. The target is scaled to the bigger inventory (grid 54×34×10 instead of 43×28×8),
  and slopes cost fill: nothing may go on a sloped face.
- Time per candidate triples. The inventory and grid are larger, and slopes are checked cell by cell
  instead of through the fit map.

**6378-1 (Shell Service Station) barely changes.** It gains a single 2420 corner: its other new-catalog
parts are off the stud grid.

**The judge is not compared across the two runs** (−0.34 vs −0.36/−0.38), since each run judges with its
own style statistics.

**The preview draws slopes as slopes** (`build.slope_profiles` + `render3d`):
- A plain slope's top and an inverted slope's underside are cut by their sloped plane, using each part's
  turn. The plane falls from full height at the studded rows to a 0.5-plate lip, as in the .dat files.
- The figure's builds are re-drawn from the cached candidates, with no new builds.
- Builds without slopes render pixel-identical to before.
- Ridges, cheese slopes and corner slopes are still drawn as studless boxes.

**Verdict:** this step does not, on its own, make the demo look clearly better side by side. It makes more
of each set usable, and gives the M12b looks steps (mirror symmetry, clean skins) and the learned proposal
the parts they need.

## Open points

- **Mac, in the morning:** open `out/check/catalog_check.ldr` (written by
  `python -m brickwfc.bricks.catalog_check`) in Studio.
  - What it shows: every corner and slope orientation, with yellow 1×1 markers in the notches, on the
    model's stud cells, and under the flat bottoms of inverted slopes (which stand one plate up).
  - What should hold: each marker sits flush, on a real stud, never cutting into a slope face.
  - Already checked automatically: `test_placement_matches_the_ldraw_part` checks the same facts against
    the .dat files.
- A slope-aware preview for ridges, cheese slopes and corner slopes (plain and inverted slopes are done).
- The fit map could learn cell-set shapes (window sums over a footprint mask) to win back the slope speed.
- Relaxing "nothing above a slope face" to allow overhangs would need per-cell heights.
- 32028 (door rail) and the jumper plates (3794) remain the largest missing groups.
