# M12b step 3: clean skins and mirror symmetry, measured

Measured before building anything (`python -m brickwfc.experiments.skins --steps measure`). Builds: the step-1a rerun (`out/m12b_brickgpt_v2`, pipeline defaults, 88-part catalog, 50 candidates per run); *mean* is over the valid candidates, *selected* is the build the funnel picked.

**Skin** (`bricks/skin.py`): every cell face open to the outside (not the ground's bottom). Share of skin faces on small parts (footprint of 1-2 cells), long ones (1 x n, n >= 3) and wide ones (>= 2 x 2); faces per visible part (higher: cleaner); distinct parts in each 4 x 4-cell window that is all skin, on top faces of one layer and on side faces of one column of cells (a side window is 4 studs x 4 plates; lower: cleaner, 1 = one part), with the number of such windows.

**Symmetry** (`bricks/symmetry.py`): across the target's best vertical mirror plane, the share of parts whose mirror image (same part, reflected) is also placed, any color / same color; the share of parts that are *mirrorable* (their mirror image lies inside the target), and the mirrored share among those; and the share of filled cells whose reflection is filled.

## Skins

### Real sets (reference: 28 building sets, voxelized, catalog parts only)

| set | parts | small % | long % | wide % | faces / visible part | top: parts per 4x4 (windows) | sides: parts per 4x4 (windows) |
|---|---|---|---|---|---|---|---|
| 349-1 | 59 | 20 | 34 | 47 | 24.9 | 3.20 (15) | 2.67 (36) |
| 374-1 | 218 | 34 | 38 | 28 | 20.4 | 1.65 (97) | 3.13 (323) |
| 377-1 | 119 | 21 | 63 | 15 | 15.7 | 6.00 (1) | 3.34 (140) |
| 361-2 | 52 | 27 | 50 | 24 | 27.5 | 1.46 (91) | 2.70 (182) |
| 6363-1 | 73 | 31 | 48 | 21 | 21.2 | 1.56 (63) | 3.43 (136) |
| 6382-1 | 181 | 34 | 30 | 35 | 22.9 | 1.23 (52) | 3.32 (338) |
| 6362-1 | 77 | 24 | 26 | 50 | 20.7 | 2.31 (16) | 3.43 (63) |
| 6372-1 | 161 | 20 | 37 | 43 | 19.4 | 2.27 (26) | 2.84 (189) |
| 6370-1 | 128 | 20 | 31 | 49 | 21.9 | 1.00 (1) | 2.80 (206) |
| 6378-1 | 165 | 20 | 41 | 39 | 20.9 | 1.49 (180) | 2.25 (230) |
| 6380-1 | 131 | 44 | 33 | 24 | 21.8 | 1.05 (59) | 2.94 (236) |
| 10182-1 | 1289 | 32 | 44 | 24 | 13.5 | 4.09 (616) | 3.33 (5268) |
| 10190-1 | 850 | 26 | 48 | 25 | 16.0 | 4.01 (188) | 3.80 (4566) |
| 4954-1 | 823 | 17 | 42 | 41 | 18.8 | 3.63 (67) | 3.13 (3826) |
| 4956-1 | 543 | 11 | 43 | 47 | 18.4 | 13.50 (8) | 2.95 (2015) |
| 10185-1 | 1698 | 26 | 51 | 23 | 13.2 | 5.58 (361) | 3.39 (5764) |
| 7743-1 | 153 | 24 | 50 | 25 | 19.0 | 1.00 (3) | 2.86 (385) |
| 7796-1 | 56 | 43 | 11 | 46 | 11.5 | — (0) | 5.29 (28) |
| 10197-1 | 1241 | 28 | 48 | 24 | 13.8 | 4.93 (151) | 3.34 (3638) |
| 5891-1 | 414 | 17 | 41 | 42 | 17.5 | 2.45 (20) | 3.30 (1458) |
| 10218-1 | 1082 | 27 | 55 | 18 | 15.2 | 5.13 (141) | 3.20 (4060) |
| 5766-1 | 245 | 18 | 32 | 49 | 17.6 | 3.17 (12) | 4.21 (275) |
| 5771-1 | 436 | 14 | 44 | 42 | 19.7 | 2.33 (6) | 2.80 (1024) |
| 10224-1 | 1699 | 21 | 59 | 19 | 16.8 | 2.17 (192) | 3.35 (7451) |
| 31009-1 | 206 | 15 | 34 | 51 | 15.7 | 3.50 (8) | 4.19 (278) |
| 10243-1 | 1209 | 36 | 44 | 20 | 11.9 | 7.47 (175) | 3.45 (1990) |
| 31048-1 | 201 | 34 | 27 | 39 | 13.8 | 3.42 (12) | 3.74 (87) |
| 10264-1 | 892 | 17 | 61 | 22 | 15.7 | 6.03 (242) | 3.27 (3513) |
| **mean of 28** | 514 | 25 | 42 | 33 | 18.1 | 3.54 (100) | 3.30 (1704) |

### BrickGPT's structures (bricks only)

| object | bricks | small % | long % | wide % | faces / visible part | top: parts per 4x4 (windows) | sides: parts per 4x4 (windows) |
|---|---|---|---|---|---|---|---|
| chair | 119 | 24 | 14 | 63 | 19.0 | 3.48 (25) | 3.12 (522) |
| table | 104 | 12 | 9 | 78 | 17.1 | 4.17 (139) | 3.04 (156) |
| car | 94 | 17 | 29 | 54 | 14.4 | 3.27 (15) | 3.43 (159) |

### Our builds (step-1a rerun)

| object | set | valid | which | small % | long % | wide % | faces / visible part | top: parts per 4x4 (windows) | sides: parts per 4x4 (windows) |
|---|---|---|---|---|---|---|---|---|---|
| chair | 6378-1 | 43 | mean | 25 | 46 | 28 | 10.5 | 5.66 (12) | 3.65 (177) |
| chair | 6378-1 | 43 | selected | 27 | 43 | 30 | 9.6 | 5.27 (15) | 4.35 (236) |
| chair | 5891-1 | 36 | mean | 29 | 50 | 22 | 10.1 | 7.07 (29) | 3.30 (290) |
| chair | 5891-1 | 36 | selected | 30 | 46 | 24 | 9.7 | 8.80 (5) | 3.59 (234) |
| chair | 10182-1 | 48 | mean | 35 | 39 | 26 | 7.4 | 8.43 (124) | 4.37 (1233) |
| chair | 10182-1 | 48 | selected | 33 | 42 | 25 | 7.6 | 8.44 (114) | 4.41 (1195) |
| table | 6378-1 | 50 | mean | 21 | 35 | 45 | 9.8 | 4.52 (35) | 4.37 (43) |
| table | 6378-1 | 50 | selected | 22 | 36 | 42 | 8.9 | 4.20 (10) | 4.97 (66) |
| table | 5891-1 | 33 | mean | 26 | 47 | 27 | 9.5 | 4.72 (31) | 5.29 (227) |
| table | 5891-1 | 33 | selected | 22 | 45 | 33 | 10.6 | 4.45 (31) | 5.08 (303) |
| table | 10182-1 | 47 | mean | 37 | 40 | 24 | 5.9 | 7.41 (239) | 5.65 (767) |
| table | 10182-1 | 47 | selected | 37 | 42 | 21 | 6.1 | 7.69 (172) | 5.37 (850) |
| car | 6378-1 | 50 | mean | 23 | 45 | 32 | 10.0 | 3.60 (6) | 3.44 (63) |
| car | 6378-1 | 50 | selected | 21 | 43 | 36 | 10.2 | 4.50 (4) | 4.15 (20) |
| car | 5891-1 | 50 | mean | 24 | 50 | 26 | 11.1 | 3.95 (14) | 3.99 (182) |
| car | 5891-1 | 50 | selected | 23 | 53 | 24 | 11.0 | 6.00 (2) | 4.24 (176) |
| car | 10182-1 | 47 | mean | 36 | 38 | 26 | 8.1 | 6.61 (93) | 4.59 (763) |
| car | 10182-1 | 47 | selected | 33 | 40 | 27 | 7.9 | 7.01 (146) | 4.71 (714) |

## Mirror symmetry

### Targets

| object | their structure: plane (score) | scaled object, per set: plane (score) |
|---|---|---|
| chair | x = 6 (0.72) | 6378-1: x = 6 (0.71), 5891-1: x = 8 (0.77), 10182-1: x = 11 (0.75) |
| table | z = 10.5 (0.98) | 6378-1: x = 8.5 (0.98), 5891-1: z = 11.5 (0.98), 10182-1: x = 15 (0.92) |
| car | x = 3.5 (0.97) | 6378-1: x = 4 (0.85), 5891-1: x = 5.5 (0.92), 10182-1: x = 7.5 (0.97) |

| object | source | which | mirrored parts % | same color % | mirrorable % | mirrored of mirrorable % | cells mirrored % |
|---|---|---|---|---|---|---|---|
| chair | BrickGPT | their structure | 2 | 2 | 32 | 5 | 72 |
| chair | 6378-1 | mean | 8 | 8 | 52 | 16 | 63 |
| chair | 6378-1 | selected | 8 | 8 | 50 | 17 | 69 |
| chair | 5891-1 | mean | 7 | 7 | 68 | 11 | 68 |
| chair | 5891-1 | selected | 9 | 8 | 60 | 15 | 67 |
| chair | 10182-1 | mean | 5 | 4 | 61 | 8 | 68 |
| chair | 10182-1 | selected | 5 | 4 | 64 | 7 | 68 |
| table | BrickGPT | their structure | 43 | 43 | 88 | 49 | 98 |
| table | 6378-1 | mean | 22 | 18 | 96 | 22 | 77 |
| table | 6378-1 | selected | 15 | 10 | 97 | 15 | 83 |
| table | 5891-1 | mean | 19 | 16 | 98 | 20 | 79 |
| table | 5891-1 | selected | 19 | 18 | 97 | 20 | 81 |
| table | 10182-1 | mean | 9 | 8 | 84 | 11 | 82 |
| table | 10182-1 | selected | 10 | 9 | 81 | 12 | 84 |
| car | BrickGPT | their structure | 52 | 52 | 90 | 58 | 97 |
| car | 6378-1 | mean | 7 | 6 | 71 | 10 | 71 |
| car | 6378-1 | selected | 7 | 7 | 69 | 10 | 74 |
| car | 5891-1 | mean | 7 | 6 | 83 | 9 | 77 |
| car | 5891-1 | selected | 7 | 6 | 82 | 9 | 78 |
| car | 10182-1 | mean | 6 | 4 | 88 | 6 | 84 |
| car | 10182-1 | selected | 6 | 5 | 88 | 7 | 83 |

Real sets with a mirror plane (cells score >= 0.9): 3 of 28.

| set | plane (score) | mirrored parts % | same color % | mirrorable % | mirrored of mirrorable % | cells mirrored % |
|---|---|---|---|---|---|---|
| 349-1 | z = 6.5 (0.96) | 76 | 76 | 95 | 80 | 96 |
| 6382-1 | x = 15.5 (0.94) | 85 | 85 | 92 | 92 | 94 |
| 7743-1 | x = 2.5 (1.00) | 99 | 99 | 99 | 100 | 100 |

## Findings (hand-written from the tables above)

**Skins: a gap in how the skin is laid out, not in which part sizes show.**
- The share of skin on small / long / wide parts follows the inventory: ours 21-37% small, the real sets
  11-44% (mean 25%); per set, 6378-1 real 20% vs ours 21-27%, 10182-1 real 32% vs ours 33-37%. No clear gap.
- Fragmentation is the gap. Parts per 4 x 4 top window, real set vs our builds of its inventory (mean over
  valid candidates): 6378-1 1.5 vs 3.6-5.7; 5891-1 2.5 vs 4.0-7.1; 10182-1 4.1 vs 6.6-8.4. Side windows: 2.3
  vs 3.4-4.4; 3.3 vs 3.3-5.3; 3.3 vs 4.4-5.7. BrickGPT's structures (bricks only): top 3.3-4.2, sides 3.0-3.4.
  Our worst: the table and everything on 10182-1 (sides 5.3-5.7).
- Faces per visible part: real 18 (12-28), BrickGPT 14-19, ours 6-11. Part of this is form (real models are
  thin walls that show a whole part; our targets are solid, so many parts show only an end), so the window
  measures are the fairer comparison.

**Mirror symmetry: a large gap where the target is symmetric.**
- Targets: the table and the car have a plane (their structures 0.97-0.98). The chair does not (0.72: the
  seat and back are symmetric, the five-arm base is not); 50-68% of our chair's parts are mirrorable.
- Scaling breaks some symmetry: nearest-neighbour resampling from BrickGPT's 20-grid takes the car from 0.97
  to 0.85 on 6378-1 (0.92 on 5891-1). A symmetric decoder needs a symmetric target first.
- Mirrored share of mirrorable parts: BrickGPT's table 49%, car 58%; the three real sets with a mirror plane
  80-100%; ours 7-22% (table 11-22%, car 6-10%, chair 7-17%). Cells alone are 63-84% symmetric in our builds,
  so the target's symmetry survives in the occupancy but not in the parts.

**Next (step 3 build):** both gaps are real, so both changes are built: (a) skin preference in the builder, (b)
symmetric decoding (with a mirror-preserving target scale), before/after on chair and car x 3 sets.
