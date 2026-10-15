# M12e: token dataset for proposal model v2

`python -m brickwfc.experiments.export_tokens` (format: `bricks/tokens.py`). One part = 5 tokens (Y Z X SHAPE COLOR), raster order (layer, z, x); prefix = 4 header tokens + 64 mask patches (20^3 coarse mask, 5^3 patches); context 1024 tokens = 191 parts.

Vocabulary: **835 tokens** (421 shapes, 78 colors).

| split | source | sequences | parts | part tokens | mean parts | p50 | p90 | max | windows @1024 |
|---|---|---|---|---|---|---|---|---|---|
| train | brickgpt | 42604 | 4581531 | 22907655 | 107.5 | 92 | 193 | 409 | 48511 |
| train | set | 4408 | 911144 | 4555720 | 206.7 | 96 | 460 | 2858 | 9640 |
| val | brickgpt | 4785 | 515799 | 2578995 | 107.8 | 92 | 192 | 409 | 5452 |
| setval | set | 37 | 5934 | 29670 | 160.4 | 61 | 329 | 1560 | 69 |
| heldout | set | 4 | 688 | 3440 | 172.0 | 166 | 209 | 227 | 5 |

Skipped as malformed (BrickGPT): train 0, test 0.

## Sources and splits

- Pool: `results/m12e_omr_pool.json` (catalog `475df2114737`, 183 parts; thresholds {'min_share': 50.0, 'min_on_grid': 50.0, 'min_grid_parts': 20, 'flat_plates': 9, 'flat_area': 1024}): **582 models from 457 sets**. The vocabulary is built from `parts.CATALOG` at export time: 421 shape tokens.
- BrickGPT's splits as before: train in training, test as `val`.
- **Held out** (`heldout.npz`, never trained on, never used for selection; the demo sets): 31048-1, 6378-1.
- **Set validation** (`setval.npz`, the real-set half of the selection loss in `training/train.py`): 23 sets, a seeded 5% of the rest (seed 0): 10018-1, 10025-1, 107-2, 1854-1, 21041-1, 21045-1, 30025-1, 3186-1, 341-2, 40433-1, 41586-1, 41590-1, 4547-1, 4883-1, 5982-1, 6984-1, 75053-1, 76139-1, 7657-1, 7824-1, 7866-1, 8131-1, 8664-1.
- Training: 432 sets, each crop in **8 horizontal symmetries**. A set's main model and alternates are always in the same split.
- Cropping: 14 models do not fit the token grid (64 x 64 studs x 192 plates) and are cut into blocks of that size, each keeping the parts wholly inside it (parts across a block edge and blocks under 20 parts dropped); blocks kept per model: 10214-1 (2), 10233-1 (2), 10241-1 (2), 10261-1 (2), 10277-1 (1), 10294-1 (3), 31084-1 (2), 3185-1 (1), 5974-1 (1), 6286-1 (1), 6392-1 (1), 6396-1 (2), 76042-1 (2), 76139-1 (2).
- Real sets are 16.6% of training parts (after symmetries); `training/train.py` draws `--set-share` of training windows from them.

## Out of vocabulary

Of the pool's 228479 part instances: **27.1% out of vocabulary** (no catalog part; 61860), 19.7% recognized but off the grid (tilted, off the stud grid or overlapping; 45098), 0.3% accessories held by frames (exported with the frame, no token; 755), 0.1% dropped by cropping (across a block edge, or in a block under the minimum size; 251); **52.7% encoded** (120515).
Per model, 10th / 50th / 90th percentile: out of vocabulary 11.5 / 32.6 / 46.3%, not encoded 23.2 / 48.9 / 64.6%.

Per model: `results/m12e_tokens_oov.md`.

## Part types (training split)

| part | brickgpt | set |
|---|---|---|
| brick1x2 | 1104612 | 56312 |
| brick2x6 | 989014 | 2160 |
| brick1x1 | 838551 | 45648 |
| brick2x2 | 542462 | 10536 |
| brick1x4 | 295549 | 27256 |
| brick1x8 | 307004 | 13000 |
| brick2x4 | 275829 | 10168 |
| brick1x6 | 228510 | 20168 |
| plate1x2 | 0 | 67688 |
| plate1x1 | 0 | 45816 |
| tile1x2 | 0 | 29104 |
| plate1x1_6141 | 0 | 27712 |
| plate1x4 | 0 | 27152 |
| tile1x1 | 0 | 22320 |
| plate2x4 | 0 | 20168 |
| brick1x3 | 0 | 19360 |
| plate1x6 | 0 | 18120 |
| plate1x3 | 0 | 15984 |
| brick1x1_4070 | 0 | 15416 |
| tile2x2 | 0 | 14536 |
| brick1x1_3062b | 0 | 14456 |
| plate2x3 | 0 | 14416 |
| plate2x2 | 0 | 14208 |
| tile1x4 | 0 | 12704 |
| slope31_1x1x2 | 0 | 11880 |
| plate1x8 | 0 | 10584 |
| plate2x6 | 0 | 9688 |
| tile1x6 | 0 | 8440 |
| slope45_2x1 | 0 | 7706 |
| slope45inv_2x1 | 0 | 7354 |
| brick1x2_2877 | 0 | 7112 |
| tile1x2_2412b | 0 | 7104 |
| slope45_2x4 | 0 | 6888 |
| plate2x8 | 0 | 6864 |
| tile1x8 | 0 | 6544 |
| brick1x2_3700 | 0 | 6264 |
| jumper1x2_15573 | 0 | 6056 |
| doorrail1x2_32028 | 0 | 6026 |
| plate2x2_corner | 0 | 5648 |
| jumper1x2_3794a | 0 | 5528 |
| brick2x2_6143 | 0 | 5328 |
| brick1x2_30136 | 0 | 5184 |
| brick2x3 | 0 | 4896 |
| tile1x3 | 0 | 4856 |
| slope45inv_2x2 | 0 | 4792 |
| plate1x10 | 0 | 4504 |
| tile2x4 | 0 | 4280 |
| plate2x2_4032a | 0 | 4232 |
| brick2x2_corner | 0 | 4192 |
| brick1x2_98283 | 0 | 4136 |
| plate2x10 | 0 | 3944 |
| slope45_2x2 | 0 | 3848 |
| jumper2x2_87580 | 0 | 3672 |
| slope31_1x2x2 | 0 | 3672 |
| brick1x1_sidestud_87087 | 0 | 3632 |
| jumper1x2_3794b | 0 | 3576 |
| panel1x1x1_6231 | 0 | 3224 |
| plate4x6 | 0 | 3176 |
| slope33_3x1 | 0 | 3124 |
| brick1x1_6541 | 0 | 3032 |
| brick1x2_4216 | 0 | 2968 |
| bracket1x2_2x2_44728 | 0 | 2930 |
| slope45inv_2x2_r270 | 0 | 2848 |
| plate2x2_corner_r180 | 0 | 2832 |
| window1x2x2_60592 | 0 | 2792 |
| plate4x4 | 0 | 2680 |
| brick1x4_sidestuds_30414 | 0 | 2546 |
| plate2x2_corner_r270 | 0 | 2504 |
| brick2x2_3941 | 0 | 2488 |
| slope45_2x3 | 0 | 2416 |
| slope45inv_2x2_r180 | 0 | 2288 |
| brick1x1_59900 | 0 | 2248 |
| plate4x8 | 0 | 2232 |
| plate2x12 | 0 | 2192 |
| slope33_3x2 | 0 | 2140 |
| slope33_3x4 | 0 | 2130 |
| brick2x2_corner_r270 | 0 | 2056 |
| brick2x2_corner_r180 | 0 | 2016 |
| plate1x12 | 0 | 1976 |
| plate6x10 | 0 | 1816 |
| plate1x4_2studs | 0 | 1808 |
| plate2x16 | 0 | 1800 |
| slope45_2x2_r270 | 0 | 1800 |
| panel1x2x2_87552 | 0 | 1776 |
| brick1x1_sidestuds_47905 | 0 | 1768 |
| plate1x1_85861 | 0 | 1720 |
| panel1x2x1_4865a | 0 | 1680 |
| brick1x10 | 0 | 1664 |
| slope45_2x2_r180 | 0 | 1640 |
| plate4x10 | 0 | 1624 |
| brick1x1_sidestud_87087_r270 | 0 | 1600 |
| brick2x8 | 0 | 1592 |
| fence1x4x1_3633 | 0 | 1584 |
| brick1x2x2 | 0 | 1584 |
| tile1x1_98138 | 0 | 1552 |
| plate6x8 | 0 | 1552 |
| slope45_2x8 | 0 | 1550 |
| window1x2x3_60593 | 0 | 1544 |
| doorrail1x8_4510 | 0 | 1506 |
| fence1x4x2_3185 | 0 | 1504 |
| brick1x2x5 | 0 | 1448 |
| brick1x2_3065 | 0 | 1440 |
| panel1x2x1_4865b | 0 | 1432 |
| arch1x4 | 0 | 1256 |
| slope65_2x1x2 | 0 | 1204 |
| plate6x6 | 0 | 1200 |
| brick1x1_sidestud_87087_r180 | 0 | 1184 |
| panel1x2x2_4864b | 0 | 1184 |
| brick1x1_handle_2921 | 0 | 1168 |
| doorframe1x4x6_60596 | 0 | 1104 |
| brick1x1_4589 | 0 | 1104 |
| tile1x1_2555 | 0 | 1072 |
| brick1x12 | 0 | 1024 |
| slope45concave_2x2 | 0 | 1016 |
| plate1x2_35480 | 0 | 968 |
| window1x4x3_60594 | 0 | 960 |
| tile2x2_corner | 0 | 952 |
| brick1x1x5 | 0 | 952 |
| plate4x12 | 0 | 896 |
| slope75_2x1x3 | 0 | 858 |
| brick1x16 | 0 | 856 |
| slope45convex_2x2 | 0 | 848 |
| plate2x2_2studs | 0 | 816 |
| plate1x1_24866 | 0 | 808 |
| plate1x4_2studs_41740 | 0 | 800 |
| tile1x1_25269 | 0 | 792 |
| plate6x12 | 0 | 784 |
| brick1x2_32064a | 0 | 760 |
| plate2x3_hole | 0 | 730 |
| slope33inv_3x2 | 0 | 710 |
| curved2x3_6215 | 0 | 682 |
| brick1x1_handle_2921_r270 | 0 | 664 |
| brick2x2_round_corner | 0 | 648 |
| slope45inv_2x1_r270 | 0 | 626 |
| slope45double_2x4 | 0 | 608 |
| curved1x2x4_6091 | 0 | 598 |
| plate6x16 | 0 | 592 |
| curved1x1x2_49307 | 0 | 584 |
| brick1x1x3 | 0 | 568 |
| plate2x2_2studs_r270 | 0 | 568 |
| plate3x3_round_corner | 0 | 568 |
| curved1x4x4_6191 | 0 | 568 |
| curved1x2_37352 | 0 | 560 |
| fence1x4x2_30055 | 0 | 536 |
| tile2x3 | 0 | 536 |
| brick1x1_3062a | 0 | 528 |
| arch1x6 | 0 | 520 |
| brick1x1_handle_2921_r180 | 0 | 512 |
| slope45_2x1_cutout | 0 | 512 |
| slope45_2x4_r270 | 0 | 510 |
| slope45_2x1_r180 | 0 | 502 |
| slope45_2x1_r270 | 0 | 496 |
| tile2x2_corner_r270 | 0 | 496 |
| window1x2x2_30044 | 0 | 488 |
| baseplate16x32 | 0 | 488 |
| slope45triple_1x2 | 0 | 488 |
| tile2x2_corner_r180 | 0 | 480 |
| slope45inv_2x1_r180 | 0 | 476 |
| brick2x10 | 0 | 472 |
| slope65_2x2x2 | 0 | 472 |
| curved3x1 | 0 | 454 |
| doorrail1x2_32028_r270 | 0 | 448 |
| brick1x4_15533 | 0 | 448 |
| slope18_4x2 | 0 | 446 |
| slope45_2x4_r180 | 0 | 426 |
| window1x2x2_2377 | 0 | 408 |
| arch1x6_raised | 0 | 392 |
| brick2x2_round_corner_r270 | 0 | 368 |
| brick2x2_round_corner_r180 | 0 | 360 |
| window1x4x3_6556 | 0 | 360 |
| slope33convex_3x3 | 0 | 344 |
| slope45convex_2x2_r270 | 0 | 328 |
| slope45convex_2x2_r180 | 0 | 320 |
| doorrail2x8_30586 | 0 | 316 |
| brick2x2_round_corner_85080 | 0 | 312 |
| plate3x3_round_corner_r180 | 0 | 304 |
| plate1x1_4073 | 0 | 304 |
| slope75_2x2x3 | 0 | 304 |
| window1x4x5_2493b | 0 | 296 |
| panel1x2x3_2362b | 0 | 296 |
| plate8x8 | 0 | 296 |
| doorrail1x2_32028_r180 | 0 | 294 |
| slope33_3x3 | 0 | 288 |
| curved2x1 | 0 | 276 |
| plate2x2_2studs_r180 | 0 | 272 |
| tile1x1_3070a | 0 | 264 |
| bracket1x2_2x4_93274 | 0 | 262 |
| arch1x6x2 | 0 | 256 |
| bracket1x2_2x2_44728_r270 | 0 | 254 |
| brick1x4_sidestuds_30414_r270 | 0 | 252 |
| slope65_2x2x2_r270 | 0 | 248 |
| arch1x4x2 | 0 | 248 |
| slope33_3x6 | 0 | 230 |
| slope45double_2x2 | 0 | 216 |
| slope45concave_2x2_r270 | 0 | 208 |
| plate3x3_round_corner_r270 | 0 | 208 |
| curved2x2x2 | 0 | 208 |
| plate2x2_4032b | 0 | 200 |
| plate6x14 | 0 | 200 |
| slope75_2x2x3_r180 | 0 | 192 |
| slope33_3x1_r180 | 0 | 188 |
| slope75_2x2x3_r270 | 0 | 184 |
| slope33_3x4_r270 | 0 | 172 |
| brick1x2_32064b | 0 | 168 |
| slope45_2x3_r180 | 0 | 152 |
| slope33_3x2_r270 | 0 | 144 |
| brick2x2_round_corner_85080_r180 | 0 | 144 |
| slope65_2x1x2_r270 | 0 | 140 |
| brick1x14_4217 | 0 | 136 |
| plate4x4_4studs | 0 | 136 |
| slope65_2x2x2_r180 | 0 | 136 |
| bracket1x2_2x2_44728_r180 | 0 | 136 |
| slope45_2x3_r270 | 0 | 136 |
| slope33double_2x4 | 0 | 136 |
| slope45_2x8_r180 | 0 | 132 |
| brick2x2_round_corner_85080_r270 | 0 | 128 |
| baseplate32x32 | 0 | 128 |
| slope33_3x1_r270 | 0 | 128 |
| window1x2x3_4035 | 0 | 120 |
| slope33_3x3_r270 | 0 | 120 |
| slope33_3x2_r180 | 0 | 116 |
| curved4x1 | 0 | 114 |
| slope45concave_2x2_r180 | 0 | 112 |
| tile1x2_2412a | 0 | 112 |
| brick1x4_sidestuds_30414_r180 | 0 | 106 |
| curved2x2x2_r270 | 0 | 104 |
| doorrail1x8_4510_r180 | 0 | 104 |
| slope33convex_3x3_r270 | 0 | 104 |
| slope33double_2x2 | 0 | 104 |
| window1x4x2_4863 | 0 | 96 |
| brick1x4_3066 | 0 | 96 |
| doorrail1x8_4510_r270 | 0 | 94 |
| tile2x2_round_corner | 0 | 88 |
| curved4x1_double | 0 | 88 |
| slope33convex_3x3_r180 | 0 | 88 |
| slope45double_2x1 | 0 | 88 |
| arch1x3x2_curved | 0 | 86 |
| slope33_3x3_r180 | 0 | 80 |
| slope45_2x8_r270 | 0 | 78 |
| slope75_2x1x3_r270 | 0 | 76 |
| slope33_3x4_r180 | 0 | 74 |
| slope65_2x1x2_r180 | 0 | 72 |
| plate4x4_4studs_r180 | 0 | 72 |
| plate4x4_4studs_r270 | 0 | 64 |
| curved2x2x2_r180 | 0 | 64 |
| plate2x3_hole_r180 | 0 | 64 |
| curved2x3_6215_r270 | 0 | 62 |
| slope33inv_3x2_r180 | 0 | 52 |
| doorrail2x8_30586_r270 | 0 | 52 |
| curved3x1_r180 | 0 | 50 |
| slope75_2x1x3_r180 | 0 | 50 |
| doorframe1x4x6_30179 | 0 | 48 |
| slope18_4x2_r180 | 0 | 42 |
| slope18_4x2_r270 | 0 | 40 |
| curved1x2x4_6091_r270 | 0 | 38 |
| curved2x1_r180 | 0 | 38 |
| slope33inv_3x2_r270 | 0 | 38 |
| slope45double_1x1x2 | 0 | 32 |
| tile2x2_round_corner_r270 | 0 | 32 |
| tile2x2_round_corner_r180 | 0 | 32 |
| plate2x3_hole_r270 | 0 | 30 |
| bracket1x2_2x4_93274_r270 | 0 | 28 |
| slope45double_2x3 | 0 | 24 |
| curved1x2x4_6091_r180 | 0 | 20 |
| curved3x1_r270 | 0 | 16 |
| slope33_3x6_r270 | 0 | 16 |
| curved2x3_6215_r180 | 0 | 16 |
| curved2x1_r270 | 0 | 14 |
| bracket1x2_2x4_93274_r180 | 0 | 14 |
| doorrail2x8_30586_r180 | 0 | 8 |
| arch1x3x2_curved_r180 | 0 | 8 |
| curved4x1_r180 | 0 | 8 |
| curved4x1_r270 | 0 | 6 |
| slope33_3x6_r180 | 0 | 2 |
| arch1x3x2_curved_r270 | 0 | 2 |

## Colors (training sets)

white 138208, black 122352, light_gray 107544, tan 91240, red 78288, dark_gray 61240, yellow 43320, reddish_brown 34408, old_light_gray 30992, blue 28952, dark_red 21584, ldraw47 14376, dark_tan 13264, green 12248, ldraw84 10016, dark_blue 8904, ldraw73 6984, dark_green 6824, ldraw378 6456, ldraw43 6152, ldraw484 5824, old_dark_gray 4768, ldraw40 4496, orange 4432, ldraw379 3832, lime 3584, ldraw322 3448, ldraw330 3352, ldraw36 2480, ldraw30 2480, ldraw308 2248, brown 2208, ldraw3 2080, ldraw191 1816, ldraw297 1768, ldraw46 1560, ldraw29 1544, ldraw57 1528, ldraw34 1432, ldraw33 1432, ldraw179 1224, ldraw212 1216, ldraw135 1096, ldraw78 1096, bright_green 1008, ldraw80 920, ldraw9 776, ldraw85 736, ldraw26 616, ldraw226 432, ldraw38 416, ldraw321 376, ldraw5 256, ldraw42 224, ldraw334 200, ldraw13 152, ldraw37 128, ldraw41 128, ldraw52 96, ldraw23 72, ldraw129 64, ldraw114 64, ldraw323 56, ldraw128 24, ldraw31 16, ldraw326 16, ldraw86 8, ldraw383 8, ldraw35 8, ldraw118 8, ldraw256 8, ldraw511 8, ldraw16 8, ldraw39 8, ldraw12 8
