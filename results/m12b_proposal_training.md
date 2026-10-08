# M12b step 2: training the learned proposal model (local GPU, 2026-10-09)

Two runs of `training/train.py` on the token data of `results/m12b_tokens.md`. The weights are in `data/models/`
(gitignored): `proposal_run1.npz`, `proposal_run2.npz`, the shared `vocab.json`, and each run's log as
`proposal_run{1,2}_log.jsonl`.

**Use `proposal_run2.npz` for the comparison** (`experiments/proposal.py`). The reason, and the rule it departs
from, are in the last section.

## Setup

**Hardware and software**

- GPU: NVIDIA GeForce RTX 3060 Laptop, 6 GB, driver 596.36.
- PyTorch 2.6.0+cu124 in a throwaway venv, not a project dependency.
- Mixed precision (fp16 autocast with a gradient scaler).
- One data process; the CPU was shared with other experiments.

**Model** (the notebook's defaults)

- Decoder-only transformer: 6 layers, d 256, 8 heads, context 1024.
- 5.16M parameters; the exported `.npz` is 20.7 MB.

**Optimization**

- AdamW, peak learning rate 5e-4, 300 warmup steps, cosine schedule to 10% over `--steps 7000`.
- Weight decay 0.1. 20% of windows have no target mask.

**Batch size: 64 windows (up to 65,536 tokens).** Benchmark, GPU part only, 30 steps each:

| batch | s/step | peak GPU memory |
|---|---|---|
| 32 | 0.13 | 2.0 GiB |
| 48 | 0.20 | 3.0 GiB |
| 64 | 0.26 | 3.9 GiB |
| 96 | 5.3 (spills into shared memory) | 5.8 GiB |

With data sampling on one CPU process, a full step takes 0.46 s.

**Evaluation**, every 500 steps:

- **val**: 430 windows of 400 BrickGPT test structures. These are colorless, so their color loss is ~0.
- **set-val** (run 2 only): every symmetry of two training sets held out of training. These are 6378-1 and 31048-1,
  ranks 10 and 11 of the 21 training sets by size (164 and 166 parts; 31048-1 is the median). That gives 16 windows.
- **held-out sets**: fold 0, the 7 test sets of the comparison, 36 windows. Reported only, never used for selection.

Loss is mean cross-entropy per target token (nats). For reference, a uniform guess over the 107 shape tokens scores
ln 107 = 4.67.

## Run 1: `--set-share 0.25` (the briefed defaults), selection on BrickGPT val

7000 steps in 55.4 minutes. Selected: step 7000 (val 0.3356).

| step | minutes | train | val (BrickGPT test) | val shape | val color | held-out sets | held-out shape | held-out color |
|---|---|---|---|---|---|---|---|---|
| 500 | 3.8 | 1.190 | 0.9836 | 1.786 | 0.000 | 2.7137 | 3.488 | 3.773 |
| 1000 | 7.7 | 0.713 | 0.6761 | 1.589 | 0.000 | 3.1313 | 4.196 | 4.987 |
| 1500 | 11.8 | 0.471 | 0.5949 | 1.480 | 0.000 | 3.7478 | 5.486 | 5.464 |
| 2000 | 15.7 | 0.388 | 0.5435 | 1.405 | 0.000 | 4.2468 | 6.295 | 5.848 |
| 2500 | 19.6 | 0.352 | 0.4936 | 1.321 | 0.000 | 4.5070 | 6.852 | 5.908 |
| 3000 | 23.5 | 0.291 | 0.4596 | 1.251 | 0.000 | 4.7982 | 7.244 | 6.261 |
| 3500 | 27.4 | 0.291 | 0.4231 | 1.183 | 0.000 | 4.9346 | 7.514 | 6.355 |
| 4000 | 31.4 | 0.259 | 0.3993 | 1.136 | 0.000 | 5.1226 | 7.753 | 6.534 |
| 4500 | 35.5 | 0.220 | 0.3770 | 1.091 | 0.000 | 5.3279 | 8.095 | 6.655 |
| 5000 | 39.8 | 0.242 | 0.3599 | 1.063 | 0.000 | 5.4380 | 8.362 | 6.840 |
| 5500 | 43.7 | 0.225 | 0.3508 | 1.041 | 0.000 | 5.5869 | 8.561 | 7.019 |
| 6000 | 47.6 | 0.200 | 0.3452 | 1.031 | 0.000 | 5.6668 | 8.586 | 7.212 |
| 6500 | 51.5 | 0.204 | 0.3376 | 1.016 | 0.000 | 5.7499 | 8.696 | 7.386 |
| 7000 | 55.4 | 0.165 | 0.3356 | 1.010 | 0.000 | 5.7991 | 8.775 | 7.454 |

**The model learns BrickGPT's structures but memorizes the real sets.**

- BrickGPT validation falls throughout, from 0.98 to 0.34.
- The loss on the unseen real sets rises from step 500 on, from 2.71 to 5.80.
- Its held-out shape loss (8.78) is far worse than a uniform guess (4.67): on real sets the model is confidently
  wrong.
- The cause: the 21 training sets (168 symmetry sequences, 1.5% of the training parts) are drawn 25% of the time,
  16x their natural share, so the model sees each set's windows dozens of times.
- Selection on BrickGPT val cannot see this.

## Run 2: `--set-share 0.05 --val-sets 6378-1 31048-1`, selection on mean(val, set-val)

Stopped at step 3000 of 7000 (23.9 minutes): early stopping on its own selection loss, which had risen for three
evaluations in a row after step 1500. Selected: step 1500 (selection 1.3510: val 0.5518, set-val 2.1502).

| step | minutes | train | val (BrickGPT test) | val shape | val color | set-val | set-val shape | set-val color | held-out sets | held-out shape | held-out color |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 500 | 3.9 | 1.046 | 0.9820 | 1.798 | 0.000 | 2.3776 | 3.913 | 1.769 | 2.7524 | 3.651 | 3.544 |
| 1000 | 7.9 | 0.806 | 0.6480 | 1.550 | 0.000 | 2.1690 | 3.653 | 1.744 | 2.5664 | 3.283 | 3.642 |
| **1500** | 11.8 | 0.700 | 0.5518 | 1.413 | 0.000 | 2.1502 | 3.655 | 1.885 | 2.6816 | 3.279 | 4.106 |
| 2000 | 15.9 | 0.493 | 0.4793 | 1.289 | 0.000 | 2.3242 | 4.051 | 2.212 | 2.7455 | 3.454 | 4.138 |
| 2500 | 19.9 | 0.473 | 0.4291 | 1.183 | 0.000 | 2.4531 | 4.334 | 2.382 | 2.7766 | 3.611 | 4.384 |
| 3000 | 23.9 | 0.397 | 0.3927 | 1.101 | 0.000 | 2.6416 | 4.898 | 2.395 | 2.9471 | 3.932 | 4.507 |

- With a fifth of run 1's set share, the held-out sets stay near their early level: 2.68 at the selected step, against
  5.80 for run 1.
- Shape is predicted better than uniform on unseen sets (3.28 vs 4.67).
- The set-validation loss turns up after step 1500, so the real-set side still overfits, only later and more slowly.
- The selected checkpoint is early in the cosine schedule (learning rate still high), which costs it on BrickGPT:
  val 0.55 against run 1's 0.34.

## Parity and decoding

- **Parity** (`training/parity.py check`, numpy inference against PyTorch on the trained weights, full pass and
  token by token through the key/value cache, 4 val windows):
  - run 1: max difference 1.8e-4;
  - run 2: max difference 1.0e-4;
  - tolerance 2e-3; **parity OK** for both.
- **Smoke run** of the comparison driver with the real models: `experiments/proposal.py --sets 7796-1 --seeds 1
  --workers 1`, one small held-out set (49 parts). The point is that decoding works end to end; one set and one seed
  say nothing about quality.

| model | condition | valid % | utilization % | size-matched judge | s/build |
|---|---|---|---|---|---|
| none | stats_random | 100 | 95.9 | -0.4490 | 0.10 |
| none | stats_raster | 100 | 95.9 | -0.4563 | 0.08 |
| run 1 | proposal_raster | 100 | 95.9 | -0.4537 | 1.79 |
| run 2 | proposal_raster | 100 | 95.9 | -0.4601 | 1.44 |

The model costs about 1.5 s per build on this 49-part set: one query per visited cell, two forward calls of about
3 ms each. It
grows with the number of visited cells, so larger sets take proportionally longer.

## Which model the comparison should use

**Run 2.** The rule agreed beforehand was "run 2 unless its BrickGPT val is clearly worse", and it is clearly worse:
0.55 against 0.34. We recommend run 2 anyway.

- **The comparison runs on real-set inventories**: fold 0's sets, decoded as `SRC_set`.
- **There, run 1 is worse than uniform**: held-out shape loss 8.78 against 4.67, so its proposal would push the
  builder toward wrong parts.
- **Run 2 is the model that predicts unseen real sets**: held-out loss 2.68, shape 3.28.
- **BrickGPT validation measures something the comparison does not use.**

Run 1 stays in `data/models/` as the BrickGPT-style baseline. Its overfitting table is a result in itself: real-set
data must be oversampled far less, and selected on held-out training sets.

A next run could keep run 2's selection and lower the learning rate on the set side, or give it more set data.
Options: more symmetries, or the Rebrickable inventories of other sets (no geometry, so not as sequences). Another
option is to anneal the schedule to the step where set-val turns up (about 1500 at this batch size), so the selected
checkpoint is also well fitted on BrickGPT.
