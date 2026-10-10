# M12b step 1 — true 3D targets, and a head-to-head on BrickGPT's data

*Note (2026-10-10): the builds here predate the `_fit_key` fix (60b3a3b, `builder_version` 2: a tile that failed at a cell no longer makes the builder skip the plate of its box). On 9 set x object pairs the fix moves mean fill by -0.9 to +2.5 points (mean +0.5; within 1.2 SE on 8 pairs, +2.6 SE on the 4956-1 car; old vs fixed base in [`m12b_complete.md`](m12b_complete.md)); a rerun would give different individual builds. Since 49d5739 the thin-aware scale also keeps a thin post under its load, which gives the 5891-1 chair a different target under fillable sizing (2859 -> 2784 cells).*

**Steps 1a–1d done; 1d's tables in [`m12b_overhangs_tables.md`](m12b_overhangs_tables.md).** Targets can now be true
3D shapes instead of extruded heightfields:
- 1a: a StableText2Brick structure, `--shape brickgpt:<id>` (`bricks/brickgpt.py`);
- 1b: a watertight mesh, `--shape model.stl` (`bricks/mesh.py`, `trimesh`);
- 1c: either one hollowed (`--hollow N`);
- 1d: tiles may not cap thin parts (open tops), support columns up to 6 cells tall go under far overhangs
  (`--supports --support-height 6`), and builds must stand within real clutch (`--max-clutch 1111`). All three are
  pipeline defaults; the last two since 2026-10-09 (Mac).

The generator was already 3D, so the funnel, the guarantees and the judge are unchanged.

**Which runs.** The 1a numbers and every table here are a rerun on 2026-10-09 on the 88-part catalog (corners and
slopes, M12b step 4, style v2) with the pipeline defaults above, **at fd9015b: box sizing and lattice support
columns**. Both before/after figures (chair, table) are redrawn at a0ec36c (fillable sizing, support columns that
cover every far overhang cell, thin-aware scale): their runs and the before/after numbers are in
[`m12b_sizing.md`](m12b_sizing.md). Step 1c (hollow) and the 1d tables are from the 63-part catalog with open tops
only, before the support and clutch defaults.

## Data: theirs, not their model

StableText2Brick (BrickGPT, ICCV 2025; MIT license):
- 47k brick structures of ShapeNetCore objects, with GPT-4o captions.
- Each structure is a list of "hxw (x,y,z)" bricks on a 20 × 20 × 20 grid, with a per-brick stability score.
- We fetch the test split (4,785 rows) from the Hugging Face datasets-server into `data/brickgpt/` (gitignored;
  resumable, rate-limit aware).

**All 8 brick sizes they use map 1:1 onto bricks in our catalog.** A structure therefore converts exactly into
our parts, so the same physics (`physics.table_clutch`) and piece count (`balance.clusters`) measure both sides.
We compare against their *data*, not their *model*: their generator needs a GPU, a gated Llama checkpoint and
Gurobi, and it builds from unlimited bricks.

**Objects:** the median-size structure (by brick count) of each of the 6 most common test categories.
**Ours:** the alternate-build pipeline (D2 + learned style, 50 candidates, the top-scored build) from one real
set's inventory (6378-1, 5891-1, 10182-1), with the structure's exact cells as the target, scaled to the
inventory's volume, and the pipeline defaults (open tops, support columns up to 6 cells, real clutch).


## Their structures, measured with our physics

| object | id | bricks | size (studs x studs x bricks) | cells | stands (ours) | clutch | pieces | their score: min | their score: bricks > 0 % |
|---|---|---|---|---|---|---|---|---|---|
| table | 858f0955 | 104 | 18x18x16 | 1980 | yes | 131.2 | **3** | 0.936 | 100 |
| chair | a712684f | 119 | 13x13x18 | 1995 | yes | **815.9** | 1 | 0.082 | 100 |
| car | 4b15b71c | 94 | 8x18x6 | 1470 | yes | 72.0 | 1 | 0.898 | 100 |
| sofa | d1137e5f | 84 | 18x14x5 | 1791 | yes | 0.0 | 1 | 1.000 | 100 |
| vessel | 5c5f88b6 | 46 | 5x18x5 | 639 | yes | 0.0 | 1 | 0.995 | 100 |
| bench | 365bf4bd | 56 | 18x8x9 | 1104 | yes | 65.3 | 1 | 0.992 | 100 |

**Their table is 3 separate pieces.** Each piece stands on the table, and every brick passes their stability
score, but lifting it would leave two pieces behind. "Stable" in their sense does not mean one piece.
**Their chair needs a clutch of 816** plate-cell weights on its worst stud, about 3/4 of what a real stud holds
(1111; calibration in the 1d write-up). Our pipeline guarantees one piece by construction (`connect`).

Clutch is the largest per-stud pull the physics LP needs to keep the build standing on a table, in plate-cell
weights (one 1 × 1 plate's weight). The same units are used everywhere below.


## Ours: the same objects from real inventories

Every built candidate is one piece. Every valid build stands within real clutch, by construction: the clutch cap is
the only physics failure, and without it every candidate would stand (finite clutch). Fill below is *object* fill:
support columns are extra cells outside the object and are not counted.

- **The cap.** It rejects no candidate in 9 of 18 runs and 1–17 of 50 in the rest (most: table 5891-1 17,
  chair 5891-1 14, chair 6378-1 7). Selected builds need at most 768.
- **The chair is fixed.** Mean fill 63.8 / 58.0 / 80.8 (6378-1 / 5891-1 / 10182-1); no valid chair fills under 37%.
  With open tops alone it was 15.5 / 9.1 / 73.5, bimodal on the small sets (38/50 and 43/50 builds under 20%).
  Cause: the target's base is a five-arm star of small casters around a hub. The balance mask keeps the builder off
  the tiny casters, the arms never meet at the hub, and the connect pass keeps one arm. One 3-cell support column
  under the hub (`--supports --support-height 6`) removes the low mode; taller columns (under a table top, a seat)
  are not added.
- **The other objects.** Mean fill per set (6378-1 / 5891-1 / 10182-1): table 54 / 59 / 79, car 70 / 61 / 83,
  sofa 78 / 61 / 83, vessel 75 / 58 / 86, bench 70 / 60 / 81.
- **Defaults vs catalog.** On 6378-1 the new catalog barely changes the inventory (203 → 204 recognized parts, the
  same object cells), so these runs isolate the defaults: fill moves −0.3 to +1.0 points on the five non-chair
  objects. On 10182-1 it moves −2.5 to +1.0. On 5891-1 it drops 5–24 points (to 58–61%), and that is the catalog:
  - 5891-1 has 135 slopes, which the 88-part catalog recognizes (323 → 460 parts). They add 2,170 cells to the
    inventory's volume (2,505 → 4,675, +87%), so `sized_for` scales each target to nearly twice the cells.
  - A slope counts as its bounding box, but it can only go where its sloped face is on top (open tops forbids it
    under target cells), so the larger target is filled less.
  - Control: the 5891-1 car on the 63-part catalog under the new defaults fills 72.6% (style v1) and 73.2% (v2),
    against 71.4% with open tops alone and 61.1% on the 88-part catalog. All 50 candidates valid in each.
  - **Follow-up (not done):** count slopes (and other parts with restricted tops) in `sized_for` by the cells they
    can fill, not by their bounding box.
- **Time.** Seconds per candidate grow with the target: 5891-1 3.2–29.5 → 25.7–96.3, 10182-1 17.8–204.5 →
  47.7–127.9, 6378-1 2.2–17.3 → 3.9–12.0. The 10182-1 table's 127.9 is inflated: a control run shared the CPU for
  its first 4 minutes.

### Before the defaults (63-part catalog, open tops only)

These findings led to the support and clutch defaults; numbers from `m12b_overhangs_summary.json`.
- **Bimodal groups on 10182-1, before open tops.** Without open tops, the table and the chair on 10182-1 split
  into two groups of seeds. Table: 28/50 builds with mean fill 0.22, 22/50 with 0.71. Chair: 26/50 with 0.11, 24/50
  with 0.66. In the low group, a tile or a brick's studless top had capped a thin stem (a table leg, the chair
  post), and nothing could be built above it. Open tops allows a studless top only where the target is empty
  directly above, which removes the low group (table 10182-1: 43.5 → 77.9; chair 37.2 → 73.5). It only removes
  placements, so no guarantee changes.
- **The full chairs exceeded real clutch.** Full chairs (fill > 40%) needed clutch above 1111 in 82–98% of cases:
  the seat and back are long cantilevers. The selected builds needed 1427–5212 on the six demo sets (their chair
  needs 816). Support columns kept 84/88/100% of chair builds within 1111; open tops alone 80/88/2%. Tables, cars,
  sofas, vessels and benches stayed within 1111 in 96–100% of builds.
- **So:** finite clutch is the right criterion except for long cantilevers, and for those support columns are the
  lever; a cap only removes builds. Both are now on by default, the columns capped at 6 cells so they prop low
  overhangs (the chair's hub) without towers under a table top.

### Before / after: `results/m12b_before_after.png`

Redrawn at a0ec36c; its runs are tabled in `m12b_sizing.md` ("Figure runs (chair)"). The fill ranges below and
"Table 1a, figure runs" are the lattice runs at fd9015b.

The chair on the six M12 demo sets, both sides on the 88-part catalog and under the clutch cap:
- **before:** the pipeline as of M12, the target as solid columns (the heightfield input, `--shape-columns`);
- **after:** step 1 with the pipeline defaults: exact 3D cells, open tops, support columns up to 6 cells.

The labels follow the M12 sheet: `set: parts used of parts in the set`, then fill, stands, pieces. Every pictured
build is valid, stands and is one piece. Before, every set produces a solid block. After, every set produces a
chair with a caster base, a post, a seat and a back (with open tops alone, the mean chair filled under 25% on four
of the six sets).

*Note on size:* both targets are scaled to the same volume (the inventory's), so the solid-column "before" chair is
physically smaller (e.g. 10 × 8 × 39 vs 13 × 13 × 53 cells on 374-1). Its higher mean fill (68–81% vs 58–81%) is
fill of an easier, block-shaped target.

### Before / after: `results/m12b_opentops_before_after.png`

Redrawn at a0ec36c: a full table on every set, the 4956-1 failure below fixed by fillable sizing; its runs are
tabled in `m12b_sizing.md` ("Figure runs (table)"). The numbers in this section and "Table 1d, figure runs" are the
lattice runs at fd9015b.

The table on the six demo sets: the exact target (no open tops, no support columns) | the pipeline defaults, both
under the clutch cap. Mean fill exact → defaults: 374-1 53.0 → 53.6, 6378-1 16.0 → 54.3, 7743-1 28.8 → 63.0,
5891-1 21.5 → 58.8, 4956-1 21.9 → 24.6, 10182-1 37.4 → 78.9. On 10182-1 the cap rejects 39/50 exact tables and 3/50 with the defaults. The pictured builds are the selected
ones: on 6378-1 the fill floor and the fill-weighted selection pick the one full exact table (64%; mean 16%).

**4956-1 fails on the 88-part catalog** (61.7% with open tops on the 63-part catalog):
- The target grows to 6,813 cells, and its post becomes a 3 × 3 column 50 plates tall.
- The base uses up the small studded parts. What is left fits the post only as tiles and slopes (studless tops, not
  allowed under target cells) or as 1 × 8 bricks (too long), so 45 of 50 builds with the defaults stop inside the post. 77 of the
  set's 573 parts are 2 × 4 slopes.
- Same cause as on 5891-1 (slopes inflate the target), plus a limit of building bottom-up: the builder does not
  reserve parts for a narrow stem higher up. Both sides of the figure show the base and the post only.

## Tables

### Table 1a. Ours (D2 + learned style from one set's inventory; the structure's exact cells as target, pipeline defaults; 88-part catalog)

Fill and IoU are against the object (without support columns); best: fill % is against the target. Cap rejected:
candidates that stand but need more than 1111 clutch per stud.

| object | set | inventory parts | grid (WxDxH) | object cells | support cells | valid % | physics % | one piece % | cap rejected | fill % | IoU | utilization % | best: parts | best: fill % | best: clutch | their clutch | best: pieces | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| table | 6378-1 | 204 | 18x17x46 | 1706 | 0 | 100 | 100 | 100 | 0/50 | 54.3 | 0.54 | 72.3 | 176 | 65.8 | 57.6 | 131.2 | 1 | 12.01 |
| table | 5891-1 | 460 | 24x24x64 | 4632 | 0 | 66 | 66 | 100 | 17/50 | 58.8 | 0.59 | 78.2 | 390 | 69.5 | 696.0 | 131.2 | 1 | 86.99 |
| table | 10182-1 | 1665 | 31x30x83 | 10609 | 0 | 94 | 94 | 100 | 3/50 | 78.9 | 0.79 | 79.6 | 1371 | 83.1 | 768.0 | 131.2 | 1 | 127.90 |
| chair | 6378-1 | 204 | 13x12x51 | 1725 | 3 | 86 | 86 | 100 | 7/50 | 63.8 | 0.64 | 82.7 | 189 | 71.0 | 141.4 | 815.9 | 1 | 11.21 |
| chair | 5891-1 | 460 | 17x17x70 | 4688 | 12 | 72 | 72 | 100 | 14/50 | 58.0 | 0.58 | 76.7 | 357 | 58.8 | 131.6 | 815.9 | 1 | 96.34 |
| chair | 10182-1 | 1665 | 23x22x94 | 10656 | 72 | 96 | 96 | 100 | 2/50 | 80.8 | 0.80 | 76.0 | 1266 | 81.4 | 263.4 | 815.9 | 1 | 102.47 |
| car | 6378-1 | 204 | 9x18x20 | 1689 | 12 | 100 | 100 | 100 | 0/50 | 69.8 | 0.69 | 90.6 | 187 | 72.8 | 48.0 | 72.0 | 1 | 4.18 |
| car | 5891-1 | 460 | 12x26x27 | 4613 | 60 | 100 | 100 | 100 | 0/50 | 61.1 | 0.60 | 77.4 | 360 | 61.9 | 82.0 | 72.0 | 1 | 56.68 |
| car | 10182-1 | 1665 | 16x34x35 | 10704 | 276 | 94 | 94 | 100 | 3/50 | 82.7 | 0.81 | 78.8 | 1342 | 84.1 | 204.0 | 72.0 | 1 | 53.31 |
| sofa | 6378-1 | 204 | 17x13x14 | 1589 | 0 | 100 | 100 | 100 | 0/50 | 78.3 | 0.78 | 93.0 | 197 | 80.2 | 0.6 | 0.0 | 1 | 4.30 |
| sofa | 5891-1 | 460 | 25x18x21 | 4678 | 0 | 100 | 100 | 100 | 0/50 | 60.6 | 0.61 | 76.1 | 352 | 64.3 | 16.0 | 0.0 | 1 | 67.50 |
| sofa | 10182-1 | 1665 | 33x25x28 | 10591 | 0 | 100 | 100 | 100 | 0/50 | 83.3 | 0.83 | 76.2 | 1295 | 85.3 | 27.0 | 0.0 | 1 | 50.17 |
| vessel | 6378-1 | 204 | 7x24x21 | 1681 | 0 | 100 | 100 | 100 | 0/50 | 75.4 | 0.75 | 92.0 | 191 | 78.1 | 0.0 | 0.0 | 1 | 4.42 |
| vessel | 5891-1 | 460 | 10x34x29 | 4668 | 0 | 100 | 100 | 100 | 0/50 | 57.8 | 0.58 | 72.6 | 340 | 60.3 | 351.0 | 0.0 | 1 | 74.84 |
| vessel | 10182-1 | 1665 | 13x45x39 | 10683 | 0 | 98 | 98 | 100 | 1/50 | 85.5 | 0.86 | 77.3 | 1297 | 85.7 | 32.0 | 0.0 | 1 | 47.74 |
| bench | 6378-1 | 204 | 21x9x32 | 1694 | 0 | 90 | 90 | 100 | 5/50 | 70.4 | 0.70 | 89.6 | 193 | 72.7 | 110.6 | 65.3 | 1 | 3.93 |
| bench | 5891-1 | 460 | 29x12x44 | 4641 | 0 | 94 | 94 | 100 | 3/50 | 60.0 | 0.60 | 78.4 | 365 | 62.2 | 416.8 | 65.3 | 1 | 25.68 |
| bench | 10182-1 | 1665 | 39x17x58 | 10471 | 0 | 100 | 100 | 100 | 0/50 | 80.8 | 0.81 | 76.1 | 1266 | 84.5 | 244.9 | 65.3 | 1 | 72.47 |

### Table 1a, 63-part open tops → 88-part defaults

Object fill, mean over valid builds. The 63-part runs are table (ii) of the 1d write-up (open tops, no supports, no
cap). \* inflated: a control run shared the CPU for the first 4 minutes.

| object | set | parts recognized: 63 → 88 | object cells: 63 → 88 | cap rejected (88) | object fill %: 63 open tops → 88 defaults | s/candidate: 63 → 88 |
|---|---|---|---|---|---|---|
| table | 6378-1 | 203 → 204 | 1706 → 1706 | 0/50 | 54.4 → 54.3 | 10.1 → 12.0 |
| table | 5891-1 | 323 → 460 | 2501 → 4632 | 17/50 | 64.0 → 58.8 | 17.4 → 87.0 |
| table | 10182-1 | 1514 → 1665 | 9462 → 10609 | 3/50 | 77.9 → 78.9 | 65.2 → 127.9 * |
| chair | 6378-1 | 203 → 204 | 1641 → 1725 | 7/50 | 15.5 → 63.8 | 17.3 → 11.2 |
| chair | 5891-1 | 323 → 460 | 2488 → 4688 | 14/50 | 9.1 → 58.0 | 29.5 → 96.3 |
| chair | 10182-1 | 1514 → 1665 | 9265 → 10656 | 2/50 | 73.5 → 80.8 | 204.5 → 102.5 |
| car | 6378-1 | 203 → 204 | 1689 → 1689 | 0/50 | 68.8 → 69.8 | 2.6 → 4.2 |
| car | 5891-1 | 323 → 460 | 2555 → 4613 | 0/50 | 71.4 → 61.1 | 3.7 → 56.7 |
| car | 10182-1 | 1514 → 1665 | 9368 → 10704 | 3/50 | 85.2 → 82.7 | 17.8 → 53.3 |
| sofa | 6378-1 | 203 → 204 | 1589 → 1589 | 0/50 | 78.1 → 78.3 | 2.6 → 4.3 |
| sofa | 5891-1 | 323 → 460 | 2509 → 4678 | 0/50 | 84.6 → 60.6 | 4.3 → 67.5 |
| sofa | 10182-1 | 1514 → 1665 | 9113 → 10591 | 0/50 | 85.2 → 83.3 | 20.9 → 50.2 |
| vessel | 6378-1 | 203 → 204 | 1681 → 1681 | 0/50 | 75.6 → 75.4 | 2.2 → 4.4 |
| vessel | 5891-1 | 323 → 460 | 2478 → 4668 | 0/50 | 80.9 → 57.8 | 3.2 → 74.8 |
| vessel | 10182-1 | 1514 → 1665 | 9462 → 10683 | 1/50 | 85.1 → 85.5 | 18.9 → 47.7 |
| bench | 6378-1 | 203 → 204 | 1673 → 1694 | 5/50 | 70.7 → 70.4 | 2.2 → 3.9 |
| bench | 5891-1 | 323 → 460 | 2517 → 4641 | 3/50 | 74.6 → 60.0 | 4.5 → 25.7 |
| bench | 10182-1 | 1514 → 1665 | 9300 → 10471 | 0/50 | 83.2 → 80.8 | 29.6 → 72.5 |

### Table 1a, figure runs. Before / after on the demo sets (chair; before: solid columns, after: exact cells, pipeline defaults; lattice at fd9015b)

| set | target | grid (WxDxH) | target cells | valid % | cap rejected | fill % | IoU | best: parts | best: fill % | best: clutch | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 374-1 | columns | 10x8x39 | 1943 | 100 | 0/50 | 81.0 | 0.81 | 213 | 83.9 | 0.0 | 4.27 |
| 374-1 | exact, defaults | 13x13x53 | 1946 | 80 | 10/50 | 59.8 | 0.60 | 208 | 80.4 | 48.0 | 16.16 |
| 6378-1 | columns | 9x8x35 | 1596 | 100 | 0/50 | 70.8 | 0.71 | 189 | 74.0 | 8.0 | 5.63 |
| 6378-1 | exact, defaults | 13x12x51 | 1728 | 86 | 7/50 | 63.8 | 0.64 | 189 | 71.0 | 141.4 | 11.21 |
| 7743-1 | columns | 10x9x38 | 2031 | 90 | 5/50 | 70.8 | 0.71 | 275 | 74.6 | 505.0 | 12.50 |
| 7743-1 | exact, defaults | 13x13x54 | 1998 | 92 | 4/50 | 57.7 | 0.58 | 229 | 68.1 | 1007.4 | 27.47 |
| 5891-1 | columns | 13x12x50 | 4572 | 78 | 11/50 | 72.7 | 0.73 | 415 | 76.0 | 248.0 | 65.01 |
| 5891-1 | exact, defaults | 17x17x70 | 4700 | 72 | 14/50 | 58.0 | 0.58 | 357 | 58.8 | 131.6 | 96.34 |
| 4956-1 | columns | 14x13x57 | 6670 | 54 | 23/50 | 67.8 | 0.68 | 474 | 67.6 | 688.0 | 63.31 |
| 4956-1 | exact, defaults | 20x19x81 | 6633 | 62 | 19/50 | 58.0 | 0.58 | 396 | 59.4 | 393.4 | 98.17 |
| 10182-1 | columns | 17x16x68 | 10570 | 74 | 13/50 | 80.1 | 0.80 | 1479 | 82.1 | 819.4 | 117.23 |
| 10182-1 | exact, defaults | 23x22x94 | 10728 | 96 | 2/50 | 80.8 | 0.80 | 1266 | 81.4 | 263.4 | 102.47 |

### Table 1d, figure runs. The table on the demo sets (exact | pipeline defaults; 88-part catalog; lattice at fd9015b)

| object | set | target | object cells | support cells (% of object) | valid % | physics % | one piece % | object fill % | object IoU | overhang loss % | built outside object (cells) | best: parts | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| table | 374-1 | exact | 1934 | 0 (0%) | 98 | 98 | 100 | 53.0 | 0.53 | 42.4 | 0 | 192 | 15.50 |
| table | 374-1 | default | 1934 | 0 (0%) | 96 | 96 | 100 | 53.6 | 0.54 | 42.1 | 0 | 180 | 16.02 |
| table | 6378-1 | exact | 1706 | 0 (0%) | 100 | 100 | 100 | 16.0 | 0.16 | 81.5 | 0 | 167 | 18.23 |
| table | 6378-1 | default | 1706 | 0 (0%) | 100 | 100 | 100 | 54.3 | 0.54 | 41.3 | 0 | 176 | 12.01 |
| table | 7743-1 | exact | 2044 | 0 (0%) | 96 | 96 | 100 | 28.8 | 0.29 | 68.0 | 0 | 203 | 33.05 |
| table | 7743-1 | default | 2044 | 0 (0%) | 98 | 98 | 100 | 63.0 | 0.63 | 34.7 | 0 | 256 | 19.48 |
| table | 5891-1 | exact | 4632 | 0 (0%) | 84 | 84 | 100 | 21.5 | 0.22 | 76.7 | 0 | 397 | 97.60 |
| table | 5891-1 | default | 4632 | 0 (0%) | 66 | 66 | 100 | 58.8 | 0.59 | 36.9 | 0 | 390 | 86.99 |
| table | 4956-1 | exact | 6813 | 0 (0%) | 62 | 62 | 100 | 21.9 | 0.22 | 76.7 | 0 | 328 | 109.10 |
| table | 4956-1 | default | 6813 | 0 (0%) | 90 | 90 | 100 | 24.6 | 0.25 | 74.4 | 0 | 297 | 81.34 |
| table | 10182-1 | exact | 10609 | 0 (0%) | 22 | 22 | 100 | 37.4 | 0.37 | 60.1 | 0 | 1307 | 258.45 |
| table | 10182-1 | default | 10609 | 0 (0%) | 94 | 94 | 100 | 78.9 | 0.79 | 18.4 | 0 | 1371 | 127.90 |

## Step 1c — hollow targets (63-part catalog, open tops only)

`--hollow N` keeps an N-cell shell of the target (`shapes.hollow`: the mask minus its N-step erosion) plus 2x2
internal pillars every 4 studs, which run from the inside of the roof down to the floor so every roof cell over
the cavity has a support within reach. `scaled_to` then fits the *hollowed* volume to the inventory, so the
same parts make a larger object. Step 1b's mesh voxelizer (`bricks/mesh.py`, `trimesh`: `.obj`/`.stl`/`.ply`/`.off`,
watertight meshes only, z-up or y-up, plates stretched 2.5× so a stud is a cube) feeds the same path; this run
uses the BrickGPT structures as above.

Same 6 objects × 3 sets, solid (open tops) vs hollow (`--hollow 2`, open tops), 50 candidates each. **Every
run is 100% valid, 100% physics, 100% one piece.** Because the two targets have different cells, fill is not
comparable; the measure is the share of the object's *outer surface* cells the build covers (`shapes.surface`),
which is what a viewer sees.

| | result |
|---|---|
| object size | 1.00–1.21× larger along its longest side (vessel most, up to 1.21× on 10182-1) |
| surface covered, mean over valid builds | up on 13 of 18 runs; median change +0.9 points; range −10.5 (bench 5891-1) to +10.4 (sofa 10182-1) |
| surface covered, selected build | up on 11 of 18, equal on 1; largest gains on the chair (6378-1 49 → 62, 5891-1 58 → 68) |
| time per candidate | mixed: vessel 1.3–2.7× slower (10182-1: 19 → 50 s), chair 1.4–1.5× faster, the rest 0.5–1.6× the solid time |

**Conclusion.** Hollowing is sound (every guarantee holds) and gives a 0–21% larger object from the same parts,
but it does not by itself make the surface more complete: thin 2-cell walls on a small inventory leave gaps
(bench 5891-1, sofa 6378-1). It stays an option, off by default. Figure: `results/m12b_hollow_before_after.png`
(the vessel on the six demo sets, solid | hollow).

### Table 1c. Solid (open tops) vs hollow

| object | set | target | grid (WxDxH) | target cells | surface cells | valid % | physics % | one piece % | fill % | surface covered % | best: parts | best: surface covered % | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| table | 6378-1 | opentops | 18x17x46 | 1706 | 1151 | 100 | 100 | 100 | 54.4 | 50.2 | 185 | 59.8 | 10.07 |
| table | 6378-1 | hollow2 | 17x17x46 | 1664 | 1166 | 100 | 100 | 100 | 52.0 | 50.9 | 173 | 63.3 | 7.66 |
| table | 5891-1 | opentops | 20x18x52 | 2501 | 1459 | 100 | 100 | 100 | 64.0 | 58.4 | 262 | 68.3 | 17.41 |
| table | 5891-1 | hollow2 | 21x19x54 | 2491 | 1694 | 100 | 100 | 100 | 61.5 | 60.6 | 289 | 68.8 | 8.40 |
| table | 10182-1 | opentops | 31x29x81 | 9462 | 4202 | 100 | 100 | 100 | 77.9 | 72.1 | 1225 | 75.6 | 65.18 |
| table | 10182-1 | hollow2 | 34x34x91 | 9451 | 5227 | 100 | 100 | 100 | 58.9 | 65.4 | 1147 | 76.8 | 64.22 |
| chair | 6378-1 | opentops | 12x11x50 | 1641 | 1330 | 100 | 100 | 100 | 15.5 | 16.0 | 141 | 49.0 | 17.27 |
| chair | 6378-1 | hollow2 | 13x12x51 | 1684 | 1403 | 100 | 100 | 100 | 16.4 | 17.3 | 171 | 61.6 | 12.49 |
| chair | 5891-1 | opentops | 14x13x58 | 2488 | 1788 | 100 | 100 | 100 | 9.1 | 9.9 | 239 | 57.9 | 29.54 |
| chair | 5891-1 | hollow2 | 14x14x59 | 2481 | 1924 | 100 | 100 | 100 | 10.4 | 10.9 | 273 | 67.9 | 19.90 |
| chair | 10182-1 | opentops | 22x21x89 | 9265 | 5090 | 100 | 100 | 100 | 73.5 | 69.1 | 1158 | 78.0 | 204.46 |
| chair | 10182-1 | hollow2 | 23x22x94 | 9213 | 5573 | 100 | 100 | 100 | 73.7 | 71.9 | 1167 | 78.0 | 143.05 |
| car | 6378-1 | opentops | 9x18x20 | 1689 | 929 | 100 | 100 | 100 | 68.8 | 66.2 | 190 | 64.2 | 2.62 |
| car | 6378-1 | hollow2 | 9x18x20 | 1681 | 931 | 100 | 100 | 100 | 68.5 | 66.6 | 191 | 69.3 | 2.65 |
| car | 5891-1 | opentops | 10x21x22 | 2555 | 1254 | 100 | 100 | 100 | 71.4 | 68.0 | 283 | 72.9 | 3.71 |
| car | 5891-1 | hollow2 | 10x21x22 | 2476 | 1186 | 100 | 100 | 100 | 73.9 | 72.4 | 292 | 79.7 | 3.60 |
| car | 10182-1 | opentops | 15x33x34 | 9368 | 3071 | 100 | 100 | 100 | 85.2 | 77.9 | 1181 | 80.9 | 17.75 |
| car | 10182-1 | hollow2 | 16x35x36 | 9315 | 3542 | 100 | 100 | 100 | 77.2 | 78.2 | 1147 | 80.4 | 28.70 |
| sofa | 6378-1 | opentops | 17x13x14 | 1589 | 991 | 100 | 100 | 100 | 78.1 | 72.3 | 195 | 77.9 | 2.55 |
| sofa | 6378-1 | hollow2 | 18x14x15 | 1747 | 1134 | 100 | 100 | 100 | 70.3 | 64.5 | 190 | 65.4 | 3.44 |
| sofa | 5891-1 | opentops | 21x15x17 | 2509 | 1442 | 100 | 100 | 100 | 84.6 | 79.8 | 289 | 85.6 | 4.28 |
| sofa | 5891-1 | hollow2 | 22x15x18 | 2560 | 1582 | 100 | 100 | 100 | 83.2 | 82.5 | 308 | 84.3 | 4.81 |
| sofa | 10182-1 | opentops | 31x23x26 | 9113 | 3587 | 100 | 100 | 100 | 85.2 | 76.9 | 1157 | 77.2 | 20.93 |
| sofa | 10182-1 | hollow2 | 33x26x28 | 9285 | 4226 | 100 | 100 | 100 | 85.0 | 87.3 | 1221 | 85.0 | 26.77 |
| vessel | 6378-1 | opentops | 7x24x21 | 1681 | 870 | 100 | 100 | 100 | 75.6 | 68.5 | 193 | 72.1 | 2.22 |
| vessel | 6378-1 | hollow2 | 8x25x22 | 1684 | 982 | 100 | 100 | 100 | 67.4 | 65.6 | 185 | 70.6 | 4.38 |
| vessel | 5891-1 | opentops | 8x27x24 | 2478 | 1144 | 100 | 100 | 100 | 80.9 | 73.4 | 290 | 75.3 | 3.19 |
| vessel | 5891-1 | hollow2 | 9x29x26 | 2544 | 1428 | 100 | 100 | 100 | 72.8 | 74.6 | 287 | 76.4 | 7.05 |
| vessel | 10182-1 | opentops | 13x43x37 | 9462 | 3193 | 100 | 100 | 100 | 85.1 | 76.1 | 1170 | 77.2 | 18.87 |
| vessel | 10182-1 | hollow2 | 15x52x44 | 10279 | 4765 | 100 | 100 | 100 | 71.9 | 79.2 | 1191 | 78.8 | 50.40 |
| bench | 6378-1 | opentops | 21x9x32 | 1673 | 1228 | 100 | 100 | 100 | 70.7 | 72.9 | 184 | 70.4 | 2.21 |
| bench | 6378-1 | hollow2 | 22x9x32 | 1705 | 1323 | 100 | 100 | 100 | 70.5 | 72.4 | 187 | 73.8 | 2.30 |
| bench | 5891-1 | opentops | 23x10x35 | 2517 | 1604 | 100 | 100 | 100 | 74.6 | 76.0 | 287 | 80.0 | 4.51 |
| bench | 5891-1 | hollow2 | 27x11x40 | 2504 | 1896 | 100 | 100 | 100 | 57.9 | 65.5 | 267 | 76.8 | 6.07 |
| bench | 10182-1 | opentops | 37x16x56 | 9300 | 4644 | 100 | 100 | 100 | 83.2 | 80.5 | 1191 | 82.8 | 29.64 |
| bench | 10182-1 | hollow2 | 40x17x60 | 9424 | 5447 | 100 | 100 | 100 | 77.6 | 80.8 | 1145 | 82.4 | 35.74 |

### Table 1c, figure runs (vessel)

| object | set | target | grid (WxDxH) | target cells | surface cells | valid % | physics % | one piece % | fill % | surface covered % | best: parts | best: surface covered % | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vessel | 374-1 | opentops | 8x25x22 | 1952 | 973 | 100 | 100 | 100 | 77.7 | 69.1 | 208 | 75.0 | 2.95 |
| vessel | 374-1 | hollow2 | 8x26x23 | 1888 | 1071 | 100 | 100 | 100 | 73.6 | 70.8 | 203 | 74.2 | 3.87 |
| vessel | 6378-1 | opentops | 7x24x21 | 1681 | 870 | 100 | 100 | 100 | 75.6 | 68.5 | 193 | 72.1 | 2.22 |
| vessel | 6378-1 | hollow2 | 8x25x22 | 1684 | 982 | 100 | 100 | 100 | 67.4 | 65.6 | 185 | 70.6 | 4.38 |
| vessel | 7743-1 | opentops | 8x25x22 | 1970 | 982 | 100 | 100 | 100 | 76.6 | 69.2 | 232 | 76.4 | 4.68 |
| vessel | 7743-1 | hollow2 | 8x27x23 | 1889 | 1092 | 100 | 100 | 100 | 72.8 | 71.8 | 235 | 78.9 | 6.53 |
| vessel | 5891-1 | opentops | 8x27x24 | 2478 | 1144 | 100 | 100 | 100 | 80.9 | 73.4 | 290 | 75.3 | 3.19 |
| vessel | 5891-1 | hollow2 | 9x29x26 | 2544 | 1428 | 100 | 100 | 100 | 72.8 | 74.6 | 287 | 76.4 | 7.05 |
| vessel | 4956-1 | opentops | 9x32x27 | 3765 | 1595 | 100 | 100 | 100 | 77.0 | 69.0 | 348 | 73.4 | 8.28 |
| vessel | 4956-1 | hollow2 | 10x36x30 | 3738 | 2038 | 100 | 100 | 100 | 64.9 | 67.0 | 293 | 79.1 | 12.46 |
| vessel | 10182-1 | opentops | 13x43x37 | 9462 | 3193 | 100 | 100 | 100 | 85.1 | 76.1 | 1170 | 77.2 | 18.87 |
| vessel | 10182-1 | hollow2 | 15x52x44 | 10279 | 4765 | 100 | 100 | 100 | 71.9 | 79.2 | 1191 | 78.8 | 50.40 |


## Reproduce

The 88-part rerun (1a, Table 1a, the lattice figure runs), at fd9015b:

```
python -m brickwfc.experiments.brickgpt --out out/m12b_brickgpt_v2 --steps 1a 1d-figure --workers 10
```

It writes `results.md`, `summary.json`, `objects.png`, `before_after.png` (1a) and `overhangs_figure.md`,
`overhangs_figure_summary.json`, `overhangs_before_after.png` (1d-figure). Committed copy: `results/m12b_brickgpt_summary.json`.
The two figures are redrawn at a0ec36c (see `m12b_sizing.md`). The 5891-1 catalog control:

```
CAR=brickgpt:4b15b71c-f400-4e54-a118-f0c2afba6e17
for v in v1 v2; do
  python -m brickwfc.alt 5891-1 --shape $CAR --n 50 --k 1 --catalog m8 --style-version $v --workers 10 \
      --out out/m12b_brickgpt_v2/control/5891-1/4b15b71c_m8_$v
done
```

Step 1c and the 1d tables (`results/m12b_hollow_summary.json`, `results/m12b_overhangs_summary.json`,
`results/m12b_hollow_before_after.png`) are from commit 9c4a108, on the 63-part catalog before the support and
clutch defaults; `--steps 1c 1d` on main now runs them on the 88-part catalog with the defaults.
