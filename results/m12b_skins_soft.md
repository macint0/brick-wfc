# M12b step 3: skin preference and symmetric decoding, before / after

`python -m brickwfc.experiments.skins --steps compare` (measures: `results/m12b_skins_measure.md`). Chair, car and table on 6378-1, 5891-1 and 10182-1, 50 candidates per run, pipeline defaults plus the arm's flags: **base** (the step-1a rerun), **skin** (`--skin`: largest parts first on the target's surface), **symmetric** (`--symmetric`: the target's mirror plane; a car or table, at least 0.8 symmetric after scaling, is made exactly symmetric by adding the mirror image of its cells, the chair, 0.71-0.77, is not; each part's mirror image is placed with it where it fits and the inventory has it), **both**; **skin_a<a>** / **both_a<a>**: the soft skin preference (`--skin --skin-power a`: choice weights x cells ** a on skin cells instead of largest first), alone or with `--symmetric`.

Judge: size-matched across the arms of a cell (every valid candidate subsampled to the smallest one's contact events; higher is better). Fill: of the arm's own object (no support columns). Base-object fill: of the base arm's object, on the same grid (the symmetric arms make a car or table exactly symmetric by adding the mirror image of its cells, so their own object is 2-15% larger). Fragmentation: distinct parts per all-skin 4 x 4-cell window (lower is cleaner). Mirrored: share of mirrorable parts whose mirror image is placed (any color; then same color).

## Change against base (means over valid candidates, averaged over the 9 cells)

| arm | judge | fill (points) | base-object fill (points) | top parts per 4x4 | side parts per 4x4 | faces / visible part | mirrored of mirrorable (points) | judge up in | fill up in |
|---|---|---|---|---|---|---|---|---|---|
| (base: judge sd across candidates, mean over cells) | 0.0121 | | | | | | | | |
| skin | -0.0163 | +2.4 | +2.4 | -0.69 | -0.78 | +1.3 | -0 | 0/9 | 7/9 |
| both | -0.0207 | +0.3 | +0.6 | -1.13 | -0.82 | +1.3 | +31 | 0/9 | 3/9 |
| skin_a1 | -0.0004 | +1.1 | +1.1 | -0.42 | -0.33 | +0.4 | -0 | 2/9 | 6/9 |
| both_a1 | -0.0072 | -1.6 | -1.3 | -0.55 | -0.27 | +0.4 | +35 | 0/9 | 2/9 |
| symmetric | -0.0078 | -2.0 | -1.6 | -0.18 | +0.11 | +0.0 | +35 | 1/9 | 3/9 |

## Means over valid candidates

| object | set | arm | valid | judge (sd) | fill % | base-object fill % | top: parts per 4x4 | sides: parts per 4x4 | faces / visible part | mirrored of mirrorable % | same color % | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chair | 6378-1 | base | 43/50 | -0.4380 (0.0187) | 63.8 | 63.8 | 5.66 | 3.65 | 10.5 | 16 | 15 | 11.2 |
| chair | 6378-1 | skin | 45/50 | -0.4531 (0.0192) | 61.4 | 61.4 | 4.35 | 3.90 | 11.4 | 12 | 11 | 12.0 |
| chair | 6378-1 | both | 41/50 | -0.4533 (0.0263) | 61.6 | 61.6 | 4.52 | 3.75 | 11.2 | 24 | 20 | 12.2 |
| chair | 6378-1 | skin_a1 | 42/50 | -0.4425 (0.0204) | 62.1 | 62.1 | 5.35 | 3.83 | 10.5 | 16 | 15 | 12.9 |
| chair | 6378-1 | both_a1 | 42/50 | -0.4433 (0.0184) | 64.5 | 64.5 | 5.24 | 3.78 | 10.6 | 29 | 26 | 12.7 |
| chair | 6378-1 | symmetric | 47/50 | -0.4424 (0.0171) | 65.2 | 65.2 | 5.80 | 3.77 | 10.4 | 28 | 26 | 11.1 |
| chair | 5891-1 | base | 36/50 | -0.3626 (0.0109) | 58.0 | 58.0 | 7.07 | 3.30 | 10.1 | 11 | 10 | 96.3 |
| chair | 5891-1 | skin | 18/50 | -0.3659 (0.0100) | 58.6 | 58.6 | 5.16 | 3.30 | 11.4 | 7 | 6 | 89.4 |
| chair | 5891-1 | both | 25/50 | -0.3663 (0.0124) | 55.5 | 55.5 | 4.77 | 3.29 | 11.0 | 23 | 20 | 97.4 |
| chair | 5891-1 | skin_a1 | 24/50 | -0.3631 (0.0098) | 57.5 | 57.5 | 6.29 | 3.35 | 10.4 | 10 | 9 | 101.4 |
| chair | 5891-1 | both_a1 | 34/50 | -0.3677 (0.0112) | 57.0 | 57.0 | 6.81 | 3.25 | 10.4 | 24 | 22 | 94.6 |
| chair | 5891-1 | symmetric | 30/50 | -0.3613 (0.0112) | 58.4 | 58.4 | 6.66 | 3.30 | 10.1 | 26 | 24 | 100.9 |
| chair | 10182-1 | base | 48/50 | -0.2925 (0.0070) | 80.8 | 80.8 | 8.43 | 4.37 | 7.4 | 8 | 7 | 102.5 |
| chair | 10182-1 | skin | 50/50 | -0.3119 (0.0068) | 82.9 | 82.9 | 6.95 | 4.23 | 9.2 | 6 | 5 | 82.8 |
| chair | 10182-1 | both | 49/50 | -0.3190 (0.0061) | 82.4 | 82.4 | 7.34 | 4.21 | 9.2 | 31 | 29 | 83.7 |
| chair | 10182-1 | skin_a1 | 49/50 | -0.2949 (0.0071) | 80.9 | 80.9 | 7.92 | 4.37 | 7.9 | 7 | 6 | 106.7 |
| chair | 10182-1 | both_a1 | 48/50 | -0.3012 (0.0066) | 80.0 | 80.0 | 8.43 | 4.26 | 7.9 | 28 | 26 | 103.3 |
| chair | 10182-1 | symmetric | 49/50 | -0.2976 (0.0083) | 79.9 | 79.9 | 8.38 | 4.34 | 7.3 | 29 | 27 | 104.9 |
| car | 6378-1 | base | 50/50 | -0.3269 (0.0136) | 69.8 | 69.8 | 3.60 | 3.44 | 10.0 | 10 | 9 | 4.2 |
| car | 6378-1 | skin | 50/50 | -0.3457 (0.0142) | 73.9 | 73.9 | 3.84 | 3.57 | 10.0 | 15 | 13 | 2.1 |
| car | 6378-1 | both | 50/50 | -0.3580 (0.0136) | 66.4 | 66.9 | 2.73 | 3.40 | 10.1 | 51 | 46 | 2.0 |
| car | 6378-1 | skin_a1 | 50/50 | -0.3240 (0.0118) | 71.2 | 71.2 | 3.73 | 3.55 | 9.9 | 11 | 9 | 2.3 |
| car | 6378-1 | both_a1 | 50/50 | -0.3415 (0.0128) | 65.2 | 65.9 | 2.67 | 3.44 | 9.8 | 57 | 51 | 1.8 |
| car | 6378-1 | symmetric | 50/50 | -0.3451 (0.0156) | 65.2 | 65.9 | 2.86 | 3.43 | 9.7 | 56 | 49 | 3.9 |
| car | 5891-1 | base | 50/50 | -0.3496 (0.0086) | 61.1 | 61.1 | 3.95 | 3.99 | 11.1 | 9 | 7 | 56.7 |
| car | 5891-1 | skin | 50/50 | -0.3615 (0.0078) | 61.4 | 61.4 | 4.92 | 3.12 | 11.1 | 10 | 8 | 14.7 |
| car | 5891-1 | both | 48/50 | -0.3656 (0.0099) | 54.7 | 55.5 | 4.33 | 3.20 | 11.3 | 57 | 52 | 9.7 |
| car | 5891-1 | skin_a1 | 49/50 | -0.3509 (0.0083) | 61.7 | 61.7 | 3.69 | 3.72 | 11.4 | 9 | 7 | 28.2 |
| car | 5891-1 | both_a1 | 48/50 | -0.3613 (0.0105) | 54.1 | 55.0 | 4.37 | 3.90 | 11.1 | 60 | 54 | 31.7 |
| car | 5891-1 | symmetric | 48/50 | -0.3633 (0.0090) | 53.8 | 54.7 | 4.17 | 4.40 | 10.8 | 63 | 56 | 43.4 |
| car | 10182-1 | base | 47/50 | -0.2979 (0.0057) | 82.7 | 82.7 | 6.61 | 4.59 | 8.1 | 6 | 5 | 53.3 |
| car | 10182-1 | skin | 49/50 | -0.3074 (0.0059) | 86.3 | 86.3 | 4.56 | 3.77 | 9.1 | 6 | 5 | 61.1 |
| car | 10182-1 | both | 48/50 | -0.3171 (0.0072) | 81.3 | 81.2 | 3.66 | 3.56 | 10.1 | 58 | 54 | 56.3 |
| car | 10182-1 | skin_a1 | 49/50 | -0.2985 (0.0047) | 83.2 | 83.2 | 5.28 | 4.28 | 8.7 | 6 | 5 | 45.1 |
| car | 10182-1 | both_a1 | 47/50 | -0.3093 (0.0068) | 80.8 | 80.7 | 4.76 | 4.37 | 9.1 | 62 | 57 | 36.5 |
| car | 10182-1 | symmetric | 48/50 | -0.3077 (0.0061) | 79.7 | 79.7 | 5.75 | 4.93 | 8.4 | 64 | 60 | 39.9 |
| table | 6378-1 | base | 50/50 | -0.4118 (0.0209) | 54.3 | 54.3 | 4.52 | 4.37 | 9.8 | 22 | 19 | 12.0 |
| table | 6378-1 | skin | 50/50 | -0.4208 (0.0223) | 59.0 | 59.0 | 4.10 | 2.69 | 12.6 | 31 | 25 | 10.6 |
| table | 6378-1 | both | 50/50 | -0.4257 (0.0289) | 62.3 | 63.0 | 4.02 | 2.77 | 12.0 | 57 | 52 | 9.5 |
| table | 6378-1 | skin_a1 | 50/50 | -0.4126 (0.0215) | 58.3 | 58.3 | 3.94 | 3.43 | 10.3 | 22 | 18 | 10.7 |
| table | 6378-1 | both_a1 | 49/50 | -0.4151 (0.0236) | 56.8 | 57.5 | 3.74 | 3.67 | 10.5 | 61 | 54 | 9.7 |
| table | 6378-1 | symmetric | 49/50 | -0.4170 (0.0251) | 54.6 | 55.3 | 4.30 | 4.49 | 10.0 | 60 | 52 | 14.7 |
| table | 5891-1 | base | 33/50 | -0.3733 (0.0159) | 58.8 | 58.8 | 4.72 | 5.29 | 9.5 | 20 | 17 | 87.0 |
| table | 5891-1 | skin | 44/50 | -0.4076 (0.0091) | 69.0 | 69.0 | 5.35 | 3.18 | 11.2 | 18 | 15 | 51.1 |
| table | 5891-1 | both | 47/50 | -0.4063 (0.0121) | 67.9 | 68.7 | 5.57 | 3.20 | 11.3 | 47 | 43 | 48.3 |
| table | 5891-1 | skin_a1 | 32/50 | -0.3697 (0.0151) | 64.5 | 64.5 | 5.30 | 4.46 | 10.0 | 21 | 18 | 73.4 |
| table | 5891-1 | both_a1 | 33/50 | -0.3733 (0.0193) | 58.2 | 58.9 | 4.77 | 4.53 | 9.8 | 58 | 53 | 61.3 |
| table | 5891-1 | symmetric | 27/50 | -0.3820 (0.0173) | 56.7 | 57.4 | 5.08 | 5.27 | 9.6 | 55 | 50 | 86.6 |
| table | 10182-1 | base | 47/50 | -0.2921 (0.0077) | 78.9 | 78.9 | 7.41 | 5.65 | 5.9 | 11 | 10 | 127.9 |
| table | 10182-1 | skin | 49/50 | -0.3177 (0.0099) | 77.1 | 77.1 | 6.50 | 3.89 | 8.1 | 8 | 7 | 82.2 |
| table | 10182-1 | both | 50/50 | -0.3199 (0.0072) | 78.7 | 78.5 | 4.83 | 3.90 | 8.3 | 44 | 41 | 34.6 |
| table | 10182-1 | skin_a1 | 50/50 | -0.2926 (0.0076) | 78.4 | 78.4 | 6.66 | 4.70 | 6.6 | 10 | 9 | 100.3 |
| table | 10182-1 | both_a1 | 49/50 | -0.2971 (0.0090) | 77.3 | 77.3 | 6.24 | 4.97 | 7.1 | 50 | 46 | 76.8 |
| table | 10182-1 | symmetric | 50/50 | -0.2986 (0.0083) | 77.0 | 77.1 | 7.31 | 5.74 | 6.4 | 48 | 45 | 92.9 |

## Selected build (k = 1)

| object | set | arm | valid | judge (sd) | fill % | base-object fill % | top: parts per 4x4 | sides: parts per 4x4 | faces / visible part | mirrored of mirrorable % | same color % | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chair | 6378-1 | base | 43/50 | -0.4236 | 71.0 | 71.0 | 5.27 | 4.35 | 9.6 | 17 | 17 | 11.2 |
| chair | 6378-1 | skin | 45/50 | -0.4548 | 72.7 | 72.7 | 5.65 | 3.59 | 11.2 | 10 | 10 | 12.0 |
| chair | 6378-1 | both | 41/50 | -0.4398 | 74.5 | 74.5 | 6.65 | 4.65 | 10.0 | 19 | 17 | 12.2 |
| chair | 6378-1 | skin_a1 | 42/50 | -0.4270 | 71.7 | 71.7 | 6.91 | 3.46 | 11.0 | 13 | 13 | 12.9 |
| chair | 6378-1 | both_a1 | 42/50 | -0.4387 | 67.8 | 67.8 | 3.15 | 3.74 | 10.3 | 24 | 22 | 12.7 |
| chair | 6378-1 | symmetric | 47/50 | -0.4024 | 71.4 | 71.4 | 6.25 | 4.06 | 9.7 | 22 | 22 | 11.1 |
| chair | 5891-1 | base | 36/50 | -0.3332 | 58.7 | 58.7 | 8.80 | 3.59 | 9.7 | 15 | 13 | 96.3 |
| chair | 5891-1 | skin | 18/50 | -0.3397 | 61.1 | 61.1 | 7.16 | 3.32 | 10.8 | 6 | 5 | 89.4 |
| chair | 5891-1 | both | 25/50 | -0.3392 | 59.0 | 59.0 | 6.06 | 3.49 | 10.7 | 23 | 20 | 97.4 |
| chair | 5891-1 | skin_a1 | 24/50 | -0.3445 | 58.0 | 58.0 | 7.32 | 3.01 | 10.1 | 12 | 10 | 101.4 |
| chair | 5891-1 | both_a1 | 34/50 | -0.3510 | 60.3 | 60.3 | 6.03 | 3.06 | 11.5 | 18 | 15 | 94.6 |
| chair | 5891-1 | symmetric | 30/50 | -0.3455 | 59.9 | 59.9 | 5.46 | 3.15 | 9.8 | 25 | 25 | 100.9 |
| chair | 10182-1 | base | 48/50 | -0.2764 | 81.3 | 81.3 | 8.44 | 4.41 | 7.6 | 7 | 7 | 102.5 |
| chair | 10182-1 | skin | 50/50 | -0.2969 | 82.9 | 82.9 | 6.91 | 4.34 | 9.3 | 8 | 6 | 82.8 |
| chair | 10182-1 | both | 49/50 | -0.3053 | 82.9 | 82.9 | 7.25 | 3.85 | 9.8 | 41 | 38 | 83.7 |
| chair | 10182-1 | skin_a1 | 49/50 | -0.2840 | 83.7 | 83.7 | 5.88 | 4.58 | 7.9 | 7 | 6 | 106.7 |
| chair | 10182-1 | both_a1 | 48/50 | -0.2902 | 82.4 | 82.4 | 6.74 | 4.28 | 8.0 | 29 | 28 | 103.3 |
| chair | 10182-1 | symmetric | 49/50 | -0.3053 | 84.1 | 84.1 | 8.18 | 4.43 | 7.2 | 22 | 21 | 104.9 |
| car | 6378-1 | base | 50/50 | -0.3067 | 72.9 | 72.9 | 4.50 | 4.15 | 10.2 | 10 | 10 | 4.2 |
| car | 6378-1 | skin | 50/50 | -0.3241 | 76.7 | 76.7 | 5.50 | 3.93 | 9.4 | 14 | 11 | 2.1 |
| car | 6378-1 | both | 50/50 | -0.3391 | 69.7 | 69.6 | 2.83 | 3.00 | 10.2 | 44 | 35 | 2.0 |
| car | 6378-1 | skin_a1 | 50/50 | -0.3107 | 73.8 | 73.8 | 7.00 | 4.41 | 9.3 | 12 | 12 | 2.3 |
| car | 6378-1 | both_a1 | 50/50 | -0.3121 | 66.6 | 67.2 | — | 3.64 | 9.9 | 56 | 51 | 1.8 |
| car | 6378-1 | symmetric | 50/50 | -0.3295 | 67.9 | 69.6 | 6.00 | 2.74 | 9.8 | 55 | 48 | 3.9 |
| car | 5891-1 | base | 50/50 | -0.3286 | 61.4 | 61.4 | 6.00 | 4.24 | 11.0 | 9 | 7 | 56.7 |
| car | 5891-1 | skin | 50/50 | -0.3605 | 65.5 | 65.5 | 3.71 | 2.52 | 11.8 | 11 | 11 | 14.7 |
| car | 5891-1 | both | 48/50 | -0.3523 | 56.9 | 57.7 | 6.78 | 3.24 | 10.7 | 62 | 56 | 9.7 |
| car | 5891-1 | skin_a1 | 49/50 | -0.3341 | 65.1 | 65.1 | 2.57 | 3.70 | 11.8 | 16 | 13 | 28.2 |
| car | 5891-1 | both_a1 | 48/50 | -0.3411 | 55.7 | 56.4 | 3.14 | 3.93 | 11.0 | 71 | 63 | 31.7 |
| car | 5891-1 | symmetric | 48/50 | -0.3412 | 55.6 | 56.6 | 6.56 | 4.01 | 10.3 | 65 | 59 | 43.4 |
| car | 10182-1 | base | 47/50 | -0.2869 | 83.9 | 83.9 | 7.01 | 4.71 | 7.9 | 7 | 6 | 53.3 |
| car | 10182-1 | skin | 49/50 | -0.2892 | 87.8 | 87.8 | 5.24 | 3.77 | 8.9 | 8 | 6 | 61.1 |
| car | 10182-1 | both | 48/50 | -0.3048 | 82.4 | 82.5 | 3.82 | 3.29 | 11.0 | 45 | 42 | 56.3 |
| car | 10182-1 | skin_a1 | 49/50 | -0.2893 | 85.7 | 85.7 | 5.30 | 4.27 | 8.6 | 7 | 5 | 45.1 |
| car | 10182-1 | both_a1 | 47/50 | -0.2976 | 82.1 | 82.1 | 5.11 | 4.61 | 8.9 | 58 | 54 | 36.5 |
| car | 10182-1 | symmetric | 48/50 | -0.2913 | 80.7 | 80.6 | 6.11 | 5.03 | 8.0 | 69 | 65 | 39.9 |
| table | 6378-1 | base | 50/50 | -0.3888 | 65.8 | 65.8 | 4.20 | 4.97 | 8.9 | 15 | 11 | 12.0 |
| table | 6378-1 | skin | 50/50 | -0.4217 | 71.6 | 71.6 | 3.00 | 2.38 | 10.7 | 24 | 18 | 10.6 |
| table | 6378-1 | both | 50/50 | -0.4357 | 80.6 | 81.2 | 2.44 | 2.93 | 12.1 | 68 | 61 | 9.5 |
| table | 6378-1 | skin_a1 | 50/50 | -0.3764 | 67.2 | 67.2 | 3.45 | 2.92 | 12.6 | 14 | 14 | 10.7 |
| table | 6378-1 | both_a1 | 49/50 | -0.4236 | 80.6 | 81.6 | 4.54 | 3.63 | 9.4 | 67 | 60 | 9.7 |
| table | 6378-1 | symmetric | 49/50 | -0.3620 | 58.8 | 59.6 | 5.52 | 6.30 | 8.8 | 54 | 48 | 14.7 |
| table | 5891-1 | base | 33/50 | -0.3577 | 69.5 | 69.5 | 4.45 | 5.08 | 10.6 | 20 | 18 | 87.0 |
| table | 5891-1 | skin | 44/50 | -0.3901 | 73.6 | 73.6 | 5.03 | 3.16 | 11.1 | 16 | 14 | 51.1 |
| table | 5891-1 | both | 47/50 | -0.3946 | 73.8 | 74.4 | 5.51 | 3.10 | 11.7 | 46 | 43 | 48.3 |
| table | 5891-1 | skin_a1 | 32/50 | -0.3641 | 73.9 | 73.9 | 4.37 | 4.17 | 10.3 | 21 | 19 | 73.4 |
| table | 5891-1 | both_a1 | 33/50 | -0.3549 | 68.2 | 69.1 | 5.54 | 4.81 | 10.8 | 59 | 56 | 61.3 |
| table | 5891-1 | symmetric | 27/50 | -0.3650 | 67.4 | 67.9 | 5.80 | 5.46 | 8.7 | 65 | 60 | 86.6 |
| table | 10182-1 | base | 47/50 | -0.2797 | 83.1 | 83.1 | 7.69 | 5.37 | 6.1 | 12 | 11 | 127.9 |
| table | 10182-1 | skin | 49/50 | -0.3191 | 88.2 | 88.2 | 5.88 | 4.05 | 7.9 | 7 | 6 | 82.2 |
| table | 10182-1 | both | 50/50 | -0.3094 | 82.1 | 82.0 | 4.48 | 3.85 | 8.5 | 31 | 29 | 34.6 |
| table | 10182-1 | skin_a1 | 50/50 | -0.2826 | 81.6 | 81.6 | 7.20 | 4.67 | 6.6 | 8 | 7 | 100.3 |
| table | 10182-1 | both_a1 | 49/50 | -0.2828 | 79.9 | 79.8 | 6.62 | 4.65 | 7.2 | 42 | 40 | 76.8 |
| table | 10182-1 | symmetric | 50/50 | -0.2879 | 80.5 | 80.6 | 6.77 | 5.38 | 6.7 | 48 | 46 | 92.9 |

## Targets

| object | set | arm | object cells | plane (score) | judge size (events) |
|---|---|---|---|---|---|
| chair | 6378-1 | base | 1725 | x = 6 (0.71) | 94 |
| chair | 6378-1 | skin | 1725 | x = 6 (0.71) | 94 |
| chair | 6378-1 | both | 1725 | x = 6 (0.71) | 94 |
| chair | 6378-1 | skin_a1 | 1725 | x = 6 (0.71) | 94 |
| chair | 6378-1 | both_a1 | 1725 | x = 6 (0.71) | 94 |
| chair | 6378-1 | symmetric | 1725 | x = 6 (0.71) | 94 |
| chair | 5891-1 | base | 4688 | x = 8 (0.77) | 1908 |
| chair | 5891-1 | skin | 4688 | x = 8 (0.77) | 1908 |
| chair | 5891-1 | both | 4688 | x = 8 (0.77) | 1908 |
| chair | 5891-1 | skin_a1 | 4688 | x = 8 (0.77) | 1908 |
| chair | 5891-1 | both_a1 | 4688 | x = 8 (0.77) | 1908 |
| chair | 5891-1 | symmetric | 4688 | x = 8 (0.77) | 1908 |
| chair | 10182-1 | base | 10656 | x = 11 (0.75) | 10573 |
| chair | 10182-1 | skin | 10656 | x = 11 (0.75) | 10573 |
| chair | 10182-1 | both | 10656 | x = 11 (0.75) | 10573 |
| chair | 10182-1 | skin_a1 | 10656 | x = 11 (0.75) | 10573 |
| chair | 10182-1 | both_a1 | 10656 | x = 11 (0.75) | 10573 |
| chair | 10182-1 | symmetric | 10656 | x = 11 (0.75) | 10573 |
| car | 6378-1 | base | 1689 | x = 4 (0.85) | 1183 |
| car | 6378-1 | skin | 1689 | x = 4 (0.85) | 1183 |
| car | 6378-1 | both | 1946 | x = 4 (1.00) | 1183 |
| car | 6378-1 | skin_a1 | 1689 | x = 4 (0.85) | 1183 |
| car | 6378-1 | both_a1 | 1946 | x = 4 (1.00) | 1183 |
| car | 6378-1 | symmetric | 1946 | x = 4 (1.00) | 1183 |
| car | 5891-1 | base | 4613 | x = 5.5 (0.92) | 2593 |
| car | 5891-1 | skin | 4613 | x = 5.5 (0.92) | 2593 |
| car | 5891-1 | both | 4970 | x = 5.5 (1.00) | 2593 |
| car | 5891-1 | skin_a1 | 4613 | x = 5.5 (0.92) | 2593 |
| car | 5891-1 | both_a1 | 4970 | x = 5.5 (1.00) | 2593 |
| car | 5891-1 | symmetric | 4970 | x = 5.5 (1.00) | 2593 |
| car | 10182-1 | base | 10704 | x = 7.5 (0.97) | 11420 |
| car | 10182-1 | skin | 10704 | x = 7.5 (0.97) | 11420 |
| car | 10182-1 | both | 11020 | x = 7.5 (1.00) | 11420 |
| car | 10182-1 | skin_a1 | 10704 | x = 7.5 (0.97) | 11420 |
| car | 10182-1 | both_a1 | 11020 | x = 7.5 (1.00) | 11420 |
| car | 10182-1 | symmetric | 11020 | x = 7.5 (1.00) | 11420 |
| table | 6378-1 | base | 1706 | x = 8.5 (0.98) | 269 |
| table | 6378-1 | skin | 1706 | x = 8.5 (0.98) | 269 |
| table | 6378-1 | both | 1746 | x = 8.5 (1.00) | 269 |
| table | 6378-1 | skin_a1 | 1706 | x = 8.5 (0.98) | 269 |
| table | 6378-1 | both_a1 | 1746 | x = 8.5 (1.00) | 269 |
| table | 6378-1 | symmetric | 1746 | x = 8.5 (1.00) | 269 |
| table | 5891-1 | base | 4632 | z = 11.5 (0.98) | 1304 |
| table | 5891-1 | skin | 4632 | z = 11.5 (0.98) | 1304 |
| table | 5891-1 | both | 4728 | z = 11.5 (1.00) | 1304 |
| table | 5891-1 | skin_a1 | 4632 | z = 11.5 (0.98) | 1304 |
| table | 5891-1 | both_a1 | 4728 | z = 11.5 (1.00) | 1304 |
| table | 5891-1 | symmetric | 4728 | z = 11.5 (1.00) | 1304 |
| table | 10182-1 | base | 10609 | x = 15 (0.92) | 9592 |
| table | 10182-1 | skin | 10609 | x = 15 (0.92) | 9592 |
| table | 10182-1 | both | 11449 | x = 15 (1.00) | 9592 |
| table | 10182-1 | skin_a1 | 10609 | x = 15 (0.92) | 9592 |
| table | 10182-1 | both_a1 | 11449 | x = 15 (1.00) | 9592 |
| table | 10182-1 | symmetric | 11449 | x = 15 (1.00) | 9592 |

## Findings (soft skin preference, a = 1)

The arm set is base, skin, both, skin_a1, both_a1 and symmetric. Seeds are the same as the first run, and only skin_a1 and both_a1 are new runs; the other arms come from cache. The judge is size-matched across all six arms of a cell, so the base, skin, both and symmetric judge deltas move by up to 0.0005 against `results/m12b_skins.md` (skin −0.0167 → −0.0163, symmetric −0.0073 → −0.0078). a = 1 is the best value from the 6378-1 table sweep (`results/m12b_skins_soft_sweep.md`); the selected skin_a1 build for that cell is identical here (judge −0.376, fill 67%, fragmentation 3.45 / 2.92).

- **skin_a1 against base, means: about half the cleanup for none of the mean judge cost.**
  - Judge −0.0004 (up in 2/9; every cell is within 0.0045 of base, and the base sd across candidates is 0.012).
  - Fill +1.1 points (up in 6/9).
  - Fragmentation: top −0.42 and sides −0.33 parts per 4×4 window, against −0.69 / −0.78 for the hard skin; faces per visible part +0.4 against +1.3.
  - The hard skin costs −0.0163 on the judge and is up in 0/9.
- **Trades still there:**
  - (1) The **5891-1 chair** loses valid candidates: 24/50 against 36/50 for base (hard skin 18/50). The failures are the clutch cap, as with the hard skin. Every other cell is within one candidate of base or above it.
  - (2) **Selected build (k = 1):** the judge is below base in 8/9 cells, by a mean of −0.0035, against −0.024 for the hard skin (9/9 below). The selected build's fill is up in 7/9 (mean +1.8 points). The selected build is the best of about 50 candidates, so it is noisier than the means. Still, the soft preference does not give a better top build under the judge; it gives a cleaner one at roughly equal judge.
- **both_a1 against symmetric:**
  - Mirrored share is the same (+35 points).
  - Judge −0.0072 against −0.0078, fill −1.6 against −2.0 points.
  - Fragmentation −0.55 / −0.27 against −0.18 / +0.11.
  - On the means, adding the soft skin to `--symmetric` costs nothing and cleans the skin. On the selected build it is mixed: the judge is better in 4/9 cells, worse in 4/9 and tied in 1. The 6378-1 table is the largest trade there: −0.4236 at 80.6% fill against −0.3620 at 58.8%.
- **both_a1 against hard both:**
  - Judge −0.0072 against −0.0207, but fill −1.6 against +0.3 points.
  - Fragmentation −0.55 / −0.27 against −1.13 / −0.82.
  - The hard sort cleans more and fills more, while the soft weighting keeps the style.
- **Time:** s/candidate is within the run-to-run spread of base, so there is no cost.

**Recommendation.** a = 1 replaces the hard sort as what `--skin` does: the hard sort's judge cost is too large for its extra cleanup. Keep it off by default for now, because the selected build's judge is slightly lower in 8/9 cells and the 5891-1 chair loses a third of its valid candidates. If `--symmetric` becomes the default for targets with a plane, `--skin --skin-power 1` can go with it (both_a1 is no worse than symmetric on any mean metric). Defaults are Mac's call; nothing on the branch changes them.
