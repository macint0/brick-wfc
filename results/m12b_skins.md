# M12b step 3: skin preference and symmetric decoding, before / after

*Note (2026-10-10): the builds here predate the `_fit_key` fix (60b3a3b, `builder_version` 2: a tile that failed at a cell no longer makes the builder skip the plate of its box). On 9 set x object pairs the fix moves mean fill by -0.9 to +2.5 points (mean +0.5; within 1.2 SE on 8 pairs, +2.6 SE on the 4956-1 car; old vs fixed base in [`m12b_complete.md`](m12b_complete.md)); a rerun would give different individual builds. Since 49d5739 the thin-aware scale also keeps a thin post under its load, which gives the 5891-1 chair a different target under fillable sizing (2859 -> 2784 cells).*

`python -m brickwfc.experiments.skins --steps compare` (measures: `results/m12b_skins_measure.md`). Chair, car and table on 6378-1, 5891-1 and 10182-1, 50 candidates per run, pipeline defaults plus the arm's flags: **base** (the step-1a rerun), **skin** (`--skin`: largest parts first on the target's surface), **symmetric** (`--symmetric`: the target's mirror plane; a car or table, at least 0.8 symmetric after scaling, is made exactly symmetric by adding the mirror image of its cells, the chair, 0.71-0.77, is not; each part's mirror image is placed with it where it fits and the inventory has it), **both**.

Judge: size-matched across the four arms of a cell (every valid candidate subsampled to the smallest one's contact events; higher is better). Fill: of the arm's own object (no support columns). Base-object fill: of the base arm's object, on the same grid (the symmetric arms make a car or table exactly symmetric by adding the mirror image of its cells, so their own object is 2-15% larger). Fragmentation: distinct parts per all-skin 4 x 4-cell window (lower is cleaner). Mirrored: share of mirrorable parts whose mirror image is placed (any color; then same color).

## Change against base (means over valid candidates, averaged over the 9 cells)

| arm | judge | fill (points) | base-object fill (points) | top parts per 4x4 | side parts per 4x4 | faces / visible part | mirrored of mirrorable (points) | judge up in | fill up in |
|---|---|---|---|---|---|---|---|---|---|
| (base: judge sd across candidates, mean over cells) | 0.0121 | | | | | | | | |
| skin | -0.0167 | +2.4 | +2.4 | -0.69 | -0.78 | +1.3 | -0 | 0/9 | 7/9 |
| symmetric | -0.0073 | -2.0 | -1.6 | -0.18 | +0.11 | +0.0 | +35 | 2/9 | 3/9 |
| both | -0.0207 | +0.3 | +0.6 | -1.13 | -0.82 | +1.3 | +31 | 0/9 | 3/9 |

## Means over valid candidates

| object | set | arm | valid | judge (sd) | fill % | base-object fill % | top: parts per 4x4 | sides: parts per 4x4 | faces / visible part | mirrored of mirrorable % | same color % | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chair | 6378-1 | base | 43/50 | -0.4108 (0.0194) | 63.8 | 63.8 | 5.66 | 3.65 | 10.5 | 16 | 15 | 11.2 |
| chair | 6378-1 | skin | 45/50 | -0.4288 (0.0181) | 61.4 | 61.4 | 4.35 | 3.90 | 11.4 | 12 | 11 | 12.0 |
| chair | 6378-1 | symmetric | 47/50 | -0.4098 (0.0162) | 65.2 | 65.2 | 5.80 | 3.77 | 10.4 | 28 | 26 | 11.1 |
| chair | 6378-1 | both | 41/50 | -0.4250 (0.0261) | 61.6 | 61.6 | 4.52 | 3.75 | 11.2 | 24 | 20 | 12.2 |
| chair | 5891-1 | base | 36/50 | -0.3626 (0.0109) | 58.0 | 58.0 | 7.07 | 3.30 | 10.1 | 11 | 10 | 96.3 |
| chair | 5891-1 | skin | 18/50 | -0.3659 (0.0100) | 58.6 | 58.6 | 5.16 | 3.30 | 11.4 | 7 | 6 | 89.4 |
| chair | 5891-1 | symmetric | 30/50 | -0.3613 (0.0112) | 58.4 | 58.4 | 6.66 | 3.30 | 10.1 | 26 | 24 | 100.9 |
| chair | 5891-1 | both | 25/50 | -0.3663 (0.0124) | 55.5 | 55.5 | 4.77 | 3.29 | 11.0 | 23 | 20 | 97.4 |
| chair | 10182-1 | base | 48/50 | -0.2922 (0.0069) | 80.8 | 80.8 | 8.43 | 4.37 | 7.4 | 8 | 7 | 102.5 |
| chair | 10182-1 | skin | 50/50 | -0.3116 (0.0069) | 82.9 | 82.9 | 6.95 | 4.23 | 9.2 | 6 | 5 | 82.8 |
| chair | 10182-1 | symmetric | 49/50 | -0.2975 (0.0082) | 79.9 | 79.9 | 8.38 | 4.34 | 7.3 | 29 | 27 | 104.9 |
| chair | 10182-1 | both | 49/50 | -0.3188 (0.0060) | 82.4 | 82.4 | 7.34 | 4.21 | 9.2 | 31 | 29 | 83.7 |
| car | 6378-1 | base | 50/50 | -0.3263 (0.0132) | 69.8 | 69.8 | 3.60 | 3.44 | 10.0 | 10 | 9 | 4.2 |
| car | 6378-1 | skin | 50/50 | -0.3452 (0.0138) | 73.9 | 73.9 | 3.84 | 3.57 | 10.0 | 15 | 13 | 2.1 |
| car | 6378-1 | symmetric | 50/50 | -0.3451 (0.0154) | 65.2 | 65.9 | 2.86 | 3.43 | 9.7 | 56 | 49 | 3.9 |
| car | 6378-1 | both | 50/50 | -0.3579 (0.0133) | 66.4 | 66.9 | 2.73 | 3.40 | 10.1 | 51 | 46 | 2.0 |
| car | 5891-1 | base | 50/50 | -0.3494 (0.0087) | 61.1 | 61.1 | 3.95 | 3.99 | 11.1 | 9 | 7 | 56.7 |
| car | 5891-1 | skin | 50/50 | -0.3617 (0.0079) | 61.4 | 61.4 | 4.92 | 3.12 | 11.1 | 10 | 8 | 14.7 |
| car | 5891-1 | symmetric | 48/50 | -0.3636 (0.0088) | 53.8 | 54.7 | 4.17 | 4.40 | 10.8 | 63 | 56 | 43.4 |
| car | 5891-1 | both | 48/50 | -0.3659 (0.0099) | 54.7 | 55.5 | 4.33 | 3.20 | 11.3 | 57 | 52 | 9.7 |
| car | 10182-1 | base | 47/50 | -0.2979 (0.0057) | 82.7 | 82.7 | 6.61 | 4.59 | 8.1 | 6 | 5 | 53.3 |
| car | 10182-1 | skin | 49/50 | -0.3074 (0.0059) | 86.3 | 86.3 | 4.56 | 3.77 | 9.1 | 6 | 5 | 61.1 |
| car | 10182-1 | symmetric | 48/50 | -0.3077 (0.0061) | 79.7 | 79.7 | 5.75 | 4.93 | 8.4 | 64 | 60 | 39.9 |
| car | 10182-1 | both | 48/50 | -0.3171 (0.0072) | 81.3 | 81.2 | 3.66 | 3.56 | 10.1 | 58 | 54 | 56.3 |
| table | 6378-1 | base | 50/50 | -0.4118 (0.0209) | 54.3 | 54.3 | 4.52 | 4.37 | 9.8 | 22 | 19 | 12.0 |
| table | 6378-1 | skin | 50/50 | -0.4208 (0.0223) | 59.0 | 59.0 | 4.10 | 2.69 | 12.6 | 31 | 25 | 10.6 |
| table | 6378-1 | symmetric | 49/50 | -0.4170 (0.0251) | 54.6 | 55.3 | 4.30 | 4.49 | 10.0 | 60 | 52 | 14.7 |
| table | 6378-1 | both | 50/50 | -0.4257 (0.0289) | 62.3 | 63.0 | 4.02 | 2.77 | 12.0 | 57 | 52 | 9.5 |
| table | 5891-1 | base | 33/50 | -0.3733 (0.0159) | 58.8 | 58.8 | 4.72 | 5.29 | 9.5 | 20 | 17 | 87.0 |
| table | 5891-1 | skin | 44/50 | -0.4076 (0.0091) | 69.0 | 69.0 | 5.35 | 3.18 | 11.2 | 18 | 15 | 51.1 |
| table | 5891-1 | symmetric | 27/50 | -0.3820 (0.0173) | 56.7 | 57.4 | 5.08 | 5.27 | 9.6 | 55 | 50 | 86.6 |
| table | 5891-1 | both | 47/50 | -0.4063 (0.0121) | 67.9 | 68.7 | 5.57 | 3.20 | 11.3 | 47 | 43 | 48.3 |
| table | 10182-1 | base | 47/50 | -0.2921 (0.0077) | 78.9 | 78.9 | 7.41 | 5.65 | 5.9 | 11 | 10 | 127.9 |
| table | 10182-1 | skin | 49/50 | -0.3177 (0.0099) | 77.1 | 77.1 | 6.50 | 3.89 | 8.1 | 8 | 7 | 82.2 |
| table | 10182-1 | symmetric | 50/50 | -0.2986 (0.0083) | 77.0 | 77.1 | 7.31 | 5.74 | 6.4 | 48 | 45 | 92.9 |
| table | 10182-1 | both | 50/50 | -0.3199 (0.0072) | 78.7 | 78.5 | 4.83 | 3.90 | 8.3 | 44 | 41 | 34.6 |

## Selected build (k = 1)

| object | set | arm | valid | judge (sd) | fill % | base-object fill % | top: parts per 4x4 | sides: parts per 4x4 | faces / visible part | mirrored of mirrorable % | same color % | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chair | 6378-1 | base | 43/50 | -0.3775 | 71.0 | 71.0 | 5.27 | 4.35 | 9.6 | 17 | 17 | 11.2 |
| chair | 6378-1 | skin | 45/50 | -0.4248 | 72.7 | 72.7 | 5.65 | 3.59 | 11.2 | 10 | 10 | 12.0 |
| chair | 6378-1 | symmetric | 47/50 | -0.3837 | 71.4 | 71.4 | 6.25 | 4.06 | 9.7 | 22 | 22 | 11.1 |
| chair | 6378-1 | both | 41/50 | -0.4190 | 74.5 | 74.5 | 6.65 | 4.65 | 10.0 | 19 | 17 | 12.2 |
| chair | 5891-1 | base | 36/50 | -0.3332 | 58.7 | 58.7 | 8.80 | 3.59 | 9.7 | 15 | 13 | 96.3 |
| chair | 5891-1 | skin | 18/50 | -0.3397 | 61.1 | 61.1 | 7.16 | 3.32 | 10.8 | 6 | 5 | 89.4 |
| chair | 5891-1 | symmetric | 30/50 | -0.3455 | 59.9 | 59.9 | 5.46 | 3.15 | 9.8 | 25 | 25 | 100.9 |
| chair | 5891-1 | both | 25/50 | -0.3392 | 59.0 | 59.0 | 6.06 | 3.49 | 10.7 | 23 | 20 | 97.4 |
| chair | 10182-1 | base | 48/50 | -0.2761 | 81.3 | 81.3 | 8.44 | 4.41 | 7.6 | 7 | 7 | 102.5 |
| chair | 10182-1 | skin | 50/50 | -0.2982 | 82.9 | 82.9 | 6.91 | 4.34 | 9.3 | 8 | 6 | 82.8 |
| chair | 10182-1 | symmetric | 49/50 | -0.3042 | 84.1 | 84.1 | 8.18 | 4.43 | 7.2 | 22 | 21 | 104.9 |
| chair | 10182-1 | both | 49/50 | -0.3054 | 82.9 | 82.9 | 7.25 | 3.85 | 9.8 | 41 | 38 | 83.7 |
| car | 6378-1 | base | 50/50 | -0.3052 | 72.9 | 72.9 | 4.50 | 4.15 | 10.2 | 10 | 10 | 4.2 |
| car | 6378-1 | skin | 50/50 | -0.3189 | 76.7 | 76.7 | 5.50 | 3.93 | 9.4 | 14 | 11 | 2.1 |
| car | 6378-1 | symmetric | 50/50 | -0.3292 | 67.9 | 69.6 | 6.00 | 2.74 | 9.8 | 55 | 48 | 3.9 |
| car | 6378-1 | both | 50/50 | -0.3393 | 69.7 | 69.6 | 2.83 | 3.00 | 10.2 | 44 | 35 | 2.0 |
| car | 5891-1 | base | 50/50 | -0.3292 | 61.4 | 61.4 | 6.00 | 4.24 | 11.0 | 9 | 7 | 56.7 |
| car | 5891-1 | skin | 50/50 | -0.3599 | 65.5 | 65.5 | 3.71 | 2.52 | 11.8 | 11 | 11 | 14.7 |
| car | 5891-1 | symmetric | 48/50 | -0.3423 | 55.6 | 56.6 | 6.56 | 4.01 | 10.3 | 65 | 59 | 43.4 |
| car | 5891-1 | both | 48/50 | -0.3523 | 56.9 | 57.7 | 6.78 | 3.24 | 10.7 | 62 | 56 | 9.7 |
| car | 10182-1 | base | 47/50 | -0.2869 | 83.9 | 83.9 | 7.01 | 4.71 | 7.9 | 7 | 6 | 53.3 |
| car | 10182-1 | skin | 49/50 | -0.2892 | 87.8 | 87.8 | 5.24 | 3.77 | 8.9 | 8 | 6 | 61.1 |
| car | 10182-1 | symmetric | 48/50 | -0.2913 | 80.7 | 80.6 | 6.11 | 5.03 | 8.0 | 69 | 65 | 39.9 |
| car | 10182-1 | both | 48/50 | -0.3048 | 82.4 | 82.5 | 3.82 | 3.29 | 11.0 | 45 | 42 | 56.3 |
| table | 6378-1 | base | 50/50 | -0.3888 | 65.8 | 65.8 | 4.20 | 4.97 | 8.9 | 15 | 11 | 12.0 |
| table | 6378-1 | skin | 50/50 | -0.4217 | 71.6 | 71.6 | 3.00 | 2.38 | 10.7 | 24 | 18 | 10.6 |
| table | 6378-1 | symmetric | 49/50 | -0.3620 | 58.8 | 59.6 | 5.52 | 6.30 | 8.8 | 54 | 48 | 14.7 |
| table | 6378-1 | both | 50/50 | -0.4357 | 80.6 | 81.2 | 2.44 | 2.93 | 12.1 | 68 | 61 | 9.5 |
| table | 5891-1 | base | 33/50 | -0.3577 | 69.5 | 69.5 | 4.45 | 5.08 | 10.6 | 20 | 18 | 87.0 |
| table | 5891-1 | skin | 44/50 | -0.3901 | 73.6 | 73.6 | 5.03 | 3.16 | 11.1 | 16 | 14 | 51.1 |
| table | 5891-1 | symmetric | 27/50 | -0.3650 | 67.4 | 67.9 | 5.80 | 5.46 | 8.7 | 65 | 60 | 86.6 |
| table | 5891-1 | both | 47/50 | -0.3946 | 73.8 | 74.4 | 5.51 | 3.10 | 11.7 | 46 | 43 | 48.3 |
| table | 10182-1 | base | 47/50 | -0.2797 | 83.1 | 83.1 | 7.69 | 5.37 | 6.1 | 12 | 11 | 127.9 |
| table | 10182-1 | skin | 49/50 | -0.3191 | 88.2 | 88.2 | 5.88 | 4.05 | 7.9 | 7 | 6 | 82.2 |
| table | 10182-1 | symmetric | 50/50 | -0.2879 | 80.5 | 80.6 | 6.77 | 5.38 | 6.7 | 48 | 46 | 92.9 |
| table | 10182-1 | both | 50/50 | -0.3094 | 82.1 | 82.0 | 4.48 | 3.85 | 8.5 | 31 | 29 | 34.6 |

## Targets

| object | set | arm | object cells | plane (score) | judge size (events) |
|---|---|---|---|---|---|
| chair | 6378-1 | base | 1725 | x = 6 (0.71) | 188 |
| chair | 6378-1 | skin | 1725 | x = 6 (0.71) | 188 |
| chair | 6378-1 | symmetric | 1725 | x = 6 (0.71) | 188 |
| chair | 6378-1 | both | 1725 | x = 6 (0.71) | 188 |
| chair | 5891-1 | base | 4688 | x = 8 (0.77) | 1908 |
| chair | 5891-1 | skin | 4688 | x = 8 (0.77) | 1908 |
| chair | 5891-1 | symmetric | 4688 | x = 8 (0.77) | 1908 |
| chair | 5891-1 | both | 4688 | x = 8 (0.77) | 1908 |
| chair | 10182-1 | base | 10656 | x = 11 (0.75) | 10705 |
| chair | 10182-1 | skin | 10656 | x = 11 (0.75) | 10705 |
| chair | 10182-1 | symmetric | 10656 | x = 11 (0.75) | 10705 |
| chair | 10182-1 | both | 10656 | x = 11 (0.75) | 10705 |
| car | 6378-1 | base | 1689 | x = 4 (0.85) | 1194 |
| car | 6378-1 | skin | 1689 | x = 4 (0.85) | 1194 |
| car | 6378-1 | symmetric | 1946 | x = 4 (1.00) | 1194 |
| car | 6378-1 | both | 1946 | x = 4 (1.00) | 1194 |
| car | 5891-1 | base | 4613 | x = 5.5 (0.92) | 2603 |
| car | 5891-1 | skin | 4613 | x = 5.5 (0.92) | 2603 |
| car | 5891-1 | symmetric | 4970 | x = 5.5 (1.00) | 2603 |
| car | 5891-1 | both | 4970 | x = 5.5 (1.00) | 2603 |
| car | 10182-1 | base | 10704 | x = 7.5 (0.97) | 11420 |
| car | 10182-1 | skin | 10704 | x = 7.5 (0.97) | 11420 |
| car | 10182-1 | symmetric | 11020 | x = 7.5 (1.00) | 11420 |
| car | 10182-1 | both | 11020 | x = 7.5 (1.00) | 11420 |
| table | 6378-1 | base | 1706 | x = 8.5 (0.98) | 269 |
| table | 6378-1 | skin | 1706 | x = 8.5 (0.98) | 269 |
| table | 6378-1 | symmetric | 1746 | x = 8.5 (1.00) | 269 |
| table | 6378-1 | both | 1746 | x = 8.5 (1.00) | 269 |
| table | 5891-1 | base | 4632 | z = 11.5 (0.98) | 1304 |
| table | 5891-1 | skin | 4632 | z = 11.5 (0.98) | 1304 |
| table | 5891-1 | symmetric | 4728 | z = 11.5 (1.00) | 1304 |
| table | 5891-1 | both | 4728 | z = 11.5 (1.00) | 1304 |
| table | 10182-1 | base | 10609 | x = 15 (0.92) | 9592 |
| table | 10182-1 | skin | 10609 | x = 15 (0.92) | 9592 |
| table | 10182-1 | symmetric | 11449 | x = 15 (1.00) | 9592 |
| table | 10182-1 | both | 11449 | x = 15 (1.00) | 9592 |

## Findings (hand-written from the tables above)

Base judge spread across candidates: sd 0.012 (mean over the 9 cells). Fragmentation of the base builds: top 3.6-8.4,
sides 3.3-5.7 parts per 4 x 4 window (real sets of the same inventories: top 1.5-4.1, sides 2.3-3.3,
`m12b_skins_measure.md`).

**`--skin`: a trade (cleaner skin and more fill, paid with the judge).** Fragmentation falls by 0.69 (top) and
0.78 (sides) parts per window, faces per visible part rise by 1.3, and fill rises by 2.4 points (higher in 7 of 9
cells). It is as fast or faster (up to 4x on the car: bigger parts, fewer placements). The judge falls by 0.017,
more than one sd, in 9 of 9 cells: on the skin, size ordering overrides the learned style. One stability cost: on
the 5891-1 chair, only 18/50 candidates are valid (base 36/50), because 32 fail the real-clutch cap (big parts
cantilevered from the seat and back). Elsewhere validity is unchanged or higher (5891-1 table: 33 -> 44).

**`--symmetric`: a large gain in symmetry for a small fill and judge cost.** The mirrored share of mirrorable
parts rises by 35 points: car 6-10% -> 56-64%, table 11-22% -> 48-60%, chair 8-16% -> 26-29% (the chair has no
global plane; only its seat and back mirror). Most pairs match in color too. That puts it at or above BrickGPT's
own structures (table 49%, car 58%) and still below the real symmetric sets (80-100%). The cost is fill -2.0
points (base-object fill -1.6; the car loses most: 5891-1 61 -> 54%, 10182-1 83 -> 80%) and judge -0.007 (within
one sd, higher in 2 of 9 cells). Fragmentation is unchanged. Time is the same or lower.

**Both: the cleanest skins (top -1.13, sides -0.82) and +31 points mirrored, at the largest judge cost (-0.021,
0/9); fill +0.3.** Selected builds show the best case: the 6378-1 table fills 81% (base 66%), top 2.4 (4.2),
68% mirrored (15%); the 10182-1 car fills 82%, top 3.8 (7.0), sides 3.3 (4.7), 45% mirrored (7%).

**Recommendation (defaults unchanged on this branch; Mac's call):**
- `--symmetric` on by default for a target with a mirror plane. The symmetry gain is large and visible; the
  judge cost is within noise. Fill falls about 2 points, up to 7 on one car. The judge cannot reward
  symmetry, since it compares contact statistics only.
- `--skin` stays a flag for now. Next step if wanted: a soft preference (style weight x cells^a on skin cells
  instead of a hard largest-first sort), measured on the same 9 cells, to keep the cleaner skin without
  the judge loss.

**Mask dependence.** Both flags read only the target mask they are given. `--skin` uses its outer surface
(`shapes.surface`, support columns included). `--symmetric` finds the plane on the scaled object before support
columns and symmetrizes it at a score of 0.8 or more (scores here: car 0.85-0.97, table 0.92-0.98, chair
0.71-0.77). It then adds support columns itself with `with_supports`, mirrored across the plane. A different
sizing (ee's a0ec36c) changes the scores and so needs a recheck of the 0.8 threshold (the 6378-1 car sits at 0.85).
The numbers above are measured on the fd9015b masks.
