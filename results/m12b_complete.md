# M12b completeness: how much of the target the builds fill, and where they don't

Mac (2026-10-10): the builds are recognizable but incomplete; a smaller complete object beats a larger partial one.
This write-up measures completeness on the runs that already exist (no generation) and, in a second part, why
target cells stay empty as the builder saw them. A third part fixes what that found (a builder bug, two scale
failures), sweeps hanging support, usable sizing and fill slack on 9 pairs, and says what still blocks completeness. A fourth keeps small parts for the hole pass (two builder options, 6 arms) and diagnoses the best arm. A fifth measures, by replay only, a small-part budget sizing and the bound of a remnant-aware placement score; neither holds.

**Runs.** Pipeline defaults at 3985e76 (fillable sizing, thin-aware scale, covering support columns up to 6 cells, open
tops, clutch cap 1111): the chair (a712684f) and table (858f0955) on the six M12 demo sets
(`out/m12b_sizing_fig/<set>/<object>_default`, the sizing figure runs) and the car (4b15b71c) on the four sets it was
run on (`out/m12b_sizing/<set>/car_cover`; 20 candidates on 10182-1, 50 elsewhere). No current-defaults car run exists
for 374-1 or 7743-1.

**Metrics** (`experiments/complete.py`), against the target as built in (support columns included, as the pipeline's
fill):
- **fill**: share of target cells filled;
- **holes**: connected components (across faces) of unfilled target cells: count, and the largest one's size in cells;
- **surface**: share of the target's outer surface cells (`shapes.surface`) that are filled;
- **unfilled on surface**: share of the unfilled cells that lie on that surface (the rest are inside).

**Complete** (cf, 2026-10-10): fill ≥ 97%, no hole larger than 4 cells, surface ≥ 98%.

## Final state

"valid" counts candidates that pass every check (integrity, inventory, support, shape, physics within 1111, one piece),
before the funnel's size and fill floors; means are over those. "sel" is the selected build.

| object | set | target cells | valid | complete | fill % (sel / mean) | holes (sel / mean) | largest hole (sel / mean) | unfilled cells (sel) | surface % (sel / mean) | unfilled on surface % (sel / mean) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| chair | 6378-1 | 1737 | 50/50 | 0 | 69.3 / 64.7 | 27 / 22.9 | 211 / 319 | 533 | 66.0 / 63.7 | 91 / 85 |
| chair | 5891-1 | 2859 | 46/50 | 0 | 79.0 / 67.7 | 48 / 38.1 | 235 / 436 | 601 | 72.9 / 63.7 | 91 / 80 |
| chair | 4956-1 | 4334 | 36/50 | 0 | 75.2 / 69.0 | 33 / 34.5 | 475 / 606 | 1075 | 71.5 / 65.5 | 78 / 76 |
| chair | 374-1 | 1926 | 44/50 | 0 | 76.0 / 69.6 | 23 / 24.8 | 147 / 246 | 463 | 71.4 / 66.1 | 93 / 88 |
| chair | 7743-1 | 1964 | 44/50 | 0 | 74.9 / 65.1 | 19 / 20.5 | 238 / 349 | 492 | 70.6 / 63.8 | 91 / 82 |
| chair | 10182-1 | 10135 | 44/50 | 0 | 82.6 / 83.2 | 85 / 95.3 | 890 / 754 | 1760 | 76.3 / 77.5 | 72 / 71 |
| table | 6378-1 | 1748 | 48/50 | 0 | 67.6 / 53.7 | 19 / 14.6 | 489 / 491 | 567 | 68.5 / 49.3 | 66 / 76 |
| table | 5891-1 | 2880 | 34/50 | 0 | 67.7 / 58.5 | 24 / 24.3 | 764 / 893 | 929 | 62.9 / 54.0 | 66 / 65 |
| table | 4956-1 | 4414 | 42/50 | 0 | 68.0 / 60.8 | 33 / 23.6 | 1149 / 1445 | 1412 | 63.4 / 58.0 | 60 / 57 |
| table | 374-1 | 1976 | 48/50 | 0 | 61.5 / 53.6 | 9 / 9.2 | 576 / 657 | 760 | 55.1 / 45.7 | 72 / 73 |
| table | 7743-1 | 1976 | 50/50 | 0 | 71.8 / 58.0 | 18 / 9.3 | 358 / 559 | 557 | 65.8 / 50.8 | 75 / 74 |
| table | 10182-1 | 10100 | 48/50 | 0 | 79.4 / 78.3 | 81 / 73.3 | 1616 / 1661 | 2082 | 74.7 / 72.7 | 54 / 56 |
| car | 6378-1 | 1721 | 50/50 | 0 | 75.9 / 70.2 | 26 / 23.3 | 263 / 307 | 414 | 72.8 / 67.6 | 63 / 61 |
| car | 5891-1 | 2807 | 50/50 | 0 | 80.8 / 76.8 | 64 / 49.2 | 305 / 377 | 538 | 73.1 / 73.2 | 65 / 54 |
| car | 4956-1 | 4554 | 49/50 | 0 | 75.4 / 72.4 | 35 / 30.1 | 944 / 776 | 1120 | 70.8 / 68.9 | 49 / 46 |
| car | 10182-1 | 9778 | 20/20 | 0 | 88.9 / 87.5 | 92 / 106.5 | 356 / 339 | 1089 | 82.7 / 82.9 | 53 / 46 |

**No valid candidate on any pair is complete** (0 of 753). The selected builds fill 62–89% of their target and 55–83%
of its surface.

### Missing maps: `m12b_complete_missing.png`

Each selected build is drawn in grey (each part keeps its brightness), with its unfilled target cells in red. Rows:
chair, table, car. Columns: 6378-1, 5891-1, 4956-1, 374-1, 7743-1, 10182-1. The sets have many red parts, so the
build's own colors would hide the red.

- **Chairs:** the four caster arm tips are missing whole on every set; the seat's underside and the backrest's edges
  are spotty. 72–93% of the unfilled cells are on the surface.
- **Tables:** the top's rim and underside, and the upturned foot ends. The empty space under the top is one connected
  component, so the table's "largest hole" (358–1616 cells) is mostly the top's underside layer.
- **Cars:** scattered surface patches, and more of the unfilled cells inside (35–51% of them).

What goes missing is mostly overhang undersides and tips, not an interior shortfall.


## Why cells stay empty: traced replay

**Builds.** 10 builds per pair, 160 in all: the selected build and the 9 lowest-seed other valid candidates. Each
is replayed from its cached run with a trace on the builder (`BottomUpBuilder.trace`). The trace draws nothing from
the generator, and every replay was checked to be identical to the cached build (160/160). The run context is
rebuilt from the run's stats.json, and its cache key must equal the cached one.

**Causes.** Every unfilled target cell gets the cause of its last visit, as the builder saw it then:

- **support**: no stud within a part's reach below, or no placement that fits the free space has a stud under it;
- **repair**: the cell was filled before a connect repair returned its part to the inventory (the cause of the
  refill's miss is in the last column);
- **inventory**: a placement fits and balances, but only with a part that is used up;
- **skipped**: the solid-share draw passed the cell over (about 5% of visits), and no later part covered it;
- **balance**: placements fit, but each one would tip its cluster over;
- **geometry**: no part fits the free space (target too narrow there, or the open-top or tile rules);
- **missed**: a remaining part fits and balances, yet the builder placed nothing (the `_fit_key` bug below).

Shares are of all unfilled cells of the pair's 10 builds; the mean row weighs each pair the same.

| object | set | builds | unfilled / build | support % | repair % | inventory % | skipped % | balance % | geometry % | missed % | on surface % | repair refill: support / inventory / skipped % |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| chair | 6378-1 | 10 | 657 | 65 | 25 | 4 | 4 | 1 | 0 | 0 | 82 | 87 / 0 / 7 |
| chair | 5891-1 | 10 | 846 | 61 | 26 | 5 | 4 | 3 | 2 | 0 | 82 | 88 / 0 / 6 |
| chair | 4956-1 | 10 | 1343 | 70 | 17 | 6 | 4 | 2 | 0 | 1 | 74 | 89 / 0 / 6 |
| chair | 374-1 | 10 | 583 | 61 | 21 | 12 | 4 | 1 | 0 | 0 | 85 | 86 / 1 / 7 |
| chair | 7743-1 | 10 | 638 | 65 | 24 | 5 | 4 | 1 | 0 | 1 | 83 | 87 / 0 / 8 |
| chair | 10182-1 | 10 | 1660 | 59 | 21 | 14 | 4 | 0 | 2 | 0 | 72 | 91 / 0 / 5 |
| table | 6378-1 | 10 | 853 | 67 | 26 | 4 | 3 | 0 | 0 | 0 | 70 | 82 / 0 / 6 |
| table | 5891-1 | 10 | 1308 | 73 | 21 | 3 | 4 | 0 | 0 | 0 | 61 | 84 / 0 / 7 |
| table | 4956-1 | 10 | 1729 | 76 | 11 | 8 | 4 | 0 | 0 | 0 | 55 | 82 / 3 / 7 |
| table | 374-1 | 10 | 942 | 62 | 27 | 6 | 3 | 0 | 0 | 0 | 72 | 81 / 0 / 7 |
| table | 7743-1 | 10 | 796 | 63 | 31 | 1 | 3 | 1 | 0 | 0 | 73 | 82 / 0 / 6 |
| table | 10182-1 | 10 | 2024 | 76 | 6 | 12 | 4 | 0 | 1 | 0 | 55 | 87 / 1 / 6 |
| car | 6378-1 | 10 | 499 | 67 | 0 | 23 | 6 | 1 | 0 | 2 | 59 | 62 / 19 / 12 |
| car | 5891-1 | 10 | 642 | 75 | 0 | 16 | 6 | 1 | 1 | 1 | 54 | 73 / 13 / 10 |
| car | 4956-1 | 10 | 1286 | 63 | 3 | 25 | 5 | 0 | 0 | 4 | 46 | 80 / 8 / 7 |
| car | 10182-1 | 10 | 1215 | 55 | 1 | 29 | 5 | 0 | 2 | 8 | 46 | 78 / 10 / 7 |
| **mean of pairs** | | | | 66 | 16 | 11 | 4 | 1 | 1 | 1 | | |

Per cause, the share of its cells on the target's outer surface (all pairs pooled):

| cause | cells | on surface % |
|---|---:|---:|
| inventory | 18892 | 48 |
| support | 113819 | 61 |
| balance | 1012 | 58 |
| repair | 26172 | 95 |
| skipped | 7188 | 60 |
| geometry | 1363 | 50 |
| missed | 1768 | 37 |

**The three biggest causes:**

1. **Support, 66% of unfilled cells** (55–76% per pair). This is the underside of everything that overhangs: the
   seat, the table top, the car's body over its wheels, the backrest's lower rim. Bottom-up, a part needs a stud
   below it within reach, and the lowest layer of an overhang never has one.
2. **Connect repair, 16%** (0–31%; 17–31% on chairs and tables, 0–3% on cars). These are the chair's caster arm
   tips and the table's foot ends: they start as separate stacks, lose to the largest cluster, and go back to the
   inventory. The last repair round refills only above the ground, so the tips are not rebuilt. 95% of these cells
   are on the surface.
3. **Inventory, 11%** (1–14% on chairs and tables, 16–29% on cars). Parts that would fit are used up. On the cars
   this is the second cause: the car's body is a large volume of small cells.

Skipped (4%), balance (1%), geometry (1%) and missed (1%) are small.

### What a hanging rule can reach

Support-blocked cells with a placed part directly above them (1 cell up) or within 2 cells up, in the final build.
A part hanging by its studs from the part above reaches the first group directly; the second needs a second hung
part below it. Repair cells are listed for contrast: nothing is above a caster arm tip.

| object | set | support cells | part 1 up % | part 1-2 up % | repair cells | part 1 up % | part 1-2 up % |
|---|---|---:|---:|---:|---:|---:|---:|
| chair | 6378-1 | 4296 | 24 | 42 | 1635 | 0 | 1 |
| chair | 5891-1 | 5121 | 30 | 51 | 2165 | 0 | 1 |
| chair | 4956-1 | 9348 | 27 | 48 | 2296 | 1 | 2 |
| chair | 374-1 | 3539 | 32 | 54 | 1249 | 1 | 1 |
| chair | 7743-1 | 4141 | 32 | 52 | 1512 | 0 | 0 |
| chair | 10182-1 | 9713 | 38 | 62 | 3562 | 1 | 1 |
| table | 6378-1 | 5704 | 24 | 39 | 2194 | 0 | 0 |
| table | 5891-1 | 9490 | 25 | 47 | 2725 | 0 | 0 |
| table | 4956-1 | 13198 | 25 | 47 | 1934 | 1 | 2 |
| table | 374-1 | 5867 | 31 | 55 | 2555 | 0 | 0 |
| table | 7743-1 | 4990 | 32 | 53 | 2474 | 0 | 0 |
| table | 10182-1 | 15436 | 38 | 63 | 1289 | 1 | 2 |
| car | 6378-1 | 3358 | 29 | 53 | 16 | 6 | 31 |
| car | 5891-1 | 4828 | 34 | 62 | 30 | 0 | 3 |
| car | 4956-1 | 8133 | 32 | 52 | 381 | 6 | 14 |
| car | 10182-1 | 6657 | 39 | 59 | 155 | 8 | 17 |

24–39% of support-blocked cells have a part directly above, 39–63% within 2 cells. The rest have empty target above
them too: they lie under other unfilled cells (an overhang's lower layers, whose upper layers are themselves
missing). Repair cells have almost nothing above them (0–8%, the car's 31% is 16 cells). A hanging rule cannot reach
them; keeping the tips needs a different repair.

### Builder bug: `_fit_key` ignores studs

The probe of the "missed" cells (the 4956-1 chair, seed 4: 68 of them) found one cause. In `_fill`, a part that
fails at a cell puts its box (`_fit_key`: size_y, size_z, size_x for a rectangular part) in a `failed` set, and
every other part with that box is then skipped at that cell. Since open tops (M12b step 1d), whether a part fits
also depends on its studs: a tile's studless top may not sit under a target cell, a plate's may. So a tile that fails
there blocks the studded plate of the same box. In that build every missed visit is a round 1x1 plate (6141) skipped
after a 1x1 tile failed, the plain 1x1 plate being used up. 1768 of 170,214 unfilled cells (1%) are missed; cars
show the most (2–8%). Fixed on this branch (below); every number before the fix, `m12b_brickgpt`, `m12b_sizing`,
`m12b_skins` included, was produced with the bug.

## Fixes

### `_fit_key` counts studs (60b3a3b)

A rectangular part's key is now its box and whether it has studs, in the main pass and in the hole pass alike
(`test_failed_tile_does_not_block_plate_of_same_box`). Builds change only where a tile can fail and a plate of its box
fit: open tops and connect repair rounds; plain D and D2 builds are identical, three golden fingerprints of connect
builds changed. Cached runs are keyed by `builder_version` 2 now, so a pre-fix cache is refused instead of reused.

Old (cached, pre-fix) vs fixed base, the same 50 seeds and the same targets, mean fill of the valid candidates ± SE
(the 5891-1 chair's fixed base is the run before the moment key below, on the old target):

| object | set | old fill % | fixed fill % | Δ points | Δ / SE | old valid | fixed valid |
|---|---|---:|---:|---:|---:|---:|---:|
| chair | 6378-1 | 64.7 ± 0.9 | 65.3 ± 0.8 | +0.7 | +0.6 | 50/50 | 50/50 |
| chair | 5891-1 | 67.7 ± 1.1 | 69.0 ± 0.8 | +1.3 | +1.0 | 46/50 | 49/50 |
| chair | 4956-1 | 69.0 ± 0.7 | 68.7 ± 0.6 | -0.3 | -0.3 | 36/50 | 42/50 |
| table | 6378-1 | 53.7 ± 1.8 | 56.2 ± 1.1 | +2.5 | +1.2 | 48/50 | 49/50 |
| table | 5891-1 | 58.5 ± 2.0 | 59.2 ± 1.5 | +0.8 | +0.3 | 34/50 | 38/50 |
| table | 4956-1 | 60.8 ± 1.0 | 59.9 ± 1.1 | -0.9 | -0.6 | 42/50 | 36/50 |
| car | 6378-1 | 70.2 ± 0.4 | 70.2 ± 0.4 | -0.0 | -0.1 | 50/50 | 50/50 |
| car | 5891-1 | 76.8 ± 0.3 | 76.5 ± 0.2 | -0.3 | -0.9 | 50/50 | 50/50 |
| car | 4956-1 | 72.4 ± 0.3 | 73.4 ± 0.3 | +1.0 | +2.6 | 49/50 | 47/50 |

Mean Δ +0.5 points; 8 of 9 pairs within 1.2 SE, the 4956-1 car +1.0 point at 2.6 SE. Valid counts move both ways
(4956-1 chair +6, 4956-1 table −6). The earlier write-ups (`m12b_brickgpt`, `m12b_sizing`, `m12b_skins`,
`m12b_symmetry_threshold`, `m12b_skins_soft`) are not rerun (cf, 2026-10-10); each carries a note that its builds
predate the fix.

### Usable sizing and fill slack (60b3a3b)

`--sizing usable`: fillable sizing, then leave out every part that fits nowhere inside the scaled target (in any
orientation, `inventory.fits_inside`), rescale to the parts left, and repeat until nothing more is left out (at most 5
rounds). `--fill-slack s` scales to s × that volume. On the sweep's 9 pairs only the 6378-1 chair leaves anything out
at 1.0 (4 × plate 6x14, 336 cells; the scaled target is 11 × 12 studs across), and the 4956-1 chair 2 × brick 1x16 at
0.9 and 0.8; every pair settles within 2 rounds.

### The scale cut a thin post (0dbb3b6)

The sweep's first pass gave the 6378-1 chair 9.3% fill at usable 1.0 and 17.1% at 0.8, with every build valid:
nearest-neighbour resampling had dropped the chair's 2-cell post entirely (13 and 11 empty layers between base and
seat), so the builder built the base and nothing joined the seat. The thin-aware scale did not prevent it because
`shapes.thinnest_section` skipped empty layers, so a factor that deleted the post scored as thick. Now an empty layer
between the lowest and highest filled layer is a section of 0, and if every factor in the 5% band cuts the shape, the
band widens once to 10% (`test_keep_sections_does_not_cut_a_thin_post`). Of the sweep's 90 sized targets (5 arms × 9
pairs, with and without support columns) only those two change.

### The scale put a post off its load (49d5739)

At usable 0.9 the 5891-1 chair gave 3 valid builds of 50 (the hang arm, at 1.0: 50/50). Not inventory (nothing left
out), not the cut above (the post is 2 cells on all 16 layers), not tip-over: all 47 failures need more than real
clutch (1124–3202 per stud, median 1554, cap 1111; hang's median 144). The support cover never reaches the seat (the
seat starts 26 layers up; support columns stop at 6), so at every scale the seat and back hang on a 1 × 2 post. What
changes at 0.9 is where resampling puts that post under them:

| 5891-1 chair | post | cells above it | their centre of mass from the post's centre | lever | moment (cells × lever) | clutch failures |
|---|---|---:|---:|---:|---:|---:|
| 1.0 (hang) | 1 × 2, y10–26 | 2387 | dz +0.28, dx −0.07 | 0.29 | 696 | 0/50 |
| usable 0.9 | 1 × 2, y10–25 | 2158 | dz +1.22, dx −0.55 | 1.34 | 2890 | 47/50 |
| usable 0.8 | 1 × 2, y10–24 | 1894 | dz +0.37, dx −0.56 | 0.67 | 1273 | 6/50 |

(The post is 1 stud wide in z, so at 0.9 the load's centre lies 0.72 studs beyond it.) Which joints bind: the duals
of the clutch LP's limits over the 47 failed builds put 66% of the binding weight on the seat-on-post joint (y26–28,
e.g. a 6 × 10 plate on the post's top 1 × 2 brick), 14% inside the post and 18% in the base under it (y4–9). This is
the first evidence that the scale's resampling phase, not the inventory or the builder, decides whether a build can
stand: two factors 5% apart give the same chair a 4.2× larger moment on one stud joint.

Fix: `shapes.overhang_moment` is, per layer and per piece of the shape at and above it, the cells above times the
distance of their centre of mass beyond the convex hull of the piece's cells in that layer; the largest over the
shape (a build needs its worst joint's clutch, and a post carries the same moment through every layer, so a sum
would grow with the post's length). `fit_scale` now picks, among the factors with the thickest thinnest section, the
smallest moment, then the closest volume (`test_fit_scale_prefers_the_post_under_its_load`). Of the 90 sized targets 8
change: the 5891-1 chair at 1.0 (base, hang and usable: 2859 → 2784 cells) and at usable 0.9 (2603 → 2621), and the
6378-1 chair at usable 1.0 (1341 → 1326). The 5891-1 chair at 0.8 keeps its target (the load's centre lies
over the post's top, dz 0.37 within its half-width 0.5, and no factor in the band does better), so its 6 clutch
failures are not this effect; the 4956-1 chair keeps its targets too.

## Sweep: hanging support, usable sizing, slack

**Decision (cf, 2026-10-10, against the pre-stated rule below; Mac can reverse):** with a 3D target the hole pass with hanging support (`--holes --hang`) and usable sizing are the pipeline defaults, scoped as `--supports` is (`alt.pipeline.resolve`; `--no-holes`, `--no-hang` and `--sizing fillable` give the old setup); no slack default (`--fill-slack` stays a flag, since none makes a build complete). The hang and usable arms below are the new defaults' numbers; nothing was rerun. The drivers of the earlier M12b tables (`experiments/brickgpt.py`, `skins.py`) and this sweep's arms pass the old setup explicitly.

Chair, table and car × 6378-1, 5891-1, 4956-1; 50 candidates, seeds 0–49, 5 workers, the same seeds in every arm; pipeline defaults otherwise (`experiments/complete.py --steps sweep`, at 49d5739 for the cells the two scale fixes changed, 59cbfdc for the rest, whose targets are byte-identical at 49d5739):
- **old base**: the cached pre-fix runs above (fillable 1.0, no flags);
- **base**: the same with the `_fit_key` fix;
- **hang**: base + `--holes --hang` (main e910ad2);
- **usable**, **usable 0.9**, **usable 0.8**: hang + `--sizing usable` at fill slack 1.0, 0.9, 0.8. Usable 1.0 differs from hang only where a part is left out (the 6378-1 chair); elsewhere it is not run and shown as hang's.

Surface here is the share of the target's exposed faces' cells that are filled, ground faces not counted (`features.exposed`, main's definition since e910ad2); the final-state table above used `shapes.surface`.

Selected build: fill % / largest hole (cells) / surface % (valid candidates of 50). **No arm gives a complete build on any pair** (fill ≥ 97, largest hole ≤ 4, surface ≥ 98), nor any complete valid candidate.

| object | set | old base (pre-fix) | base | hang | usable | usable 0.9 | usable 0.8 |
|---|---|---:|---:|---:|---:|---:|---:|
| chair | 6378-1 | 69.3 / 211 / 66.0 (50) | 72.1 / 195 / 71.0 (50) | 75.6 / 192 / 72.0 (50) | 88.6 / 34 / 87.0 (49) | 88.1 / 38 / 85.7 (50) | 90.6 / 35 / 89.1 (50) |
| chair | 5891-1 | 79.0 / 235 / 73.0 (46) | 77.5 / 268 / 70.4 (47) | 84.9 / 172 / 81.5 (50) | 84.9 / 172 / 81.5 (50) = | 87.5 / 76 / 84.5 (47) | 88.0 / 49 / 85.1 (44) |
| chair | 4956-1 | 75.2 / 475 / 71.5 (36) | 72.8 / 495 / 69.1 (42) | 77.7 / 363 / 72.6 (41) | 77.7 / 363 / 72.6 (41) = | 80.8 / 302 / 77.9 (39) | 83.0 / 122 / 78.7 (38) |
| table | 6378-1 | 67.6 / 489 / 68.4 (48) | 67.2 / 427 / 65.1 (49) | 78.5 / 96 / 76.4 (48) | 78.5 / 96 / 76.4 (48) = | 80.5 / 92 / 77.7 (50) | 83.9 / 92 / 79.1 (49) |
| table | 5891-1 | 67.7 / 764 / 62.8 (34) | 66.6 / 736 / 60.6 (38) | 87.1 / 108 / 81.3 (39) | 87.1 / 108 / 81.3 (39) = | 88.5 / 114 / 82.7 (42) | 93.3 / 29 / 91.1 (43) |
| table | 4956-1 | 68.0 / 1149 / 63.1 (42) | 73.1 / 902 / 64.5 (36) | 81.5 / 253 / 78.4 (39) | 81.5 / 253 / 78.4 (39) = | 78.4 / 689 / 76.9 (42) | 84.9 / 351 / 85.4 (41) |
| car | 6378-1 | 75.9 / 263 / 72.8 (50) | 72.7 / 301 / 68.5 (50) | 75.8 / 194 / 74.0 (50) | 75.8 / 194 / 74.0 (50) = | 81.6 / 44 / 75.4 (50) | 84.1 / 49 / 82.0 (50) |
| car | 5891-1 | 80.8 / 305 / 73.0 (50) | 81.5 / 320 / 76.8 (50) | 84.8 / 75 / 81.4 (50) | 84.8 / 75 / 81.4 (50) = | 87.5 / 34 / 84.5 (50) | 87.2 / 22 / 85.4 (50) |
| car | 4956-1 | 75.4 / 944 / 70.6 (49) | 75.3 / 792 / 73.1 (47) | 76.8 / 527 / 73.0 (46) | 76.8 / 527 / 73.0 (46) = | 78.3 / 255 / 72.6 (49) | 81.4 / 260 / 79.5 (50) |

(= : the hang run; usable sizing leaves nothing out there.) Means over the valid candidates, the run times (CPU seconds per candidate) and parts used are in `m12b_complete_sweep.json` (old vs fixed base: `m12b_complete_old_vs_base.json`; the hole diagnosis below: `m12b_complete_holes.json`). Sheets: `m12b_complete_sweep_previews.png` (the selected builds) and `m12b_complete_sweep_missing.png` (their unfilled target cells in red), pairs as rows, arms as columns.

**Hanging support** (hang vs base): selected fill up on 9/9 pairs (+1.5 to +20.5 points, mean +7.1), largest hole down on 9/9, surface up on 8/9; valid counts within ±3 of base on every pair.

**Usable sizing at 1.0** changes one pair's target, the 6378-1 chair (4 × plate 6x14 left out): selected fill 75.6 → 88.6, largest hole 192 → 34, surface 72.0 → 87.0, valid 50 → 49 (one clutch failure). On the other 8 pairs it is hang exactly.

**Slack** (usable 0.8 vs hang): selected fill +2.4 to +15.0 points (mean +6.0), largest hole down on 8/9, surface up on 9/9. Slack buys little: 20% less volume than the parts could fill moves the selected build 2–15 fill points and leaves 17–55 holes per build. One selected build per cell is noisy (4956-1 table, largest hole 253 → 689 → 351 from 1.0 to 0.9 to 0.8); the valid candidates' mean fill rises from hang to 0.9 to 0.8 on 7/9 pairs (not the 5891-1 chair, where hang's 83.6 beats both, nor the 4956-1 chair, flat at 76).

### Adoption (cf's rule)

- *Usable sizing becomes the default if every pair's selected build improves on completeness over hang without losing validity.* Not met as written: it improves the one pair where it changes the target and is identical on the other eight (nothing to improve: no part is left out). It never makes a build worse, and on the 6378-1 chair it is the largest single gain in the sweep. Recommendation: adopt it (identical builds where every part fits, better where one does not); the decision is cf's.
- *The largest slack at which every selected build is complete becomes the default.* None: no slack makes any selected build complete. Best: the 5891-1 table at usable 0.8, 93.3 / 29 / 91.1.

## What still blocks completeness: the usable 0.8 + hang builds

Each pair's selected build at usable 0.8 + hang, replayed with the trace (identity asserted, 9/9) to its final state, after the last hole pass (`--steps holes --arm usable80`). Every unfilled target cell is classified as the hole pass would see it then, under its rules (hanging support included) and with the inventory left:
- **inventory**: a part of the set would fit there under every rule, but it is used up;
- **support**: within reach (a stud below, or a part above to hang from), but no part covering the cell rests or hangs there;
- **unreachable**: no stud below and no part above within reach;
- **balance**, **geometry** as in the trace above; **ground**: a part fits on the ground layer, which the last connect round's hole pass does not visit.

Share of unfilled cells (on the outer surface in brackets); unreachable, balance and missed are 0 on every pair:

| object | set | fill % | unfilled | inventory | support | geometry | ground | parts left at the last hole pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| chair | 6378-1 | 90.6 | 107 | 28 (26) | 72 (72) | 0 (0) | 0 (0) | 52 |
| chair | 5891-1 | 88.0 | 278 | 59 (53) | 33 (32) | 6 (5) | 1 (1) | 155 |
| chair | 4956-1 | 83.0 | 593 | 56 (45) | 41 (40) | 1 (1) | 2 (2) | 237 |
| table | 6378-1 | 83.9 | 217 | 52 (42) | 41 (41) | 0 (0) | 7 (7) | 36 |
| table | 5891-1 | 93.3 | 155 | 66 (48) | 24 (22) | 10 (9) | 0 (0) | 155 |
| table | 4956-1 | 84.9 | 546 | 56 (14) | 44 (40) | 0 (0) | 0 (0) | 186 |
| car | 6378-1 | 84.1 | 219 | 70 (42) | 30 (17) | 0 (0) | 0 (0) | 34 |
| car | 5891-1 | 87.2 | 302 | 75 (40) | 20 (15) | 6 (2) | 0 (0) | 166 |
| car | 4956-1 | 81.4 | 654 | 76 (38) | 23 (10) | 1 (0) | 0 (0) | 217 |

Holes by size: holes; share of the unfilled cells:

| object | set | holes | 1 cells | 2-4 cells | 5-16 cells | 17-64 cells | 65+ cells |
|---|---|---:|---:|---:|---:|---:|---:|
| chair | 6378-1 | 17 | 8; 7% | 6; 14% | 0; 0% | 3; 79% | 0; 0% |
| chair | 5891-1 | 43 | 9; 3% | 19; 19% | 12; 39% | 3; 39% | 0; 0% |
| chair | 4956-1 | 53 | 10; 2% | 24; 12% | 11; 15% | 6; 33% | 2; 38% |
| table | 6378-1 | 36 | 10; 5% | 18; 23% | 6; 21% | 1; 9% | 1; 42% |
| table | 5891-1 | 36 | 18; 12% | 12; 23% | 4; 31% | 2; 34% | 0; 0% |
| table | 4956-1 | 29 | 6; 1% | 9; 5% | 10; 17% | 3; 13% | 1; 64% |
| car | 6378-1 | 32 | 9; 4% | 11; 14% | 9; 38% | 3; 44% | 0; 0% |
| car | 5891-1 | 55 | 13; 4% | 21; 21% | 17; 48% | 4; 26% | 0; 0% |
| car | 4956-1 | 43 | 11; 2% | 17; 7% | 9; 11% | 4; 19% | 2; 62% |

Holes of 1–4 cells, and which parts the inventory cells want:

| object | set | holes of 1–4 cells | wanting a used-up part | that part left at the last hole pass | parts the inventory cells want: cells naming it (the set's count) |
|---|---|---:|---:|---:|---|
| chair | 6378-1 | 14 | 14 | 0 | plate1x1 25 (10); plate1x1_6141 25 (12); plate1x2 13 (5); brick1x1 9 (19) |
| chair | 5891-1 | 28 | 28 | 0 | plate1x1 143 (7); plate1x1_6141 143 (40); plate1x2 113 (14); plate1x3 77 (11) |
| chair | 4956-1 | 34 | 34 | 0 | plate1x1 232 (2); plate1x1_6141 232 (38); plate1x2 229 (18); plate1x4 165 (15) |
| table | 6378-1 | 28 | 28 | 0 | plate1x1 108 (10); plate1x1_6141 108 (12); plate1x2 96 (5); plate1x3 76 (6) |
| table | 5891-1 | 30 | 25 | 0 | plate1x1 92 (7); plate1x1_6141 92 (40); plate1x2 68 (14); plate2x2_corner 59 (1) |
| table | 4956-1 | 15 | 13 | 0 | plate1x2 262 (18); plate1x1 251 (2); plate1x1_6141 251 (38); plate2x2_corner 232 (6) |
| car | 6378-1 | 20 | 20 | 0 | plate1x1 112 (10); plate1x1_6141 112 (12); plate1x2 108 (5); plate1x3 73 (6) |
| car | 5891-1 | 34 | 29 | 0 | plate1x1 186 (7); plate1x1_6141 186 (40); plate1x2 163 (14); plate1x3 115 (11) |
| car | 4956-1 | 28 | 27 | 0 | plate1x2 383 (18); plate1x1 351 (2); plate1x1_6141 351 (38); plate2x2_corner 259 (6) |

**Answer.** The missing 7–19% of each target is mostly **out of small parts**, then **support**; not reach, and only slightly the shape at this scale:
- *Out of small parts* (inventory, 28–76% of the empty cells, at least 52% on 8 of 9 pairs): a part of the set fits there under every rule, and it is always a small plate (1 × 1 plain or round, 1 × 2, 1 × 3, corner 2 × 2), but none is left, and none was left when the last hole pass started, on any pair: the main pass used them all. Every hole of 1–4 cells takes a 1 × 1 plate, and 13–34 of them per build want one. Meanwhile 34–237 parts are left over that fit nowhere free. The sets are short of 1 × 1 plates in particular (4956-1 has 2 plain and 38 round ones). So the sizing should count small parts, or the build should keep them for the holes: slack shrinks the target but the main pass still spends the small plates first.
- *Support* (20–72%; 72% on the 6378-1 chair): within reach, yet no part covering the cell rests or hangs there. On the missing sheet the larger holes are the chairs' caster tips, the table tops' rims and the cars' undersides; the 6378-1 chair's three holes of 17–64 cells hold 79% of its empty cells.
- *Unreachable* is 0 on every pair: hanging reaches every empty cell, so the reach is not the lever. *Geometry* (shape-impossible at this scale) is at most 10% (the 5891-1 table), *ground* at most 7%.

Per pair, the usable 0.8 + hang selected build against the bar (fill ≥ 97, largest hole ≤ 4, surface ≥ 98):

- chair 6378-1: 90.6 / 35 / 89.1; 107 cells empty, 28% out of small parts, 72% support; holes over 16 cells hold 79% of them.
- chair 5891-1: 88.0 / 49 / 85.1; 278 cells empty, 59% out of small parts, 33% support; holes over 16 cells hold 39% of them.
- chair 4956-1: 83.0 / 122 / 78.7; 593 cells empty, 56% out of small parts, 41% support; holes over 16 cells hold 71% of them.
- table 6378-1: 83.9 / 92 / 79.1; 217 cells empty, 52% out of small parts, 41% support; holes over 16 cells hold 52% of them.
- table 5891-1: 93.3 / 29 / 91.1; 155 cells empty, 66% out of small parts, 24% support; holes over 16 cells hold 34% of them.
- table 4956-1: 84.9 / 351 / 85.4; 546 cells empty, 56% out of small parts, 44% support; holes over 16 cells hold 77% of them.
- car 6378-1: 84.1 / 49 / 82.0; 219 cells empty, 70% out of small parts, 30% support; holes over 16 cells hold 44% of them.
- car 5891-1: 87.2 / 22 / 85.4; 302 cells empty, 75% out of small parts, 20% support; holes over 16 cells hold 26% of them.
- car 4956-1: 81.4 / 260 / 79.5; 654 cells empty, 76% out of small parts, 23% support; holes over 16 cells hold 81% of them.

## Small parts kept for the hole pass

The diagnosis above found the hole pass short of small plates, all spent in the main pass. Two builder options (8584bed, off by default; `bottomup.SMALL_CELLS = 3`: 1 × 1 to 1 × 3 plates and tiles, 1 × 1 bricks, the 2 × 2 corner plate):
- **reserve** (`--reserve-small`): at each main-pass cell small parts are tried only after every larger part has failed there, under every rule including the inventory, so a cell only a small part fits (a 1-wide post) still gets one;
- **small-last a** (`--small-last a`): in the main pass a small part's choice weight × (cells / 4)^a; a = 1, 2.

Each at the defaults (usable 1.0 + hang) and at usable 0.8 + hang, 9 pairs, 50 candidates, seeds 0–49, 5 workers, the same seeds as the default arms (at e0f97d8; `--arms reserve small1 small2 reserve80 small1_80 small2_80`). The default arms are the sweep's `usable` (hang's run on the 8 pairs where usable sizing leaves nothing out) and `usable80`. **Rule** (cf, stated before the run): an arm is adopted if every pair's selected build is more complete than the default's without losing validity; here: fill up, largest hole not larger, surface up, valid candidates not fewer. Between passing arms, the smaller judge cost.

**No arm completes any build** (0 complete candidates of 2700), and **no arm passes the rule** at either slack.

### At 1.0

Default: selected fill % / largest hole / surface % (valid of 50). Arms: change vs the default (fill points / hole cells / surface points; valid), ✓ where all four hold.

| object | set | default | reserve | small-last 1 | small-last 2 |
|---|---|---|---|---|---|
| chair | 6378-1 | 88.6 / 34 / 87.0 (49) | +4.4 / -14 / +5.1; 50 (+1) ✓ | +4.3 / -16 / +5.1; 50 (+1) ✓ | +0.3 / +19 / +0.4; 50 (+1) |
| chair | 5891-1 | 84.9 / 172 / 81.5 (50) | +6.9 / -135 / +8.3; 50 (+0) ✓ | +2.0 / -85 / +3.3; 50 (+0) ✓ | +3.9 / -95 / +4.8; 50 (+0) ✓ |
| chair | 4956-1 | 77.7 / 363 / 72.6 (41) | -1.4 / +76 / +0.8; 48 (+7) | +1.6 / -35 / +3.5; 46 (+5) ✓ | +1.7 / -182 / +1.6; 46 (+5) ✓ |
| table | 6378-1 | 78.5 / 96 / 76.4 (48) | -3.2 / +162 / -1.8; 48 (+0) | -5.3 / +120 / -4.4; 50 (+2) | +1.0 / +4 / +2.0; 50 (+2) |
| table | 5891-1 | 87.1 / 108 / 81.3 (39) | +3.9 / -72 / +7.4; 41 (+2) ✓ | +3.0 / -42 / +4.6; 42 (+3) ✓ | +0.8 / +1 / +2.0; 43 (+4) |
| table | 4956-1 | 81.5 / 253 / 78.4 (39) | -0.6 / +543 / +0.2; 39 (+0) | -0.3 / +331 / -4.1; 32 (-7) | -0.8 / +108 / +2.8; 37 (-2) |
| car | 6378-1 | 75.8 / 194 / 74.0 (50) | +2.6 / -46 / +1.8; 50 (+0) ✓ | +1.6 / +37 / -1.8; 50 (+0) | +0.1 / -33 / -1.9; 50 (+0) |
| car | 5891-1 | 84.8 / 75 / 81.4 (50) | +3.3 / -29 / +4.5; 50 (+0) ✓ | +1.5 / +10 / -0.7; 50 (+0) | +1.9 / +7 / +4.8; 50 (+0) |
| car | 4956-1 | 76.8 / 527 / 73.0 (46) | +3.3 / -236 / +2.4; 47 (+1) ✓ | +2.3 / -174 / +0.5; 46 (+0) ✓ | +2.3 / -329 / +6.2; 47 (+1) ✓ |

| of 9 pairs | reserve | small-last 1 | small-last 2 |
|---|---:|---:|---:|
| pairs passing (rule: 9) | 6 | 5 | 3 |
| selected fill up | 6 | 7 | 8 |
| largest hole larger | 3 | 4 | 5 |
| valid lost | 0 | 1 | 1 |
| mean change, selected fill | +2.1 | +1.2 | +1.2 |
| mean change, selected judge | -0.0102 | -0.0032 | +0.0009 |
| valid candidates: mean fill up | 8 | 7 | 9 |
| valid candidates: fewer holes | 9 | 8 | 9 |
| valid candidates: mean largest hole larger | 5 | 5 | 7 |
| s / candidate vs the default | × 0.69 | × 0.81 | × 0.77 |

### At 0.8

Default: selected fill % / largest hole / surface % (valid of 50). Arms: change vs the default (fill points / hole cells / surface points; valid), ✓ where all four hold.

| object | set | default | reserve | small-last 1 | small-last 2 |
|---|---|---|---|---|---|
| chair | 6378-1 | 90.6 / 35 / 89.1 (50) | +1.8 / +0 / +2.1; 49 (-1) | +0.5 / +0 / +0.6; 50 (+0) ✓ | +0.5 / +0 / +0.5; 49 (-1) |
| chair | 5891-1 | 88.0 / 49 / 85.1 (44) | +6.0 / +1 / +7.1; 46 (+2) | -4.8 / +62 / -4.8; 44 (+0) | +0.8 / -5 / +3.2; 45 (+1) ✓ |
| chair | 4956-1 | 83.0 / 122 / 78.7 (38) | +3.0 / +19 / +4.2; 36 (-2) | -0.6 / +115 / -0.9; 42 (+4) | -1.3 / +79 / -1.4; 45 (+7) |
| table | 6378-1 | 83.9 / 92 / 79.1 (49) | +1.6 / -16 / +3.5; 50 (+1) ✓ | +2.2 / +0 / +4.0; 50 (+1) ✓ | +5.7 / -16 / +6.5; 50 (+1) ✓ |
| table | 5891-1 | 93.3 / 29 / 91.1 (43) | +2.6 / -13 / +2.9; 45 (+2) ✓ | -0.3 / +0 / -1.0; 44 (+1) | -1.5 / -2 / -2.2; 46 (+3) |
| table | 4956-1 | 84.9 / 351 / 85.4 (41) | -0.7 / +172 / -5.6; 41 (+0) | +4.6 / -240 / +2.6; 41 (+0) ✓ | +1.8 / -242 / +0.9; 39 (-2) |
| car | 6378-1 | 84.1 / 49 / 82.0 (50) | +1.6 / +0 / +0.7; 50 (+0) ✓ | -1.3 / +33 / -1.3; 50 (+0) | +0.9 / +3 / +1.1; 50 (+0) |
| car | 5891-1 | 87.2 / 22 / 85.4 (50) | +2.7 / +6 / +0.8; 50 (+0) | +3.6 / +23 / +4.6; 50 (+0) | +0.0 / +31 / +0.0; 50 (+0) |
| car | 4956-1 | 81.4 / 260 / 79.5 (50) | +4.3 / +4 / +1.4; 49 (-1) | +1.9 / -64 / -0.3; 48 (-2) | +1.5 / -62 / -2.2; 50 (+0) |

| of 9 pairs | reserve | small-last 1 | small-last 2 |
|---|---:|---:|---:|
| pairs passing (rule: 9) | 3 | 3 | 2 |
| selected fill up | 8 | 5 | 6 |
| largest hole larger | 5 | 4 | 3 |
| valid lost | 3 | 1 | 2 |
| mean change, selected fill | +2.5 | +0.7 | +0.9 |
| mean change, selected judge | -0.0067 | +0.0004 | -0.0001 |
| valid candidates: mean fill up | 9 | 8 | 9 |
| valid candidates: fewer holes | 9 | 7 | 9 |
| valid candidates: mean largest hole larger | 7 | 4 | 6 |
| s / candidate vs the default | × 0.70 | × 0.80 | × 0.82 |

Judge: higher is better; its changes are within ±0.026 and mixed in sign. Means, holes and the selected builds' parts are in `m12b_complete_sweep_small.json` (`sweep_small.md` in the run directory); sheets `m12b_complete_sweep_small_previews.png`, `m12b_complete_sweep_small_missing.png` (pairs as rows; arms as columns: default, reserve, small-last 1, 2 at 1.0, then the same at 0.8).

**Reading.** Reserve is the strongest arm at both slacks: the selected build's fill is up on 6/9 pairs at 1.0 and 8/9 at 0.8, and over all valid candidates mean fill is up on 8/9 and 9/9 with fewer holes on 9/9; it is also the fastest arm (0.7× the default's time per candidate). It fails the rule on the largest hole (the selected build's grows on 3/9 pairs at 1.0, by up to 543 cells on the 4956-1 table, and on 5/9 at 0.8) and, at 0.8, on validity (−1 to −2 valid on 3 pairs). The pattern is the same for every arm: many small holes close, the large ones stay or merge. Small-last 1 and 2 do less of both.

### What still blocks completeness: reserve at 0.8

No arm passes, so (cf) only the best arm at 0.8, reserve, is diagnosed: its 9 selected builds replayed with the trace to their final state (identity asserted 9/9; `--steps holes --arm reserve80`), next to the usable 0.8 diagnosis above. Cause shares of the unfilled cells:

| object | set | fill % (usable 0.8 → reserve) | unfilled | inventory % | support % | geometry % | ground % | holes of 1–4 cells | small parts left at the last hole pass |
|---|---|---|---|---|---|---|---|---|---|
| chair | 6378-1 | 90.6 → 92.4 | 107 → 87 | 28 → 34 | 72 → 66 | 0 → 0 | 0 → 0 | 14 → 13 | 0 → 0 |
| chair | 5891-1 | 88.0 → 94.0 | 278 → 139 | 59 → 50 | 33 → 38 | 6 → 10 | 1 → 1 | 28 → 14 | 0 → 0 |
| chair | 4956-1 | 83.0 → 85.9 | 593 → 490 | 56 → 64 | 41 → 34 | 1 → 1 | 2 → 0 | 34 → 13 | 0 → 0 |
| table | 6378-1 | 83.9 → 85.5 | 217 → 195 | 52 → 50 | 41 → 44 | 0 → 0 | 7 → 6 | 28 → 11 | 0 → 0 |
| table | 5891-1 | 93.3 → 96.0 | 155 → 94 | 66 → 61 | 24 → 15 | 10 → 9 | 0 → 16 | 30 → 26 | 0 → 0 |
| table | 4956-1 | 84.9 → 84.3 | 546 → 570 | 56 → 89 | 44 → 10 | 0 → 1 | 0 → 0 | 15 → 9 | 0 → 9 |
| car | 6378-1 | 84.1 → 85.7 | 219 → 197 | 70 → 80 | 30 → 20 | 0 → 0 | 0 → 0 | 20 → 15 | 0 → 0 |
| car | 5891-1 | 87.2 → 89.9 | 302 → 238 | 75 → 56 | 20 → 39 | 6 → 5 | 0 → 0 | 34 → 22 | 0 → 0 |
| car | 4956-1 | 81.4 → 85.7 | 654 → 503 | 76 → 79 | 23 → 20 | 1 → 1 | 0 → 0 | 28 → 8 | 0 → 0 |

(Small parts left: holes of 1–4 cells whose wanted part was still in the inventory when the last hole pass started.)

**Answer.** Reserving does not keep the small plates for the hole pass: **0 are left at the last hole pass on 8 of 9 pairs**, as without it (the 4956-1 table: 9, used up during that pass; its 523-cell hole under the top wants larger plates, 1 × 2 to 2 × 4, all used up). Holes of 1–4 cells drop from 231 to 131 over the 9 builds, and inventory stays the main cause (34–89% of the empty cells). Under reserve the main pass places a small part only where no larger part fits at that moment, and those cells (rims, stepped curves, thin posts) still take them all. The supply is the limit: the three sets hold 6378-1: 77 small parts, 171 cells; 5891-1: 136 small parts, 266 cells; 4956-1: 182 small parts, 324 cells (tiles only on top, 1 × 1 bricks 3 layers), all of it spent where nothing larger fit, and the empty cells a used-up part would still fill number 30–509 per selected build on top of that (the 4956-1 car's 396 alone exceed its set's 324 small-part cells). Support stays 10–66%: the large holes on the sheet are the same caster tips, table rims and car undersides.

**Verdict.** Against the rule: no arm passes at either slack (best: reserve, 6/9 at 1.0, 3/9 at 0.8); nothing is adopted and the options stay off. Against the bar: no build, selected or candidate, is complete (best selected: the 5891-1 table under reserve at 0.8, 96.0 / 16 / 94.0; connected growth's 5891-1 chair at 0.8, 96.4 / 14 / 95.5, stays the closest). A small-part reserve cannot close the inventory gap on these sets, because the cells only small parts can fill outnumber what the sets' small parts cover. Ways around it are a sizing that counts the cells only small parts can fill against the small parts the set holds, or a smaller target; not more reordering.

## Small-part budget: does not hold

Hypothesis (cf, from the verdict above): the target has cells only small parts can fill, and where they outnumber the set's small parts the build cannot be complete; a sizing that shrinks the target until they fit the supply would then close the gap. Measured before building it (`--steps small-only`, no generation):
- **small-only cells**: target cells that no placement of any inventory part larger than 3 cells (`bottomup.SMALL_CELLS`) covers inside the target: every orientation, the shape check only, as `inventory.unusable`, but per cell (the union of all placements that fit, complemented; `complete.covered_by`, tested against brute force);
- **supply**: the set's small parts in cells (6378-1: 77 parts, 171 cells, 5891-1: 136 parts, 266 cells, 4956-1: 182 parts, 324 cells);
- the 9 pairs at usable sizing, fill slack 1.0 down to 0.6 in steps of 0.05 (81 targets; the 0.8 targets are the sweep's, cell for cell in size).

Target cells / small-only cells:

| object | set | 1.00 | 0.95 | 0.90 | 0.85 | 0.80 | 0.75 | 0.70 | 0.65 | 0.60 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| chair | 6378-1 | 1326 / 8 | 1296 / 8 | 1204 / 0 | 1145 / 0 | 1138 / 0 | 1030 / 25 | 979 / 14 | 889 / 18 | 799 / 11 |
| chair | 5891-1 | 2784 / 0 | 2741 / 0 | 2621 / 0 | 2343 / 0 | 2323 / 0 | 2179 / 0 | 1974 / 0 | 1845 / 0 | 1737 / 0 |
| chair | 4956-1 | 4334 / 0 | 4047 / 0 | 3892 / 0 | 3480 / 0 | 3480 / 0 | 3104 / 0 | 3022 / 0 | 2784 / 0 | 2617 / 0 |
| table | 6378-1 | 1748 / 0 | 1591 / 0 | 1576 / 0 | 1432 / 0 | 1344 / 0 | 1299 / 0 | 1122 / 3 | 1122 / 3 | 770 / 0 |
| table | 5891-1 | 2880 / 0 | 2820 / 0 | 2570 / 0 | 2551 / 0 | 2328 / 0 | 2096 / 0 | 1980 / 0 | 1870 / 0 | 1770 / 0 |
| table | 4956-1 | 4414 / 0 | 4104 / 0 | 4008 / 0 | 3745 / 0 | 3627 / 0 | 3418 / 0 | 2947 / 0 | 2858 / 0 | 2570 / 0 |
| car | 6378-1 | 1721 / 0 | 1658 / 0 | 1494 / 0 | 1428 / 0 | 1380 / 0 | 1265 / 0 | 1166 / 0 | 1136 / 0 | 947 / 0 |
| car | 5891-1 | 2807 / 0 | 2807 / 0 | 2627 / 0 | 2371 / 0 | 2357 / 0 | 2308 / 0 | 2005 / 0 | 1907 / 0 | 1761 / 0 |
| car | 4956-1 | 4554 / 0 | 4183 / 0 | 4032 / 0 | 3660 / 0 | 3512 / 0 | 3368 / 0 | 3134 / 0 | 2807 / 0 | 2628 / 0 |

Small-only cells are 0 at every scale on 7 of 9 pairs; the 6378-1 chair has up to 25 and the 6378-1 table 3 at two scales. The largest ratio to the supply is 0.15: small-only ≤ supply holds at slack 1.0 on every pair, so the proposed sizing would not shrink any target.

**Against the diagnosed builds** (the usable 0.8 and reserve 0.8 selected builds above, replayed, identity asserted): empty cells that want a used-up small part (some small part would fit there under every rule), and the cells of the small parts the build placed; in brackets, how many lie on small-only cells:

| object | set | want a small part: usable 0.8 → reserve 0.8 | small parts placed, cells: usable 0.8 → reserve 0.8 | supply, cells |
|---|---|---|---|---:|
| chair | 6378-1 | 29 (0) → 30 (0) | 167 (0) → 171 (0) | 171 |
| chair | 5891-1 | 164 (0) → 70 (0) | 252 (0) → 221 (0) | 266 |
| chair | 4956-1 | 294 (0) → 284 (0) | 282 (0) → 279 (0) | 324 |
| table | 6378-1 | 113 (0) → 97 (0) | 165 (0) → 171 (0) | 171 |
| table | 5891-1 | 102 (0) → 57 (0) | 248 (0) → 240 (0) | 266 |
| table | 4956-1 | 297 (0) → 440 (0) | 324 (0) → 300 (0) | 324 |
| car | 6378-1 | 150 (0) → 148 (0) | 171 (0) → 171 (0) | 171 |
| car | 5891-1 | 223 (0) → 131 (0) | 260 (0) → 232 (0) | 266 |
| car | 4956-1 | 476 (0) → 342 (0) | 295 (0) → 294 (0) | 324 |

**Reading.** The shortfall does not track the small-only count: 29–476 empty cells per build want a small part where the target requires none, and the builds place 165–324 cells of small parts, most or all of each set's supply, none of them on a small-only cell. The demand for small parts is made by the packing, not by the shape: larger parts placed at any offset leave remnants between themselves and the target's boundary, half of them 1-wide strips (next section), that only a used-up small part would fill. Counting the small parts already placed, the builds call for 196–771 cells of small parts per build against a supply of 171–324. No sizing by the target's geometry, and no order of trying parts (the reserve only decides which remnants get the supply), can close that; a lever has to act on where the remnants form.

### Remnants: what a remnant-aware placement could win

The bound for the next lever, a placement score that avoids leaving remnants the inventory cannot fill (`--steps remnants`, no generation; the 18 diagnosed builds, each replayed twice, identity asserted). A **remnant** is an empty cell that wants a used-up small part (as above). Each is charged to the placement that left it: the last-placed of the final parts next to it, or, inside a larger hole, next to the hole ("alone": a hole no part touches, not charged). The second replay stops at each charged placement and asks, in order:
- **fillable after**: right after the placement, some part the inventory still held covers the remnant under every rule (hanging allowed, as in the later hole passes): it was not made unfillable here but used up later;
- **alternative covers it**: another placement at the same visited cell (any part held then, any offset, every rule as the builder checks it, balance included) covers the remnant;
- **alternative leaves it fillable**: another such placement leaves it coverable by a part held then (that fit checked without balance, so optimistic);
- **no alternative**: neither.

The bound of a remnant-aware score is the two alternative rows: a score at the placement could have avoided at most those (an upper bound: each remnant is judged alone, and the alternative's own later effects are ignored).

| arm | object | set | remnants | by pass: main / connect / holes | fillable after | alternative covers | alternative leaves fillable | no alternative | bound | width 1 / 2 / 3+ |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---|
| usable 0.8 | chair | 6378-1 | 29 (2 alone) | 7 / 4 / 16 | 4 | 4 | 0 | 19 | 4 (14%) | 26 / 3 / 0 |
| usable 0.8 | chair | 5891-1 | 164 | 83 / 21 / 60 | 34 | 8 | 25 | 97 | 33 (20%) | 111 / 43 / 10 |
| usable 0.8 | chair | 4956-1 | 294 | 137 / 34 / 123 | 72 | 50 | 25 | 147 | 75 (26%) | 188 / 47 / 59 |
| usable 0.8 | table | 6378-1 | 113 | 53 / 7 / 53 | 25 | 21 | 15 | 52 | 36 (32%) | 101 / 7 / 5 |
| usable 0.8 | table | 5891-1 | 102 | 0 / 34 / 68 | 28 | 7 | 11 | 56 | 18 (18%) | 51 / 39 / 12 |
| usable 0.8 | table | 4956-1 | 297 | 62 / 34 / 201 | 79 | 20 | 34 | 164 | 54 (18%) | 89 / 54 / 154 |
| usable 0.8 | car | 6378-1 | 150 | 109 / 0 / 41 | 32 | 19 | 18 | 81 | 37 (25%) | 129 / 13 / 8 |
| usable 0.8 | car | 5891-1 | 223 | 140 / 0 / 83 | 66 | 19 | 34 | 104 | 53 (24%) | 133 / 76 / 14 |
| usable 0.8 | car | 4956-1 | 476 | 421 / 2 / 53 | 147 | 56 | 24 | 249 | 80 (17%) | 257 / 93 / 126 |
| reserve 0.8 | chair | 6378-1 | 30 (2 alone) | 4 / 1 / 23 | 4 | 2 | 1 | 21 | 3 (10%) | 30 / 0 / 0 |
| reserve 0.8 | chair | 5891-1 | 70 | 20 / 0 / 50 | 35 | 3 | 4 | 28 | 7 (10%) | 49 / 15 / 6 |
| reserve 0.8 | chair | 4956-1 | 284 | 89 / 39 / 156 | 108 | 33 | 21 | 122 | 54 (19%) | 163 / 67 / 54 |
| reserve 0.8 | table | 6378-1 | 97 | 32 / 23 / 42 | 48 | 6 | 6 | 37 | 12 (12%) | 60 / 18 / 19 |
| reserve 0.8 | table | 5891-1 | 57 | 5 / 7 / 45 | 30 | 6 | 0 | 21 | 6 (11%) | 52 / 5 / 0 |
| reserve 0.8 | table | 4956-1 | 440 | 184 / 0 / 256 | 170 | 20 | 15 | 235 | 35 (8%) | 67 / 62 / 311 |
| reserve 0.8 | car | 6378-1 | 148 | 129 / 0 / 19 | 59 | 15 | 11 | 63 | 26 (18%) | 117 / 21 / 10 |
| reserve 0.8 | car | 5891-1 | 131 | 60 / 0 / 71 | 44 | 12 | 5 | 70 | 17 (13%) | 85 / 27 / 19 |
| reserve 0.8 | car | 4956-1 | 342 | 302 / 0 / 40 | 162 | 23 | 18 | 139 | 41 (12%) | 111 / 79 / 152 |

Over the 18 builds: 3447 remnants; fillable after 1147 (33%), alternative covers 324 (9%), alternative leaves fillable 267 (8%), no alternative 1705 (49%). Charged to the main pass 1837, connect rounds 206, hole passes 1400.

**Width** (the narrower free run through the remnant along z and x in its layer, in the final build): 1-wide 1819 (53%), 2-wide 669, 3 or more 959 (cells inside larger holes). Lever (c) as a count: remnants in a hole that no part of the set fits at all (shape only, the full inventory): **0** on every build. Every set has 1 × 1 and 1 × 2 parts, so no remnant has a width the set lacks; what it lacks is enough of them.

**Answer.** The bound is under half the shortfall on every build: 8–32% of the remnants (17% over all 18). A remnant-aware placement score cannot close the gap, so it is not proposed. Half the remnants had no alternative at the placement that left them (the visited cell took only that placement, or every other also left them unfillable), and a third were still fillable afterwards and lost to later demand: the small parts went to remnants elsewhere first. Coarser offsets (lever (c)) have nothing to align to: no remnant is narrower than every part of its set. What the counts point to instead is the supply itself: the remnants a build leaves outnumber the small parts every set holds, whatever order or placement made them.
