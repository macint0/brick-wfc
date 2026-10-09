# M12b completeness: how much of the target the builds fill, and where they don't

Mac (2026-10-10): the builds are recognizable but incomplete; a smaller complete object beats a larger partial one.
This write-up measures completeness on the runs that already exist (no generation) and, in a second part, why
target cells stay empty as the builder saw them.

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
