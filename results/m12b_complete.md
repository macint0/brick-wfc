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
