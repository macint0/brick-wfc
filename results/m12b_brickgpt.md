# M12b step 1 — true 3D targets, and a head-to-head on BrickGPT's data

**Steps 1a, 1b, 1c done; 1d in [`m12b_overhangs_tables.md`](m12b_overhangs_tables.md).** Targets can now be true
3D shapes instead of extruded heightfields:
- 1a: a StableText2Brick structure, `--shape brickgpt:<id>` (`bricks/brickgpt.py`);
- 1b: a watertight mesh, `--shape model.stl` (`bricks/mesh.py`, `trimesh`);
- 1c: either one hollowed (`--hollow N`);
- 1d: tiles may not cap thin parts (open tops, the default) and support columns are optional (`--supports`).

The generator was already 3D, so the funnel, the guarantees and the judge are unchanged.

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
inventory's volume, open tops on.

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

Every build of every run is 100% valid, 100% physics and 100% one piece. Tables:
- head-to-head: Table 1a below, with their clutch next to ours;
- exact targets without open tops: the 1d write-up, table (ii).

Findings:
- **Car, sofa, vessel, bench.** Mean fill is 69–85%, utilization 75–93%.
- **Table.** Mean fill 54/64/78 (6378-1 / 5891-1 / 10182-1).
- **Chair.** It is bimodal on the two small sets:
  - Mean fill is 15.5 (6378-1) and 9.1 (5891-1). 38/50 and 43/50 valid builds fill under 20% of the chair, but
    the rest are full chairs.
  - The funnel's fill floor and fill-weighted selection pick a full one (53.4% and 60.4% for the selected build).
  - On 10182-1, every chair fills 60–100% (mean 73.5).
  - The small-set split is not diagnosed yet. It is not the tile-capping below: open tops is already on.
- **Bimodal groups on 10182-1, before open tops.** Without open tops, the table and the chair on 10182-1 split
  into two groups of seeds. Table: 28/50 builds with mean fill 0.22, 22/50 with 0.71. Chair: 26/50 with 0.11, 24/50
    with 0.66.
  - In the low group, a tile or a brick's studless top had capped a thin stem (a table leg, the chair post), and
    nothing could be built above it.
  - Open tops allows a studless top only where the target is empty directly above, which removes the low group.
  - Table 10182-1: fill 43.5 → 77.9, all 50 builds in 0.6–1.0. Chair 10182-1: 37.2 → 73.5.
  - It is a sound restriction: it only removes placements, so no guarantee changes.

**The full chairs exceed real clutch** (from `overhangs_summary.json`):
- Full chairs (fill > 40%) need clutch above 1111 in 82–98% of cases: the seat and back are long
  cantilevers.
- The selected builds need 1427–5212 on the six demo sets. Their chair needs 816.
- Under our physics these chairs stand only if studs held harder than real ones do.
- **Support columns fix it.** With `--supports`, 84/88/100% of chair builds stay within 1111 at mean fill
  53/28/72. With open tops alone, only 80/88/2% stay within 1111, at fill 15/9/74.
- Tables, cars, sofas, vessels and benches with open tops stay within 1111 in 96–100% of builds.

The calibration therefore says:
- **Finite clutch is the right criterion for everything except long cantilevers:** for those objects, finite and
  calibrated clutch agree on 96–100% of builds.
- **For long cantilevers, support columns are the lever:** a clutch cap only removes builds, and open tops does
  not shorten a cantilever.

A calibrated `--max-clutch 1111` as the pipeline default (with `--supports` for cantilevered targets) is the
proposed follow-up. It is not applied here.

### Before / after: `results/m12b_before_after.png`

The chair on the six M12 demo sets:
- **before:** the pipeline as of M12, the target as solid columns (the heightfield input, `--shape-columns`);
- **after:** step 1, exact 3D cells with open tops.

The labels follow the M12 sheet: `set: parts used of parts in the set`, then fill, stands, pieces. Every pictured
build is valid, stands and is one piece. Before, every set produces a solid block. After, each set produces a
chair with legs, a seat and a back.

*Note on size:* both targets are scaled to the same volume (the inventory's), so the solid-column "before" chair
is physically smaller (e.g. 10 × 8 × 39 vs 13 × 12 × 53 cells on 374-1). Its higher fill (70–79% vs 9–74%) is
fill of an easier, block-shaped target.

## Tables

### Table 1a. Ours (D2 + learned style from one set's inventory; the structure's exact cells as target, open tops)

| object | set | inventory parts | grid (WxDxH) | target cells | valid % | physics % | one piece % | fill % | IoU | utilization % | best: parts | best: fill % | best: clutch | their clutch | best: pieces | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| table | 6378-1 | 203 | 18x17x46 | 1706 | 100 | 100 | 100 | 54.4 | 0.54 | 72.6 | 185 | 67.3 | 163.2 | 131.2 | 1 | 10.07 |
| table | 5891-1 | 323 | 20x18x52 | 2501 | 100 | 100 | 100 | 64.0 | 0.64 | 77.9 | 262 | 72.7 | 462.0 | 131.2 | 1 | 17.41 |
| table | 10182-1 | 1514 | 31x29x81 | 9462 | 100 | 100 | 100 | 77.9 | 0.78 | 78.0 | 1225 | 80.7 | 573.0 | 131.2 | 1 | 65.18 |
| chair | 6378-1 | 203 | 12x11x50 | 1641 | 100 | 100 | 100 | 15.5 | 0.16 | 24.6 | 141 | 53.4 | 3710.0 | 815.9 | 1 | 17.27 |
| chair | 5891-1 | 323 | 14x13x58 | 2488 | 100 | 100 | 100 | 9.1 | 0.09 | 14.8 | 239 | 60.4 | 1426.5 | 815.9 | 1 | 29.54 |
| chair | 10182-1 | 1514 | 22x21x89 | 9265 | 100 | 100 | 100 | 73.5 | 0.73 | 73.5 | 1158 | 80.6 | 3744.2 | 815.9 | 1 | 204.46 |
| car | 6378-1 | 203 | 9x18x20 | 1689 | 100 | 100 | 100 | 68.8 | 0.69 | 89.9 | 190 | 72.4 | 41.0 | 72.0 | 1 | 2.62 |
| car | 5891-1 | 323 | 10x21x22 | 2555 | 100 | 100 | 100 | 71.4 | 0.71 | 86.4 | 283 | 78.2 | 34.3 | 72.0 | 1 | 3.71 |
| car | 10182-1 | 1514 | 15x33x34 | 9368 | 100 | 100 | 100 | 85.2 | 0.85 | 77.7 | 1181 | 88.5 | 273.0 | 72.0 | 1 | 17.75 |
| sofa | 6378-1 | 203 | 17x13x14 | 1589 | 100 | 100 | 100 | 78.1 | 0.78 | 92.6 | 195 | 81.9 | 72.0 | 0.0 | 1 | 2.55 |
| sofa | 5891-1 | 323 | 21x15x17 | 2509 | 100 | 100 | 100 | 84.6 | 0.85 | 89.8 | 289 | 87.5 | 38.2 | 0.0 | 1 | 4.28 |
| sofa | 10182-1 | 1514 | 31x23x26 | 9113 | 100 | 100 | 100 | 85.2 | 0.85 | 74.7 | 1157 | 85.8 | 48.0 | 0.0 | 1 | 20.93 |
| vessel | 6378-1 | 203 | 7x24x21 | 1681 | 100 | 100 | 100 | 75.6 | 0.76 | 92.2 | 193 | 78.6 | 6.0 | 0.0 | 1 | 2.22 |
| vessel | 5891-1 | 323 | 8x27x24 | 2478 | 100 | 100 | 100 | 80.9 | 0.81 | 87.1 | 290 | 81.6 | 8.0 | 0.0 | 1 | 3.19 |
| vessel | 10182-1 | 1514 | 13x43x37 | 9462 | 100 | 100 | 100 | 85.1 | 0.85 | 76.4 | 1170 | 86.2 | 24.0 | 0.0 | 1 | 18.87 |
| bench | 6378-1 | 203 | 21x9x32 | 1673 | 100 | 100 | 100 | 70.7 | 0.71 | 88.4 | 184 | 73.5 | 221.0 | 65.3 | 1 | 2.21 |
| bench | 5891-1 | 323 | 23x10x35 | 2517 | 100 | 100 | 100 | 74.6 | 0.75 | 85.3 | 287 | 85.9 | 88.7 | 65.3 | 1 | 4.51 |
| bench | 10182-1 | 1514 | 37x16x56 | 9300 | 100 | 100 | 100 | 83.2 | 0.83 | 76.3 | 1191 | 85.4 | 139.0 | 65.3 | 1 | 29.64 |

### Table 1a, figure runs. Before / after on the demo sets (chair; before: solid columns, after: exact cells with open tops)

| set | target | grid (WxDxH) | target cells | valid % | fill % | IoU | best: parts | best: fill % | best: clutch | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|
| 374-1 | columns | 10x8x39 | 1881 | 100 | 78.1 | 0.78 | 205 | 80.4 | 0.9 | 5.29 |
| 374-1 | exact, open tops | 13x12x53 | 1861 | 100 | 24.1 | 0.24 | 179 | 65.0 | 3988.8 | 9.70 |
| 6378-1 | columns | 9x8x35 | 1596 | 100 | 70.1 | 0.70 | 186 | 74.3 | 0.0 | 6.12 |
| 6378-1 | exact, open tops | 12x11x50 | 1641 | 100 | 15.5 | 0.16 | 141 | 53.4 | 3710.0 | 17.27 |
| 7743-1 | columns | 10x8x39 | 1943 | 100 | 72.2 | 0.72 | 263 | 76.6 | 192.0 | 10.21 |
| 7743-1 | exact, open tops | 13x13x53 | 1943 | 100 | 23.6 | 0.24 | 202 | 64.6 | 5211.7 | 16.54 |
| 5891-1 | columns | 10x9x41 | 2512 | 100 | 77.9 | 0.78 | 305 | 81.4 | 1618.0 | 7.96 |
| 5891-1 | exact, open tops | 14x13x58 | 2488 | 100 | 9.1 | 0.09 | 239 | 60.4 | 1426.5 | 29.54 |
| 4956-1 | columns | 11x11x46 | 3779 | 100 | 78.8 | 0.79 | 375 | 84.5 | 902.0 | 15.00 |
| 4956-1 | exact, open tops | 17x16x67 | 3844 | 100 | 38.0 | 0.38 | 319 | 61.3 | 1486.0 | 25.65 |
| 10182-1 | columns | 16x15x64 | 9284 | 100 | 79.1 | 0.79 | 1354 | 81.4 | 1311.0 | 84.02 |
| 10182-1 | exact, open tops | 22x21x89 | 9265 | 100 | 73.5 | 0.73 | 1158 | 80.6 | 3744.2 | 204.46 |

## Step 1c — hollow targets

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

```
python -m brickwfc.experiments.brickgpt --out out/m12b_brickgpt --steps 1d 1c 1a --workers 6
```

The run writes `results.md`, `hollow.md` and `overhangs.md` (tables), `summary.json`, `hollow_summary.json` and
`overhangs_summary.json`, and the three figures. Committed copies: `results/m12b_brickgpt_summary.json`,
`results/m12b_hollow_summary.json`, `results/m12b_overhangs_summary.json`, `results/m12b_before_after.png`,
`results/m12b_hollow_before_after.png`, `results/m12b_opentops_before_after.png`. The 1a step reuses the 1d
open-tops runs.
