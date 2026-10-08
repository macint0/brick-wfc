# Reproducing the results

Every file in `results/` comes from one command below. Run all commands from the repository root, after
`pip install -e ".[dev]"`.

**What the commands write.** Each driver writes its raw output under `out/<name>/`: `results.md`, `summary.json`
and, for most, `runs.jsonl`. The `results/*.md` files are write-ups of those runs, with the tables copied in and
findings added by hand. The `results/*_summary.json` files are copies of the drivers' `summary.json` (the copying
step is manual: check). So a rerun regenerates the numbers, not the prose.

**Downloads.** OMR models are fetched into `data/omr/` on first use and cached. The BrickGPT structures go into
`data/brickgpt/`.

**Resumable** means a killed run picks up where it stopped when you rerun the same command. Results are written
after each unit of work, and units already done are skipped.

**Runtimes** are as measured on Mac's PC (12 logical cores, 16 GB). Two sources:
- the time stated in the write-up;
- for the pipeline runs, the CPU time summed from the runs' `stats.json` (`generation_cpu_s + physics_cpu_s`).
  Wall time is roughly CPU time / workers.

**Parallel output.** Parallel drivers give the same output for any worker count, apart from wall times.

## Per results file

### `results/m6_stability.md` (M6), with `m6_stability_summary.json`

```
python -m brickwfc.experiments.stability --seeds 1000 --sizes 4x4x2 4x4x3 8x8x6 --out out/m6
```

About 16 minutes, single process. Resumable.

### `results/m7_physics.md` (M7), with `m7_physics_summary.json`

```
python -m brickwfc.experiments.stability --seeds 1000 --sizes 4x4x2 4x4x3 8x8x6 --out out/m7
```

The same driver as M6, which now also runs the physics LP. About 20 minutes, single process. Resumable.

### `results/m8_parts.md` (M8), with `m8_coverage.json`

```
python -m brickwfc.experiments.coverage --out out/m8_coverage
```

- Writes `coverage.md` and `coverage.json`; `results/m8_coverage.json` is the copy.
- The driver's docstring gives `--out results/m8_coverage`, the write-up `out/m8_coverage`; either works.
- Runtime: seconds once the models are downloaded (check).
- Not resumable: there is nothing to resume.
- The catalog check model for a viewer: `python -m brickwfc.bricks.catalog_check` writes
  `out/check/catalog_check.ldr`.

### `results/m9_inventory.md` (M9), with `m9_inventory_summary.json`

```
python -m brickwfc.experiments.inventory --seeds 20 --out out/m9
```

- Four plate types per set (the default `--catalog plates`), 10 sets. Single process.
- Runtime: not stated; the original run was killed after 7 sets and resumed (check).
- Resumable: finished (set, condition) pairs are skipped.

### `results/m9b_inventory_catalog.md` (M9b), with `m9b_inventory_catalog_summary.json`

```
python -m brickwfc.experiments.inventory --catalog full --height 12 --seeds 20 \
    --conditions B_inventory D_bottom_up D2_bottom_up_any_offset --time-limit 30 --wfc-max-mb 1000 --out out/m9b
```

About 70 minutes, serial. Resumable.

### `results/sets_selection.md`, with `sets_selection.json`

```
python -m brickwfc.experiments.sets --out out/sets
```

- Fetches about 86 candidate set models into `data/omr/`, cached.
- Writes `sets.md` and `sets.json`; `results/sets_selection.*` are the copies.
- Runtime: dominated by the downloads on the first run (check).

### `results/m10_style.md` (M10), with `m10_style_summary.json` and `m10_style_stats/`

```
python -m brickwfc.experiments.style --workers 10 --wfc-workers 2 --out out/m10
```

- About 40 minutes on 10 worker processes, 2 of them for WFC (memory).
- Resumable per (set, condition, style).
- Writes `style_fold{0..3}.json` under `--out`; `results/m10_style_stats/` holds the copies used by the
  pipeline (check).

### `results/m11_shape_quick.md` (M11 quick test), with `m11_shape_quick_summary.json`

```
python -m brickwfc.experiments.shape --seeds 100 --out out/m11
```

About 4 minutes. Resumable.

### `results/m11_shape_inventory.md` (M11), with `m11_shape_inventory_summary.json`

```
python -m brickwfc.experiments.shape_inventory --seeds 20 --export 2 --out out/m11_full
```

About 11 minutes of build time. Resumable: finished (set, shape, condition) batches are skipped.
`--export 2` writes 600 example builds to `out/m11_full/builds/`.

### `results/m12_pipeline.md` (M12), with `m12_balance_summary.json`, `m12_connect_summary.json`, `m12_demo_summary.json`, `m12_demo_sheet.png`

Every M12 driver runs the alternate-build pipeline (`python -m brickwfc.alt`). Each pipeline run caches its
candidates, so all of them are resumable. Workers default to CPU count - 2.

**Step 1b, the tip-over check** (`m12_balance_summary.json`):

```
python -m brickwfc.experiments.balance --study tipover --sets 6372-1 10182-1 --n 200 --out out/m12_1b
```

- The original run called `python -m brickwfc.alt` directly for the four conditions (`out/m12_1b.sh`).
- The two "slab" conditions (`--height 12`) are the same today.
- The two "cube" conditions now get the current default grid, a cube in millimetres. The 1b table in the
  write-up used a cube in cells, so to reproduce those two rows exactly, run at commit 37f8094 (see the comment
  on `STUDIES` in `experiments/balance.py`).
- 6.1 CPU-hours over 8 runs.

**Step 2b, one piece** (`m12_connect_summary.json`):

```
python -m brickwfc.experiments.balance --study connect --sets 6372-1 10182-1 --n 200 --out out/m12_2b
```

6.7 CPU-hours over 8 runs.

**Step 3, the six-set spaceship demo** (`m12_demo_summary.json`, `m12_demo_sheet.png`):

```
python -m brickwfc.experiments.demo --out out/m12_demo
```

- Defaults: 100 D2 candidates and 100 without the connect pass per set; 10 WFC candidates with a 30 s cap, on sets
  of at most 400 parts.
- 9.5 CPU-hours over 17 runs. Up to 140 s per candidate on 10182-1.
- WFC runs use 2 workers (about 1.5 GB each on 10182-1).

**A single pipeline run, as in the write-up's 10182-1 example**:

```
python -m brickwfc.alt 10182-1 --n 200 --k 8
```

0.8 CPU-hours.

### `results/m13_diversity.md` (M13), with `m13_diversity.json`

```
python -m brickwfc.experiments.diversity_pass
```

- Reads the run folders already on disk (`out/alt/*`, `out/m12_2b/*/*`, `out/m12_demo/*/*`,
  `out/m12b_brickgpt/*/*`) and builds nothing. Run the M12 and M12b drivers first.
- About 1 minute. Cached per run by file size and modification time (`out/m13_diversity/cache.json`), so a rerun
  reads only changed runs.

### `results/m13_tables.md` (M13)

```
python -m brickwfc.experiments.paper_tables
```

- Reads only the summary files in `results/` (plus the BrickGPT and proposal summaries, if present). Seconds.
- Cells whose source file is missing read "pending".
- Then `python paper/tables.py` turns the tables into LaTeX for `paper/`, and `powershell -File paper/build.ps1`
  builds the PDF.

### `results/m12b_proposal_training.md` (M12b step 2)

Trained on a local GPU (RTX 3060 Laptop, 6 GB) with PyTorch 2.6.0+cu124 in a separate venv; PyTorch is not a project
dependency. One data process; mixed precision.

```
python training/train.py --data data/tokens --out out/proposal_run1 --batch 64 --steps 7000 --minutes 62
python training/train.py --data data/tokens --out out/proposal_run2 --batch 64 --steps 7000 --minutes 62 \
    --set-share 0.05 --val-sets 6378-1 31048-1
PYTHONPATH=src python training/parity.py check --weights out/proposal_run2/proposal.npz --data data/tokens --windows 4
```

- Run 1: 55 minutes.
- Run 2 was stopped by hand at step 3000 (24 minutes), after its selection loss rose for three evaluations; the
  selected weights are step 1500's.
- Resumable: a checkpoint is saved at every evaluation.
- Copy `proposal.npz`, `vocab.json` and `log.jsonl` into `data/models/` (as `proposal_run{1,2}.npz` and
  `proposal_run{1,2}_log.jsonl`).
- On Colab instead: `training/train.ipynb`.

### `results/m12b_overhangs_tables.md` (M12b step 1d), with `m12b_opentops_before_after.png`

```
python -m brickwfc.experiments.brickgpt --out out/m12b_brickgpt --steps 1d --workers 6
```

- Writes `overhangs.md`, `overhangs_summary.json` and `overhangs_before_after.png` under `--out`. The write-up's
  tables are `overhangs.md`; the figure is `overhangs_before_after.png`.
- Runs the six BrickGPT objects × 3 sets × {exact, open tops, supports} and the table on the six demo sets.
- 31 CPU-hours over these runs (the exact runs are shared with step 1a). Resumable through the pipeline caches.

## Not on main yet, or not run yet

Commands for results that are on branches or still to be run:

- **M12b step 1a, BrickGPT head-to-head**:
  `python -m brickwfc.experiments.brickgpt --out out/m12b_brickgpt`.
  Resumable through the pipeline caches; 17.1 CPU-hours over the 25 runs so far. Its results file is not in
  `results/` yet (check).
- **M12b step 2, token dataset (`results/m12b_tokens.md`, branch m12b-proposal)**:
  `python -m brickwfc.experiments.export_tokens --omr data/omr --workers 3`.
  Minutes, after the BrickGPT train split is downloaded (resumable). Training runs on Colab:
  `training/train.ipynb`.
- **M12b step 2, learned proposal vs statistics (branch m12b-proposal)**:
  `python -m brickwfc.experiments.proposal --weights data/models/proposal.npz --out out/m12b_proposal`.
  Resumable; 3 workers by default.
- **M12c, Rebrickable check (`results/m12c_rebrickable.md`, branch m12c-rebrickable)**:
  `python -m brickwfc.experiments.rebrickable_check --omr data/omr`.
  About 15 s once the CSVs are downloaded.
- **M13 budget curve**:
  `python -m brickwfc.experiments.budget_curve --out out/m13_budget`.
  - Defaults: 3 sets, 10 seeds, budgets up to 600 s.
  - WFC on 2 workers takes up to 3 x 10 x 600 s / 2, about 2.5 hours, as a worst case.
  - Resumable. Run it on an otherwise idle machine, because wall times are the result.
