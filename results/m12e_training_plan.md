# M12e: training plan for proposal model v2 (Colab) and how it is judged

Not trained yet. The M12d catalog has landed (183 parts), and the tokens are exported on it (catalog fingerprint
`475df2114737`), so training can start: Mac runs the notebook on Colab Pro. Data: `results/m12e_omr_pool.md` (the pool:
582 models from 457 sets) and `results/m12e_tokens.md` (the token export: 835 tokens; per-model out-of-vocabulary shares
in `results/m12e_tokens_oov.md`). After any later catalog change, the three PC commands below are rerun before
training; the vocabulary changes with the catalog.

## Checklist

**On the PC** (done for the 183-part catalog; repeat after any catalog change; resumable or deterministic):

1. `python -m brickwfc.ldraw.omr_crawl --out data/omr`: tops up the crawl (only files not on disk are fetched). Optional;
   the OMR changes slowly.
2. `python -m brickwfc.experiments.omr_pool --data data/omr`: measures every model again on the new catalog (cached per
   catalog fingerprint) and rewrites `results/m12e_omr_pool.json` / `.md`. Commit both.
3. `python -m brickwfc.experiments.export_tokens --pool results/m12e_omr_pool.json --out data/tokens_v2 --results
   results/m12e_tokens.md --brickgpt data/brickgpt`: the token data. It refuses a pool measured on another catalog.
   Commit `results/m12e_tokens.md` and `results/m12e_tokens_oov.md`. Add any further demo sets with `--heldout-sets
   6378-1 31048-1 <more>`.
4. Upload `data/tokens_v2/` (vocab.json, export.json, train / val / setval / heldout .npz) to Google Drive as
   `MyDrive/brick-wfc/tokens_v2/`.
5. Push the commit the tokens were exported from (the notebook checks out `BRANCH` and compares catalog fingerprints).

**On Colab** (`training/colab_v2.ipynb`, every cell rerunnable):

1. Runtime: GPU (A100 or L4 on Colab Pro; T4 works with `batch=32`).
2. Secret `GITHUB_TOKEN`: a fine-grained, read-only token for `macint0/brick-wfc` (the repository is private). The
   notebook clones with it and leaves it out of the clone's remote.
3. Run with `CONFIG = 'smoke'` first. It should finish in a few minutes and show a falling loss, a `proposal.npz`, and
   "parity OK".
4. Then run `base`, then `scaled`. After a disconnect, use **Run all** again. Training resumes from
   `MyDrive/brick-wfc/runs/<run>/checkpoint.pt`. Each checkpoint is written next to the old one and swapped in, so a
   disconnect during the write keeps the last good checkpoint.
5. Copy each run folder to `data/models/proposal_v2_<run>/` on the PC (`proposal.npz`, `vocab.json`, `log.jsonl`).
   Record the config, GPU, minutes, best step and loss table in `results/m12e_training.md`.

What the notebook does, in order:

1. Mount Drive and print the GPU.
2. Clone the repository at `BRANCH`.
3. `pip install -e .`. PyTorch is Colab's own CUDA build; cu124 wheels are installed only if torch is missing. torch is
   still not a dependency of the package.
4. Copy the tokens to local disk and assert that `export.json`'s catalog fingerprint equals the checkout's.
5. Run `training/train.py` with the chosen config, the run folder on Drive, and the set share from `export.json`.
6. Run `training/parity.py check` (numpy inference against PyTorch) and print the loss table.

## Configurations

| config | d / layers / heads | parameters | steps (cap) | batch | peak lr / warmup | eval every | early stop | expected time |
|---|---|---|---|---|---|---|---|---|
| smoke | 128 / 2 / 4 | 0.65M | 300 | 16 | 1e-3 / 50 | 100 | off (`--minutes 10`) | a few minutes |
| base | 256 / 6 / 8 | 5.25M (M12b's model) | 40,000 | 64 | 5e-4 / 500 | 1000 | patience 5 | about 0.1–0.25 s/step; early stop expected within 10–20k steps, at most about 1–1.5 h |
| scaled | 512 / 8 / 8 | 26.2M | 60,000 | 64 | 3e-4 / 1000 | 1000 | patience 5 | about 0.3–0.8 s/step; up to several hours to the cap, early stop earlier |

Context is 1024 tokens (196 parts per window), the same as in M12b. All configs use AdamW (betas 0.9 / 0.95, weight
decay 0.1), a cosine schedule to 10% of the peak, fp16 autocast, 20% of windows without a target mask, and seed 0.

**Why these two sizes.** `base` is M12b's run-2 model trained on the pool. Against M12b run 2 it measures the effect of
the data alone. `scaled` is the asked-for ~25M model; against `base` it measures the effect of size on the same data.
The parameter count (12·d² per block) puts d 512 × 8 layers at about 25M.

**Early stopping.** `train.py --patience 5` stops after 5 evaluations (5,000 steps) without a new best selection loss.
The selection loss is the mean of the BrickGPT validation loss and the pool's `setval` loss, as in M12b run 2. The
weights exported are those of the best evaluation. The patience count is saved in the checkpoint, so it survives a
resume. The step caps only stop runs that never stop improving. The cosine schedule is laid out over the cap, so an
early-stopped run ends at a higher learning rate than a run to the cap (M12b run 2 had the same property).

**Time estimate.** In M12b on the RTX 3060 laptop GPU, `base` ran 0.26 s per step on the GPU and 0.46 s per step in
total; window sampling on one CPU process was the rest. `train.py` now samples the next batch on a thread while the
GPU works. The batches are unchanged (each step has its own `[seed, step]` generator). The times above are
rough guesses for A100 and L4 GPUs: scaled has about 5× base's compute per token. The training data is about 58k
windows of 1024 tokens (48.5k BrickGPT, 9.6k real sets), so at batch 64 one pass over them is about 900 steps; the
step caps (40k / 60k) are far beyond where early stopping should end the runs. The smoke run prints the real s/step
on Colab's GPU; use it to replace these guesses in `results/m12e_training.md`.

## Decisions recorded (session B)

- **Training data** = BrickGPT's train split + every training-set model of the pool (main models and official
  alternates) in 8 horizontal symmetries.
- **How much of a real set the model sees.** Only the encoded parts: 52.7% of the pool's part instances. For the
  median pool model, 48.9% of its parts are not encoded: 32.6% have no catalog part, and most of the rest are tilted
  or off the stud grid. Real sets are 16.6% of the training parts; the rest is BrickGPT's colourless bricks. So the
  model learns from about half of each real set. That number goes next to any "learned from real sets" claim. The
  catalog's next step moves it: in the pool, 13.7% of all parts are tilted (sideways building) against 5.3% at
  half-stud offsets (`results/m12e_omr_pool.md`).
- **Real-set share** = the pool's natural share of training parts (`export.json`: 16.6%). M12b oversampled 21 sets 3×
  (run 2) to 16× (run 1), and run 1 memorized them. With the pool that is no longer needed. `SET_SHARE` in the notebook
  overrides it.
- **Demo sets are never used for selection.** 6378-1 and 31048-1 (and any sets Mac adds) are held out of training
  (`heldout.npz`). Their loss is reported at every evaluation but never selects a checkpoint, so the build evaluation on
  them is clean. Selection uses `setval`: a seeded 5% of the other pool sets, 23 sets (`--val-share 0.05
  --val-seed 0`; 37 sequences, 5,934 parts, 69 windows). In M12b, run 2 selected on two of the demo sets, which gave
  16 windows. 23 different sets give a steadier signal.
- **Splits are by set number**, so a set's alternates never straddle training and validation.
- **Large models are cropped**, not dropped: blocks of 64 × 64 studs × 192 plates, each keeping the parts wholly inside
  it, so every turned or mirrored block still fits the grid. Parts across a block edge and blocks under 20 parts are
  dropped: 14 models are cropped and 251 parts lost.
- **Token format unchanged** (M12b: 5 tokens per part, 4-token header, 64 mask patches). Only the shape and colour
  tokens grow with the catalog and the pool's colours, so `bricks/proposal.py` decodes v2 weights without code changes.

## Evaluation plan

Each stage is run on the held-out demo sets only. Each stage's rule is written down before its numbers are seen.

**Stage 1: held-out loss** (from `log.jsonl`, no generation).

- Per field (Y, Z, X, shape, colour), on `setval` (unseen pool sets) and `heldout` (the demo sets), at the selected
  step.
- References: a uniform guess (ln of the field's token count) and the training split's unigram frequencies per field.
  Both are computed from the token data when the table is written.
- `base` vs `scaled`: the size effect on the same data.
- M12b run 2 cannot be compared on loss: its vocabulary is different, so its losses are over a different token set. It
  is compared on builds (stage 2).
- Pass: shape and colour loss on `heldout` below the unigram reference. A model that does not beat frequencies there
  does not go to stage 2.

**Stage 2: builds** (generation; runs only when Mac says go, not on the PC unasked).

- **Pairs:** each demo set × the six M12c bench objects (chair, table, car, sofa, vessel, bench; the objects of
  `examples/m12c_bench.json`, which has 6378-1 but not 31048-1), plus the inventory-only build (no target) of each demo
  set.
- **Arms:** statistics (the current pipeline defaults); `--proposal` M12b run 2; `--proposal` v2 base; `--proposal` v2
  scaled. All arms use the same `--order raster`, same seeds, same flags and 50 candidates.
- Neither `--skin` nor `--symmetric` is set, so any cleaner skin or symmetry comes from the model. One extra arm, v2
  scaled with `--skin --symmetric --recolor`, shows the best combination.
- **Metrics, per pair and arm, on the selected build and the mean over valid candidates:**
  - **Surface cleanliness** (`bricks/skin.py`): distinct parts per all-skin 4 × 4 window and faces per visible part,
    against the real set's own value (`results/m12b_skins_measure.md`: real sets 1.5–4 parts per window, ours 3.6–8.4).
  - **Mirror share** (`bricks/symmetry.py`, `part_symmetry` across the target's best mirror plane): the share of
    mirrorable parts whose twin is placed (real sets 80–100%, ours 7–22% without `--symmetric`).
  - **Colour coherence** (`bricks/coherence.py`): the same-colour share of visible part seams and colours per 4 × 4
    window, against the own set and a within-type shuffle (`results/m12c_colour_measure.md`: ours 41–49% vs real
    64–71%, shuffled 34%).
  - **Rendered sheets:** one sheet per pair, the arms side by side at the same seed (`experiments/demo.labeled_sheet`),
    for Mac's eye.
  - **Reported, not deciding:** validity, completeness (the M12c volume and surface bars), fill, utilization, seconds
    per candidate, parts outside the model's vocabulary, and the **contact judge** (size-matched).
- **Adoption rule:** v2 replaces the statistics as the default proposal if, on the demo pairs, the selected build
  improves at least two of the three looks metrics on a majority of pairs, validity and completeness drop on none, and
  Mac prefers its sheets. The contact judge is listed and cannot veto (cf, 2026-10-09: the judge is not the arbiter of
  looks).

**Driver for stage 2 (to build after training, before running):** pipeline runs per arm into
`out/m12e_eval/<set>/<object>/<arm>` with `--pairs`, as the M12c bench does; then one read-only report driver that
computes the looks metrics above from the stored builds and writes `results/m12e_eval.md` and the sheets. This is
`experiments/proposal_shape.py`'s pattern with looks metrics in place of the judge.
