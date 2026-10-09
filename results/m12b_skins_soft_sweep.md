# M12b step 3: skin preference and symmetric decoding, before / after

`python -m brickwfc.experiments.skins --steps compare` (measures: `results/m12b_skins_measure.md`). Chair, car and table on 6378-1, 5891-1 and 10182-1, 50 candidates per run, pipeline defaults plus the arm's flags: **base** (the step-1a rerun), **skin** (`--skin`: largest parts first on the target's surface), **symmetric** (`--symmetric`: the target's mirror plane; a car or table, at least 0.8 symmetric after scaling, is made exactly symmetric by adding the mirror image of its cells, the chair, 0.71-0.77, is not; each part's mirror image is placed with it where it fits and the inventory has it), **both**; **skin_a<a>** / **both_a<a>**: the soft skin preference (`--skin --skin-power a`: choice weights x cells ** a on skin cells instead of largest first), alone or with `--symmetric`.

Judge: size-matched across the arms of a cell (every valid candidate subsampled to the smallest one's contact events; higher is better). Fill: of the arm's own object (no support columns). Base-object fill: of the base arm's object, on the same grid (the symmetric arms make a car or table exactly symmetric by adding the mirror image of its cells, so their own object is 2-15% larger). Fragmentation: distinct parts per all-skin 4 x 4-cell window (lower is cleaner). Mirrored: share of mirrorable parts whose mirror image is placed (any color; then same color).

## Change against base (means over valid candidates, averaged over the 1 cells)

| arm | judge | fill (points) | base-object fill (points) | top parts per 4x4 | side parts per 4x4 | faces / visible part | mirrored of mirrorable (points) | judge up in | fill up in |
|---|---|---|---|---|---|---|---|---|---|
| (base: judge sd across candidates, mean over cells) | 0.0209 | | | | | | | | |
| skin | -0.0090 | +4.7 | +4.7 | -0.42 | -1.68 | +2.8 | +8 | 0/1 | 1/1 |
| both | -0.0139 | +8.0 | +8.7 | -0.50 | -1.60 | +2.2 | +35 | 0/1 | 1/1 |
| skin_a0.25 | -0.0014 | -0.4 | -0.4 | -0.11 | -0.42 | +0.1 | +0 | 0/1 | 0/1 |
| skin_a0.5 | +0.0037 | +5.1 | +5.1 | -0.27 | -0.61 | +0.1 | -0 | 1/1 | 1/1 |
| skin_a1 | -0.0008 | +4.0 | +4.0 | -0.58 | -0.93 | +0.5 | -0 | 0/1 | 1/1 |
| skin_a2 | -0.0045 | +6.2 | +6.2 | -0.56 | -1.05 | +0.6 | -0 | 0/1 | 1/1 |
| skin_a4 | -0.0040 | +5.0 | +5.0 | -0.34 | -1.42 | +1.8 | +3 | 0/1 | 1/1 |

## Means over valid candidates

| object | set | arm | valid | judge (sd) | fill % | base-object fill % | top: parts per 4x4 | sides: parts per 4x4 | faces / visible part | mirrored of mirrorable % | same color % | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| table | 6378-1 | base | 50/50 | -0.4118 (0.0209) | 54.3 | 54.3 | 4.52 | 4.37 | 9.8 | 22 | 19 | 12.0 |
| table | 6378-1 | skin | 50/50 | -0.4208 (0.0223) | 59.0 | 59.0 | 4.10 | 2.69 | 12.6 | 31 | 25 | 10.6 |
| table | 6378-1 | both | 50/50 | -0.4257 (0.0289) | 62.3 | 63.0 | 4.02 | 2.77 | 12.0 | 57 | 52 | 9.5 |
| table | 6378-1 | skin_a0.25 | 50/50 | -0.4132 (0.0209) | 53.9 | 53.9 | 4.41 | 3.95 | 9.9 | 23 | 18 | 14.7 |
| table | 6378-1 | skin_a0.5 | 50/50 | -0.4081 (0.0205) | 59.4 | 59.4 | 4.25 | 3.75 | 9.9 | 22 | 17 | 12.6 |
| table | 6378-1 | skin_a1 | 50/50 | -0.4126 (0.0215) | 58.3 | 58.3 | 3.94 | 3.43 | 10.3 | 22 | 18 | 10.7 |
| table | 6378-1 | skin_a2 | 50/50 | -0.4163 (0.0178) | 60.5 | 60.5 | 3.96 | 3.31 | 10.4 | 22 | 18 | 8.0 |
| table | 6378-1 | skin_a4 | 50/50 | -0.4158 (0.0203) | 59.3 | 59.3 | 4.18 | 2.95 | 11.6 | 25 | 20 | 11.8 |

## Selected build (k = 1)

| object | set | arm | valid | judge (sd) | fill % | base-object fill % | top: parts per 4x4 | sides: parts per 4x4 | faces / visible part | mirrored of mirrorable % | same color % | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| table | 6378-1 | base | 50/50 | -0.3888 | 65.8 | 65.8 | 4.20 | 4.97 | 8.9 | 15 | 11 | 12.0 |
| table | 6378-1 | skin | 50/50 | -0.4217 | 71.6 | 71.6 | 3.00 | 2.38 | 10.7 | 24 | 18 | 10.6 |
| table | 6378-1 | both | 50/50 | -0.4357 | 80.6 | 81.2 | 2.44 | 2.93 | 12.1 | 68 | 61 | 9.5 |
| table | 6378-1 | skin_a0.25 | 50/50 | -0.3999 | 73.9 | 73.9 | 3.46 | 3.42 | 9.4 | 25 | 21 | 14.7 |
| table | 6378-1 | skin_a0.5 | 50/50 | -0.3703 | 71.3 | 71.3 | 5.11 | 4.65 | 9.0 | 12 | 12 | 12.6 |
| table | 6378-1 | skin_a1 | 50/50 | -0.3764 | 67.2 | 67.2 | 3.45 | 2.92 | 12.6 | 14 | 14 | 10.7 |
| table | 6378-1 | skin_a2 | 50/50 | -0.4228 | 78.1 | 78.1 | 1.73 | 2.81 | 9.9 | 15 | 11 | 8.0 |
| table | 6378-1 | skin_a4 | 50/50 | -0.4160 | 69.1 | 69.1 | 2.52 | 3.00 | 11.6 | 19 | 18 | 11.8 |

## Targets

| object | set | arm | object cells | plane (score) | judge size (events) |
|---|---|---|---|---|---|
| table | 6378-1 | base | 1706 | x = 8.5 (0.98) | 269 |
| table | 6378-1 | skin | 1706 | x = 8.5 (0.98) | 269 |
| table | 6378-1 | both | 1746 | x = 8.5 (1.00) | 269 |
| table | 6378-1 | skin_a0.25 | 1706 | x = 8.5 (0.98) | 269 |
| table | 6378-1 | skin_a0.5 | 1706 | x = 8.5 (0.98) | 269 |
| table | 6378-1 | skin_a1 | 1706 | x = 8.5 (0.98) | 269 |
| table | 6378-1 | skin_a2 | 1706 | x = 8.5 (0.98) | 269 |
| table | 6378-1 | skin_a4 | 1706 | x = 8.5 (0.98) | 269 |
