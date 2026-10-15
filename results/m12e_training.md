# M12e: proposal model v2 trained on the OMR pool (Colab A100, 2026-10-16)

Plan and evaluation rules: `results/m12e_training_plan.md`. Data: `data/tokens_v2` (catalog fingerprint `475df2114737`,
183 parts; 835 tokens; real sets 16.6% of training parts). Trained from the main checkout at 921ad1d through the Colab
CLI (`colab` in WSL, session on an **A100-SXM4 40 GB**, torch 2.11 cu130): the source (`pyproject.toml`, `src`,
`training`) and the token files were uploaded to the VM directly, so no Drive copy, GitHub token or push was needed;
`training/colab_v2.ipynb` does the same through the browser. Every run: batch 64, AdamW, cosine schedule, fp16 autocast,
`--mask-drop 0.2`, seed 0, evaluation every 1,000 steps, early stop with patience 5 on the selection loss
(mean of BrickGPT val and the pool's `setval`). Weights, `vocab.json`, `log.jsonl`, `train.log` and the parity log of
each run are under `data/models/proposal_v2_<run>/` (gitignored); numpy inference matches PyTorch on every run
(`training/parity.py check`, max |numpy − torch| 1.3e-4 against a tolerance of 2e-3).

## The planned runs

| run | params | s/step | stopped at | minutes | best step (select) | select | BrickGPT val | setval | heldout | heldout shape | heldout colour |
|---|---|---|---|---|---|---|---|---|---|---|---|
| smoke (d128, 2 layers) | 0.65M | 0.014 | 300 (cap) | 0.2 | 300 | 2.489 | 1.625 | 3.352 | 2.961 | 4.709 | 2.754 |
| base (d256, 6 layers) | 5.25M | 0.056 | 10,000 (early stop) | 9.0 | 5,000 | 1.056 | 0.348 | 1.764 | 1.744 | 3.580 | 1.961 |
| scaled (d512, 8 layers) | 26.2M | 0.121 | 8,000 (early stop) | 16.5 | 3,000 | 0.917 | 0.301 | 1.533 | 1.378 | 3.219 | 0.967 |

The A100 is 5–10× faster per step than the plan's guesses (which were made from the RTX 3060), and both runs ended
long before their step caps: **the real-set loss turns up after 3,000–5,000 steps while the BrickGPT loss is still
falling.** Full curves (`log.jsonl`):

| base step | train | val | setval | select | heldout | h. shape | h. colour |
|---|---|---|---|---|---|---|---|
| 1,000 | 0.962 | 0.719 | 2.116 | 1.417 | 1.928 | 3.915 | 1.433 |
| 2,000 | 0.687 | 0.539 | 1.802 | 1.171 | 1.737 | 3.675 | 1.398 |
| 3,000 | 0.675 | 0.448 | 1.743 | 1.095 | **1.701** | 3.664 | 1.385 |
| 4,000 | 0.638 | 0.395 | **1.740** | 1.068 | 1.710 | 3.581 | 1.719 |
| 5,000 | 0.487 | 0.348 | 1.764 | **1.056** | 1.744 | 3.580 | 1.961 |
| 6,000 | 0.480 | 0.328 | 1.815 | 1.072 | 1.796 | 3.636 | 2.163 |
| 8,000 | 0.481 | 0.298 | 1.935 | 1.117 | 1.860 | 3.861 | 2.204 |
| 10,000 | 0.410 | 0.283 | 2.069 | 1.176 | 1.997 | 4.058 | 2.701 |

| scaled step | train | val | setval | select | heldout | h. shape | h. colour |
|---|---|---|---|---|---|---|---|
| 1,000 | 0.859 | 0.631 | 2.029 | 1.330 | 1.874 | 3.923 | 1.517 |
| 2,000 | 0.497 | 0.373 | 1.610 | 0.992 | 1.445 | 3.282 | 0.978 |
| 3,000 | 0.474 | 0.301 | **1.533** | **0.917** | **1.378** | 3.219 | 0.967 |
| 4,000 | 0.418 | 0.271 | 1.612 | 0.941 | 1.430 | 3.354 | 1.140 |
| 5,000 | 0.294 | 0.262 | 1.754 | 1.008 | 1.594 | 3.806 | 1.339 |
| 6,000 | 0.261 | 0.259 | 1.845 | 1.052 | 1.692 | 4.001 | 1.552 |
| 8,000 | 0.238 | 0.277 | 2.182 | 1.229 | 2.022 | 4.949 | 1.734 |

**Diagnosis: the model memorizes the real sets.** The 4,408 real training sequences are 551 distinct models in 8
symmetries, with absolute Y/Z/X tokens, and nothing in `train.py` regularizes beyond weight decay 0.1 (no dropout, no
positional jitter). At batch 64 and a 16.6% real-set share the model has seen every real window about three times by
step 3,000. The BrickGPT split (42,604 sequences) never overfits in this range. The same thing happened in M12b run 1 at
a 16× oversampling; the pool made it later, not absent. Scaled's held-out shape loss at step 8,000 (4.95) is *worse*
than the real-set unigram reference (4.68 below): past its best step the larger model is worse than guessing frequencies
on an unseen set.

## Stage 1: held-out loss against the references

References computed from the token data (`train.npz` unigram per field, with 0.5 smoothing; "real-set unigram" uses
only the training rows from real sets, which is the stronger reference for the real-set splits; uniform is ln of the
field's token count in the training data). Per-field cross-entropies in nats, mean over part tokens.

| field | uniform | setval: unigram (all / real) | setval: base @5k | setval: scaled @3k | heldout: unigram (all / real) | heldout: base @5k | heldout: scaled @3k |
|---|---|---|---|---|---|---|---|
| Y | 4.96 | 5.37 / 4.44 | 0.51 | 0.57 | 4.34 / 3.67 | 0.40 | 0.35 |
| Z | 4.16 | 4.20 / 3.66 | 1.17 | 1.04 | 3.61 / 3.39 | 1.19 | 1.03 |
| X | 4.16 | 3.92 / 3.53 | 2.06 | 1.89 | 3.19 / 3.26 | 1.60 | 1.33 |
| shape | 6.04 | 6.09 / 4.96 | 3.56 | 3.20 | 5.78 / 4.68 | 3.58 | 3.22 |
| colour | 4.33 | 4.46 / 2.67 | 1.53 | 0.96 | 4.66 / 2.86 | 1.96 | 0.97 |

(Per-field values at the selected step from `log.jsonl`; the loss columns in the run table are their means over the
five fields.)

**Stage 1 passes for both models:** on the held-out demo sets, shape and colour are below the real-set unigram
reference (base: 3.58 vs 4.68 and 1.96 vs 2.86; scaled: 3.22 vs 4.68 and 0.97 vs 2.86). Scaled is better than base on
every field on both real-set splits, and twice as good on colour (0.97 vs 1.96 nats on the demo sets). Size helps, and
overfits faster.

**M12b run 2** (5.16M, 1,500 steps on 21 sets, 88-part vocabulary) is not comparable on loss (different token set);
it meets v2 in stage 2 on builds.

## Regularization sweep (flags only, no code change)

Run right after the planned runs on the same VM, same settings, base size unless noted: the real-set share of the
training windows (`--set-share`) and weight decay (`--weight-decay`), to see how far the overfit can be pushed back
without new code. The dropout and positional-jitter options are session B's work and are trained after this sweep.

Values at the selected step (best selection loss); the last two columns give each run's real-set minima wherever they fell.
Every run: parity OK.

| run | stopped at | min | best step | select | BrickGPT val | setval | heldout | h. shape | h. colour | setval min (step) | heldout min (step) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| base, share 0.166, wd 0.1 (planned) | 10,000 | 9 | 5,000 | 1.056 | 0.348 | 1.764 | 1.744 | 3.58 | 1.96 | 1.740 (4,000) | 1.701 (3,000) |
| base, share 0.10 | 12,000 | 11 | 7,000 | 1.007 | 0.300 | 1.713 | 1.675 | 3.42 | 1.97 | 1.705 (6,000) | 1.559 (6,000) |
| base, share 0.05 | 15,000 | 14 | 10,000 | 0.988 | 0.266 | 1.710 | 1.535 | 3.38 | 1.29 | 1.710 (10,000) | 1.535 (10,000) |
| base, wd 0.3 | 11,000 | 10 | 6,000 | 1.036 | 0.325 | 1.747 | 1.642 | 3.49 | 1.79 | 1.721 (4,000) | 1.642 (6,000) |
| base, share 0.05, wd 0.3 | 19,000 | 17 | 14,000 | **0.956** | 0.232 | **1.679** | 1.556 | 3.34 | 1.57 | 1.676 (10,000) | 1.536 (15,000) |
| scaled, share 0.166 (planned) | 8,000 | 16 | 3,000 | 0.917 | 0.301 | **1.533** | 1.378 | 3.22 | **0.97** | 1.533 (3,000) | 1.378 (3,000) |
| scaled, share 0.05 | 11,000 | 23 | 6,000 | 0.921 | 0.251 | 1.592 | **1.356** | **3.12** | 1.00 | 1.592 (6,000) | 1.356 (6,000) |

**Reading.** The real-set share sets *when* the overfit starts, not the floor it reaches. At base size the real-set
validation loss bottoms at 1.68–1.76 whatever the share (0.166 → 0.05 moves the minimum from step 4,000 to 10,000 and
improves it by 0.03), and weight decay 0.3 adds another 0.03; the larger gains at the low share are on the BrickGPT
split (0.348 → 0.232), which simply gets more of the batches, and on the held-out demo sets (1.74 → 1.54), where the
demo sets' colour loss falls (1.96 → 1.29). Capacity lowers the floor: scaled reaches 1.53 on `setval` at the natural
share, 0.15 below any base run, and the two scaled runs tie on the demo sets (1.38 vs 1.36). Diluting the real sets
therefore costs real-set loss at the large size (1.533 → 1.592) while buying nothing on the demo sets. What the sweep
cannot do is let the model keep learning from the real sets past a few passes; that needs regularization that changes
each visit (translation jitter) and dropout, which `train.py` gained on branch `m12e-reg` (merged e3b1a21) and which
the runs below test.

## Regularized runs (dropout + translation jitter on both sources)

`train.py` from `m12e-reg` (e3b1a21): `--dropout p --jitter set brickgpt`, otherwise the planned settings; the selection
stays the mean of the two validation losses, and the weights at the `setval` minimum are exported too
(`proposal_setval.npz`). Both files pass parity on every run. Values at the selected step; the last columns give the
real-set minima and the demo-set shape / colour loss at the demo-set minimum.

| run | stopped at | min | best step | select | BrickGPT val | setval | heldout | h. shape | h. colour | setval min (step) | heldout min (step) | h. shape / colour there |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base, share 0.166, dropout 0.1 | 24,000 | 23 | 19,000 | 0.776 | 0.242 | 1.311 | 1.404 | 3.17 | 1.67 | 1.301 (15,000) | 1.321 (18,000) | 3.09 / 1.35 |
| base, share 0.05, dropout 0.1 | 40,000 (cap) | 40 | 37,000 | 0.708 | 0.157 | 1.259 | **1.099** | **2.68** | **0.75** | 1.259 (37,000) | 1.092 (39,000) | 2.66 / 0.75 |
| scaled, share 0.166, dropout 0.1 | 11,000 | 24 | 6,000 | 0.784 | 0.254 | 1.313 | 1.253 | 2.93 | 1.03 | 1.313 (6,000) | 1.253 (6,000) | 2.93 / 1.03 |
| scaled, share 0.166, dropout 0.2 | 16,000 | 34 | 11,000 | 0.771 | 0.225 | 1.317 | 1.321 | 3.06 | 1.43 | 1.295 (7,000) | 1.246 (6,000) | 2.90 / 0.90 |
| scaled, share 0.05, dropout 0.1 | 26,000 | 57 | 21,000 | **0.697** | 0.155 | **1.240** | 1.121 | 2.74 | 0.85 | 1.240 (21,000) | 1.085 (16,000) | 2.66 / 0.79 |

Per field at the selected step, the two best runs (nats):

| field | setval: base 0.05 reg | setval: scaled 0.05 reg | heldout: base 0.05 reg | heldout: scaled 0.05 reg | heldout: real-set unigram |
|---|---|---|---|---|---|
| Y | 0.66 | 0.60 | 0.26 | 0.27 | 3.67 |
| Z | 0.84 | 0.78 | 0.81 | 0.78 | 3.39 |
| X | 1.41 | 1.32 | 1.00 | 0.97 | 3.26 |
| shape | 2.62 | 2.64 | 2.68 | 2.74 | 4.68 |
| colour | 0.76 | 0.85 | 0.75 | 0.85 | 2.86 |

**Reading.** Jitter and dropout are the lever the sweep lacked. At the natural share, base's real-set loss falls from
1.74 to 1.30 and scaled's from 1.53 to 1.31, and the runs last 2–3× longer before the overfit; the two sizes now meet at
the same real-set floor (1.30–1.31). With the real-set share at 0.05 on top, both keep improving far longer: base to its
40,000-step cap (still improving at the cap: best step 37,000 of 40), scaled to step 21,000; they end within 0.02 of each
other on `setval` (1.26 / 1.24) and on the demo sets (1.10 / 1.12), with the demo-set colour loss at 0.75–0.85, a third of
the real-set unigram's 2.86 and half the unregularized scaled model's 1.96 → 0.97. Dropout 0.2 instead of 0.1 (scaled,
natural share) buys nothing (1.317 vs 1.313). The demo-set shape loss, 2.66–2.74, is the first below 3 (unregularized
best 3.22). In all, against the planned base model the regularized low-share runs cut the real-set loss by 0.5 nats
(1.76 → 1.24) and the demo-set loss by 0.65 (1.74 → 1.10).

The two demo sets are 4 sequences / 5 windows, so their numbers are noisy; `setval` (23 sets, 69 windows) is the
selection signal and agrees in direction on every comparison above.

## What goes to stage 2

Stage 2 (builds on the demo pairs, the plan's arms and metrics, rendered sheets) runs when Mac says go. The arms
`--proposal` v2 base and v2 scaled of the plan are taken by the two best runs, both regularized at share 0.05:

- **v2 base** = `data/models/proposal_v2_base_reg_ss05/proposal.npz` (5.25M; selected step 37,000; about 6 ms per cell query
  expected, as M12b's model of the same size);
- **v2 scaled** = `data/models/proposal_v2_scaled_reg_ss05/proposal.npz` (26.2M; selected step 21,000; numpy inference
  of a 5× larger model is slower per query, to be measured in stage 2).

The planned unregularized `base` and `scaled` stay as the "data alone" and "size alone" references in the loss tables
and are not built with. The `proposal_setval.npz` files are the same steps on the two chosen runs (the selection and the
real-set minimum coincide), so there is one file per arm. Decision still open and not pre-empted here: whether a loss
0.5 nats lower shows up in the builds' surface, mirror share and colour (the plan's adoption rule).

**Open questions from the night** (not run): a base run past 40,000 steps at share 0.05 (it was still improving at the
cap); more than one seed (every number above is seed 0); jitter on the real sets only (BrickGPT's structures sit at the
origin and may not need it); and whether the colour gain holds on more than two demo sets (`--heldout-sets` with more
of Mac's sets, which re-exports the tokens).

## Cost

| | A100 minutes | compute units |
|---|---|---|
| smoke + base + scaled | 27 | 2.4 |
| flag sweep (5 runs) | 75 | 6.6 |
| regularized runs (5 runs) | 178 | 15.7 |
| idle, parity checks, uploads | about 55 | 5.0 |
| **night total** | **5.6 h** | **29.7** (balance 172.6 → 142.9) |

The A100 session costs 5.3 compute units per hour; it was stopped at 23:31 UTC when the queue ended.
