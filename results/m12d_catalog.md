# M12d — the catalog extended to the real sets' parts

**Branch `m12d-catalog`, four batches, each merged on its own:** dccc017 (batch 1), 6556e0f (batch 2), 7e99f36 (batch 3),
03d2759 (batch 4), then this write-up with style v3.

- The catalog grows from 88 to 183 parts.
- A window or door frame can now also carry its glass, panes and door (12 accessory files, no cells of their own).
- **Recognized share of the 28 building sets: 69.5% → 82.8%; on grid: 56.9% → 65.3%.** The plan's target was 80–83%.
- On the 20 OMR sets: 57.1 → 68.1% recognized, 24.7 → 27.5% on grid.
- Style statistics v3 are relearned with the new parts (v1 and v2 kept).
- Builds from the M8 catalog are unchanged (`test_m8_builds_are_unchanged`).

## What changed

- **Geometry from the library, by program** (`ldraw/library.py`).
  - What it does: `python -m brickwfc.ldraw.library PART --cache data/ldraw` resolves a part's `.dat` through its
    subfiles. It reports the top and side studs, the body's extents without the studs, and a per-cell map: a stud on
    top, and whether the bottom plane is flat under the cell.
  - Where the files come from: the library rate-limits single files (HTTP 429 after a few dozen). Its `complete.zip`
    (146 MB, one request) is unpacked under `data/ldraw` (gitignored).
  - Rule: a cell is *seated* where the bottom plane covers at least 10% of it. Rounded corners leave slivers of 3–10%
    (27925, 3063b, 30357), and those cells are not seated.
  - The test rows are generated from these facts by script, not typed in.
- **Placement test** (`test_catalog_shapes.test_placement_matches_the_ldraw_part`, 121 files: 26 from M12b, 95 new): every orientation's
  `.ldr` placement must put the real studs on the model's stud cells, the flat bottom on its seated cells, and the body
  exactly over its cells and layers. New annotations, each checked:
  - `within`: the body lies inside the box, the box being the conservative bound. Examples: a log brick 9.9 LDU deep,
    a 33° ridge only 14 LDU tall, a baseplate 4 LDU thick.
  - `lower_studs`: a stud a plate or more below the box top, hidden in the box (the part counts as studless there).
  - `rise`: a collar under a plate tall over studless top cells.
  - `offgrid_studs`: a stud between cell centres.

  The test was mutation-checked: wrong seats, a phantom stud, a wrong height, a wrong origin and a mirrored footprint
  all fail.
- **New part fields** (`bricks/parts.py`):
  - `Part.ground_only` (baseplates): no seated cells. On the ground the whole bottom bears on the table
    (`PlacedPart.contact_cells`, used by physics and balance).
  - `Part.origin_plates`: the origin inside the box, not on its top or bottom face (92946).
  - `Part.keep_out`: neighbour cells and layers that must stay empty (batch 3).
  - `Part.side_studs`: recorded, unused.
  - `Part.wfc`: whether WFC can place the part soundly.
- **The other changes:**
  - `parts._mapped` builds a part from the library's cell map.
  - `Part.__hash__` uses (name, file). Hashing a baseplate's three 512-cell tuples on every cached `geometry()` call
    made a build take 81 s instead of 4.7 s. Hash values were already random per process, so builds cannot depend on
    them.
  - `parts.M12B_FILES` keeps the 88-part catalog for before/after numbers. The coverage driver and the pipeline accept
    `--catalog m12b`.

## Batches

### 1. Existing mechanisms (68 parts, dccc017)

- Plain plates and bricks:
  - plates 2×16, 4×12, 6×12, 6×16;
  - tall bricks 1×2×2 (3245c/a), 1×2×5, 1×1×3 and 1×1×5 (2453a/2453).
- Baseplates 16×32 (3857) and 32×32 (3811).
- Lookalike boxes:
  - log and masonry bricks;
  - Technic bricks 3700, 6541, 32064a/b;
  - cones 59900 and 4589;
  - round and quarter tiles;
  - round plates 85861, 24866, 35480;
  - panels 6231, 4865a, 4865b (studless) and 87552, 4864b, 2362b.
- Per-cell parts:
  - tile corner 14719;
  - round corners 30357, 27925, 3063b, 85080;
  - plates with studs on some cells 92593, 41740, 33909, 6179, 3176;
  - arches 3659, 3455, 92950, 6182, 3307, seated at their end cells only (the box stays full);
  - 6005.
- Slopes and curved parts:
  - slopes 3678b (+3678a), 3684c, 4161, 3939, 3675;
  - ridges 3300, 3299, 3048b;
  - cheese slope 85984 and the cutout slope 92946;
  - curved bricks as studless boxes: 6091, 6191, 37352, 6215, 50950, 61678, 11477, 15068, 93273, 49307.
- Aliases 3665b and 63325.

**Deviation from the plan.** 6091's stud sits one plate below its curved top, and the same holds for 6005 and 92946.
The four-plate box hides that stud, so these parts are studless. They are not slopes with a back stud.

### 2. Frames with contained glass (14 parts and 12 accessories, 6556e0f)

**Frames:**
- windows: 60592 (+60592c01), 60593 (+60593c01), 2377, 4863, 2493b, 4035, 30044, 60594, 6556;
- door frames: 60596, 30179;
- fences: 30055, 3633, 3185.

**Two things not in the plan:**
- In the models, 3854 and 60608 are hinged panes inside 3853, 6556 and 60594 frames, and 30046 is the pane of 30044.
  They are accessories, not frames.
- 3853 is skipped as a frame: its body sticks 4 LDU past its 1×4 box at both ends and 6 LDU out of its front.

**Collars and off-grid studs.** The collars of 60594, 60596, 6556 and 30179 rise 4 LDU, over studless end cells only.
Nothing may sit there anyway, so no new rule is needed. 30044's one stud sits between its cells, so its top counts
as studless.

**Accessories** (`bricks/accessories.py`): 60601, 60602, 4862, 2494, 30046, 3854, 86210, 60608, 60623, 60616a/b, 57895.
- Slots: each frame has slots at the pose real models use most, measured over the 93 local models. These turned out
  to be the closed poses. `test_every_slot_keeps_its_accessory_inside_the_frame` checks every slot, in every turn,
  against the accessories' `.dat` extents: inside the frame's box.
- Inventories: `Source.accessories`, keyed by (file, LDraw color code), so trans-clear round-trips. A composite frame
  file adds its glass.
- Builds: `write_build` fits accessories after selection. Each frame, in order, fills its slots from what is left,
  taking the color with the most left. They are written in the frame's step, and the stats row counts them.
- Recognition: coverage and voxelize count an accessory as recognized (or on grid) when a recognized (or kept) frame's
  box holds its origin.
- Not read from Rebrickable inventories.

**Baseplates, fixed after the batch-1 review.** A part bridging a baseplate (4 LDU thick, modelled as a plate) and a
part beside it would have had a stud joint 4 LDU off. Three changes:
- A ground-only part goes only on an empty ground layer and then closes it (`bottomup._ground_ok`), so it is the whole
  ground.
- A build on a baseplate is exported 4 LDU lower (`parts.build_placements`). The baseplate lies on the table and every
  part sits on its studs: the `.ldr` is exact.
- WFC leaves ground-only parts out.

Cost, measured with inventory-only D2 (balance + connect, no style) on the same 32×32 grid, 3 seeds:

| set | builds using the baseplate | s/build with it | s/build without it |
|---|---|---|---|
| 6370-1 | 4/10 | 43.4 | 24.7 |
| 6372-1 | 4/10 | 52.5 | 27.9 |

- About 1.8× per build: a 32-stud part makes the fit maps' reach 32. The rest of the cost against an ordinary build
  is the 32×32 grid that a baseplate needs.
- 14 of the 28 sets have a baseplate: 10 a 3857, 4 a 3811.

**Coverage denominator.** `coverage.PRIMITIVE` now drops every name that starts with a letter (rect3, box2-5,
t01i3333, …): the 28 sets go from 25,463 to 25,321 instances. This also drops the few unofficial parts named so
(u9026, u8001b: 46 instances in the 93 models).

### 3. Keep-out cells (9 parts, 7e99f36)

`Part.keep_out` lists (x, z, first layer, last layer) in the part's frame, with layers counted from its bottom layer
(negative: below it).
- **Orientations:** keep-out cells turn with the part (`Geometry.keep_out`) and make orientations distinct. A door
  rail turned 180° has its rail on the other side.
- **Builder** (`bottomup._keep_ok`, in `_place` and for mirror images): a part fits only if its keep-out cells are
  empty, are no other part's keep-out, and none is below the ground, and if its own cells are nobody's keep-out. Once
  it is placed its keep-out cells are blocked (`_State.blocked`) for every later placement, the hole and connect
  passes included.
- **Fit key:** `_fit_key` carries the keep-outs, so a rail plate that fails on its rail does not make the builder skip
  the plain plate.
- **Verify:** `extract_parts` reports a part in another's keep-out.
- **Mirror images:** `mirror_shape` reflects keep-outs.
- **WFC** leaves these parts out: an empty cell next to a part is not an adjacency rule (`Part.wfc`;
  `SupportConstraint` refuses them).

| part | what sticks out (from the .dat) | keep-out |
|---|---|---|
| 32028, 4510 door rail | rail 9 LDU deep at plate height | front row, own layer |
| 30586 door rail 2×8 | studs on one row; rail beyond the other, rising 4 LDU | the row beyond, own layer and one up |
| 87087, 47905, 30414 side studs | studs 4 LDU out, centred 10 LDU below the top | facing cells, layers 1–2 |
| 44728, 93274 brackets | face 4 LDU thick hanging 32 LDU below the plate, 2 / 4 studs wide | front row, layers −4..0 |
| 2921 handle | handle 14 LDU out over the brick's height | front cell, layers 0–2 |

`test_keep_out` checks, in every turn, that every cell the geometry outside a part's box overlaps is a keep-out cell,
and checks the recorded side studs against the `.dat`.

### 4. Jumpers (4 parts, 03d2759)

3794a, 3794b, 15573 (1×2) and 87580 (2×2) are plates with a studless top. Their one stud is off the grid, and a real
model's part on it is already dropped by the voxelizer as off-grid.

## The model and its simplifications

**Soundness.** Every approximation is conservative: a part may occupy more than it really does, never less.

**Boxes and seats.** These parts are full boxes, seated only where their bottom is flat:
- arches (the opening counts as filled; nothing may go under the span);
- round corners and rounded plates (the cut-off corner counts as filled; its stud and seat are not claimed);
- curved bricks and studless slopes (nothing on the curve);
- cones (the full 1×1 brick).

**Studs the model leaves out:**
- studs below the box top (6091, 6005, 92946);
- studs between cells (30044, jumpers);
- side studs (they are keep-out).

**Baseplates and accessories:**
- A baseplate is one plate tall in the model and exported exact.
- An accessory is fitted after the build, which can only add parts: it never changes whether anything fits.

## Parts added (28 sets: instances and sets; the 3,044 instances of new catalog parts, plus 320 accessories in frames)

| kind | parts (instances in the 28 sets, sets) |
|---|---|
| door rails | 32028 233 (12), 4510 45 (5), 30586 24 (5) |
| jumpers | 3794a 216 (8), 15573 81 (2), 3794b 55 (3), 87580 34 (4) |
| lookalike bricks | log 30136 158 (8), Technic 3700 70 (11) / 6541 37 (9) / 32064a 12, cones 59900 88 (9) / 4589 22, masonry 98283 15, 4217 6 |
| windows and doors | 60592 154 (10), 60593 87 (6), 60596 55 (12), 60594 40 (8), 30044 22, 6556 22, 2493b 12, 30179 6, 4035 4, 4863 1 |
| accessories in a frame | 60601 105, 3854 58, 60608 46, 60602 36, 60623 30, 57895 19, 30046 18, 86210 14, 60616a 6, 2494 5, 60616b 3 |
| curved | 6091 139 (10), 50950 66 (6), 61678 31, 11477 25, 15068 12, 93273 8, 6191 7, 37352 3, 6215 2 |
| side studs, brackets, handle | 87087 81 (7), 44728 56 (8), 30414 51 (8), 47905 46 (6), 2921 39 (6), 93274 21 |
| panels | 6231 62 (6), 87552 36, 2362b 23, 4865b 22, 4865a 18, 4864b 2 |
| round and quarter tiles, round plates | 25269 61, 35480 56, 98138 53, 85861 18, 24866 16, 30357 32, 27925 16 |
| per-cell plates | 92593 54 (6), 3176 15, 6179 6, 33909 2 |
| plain plates, bricks, baseplates | 4282 42 (11), 3029 22, 3028 16, 3027 16, 3245c 10, 2454 6, 2453a 5, 3857 18 (10), 3811 4 |
| arches | 3659 37 (9), 6182 20, 3455 17, 6005 12, 92950 6, 3307 2 |
| slopes | 3678b 32, 92946 17, 85984 13, 3048b 11, 3939 8, 4161 8, 3675 8, 3684c 7, 3299 6, 3300 4 |
| fences | 30055 31 (7), 3633 23 (8), 3185 20 (5) |
| aliases | 3665b 16, 63325 16 |

## Skipped, and why

| part | instances (28 sets) | why |
|---|---|---|
| 33291 flower plate | 97 | tabs overhang the cell by 2 LDU on every side |
| 32607 leaf plate | 29 | leaves reach 18 LDU outside the cell |
| 4079 seat | 37 | backrest rises 40 LDU above and 5 LDU behind its 2×2 |
| 3853 window 1×4×3 | 22 | body 4 LDU past both ends and 6 LDU out of the front; its panes (3854) and glass (3855b) stay unrecognized |
| 2339 arch 1×5×4 | 10 | studs at four heights |
| minifigure parts (3815–3820, 3626 heads, 973 torsos, …) | 646 | not building parts |
| hinges, clips, bars (2429/2430, 4081b, 92280, 60897, 4085c, …) | 650 | they join at angles or off the grid; needs joints the model does not have |
| Technic pins and axles (2780, 4274, 32062, …) | 308 (Technic) | not stud joints |
| wheels and tyres (3641, 4624, 6014/6015) | 221 | round, on axles |
| plants (3742, 3741, 2423, 22667) | 135 | not stud-cell shapes |
| dishes and other round parts (4740 dish, 30565 / 30562 round corners and panels, 15712 clip tile, ...) | ~350 (round) | partly round shapes not measured yet; candidates for a later batch |
| 756, 754 (flexible hose segments), 80 (moved to a kit file) | 274 | hose segments are not stud-cell parts; 80 resolves to a whole kit |

Still missing on the 28 sets: 4,350 instances (17.2%) in 702 files, a long tail (`out/m12d_missing_after.md`,
`experiments/missing_parts.py`; it counts accessories in frames as missing, so its 81.6% is below the coverage
driver's 82.8%).

## Coverage: how much of each set can be used

Reproduce (`--data` points at the OMR models):

```
python -m brickwfc.experiments.coverage --on-grid --sets-file results/sets_selection.json --out out/m12d_cov/m10
python -m brickwfc.experiments.coverage --on-grid --out out/m12d_cov/omr20
```

Raw data: `m12d_coverage_m10.json`, `m12d_coverage_omr20.json`. Columns:
- **M8**, **M12b** and **catalog**: the share of part instances that are recognized with each catalog;
- **on grid**: the share that also voxelizes onto the stud grid with that catalog.

| set list | parts | M8 % | M12b % | catalog % | on grid M8 % | on grid M12b % | on grid % |
|---|---|---|---|---|---|---|---|
| 28 M10 building sets | 25,321 | 61 | 70 | **83** | 50 | 57 | **65** |
| 20 OMR sets (M8) | 14,359 | 51 | 57 | **68** | 22 | 25 | **27** |

Recognized parts gain 13 points on the 28 sets and 11 on the 20 OMR sets; on-grid parts gain 8 and 3.
- The largest gains are on the modular buildings: 10224-1 68 → 90%, 10218-1 68 → 86%, 10197-1 69 → 86%,
  10243-1 61 → 78%, 10264-1 57 → 77%. Their door rails, jumpers, windows and logs are now recognized.
- Two Creator houses: 4954-1 83 → 97%, 4956-1 91 → 97%.
- On grid stays well below recognized where a set's parts are tilted or off the grid: 10264-1 is at 42%, 7743-1 at
  31%, and the 20 OMR sets mostly under 50%.

### 28 M10 building sets

| set | parts | four plates % | M8 catalog % | M12b catalog % | catalog % | on grid M8 % | on grid M12b % | on grid % | most common missing |
|---|---|---|---|---|---|---|---|---|---|
| 7796-1 | 56 | 11 | 88 | 100 | 100 | 88 | 100 | 100 |  |
| 4956-1 | 629 | 3 | 63 | 91 | 97 | 59 | 86 | 92 | 32000 (4), 2423 (4), 2432 (2) |
| 4954-1 | 1174 | 5 | 66 | 83 | 97 | 54 | 70 | 79 | 30413 (5), 32000 (4), 4488 (4) |
| 5891-1 | 539 | 6 | 60 | 85 | 93 | 54 | 77 | 83 | 4081b (5), 4599a (3), 6019 (3) |
| 10182-1 | 2073 | 14 | 73 | 80 | 92 | 57 | 62 | 68 | 6120 (11), 44302 (9), 3680 (8) |
| 31009-1 | 270 | 8 | 59 | 78 | 91 | 57 | 76 | 89 | 2429c01 (2), 32001 (2), 2496 (2) |
| 10224-1 | 2797 | 10 | 64 | 68 | 90 | 57 | 61 | 78 | 4218b (18), 3820 (16), 33291 (12) |
| 10218-1 | 2042 | 9 | 62 | 68 | 86 | 47 | 53 | 64 | 33291 (36), 2430 (18), 2429 (18) |
| 5766-1 | 360 | 6 | 56 | 74 | 86 | 51 | 68 | 76 | 49668 (15), 6266 (2), 33057 (2) |
| 10197-1 | 2302 | 16 | 62 | 69 | 86 | 47 | 54 | 66 | 80 (40), 48729a (12), 4081b (11) |
| 5771-1 | 702 | 8 | 60 | 74 | 85 | 51 | 62 | 69 | 60478 (8), 91405 (5), 4287b (5) |
| 10185-1 | 2405 | 10 | 64 | 76 | 85 | 59 | 71 | 77 | 6266 (37), 2429 (34), 2430 (34) |
| 349-1 | 80 | 0 | 58 | 74 | 81 | 58 | 74 | 81 | 3069a (6), 646cc01 (3), 3081cc01 (2) |
| 10243-1 | 2470 | 13 | 58 | 61 | 78 | 46 | 49 | 59 | 33291 (49), 92280 (23), 30126 (18) |
| 10264-1 | 2564 | 10 | 52 | 57 | 77 | 33 | 35 | 42 | 32607 (29), 59443 (18), 32062 (17) |
| 10190-1 | 1484 | 4 | 67 | 69 | 76 | 55 | 57 | 61 | 756 (192), 30377 (13), 71944k02 (12) |
| 31048-1 | 369 | 10 | 54 | 64 | 76 | 45 | 54 | 64 | 30137 (8), 30503 (5), 30565 (4) |
| 377-1 | 203 | 12 | 68 | 72 | 74 | 57 | 59 | 60 | 3641 (6), 3317 (4), 3831d01 (4) |
| 6362-1 | 139 | 6 | 59 | 70 | 74 | 45 | 55 | 60 | 3641 (4), 3359 (2), 3358 (2) |
| 6370-1 | 185 | 6 | 51 | 70 | 71 | 50 | 69 | 71 | 4079 (4), 3741ac01 (4), 3820 (4) |
| 6372-1 | 239 | 6 | 56 | 69 | 71 | 55 | 67 | 70 | 3742 (18), 3741 (6), 4079 (4) |
| 6363-1 | 148 | 11 | 64 | 68 | 68 | 46 | 49 | 50 | 4084 (4), 4085a (4), 4079 (2) |
| 374-1 | 363 | 9 | 60 | 62 | 68 | 59 | 60 | 66 | 3641 (12), 3820 (8), 3788 (6) |
| 7743-1 | 547 | 9 | 51 | 55 | 66 | 27 | 28 | 31 | 6014 (14), 6015 (14), 3820 (8) |
| 6380-1 | 333 | 10 | 54 | 59 | 63 | 35 | 39 | 42 | 2494d01 (10), 3820 (10), 3816 (5) |
| 361-2 | 85 | 0 | 61 | 61 | 62 | 61 | 61 | 61 | (accessories outside a frame) (8), 3853 (4), 3865 (2) |
| 6382-1 | 415 | 10 | 51 | 59 | 62 | 36 | 44 | 47 | 4218a (20), 3853 (12), 3855b (11) |
| 6378-1 | 348 | 8 | 58 | 59 | 59 | 47 | 47 | 48 | 754 (41), 4624 (7), 3641 (7) |
| **all** | 25321 | 10 | 61 | 70 | 83 | 50 | 57 | 65 |  |

### 20 OMR sets

| set | parts | four plates % | M8 catalog % | M12b catalog % | catalog % | on grid M8 % | on grid M12b % | on grid % | most common missing |
|---|---|---|---|---|---|---|---|---|---|
| 10018-1 | 1865 | 21 | 85 | 93 | 97 | 73 | 82 | 84 | 2356 (8), 6212 (7), 30562 (4) |
| 10170-1 | 365 | 9 | 67 | 75 | 85 | 21 | 23 | 24 | 2432 (8), 4175 (8), 6087 (8) |
| 10014-1 | 170 | 2 | 55 | 56 | 83 | 36 | 38 | 58 | 30374 (3), 32083 (3), 4175 (2) |
| 10020-1 | 444 | 15 | 61 | 62 | 79 | 43 | 43 | 49 | 4085c (18), 4174735a (4), 2723 (4) |
| 10015-1 | 192 | 12 | 56 | 56 | 77 | 40 | 40 | 56 | 4036 (14), 32083 (6), 2878c01 (4) |
| 10133-1 | 419 | 14 | 60 | 62 | 74 | 26 | 26 | 30 | 30377 (14), 2540 (12), 50746 (10) |
| 10129-1 | 1453 | 9 | 49 | 61 | 70 | 1 | 2 | 2 | 30244 (62), 4274 (32), 2780 (16) |
| 10143-1 | 3457 | 5 | 49 | 50 | 68 | 11 | 11 | 12 | 2780 (72), 6558 (66), 44570 (46) |
| 10017-1 | 208 | 4 | 33 | 64 | 67 | 6 | 6 | 6 | 6553 (12), 32000 (8), 4175 (6) |
| 10158-1 | 173 | 8 | 41 | 46 | 64 | 29 | 29 | 46 | 32083 (5), 4079 (4), 3245b (4) |
| 10019-1 | 1746 | 5 | 43 | 53 | 62 | 14 | 20 | 26 | 30565 (52), 30562 (52), 2476a (31) |
| 10036-1 | 166 | 8 | 49 | 55 | 60 | 36 | 40 | 43 | 3820 (6), 3641 (4), 4624 (4) |
| 10159-1 | 581 | 8 | 43 | 48 | 57 | 27 | 28 | 31 | 3820 (14), 4624 (12), 4079 (7) |
| 10156-1 | 111 | 10 | 52 | 54 | 54 | 0 | 0 | 0 | 6014 (6), 6015 (6), 4085c (4) |
| 10134-1 | 1491 | 4 | 36 | 44 | 53 | 2 | 2 | 2 | 72504 (112), 32123b (50), 2780 (38) |
| 10016-1 | 120 | 7 | 43 | 45 | 48 | 9 | 11 | 13 | 30565 (16), 30562 (8), 4175 (6) |
| 10037-1 | 221 | 9 | 35 | 37 | 48 | 32 | 34 | 44 | 3742 (18), 3820 (10), 3741a (6) |
| 10124-1 | 677 | 6 | 37 | 39 | 47 | 28 | 30 | 35 | 3711 (91), 6628 (24), 32293 (14) |
| 10128-1 | 338 | 8 | 37 | 41 | 45 | 29 | 33 | 36 | 4459 (18), 75535 (18), 30258 (8) |
| 10013-1 | 162 | 1 | 41 | 44 | 44 | 8 | 9 | 9 | 30104k02 (42), 4095 (10), 30237 (10) |
| **all** | 14359 | 8 | 51 | 57 | 68 | 22 | 25 | 27 |  |

### All local OMR models

Pending: session B's crawl is still filling `data/omr` (about 1,836 models). The table over every local model follows
in a small commit once it is done (third command in `docs/reproduce.md`).

## Style statistics v3

**Command and files:**
- Relearned with `python -m brickwfc.experiments.style --learn-only v3` (learning only, no CV rerun).
- Same 28 sets, same 4 folds, voxelized with the full catalog.
- Written to `results/m10_style_stats/style_fold{i}_v3.json`, tagged `"catalog": "m12d"`. v1 and v2 are untouched.

**Check:** `--learn-only v2 --catalog m12b` reproduces the v2 files exactly. Every count is identical; the rerun only
lists the 95 newer parts, all with zero counts.

**Which version is used:**
- The pipeline uses v3 by default (`alt.inputs.STYLE_VERSION`). The statistics must know the catalog's parts, as
  with v2 in M12b.
- `--style-version v2 --catalog m12b` gives the M12b/M12c setup. Candidate caches name the style version, so v2 and
  v3 caches never mix.
- `experiments/proposal.py` stays on v2 for its M12b tables, and the M12 demo and balance drivers stay on v1.
- To reproduce M12b/M12c tables through the pipeline, pass `--catalog m12b --style-version v2`.

Part-type mass, all 28 sets (the sum of the folds / 3):

| statistics | parts | M12b parts | M12d parts | vertical contacts | horizontal contacts |
|---|---|---|---|---|---|
| v2 (M12b catalog) | 14,401 | 100% | 0 | 17,447 | 32,626 |
| v3 (M12d catalog) | 16,299 | 88.4% | 11.6% | 23,546 | 42,692 |

- v3 learns from 13% more parts.
- Contacts grow by about a third (vertical +35%, horizontal +31%). A door rail, a jumper or a window now joins the
  stack above and beside it instead of breaking it.
- Most frequent new parts: 32028 door rail 177, log 30136 139, jumper 3794a 132, window 60592 121, side-stud brick
  87087 65, Technic brick 3700 58, window 60593 55, jumper 15573 48, plate 92593 46.

## For Mac

- **Studio check.**
  - File: `out/check/catalog_check.ldr` (`python -m brickwfc.bricks.catalog_check`), 183 parts in all their
    orientations.
  - Window and door frames carry their glass, panes and doors in every slot.
  - Keep-out parts (door rails, side-stud bricks, brackets, the handle brick) appear in all four turns. Brackets float
    four plates up.
  - Markers, as in M12b: on the stud cells, and under the seated cells of parts with an open bottom. Arches stand one
    plate up on markers under their end cells.
  - What should hold:
    - every marker sits flush on a real stud;
    - no glass, pane or door sticks out of its frame;
    - each rail, side stud, bracket face or handle sticks out into the empty one-stud gap on the side the model keeps
      empty;
    - the baseplates lie flat on the ground.
- **Not done here:**
  - generation runs with the new catalog;
  - a demo or figure.

## Open points

- More round parts (dish 4740, round bricks with clips) and the 3853 window need geometry beyond boxes.
- Accessories are not read from Rebrickable inventories.
- Side studs are recorded on the `Part` (`side_studs`) for sideways building and not used.
- Baseplate builds are about 1.8× slower per build. With quality over speed this stays.
