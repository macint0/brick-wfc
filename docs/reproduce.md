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

**Tests in a git worktree.** `pyproject.toml` sets `[tool.pytest.ini_options] pythonpath = ["src"]`, so pytest
puts the checkout's own `src/` ahead of `PYTHONPATH`. To test a worktree's tests against another branch's package,
override it: `pytest -o pythonpath=<other checkout>/src`. Drivers run with `python -m` are not affected; set
`PYTHONPATH=<worktree>/src` for those, because the editable install points at the main checkout.

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
- Writes `style_fold{0..3}.json` under `--out`; `results/m10_style_stats/` holds the copies the pipeline reads
  (`alt.inputs.STYLE_DIR`), next to the v2 files of M12b step 4.

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

### `results/m12b_catalog.md` (M12b step 4: corners and slopes), with `m12b_coverage_omr20.json`, `m12b_coverage_m10.json`, `m10_style_stats/style_fold*_v2.json`, `m12b_catalog_before_after.png`, `m12b_catalog_before_summary.json`, `m12b_catalog_after_summary.json`

**Coverage** (`m12b_coverage_*.json`). Seconds per set:

```
python -m brickwfc.experiments.coverage --on-grid --out out/m12b_cov_omr20
python -m brickwfc.experiments.coverage --on-grid --sets-file results/sets_selection.json --out out/m12b_cov_m10
```

**Style statistics v2** (`m10_style_stats/style_fold{i}_v2.json`). About a minute; learning only:

```
python -m brickwfc.experiments.style --learn-only v2
```

`--catalog m8 --learn-only v1check` reproduces the M10 (v1) files exactly.

**Before/after figure** (`m12b_catalog_before_after.png` and the two summaries):

```
python -m brickwfc.experiments.demo --sets 6378-1 5891-1 --wfc-n 0 --n 100 --out out/m12b_catalog_fig/before
python -m brickwfc.experiments.demo --sets 6378-1 5891-1 --wfc-n 0 --n 100 --catalog full --style-version v2 --out out/m12b_catalog_fig/after
python -m brickwfc.experiments.catalog_figure
```

- The before run equals the M12 demo's D2 runs, so copying `out/m12_demo/<set>/{d2,d2_no_connect}/candidates.jsonl`
  into its folders makes it instant.
- The after run took about 2.4 CPU-hours (5891-1: 68 s per candidate).
- Copy the two `summary.json` files to `results/m12b_catalog_{before,after}_summary.json`.

**Catalog check for Studio** (not in `results/`):

```
python -m brickwfc.bricks.catalog_check
```

It writes `out/check/catalog_check.ldr`.

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

### `results/m12b_tokens.md` (M12b step 2a)

```
python -m brickwfc.experiments.export_tokens --omr data/omr --out data/tokens --workers 3
```

- Minutes, after the BrickGPT train split is downloaded into `data/brickgpt/` (fetched if missing; resumable).
- Writes `vocab.json`, `train.npz`, `val.npz` and `heldout.npz` under `data/tokens/` (gitignored), and the
  statistics in the write-up.
- The write-up and the trained models used the 63-part catalog (488 tokens; run at 922f0e6). On main the
  vocabulary has the 88-part catalog's shapes (548 tokens before set colors), so a rerun exports different data,
  which does not fit the trained runs' `vocab.json`.

### `results/m12b_proposal_training.md` (M12b step 2)

Trained on a local GPU (RTX 3060 Laptop, 6 GB) with PyTorch 2.6.0+cu124 in a separate venv; PyTorch is not a project
dependency. One data process; mixed precision. Make the venv once (use only the cu124 index; with PyPI as an extra
index, pip picks a CPU-only wheel), then run the commands below with its `python`:

```
python -m venv <venv>
<venv>/Scripts/pip install numpy torch --index-url https://download.pytorch.org/whl/cu124
```

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
- Run 2 is the model chosen for the comparison with the statistics (reasons in the write-up's last section).
- Optional alternative: `training/train.ipynb` on Colab (free T4).

### `results/m12b_proposal.md` (M12b step 2: learned proposal vs statistics), with `m12b_proposal_summary.json`, `m12b_proposal_runs.jsonl`, `m12b_proposal_before_after.png`

Needs `data/models/proposal_run2.npz` and `vocab.json` (see the previous section). One invocation per set, smallest
first, then one for the summary over all sets:

```
for s in 7796-1 6370-1 7743-1 5891-1 10264-1 10243-1 10197-1; do
  python -m brickwfc.experiments.proposal --weights data/models/proposal_run2.npz --seeds 5 --workers 10       --sets $s --out out/m12b_proposal
done
python -m brickwfc.experiments.proposal --weights data/models/proposal_run2.npz --seeds 5 --out out/m12b_proposal
python -m brickwfc.experiments.proposal_report --dir out/m12b_proposal --weights data/models/proposal_run2.npz     --figure-set 6370-1 --figure results/m12b_proposal_before_after.png --json results/m12b_proposal_summary.json     --spot-check 6
```

- Style statistics v2 (`--style-version`, the default). The driver refuses to resume into a folder holding builds
  made with another version.
- About 7 minutes on 10 workers (35 minutes of build time); the largest set takes up to 104 s per proposal build.
- Resumable per (set, condition, seed). `runs.jsonl` logs each build's placed parts, so the report and the figure
  need no rebuilds; `--spot-check` rebuilds a few builds from their seeds and checks that they match.
- The report prints the write-up's tables.
- `results/m12b_proposal_runs.jsonl` is `runs.jsonl` without the placed parts (the copying step is manual); the
  paper tables read it.

### `results/m12b_proposal_shape.md` (M12b step 2, phase 2: with a target shape), with `m12b_proposal_shape.json`, `m12b_proposal_shape.png`

Needs `data/models/proposal_run2.npz` and `vocab.json`. Three pipeline runs per set (one per arm), then the report:

```
CAR=brickgpt:4b15b71c-f400-4e54-a118-f0c2afba6e17
for s in 7796-1 6370-1 7743-1; do
  python -m brickwfc.alt $s --shape $CAR --n 20 --workers 10 --out out/m12b_proposal_shape/$s/stats_random
  python -m brickwfc.alt $s --shape $CAR --n 20 --workers 10 --order raster \
      --out out/m12b_proposal_shape/$s/stats_raster
  python -m brickwfc.alt $s --shape $CAR --n 20 --workers 10 --order raster \
      --proposal data/models/proposal_run2.npz --out out/m12b_proposal_shape/$s/proposal_raster
done
python -m brickwfc.experiments.proposal_shape --dir out/m12b_proposal_shape \
    --weights data/models/proposal_run2.npz --figure-set 6370-1 --figure results/m12b_proposal_shape.png \
    --json results/m12b_proposal_shape.json
```

- About 1.2 CPU-hours of generation, most of it the proposal arm (38-66 s per candidate against 2-14 s).
- Resumable through the pipeline caches. `--order` and `--proposal` enter the cache key (the model by a hash of
  its weights), so a statistics cache is never reused for the model.
- The report reads the run folders and builds nothing; it prints the write-up's table.

### `results/m12c_rebrickable.md` (M12c), with `m12c_rebrickable.json`

```
python -m brickwfc.experiments.rebrickable_check --omr data/omr --out out/m12c/rebrickable.md
```

- About 15 s once the Rebrickable CSVs are in `data/rebrickable/` (downloaded on first use).
- The driver's default `--out` is `results/m12c_rebrickable.md` itself, which overwrites the write-up.
- The write-up used the 63-part catalog (run before the 88-part catalog merged, at 056cff2). A rerun on main reads
  both inventories with corners and slopes, so the part counts and agreements change.

### `results/m12b_brickgpt.md` (M12b steps 1a and 1c), with `m12b_brickgpt_summary.json`, `m12b_hollow_summary.json`, `m12b_before_after.png`, `m12b_hollow_before_after.png`

```
python -m brickwfc.experiments.brickgpt --out out/m12b_brickgpt --steps 1d 1c 1a --workers 6
```

- Step 1a's head-to-head uses step 1d's open-tops runs, so run 1d first (or in the same command, as above).
- Writes `results.md`, `summary.json`, `objects.png`, `before_after.png` (1a) and `hollow.md`,
  `hollow_summary.json`, `hollow_before_after.png` (1c) under `--out`.
- Downloads the StableText2Brick test split into `data/brickgpt/` on first use (resumable).
- Resumable through the pipeline caches. The 21 hollow runs (1c) take 6.3 CPU-hours.

### `results/m12b_overhangs_tables.md` (M12b step 1d), with `m12b_opentops_before_after.png`

```
python -m brickwfc.experiments.brickgpt --out out/m12b_brickgpt --steps 1d --workers 6
```

- Writes `overhangs.md`, `overhangs_summary.json` (copied to `results/m12b_overhangs_summary.json`) and
  `overhangs_before_after.png` under `--out`. The write-up's
  tables are `overhangs.md`; the figure is `overhangs_before_after.png`.
- Runs the six BrickGPT objects × 3 sets × {exact, open tops, supports} and the table on the six demo sets.
- 31 CPU-hours over these runs (the exact runs are shared with step 1a). Resumable through the pipeline caches.

## Not run yet

Commands for results that are still to be run (the drivers are on main):

- **M13 budget curve**:
  `python -m brickwfc.experiments.budget_curve --out out/m13_budget`.
  - Defaults: 3 sets, 10 seeds, budgets up to 600 s.
  - WFC on 2 workers takes up to 3 x 10 x 600 s / 2, about 2.5 hours, as a worst case.
  - Resumable. Run it on an otherwise idle machine, because wall times are the result.
