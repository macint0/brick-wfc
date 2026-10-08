# M12b step 2: token dataset

`python -m brickwfc.experiments.export_tokens` (format: `bricks/tokens.py`). One part = 5 tokens (Y Z X SHAPE COLOR), raster order (layer, z, x); prefix = 4 header tokens + 64 mask patches (20^3 coarse mask, 5^3 patches); context 1024 tokens = 191 parts.

Vocabulary: **488 tokens** (107 shapes, 45 colors).

| split | source | sequences | parts | part tokens | mean parts | p50 | p90 | max | windows @1024 |
|---|---|---|---|---|---|---|---|---|---|
| train | brickgpt | 42604 | 4581531 | 22907655 | 107.5 | 92 | 193 | 409 | 48511 |
| train | set | 168 | 71632 | 358160 | 426.4 | 166 | 1179 | 1591 | 688 |
| val | brickgpt | 4785 | 515799 | 2578995 | 107.8 | 92 | 192 | 409 | 5452 |
| heldout | set | 7 | 3641 | 18205 | 520.1 | 290 | 1103 | 1135 | 36 |

Skipped as malformed (overlapping bricks or empty): train 0, test 0.

## Real sets: folds, symmetries, oversampling

- Folds: M10's (`experiments.style.folds`, 4 folds, seed 0). **Held out (fold 0):** 6370-1, 7743-1, 7796-1, 10197-1, 5891-1, 10243-1, 10264-1. Not in training; exported once as `heldout.npz`.
- Training sets: each in **8 horizontal symmetries** (4 quarter turns x mirror along x).
- Oversampling: real sets are 1.54% of training parts (after symmetries); `training/train.py` draws 25% of training windows from them (`--set-share`), **16.2x** their natural share.

## Part types (training split)

| part | brickgpt | set |
|---|---|---|
| brick1x2 | 1104612 | 7800 |
| brick2x6 | 989014 | 248 |
| brick1x1 | 838551 | 5264 |
| brick2x2 | 542462 | 808 |
| brick1x8 | 307004 | 3608 |
| brick1x4 | 295549 | 4872 |
| brick2x4 | 275829 | 872 |
| brick1x6 | 228510 | 3424 |
| plate1x2 | 0 | 4160 |
| brick1x3 | 0 | 3880 |
| tile1x2 | 0 | 3456 |
| tile1x1 | 0 | 3344 |
| plate1x1 | 0 | 2960 |
| plate1x1_6141 | 0 | 2696 |
| brick1x1_4070 | 0 | 2456 |
| brick1x1_3062b | 0 | 2216 |
| plate1x4 | 0 | 2128 |
| tile1x6 | 0 | 1752 |
| tile2x2 | 0 | 1720 |
| plate1x6 | 0 | 1448 |
| plate1x3 | 0 | 1040 |
| plate2x4 | 0 | 968 |
| plate1x8 | 0 | 944 |
| tile1x8 | 0 | 944 |
| tile1x4 | 0 | 776 |
| plate2x2 | 0 | 752 |
| plate1x10 | 0 | 696 |
| plate2x6 | 0 | 688 |
| plate2x3 | 0 | 680 |
| brick1x2_2877 | 0 | 664 |
| plate2x10 | 0 | 456 |
| plate2x8 | 0 | 440 |
| brick2x3 | 0 | 352 |
| tile1x2_2412b | 0 | 328 |
| tile1x3 | 0 | 304 |
| brick1x10 | 0 | 296 |
| plate6x10 | 0 | 240 |
| plate2x12 | 0 | 240 |
| plate4x10 | 0 | 152 |
| plate2x2_4032a | 0 | 152 |
| tile1x1_2555 | 0 | 144 |
| tile2x4 | 0 | 128 |
| plate4x8 | 0 | 128 |
| plate6x8 | 0 | 112 |
| brick2x8 | 0 | 104 |
| plate4x4 | 0 | 104 |
| plate4x6 | 0 | 96 |
| plate1x12 | 0 | 96 |
| brick1x16 | 0 | 88 |
| plate8x8 | 0 | 64 |
| plate6x6 | 0 | 64 |
| plate6x14 | 0 | 64 |
| brick2x2_3941 | 0 | 56 |
| brick2x10 | 0 | 56 |
| brick2x2_6143 | 0 | 40 |
| brick1x12 | 0 | 40 |
| plate2x2_4032b | 0 | 16 |
| brick1x2_3065 | 0 | 8 |

## Colors (training sets)

light_gray 16776, white 9352, dark_gray 7816, tan 7272, reddish_brown 5320, black 4520, red 3216, ldraw484 3184, ldraw73 2360, yellow 2104, dark_blue 1952, ldraw378 1440, blue 1312, dark_red 1272, ldraw379 1272, dark_green 776, lime 376, green 344, dark_tan 272, ldraw34 160, old_light_gray 80, ldraw9 72, ldraw38 72, ldraw47 56, ldraw80 48, ldraw29 48, ldraw57 48, orange 40, ldraw85 32, ldraw33 16, ldraw46 16, bright_green 8
