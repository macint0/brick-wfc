# M12c: the wider bench (plan, sizing dry run, run-time estimate)

**Question.** Which sets and objects widen the 9-pair bench (3 small sets × chair / table / car) for the paper
tables, do their targets size without failures, and how long would the creserve arm take on all of them?

**Answer.**
- **Bench:** 9 sets × 6 objects = 54 pairs (`examples/m12c_bench.json`). The 9 current pairs are part of it.
- **Sizing:** every target sizes cleanly at 1.0 and 0.8 (108 targets). No scale cuts an object in two, and usable
  sizing settles every time.
- **What to watch:** the smallest set's objects are tiny, and three chairs at 0.8 have a large overhang moment.
- **Time:** the creserve arm needs about 8.4 h for the 45 new pairs at slack 1.0, or 5.5 h at 0.8. Two thirds of
  that is the two Modular sets, and their estimate is extrapolated beyond the measured sizes. Without 10182-1 it is
  4.0 h or 2.6 h.

## The sets

The 28 building sets of `sets_selection.md`, by inventory volume (fillable cells of the recognized parts), run from
270 to 13958 cells. The three current sets sit in the middle: 6378-1 (1685), 5891-1 (2882), 4956-1 (4382). Six more
widen the bench at both ends and across the themes:

| set | name | theme | year | recognized parts | inventory cells | colours | why |
|---|---|---|---|---:|---:|---:|---|
| 7796-1 | House | Creator | 2008 | 56 | 270 | 9 | the smallest set: a stress test for small targets |
| 6370-1 | Weekend Home | Classic Town | 1985 | 129 | 865 | 6 | small Classic Town; 99% of its parts on the grid |
| 6372-1 | Town House | Classic Town | 1982 | 164 | 1207 | 6 | fills the gap below 6378-1 |
| 6378-1 | Shell Service Station | Classic Town | 1986 | 204 | 1685 | 9 | current |
| 7743-1 | Police Command Center | City | 2008 | 300 | 1952 | 12 | the only City set; an M12 demo set |
| 5891-1 | Apple Tree House | Creator 3-in-1 | 2010 | 460 | 2882 | 13 | current |
| 4956-1 | House | Creator 3-in-1 | 2007 | 573 | 4382 | 12 | current |
| 10190-1 | Market Street | Modular Buildings | 2007 | 1022 | 7686 | 11 | a large Modular set |
| 10182-1 | Cafe Corner | Modular Buildings | 2007 | 1665 | 9720 | 13 | the largest set measured before (M12, M12b); an M12 demo set |

- **Themes:** 3 Classic Town, 3 Creator, 1 City, 2 Modular.
- **Size:** each step is about 1.1–1.7× the next smaller set.
- **Left out:**
  - **349-1 (Legoland):** 2 colours, so it would say nothing about colour.
  - **The Modular sets above 10182-1** (10185-1, 10224-1: 11219 and 13958 cells): by the time model, about 1.3–2× its
    time.
  - **More Creator houses:** they would repeat 5891-1 / 4956-1.

## The objects

BrickGPT's test split, the median-size structure of each of the six most common categories (`experiments/brickgpt.py:
pick_objects`). These are the objects of `m12b_brickgpt.md`, and BrickGPT's own paper shows these categories. Added to
chair / table / car:

| object | id | bricks | form | what it tests |
|---|---|---:|---|---|
| sofa | d1137e5f | 84 | a low solid block with back and arms, no overhang | completeness without support: interior and surface (the thickest object; thinnest section 4–236 cells) |
| vessel | 5c5f88b6 | 46 | a long hull, tapered ends, stepped sides | stepped curves and rims, which use the small parts the M12c limit is about |
| bench | 365bf4bd | 56 | a long thin seat on legs | thin legs and a long span: thin sections, tips, the connect repair |

The six ids are `complete.STRUCTURES`.

## The pair list

`examples/m12c_bench.json` holds `{"sets": [...], "objects": [...]}`: every pair, objects outer.
- **Where it works:** `complete.load_pairs` reads it, and `--pairs FILE` runs these steps on it unchanged:
  - `complete.py --steps sweep sweep-report size-report hollow-sizing bench-plan`
  - `select.py --pairs`
  - `coherence.py --pairs`
- **Defaults:** without the flag every step keeps the 9 sweep pairs (`complete.PAIRS`) in the same order, so every
  existing table reproduces.
- **Order in reports:** they follow the order their cells were built in (`pair_order`).
- **Runs:** each goes to `<out>/sweep/<arm>/<set>/<object>/`, as before. The cached creserve / creserve80 runs of the
  9 current pairs are reused, since a finished run is skipped.

## Sizing dry run

`complete.py --steps bench-plan` sizes each pair as the creserve (1.0) and creserve80 (0.8) runs would: usable sizing,
support columns, thin-aware scale. It generates nothing (108 targets, about 15 minutes on one process).
- **Same targets:** the solid targets of the 9 current pairs equal the cached runs' targets (`m12c_hollow_sizing.md`
  checked this for the same arms).
- **Grids:** within 4–89 cells per axis.
- **Thin-aware scale:** no target was cut in two (thinnest section ≥ 1 everywhere).
- **Usable sizing:** settles in 1–4 rounds.

Three things to watch:
- **7796-1's objects are 177–281 cells.** The chair is 5 × 6 studs, and the thinnest section is 1 cell for most
  objects there. These builds will be crude, and they are the test of how small a target can still be complete.
- **Chairs at 0.8 with a large overhang moment:** 10190-1 (535), 7796-1 (328) and 7743-1 (310). The thin-aware scale
  found no factor whose seat sits over the post. The 4956-1 chair at 0.8 (moment 96) has 42/50 valid against 47/50 at
  1.0 (moment 0), so expect fewer valid candidates on these three.
- **Parts left out by usable sizing:** the 6378-1 plate6x14 ×4 as before, 7743-1's brick1x16 ×2, and small numbers
  elsewhere. That reflects the scale, not a failure.

## Time estimate (creserve arm, 50 candidates, 5 workers)

**Model:** fitted on the 18 cached creserve and creserve80 runs (1138–4554 target cells):
- CPU seconds per candidate (generation and physics) = 4.56e-6 × target cells^1.93, with a log residual sd of 0.25;
- × 1.17 (the median ratio of wall time to CPU time over 5 workers);
- × 50 candidates / 5 workers.

**Check on the cached runs:** it predicts 46 min for the 9 creserve runs (measured 45) and 30 min for creserve80
(measured 30).

| arm | 54 pairs | the 9 cached pairs | 45 new pairs | new pairs without 10182-1 |
|---|---:|---:|---:|---:|
| creserve (1.0) | 9.2 h | 46 min (done) | 8.4 h | 4.0 h |
| creserve80 (0.8) | 6.0 h | 30 min (done) | 5.5 h | 2.6 h |

Per set, all 6 objects:

| set | creserve (1.0) | creserve80 (0.8) |
|---|---:|---:|
| 7796-1 | 0 min | 0 min |
| 6370-1 | 2 min | 2 min |
| 6372-1 | 5 min | 3 min |
| 6378-1 | 9 min | 5 min |
| 7743-1 | 12 min | 8 min |
| 5891-1 | 25 min | 17 min |
| 4956-1 | 58 min | 39 min |
| 10190-1 | 174 min | 111 min |
| 10182-1 | 267 min | 174 min |

**The large sets are extrapolated.** 7500–10100 cells is 1.7–2.2× the largest fitted run. For comparison, the model
gives about 230 CPU s per candidate on 10182-1. M12b measured 48–128 s there (`m12b_brickgpt.md`, `m12b_sizing.md`),
but without the hole pass, hanging or connected growth, which add work at every size. Treat 10190-1 and 10182-1 as
±2×.

**Overnight:**
- At the size rule's slack, run the new pairs of the 7 smaller sets first: 1.1 h at 1.0, 0.7 h at 0.8.
- Then 10190-1, then 10182-1. Every run is resumable, so a morning cut-off loses only what has not finished.

## Dry-run table

Columns:
- **Est. minutes:** the model's wall minutes for that pair's run.
- **Support cells:** target − object (columns under overhangs).
- **Thinnest section:** of the object after the thin-aware scale (0 would mean cut).
- **Overhang moment:** `shapes.overhang_moment` (0: every section's load is over its footprint).

| object | set | slack | inventory parts | grid (YxZxX) | target cells | object cells | support cells | left out (cells) | usable rounds | thinnest section | overhang moment | est. minutes |
|---|---|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---:|
| chair | 7796-1 | 1.0 | 56 | 25x5x6 | 219 | 215 | 4 | 32 (plate2x8 x2) | 2 | 1 | 13 | 0.0 |
| chair | 6370-1 | 1.0 | 129 | 40x9x10 | 799 | 799 | 0 | 40 (plate4x10 x1) | 2 | 1 | 0 | 0.4 |
| chair | 6372-1 | 1.0 | 164 | 43x10x11 | 1151 | 1139 | 12 | 0 | 1 | 2 | 2 | 0.7 |
| chair | 6378-1 | 1.0 | 204 | 48x11x12 | 1326 | 1314 | 12 | 336 (plate6x14 x4) | 2 | 1 | 0 | 1.0 |
| chair | 7743-1 | 1.0 | 300 | 52x12x13 | 1845 | 1836 | 9 | 96 (brick1x16 x2) | 2 | 2 | 0 | 1.8 |
| chair | 5891-1 | 1.0 | 460 | 60x14x15 | 2784 | 2772 | 12 | 0 | 1 | 2 | 0 | 4.0 |
| chair | 4956-1 | 1.0 | 573 | 71x16x18 | 4334 | 4318 | 16 | 0 | 1 | 2 | 0 | 9.3 |
| chair | 10190-1 | 1.0 | 1022 | 83x20x20 | 7685 | 7665 | 20 | 0 | 1 | 6 | 0 | 28.2 |
| chair | 10182-1 | 1.0 | 1665 | 89x21x22 | 9325 | 9265 | 60 | 0 | 1 | 6 | 0 | 41.0 |
| table | 7796-1 | 1.0 | 56 | 25x8x10 | 262 | 262 | 0 | 0 | 1 | 1 | 27 | 0.0 |
| table | 6370-1 | 1.0 | 129 | 36x13x14 | 862 | 862 | 0 | 0 | 1 | 2 | 0 | 0.4 |
| table | 6372-1 | 1.0 | 164 | 43x16x16 | 1299 | 1299 | 0 | 0 | 1 | 2 | 0 | 0.9 |
| table | 6378-1 | 1.0 | 204 | 47x18x18 | 1748 | 1748 | 0 | 0 | 1 | 4 | 0 | 1.6 |
| table | 7743-1 | 1.0 | 300 | 47x18x18 | 1976 | 1976 | 0 | 0 | 1 | 4 | 0 | 2.1 |
| table | 5891-1 | 1.0 | 460 | 55x20x21 | 2880 | 2880 | 0 | 0 | 1 | 4 | 0 | 4.2 |
| table | 4956-1 | 1.0 | 573 | 63x23x24 | 4414 | 4414 | 0 | 0 | 1 | 6 | 0 | 9.7 |
| table | 10190-1 | 1.0 | 1022 | 76x28x29 | 7521 | 7521 | 0 | 0 | 1 | 9 | 0 | 27.1 |
| table | 10182-1 | 1.0 | 1665 | 83x31x32 | 10100 | 10100 | 0 | 0 | 1 | 12 | 0 | 47.9 |
| car | 7796-1 | 1.0 | 56 | 11x9x5 | 268 | 268 | 0 | 0 | 1 | 1 | 0 | 0.0 |
| car | 6370-1 | 1.0 | 129 | 15x15x7 | 877 | 877 | 0 | 0 | 1 | 4 | 0 | 0.4 |
| car | 6372-1 | 1.0 | 164 | 17x16x8 | 1205 | 1205 | 0 | 0 | 1 | 6 | 0 | 0.8 |
| car | 6378-1 | 1.0 | 204 | 20x18x9 | 1721 | 1689 | 32 | 0 | 1 | 6 | 0 | 1.6 |
| car | 7743-1 | 1.0 | 300 | 21x19x9 | 2005 | 1973 | 32 | 0 | 1 | 6 | 0 | 2.1 |
| car | 5891-1 | 1.0 | 460 | 23x22x10 | 2807 | 2775 | 32 | 0 | 1 | 8 | 0 | 4.0 |
| car | 4956-1 | 1.0 | 573 | 26x26x12 | 4554 | 4474 | 80 | 0 | 1 | 12 | 0 | 10.3 |
| car | 10190-1 | 1.0 | 1022 | 32x31x14 | 7902 | 7686 | 216 | 0 | 1 | 15 | 0 | 29.8 |
| car | 10182-1 | 1.0 | 1665 | 34x33x15 | 9778 | 9526 | 252 | 0 | 1 | 15 | 0 | 45.0 |
| sofa | 7796-1 | 1.0 | 56 | 8x7x10 | 281 | 281 | 0 | 0 | 1 | 25 | 0 | 0.0 |
| sofa | 6370-1 | 1.0 | 129 | 12x11x15 | 902 | 902 | 0 | 0 | 1 | 4 | 0 | 0.5 |
| sofa | 6372-1 | 1.0 | 164 | 14x12x16 | 1324 | 1324 | 0 | 0 | 1 | 66 | 0 | 0.9 |
| sofa | 6378-1 | 1.0 | 204 | 15x14x18 | 1791 | 1791 | 0 | 0 | 1 | 76 | 0 | 1.7 |
| sofa | 7743-1 | 1.0 | 300 | 16x13x19 | 1867 | 1867 | 0 | 0 | 1 | 71 | 0 | 1.8 |
| sofa | 5891-1 | 1.0 | 460 | 17x16x21 | 2893 | 2893 | 0 | 0 | 1 | 111 | 0 | 4.3 |
| sofa | 4956-1 | 1.0 | 573 | 20x19x24 | 4380 | 4380 | 0 | 0 | 1 | 149 | 0 | 9.5 |
| sofa | 10190-1 | 1.0 | 1022 | 25x23x30 | 7870 | 7870 | 0 | 0 | 1 | 210 | 0 | 29.6 |
| sofa | 10182-1 | 1.0 | 1665 | 27x24x32 | 9815 | 9815 | 0 | 0 | 1 | 236 | 0 | 45.3 |
| vessel | 7796-1 | 1.0 | 56 | 12x13x4 | 276 | 276 | 0 | 0 | 1 | 1 | 0 | 0.0 |
| vessel | 6370-1 | 1.0 | 129 | 17x19x6 | 868 | 868 | 0 | 0 | 1 | 1 | 0 | 0.4 |
| vessel | 6372-1 | 1.0 | 164 | 19x21x7 | 1206 | 1206 | 0 | 0 | 1 | 1 | 0 | 0.8 |
| vessel | 6378-1 | 1.0 | 204 | 21x24x7 | 1681 | 1681 | 0 | 0 | 1 | 2 | 0 | 1.5 |
| vessel | 7743-1 | 1.0 | 300 | 22x25x8 | 1970 | 1970 | 0 | 0 | 1 | 4 | 0 | 2.0 |
| vessel | 5891-1 | 1.0 | 460 | 25x29x9 | 2970 | 2970 | 0 | 0 | 1 | 2 | 0 | 4.5 |
| vessel | 4956-1 | 1.0 | 573 | 28x33x10 | 4424 | 4424 | 0 | 0 | 1 | 4 | 0 | 9.7 |
| vessel | 10190-1 | 1.0 | 1022 | 35x41x12 | 7980 | 7980 | 0 | 0 | 1 | 6 | 0 | 30.4 |
| vessel | 10182-1 | 1.0 | 1665 | 37x43x13 | 9462 | 9462 | 0 | 0 | 1 | 9 | 0 | 42.2 |
| bench | 7796-1 | 1.0 | 56 | 13x4x13 | 262 | 262 | 0 | 0 | 1 | 1 | 0 | 0.0 |
| bench | 6370-1 | 1.0 | 129 | 24x7x16 | 850 | 850 | 0 | 0 | 1 | 2 | 0 | 0.4 |
| bench | 6372-1 | 1.0 | 164 | 29x8x19 | 1205 | 1205 | 0 | 0 | 1 | 2 | 0 | 0.8 |
| bench | 6378-1 | 1.0 | 204 | 32x9x21 | 1694 | 1694 | 0 | 0 | 1 | 2 | 0 | 1.5 |
| bench | 7743-1 | 1.0 | 300 | 34x10x23 | 1961 | 1961 | 0 | 0 | 1 | 2 | 0 | 2.0 |
| bench | 5891-1 | 1.0 | 460 | 39x11x26 | 2916 | 2916 | 0 | 0 | 1 | 2 | 0 | 4.4 |
| bench | 4956-1 | 1.0 | 573 | 42x12x28 | 4302 | 4302 | 0 | 0 | 1 | 6 | 0 | 9.2 |
| bench | 10190-1 | 1.0 | 1022 | 53x15x35 | 7717 | 7717 | 0 | 0 | 1 | 6 | 0 | 28.5 |
| bench | 10182-1 | 1.0 | 1665 | 56x16x37 | 9810 | 9810 | 0 | 0 | 1 | 8 | 0 | 45.2 |
| chair | 7796-1 | 0.8 | 56 | 24x5x6 | 177 | 177 | 0 | 60 (brick2x2 x1, plate2x8 x2, slope45_2x4 x4, slope45double_2x4 x1) | 4 | 1 | 328 | 0.0 |
| chair | 6370-1 | 0.8 | 129 | 39x8x10 | 682 | 682 | 0 | 40 (plate4x10 x1) | 2 | 1 | 46 | 0.3 |
| chair | 6372-1 | 0.8 | 164 | 42x9x10 | 941 | 932 | 9 | 0 | 1 | 1 | 29 | 0.5 |
| chair | 6378-1 | 0.8 | 204 | 43x10x11 | 1138 | 1126 | 12 | 336 (plate6x14 x4) | 2 | 2 | 2 | 0.7 |
| chair | 7743-1 | 0.8 | 300 | 49x11x12 | 1487 | 1475 | 12 | 96 (brick1x16 x2) | 2 | 2 | 310 | 1.2 |
| chair | 5891-1 | 0.8 | 460 | 56x13x14 | 2323 | 2311 | 12 | 0 | 1 | 2 | 0 | 2.8 |
| chair | 4956-1 | 0.8 | 573 | 66x15x16 | 3480 | 3468 | 12 | 96 (brick1x16 x2) | 2 | 2 | 96 | 6.1 |
| chair | 10190-1 | 0.8 | 1022 | 80x18x20 | 6202 | 6182 | 20 | 0 | 1 | 3 | 535 | 18.7 |
| chair | 10182-1 | 0.8 | 1665 | 83x20x20 | 7685 | 7665 | 20 | 0 | 1 | 6 | 0 | 28.2 |
| table | 7796-1 | 0.8 | 56 | 23x8x9 | 213 | 213 | 0 | 0 | 1 | 1 | 0 | 0.0 |
| table | 6370-1 | 0.8 | 129 | 35x12x14 | 714 | 714 | 0 | 0 | 1 | 2 | 0 | 0.3 |
| table | 6372-1 | 0.8 | 164 | 38x14x14 | 985 | 985 | 0 | 0 | 1 | 2 | 0 | 0.5 |
| table | 6378-1 | 0.8 | 204 | 41x15x16 | 1344 | 1344 | 0 | 0 | 1 | 2 | 0 | 1.0 |
| table | 7743-1 | 0.8 | 300 | 45x17x17 | 1576 | 1576 | 0 | 0 | 1 | 4 | 0 | 1.3 |
| table | 5891-1 | 0.8 | 460 | 51x18x19 | 2328 | 2328 | 0 | 0 | 1 | 4 | 0 | 2.8 |
| table | 4956-1 | 0.8 | 573 | 59x22x23 | 3627 | 3627 | 0 | 0 | 1 | 6 | 0 | 6.6 |
| table | 10190-1 | 0.8 | 1022 | 69x25x26 | 6090 | 6090 | 0 | 0 | 1 | 6 | 0 | 18.0 |
| table | 10182-1 | 0.8 | 1665 | 75x27x28 | 7786 | 7786 | 0 | 0 | 1 | 9 | 0 | 29.0 |
| car | 7796-1 | 0.8 | 56 | 10x8x5 | 226 | 226 | 0 | 0 | 1 | 1 | 0 | 0.0 |
| car | 6370-1 | 0.8 | 129 | 14x13x7 | 705 | 705 | 0 | 0 | 1 | 4 | 0 | 0.3 |
| car | 6372-1 | 0.8 | 164 | 16x15x7 | 947 | 947 | 0 | 0 | 1 | 2 | 0 | 0.5 |
| car | 6378-1 | 0.8 | 204 | 17x17x8 | 1380 | 1356 | 24 | 0 | 1 | 6 | 0 | 1.0 |
| car | 7743-1 | 0.8 | 300 | 19x17x9 | 1601 | 1569 | 32 | 0 | 1 | 6 | 0 | 1.4 |
| car | 5891-1 | 0.8 | 460 | 21x20x10 | 2357 | 2325 | 32 | 0 | 1 | 9 | 0 | 2.9 |
| car | 4956-1 | 0.8 | 573 | 24x23x11 | 3512 | 3480 | 32 | 0 | 1 | 12 | 0 | 6.2 |
| car | 10190-1 | 0.8 | 1022 | 29x28x13 | 6294 | 6214 | 80 | 0 | 1 | 15 | 0 | 19.2 |
| car | 10182-1 | 0.8 | 1665 | 32x31x14 | 7932 | 7716 | 216 | 0 | 1 | 15 | 0 | 30.0 |
| sofa | 7796-1 | 0.8 | 56 | 8x6x10 | 224 | 224 | 0 | 0 | 1 | 4 | 0 | 0.0 |
| sofa | 6370-1 | 0.8 | 129 | 11x9x13 | 665 | 665 | 0 | 0 | 1 | 38 | 0 | 0.3 |
| sofa | 6372-1 | 0.8 | 164 | 12x11x14 | 941 | 941 | 0 | 60 (plate6x10 x1) | 2 | 55 | 0 | 0.5 |
| sofa | 6378-1 | 0.8 | 204 | 13x11x16 | 1108 | 1108 | 0 | 336 (plate6x14 x4) | 2 | 48 | 0 | 0.7 |
| sofa | 7743-1 | 0.8 | 300 | 14x13x17 | 1589 | 1589 | 0 | 0 | 1 | 72 | 0 | 1.3 |
| sofa | 5891-1 | 0.8 | 460 | 17x15x20 | 2420 | 2420 | 0 | 0 | 1 | 95 | 0 | 3.0 |
| sofa | 4956-1 | 0.8 | 573 | 19x17x23 | 3622 | 3622 | 0 | 0 | 1 | 121 | 0 | 6.6 |
| sofa | 10190-1 | 0.8 | 1022 | 23x20x28 | 6101 | 6101 | 0 | 0 | 1 | 170 | 0 | 18.1 |
| sofa | 10182-1 | 0.8 | 1665 | 25x23x30 | 7870 | 7870 | 0 | 0 | 1 | 210 | 0 | 29.6 |
| vessel | 7796-1 | 0.8 | 56 | 8x10x4 | 198 | 198 | 0 | 0 | 1 | 6 | 0 | 0.0 |
| vessel | 6370-1 | 0.8 | 129 | 16x17x6 | 743 | 743 | 0 | 0 | 1 | 1 | 0 | 0.3 |
| vessel | 6372-1 | 0.8 | 164 | 18x20x6 | 967 | 967 | 0 | 0 | 1 | 1 | 0 | 0.5 |
| vessel | 6378-1 | 0.8 | 204 | 18x21x6 | 1062 | 1062 | 0 | 336 (plate6x14 x4) | 2 | 1 | 0 | 0.6 |
| vessel | 7743-1 | 0.8 | 300 | 20x24x7 | 1536 | 1536 | 0 | 0 | 1 | 1 | 0 | 1.3 |
| vessel | 5891-1 | 0.8 | 460 | 23x26x8 | 2291 | 2291 | 0 | 0 | 1 | 2 | 0 | 2.7 |
| vessel | 4956-1 | 0.8 | 573 | 27x31x9 | 3630 | 3630 | 0 | 0 | 1 | 4 | 0 | 6.6 |
| vessel | 10190-1 | 0.8 | 1022 | 32x37x11 | 6132 | 6132 | 0 | 0 | 1 | 4 | 0 | 18.3 |
| vessel | 10182-1 | 0.8 | 1665 | 34x40x12 | 7745 | 7745 | 0 | 0 | 1 | 4 | 0 | 28.7 |
| bench | 7796-1 | 0.8 | 56 | 15x4x10 | 235 | 215 | 20 | 0 | 1 | 1 | 0 | 0.0 |
| bench | 6370-1 | 0.8 | 129 | 23x7x15 | 713 | 713 | 0 | 0 | 1 | 2 | 0 | 0.3 |
| bench | 6372-1 | 0.8 | 164 | 26x7x17 | 910 | 910 | 0 | 60 (plate6x10 x1) | 2 | 2 | 0 | 0.5 |
| bench | 6378-1 | 0.8 | 204 | 29x8x19 | 1352 | 1352 | 0 | 0 | 1 | 2 | 0 | 1.0 |
| bench | 7743-1 | 0.8 | 300 | 30x8x20 | 1545 | 1545 | 0 | 0 | 1 | 2 | 0 | 1.3 |
| bench | 5891-1 | 0.8 | 460 | 35x10x24 | 2296 | 2296 | 0 | 0 | 1 | 2 | 0 | 2.7 |
| bench | 4956-1 | 0.8 | 573 | 39x11x26 | 3544 | 3544 | 0 | 0 | 1 | 3 | 0 | 6.3 |
| bench | 10190-1 | 0.8 | 1022 | 49x14x33 | 6147 | 6147 | 0 | 0 | 1 | 6 | 0 | 18.4 |
| bench | 10182-1 | 0.8 | 1665 | 51x15x34 | 7769 | 7769 | 0 | 0 | 1 | 8 | 0 | 28.8 |

## Reproduce

See `docs/reproduce.md` (§ `results/m12c_bench_plan.md`).
