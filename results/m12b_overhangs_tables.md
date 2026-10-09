# M12b step 1d — overhangs

*History: these tables are from the 63-part catalog, before support columns (up to 6 cells) and the 1111 clutch
cap became defaults; their support columns are on the 4-stud lattice (replaced at a0ec36c). The 88-part rerun with
the defaults is in [`m12b_brickgpt.md`](m12b_brickgpt.md) (lattice at fd9015b); the redrawn table figure and the
current support rule in [`m12b_sizing.md`](m12b_sizing.md).*

Targets are StableText2Brick structures (their data, not their model), each set's whole inventory, D2 + learned
style, 50 candidates per run. Three ways to handle overhangs on the six objects × 3 sets (6378-1, 5891-1, 10182-1):

- **exact**: the structure's exact cells as the target, with no overhang handling.
- **opentops**: as exact, plus one rule in the builder. A part's studless top cells (tiles, and the top of a brick
  whose stud side is covered) may sit only where the target is empty directly above. Before this rule, the builder
  could cap a thin stem (a table leg, a chair back post) with a tile, and nothing could be built on top of it.
  The rule only removes placements, so every guarantee (inventory, support, balance, shape, one piece) is unchanged.
  **Open tops is the pipeline default** (`AltConfig.open_tops = True`; it applies only when there is a target
  shape, and `--no-open-tops` turns it off).
- **supports** (`--supports`): open tops, plus support columns added to the target. Columns go under every
  overhang cell that is more than 3 studs from a held cell, on a 4-stud lattice, down to the next object cell
  or the ground. Support cells are reported as a share of the object's cells. Fill and IoU are measured on the
  object's cells only. "Built outside object" counts the cells a build places in the columns.

**Figure:** `results/m12b_opentops_before_after.png` showed the table on the six demo sets, exact | open tops, on
the 63-part catalog; it is now redrawn on the 88-part catalog at a0ec36c, exact | the pipeline defaults (see
`m12b_sizing.md`).
The figure runs below are the 63-part ones. A caption's fill is the pictured (selected) build's fill; the tables
give the mean over all valid candidates.

Every run, the 54 head-to-head runs and the 12 figure runs, is 100% valid, 100% physics (stands on a table)
and 100% one piece.

## Conclusions

1. **Open tops always wins, at no cost.** Object fill rises on all 18 object × set pairs. The gains:
   - table: 15/24/44 → 54/64/78;
   - chair: 11/2/37 → 16/9/74;
   - car, sofa, vessel, bench: +1 to +8 points.

   Open tops is also faster per candidate, by 1.3–7.6× (median 2.9×; table on 10182-1: 188 → 65 s), because fewer builds dead-end
   on a capped stem. On the demo sets the table's fill goes 15 → 54 (6378-1), 37 → 61 (7743-1), 24 → 64
   (5891-1), 30 → 62 (4956-1) and 44 → 78 (10182-1). On 374-1 it barely moves (49 → 50).
2. **Supports only pay off where the object hangs over nothing.**
   - Chair: fill goes from 16/9/74 with open tops to 53/28/72 with supports (no gain on 10182-1). The seat is held up by columns
     that cost 19–24% of the object's cells. The columns also keep the chair within real clutch (≤ 1111): 84/88/100% of builds
     with supports, against 80/88/2% with open tops alone. Full chairs without columns are long cantilevers (see
     `m12b_brickgpt.md`).
   - Bench, 5891-1: 75 → 81.
   - Table: the table top needs columns worth 86–103% of the object, and they use up the inventory. Fill drops
     to 20/23/68, against 54/64/78 with open tops alone.
   - Car (1–3% support cells): no change.
   - Sofa and vessel: no overhang, so no columns.
3. **A calibrated clutch cap binds on the big set and only removes builds** (table (i) below, exact runs).
   - Real clutch is about 1111 plate-cell weights per stud (StableLego: 0.98 N per knob; a plate cell weighs
     0.882 mN). A part held by one stud needs at most 144 (a 1x8 brick).
   - **6378-1 and 5891-1:** at ≤ 1111, 84–100% of builds stand (chair 6378-1 84%, table 5891-1 92%, the rest
     ≥ 94%).
   - **10182-1 (1514 parts):** 56–94% stand at ≤ 1111. The cap also lowers mean fill: table 43.5 → 31.8,
     chair 37.2 → 15.0, because the builds that fill the overhangs are the ones removed. Tighter caps remove
     most builds (≤ 100: 0–40% of the 10182-1 builds stand).

   Finite clutch, meaning the build stands on a table if studs hold, is therefore the right criterion for small
   and medium sets. On the largest set it overstates stability for 6–44% of builds. A clutch cap is a filter,
   not a way to fill overhangs: open tops and support columns are the levers that change what gets built.

# Tables

## Calibration

Real clutch: 0.98 N per knob / 0.882 mN per plate cell = **1111** plate-cell weights per stud.

| part held by one stud | 1x2 (1 out) | 1x3 (2 out) | 1x4 (3 out) | 1x6 (5 out) | 1x8 (7 out) |
|---|---|---|---|---|---|
| plate | 0.0 | 3.0 | 8.0 | 24.0 | 48.0 |
| brick | 0.0 | 9.0 | 24.0 | 72.0 | 144.0 |

## (i) Clutch limits on the exact runs

| object | set | any clutch: stand % / fill % | ≤ 1111: stand % / fill % | ≤ 100: stand % / fill % | ≤ 30: stand % / fill % | ≤ 10: stand % / fill % |
|---|---|---|---|---|---|---|
| table | 6378-1 | 100 / 15.4 | 100 / 15.4 | 98 / 14.7 | 94 / 14.3 | 94 / 14.3 |
| table | 5891-1 | 100 / 24.2 | 92 / 21.4 | 80 / 18.1 | 74 / 16.9 | 70 / 16.9 |
| table | 10182-1 | 100 / 43.5 | 70 / 31.8 | 40 / 21.9 | 28 / 21.5 | 10 / 21.1 |
| chair | 6378-1 | 100 / 11.0 | 84 / 3.1 | 84 / 3.1 | 48 / 2.5 | 28 / 2.2 |
| chair | 5891-1 | 100 / 2.0 | 100 / 2.0 | 100 / 2.0 | 80 / 1.8 | 64 / 1.8 |
| chair | 10182-1 | 100 / 37.2 | 56 / 15.0 | 26 / 11.0 | 0 / — | 0 / — |
| car | 6378-1 | 100 / 65.4 | 100 / 65.4 | 54 / 65.4 | 20 / 66.7 | 4 / 64.2 |
| car | 5891-1 | 100 / 67.5 | 100 / 67.5 | 34 / 67.5 | 0 / — | 0 / — |
| car | 10182-1 | 100 / 78.7 | 92 / 78.8 | 2 / 81.4 | 0 / — | 0 / — |
| sofa | 6378-1 | 100 / 77.4 | 100 / 77.4 | 82 / 77.4 | 46 / 77.4 | 26 / 77.2 |
| sofa | 5891-1 | 100 / 80.8 | 100 / 80.8 | 54 / 80.7 | 28 / 81.4 | 6 / 80.7 |
| sofa | 10182-1 | 100 / 82.5 | 88 / 82.6 | 2 / 84.7 | 0 / — | 0 / — |
| vessel | 6378-1 | 100 / 73.3 | 100 / 73.3 | 100 / 73.3 | 80 / 73.4 | 66 / 73.5 |
| vessel | 5891-1 | 100 / 78.7 | 100 / 78.7 | 96 / 78.8 | 54 / 79.1 | 10 / 78.2 |
| vessel | 10182-1 | 100 / 80.0 | 94 / 79.9 | 16 / 80.6 | 0 / — | 0 / — |
| bench | 6378-1 | 100 / 65.4 | 94 / 65.6 | 42 / 66.6 | 2 / 61.4 | 0 / — |
| bench | 5891-1 | 100 / 69.1 | 98 / 69.1 | 16 / 66.7 | 0 / — | 0 / — |
| bench | 10182-1 | 100 / 75.6 | 90 / 76.4 | 0 / — | 0 / — | 0 / — |

## (ii) Support columns and (iii) open tops vs exact

| object | set | target | object cells | support cells (% of object) | valid % | physics % | one piece % | object fill % | object IoU | overhang loss % | built outside object (cells) | best: parts | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| table | 6378-1 | exact | 1706 | 0 (0%) | 100 | 100 | 100 | 15.4 | 0.15 | 82.2 | 0 | 92 | 76.29 |
| table | 6378-1 | opentops | 1706 | 0 (0%) | 100 | 100 | 100 | 54.4 | 0.54 | 41.6 | 0 | 185 | 10.07 |
| table | 6378-1 | supports | 1706 | 1502 (88%) | 100 | 100 | 100 | 20.2 | 0.19 | 77.8 | 153 | 164 | 33.86 |
| table | 5891-1 | exact | 2501 | 0 (0%) | 100 | 100 | 100 | 24.2 | 0.24 | 73.9 | 0 | 231 | 110.32 |
| table | 5891-1 | opentops | 2501 | 0 (0%) | 100 | 100 | 100 | 64.0 | 0.64 | 33.7 | 0 | 262 | 17.41 |
| table | 5891-1 | supports | 2501 | 2158 (86%) | 100 | 100 | 100 | 22.5 | 0.21 | 76.1 | 237 | 258 | 38.33 |
| table | 10182-1 | exact | 9462 | 0 (0%) | 100 | 100 | 100 | 43.5 | 0.44 | 53.0 | 0 | 1338 | 187.53 |
| table | 10182-1 | opentops | 9462 | 0 (0%) | 100 | 100 | 100 | 77.9 | 0.78 | 19.9 | 0 | 1225 | 65.18 |
| table | 10182-1 | supports | 9462 | 9706 (103%) | 100 | 100 | 100 | 68.4 | 0.60 | 27.2 | 1319 | 1224 | 203.22 |
| chair | 6378-1 | exact | 1641 | 0 (0%) | 100 | 100 | 100 | 11.0 | 0.11 | 87.4 | 0 | 132 | 23.73 |
| chair | 6378-1 | opentops | 1641 | 0 (0%) | 100 | 100 | 100 | 15.5 | 0.16 | 83.0 | 0 | 141 | 17.27 |
| chair | 6378-1 | supports | 1641 | 341 (21%) | 100 | 100 | 100 | 53.3 | 0.49 | 42.3 | 145 | 176 | 19.53 |
| chair | 5891-1 | exact | 2488 | 0 (0%) | 100 | 100 | 100 | 2.0 | 0.02 | 97.4 | 0 | 35 | 37.99 |
| chair | 5891-1 | opentops | 2488 | 0 (0%) | 100 | 100 | 100 | 9.1 | 0.09 | 89.9 | 0 | 239 | 29.54 |
| chair | 5891-1 | supports | 2488 | 476 (19%) | 100 | 100 | 100 | 28.3 | 0.27 | 68.8 | 98 | 262 | 32.89 |
| chair | 10182-1 | exact | 9265 | 0 (0%) | 100 | 100 | 100 | 37.2 | 0.37 | 58.9 | 0 | 1191 | 307.10 |
| chair | 10182-1 | opentops | 9265 | 0 (0%) | 100 | 100 | 100 | 73.5 | 0.73 | 22.3 | 0 | 1158 | 204.46 |
| chair | 10182-1 | supports | 9265 | 2195 (24%) | 100 | 100 | 100 | 72.3 | 0.65 | 23.5 | 1017 | 1141 | 57.16 |
| car | 6378-1 | exact | 1689 | 0 (0%) | 100 | 100 | 100 | 65.4 | 0.65 | 28.0 | 0 | 180 | 7.60 |
| car | 6378-1 | opentops | 1689 | 0 (0%) | 100 | 100 | 100 | 68.8 | 0.69 | 26.1 | 0 | 190 | 2.62 |
| car | 6378-1 | supports | 1689 | 12 (1%) | 100 | 100 | 100 | 69.2 | 0.69 | 25.3 | 11 | 186 | 2.27 |
| car | 5891-1 | exact | 2555 | 0 (0%) | 100 | 100 | 100 | 67.5 | 0.68 | 26.4 | 0 | 294 | 9.96 |
| car | 5891-1 | opentops | 2555 | 0 (0%) | 100 | 100 | 100 | 71.4 | 0.71 | 25.1 | 0 | 283 | 3.71 |
| car | 5891-1 | supports | 2555 | 16 (1%) | 100 | 100 | 100 | 72.6 | 0.72 | 23.4 | 16 | 298 | 3.49 |
| car | 10182-1 | exact | 9368 | 0 (0%) | 100 | 100 | 100 | 78.7 | 0.79 | 13.3 | 0 | 1341 | 71.23 |
| car | 10182-1 | opentops | 9368 | 0 (0%) | 100 | 100 | 100 | 85.2 | 0.85 | 10.4 | 0 | 1181 | 17.75 |
| car | 10182-1 | supports | 9368 | 264 (3%) | 100 | 100 | 100 | 84.0 | 0.82 | 10.6 | 254 | 1212 | 21.09 |
| sofa | 6378-1 | exact | 1589 | 0 (0%) | 100 | 100 | 100 | 77.4 | 0.77 | 12.4 | 0 | 196 | 5.22 |
| sofa | 6378-1 | opentops | 1589 | 0 (0%) | 100 | 100 | 100 | 78.1 | 0.78 | 13.4 | 0 | 195 | 2.55 |
| sofa | 6378-1 | supports | 1589 | 0 (0%) | 100 | 100 | 100 | 78.1 | 0.78 | 13.4 | 0 | 195 | 2.56 |
| sofa | 5891-1 | exact | 2509 | 0 (0%) | 100 | 100 | 100 | 80.8 | 0.81 | 11.0 | 0 | 303 | 8.23 |
| sofa | 5891-1 | opentops | 2509 | 0 (0%) | 100 | 100 | 100 | 84.6 | 0.85 | 10.2 | 0 | 289 | 4.28 |
| sofa | 5891-1 | supports | 2509 | 0 (0%) | 100 | 100 | 100 | 84.6 | 0.85 | 10.2 | 0 | 289 | 4.27 |
| sofa | 10182-1 | exact | 9113 | 0 (0%) | 100 | 100 | 100 | 82.5 | 0.82 | 8.9 | 0 | 1418 | 63.61 |
| sofa | 10182-1 | opentops | 9113 | 0 (0%) | 100 | 100 | 100 | 85.2 | 0.85 | 9.3 | 0 | 1157 | 20.93 |
| sofa | 10182-1 | supports | 9113 | 0 (0%) | 100 | 100 | 100 | 85.2 | 0.85 | 9.3 | 0 | 1157 | 21.10 |
| vessel | 6378-1 | exact | 1681 | 0 (0%) | 100 | 100 | 100 | 73.3 | 0.73 | 16.2 | 0 | 193 | 5.09 |
| vessel | 6378-1 | opentops | 1681 | 0 (0%) | 100 | 100 | 100 | 75.6 | 0.76 | 16.0 | 0 | 193 | 2.22 |
| vessel | 6378-1 | supports | 1681 | 0 (0%) | 100 | 100 | 100 | 75.6 | 0.76 | 16.0 | 0 | 193 | 2.26 |
| vessel | 5891-1 | exact | 2478 | 0 (0%) | 100 | 100 | 100 | 78.7 | 0.79 | 12.7 | 0 | 296 | 7.68 |
| vessel | 5891-1 | opentops | 2478 | 0 (0%) | 100 | 100 | 100 | 80.9 | 0.81 | 13.0 | 0 | 290 | 3.19 |
| vessel | 5891-1 | supports | 2478 | 0 (0%) | 100 | 100 | 100 | 80.9 | 0.81 | 13.0 | 0 | 290 | 3.15 |
| vessel | 10182-1 | exact | 9462 | 0 (0%) | 100 | 100 | 100 | 80.0 | 0.80 | 10.8 | 0 | 1395 | 70.03 |
| vessel | 10182-1 | opentops | 9462 | 0 (0%) | 100 | 100 | 100 | 85.1 | 0.85 | 9.0 | 0 | 1170 | 18.87 |
| vessel | 10182-1 | supports | 9462 | 0 (0%) | 100 | 100 | 100 | 85.1 | 0.85 | 9.0 | 0 | 1170 | 18.92 |
| bench | 6378-1 | exact | 1673 | 0 (0%) | 100 | 100 | 100 | 65.4 | 0.65 | 29.4 | 0 | 189 | 9.32 |
| bench | 6378-1 | opentops | 1673 | 0 (0%) | 100 | 100 | 100 | 70.7 | 0.71 | 25.4 | 0 | 184 | 2.21 |
| bench | 6378-1 | supports | 1673 | 132 (8%) | 100 | 100 | 100 | 66.8 | 0.63 | 26.4 | 114 | 191 | 3.11 |
| bench | 5891-1 | exact | 2517 | 0 (0%) | 100 | 100 | 100 | 69.1 | 0.69 | 25.7 | 0 | 295 | 14.37 |
| bench | 5891-1 | opentops | 2517 | 0 (0%) | 100 | 100 | 100 | 74.6 | 0.75 | 22.3 | 0 | 287 | 4.51 |
| bench | 5891-1 | supports | 2517 | 288 (11%) | 100 | 100 | 100 | 80.5 | 0.73 | 14.8 | 241 | 297 | 5.44 |
| bench | 10182-1 | exact | 9300 | 0 (0%) | 100 | 100 | 100 | 75.6 | 0.76 | 17.5 | 0 | 1256 | 114.74 |
| bench | 10182-1 | opentops | 9300 | 0 (0%) | 100 | 100 | 100 | 83.2 | 0.83 | 13.5 | 0 | 1191 | 29.64 |
| bench | 10182-1 | supports | 9300 | 1368 (15%) | 100 | 100 | 100 | 69.5 | 0.61 | 25.1 | 1330 | 1148 | 29.01 |

## Figure runs (table)

| object | set | target | object cells | support cells (% of object) | valid % | physics % | one piece % | object fill % | object IoU | overhang loss % | built outside object (cells) | best: parts | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| table | 374-1 | exact | 1900 | 0 (0%) | 100 | 100 | 100 | 48.9 | 0.49 | 46.8 | 0 | 169 | 5.71 |
| table | 374-1 | opentops | 1900 | 0 (0%) | 100 | 100 | 100 | 49.8 | 0.50 | 45.9 | 0 | 154 | 6.12 |
| table | 6378-1 | exact | 1706 | 0 (0%) | 100 | 100 | 100 | 15.4 | 0.15 | 82.2 | 0 | 92 | 76.29 |
| table | 6378-1 | opentops | 1706 | 0 (0%) | 100 | 100 | 100 | 54.4 | 0.54 | 41.6 | 0 | 185 | 10.07 |
| table | 7743-1 | exact | 1934 | 0 (0%) | 100 | 100 | 100 | 37.3 | 0.37 | 58.4 | 0 | 122 | 10.88 |
| table | 7743-1 | opentops | 1934 | 0 (0%) | 100 | 100 | 100 | 60.6 | 0.61 | 36.8 | 0 | 219 | 8.29 |
| table | 5891-1 | exact | 2501 | 0 (0%) | 100 | 100 | 100 | 24.2 | 0.24 | 73.9 | 0 | 231 | 110.32 |
| table | 5891-1 | opentops | 2501 | 0 (0%) | 100 | 100 | 100 | 64.0 | 0.64 | 33.7 | 0 | 262 | 17.41 |
| table | 4956-1 | exact | 3745 | 0 (0%) | 100 | 100 | 100 | 29.8 | 0.30 | 67.0 | 0 | 355 | 16.94 |
| table | 4956-1 | opentops | 3745 | 0 (0%) | 100 | 100 | 100 | 61.7 | 0.62 | 35.2 | 0 | 335 | 12.07 |
| table | 10182-1 | exact | 9462 | 0 (0%) | 100 | 100 | 100 | 43.5 | 0.44 | 53.0 | 0 | 1338 | 187.53 |
| table | 10182-1 | opentops | 9462 | 0 (0%) | 100 | 100 | 100 | 77.9 | 0.78 | 19.9 | 0 | 1225 | 65.18 |
