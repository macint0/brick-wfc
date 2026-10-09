# M12b step 2, phase 2: learned proposal vs statistics with a target shape (2026-10-09)

Phase 1 (`results/m12b_proposal.md`) compared the learned proposal with the statistics on box grids, without a target.
There the model decodes with no mask prefix (NOMASK). This phase gives the builder a 3D target shape, the
BrickGPT-style setting the model was trained on: its header carries the target's coarse 20^3 mask. Statistics stay
the no-training baseline in every table. Numbers: `results/m12b_proposal_shape.json`; figure:
`results/m12b_proposal_shape.png`.

**Verdict, with a target shape:**

- **The model does not win on fill.** Against the raster-order control, its object fill is -1.4 points on average.
  It is behind on the two larger sets (-3.2 and -1.4 points, about 1.5-2 standard errors) and level on the smallest
  (+0.4).
- **The model wins under the judge on two of three sets.** Its size-matched judge is higher than the control's on
  6370-1 (+0.010, about 2.5 standard errors) and 7743-1 (+0.021, about 5). It is lower on 7796-1 (-0.012, about
  1.7). The mean difference is +0.0065. This is the reverse of the box setup, where the model lost on 6 of 7 sets.
- **The judge-free check is mixed.** The distance to each set's own statistics confirms the model's judge win on
  6370-1, where its builds are closer. It does not confirm it on 7743-1, where they are slightly farther.
- **Cost.** Every build of every arm is valid, stands, and is one piece. The model takes 4-20x the time per
  candidate: 38-66 s against 2-14 s.

## Setup

**Code and runs.**

- Code: branch m12b-shape-arm at f372c8a, which is main 236ffdf plus `--order` and `--proposal` in the
  alternate-build pipeline. It ran from the worktree's `src` (`PYTHONPATH`).
- Working directory: the main tree, so `data/` (OMR models, BrickGPT structures, the model) and `results/` (style
  statistics, set list) are main's.
- Workers: 10. Nothing else ran on the machine.

**Target and builds.**

- Target: the car `brickgpt:4b15b71c-f400-4e54-a118-f0c2afba6e17`, a BrickGPT test structure with its exact cells
  (overhangs kept), scaled to each inventory's volume.
- Builds: pipeline defaults of the time (open tops; no clutch limit or support columns, both defaults since 2026-10-09): D2 with balance, the bridge preference, the connect pass (10 rounds),
  and the fill floor. 20 candidates per (set, arm), seeds 0-19, the same seeds in every arm.

| arm | pipeline options |
|---|---|
| stats_random | none (M12's pipeline) |
| stats_raster | `--order raster`: the control for the visiting order |
| proposal_raster | `--order raster --proposal data/models/proposal_run2.npz` |

**Model.** `proposal_run2.npz`, the model of phase 1. Its session gets the target as its mask prefix (`MASK` plus
the 64 mask patches). The `--proposal` option keys the candidates cache by a hash of the weights, so no statistics
candidate is reused.

**Sets.** The three smallest fold-0 sets: 7796-1, 6370-1, 7743-1. Neither the model nor the style statistics (v2,
fold 0) were trained on them.

**Not cut.** The 150 s per candidate rule for 7743-1 did not apply: its proposal arm took 66 s per candidate. The run
of that arm was interrupted and resumed from its cache. All 20 candidates were generated once. The funnel outputs were
rewritten from the cache with `--n 20`.

| set | inventory parts | target cells | grid (Y, Z, X) |
|---|---|---|---|
| 7796-1 | 56 | 370 | 12 x 10 x 5 |
| 6370-1 | 129 | 1404 | 18 x 17 x 8 |
| 7743-1 | 300 | 1973 | 21 x 19 x 9 |

The pipeline reads more of each set's parts than phase 1 did: all parts in the catalog, not only those voxelized
onto the M10 grid. 7743-1 has 300 parts here and 153 there.

**Metrics.** Computed by `experiments/proposal_shape.py` over each arm's candidates.

- Valid, physics and one-piece shares: over all candidates.
- Everything else: over the valid builds.
- Object fill and IoU: against the target.
- Size-matched judge: M10's judge (`style.size_matched` against the real set, the set's v2 fold statistics, as in
  phase 1).
- Distance to the set: from the set's own statistics; lower is closer.
- Outside vocab: placed parts outside the model's vocabulary.
- Seconds per candidate: generation plus physics, with 10 candidates built at once.

## Results

| set | arm | candidates | valid % | physics % | one piece % | object fill % (sd) | IoU | utilization % | size-matched judge (sd) | real ceiling | distance to set | parts | outside vocab / build | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 7796-1 | stats_random | 20 | 100 | 100 | 100 | 58.1 (5.0) | 0.581 | 82.1 | -0.4880 (0.0228) | -0.4786 | 0.2980 | 46 | 1.8 | 1.9 |
| 7796-1 | stats_raster | 20 | 100 | 100 | 100 | 58.3 (5.1) | 0.583 | 82.0 | -0.4952 (0.0202) | -0.4808 | 0.3182 | 46 | 1.6 | 1.8 |
| 7796-1 | proposal_raster | 20 | 100 | 100 | 100 | 58.7 (5.7) | 0.587 | 83.4 | -0.5067 (0.0218) | -0.4805 | 0.3258 | 47 | 1.7 | 38.0 |
| 6370-1 | stats_random | 20 | 100 | 100 | 100 | 66.1 (3.2) | 0.661 | 82.9 | -0.3813 (0.0124) | -0.3826 | 0.4417 | 107 | 13.9 | 11.1 |
| 6370-1 | stats_raster | 20 | 100 | 100 | 100 | 67.3 (5.0) | 0.673 | 83.8 | -0.3709 (0.0118) | -0.3826 | 0.4296 | 108 | 15.1 | 14.2 |
| 6370-1 | proposal_raster | 20 | 100 | 100 | 100 | 64.1 (5.7) | 0.641 | 82.2 | -0.3613 (0.0128) | -0.3826 | 0.4153 | 106 | 13.4 | 63.4 |
| 7743-1 | stats_random | 20 | 100 | 100 | 100 | 73.4 (3.1) | 0.734 | 78.7 | -0.3982 (0.0120) | -0.4231 | 0.4006 | 236 | 20.8 | 8.9 |
| 7743-1 | stats_raster | 20 | 100 | 100 | 100 | 76.2 (2.7) | 0.762 | 78.4 | -0.3876 (0.0138) | -0.4231 | 0.3927 | 235 | 19.4 | 8.2 |
| 7743-1 | proposal_raster | 20 | 100 | 100 | 100 | 74.8 (3.3) | 0.748 | 76.3 | -0.3662 (0.0124) | -0.4231 | 0.3955 | 229 | 20.0 | 66.5 |

The sds are over the 20 candidates. The standard error of a difference between two arms is about
sqrt(sd1^2 + sd2^2) / sqrt(20).

| comparison | size-matched judge | object fill | distance to set (lower is closer) |
|---|---|---|---|
| proposal_raster vs stats_raster | higher on 2/3 sets, mean +0.0065 | higher on 1/3, mean -1.35 points | closer on 1/3, mean -0.0013 |
| proposal_raster vs stats_random | higher on 2/3, mean +0.0111 | higher on 2/3, mean +0.03 points | closer on 2/3, mean -0.0013 |
| stats_raster vs stats_random | higher on 2/3, mean +0.0046 | higher on 3/3, mean +1.38 points | closer on 2/3, mean +0.0001 |

**Fill.** Raster order alone raises fill on all three sets (+1.4 points on average). Adding the model takes part of
that back:

- 6370-1: 64.1% against 67.3%;
- 7743-1: 74.8% against 76.2%, with lower utilization (76.3% against 78.4%) and 6 fewer parts per build;
- 7796-1: no difference.

So the model does not help the builder fill the target; if anything it makes it a little worse.

**Judge.** On the two larger sets the model's builds score higher than both statistics arms.

| set | difference against the control | standard errors |
|---|---|---|
| 6370-1 | +0.0096 | about 2.5 |
| 7743-1 | +0.0214 | about 5 |
| 7796-1 (46 parts) | -0.0115 | about 1.7 |

On 7743-1 every arm scores above the real set's own size-matched judge (the "real ceiling"), so a higher score there
is not "closer to the real set".

**Distance to the set's own statistics** is the judge-free check that settled phase 1.

- **6370-1:** the model's builds are the closest of the three arms (0.415 against 0.430 for the control), which
  supports its judge win.
- **7743-1:** they are slightly farther than the control (0.3955 against 0.3927), so the judge win there is not
  confirmed.
- **7796-1:** they are the farthest, as their judge says.

**The vocabulary handicap is small here.** The car target leaves room for fewer of the parts the model lacks: 1.6 to
20.8 per build, about the same in every arm.

**Cost.** One model query per visited cell, repeated in each connect round. The model's candidates take 38 s
(7796-1) to 66 s (7743-1), against 2-14 s for the statistics. That is 20x on the smallest set and 4-8x on the
others.

## Compared with phase 1 (box grids, no target)

|  | box (7 sets, 5 seeds) | car target (3 sets, 20 candidates) |
|---|---|---|
| judge, model vs raster control | higher on 1/7, mean -0.0025 | higher on 2/3, mean +0.0065 |
| judge-free distance, model vs control | closer on 2/7 | closer on 1/3 |
| fill | does not apply | lower on 2/3, mean -1.35 points |

The model was trained mostly on BrickGPT structures, which always come with their shape. It helps the judge more
when it gets a shape, but it does not fill the shape better.

## Caveats

- **One object** (the car), three small sets, 20 candidates each. The sets are the smallest of fold 0 because of
  the model's cost.
- **The judge favors the statistics arms by construction** (see phase 1). A win under it counts for the model, but
  the judge-free distance confirms it on one set of three.
- **The model is run 2:** the early, set-validated checkpoint, with the 107-shape vocabulary.
- **The proposal strength** is 1 throughout, with no tuning.

## Figure

`results/m12b_proposal_shape.png`: 6370-1, seed 0 (the first seed valid in all three arms), one build per arm, left
to right stats_random, stats_raster, proposal_raster. The labels give each arm's mean fill and judge. The set was
chosen before the results, to match phase 1's figure.
