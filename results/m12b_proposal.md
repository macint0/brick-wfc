# M12b step 2: learned proposal vs statistics (2026-10-09)

The learned proposal model (`data/models/proposal_run2.npz`, see `results/m12b_proposal_training.md`) against the
M10 statistics, decoded by the same bottom-up builder on the sets held out of the model's training. Statistics stay
the no-training baseline in every table. Summary numbers: `results/m12b_proposal_summary.json`; figure:
`results/m12b_proposal_before_after.png`.

**Verdict: the proposal loses narrowly to statistics under the judge.**

- With the visiting order fixed (raster), adding the model gives a higher size-matched judge on **1 of 7 sets**.
  The mean difference is **-0.0025**.
- The proposal does beat M10's builder (random order) on 6 of 7 sets (+0.0128). But raster order alone does that
  too (5 of 7, +0.0153), so the gain is the order's, not the model's.
- Every build of every arm is valid. The model costs about 7x the build time.

## Setup

**Code and command.** Main at 03f290c. Each set ran as its own invocation, smallest first, all into one output
folder, then one invocation without `--sets` for the summary (commands in `docs/reproduce.md`). 10 worker
processes; nothing else ran on the machine. 105 builds in about 7 minutes of wall time.

**Builds.** M10's `D2_inventory` setup (`experiments.style.setup`):

- the bottom-up builder (any offset) with exactly the set's parts and the learned contact style;
- a box grid 12 plates tall with 1.5x the inventory's volume;
- no target shape, so **fill does not apply**: this is the inventory-only comparison;
- no connect or balance pass; valid means whole parts, every part supported, nothing over the inventory.

**Conditions** (5 seeds each, seeds 0-4, the same seeds in every arm):

| condition | proposal | order cells are visited in a layer |
|---|---|---|
| stats_random | statistics only (M10's builder) | random |
| stats_raster | statistics only: the control for the order | raster |
| proposal_raster | statistics x the model's weights, strength 1 | raster |

**Statistics: v2.** `results/m10_style_stats/style_fold0_v2.json`, relearned with corners and slopes. It is used
both for the style bias and for the judge (`--style-version v2`, the driver's default).

**Sets: fold 0 of M10's 4-fold split**, the 7 sets neither the statistics nor the model trained on: 7796-1, 6370-1,
7743-1, 5891-1, 10264-1, 10243-1, 10197-1. Checked in the token data:

- `data/tokens/train.npz` holds 168 set sequences: the 21 sets of folds 1-3, 8 symmetries each. No fold-0 set.
- `heldout.npz` is exactly the 7 fold-0 sets.
- 6378-1 and 31048-1, run 2's set-validation sets, are fold 1-3 sets. They were held out of run 2's sampling and
  used only to select its checkpoint. Neither is in the comparison.

**Judge.** The M10 judge: the negative divergence of a build's contact statistics from the learned statistics,
size-matched to the real model (`style.size_matched`); higher is better. "Real ceiling" is the real set's own
size-matched judge.

## The model's vocabulary is a handicap

The model was trained before the catalog gained corners, slopes and brick1x2_4216. Its vocabulary has 107 shapes;
the catalog now has 190. How the builder handles parts outside the vocabulary:

- **Proposal arm:** such parts get the uniform shape probability (1/107) instead of a learned one. When placed, they
  are left out of the model's context (`Session.add` skips them).
- **Statistics arms:** they have learned v2 statistics for every part.

Parts outside the model's vocabulary, per set:

| set | parts in inventory | outside the model's vocabulary | share % |
|---|---|---|---|
| 7796-1 | 56 | 7 | 12 |
| 6370-1 | 128 | 35 | 27 |
| 7743-1 | 153 | 8 | 5 |
| 5891-1 | 414 | 124 | 30 |
| 10264-1 | 892 | 44 | 5 |
| 10243-1 | 1209 | 74 | 6 |
| 10197-1 | 1241 | 160 | 13 |

Placed parts outside the vocabulary per build are in the "outside vocab / build" column below, per set and arm. Every
arm uses 96-100% of the inventory, so every arm places nearly all of these parts: 64 per build on average for each
arm.

**The handicap does not explain the result.** 7743-1 and 10264-1 both have 5% of their parts outside the vocabulary.
The proposal's only clear win is on the first; its clearest loss is on the second.

## Results

Means over the 7 sets:

| condition | sets | builds | valid % | utilization % | size-matched judge | outside vocab / build | s/build |
|---|---|---|---|---|---|---|---|
| stats_random | 7 | 35 | 100 | 99.1 | -0.3573 | 64.2 | 6.58 |
| stats_raster | 7 | 35 | 100 | 99.2 | -0.3420 | 64.5 | 6.83 |
| proposal_raster | 7 | 35 | 100 | 99.0 | -0.3445 | 64.1 | 46.60 |

Paired over sets (mean of the 5 seeds per set):

- proposal_raster has the higher size-matched judge than stats_raster on **1/7** sets (mean difference -0.0025)
- proposal_raster has the higher size-matched judge than stats_random on 6/7 sets (mean difference +0.0128)
- stats_raster has the higher size-matched judge than stats_random on 5/7 sets (mean difference +0.0153)

Per set and condition. The sd is over the 5 seeds. Seconds are build time while 10 builds ran at once.

| set | condition | builds | valid % | utilization % | size-matched judge (sd) | real ceiling | distance to set | outside vocab / build | s/build |
|---|---|---|---|---|---|---|---|---|---|
| 7796-1 | stats_random | 5 | 100 | 96.4 | -0.4840 (0.0225) | -0.4755 | 0.2639 | 7.0 | 0.21 |
| 7796-1 | stats_raster | 5 | 100 | 96.1 | -0.4783 (0.0184) | -0.4750 | 0.2988 | 7.0 | 0.20 |
| 7796-1 | proposal_raster | 5 | 100 | 96.1 | -0.4810 (0.0168) | -0.4770 | 0.3422 | 6.8 | 3.64 |
| 6370-1 | stats_random | 5 | 100 | 99.5 | -0.3852 (0.0145) | -0.3826 | 0.4224 | 34.8 | 1.46 |
| 6370-1 | stats_raster | 5 | 100 | 99.8 | -0.3855 (0.0184) | -0.3826 | 0.4274 | 35.0 | 1.65 |
| 6370-1 | proposal_raster | 5 | 100 | 99.5 | -0.3888 (0.0087) | -0.3826 | 0.4281 | 34.4 | 12.17 |
| 7743-1 | stats_random | 5 | 100 | 98.7 | -0.3729 (0.0095) | -0.4231 | 0.3926 | 8.0 | 0.98 |
| 7743-1 | stats_raster | 5 | 100 | 98.7 | -0.3823 (0.0115) | -0.4231 | 0.3746 | 8.0 | 1.37 |
| 7743-1 | proposal_raster | 5 | 100 | 98.7 | -0.3508 (0.0114) | -0.4231 | 0.3625 | 8.0 | 12.60 |
| 5891-1 | stats_random | 5 | 100 | 99.5 | -0.3698 (0.0036) | -0.2769 | 0.3217 | 121.8 | 7.47 |
| 5891-1 | stats_raster | 5 | 100 | 99.9 | -0.3565 (0.0105) | -0.2769 | 0.3030 | 123.4 | 8.59 |
| 5891-1 | proposal_raster | 5 | 100 | 99.8 | -0.3680 (0.0147) | -0.2769 | 0.3133 | 123.2 | 36.41 |
| 10264-1 | stats_random | 5 | 100 | 100.0 | -0.3173 (0.0059) | -0.2311 | 0.3181 | 44.0 | 8.19 |
| 10264-1 | stats_raster | 5 | 100 | 100.0 | -0.2661 (0.0049) | -0.2311 | 0.2602 | 44.0 | 7.71 |
| 10264-1 | proposal_raster | 5 | 100 | 100.0 | -0.2895 (0.0090) | -0.2311 | 0.2701 | 44.0 | 78.48 |
| 10243-1 | stats_random | 5 | 100 | 99.8 | -0.3086 (0.0056) | -0.2102 | 0.2753 | 74.0 | 10.15 |
| 10243-1 | stats_raster | 5 | 100 | 99.9 | -0.2787 (0.0064) | -0.2102 | 0.2589 | 74.0 | 9.41 |
| 10243-1 | proposal_raster | 5 | 100 | 99.0 | -0.2836 (0.0113) | -0.2102 | 0.2919 | 72.6 | 78.72 |
| 10197-1 | stats_random | 5 | 100 | 100.0 | -0.2631 (0.0015) | -0.2079 | 0.2926 | 160.0 | 17.59 |
| 10197-1 | stats_raster | 5 | 100 | 100.0 | -0.2468 (0.0054) | -0.2079 | 0.2790 | 160.0 | 18.85 |
| 10197-1 | proposal_raster | 5 | 100 | 100.0 | -0.2497 (0.0096) | -0.2079 | 0.2723 | 160.0 | 104.18 |

**Valid and utilization.** Every build of every arm is valid, and each arm uses 96-100% of its inventory. So the
arms build with nearly the same parts, and the judge differences come from how the parts are arranged.

**Order.** Raster order beats random order on 5 of 7 sets. The gains are largest on the large sets: +0.051 on
10264-1 and +0.030 on 10243-1. M10's builder visits cells in random order, so part of any gain over M10 is the order's.

**Proposal vs the raster control: no gain.**

- **Its one win, 7743-1:** +0.0315, about 3 seed sds.
- **Its one clear loss, 10264-1:** -0.0234, about 5 sds.
- **The other five sets:** small losses, each within about one sd (-0.003 to -0.012).

**Distance to the held-out set's own statistics** is a check that does not use the learned statistics (lower is
closer). Means: stats_raster 0.3146, proposal_raster 0.3258, stats_random 0.3266. The proposal is closer than the
raster control on 2 of 7 sets (10197-1, 7743-1). This agrees with the judge.

**Cost.** The proposal takes 46.6 s per build against 6.8 s for statistics, about 7x. It reaches 104 s per build on
10197-1 (1241 parts). That is one query of the model per visited cell: two forward steps, each with key/value cache.

## Caveats

- **The judge favors the statistics arms by construction.** It measures the divergence from the same learned
  statistics that steer those arms. Any departure the model makes from them is scored as a loss, even when it moves
  toward the real set. The distance to the held-out set's own statistics avoids this, and it gives the same answer.
- **Five seeds per set** and no significance test. The per-set differences are reported with the seed sd.
- **The model is run 2:** selected at step 1500 for real-set validation, early in its learning-rate schedule, and
  trained with the 107-shape vocabulary.
- **No target shape:** box grids only. A target shape, and the mask prefix the model was trained with, is phase 2.

## Figure

`results/m12b_proposal_before_after.png`: 6370-1, seed 0, one build per condition (left to right: stats_random,
stats_raster, proposal_raster). I chose this set before the full results were in: a small set where 27% of the parts
are outside the model's vocabulary. Each panel is drawn from its logged parts.

## Determinism

`experiments/proposal_report.py --spot-check 6` rebuilt six logged builds from their seeds with the driver's
`run_job`: 7796-1, seeds 0 and 1, all three conditions. All six were identical to the logged ones, in parts and in
judge.
