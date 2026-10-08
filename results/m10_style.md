# M10 — learning style from real sets; WFC vs bottom-up under a learned judge

Reproduce (about 40 minutes on 10 worker processes; resumable):

```
python -m brickwfc.experiments.style --workers 10 --wfc-workers 2 --out out/m10
```

Raw data: `m10_style_summary.json`. Learned statistics for each fold: `m10_style_stats/style_fold*.json`
(`bricks.style.StyleStats.load`).

## What is learned (`bricks/style.py`)

From the voxelized real models (28 building sets, `sets_selection.md`; 12,595 parts on the stud grid):

- **(a) Weights:** part-type and color frequencies.
- **(b) Contact rules, as soft weights:**
  - which part type sits on which: P(U | L);
  - which sits beside which: P(B | A);
  - how often touching parts share a color (vertical 59%, beside 58%);
  - how many parts each part rests on: 1, 2 or 3+ (52% / 25% / 23%; 2+ means it bridges parts, as in a
    running bond).

  `StyleBias` turns these into likelihood ratios that weight the generators' choices:
  - bottom-up D2: the parts tried at a cell, given the part below it and the parts beside it;
  - WFC: tiles at each collapse, given fixed neighbors (`wfc.run(bias=...)`).
- **(c) Judge:** `judge = -divergence`, where the divergence compares the build's own contact statistics
  with the learned ones. It is the mean of the Jensen-Shannon divergences of the vertical type pairs, the
  side-by-side type pairs and the support counts, plus the gaps in the two same-color rates. Higher (closer
  to 0) means more like the training sets. The mean log-likelihood per contact is reported but **not** used
  as the judge: it is gamed by repetitive builds (below).

## Setup

- **4-fold cross-validation** over the 28 sets (folds by a seeded shuffle): every set is held out once, and
  statistics are learned from the other **21** sets.
- **Input for a held-out set X:** the parts of X's real model that lie on the stud grid. So the real model
  is itself a valid build from that input, and serves as the reference.
- **Three styles (ablation):**
  - **uniform:** each of X's (part, color) pairs equally likely; no contact bias.
  - **frequencies:** learned part-type x color frequencies, restricted to X's parts and colors.
  - **contacts:** frequencies + `StyleBias` (strength 1, not tuned).
- **Conditions:**
  - **D2_inventory:** bottom-up builder (any offset), exactly X's parts. This is the real task. Counts are
    fixed, so *frequencies* only change the order in which parts are tried.
  - **D2_free:** the same without part counts.
  - **WFC_free:** WFC + support constraint, no counts. WFC + inventory does not finish at this scale (M9b).
    Only run on sets with at most 250 parts (16 of 28); 120 s cap per build.

  Seeds: 5 for D2, 3 for WFC. Grid: 12 plates tall, volume 1.5x X's.
- **Two metrics:**
  - **Judge** (vs the training sets' statistics), reported in full and **size-matched**: build and real
    model are subsampled to the smaller one's number of contact events (5 seeded draws), because the
    divergence shrinks with size (next section). *Gap* = real model's size-matched judge minus the build's.
  - **Distance to held-out real:** divergence between the build's statistics and X's own (held-out)
    statistics. This is the "held-out statistics" test.
- **Timing caveat:** all jobs ran in parallel (8 bottom-up and 2 WFC worker processes), so times include
  contention and are not comparable with M9b's single-process times.

## The judge depends on size; it is not won by repetition

Over the 28 real models (each judged against the other 27), judge and size correlate with **Spearman
rho = 0.93**: small models (about 200 contact events) score about -0.45, large ones (5,000+) about -0.18.
Sampling noise alone inflates a small build's divergence. So comparisons with the real models are
size-matched; paired comparisons between styles on the same input are barely affected.

Degenerate builds (judged against all 28 sets), with real models subsampled to the same size:

| build | judge terms | judge | real models at this size: min / median / max | likelihood |
|---|---|---|---|---|
| tower of 20 2x4 bricks | 57 | -0.653 | -0.524 / -0.415 / -0.381 | -0.926 |
| tower of 20 1x2 bricks | 57 | -0.635 | -0.524 / -0.415 / -0.381 | -0.806 |
| sheet of 25 2x4 plates | 80 | -0.801 | -0.519 / -0.399 / -0.361 | -1.667 |
| 6 stacked sheets of 1x2 plates | 528 | -0.610 | -0.476 / -0.309 / -0.243 | -1.145 |
| running-bond wall of 1x2 bricks | 163 | -0.581 | -0.479 / -0.355 / -0.310 | -0.970 |
| same wall in two colors | 163 | -0.479 | -0.479 / -0.355 / -0.310 | -1.049 |

Every repetitive build scores below **every** real model of the same size. The likelihood alone would rank
the brick towers (-0.81, -0.93) far above all real models (-1.3 to -1.9 per contact, measured with
statistics that include each model itself, which favors the real models). The one borderline case
is the running-bond wall in two colors: it ties the lowest real model of its size (-0.479). A plausible wall
is judged like a weak real model.

## Results

### All conditions (means over the sets where all three styles produced builds)

| condition | style | sets | valid % | judge | real judge | judge, size-matched | real judge, size-matched | gap to real (size-matched) | likelihood | distance to real | closer than uniform (sets) | time/build (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D2_inventory | uniform | 28 | 100.0 | -0.357 | -0.299 | -0.372 | -0.299 | 0.073 | -2.110 | 0.330 |  | 2.79 |
| D2_inventory | frequencies | 28 | 100.0 | -0.345 | -0.299 | -0.357 | -0.299 | 0.059 | -2.109 | 0.323 | 18/28 | 3.47 |
| D2_inventory | contacts | 28 | 100.0 | -0.316 | -0.299 | -0.328 | -0.299 | 0.029 | -2.007 | 0.298 | 23/28 | 3.26 |
| D2_free | uniform | 28 | 100.0 | -0.369 | -0.299 | -0.402 | -0.299 | 0.103 | -2.126 | 0.391 |  | 3.57 |
| D2_free | frequencies | 28 | 100.0 | -0.298 | -0.299 | -0.324 | -0.299 | 0.025 | -1.814 | 0.335 | 24/28 | 2.98 |
| D2_free | contacts | 28 | 100.0 | -0.234 | -0.299 | -0.256 | -0.299 | -0.043 | -1.589 | 0.282 | 25/28 | 2.06 |
| WFC_free | uniform | 13 | 94.9 | -0.487 | -0.366 | -0.494 | -0.371 | 0.123 | -1.935 | 0.467 |  | 33.48 |
| WFC_free | frequencies | 13 | 97.4 | -0.431 | -0.366 | -0.443 | -0.366 | 0.077 | -1.771 | 0.403 | 12/13 | 33.46 |
| WFC_free | contacts | 13 | 97.4 | -0.382 | -0.366 | -0.399 | -0.366 | 0.033 | -1.642 | 0.373 | 12/13 | 31.18 |

*closer than uniform (sets)*: on how many sets this style's builds are closer to the held-out set's own
statistics than uniform's. *valid %*: whole parts, every part supported, over all seeds. A WFC build that
timed out counts as not valid; every WFC build that finished was valid.

### WFC vs bottom-up, same 13 sets, no part counts (paired)

The 13 sets on which every WFC style finished at least one build. WFC timed out on every build of 374-1 and
6382-1, and on some builds of 7743-1 and 6378-1.

| generator | style | judge, size-matched | real judge, size-matched | gap to real | distance to held-out real | time/build (s) | valid % |
|---|---|---|---|---|---|---|---|
| D2_free | uniform | -0.422 | -0.366 | 0.056 | 0.372 | 0.33 | 100.0 |
| D2_free | frequencies | -0.359 | -0.366 | -0.007 | 0.322 | 0.28 | 100.0 |
| D2_free | contacts | -0.315 | -0.366 | -0.050 | 0.303 | 0.24 | 100.0 |
| WFC_free | uniform | -0.494 | -0.371 | 0.123 | 0.467 | 33.48 | 94.9 |
| WFC_free | frequencies | -0.443 | -0.366 | 0.077 | 0.403 | 33.46 | 97.4 |
| WFC_free | contacts | -0.399 | -0.366 | 0.033 | 0.373 | 31.18 | 97.4 |

With learned contacts, D2's builds get a higher judge than WFC's on **13 of 13** sets and are closer to the
held-out set on **12 of 13**, at about 1/100 of the time.

## Findings

1. **Learned style brings builds closer to held-out real sets, for both generators.** This is the M10 "done
   when". Distance to the held-out set's own statistics, uniform -> frequencies + contacts:
   - D2 with X's parts: 0.330 -> 0.298 (closer on 23 of 28 sets);
   - D2 without counts: 0.391 -> 0.282 (25 of 28);
   - WFC: 0.467 -> 0.373 (12 of 13).

   The size-matched gap to the real model shrinks accordingly: 0.073 -> 0.029 (D2_inventory) and
   0.123 -> 0.033 (WFC).
2. **Both kinds of learning help.**
   - *Frequencies* (which parts and colors) account for a large part of the gain when counts are free.
     There the bottom-up builder otherwise over-uses rare parts.
   - *Contact rules* (what goes on and beside what) add a similar or larger step on top, in every
     condition.
   - With fixed counts (D2_inventory), frequencies only change the order parts are tried in, and do little
     (18/28 sets closer); contacts do the work (23/28).
3. **Bottom-up beats WFC under the learned judge too.** On the same sets and inputs, D2 scores higher than
   WFC with every style, is closer to the held-out sets, never fails, and is about 100x faster. WFC's
   look-ahead does not translate into more realistic structure here. Together with M9b (WFC + inventory
   does not finish), this confirms the pivot: WFC stays a compared method.
4. **The real model is a reference, not a ceiling.** Without counts, D2 with learned contacts scores
   *above* the real held-out model (gap -0.050 on the paired sets, -0.043 over all 28 sets). The judge
   measures closeness to the *average* of the training sets, and the bias pulls builds toward that average,
   while each real set has its own style. The distance to the held-out set's own statistics never gets
   near 0 (0.28 at best). So "scores like a real set" is reached; "looks like *this* set" is not.

## Caveats

- Statistics come from the 81% of recognized parts that voxelize onto the stud grid (`sets_selection.md`).
- Contact statistics are local (pairs of touching parts, support counts). They say nothing about overall
  form: symmetry, walls enclosing rooms, roofs, windows.
- `StyleBias` strength is 1 and was not tuned. The bottom-up bias uses the part below the *visited cell* and
  its side neighbors, not the full footprint of the part finally placed.
- WFC_free covers only the 16 sets with at most 250 parts (4 of them partly or wholly timed out), so the WFC
  comparison is about small sets.

## Judge vs size of real models

Spearman correlation between size (judge terms) and judge over the 28 real models: **0.93**.

| set | judge terms | judge |
|---|---|---|
| 349-1 | 194 | -0.476 |
| 361-2 | 250 | -0.442 |
| 6362-1 | 256 | -0.377 |
| 6363-1 | 274 | -0.379 |
| 7796-1 | 277 | -0.472 |
| 6370-1 | 353 | -0.336 |
| 6380-1 | 418 | -0.413 |
| 377-1 | 529 | -0.325 |
| 6372-1 | 600 | -0.311 |
| 7743-1 | 666 | -0.411 |
| 6382-1 | 682 | -0.356 |
| 6378-1 | 689 | -0.311 |
| 31009-1 | 696 | -0.299 |
| 31048-1 | 703 | -0.341 |
| 374-1 | 862 | -0.352 |
| 5766-1 | 870 | -0.258 |
| 5891-1 | 1371 | -0.257 |
| 5771-1 | 1622 | -0.220 |
| 4956-1 | 1678 | -0.260 |
| 4954-1 | 3287 | -0.262 |
| 10264-1 | 4010 | -0.216 |
| 10190-1 | 4766 | -0.225 |
| 10218-1 | 5002 | -0.184 |
| 10197-1 | 5119 | -0.179 |
| 10243-1 | 5714 | -0.187 |
| 10182-1 | 6104 | -0.152 |
| 10185-1 | 7655 | -0.153 |
| 10224-1 | 8673 | -0.194 |

## Per set

| set | fold | condition | style | finished | valid % | parts | overuse | utilization % | judge | real judge | distance | time/build (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 349-1 | 1 | D2_inventory | uniform | 5/5 | 100 | 46 | 0 | 100 | -0.461 | -0.470 | 0.194 | 0.08 |
| 349-1 | 1 | D2_inventory | frequencies | 5/5 | 100 | 46 | 0 | 100 | -0.452 | -0.470 | 0.194 | 0.11 |
| 349-1 | 1 | D2_inventory | contacts | 5/5 | 100 | 46 | 0 | 100 | -0.451 | -0.470 | 0.182 | 0.10 |
| 349-1 | 1 | D2_free | uniform | 5/5 | 100 | 72 | 30 | 90 | -0.462 | -0.470 | 0.221 | 0.07 |
| 349-1 | 1 | D2_free | frequencies | 5/5 | 100 | 83 | 41 | 91 | -0.420 | -0.470 | 0.159 | 0.06 |
| 349-1 | 1 | D2_free | contacts | 5/5 | 100 | 70 | 30 | 87 | -0.415 | -0.470 | 0.185 | 0.07 |
| 349-1 | 1 | WFC_free | uniform | 3/3 | 100 | 31 | 6 | 55 | -0.550 | -0.470 | 0.282 | 4.46 |
| 349-1 | 1 | WFC_free | frequencies | 3/3 | 100 | 33 | 3 | 66 | -0.533 | -0.470 | 0.262 | 26.78 |
| 349-1 | 1 | WFC_free | contacts | 3/3 | 100 | 43 | 7 | 79 | -0.523 | -0.470 | 0.226 | 24.94 |
| 374-1 | 2 | D2_inventory | uniform | 5/5 | 100 | 213 | 0 | 100 | -0.265 | -0.354 | 0.330 | 0.86 |
| 374-1 | 2 | D2_inventory | frequencies | 5/5 | 100 | 213 | 0 | 100 | -0.265 | -0.354 | 0.324 | 0.90 |
| 374-1 | 2 | D2_inventory | contacts | 5/5 | 100 | 213 | 0 | 100 | -0.254 | -0.354 | 0.303 | 0.85 |
| 374-1 | 2 | D2_free | uniform | 5/5 | 100 | 448 | 289 | 75 | -0.364 | -0.354 | 0.492 | 0.96 |
| 374-1 | 2 | D2_free | frequencies | 5/5 | 100 | 540 | 383 | 74 | -0.340 | -0.354 | 0.462 | 0.92 |
| 374-1 | 2 | D2_free | contacts | 5/5 | 100 | 462 | 307 | 72 | -0.243 | -0.354 | 0.299 | 0.63 |
| 374-1 | 2 | WFC_free | uniform | 0/3 | 0 | — | — | — | — | -0.354 | — | 120.04 |
| 374-1 | 2 | WFC_free | frequencies | 0/3 | 0 | — | — | — | — | -0.354 | — | 120.04 |
| 374-1 | 2 | WFC_free | contacts | 0/3 | 0 | — | — | — | — | -0.354 | — | 120.08 |
| 377-1 | 1 | D2_inventory | uniform | 5/5 | 100 | 116 | 0 | 100 | -0.341 | -0.329 | 0.307 | 0.18 |
| 377-1 | 1 | D2_inventory | frequencies | 5/5 | 100 | 116 | 0 | 100 | -0.337 | -0.329 | 0.297 | 0.19 |
| 377-1 | 1 | D2_inventory | contacts | 5/5 | 100 | 116 | 0 | 100 | -0.335 | -0.329 | 0.306 | 0.21 |
| 377-1 | 1 | D2_free | uniform | 5/5 | 100 | 209 | 121 | 76 | -0.383 | -0.329 | 0.395 | 0.20 |
| 377-1 | 1 | D2_free | frequencies | 5/5 | 100 | 221 | 152 | 60 | -0.261 | -0.329 | 0.300 | 0.20 |
| 377-1 | 1 | D2_free | contacts | 5/5 | 100 | 184 | 123 | 53 | -0.256 | -0.329 | 0.304 | 0.20 |
| 377-1 | 1 | WFC_free | uniform | 3/3 | 100 | 158 | 92 | 57 | -0.486 | -0.329 | 0.495 | 13.72 |
| 377-1 | 1 | WFC_free | frequencies | 3/3 | 100 | 185 | 114 | 61 | -0.382 | -0.329 | 0.387 | 14.01 |
| 377-1 | 1 | WFC_free | contacts | 3/3 | 100 | 189 | 115 | 64 | -0.343 | -0.329 | 0.363 | 13.27 |
| 361-2 | 2 | D2_inventory | uniform | 5/5 | 100 | 49 | 0 | 94 | -0.465 | -0.448 | 0.217 | 0.39 |
| 361-2 | 2 | D2_inventory | frequencies | 5/5 | 100 | 49 | 0 | 94 | -0.462 | -0.448 | 0.220 | 0.35 |
| 361-2 | 2 | D2_inventory | contacts | 5/5 | 100 | 49 | 0 | 94 | -0.463 | -0.448 | 0.231 | 0.41 |
| 361-2 | 2 | D2_free | uniform | 5/5 | 100 | 104 | 57 | 92 | -0.431 | -0.448 | 0.216 | 0.17 |
| 361-2 | 2 | D2_free | frequencies | 5/5 | 100 | 103 | 56 | 90 | -0.430 | -0.448 | 0.205 | 0.13 |
| 361-2 | 2 | D2_free | contacts | 5/5 | 100 | 96 | 52 | 85 | -0.424 | -0.448 | 0.219 | 0.11 |
| 361-2 | 2 | WFC_free | uniform | 3/3 | 100 | 24 | 7 | 34 | -0.583 | -0.448 | 0.399 | 9.36 |
| 361-2 | 2 | WFC_free | frequencies | 3/3 | 100 | 50 | 17 | 65 | -0.524 | -0.448 | 0.327 | 7.78 |
| 361-2 | 2 | WFC_free | contacts | 3/3 | 100 | 50 | 19 | 61 | -0.533 | -0.448 | 0.344 | 7.75 |
| 6363-1 | 1 | D2_inventory | uniform | 5/5 | 100 | 65 | 0 | 96 | -0.306 | -0.379 | 0.278 | 0.42 |
| 6363-1 | 1 | D2_inventory | frequencies | 5/5 | 100 | 65 | 0 | 96 | -0.315 | -0.379 | 0.294 | 0.41 |
| 6363-1 | 1 | D2_inventory | contacts | 5/5 | 100 | 65 | 0 | 96 | -0.307 | -0.379 | 0.293 | 0.41 |
| 6363-1 | 1 | D2_free | uniform | 5/5 | 100 | 136 | 78 | 86 | -0.308 | -0.379 | 0.383 | 0.18 |
| 6363-1 | 1 | D2_free | frequencies | 5/5 | 100 | 121 | 84 | 54 | -0.292 | -0.379 | 0.386 | 0.15 |
| 6363-1 | 1 | D2_free | contacts | 5/5 | 100 | 103 | 69 | 49 | -0.252 | -0.379 | 0.343 | 0.12 |
| 6363-1 | 1 | WFC_free | uniform | 3/3 | 100 | 65 | 30 | 51 | -0.453 | -0.379 | 0.515 | 12.27 |
| 6363-1 | 1 | WFC_free | frequencies | 3/3 | 100 | 94 | 61 | 50 | -0.462 | -0.379 | 0.525 | 10.35 |
| 6363-1 | 1 | WFC_free | contacts | 3/3 | 100 | 111 | 76 | 52 | -0.414 | -0.379 | 0.504 | 9.09 |
| 6382-1 | 3 | D2_inventory | uniform | 5/5 | 100 | 150 | 0 | 100 | -0.306 | -0.354 | 0.354 | 0.85 |
| 6382-1 | 3 | D2_inventory | frequencies | 5/5 | 100 | 150 | 0 | 100 | -0.294 | -0.354 | 0.363 | 1.02 |
| 6382-1 | 3 | D2_inventory | contacts | 5/5 | 100 | 150 | 0 | 100 | -0.282 | -0.354 | 0.329 | 1.06 |
| 6382-1 | 3 | D2_free | uniform | 5/5 | 100 | 388 | 272 | 77 | -0.248 | -0.354 | 0.376 | 1.22 |
| 6382-1 | 3 | D2_free | frequencies | 5/5 | 100 | 416 | 310 | 71 | -0.251 | -0.354 | 0.376 | 0.80 |
| 6382-1 | 3 | D2_free | contacts | 5/5 | 100 | 369 | 265 | 69 | -0.211 | -0.354 | 0.323 | 0.70 |
| 6382-1 | 3 | WFC_free | uniform | 0/3 | 0 | — | — | — | — | -0.354 | — | 120.08 |
| 6382-1 | 3 | WFC_free | frequencies | 0/3 | 0 | — | — | — | — | -0.354 | — | 120.06 |
| 6382-1 | 3 | WFC_free | contacts | 0/3 | 0 | — | — | — | — | -0.354 | — | 120.08 |
| 6362-1 | 3 | D2_inventory | uniform | 5/5 | 100 | 62 | 0 | 100 | -0.369 | -0.384 | 0.303 | 0.13 |
| 6362-1 | 3 | D2_inventory | frequencies | 5/5 | 100 | 62 | 0 | 100 | -0.374 | -0.384 | 0.331 | 0.13 |
| 6362-1 | 3 | D2_inventory | contacts | 5/5 | 100 | 62 | 0 | 100 | -0.350 | -0.384 | 0.301 | 0.14 |
| 6362-1 | 3 | D2_free | uniform | 5/5 | 100 | 114 | 61 | 85 | -0.361 | -0.384 | 0.396 | 0.14 |
| 6362-1 | 3 | D2_free | frequencies | 5/5 | 100 | 116 | 68 | 77 | -0.339 | -0.384 | 0.359 | 0.10 |
| 6362-1 | 3 | D2_free | contacts | 5/5 | 100 | 108 | 61 | 76 | -0.321 | -0.384 | 0.271 | 0.11 |
| 6362-1 | 3 | WFC_free | uniform | 3/3 | 100 | 72 | 45 | 44 | -0.401 | -0.384 | 0.478 | 9.71 |
| 6362-1 | 3 | WFC_free | frequencies | 3/3 | 100 | 90 | 58 | 51 | -0.403 | -0.384 | 0.396 | 8.60 |
| 6362-1 | 3 | WFC_free | contacts | 3/3 | 100 | 118 | 80 | 61 | -0.422 | -0.384 | 0.323 | 6.96 |
| 6372-1 | 2 | D2_inventory | uniform | 5/5 | 100 | 131 | 0 | 100 | -0.309 | -0.315 | 0.304 | 0.41 |
| 6372-1 | 2 | D2_inventory | frequencies | 5/5 | 100 | 131 | 0 | 100 | -0.303 | -0.315 | 0.302 | 0.43 |
| 6372-1 | 2 | D2_inventory | contacts | 5/5 | 100 | 131 | 0 | 100 | -0.274 | -0.315 | 0.281 | 0.45 |
| 6372-1 | 2 | D2_free | uniform | 5/5 | 100 | 259 | 157 | 78 | -0.365 | -0.315 | 0.399 | 0.45 |
| 6372-1 | 2 | D2_free | frequencies | 5/5 | 100 | 272 | 197 | 57 | -0.328 | -0.315 | 0.350 | 0.36 |
| 6372-1 | 2 | D2_free | contacts | 5/5 | 100 | 249 | 190 | 45 | -0.246 | -0.315 | 0.278 | 0.29 |
| 6372-1 | 2 | WFC_free | uniform | 3/3 | 100 | 146 | 83 | 48 | -0.461 | -0.315 | 0.510 | 51.90 |
| 6372-1 | 2 | WFC_free | frequencies | 3/3 | 100 | 213 | 158 | 42 | -0.427 | -0.315 | 0.502 | 51.60 |
| 6372-1 | 2 | WFC_free | contacts | 3/3 | 100 | 230 | 172 | 44 | -0.338 | -0.315 | 0.401 | 43.97 |
| 6370-1 | 0 | D2_inventory | uniform | 5/5 | 100 | 93 | 0 | 100 | -0.378 | -0.337 | 0.418 | 0.25 |
| 6370-1 | 0 | D2_inventory | frequencies | 5/5 | 100 | 93 | 0 | 100 | -0.371 | -0.337 | 0.405 | 0.29 |
| 6370-1 | 0 | D2_inventory | contacts | 5/5 | 100 | 93 | 0 | 100 | -0.340 | -0.337 | 0.373 | 0.31 |
| 6370-1 | 0 | D2_free | uniform | 5/5 | 100 | 176 | 99 | 83 | -0.371 | -0.337 | 0.432 | 0.26 |
| 6370-1 | 0 | D2_free | frequencies | 5/5 | 100 | 186 | 115 | 75 | -0.362 | -0.337 | 0.419 | 0.31 |
| 6370-1 | 0 | D2_free | contacts | 5/5 | 100 | 178 | 113 | 70 | -0.290 | -0.337 | 0.323 | 0.26 |
| 6370-1 | 0 | WFC_free | uniform | 3/3 | 100 | 133 | 82 | 55 | -0.481 | -0.337 | 0.545 | 20.76 |
| 6370-1 | 0 | WFC_free | frequencies | 3/3 | 100 | 144 | 90 | 58 | -0.407 | -0.337 | 0.462 | 21.25 |
| 6370-1 | 0 | WFC_free | contacts | 3/3 | 100 | 158 | 104 | 59 | -0.341 | -0.337 | 0.416 | 19.54 |
| 6378-1 | 3 | D2_inventory | uniform | 5/5 | 100 | 164 | 0 | 100 | -0.371 | -0.314 | 0.415 | 0.78 |
| 6378-1 | 3 | D2_inventory | frequencies | 5/5 | 100 | 164 | 0 | 100 | -0.336 | -0.314 | 0.376 | 0.77 |
| 6378-1 | 3 | D2_inventory | contacts | 5/5 | 100 | 164 | 0 | 100 | -0.325 | -0.314 | 0.371 | 0.79 |
| 6378-1 | 3 | D2_free | uniform | 5/5 | 100 | 381 | 246 | 82 | -0.346 | -0.314 | 0.445 | 0.89 |
| 6378-1 | 3 | D2_free | frequencies | 5/5 | 100 | 394 | 283 | 68 | -0.209 | -0.314 | 0.326 | 0.70 |
| 6378-1 | 3 | D2_free | contacts | 5/5 | 100 | 338 | 241 | 60 | -0.193 | -0.314 | 0.330 | 0.67 |
| 6378-1 | 3 | WFC_free | uniform | 1/3 | 33 | 233 | 137 | 59 | -0.452 | -0.314 | 0.510 | 117.87 |
| 6378-1 | 3 | WFC_free | frequencies | 2/3 | 67 | 291 | 190 | 62 | -0.327 | -0.314 | 0.386 | 116.56 |
| 6378-1 | 3 | WFC_free | contacts | 2/3 | 67 | 319 | 218 | 62 | -0.292 | -0.314 | 0.376 | 116.07 |
| 6380-1 | 2 | D2_inventory | uniform | 5/5 | 100 | 115 | 0 | 100 | -0.332 | -0.415 | 0.356 | 0.32 |
| 6380-1 | 2 | D2_inventory | frequencies | 5/5 | 100 | 115 | 0 | 100 | -0.317 | -0.415 | 0.365 | 0.35 |
| 6380-1 | 2 | D2_inventory | contacts | 5/5 | 100 | 115 | 0 | 100 | -0.311 | -0.415 | 0.368 | 0.39 |
| 6380-1 | 2 | D2_free | uniform | 5/5 | 100 | 243 | 159 | 73 | -0.302 | -0.415 | 0.434 | 0.39 |
| 6380-1 | 2 | D2_free | frequencies | 5/5 | 100 | 251 | 150 | 88 | -0.271 | -0.415 | 0.344 | 0.31 |
| 6380-1 | 2 | D2_free | contacts | 5/5 | 100 | 211 | 121 | 78 | -0.233 | -0.415 | 0.401 | 0.25 |
| 6380-1 | 2 | WFC_free | uniform | 3/3 | 100 | 125 | 74 | 44 | -0.376 | -0.415 | 0.428 | 55.09 |
| 6380-1 | 2 | WFC_free | frequencies | 3/3 | 100 | 184 | 119 | 57 | -0.407 | -0.415 | 0.357 | 40.65 |
| 6380-1 | 2 | WFC_free | contacts | 3/3 | 100 | 201 | 134 | 59 | -0.357 | -0.415 | 0.362 | 39.75 |
| 10182-1 | 3 | D2_inventory | uniform | 5/5 | 100 | 1179 | 0 | 100 | -0.346 | -0.155 | 0.394 | 9.66 |
| 10182-1 | 3 | D2_inventory | frequencies | 5/5 | 100 | 1179 | 0 | 100 | -0.333 | -0.155 | 0.381 | 11.07 |
| 10182-1 | 3 | D2_inventory | contacts | 5/5 | 100 | 1179 | 0 | 100 | -0.273 | -0.155 | 0.326 | 10.00 |
| 10182-1 | 3 | D2_free | uniform | 5/5 | 100 | 2038 | 1144 | 76 | -0.346 | -0.155 | 0.418 | 10.33 |
| 10182-1 | 3 | D2_free | frequencies | 5/5 | 100 | 2099 | 1413 | 58 | -0.250 | -0.155 | 0.329 | 8.79 |
| 10182-1 | 3 | D2_free | contacts | 5/5 | 100 | 1769 | 1320 | 38 | -0.156 | -0.155 | 0.224 | 5.99 |
| 10182-1 | 3 | WFC_free | uniform | not run (1179 parts) | — | — | — | — | — | — | — | — |
| 10182-1 | 3 | WFC_free | frequencies | not run (1179 parts) | — | — | — | — | — | — | — | — |
| 10182-1 | 3 | WFC_free | contacts | not run (1179 parts) | — | — | — | — | — | — | — | — |
| 10190-1 | 3 | D2_inventory | uniform | 5/5 | 100 | 817 | 0 | 100 | -0.381 | -0.230 | 0.349 | 5.49 |
| 10190-1 | 3 | D2_inventory | frequencies | 5/5 | 100 | 817 | 0 | 100 | -0.374 | -0.230 | 0.341 | 8.28 |
| 10190-1 | 3 | D2_inventory | contacts | 5/5 | 100 | 817 | 0 | 100 | -0.317 | -0.230 | 0.288 | 8.93 |
| 10190-1 | 3 | D2_free | uniform | 5/5 | 100 | 1447 | 849 | 73 | -0.351 | -0.230 | 0.414 | 7.58 |
| 10190-1 | 3 | D2_free | frequencies | 5/5 | 100 | 1515 | 1162 | 43 | -0.262 | -0.230 | 0.360 | 7.43 |
| 10190-1 | 3 | D2_free | contacts | 5/5 | 100 | 1371 | 1115 | 31 | -0.168 | -0.230 | 0.271 | 6.05 |
| 10190-1 | 3 | WFC_free | uniform | not run (817 parts) | — | — | — | — | — | — | — | — |
| 10190-1 | 3 | WFC_free | frequencies | not run (817 parts) | — | — | — | — | — | — | — | — |
| 10190-1 | 3 | WFC_free | contacts | not run (817 parts) | — | — | — | — | — | — | — | — |
| 4954-1 | 1 | D2_inventory | uniform | 5/5 | 100 | 638 | 0 | 100 | -0.318 | -0.256 | 0.285 | 2.63 |
| 4954-1 | 1 | D2_inventory | frequencies | 5/5 | 100 | 638 | 0 | 100 | -0.321 | -0.256 | 0.304 | 3.64 |
| 4954-1 | 1 | D2_inventory | contacts | 5/5 | 100 | 638 | 0 | 100 | -0.274 | -0.256 | 0.250 | 3.23 |
| 4954-1 | 1 | D2_free | uniform | 5/5 | 100 | 1299 | 790 | 80 | -0.352 | -0.256 | 0.370 | 3.59 |
| 4954-1 | 1 | D2_free | frequencies | 5/5 | 100 | 1468 | 981 | 76 | -0.324 | -0.256 | 0.369 | 3.90 |
| 4954-1 | 1 | D2_free | contacts | 5/5 | 100 | 1185 | 761 | 66 | -0.182 | -0.256 | 0.251 | 2.48 |
| 4954-1 | 1 | WFC_free | uniform | not run (638 parts) | — | — | — | — | — | — | — | — |
| 4954-1 | 1 | WFC_free | frequencies | not run (638 parts) | — | — | — | — | — | — | — | — |
| 4954-1 | 1 | WFC_free | contacts | not run (638 parts) | — | — | — | — | — | — | — | — |
| 4956-1 | 1 | D2_inventory | uniform | 5/5 | 100 | 373 | 0 | 100 | -0.306 | -0.260 | 0.295 | 1.30 |
| 4956-1 | 1 | D2_inventory | frequencies | 5/5 | 100 | 373 | 0 | 100 | -0.306 | -0.260 | 0.298 | 2.06 |
| 4956-1 | 1 | D2_inventory | contacts | 5/5 | 100 | 373 | 0 | 100 | -0.262 | -0.260 | 0.257 | 1.86 |
| 4956-1 | 1 | D2_free | uniform | 5/5 | 100 | 751 | 446 | 82 | -0.326 | -0.260 | 0.368 | 1.87 |
| 4956-1 | 1 | D2_free | frequencies | 5/5 | 100 | 1021 | 735 | 77 | -0.270 | -0.260 | 0.364 | 2.20 |
| 4956-1 | 1 | D2_free | contacts | 5/5 | 100 | 838 | 614 | 60 | -0.198 | -0.260 | 0.320 | 1.63 |
| 4956-1 | 1 | WFC_free | uniform | not run (373 parts) | — | — | — | — | — | — | — | — |
| 4956-1 | 1 | WFC_free | frequencies | not run (373 parts) | — | — | — | — | — | — | — | — |
| 4956-1 | 1 | WFC_free | contacts | not run (373 parts) | — | — | — | — | — | — | — | — |
| 10185-1 | 3 | D2_inventory | uniform | 5/5 | 100 | 1417 | 0 | 100 | -0.297 | -0.157 | 0.294 | 12.83 |
| 10185-1 | 3 | D2_inventory | frequencies | 5/5 | 100 | 1417 | 0 | 100 | -0.277 | -0.157 | 0.269 | 15.19 |
| 10185-1 | 3 | D2_inventory | contacts | 5/5 | 100 | 1417 | 0 | 100 | -0.240 | -0.157 | 0.243 | 14.84 |
| 10185-1 | 3 | D2_free | uniform | 5/5 | 100 | 2330 | 1274 | 75 | -0.367 | -0.157 | 0.376 | 14.19 |
| 10185-1 | 3 | D2_free | frequencies | 5/5 | 100 | 2446 | 1547 | 63 | -0.213 | -0.157 | 0.255 | 11.74 |
| 10185-1 | 3 | D2_free | contacts | 5/5 | 100 | 2128 | 1412 | 51 | -0.131 | -0.157 | 0.212 | 8.51 |
| 10185-1 | 3 | WFC_free | uniform | not run (1417 parts) | — | — | — | — | — | — | — | — |
| 10185-1 | 3 | WFC_free | frequencies | not run (1417 parts) | — | — | — | — | — | — | — | — |
| 10185-1 | 3 | WFC_free | contacts | not run (1417 parts) | — | — | — | — | — | — | — | — |
| 7743-1 | 0 | D2_inventory | uniform | 5/5 | 100 | 143 | 0 | 98 | -0.406 | -0.410 | 0.380 | 0.92 |
| 7743-1 | 0 | D2_inventory | frequencies | 5/5 | 100 | 143 | 0 | 99 | -0.370 | -0.410 | 0.390 | 1.00 |
| 7743-1 | 0 | D2_inventory | contacts | 5/5 | 100 | 143 | 0 | 99 | -0.366 | -0.410 | 0.387 | 1.05 |
| 7743-1 | 0 | D2_free | uniform | 5/5 | 100 | 267 | 156 | 77 | -0.382 | -0.410 | 0.413 | 0.95 |
| 7743-1 | 0 | D2_free | frequencies | 5/5 | 100 | 245 | 162 | 57 | -0.220 | -0.410 | 0.436 | 0.74 |
| 7743-1 | 0 | D2_free | contacts | 5/5 | 100 | 221 | 152 | 47 | -0.224 | -0.410 | 0.431 | 0.52 |
| 7743-1 | 0 | WFC_free | uniform | 0/3 | 0 | — | — | — | — | -0.410 | — | 120.08 |
| 7743-1 | 0 | WFC_free | frequencies | 0/3 | 0 | — | — | — | — | -0.410 | — | 120.12 |
| 7743-1 | 0 | WFC_free | contacts | 2/3 | 67 | 147 | 78 | 47 | -0.362 | -0.410 | 0.457 | 109.91 |
| 7796-1 | 0 | D2_inventory | uniform | 5/5 | 100 | 47 | 0 | 96 | -0.517 | -0.471 | 0.256 | 0.08 |
| 7796-1 | 0 | D2_inventory | frequencies | 5/5 | 100 | 47 | 0 | 96 | -0.493 | -0.471 | 0.257 | 0.09 |
| 7796-1 | 0 | D2_inventory | contacts | 5/5 | 100 | 47 | 0 | 96 | -0.452 | -0.471 | 0.260 | 0.10 |
| 7796-1 | 0 | D2_free | uniform | 5/5 | 100 | 78 | 38 | 82 | -0.480 | -0.471 | 0.267 | 0.05 |
| 7796-1 | 0 | D2_free | frequencies | 5/5 | 100 | 87 | 55 | 65 | -0.463 | -0.471 | 0.280 | 0.06 |
| 7796-1 | 0 | D2_free | contacts | 5/5 | 100 | 78 | 50 | 56 | -0.370 | -0.471 | 0.390 | 0.07 |
| 7796-1 | 0 | WFC_free | uniform | 3/3 | 100 | 61 | 33 | 57 | -0.560 | -0.471 | 0.378 | 2.05 |
| 7796-1 | 0 | WFC_free | frequencies | 3/3 | 100 | 109 | 82 | 54 | -0.491 | -0.471 | 0.331 | 1.97 |
| 7796-1 | 0 | WFC_free | contacts | 3/3 | 100 | 116 | 88 | 58 | -0.378 | -0.471 | 0.426 | 1.64 |
| 10197-1 | 0 | D2_inventory | uniform | 5/5 | 100 | 1081 | 0 | 100 | -0.301 | -0.182 | 0.334 | 6.76 |
| 10197-1 | 0 | D2_inventory | frequencies | 5/5 | 100 | 1081 | 0 | 100 | -0.272 | -0.182 | 0.308 | 8.84 |
| 10197-1 | 0 | D2_inventory | contacts | 5/5 | 100 | 1081 | 0 | 100 | -0.229 | -0.182 | 0.272 | 6.95 |
| 10197-1 | 0 | D2_free | uniform | 5/5 | 100 | 1613 | 843 | 71 | -0.351 | -0.182 | 0.427 | 9.67 |
| 10197-1 | 0 | D2_free | frequencies | 5/5 | 100 | 1651 | 997 | 60 | -0.244 | -0.182 | 0.304 | 7.60 |
| 10197-1 | 0 | D2_free | contacts | 5/5 | 100 | 1467 | 943 | 48 | -0.167 | -0.182 | 0.192 | 4.98 |
| 10197-1 | 0 | WFC_free | uniform | not run (1081 parts) | — | — | — | — | — | — | — | — |
| 10197-1 | 0 | WFC_free | frequencies | not run (1081 parts) | — | — | — | — | — | — | — | — |
| 10197-1 | 0 | WFC_free | contacts | not run (1081 parts) | — | — | — | — | — | — | — | — |
| 5891-1 | 0 | D2_inventory | uniform | 5/5 | 100 | 290 | 0 | 100 | -0.356 | -0.259 | 0.359 | 1.15 |
| 5891-1 | 0 | D2_inventory | frequencies | 5/5 | 100 | 290 | 0 | 100 | -0.353 | -0.259 | 0.361 | 1.34 |
| 5891-1 | 0 | D2_inventory | contacts | 5/5 | 100 | 290 | 0 | 100 | -0.325 | -0.259 | 0.336 | 1.32 |
| 5891-1 | 0 | D2_free | uniform | 5/5 | 100 | 583 | 359 | 77 | -0.385 | -0.259 | 0.438 | 1.50 |
| 5891-1 | 0 | D2_free | frequencies | 5/5 | 100 | 570 | 374 | 67 | -0.305 | -0.259 | 0.360 | 1.26 |
| 5891-1 | 0 | D2_free | contacts | 5/5 | 100 | 511 | 352 | 55 | -0.221 | -0.259 | 0.263 | 0.84 |
| 5891-1 | 0 | WFC_free | uniform | not run (290 parts) | — | — | — | — | — | — | — | — |
| 5891-1 | 0 | WFC_free | frequencies | not run (290 parts) | — | — | — | — | — | — | — | — |
| 5891-1 | 0 | WFC_free | contacts | not run (290 parts) | — | — | — | — | — | — | — | — |
| 10218-1 | 2 | D2_inventory | uniform | 5/5 | 100 | 958 | 0 | 100 | -0.349 | -0.181 | 0.322 | 6.78 |
| 10218-1 | 2 | D2_inventory | frequencies | 5/5 | 100 | 958 | 0 | 100 | -0.343 | -0.181 | 0.312 | 8.42 |
| 10218-1 | 2 | D2_inventory | contacts | 5/5 | 100 | 958 | 0 | 100 | -0.269 | -0.181 | 0.247 | 7.06 |
| 10218-1 | 2 | D2_free | uniform | 5/5 | 100 | 1609 | 954 | 68 | -0.363 | -0.181 | 0.397 | 8.04 |
| 10218-1 | 2 | D2_free | frequencies | 5/5 | 100 | 1765 | 1230 | 56 | -0.310 | -0.181 | 0.339 | 7.69 |
| 10218-1 | 2 | D2_free | contacts | 5/5 | 100 | 1622 | 1300 | 34 | -0.177 | -0.181 | 0.245 | 5.10 |
| 10218-1 | 2 | WFC_free | uniform | not run (958 parts) | — | — | — | — | — | — | — | — |
| 10218-1 | 2 | WFC_free | frequencies | not run (958 parts) | — | — | — | — | — | — | — | — |
| 10218-1 | 2 | WFC_free | contacts | not run (958 parts) | — | — | — | — | — | — | — | — |
| 5766-1 | 3 | D2_inventory | uniform | 5/5 | 100 | 185 | 0 | 100 | -0.380 | -0.253 | 0.399 | 0.41 |
| 5766-1 | 3 | D2_inventory | frequencies | 5/5 | 100 | 185 | 0 | 100 | -0.354 | -0.253 | 0.361 | 0.51 |
| 5766-1 | 3 | D2_inventory | contacts | 5/5 | 100 | 185 | 0 | 100 | -0.330 | -0.253 | 0.346 | 0.52 |
| 5766-1 | 3 | D2_free | uniform | 5/5 | 100 | 302 | 155 | 80 | -0.394 | -0.253 | 0.435 | 0.53 |
| 5766-1 | 3 | D2_free | frequencies | 5/5 | 100 | 303 | 207 | 52 | -0.256 | -0.253 | 0.303 | 0.53 |
| 5766-1 | 3 | D2_free | contacts | 5/5 | 100 | 265 | 197 | 37 | -0.245 | -0.253 | 0.266 | 0.38 |
| 5766-1 | 3 | WFC_free | uniform | 3/3 | 100 | 232 | 131 | 55 | -0.501 | -0.253 | 0.530 | 46.79 |
| 5766-1 | 3 | WFC_free | frequencies | 3/3 | 100 | 250 | 177 | 39 | -0.355 | -0.253 | 0.402 | 44.92 |
| 5766-1 | 3 | WFC_free | contacts | 3/3 | 100 | 233 | 163 | 38 | -0.320 | -0.253 | 0.362 | 44.43 |
| 5771-1 | 2 | D2_inventory | uniform | 5/5 | 100 | 358 | 0 | 100 | -0.369 | -0.221 | 0.377 | 1.63 |
| 5771-1 | 2 | D2_inventory | frequencies | 5/5 | 100 | 357 | 0 | 100 | -0.364 | -0.221 | 0.374 | 2.42 |
| 5771-1 | 2 | D2_inventory | contacts | 5/5 | 100 | 358 | 0 | 100 | -0.319 | -0.221 | 0.322 | 2.27 |
| 5771-1 | 2 | D2_free | uniform | 5/5 | 100 | 686 | 387 | 83 | -0.404 | -0.221 | 0.433 | 2.68 |
| 5771-1 | 2 | D2_free | frequencies | 5/5 | 100 | 753 | 512 | 67 | -0.292 | -0.221 | 0.361 | 2.36 |
| 5771-1 | 2 | D2_free | contacts | 5/5 | 100 | 649 | 446 | 57 | -0.198 | -0.221 | 0.256 | 1.72 |
| 5771-1 | 2 | WFC_free | uniform | not run (358 parts) | — | — | — | — | — | — | — | — |
| 5771-1 | 2 | WFC_free | frequencies | not run (358 parts) | — | — | — | — | — | — | — | — |
| 5771-1 | 2 | WFC_free | contacts | not run (358 parts) | — | — | — | — | — | — | — | — |
| 10224-1 | 1 | D2_inventory | uniform | 5/5 | 100 | 1591 | 0 | 100 | -0.316 | -0.190 | 0.281 | 13.72 |
| 10224-1 | 1 | D2_inventory | frequencies | 5/5 | 100 | 1591 | 0 | 100 | -0.301 | -0.190 | 0.271 | 16.39 |
| 10224-1 | 1 | D2_inventory | contacts | 5/5 | 100 | 1591 | 0 | 100 | -0.258 | -0.190 | 0.234 | 15.79 |
| 10224-1 | 1 | D2_free | uniform | 5/5 | 100 | 2868 | 1680 | 75 | -0.351 | -0.190 | 0.362 | 18.87 |
| 10224-1 | 1 | D2_free | frequencies | 5/5 | 100 | 3050 | 2154 | 56 | -0.254 | -0.190 | 0.273 | 14.49 |
| 10224-1 | 1 | D2_free | contacts | 5/5 | 100 | 2690 | 2026 | 42 | -0.170 | -0.190 | 0.209 | 8.20 |
| 10224-1 | 1 | WFC_free | uniform | not run (1591 parts) | — | — | — | — | — | — | — | — |
| 10224-1 | 1 | WFC_free | frequencies | not run (1591 parts) | — | — | — | — | — | — | — | — |
| 10224-1 | 1 | WFC_free | contacts | not run (1591 parts) | — | — | — | — | — | — | — | — |
| 31009-1 | 1 | D2_inventory | uniform | 5/5 | 100 | 155 | 0 | 100 | -0.418 | -0.304 | 0.376 | 0.48 |
| 31009-1 | 1 | D2_inventory | frequencies | 5/5 | 100 | 155 | 0 | 100 | -0.403 | -0.304 | 0.357 | 0.58 |
| 31009-1 | 1 | D2_inventory | contacts | 5/5 | 100 | 155 | 0 | 100 | -0.375 | -0.304 | 0.338 | 0.55 |
| 31009-1 | 1 | D2_free | uniform | 5/5 | 100 | 310 | 175 | 87 | -0.393 | -0.304 | 0.379 | 0.56 |
| 31009-1 | 1 | D2_free | frequencies | 5/5 | 100 | 324 | 238 | 55 | -0.304 | -0.304 | 0.322 | 0.48 |
| 31009-1 | 1 | D2_free | contacts | 5/5 | 100 | 281 | 214 | 43 | -0.266 | -0.304 | 0.285 | 0.36 |
| 31009-1 | 1 | WFC_free | uniform | 3/3 | 100 | 181 | 91 | 58 | -0.513 | -0.304 | 0.477 | 58.67 |
| 31009-1 | 1 | WFC_free | frequencies | 3/3 | 100 | 230 | 158 | 47 | -0.411 | -0.304 | 0.398 | 58.39 |
| 31009-1 | 1 | WFC_free | contacts | 3/3 | 100 | 265 | 192 | 47 | -0.343 | -0.304 | 0.344 | 51.83 |
| 10243-1 | 0 | D2_inventory | uniform | 5/5 | 100 | 1135 | 0 | 100 | -0.338 | -0.187 | 0.320 | 4.81 |
| 10243-1 | 0 | D2_inventory | frequencies | 5/5 | 100 | 1133 | 0 | 100 | -0.317 | -0.187 | 0.298 | 6.45 |
| 10243-1 | 0 | D2_inventory | contacts | 5/5 | 100 | 1134 | 0 | 100 | -0.279 | -0.187 | 0.265 | 5.83 |
| 10243-1 | 0 | D2_free | uniform | 5/5 | 100 | 1442 | 627 | 72 | -0.365 | -0.187 | 0.373 | 7.66 |
| 10243-1 | 0 | D2_free | frequencies | 5/5 | 100 | 1476 | 917 | 49 | -0.231 | -0.187 | 0.227 | 5.36 |
| 10243-1 | 0 | D2_free | contacts | 5/5 | 100 | 1300 | 890 | 36 | -0.157 | -0.187 | 0.218 | 3.29 |
| 10243-1 | 0 | WFC_free | uniform | not run (1135 parts) | — | — | — | — | — | — | — | — |
| 10243-1 | 0 | WFC_free | frequencies | not run (1135 parts) | — | — | — | — | — | — | — | — |
| 10243-1 | 0 | WFC_free | contacts | not run (1135 parts) | — | — | — | — | — | — | — | — |
| 31048-1 | 2 | D2_inventory | uniform | 5/5 | 100 | 165 | 0 | 99 | -0.354 | -0.336 | 0.369 | 0.35 |
| 31048-1 | 2 | D2_inventory | frequencies | 5/5 | 100 | 165 | 0 | 99 | -0.330 | -0.336 | 0.343 | 0.37 |
| 31048-1 | 2 | D2_inventory | contacts | 5/5 | 100 | 165 | 0 | 99 | -0.291 | -0.336 | 0.313 | 0.39 |
| 31048-1 | 2 | D2_free | uniform | 5/5 | 100 | 260 | 124 | 82 | -0.399 | -0.336 | 0.436 | 0.34 |
| 31048-1 | 2 | D2_free | frequencies | 5/5 | 100 | 278 | 159 | 72 | -0.373 | -0.336 | 0.438 | 0.24 |
| 31048-1 | 2 | D2_free | contacts | 5/5 | 100 | 220 | 123 | 59 | -0.257 | -0.336 | 0.347 | 0.24 |
| 31048-1 | 2 | WFC_free | uniform | 3/3 | 100 | 163 | 71 | 55 | -0.511 | -0.336 | 0.530 | 32.63 |
| 31048-1 | 2 | WFC_free | frequencies | 3/3 | 100 | 233 | 142 | 54 | -0.474 | -0.336 | 0.510 | 32.15 |
| 31048-1 | 2 | WFC_free | contacts | 3/3 | 100 | 281 | 166 | 69 | -0.364 | -0.336 | 0.407 | 26.11 |
| 10264-1 | 0 | D2_inventory | uniform | 5/5 | 100 | 848 | 0 | 100 | -0.344 | -0.215 | 0.366 | 4.41 |
| 10264-1 | 0 | D2_inventory | frequencies | 5/5 | 100 | 848 | 0 | 100 | -0.325 | -0.215 | 0.346 | 5.60 |
| 10264-1 | 0 | D2_inventory | contacts | 5/5 | 100 | 846 | 0 | 100 | -0.289 | -0.215 | 0.320 | 5.35 |
| 10264-1 | 0 | D2_free | uniform | 5/5 | 100 | 1454 | 896 | 66 | -0.370 | -0.215 | 0.445 | 6.51 |
| 10264-1 | 0 | D2_free | frequencies | 5/5 | 100 | 1432 | 1050 | 45 | -0.277 | -0.215 | 0.365 | 4.61 |
| 10264-1 | 0 | D2_free | contacts | 5/5 | 100 | 1186 | 917 | 32 | -0.172 | -0.215 | 0.245 | 3.96 |
| 10264-1 | 0 | WFC_free | uniform | not run (848 parts) | — | — | — | — | — | — | — | — |
| 10264-1 | 0 | WFC_free | frequencies | not run (848 parts) | — | — | — | — | — | — | — | — |
| 10264-1 | 0 | WFC_free | contacts | not run (848 parts) | — | — | — | — | — | — | — | — |

