# M12c: hollow targets at the solid's scale (sizing only)

**Question.** If the shell is cut from the solid target at the solid's scale (`--hollow-scale solid`), how many cells
does it keep, is the void enclosed, and how much of the part budget does the interior free? This decides the shell
thickness of the hollow arms. Nothing is generated.

**Answer.** Use hollow 1. Every void is enclosed: the exposed cells are the solid's on all 36 shells.
- **Hollow 1** keeps 65–90% of the cells and frees a median 25% of the part budget at 1.0 (12–34%).
- **Hollow 2** keeps 82–98% and frees a median 8% (0–18%), about what slack 0.9 frees.
- **Parts that no longer fit.** Under hollow 1, long bricks and large plates fit nowhere in the shell on 8 of 18
  pair × slack cells. With those taken off, the median freed budget is 23% at 1.0, at least 3%.

## Method

`python -m brickwfc.experiments.complete --steps hollow-sizing` covers the 9 sweep pairs at slack 1.0 (creserve) and 0.8
(creserve80).
- **Solid target.** The solid target is sized as the arm sizes it (usable fixpoint, support columns). It equals the
  cached creserve / creserve80 target on 18 of 18.
- **Shell.** `pipeline.solid_scale_shell` hollows the object at that scale (`shapes.hollow`: a 1- or 2-cell shell plus
  2 × 2 pillars every 4 studs) and keeps the support columns.
- **Parts that fit nowhere.** The scale is not refit. Parts that fit in the solid but nowhere in the shell are counted
  with one `inventory.unusable` check on the shell. They stay in the inventory, unusable.

The columns of the table below:
- **Part budget:** the fillable cells of the parts not left out by the usable sizing.
- **Budget − shell:** what the shell leaves over. It can be slightly negative, because the solid lies within ±5% of
  the volume, not on it.
- **Void enclosed:** the shell's exposed cells (`features.exposed`) equal the solid's.

## Result

| object | set | slack | solid cells | exposed | part budget (cells) | hollow | cells kept (%) | exposed (shell) | void enclosed | budget - shell cells (% of budget) | fit nowhere in the shell (cells) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| chair | 6378-1 | 1.0 | 1326 | 1128 | 1349 | 1 | 1189 (90) | 1128 | yes | 160 (12) | 0 |
| chair | 6378-1 | 1.0 | 1326 | 1128 | 1349 | 2 | 1303 (98) | 1128 | yes | 46 (3) | 0 |
| chair | 5891-1 | 1.0 | 2784 | 1995 | 2882 | 1 | 2229 (80) | 1995 | yes | 653 (23) | 0 |
| chair | 5891-1 | 1.0 | 2784 | 1995 | 2882 | 2 | 2655 (95) | 1995 | yes | 227 (8) | 0 |
| chair | 4956-1 | 1.0 | 4334 | 2927 | 4382 | 1 | 3303 (76) | 2927 | yes | 1079 (25) | 0 |
| chair | 4956-1 | 1.0 | 4334 | 2927 | 4382 | 2 | 3978 (92) | 2927 | yes | 404 (9) | 0 |
| table | 6378-1 | 1.0 | 1748 | 1177 | 1685 | 1 | 1313 (75) | 1177 | yes | 372 (22) | 0 |
| table | 6378-1 | 1.0 | 1748 | 1177 | 1685 | 2 | 1642 (94) | 1177 | yes | 43 (3) | 0 |
| table | 5891-1 | 1.0 | 2880 | 1639 | 2882 | 1 | 1953 (68) | 1639 | yes | 929 (32) | 0 |
| table | 5891-1 | 1.0 | 2880 | 1639 | 2882 | 2 | 2453 (85) | 1639 | yes | 429 (15) | 0 |
| table | 4956-1 | 1.0 | 4414 | 2289 | 4382 | 1 | 2876 (65) | 2289 | yes | 1506 (34) | 96 (brick1x16 x2) |
| table | 4956-1 | 1.0 | 4414 | 2289 | 4382 | 2 | 3605 (82) | 2289 | yes | 777 (18) | 0 |
| car | 6378-1 | 1.0 | 1721 | 955 | 1685 | 1 | 1293 (75) | 955 | yes | 392 (23) | 336 (plate6x14 x4) |
| car | 6378-1 | 1.0 | 1721 | 955 | 1685 | 2 | 1690 (98) | 955 | yes | -5 (-0) | 0 |
| car | 5891-1 | 1.0 | 2807 | 1297 | 2882 | 1 | 2012 (72) | 1297 | yes | 870 (30) | 0 |
| car | 5891-1 | 1.0 | 2807 | 1297 | 2882 | 2 | 2659 (95) | 1297 | yes | 223 (8) | 0 |
| car | 4956-1 | 1.0 | 4554 | 1855 | 4382 | 1 | 3031 (67) | 1855 | yes | 1351 (31) | 684 (brick2x6 x7, brick2x8 x9) |
| car | 4956-1 | 1.0 | 4554 | 1855 | 4382 | 2 | 4201 (92) | 1855 | yes | 181 (4) | 0 |
| chair | 6378-1 | 0.8 | 1138 | 961 | 1349 | 1 | 998 (88) | 961 | yes | 351 (26) | 0 |
| chair | 6378-1 | 0.8 | 1138 | 961 | 1349 | 2 | 1138 (100) | 961 | yes | 211 (16) | 0 |
| chair | 5891-1 | 0.8 | 2323 | 1699 | 2882 | 1 | 1862 (80) | 1699 | yes | 1020 (35) | 0 |
| chair | 5891-1 | 0.8 | 2323 | 1699 | 2882 | 2 | 2181 (94) | 1699 | yes | 701 (24) | 0 |
| chair | 4956-1 | 0.8 | 3480 | 2415 | 4286 | 1 | 2700 (78) | 2415 | yes | 1586 (37) | 0 |
| chair | 4956-1 | 0.8 | 3480 | 2415 | 4286 | 2 | 3200 (92) | 2415 | yes | 1086 (25) | 0 |
| table | 6378-1 | 0.8 | 1344 | 935 | 1685 | 1 | 1044 (78) | 935 | yes | 641 (38) | 30 (brick1x10 x1) |
| table | 6378-1 | 0.8 | 1344 | 935 | 1685 | 2 | 1268 (94) | 935 | yes | 417 (25) | 0 |
| table | 5891-1 | 0.8 | 2328 | 1377 | 2882 | 1 | 1607 (69) | 1377 | yes | 1275 (44) | 0 |
| table | 5891-1 | 0.8 | 2328 | 1377 | 2882 | 2 | 1999 (86) | 1377 | yes | 883 (31) | 0 |
| table | 4956-1 | 0.8 | 3627 | 2039 | 4382 | 1 | 2404 (66) | 2039 | yes | 1978 (45) | 240 (brick1x12 x4, brick1x16 x2) |
| table | 4956-1 | 0.8 | 3627 | 2039 | 4382 | 2 | 3103 (86) | 2039 | yes | 1279 (29) | 0 |
| car | 6378-1 | 0.8 | 1380 | 718 | 1685 | 1 | 1085 (79) | 718 | yes | 600 (36) | 336 (plate6x14 x4) |
| car | 6378-1 | 0.8 | 1380 | 718 | 1685 | 2 | 1366 (99) | 718 | yes | 319 (19) | 0 |
| car | 5891-1 | 0.8 | 2357 | 1183 | 2882 | 1 | 1712 (73) | 1183 | yes | 1170 (41) | 140 (plate6x10 x1, slope45_2x8 x10) |
| car | 5891-1 | 0.8 | 2357 | 1183 | 2882 | 2 | 2293 (97) | 1183 | yes | 589 (20) | 0 |
| car | 4956-1 | 0.8 | 3512 | 1558 | 4382 | 1 | 2446 (70) | 1558 | yes | 1936 (44) | 432 (brick2x8 x9) |
| car | 4956-1 | 0.8 | 3512 | 1558 | 4382 | 2 | 3290 (94) | 1558 | yes | 1092 (25) | 0 |

Summary over the 9 pairs. Freed budget is budget − shell cells as % of the budget. Usable is the same with the parts
that fit nowhere in the shell taken off.

| slack | hollow | cells kept % (min–max) | freed % (min / median / max) | freed % usable (min / median) | pairs with parts fitting nowhere |
|---:|---:|---|---|---|---:|
| 1.0 | 1 | 65–90 | 12 / 25 / 34 | 3 / 23 | 3 |
| 1.0 | 2 | 82–98 | 0 / 8 / 18 | 0 / 8 | 0 |
| 0.8 | 1 | 66–88 | 26 / 38 / 45 | 16 / 36 | 5 |
| 0.8 | 2 | 86–100 | 16 / 25 / 31 | 16 / 25 | 0 |

## Reading

- **Hollow 2 is close to the solid.** It keeps 82–98% of the cells at 1.0, because the 2 × 2 pillars every 4 studs
  keep a quarter of what little interior a 2-cell shell leaves.
  - Its freed budget (median 8%) is about what slack 0.9 gives, and the creserve90 arm already measures that.
  - At 0.8 it adds 0–12 points (median 5) to the 16–20% the slack already frees.
- **Hollow 1 frees about three times as much** (median 25% at 1.0, 38% at 0.8). It is the arm that tests the question:
  does an object of the same size get more complete when its interior needs no parts?
- **Costs of hollow 1:**
  - **Parts that fit nowhere.** On 8 of 18 pair × slack cells, some parts fit nowhere in a 1-cell shell: long bricks,
    6 × 10 / 6 × 14 plates, 2 × 8 slopes. On the 6378-1 car that is 336 of its 392 freed cells (four 6 × 14 plates),
    so the usable gain there is 3%.
  - **Thinner structure.** The walls are 1 stud thick and the roofs over the void are 1 plate thick on 2 × 2 pillars.
    How that affects validity (balance, clutch, one piece) is unknown until a run.
- **Freed cells are not small parts.** The budget the interior frees is whatever parts the builder would have put
  there. The M12c limit was the small-part supply on the surface's remnants, so a run is the only test of whether
  freeing large-part volume helps.

## Recommendation

Run `hollow1` and `hollow1_80` (18 runs, compared with creserve / creserve80 on the same object). `hollow2` /
`hollow2_80` are defined but are not worth the time unless hollow 1 loses validity.

## Reproduce

See `docs/reproduce.md` (§ `results/m12c_hollow_sizing.md`).
