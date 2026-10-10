# M12b sizing — slopes, thin parts and support columns

*Note (2026-10-10): the builds here predate the `_fit_key` fix (60b3a3b, `builder_version` 2: a tile that failed at a cell no longer makes the builder skip the plate of its box). On 9 set x object pairs the fix moves mean fill by -0.9 to +2.5 points (mean +0.5; within 1.2 SE on 8 pairs, +2.6 SE on the 4956-1 car; old vs fixed base in [`m12b_complete.md`](m12b_complete.md)); a rerun would give different individual builds. Since 49d5739 the thin-aware scale also keeps a thin post under its load, which gives the 5891-1 chair a different target under fillable sizing (2859 -> 2784 cells).*

The 88-part rerun (`m12b_brickgpt.md`) left two failures: on slope-heavy sets the target was too large to fill
(5891-1: object fill down 5–24 points), and narrow stems starved (the 4956-1 table: 45 of 50 builds stopped inside
its post). Fixing the first exposed two more: support columns on a fixed lattice land in different places at
different scales, and nearest-neighbour scaling thins a thin part unevenly. All four are fixed by construction,
three of them as new pipeline defaults (code at a0ec36c):

1. **Fillable sizing** (`--sizing fillable`, the default; `box` is the old path). A target is scaled to the
   inventory's volume, and a slope now counts its stud cells × 1 layer, not its box
   (`inventory.fillable_cells`): its sloped face takes nothing above it, so with open tops it goes only on the
   object's top surface. Studless slopes (ridges, cheese slopes) count 0; tiles count their box as before.
   On 5891-1 valid builds use 14–22% of the slopes' box volume (300–475 cells); the rule counts 377.
   5891-1's volume goes 4,675 → 2,882 cells (2,505 on the 63-part catalog), 4956-1's 6,787 → 4,382.
2. **Thin-aware scale** (part of fillable sizing). Among scale factors whose volume is within ±5% of the target,
   the one whose thinnest horizontal section is thickest wins, ties by the closest volume (`shapes.fit_scale`).
   Nearest-neighbour resampling had thinned the 10182-1 chair's post from 8 cells (old sizing) to 3.
3. **Support columns cover every far overhang cell** (`shapes.with_supports`). Instead of 2 × 2 columns on a
   fixed 4-stud lattice, columns go one at a time under the overhang cell farthest from every held cell and
   every column so far, until all overhang cells are within 3 studs. A chair's hub gets one column at every
   scale, a large chair's caster arms or a car's floor as many as they need. The lattice put 1 to 72 cells under
   the same chair depending on its scale; it is gone (lattice numbers: fd9015b).
4. Measured and **not adopted**: setting parts aside for thin sections (`--reserve-thin 9`) and visiting thin
   sections first (`--order thin`), at 838ee58. Neither gained beyond seed noise on two set × object pairs
   without losing valid builds (table below); both are removed.

Every run below: D2 + learned style (v2), the pipeline defaults otherwise (open tops, support columns up to 6
cells, clutch cap 1111), 50 candidates (10182-1 guards: 20), 5 workers. Fill is *object* fill (support cells are
outside the object), the mean over valid candidates ± its standard error; "selected" is the funnel's pick.

## Result: before (v2) → after (a0ec36c)

v2 is the 88-part rerun of `m12b_brickgpt.md` (box sizing, lattice supports, fd9015b).

| set | object | object cells | support cells | valid | cap rejected | mean fill % | selected fill % / clutch | s/candidate |
|---|---|---|---|---|---|---|---|---|
| 6378-1 | table | 1706 → 1748 | 0 → 0 | 50/50 → 48/50 | 0 → 2 | 54.3 ± 1.4 → 53.7 ± 1.8 | 65.8 / 58 → 67.6 / 285 | 12.0 → 8.9 |
| 6378-1 | chair | 1725 → 1725 | 3 → 12 | 43/50 → 50/50 | 7 → 0 | 63.8 ± 1.4 → 64.5 ± 0.9 | 71.0 / 141 → 69.1 / 141 | 11.2 → 11.7 |
| 6378-1 | car | 1689 → 1689 | 12 → 32 | 50/50 → 50/50 | 0 → 0 | 69.8 ± 0.4 → 69.7 ± 0.5 | 72.9 / 48 → 75.6 / 5 | 4.2 → 4.9 |
| 5891-1 | table | 4632 → 2880 | 0 → 0 | 33/50 → 34/50 | 17 → 16 | 58.8 ± 1.3 → 58.5 ± 2.0 | 69.5 / 696 → 67.7 / 101 | 87.0 → 64.5 |
| 5891-1 | chair | 4688 → 2847 | 12 → 12 | 36/50 → 46/50 | 14 → 4 | 58.0 ± 0.4 → 67.6 ± 1.1 | 58.7 / 132 → 78.9 / 144 | 96.3 → 63.0 |
| 5891-1 | car | 4613 → 2775 | 60 → 32 | 50/50 → 50/50 | 0 → 0 | 61.1 ± 0.4 → 76.6 ± 0.3 | 61.4 / 82 → 80.6 / 102 | 56.7 → 15.1 |
| 4956-1 | table | 6813 → 4414 | 0 → 0 | 45/50 → 42/50 | 5 → 8 | 24.6 ± 0.2 → 60.8 ± 1.0 | 26.5 / 1 → 68.0 / 482 | 81.3 → 77.2 |
| 4956-1 | chair | 6598 → 4318 | 35 → 16 | 31/50 → 36/50 | 19 → 14 | 58.0 ± 0.2 → 68.9 ± 0.7 | 59.4 / 393 → 75.1 / 511 | 98.2 → 73.8 |
| 4956-1 | car | — → 4474 | — → 80 | — → 49/50 | — → 1 | — → 72.0 ± 0.3 | — → 75.1 / 165 | — → 42.5 |
| 10182-1 | chair | 10656 → 10045 | 72 → 90 | 48/50 → 44/50 | 2 → 6 | 80.8 ± 0.3 → 83.2 ± 0.3 | 81.3 / 263 → 82.5 / 516 | 102.5 → 90.2 |
| 10182-1 | car | 10704 → 9526 | 276 → 252 | 47/50 → 20/20 | 3 → 0 | 82.7 ± 0.2 → 87.2 ± 0.2 | 83.9 / 204 → 88.6 / 42 | 53.3 → 47.8 |

- **5891-1:** the car recovers from 61.1 to 76.6% (the 63-part control was 72.6/73.2%) and takes about a
  quarter of the time per candidate (56.7 → 15.1 s); the table keeps its fill at 62% of the cells; the chair gains 9.6 points.
- **4956-1:** the table goes from 24.6 to 60.8% (61.7% on the 63-part catalog); 0 → 100% of valid tables reach the
  top. The chair gains 10.9 points and 5 valid builds. Sizing alone fixed the table: its post was 6 cells either
  way, it had starved because the target was too large for the small parts left after the base.
- **6378-1** has no slopes: the volume is unchanged. The thin-aware scale changes the table (thinnest section
  2 → 4 cells: 1,706 → 1,748 object cells); its mean fill is unchanged (53.7 vs 54.3). Chair and car: same.
- **10182-1:** the chair keeps its fill (80.8 → 83.2) with 44/50 valid (v2: 48/50); see the post below. The car gains
  4.5 points (its 20-candidate run against v2's 50).

## Lattice vs cover, at fillable sizing

| set | object | support cells: lattice / cover | valid: lattice → cover | mean fill %: lattice → cover | selected fill % / clutch: lattice → cover |
|---|---|---|---|---|---|
| 6378-1 | chair | 3 / 12 | 43/50 → 50/50 | 63.8 ± 1.4 → 64.5 ± 0.9 | 71.0 / 141 → 69.1 / 141 |
| 6378-1 | car | 12 / 32 | 50/50 → 50/50 | 69.8 ± 0.4 → 69.7 ± 0.5 | 72.9 / 48 → 75.6 / 5 |
| 5891-1 | chair | 4 / 12 | 29/50 → 46/50 | 19.0 ± 4.5 → 67.6 ± 1.1 | 68.0 / 343 → 78.9 / 144 |
| 5891-1 | car | 16 / 32 | 50/50 → 50/50 | 76.1 ± 0.3 → 76.6 ± 0.3 | 80.2 / 25 → 80.6 / 102 |
| 4956-1 | chair | 24 / 16 | 37/50 → 36/50 | 69.4 ± 0.6 → 68.9 ± 0.7 | 72.1 / 424 → 75.1 / 511 |
| 4956-1 | car | 60 / 80 | 47/50 → 49/50 | 73.3 ± 0.3 → 72.0 ± 0.3 | 77.4 / 302 → 75.1 / 165 |
| 10182-1 | chair | 54 / 90 | 1/20 → 0/20 | 83.3 → — | 83.3 / 440 → — |
| 10182-1 | car | 240 / 252 | 20/20 → 20/20 | 87.8 ± 0.3 → 87.2 ± 0.2 | 89.2 / 120 → 88.6 / 42 |

Both arms at the closest-volume scale (before the thin-aware scale); the 10182-1 chair with the thin-aware scale and
the cover is the "after" row above (44/50).

- The cover fixes the 5891-1 chair: at the new scale the lattice put a single 1-cell column under one arm, not
  the hub; the arms never met, and the repair pass kept one arm (20 of 29 valid chairs filled under 5%).
- **Known cost: the 4956-1 car loses 1.3 points** (73.3 ± 0.3 → 72.0 ± 0.3, about 3 standard errors) with 2 more
  valid builds; the cover puts 80 cells under it, the lattice 60. The 10182-1 car: −0.6 (87.8 ± 0.3 → 87.2 ± 0.2).
  The other cars are within noise.
- The cover's car builds are pictured in the sheet (after column, rows 4–6; the 6378-1 car:
  `out/m12b_sizing/6378-1/car_cover/build_01.png`).
- A single centre column per overhang (prototype, not adopted) matched the cover on the small chairs (identical
  masks) but failed the 10182-1 chair guard: 0/20 valid.

## Thin parts and the scale

The 10182-1 chair failed under every support rule at fillable sizing (lattice 1/20 valid, cover 0/20; all cap
rejections, required clutch 1,201–8,238 with the cover): its 148-cell seat sat on a 3-cell post 26 layers tall. The scale, not
the supports: nearest-neighbour resampling keeps 2 or 3 source cells of a thin part depending on the factor.

| target | box sizing | fillable, closest volume | fillable, thin-aware |
|---|---|---|---|
| chair 10182-1: post section (cells) | 8 | 3 | 6 |
| chair 4956-1 | 3 | 3 | 3 |
| chair 5891-1, 6378-1 | 2 | 2 | 2 |
| table 4956-1 | 9 | 6 | 6 |
| table 6378-1: thinnest section | 2 | 2 | 4 |

With the thin-aware scale the 10182-1 chair is 44/50 valid at 83.2% (6 cap rejections; the 20-candidate guard run
is its first 20 seeds, identical, 17/20). Raising
`--support-height` does not help here: a column under the seat would be 27 cells tall. A support height of 9
gives the 5891-1 chair the same mask as 6: the run at 9, generated from scratch, has the same cache key and the
same 50 candidates seed by seed. With a0ec36c, heights 6 and 9 give identical targets for all six objects on all
six demo sets.

## Not adopted: parts set aside for thin sections, thin sections first (838ee58, lattice supports)

| set | object | arm | valid | cap rejected | mean fill % | selected fill % / clutch |
|---|---|---|---|---|---|---|
| 6378-1 | table | no reserve | 50/50 | 0 | 54.3 ± 1.4 | 65.8 / 58 |
| 6378-1 | table | reserve 9 | 50/50 | 0 | 51.6 ± 1.1 | 52.2 / 100 |
| 6378-1 | chair | no reserve | 43/50 | 7 | 63.8 ± 1.4 | 71.0 / 141 |
| 6378-1 | chair | reserve 9 | 43/50 | 7 | 64.7 ± 1.1 | 71.5 / 340 |
| 5891-1 | table | no reserve | 34/50 | 16 | 58.5 ± 2.0 | 67.7 / 101 |
| 5891-1 | table | reserve 9 | 43/50 | 7 | 61.1 ± 1.5 | 71.8 / 208 |
| 5891-1 | chair | no reserve | 29/50 | 21 | 19.0 ± 4.5 | 68.0 / 343 |
| 5891-1 | chair | reserve 9 | 24/50 | 26 | 27.9 ± 5.8 | 68.8 / 622 |
| 4956-1 | table | no reserve | 42/50 | 8 | 60.8 ± 1.0 | 68.0 / 482 |
| 4956-1 | table | reserve 9 | 40/50 | 10 | 63.8 ± 1.2 | 64.9 / 693 |
| 4956-1 | table | thin sections first | 41/50 | 9 | 60.7 ± 1.1 | 68.2 / 457 |
| 4956-1 | chair | no reserve | 37/50 | 13 | 69.4 ± 0.6 | 72.1 / 424 |
| 4956-1 | chair | reserve 9 | 38/50 | 12 | 68.3 ± 0.8 | 73.9 / 147 |

Reserve 9 gains only on the 5891-1 table (+2.6, 34 → 43 valid); it loses valid builds on the 5891-1 chair and the
4956-1 table and fill on the 6378-1 table. Thin sections first equals no reserve (60.7 vs 60.8): the post is above
the base, and layers are built bottom to top, so the order within a layer cannot save parts for it.

## Figures

- `m12b_sizing_before_after.png`: v2 | after, the selected build of each (set, object) above; the 4956-1 car has no
  v2 run, its before is the lattice at fillable sizing.
- `m12b_opentops_before_after.png` (redrawn): the table on the six demo sets, exact target (no open tops, no
  supports) | the pipeline defaults; a full table on every set. Table "Figure runs (table)" below.
- `m12b_before_after.png` (redrawn): the chair on the six demo sets, solid columns | the pipeline defaults.

### Figure runs (chair)

| set | target | grid (WxDxH) | target cells | valid % | cap rejected | fill % | IoU | best: parts | best: fill % | best: clutch | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 374-1 | columns | 9x9x37 | 1985 | 100 | 0/50 | 76.5 | 0.76 | 212 | 79.3 | 72.0 | 4.93 |
| 374-1 | exact, defaults | 13x12x53 | 1926 | 88 | 6/50 | 69.5 | 0.69 | 199 | 76.0 | 419.5 | 15.08 |
| 6378-1 | columns | 9x8x35 | 1596 | 100 | 0/50 | 70.8 | 0.71 | 189 | 74.0 | 8.0 | 6.58 |
| 6378-1 | exact, defaults | 13x12x51 | 1737 | 100 | 0/50 | 64.5 | 0.64 | 182 | 69.3 | 141.0 | 11.74 |
| 7743-1 | columns | 9x9x37 | 1985 | 94 | 3/50 | 72.5 | 0.72 | 274 | 76.0 | 200.0 | 11.98 |
| 7743-1 | exact, defaults | 13x12x52 | 1964 | 88 | 6/50 | 65.0 | 0.65 | 244 | 74.9 | 42.0 | 21.93 |
| 5891-1 | columns | 11x10x44 | 2988 | 88 | 6/50 | 80.7 | 0.81 | 358 | 85.0 | 321.0 | 24.39 |
| 5891-1 | exact, defaults | 15x14x60 | 2859 | 92 | 4/50 | 67.6 | 0.67 | 313 | 79.0 | 144.0 | 63.04 |
| 4956-1 | columns | 12x11x50 | 4470 | 80 | 10/50 | 75.9 | 0.76 | 430 | 84.6 | 24.0 | 46.43 |
| 4956-1 | exact, defaults | 18x16x71 | 4334 | 72 | 14/50 | 68.9 | 0.69 | 355 | 75.2 | 510.9 | 73.76 |
| 10182-1 | columns | 16x15x65 | 9913 | 78 | 11/50 | 82.8 | 0.83 | 1467 | 84.7 | 862.5 | 104.38 |
| 10182-1 | exact, defaults | 22x21x91 | 10135 | 88 | 6/50 | 83.2 | 0.82 | 1271 | 82.6 | 515.8 | 90.21 |

### Figure runs (table)

| object | set | target | object cells | support cells (% of object) | valid % | physics % | one piece % | object fill % | object IoU | overhang loss % | built outside object (cells) | best: parts | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| table | 374-1 | exact | 1976 | 0 (0%) | 98 | 98 | 100 | 52.3 | 0.52 | 43.1 | 0 | 180 | 10.49 |
| table | 374-1 | default | 1976 | 0 (0%) | 96 | 96 | 100 | 53.6 | 0.54 | 42.0 | 0 | 176 | 10.46 |
| table | 6378-1 | exact | 1748 | 0 (0%) | 100 | 100 | 100 | 20.3 | 0.20 | 77.0 | 0 | 159 | 12.26 |
| table | 6378-1 | default | 1748 | 0 (0%) | 96 | 96 | 100 | 53.7 | 0.54 | 41.6 | 0 | 182 | 8.92 |
| table | 7743-1 | exact | 1976 | 0 (0%) | 98 | 98 | 100 | 34.2 | 0.34 | 61.6 | 0 | 171 | 20.19 |
| table | 7743-1 | default | 1976 | 0 (0%) | 100 | 100 | 100 | 58.0 | 0.58 | 39.3 | 0 | 245 | 13.37 |
| table | 5891-1 | exact | 2880 | 0 (0%) | 98 | 98 | 100 | 18.0 | 0.18 | 80.1 | 0 | 278 | 63.09 |
| table | 5891-1 | default | 2880 | 0 (0%) | 68 | 68 | 100 | 58.5 | 0.58 | 38.9 | 0 | 296 | 64.48 |
| table | 4956-1 | exact | 4414 | 0 (0%) | 76 | 76 | 100 | 24.1 | 0.24 | 73.8 | 0 | 374 | 90.63 |
| table | 4956-1 | default | 4414 | 0 (0%) | 84 | 84 | 100 | 60.8 | 0.61 | 36.4 | 0 | 390 | 77.21 |
| table | 10182-1 | exact | 10100 | 0 (0%) | 24 | 24 | 100 | 45.7 | 0.46 | 51.2 | 0 | 1269 | 229.75 |
| table | 10182-1 | default | 10100 | 0 (0%) | 96 | 96 | 100 | 78.3 | 0.78 | 19.8 | 0 | 1302 | 118.44 |

## Carried over

A target unchanged by a0ec36c gives the same cache key, so the same candidates: the 5891-1 and 4956-1 tables, the
chairs on 6378-1, 5891-1 and 4956-1, and the cars on all four sets. Fresh runs with a0ec36c (the figure runs)
confirm it for the tables and chairs: same key, 50/50 identical candidates (`same_runs` check in the reproduce
notes). Changed and rerun: the 6378-1 table and the 10182-1 chair.

## Reproduce

See `docs/reproduce.md`, section `results/m12b_sizing.md`.
