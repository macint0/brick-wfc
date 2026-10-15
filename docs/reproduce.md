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
python -m brickwfc.alt 10182-1 --n 200 --k 8 --max-clutch inf
```

`--max-clutch inf`: the run predates the real-clutch default.

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
OLD="--no-supports --max-clutch inf"  # the runs predate these defaults (2026-10-09)
for s in 7796-1 6370-1 7743-1; do
  python -m brickwfc.alt $s --shape $CAR --n 20 --workers 10 $OLD --out out/m12b_proposal_shape/$s/stats_random
  python -m brickwfc.alt $s --shape $CAR --n 20 --workers 10 $OLD --order raster \
      --out out/m12b_proposal_shape/$s/stats_raster
  python -m brickwfc.alt $s --shape $CAR --n 20 --workers 10 $OLD --order raster \
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

### `results/m12b_brickgpt.md` (M12b steps 1a and 1c), with `m12b_brickgpt_summary.json`, `m12b_hollow_summary.json`, `m12b_hollow_before_after.png`

The 88-part rerun with the pipeline defaults of fd9015b (box sizing, lattice support columns; 1a and Table 1a; its
two figures are redrawn under `results/m12b_sizing.md`), at fd9015b:

```
python -m brickwfc.experiments.brickgpt --out out/m12b_brickgpt_v2 --steps 1a 1d-figure --workers 10
```

- Writes `results.md`, `summary.json`, `objects.png`, `before_after.png` (1a) and `overhangs_figure.md`,
  `overhangs_figure_summary.json`, `overhangs_before_after.png` (1d-figure, copied to
  `results/m12b_opentops_before_after.png`) under `--out`.
- Downloads the StableText2Brick test split into `data/brickgpt/` on first use (resumable).
- 36 runs, 27 CPU-hours; 3.4 hours wall time on 10 workers. Resumable through the pipeline caches.
- The 5891-1 catalog control is a loop of two pipeline runs, given in the write-up's Reproduce section.

Step 1c (hollow) is from commit 9c4a108, on the 63-part catalog with open tops only:
`python -m brickwfc.experiments.brickgpt --out out/m12b_brickgpt --steps 1d 1c --workers 6` at that commit. The 21
hollow runs take 6.3 CPU-hours.

### `results/m12b_sizing.md` (M12b sizing: slopes, thin parts, support columns), with `m12b_sizing.json`, `m12b_sizing_before_after.png`, `m12b_before_after.png`, `m12b_opentops_before_after.png`, `m12b_chair_figure_summary.json`, `m12b_overhangs_figure_summary.json`

The two figures, with the current defaults (fillable sizing, covering support columns, thin-aware scale):

```
python -m brickwfc.experiments.brickgpt --out out/m12b_sizing_fig --steps 1d-figure 1a-figure --workers 5
```

- Writes `overhangs_figure.md`, `overhangs_figure_summary.json`, `overhangs_before_after.png` (the table; copied to
  `results/m12b_opentops_before_after.png`) and `chair_figure.md`, `chair_figure_summary.json`, `before_after.png`
  (the chair; copied to `results/m12b_before_after.png`).
- 24 runs, 50 candidates each: 17 CPU-hours, 3.8 hours wall time on 5 workers (the 10182-1 runs take 90–230 s per
  candidate).
- Their default-side runs are also the write-up's "after" runs for the tables and the chairs.

The other runs of the write-up (`results/m12b_sizing.json` lists every run folder), one pipeline run each:

```
T=brickgpt:858f0955-846e-4138-84d9-df66b66eddc2; C=brickgpt:a712684f-8e79-4ecd-81de-11aef42b50d4
K=brickgpt:4b15b71c-f400-4e54-a118-f0c2afba6e17
python -m brickwfc.alt 5891-1 --shape $K --n 50 --k 1 --workers 5 --out out/m12b_sizing/5891-1/car_cover  # and 6378-1, 4956-1
python -m brickwfc.alt 10182-1 --shape $K --n 20 --k 1 --workers 5 --out out/m12b_sizing/10182-1/car_cover
```

- At a0ec36c these are the "after" and "cover" arms. The lattice, centre-column, reserve and thin-first arms ran at
  838ee58 (`--reserve-thin 9`, `--order thin`; lattice and centre column: `shapes.with_supports` at that commit and
  a patched copy), the "v2" arm is `results/m12b_brickgpt.md` at fd9015b.
- Two runs are the same run when their cache keys are equal (the key includes the target mask); the write-up's
  carry-over checks compare the keys and every candidate of two run folders.

### `results/m12b_overhangs_tables.md` (M12b step 1d), with `m12b_overhangs_summary.json`

The tables are from commit 9c4a108 (63-part catalog, before the support and clutch defaults); at that commit:

```
python -m brickwfc.experiments.brickgpt --out out/m12b_brickgpt --steps 1d --workers 6
```

- Writes `overhangs.md`, `overhangs_summary.json` (copied to `results/m12b_overhangs_summary.json`) and
  `overhangs_before_after.png` under `--out`. The write-up's
  tables are `overhangs.md`; the figure is `overhangs_before_after.png`.
- Runs the six BrickGPT objects × 3 sets × {exact, open tops, supports} and the table on the six demo sets.
- 31 CPU-hours over these runs (the exact runs are shared with step 1a). Resumable through the pipeline caches.

### `results/m12b_skins_measure.md` (M12b step 3: skins and symmetry, measured first), with `m12b_skins_measure.json`

Measures the step-1a rerun (`out/m12b_brickgpt_v2`, the `m12b_brickgpt.md` runs), the BrickGPT structures and the 28 real sets with `bricks/skin.py` (distinct parts per all-skin 4 x 4 window, faces per visible part) and `bricks/symmetry.py` (mirrored share of mirrorable parts):

```
python -m brickwfc.experiments.skins --steps measure --runs out/m12b_brickgpt_v2
```

- A few CPU-minutes; no generation.

### `results/m12b_skins.md` (M12b step 3: `--skin` and `--symmetric` before / after), with `m12b_skins.json`, `m12b_skins_sheet.png`

Chair, car and table on 6378-1, 5891-1 and 10182-1, four arms per cell (base, `--skin`, `--symmetric`, both), 50 candidates each with the pipeline defaults; the base arm reuses the step-1a cache when the key matches:

```
python -m brickwfc.experiments.skins --steps compare --sets 6378-1 5891-1 10182-1 \
    --objects chair car table --n 50 --workers 10 --compare-out out/m12b_skins
```

- About 4 CPU-hours at 5 workers, most of it the 10182-1 arms and the symmetric arms (mirrored placement).
- The step-3 write-ups are at 3c7ef1e: box sizing and lattice support columns. On main since M12b sizing
  (`results/m12b_sizing.md`) the same commands build with fillable sizing and covering support columns.

### `results/m12b_skins_soft_sweep.md` (M12b step 3: soft skin preference, sweep of a), with `m12b_skins_soft_sweep.json`

The table on 6378-1, the base, skin and both arms of `m12b_skins.md` (from their caches) next to `--skin --skin-power a` for a = 0.25, 0.5, 1, 2, 4, same seeds:

```
python -m brickwfc.experiments.skins --steps compare --objects table --sets 6378-1 \
    --arms base skin both skin_a0.25 skin_a0.5 skin_a1 skin_a2 skin_a4 --n 50 --workers 5 \
    --compare-out out/m12b_skins --compare-results results/m12b_skins_soft_sweep.md
```

- About 1 CPU-hour (5 new arms x 50 candidates at 8-15 s each).

### `results/m12b_skins_soft.md` (M12b step 3: soft skin preference, a = 1 on all cells), with `m12b_skins_soft.json`, `m12b_skins_soft_sheet.png`

Chair, car and table on 6378-1, 5891-1 and 10182-1: base, skin, both and symmetric (from the `m12b_skins.md` caches) next to `--skin --skin-power 1` alone and with `--symmetric`, same seeds:

```
python -m brickwfc.experiments.skins --steps compare --sets 6378-1 5891-1 10182-1 --objects chair car table \
    --arms base skin both skin_a1 both_a1 symmetric --n 50 --workers 5 \
    --compare-out out/m12b_skins --compare-results results/m12b_skins_soft.md
```

- About 13 CPU-hours (2 new arms x 9 cells x 50 candidates), about 3 hours at 5 workers.
- The findings and the decision at the end of the write-up are written by hand; a rerun overwrites the file, so copy them back.

### `results/m12b_symmetry_threshold.md` (M12b step 3: the symmetrize threshold after M12b sizing), with `m12b_symmetry_threshold.json`, `m12b_symmetry_threshold_chair.json`, `m12b_symmetry_threshold_chair.png`

The score table (scaled objects under box and fillable sizing; no generation, a few CPU-minutes):

```
python -m brickwfc.experiments.skins --steps threshold
```

The 5891-1 chair check: base, symmetric and both under fillable sizing, the symmetric arms forced to the old 0.8 threshold so they symmetrize the chair (the base arm reuses the sizing figure run's candidates when its setup key matches):

```
python -m brickwfc.experiments.skins --steps compare --sets 5891-1 --objects chair --arms base symmetric both     --n 50 --workers 5 --symmetrize-min-score 0.8 --runs out/m12b_sizing_fig     --compare-out out/m12b_symmetry_threshold --compare-results out/m12b_symmetry_threshold/chair_5891-1.md
```

- About 3 CPU-hours (2 arms x 50 candidates at about 100 s each), about 40 minutes at 5 workers.
- `chair_5891-1.json` and `_sheet.png` are copied to `results/m12b_symmetry_threshold_chair.json` and `.png`.
- The chair section and the notes at the end of the write-up are written by hand (from `chair_5891-1.md`); the threshold step rewrites the file, so copy them back.

### `results/m12b_complete.md` (M12b completeness: fill, holes, surface, missing maps, causes, fixes, sweep), with `m12b_complete_final.json`, `m12b_complete_missing.png`, `m12b_complete_trace.json` and the sweep's files

The final-state pass reads the sizing runs (`out/m12b_sizing_fig`, `out/m12b_sizing`; see `m12b_sizing.md`). It runs no
generation and takes about a minute:

```
python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps final
```

It writes `final.md`, `final.json` (copied to `results/m12b_complete_final.json`) and `missing_sheet.png` (copied to
`results/m12b_complete_missing.png`), plus one missing map per pair under `missing/`.

The traced replay (10 builds per pair, the selected one first) and its report, at 6095e48 (before the `_fit_key`
fix, which changes builds; the replay must match the cached candidates):

```
python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps trace --per-pair 10 --workers 5
python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps report
```

- The trace step replays 160 builds, about 35 minutes on 5 workers. It writes `traces/<object>_<set>.jsonl` (resumable)
  and stops if a replay differs from its cached build.
- The report step writes `trace.md` and `trace.json` (copied to `results/m12b_complete_trace.json`); the trace section
  of the write-up holds its tables.

The sweep (third part of the write-up; `m12b_complete_sweep.json`, `m12b_complete_sweep_previews.png`,
`m12b_complete_sweep_missing.png`, `m12b_complete_holes.json`, `m12b_complete_old_vs_base.json`), at 49d5739 or later:

```
python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps sweep --n 50 --workers 5 --arms old base hang usable usable90 usable80
python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps sweep-report --arms old base hang usable usable90 usable80
python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps holes --arm usable80 --workers 1
python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps old-vs-base
```

- The sweep step runs the pipeline for 5 arms x 9 pairs, 50 candidates each, one run after another (37 runs: usable
  1.0 only where it leaves a part out). It is resumable: a finished run is skipped, a partial one continues from its
  cache. 17 CPU hours, about 4 hours on 5 workers; give it the machine.
- The "old" arm is the cached pre-fix sizing runs (above); nothing is generated for it.
- sweep-report replays nothing. It writes `sweep.md`, `sweep.json` and the two sheets (downscaled to 40% for
  `results/`). About 10 minutes.
- holes replays the 9 selected builds of the usable 0.8 arm with the trace (identity asserted) and writes
  `holes_usable80.md` and `.json`. 6-20 minutes on one process.
- old-vs-base compares the old arm with the fixed base. The 5891-1 chair's base must be the run made before the moment
  key changed its target (49d5739): run `--steps sweep` at 0dbb3b6 first and move
  `sweep/base/5891-1/chair` to `sweep_premoment/base/5891-1/chair`.
- The sweep in the write-up was run in stages, 59cbfdc first, then the cells each scale fix changed at 0dbb3b6 and
  49d5739. Every other cell's target is byte-identical at 49d5739 and the builder is unchanged, so a run from scratch
  at 49d5739 gives the same table.

The small-part arms (fourth part; `m12b_complete_sweep_small.json`, `m12b_complete_sweep_small_previews.png`,
`m12b_complete_sweep_small_missing.png`, `m12b_complete_holes_reserve80.json`), at e0f97d8 or later, after the sweep
above (the `usable` and `usable80` runs are the defaults they are compared with):

```
python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps sweep --n 50 --workers 5 --arms reserve small1 small2 reserve80 small1_80 small2_80
python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps sweep-report --arms usable reserve small1 small2 usable80 reserve80 small1_80 small2_80 --report-name sweep_small
python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps holes --arm reserve80 --workers 1
```

- The sweep step runs 6 arms x 9 pairs, 50 candidates each (54 runs; resumable as above). 21 CPU hours, about 5 hours
  on 5 workers; give it the machine.
- sweep-report writes `sweep_small.md`, `sweep_small.json` and the two sheets (downscaled to 30% for `results/`).
  About 15 minutes.
- holes writes `holes_reserve80.md` and `.json`; about 5 minutes on one process.

The small-part budget and the remnant bound (fifth part; `m12b_complete_small_only.json`, `m12b_complete_remnants.json`),
after the two hole diagnoses (`holes_usable80.json`, `holes_reserve80.json`); replays only, no generation:

```
python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps small-only --workers 1
python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps remnants --workers 1
```

- small-only sizes the 9 targets at 9 slacks and replays the 18 diagnosed builds; writes `small_only.md` and `.json`.
  About 50 minutes on one process (the sizing dominates).
- remnants replays each of the 18 builds twice (the second stops at each placement that left a remnant); writes
  `remnants.md` and `.json`. About 25 minutes on one process.


### `results/m12b_connected.md` (M12b connected growth on the completeness sweep), with `m12b_connected_sweep.json`, `m12b_connected_sweep_previews.png`, `m12b_connected_sweep_missing.png`, `m12b_connected_stall_map.png`, `m12b_connected_sweep_connected_small.json`, `m12b_connected_sweep_connected_small_previews.png`, `m12b_connected_sweep_connected_small_missing.png`, `m12b_connected_complete_chair.png`

The three connected arms run on the 9 sweep pairs, then a report joins them to the default (usable) arms at the same
slack. The default arms must be in `out/m12b_complete/sweep/`; see `m12b_complete.md`. Commands, at m12b-connected
after the merge of 49d5739 or later:

```
python -m brickwfc.experiments.complete --out out/m12b_complete --steps sweep sweep-report \
    --arms connected connected90 connected80 --workers 5 --report-name sweep_connected
python -m brickwfc.experiments.complete --out out/m12b_complete --steps sweep-report \
    --arms usable connected usable90 connected90 usable80 connected80 --report-name sweep_joined
```

- **Runtime:** 27 runs of 50 candidates on 5 workers, about 2.5 hours; resumable (a finished cell is skipped).
- **Stages:** the runs were made in two stages, 41c9406 first, then the 4 cells whose masks the scale fixes changed,
  at 49d5739. Every other mask is byte-identical at 49d5739 and the builder is unchanged, so a run from scratch gives
  the same table.
- **Report outputs:** `sweep_joined.md` / `.json` and `sweep_joined_previews.png` / `_missing.png`.
  - The `.json` is copied to `results/m12b_connected_sweep.json`.
  - The sheets are scaled to 40% as `results/m12b_connected_sweep_previews.png` and `_missing.png`.
  - The `.md`'s two tables are in the write-up.
- **Stall diagnosis and `m12b_connected_stall_map.png`:** these come from one-off scripts. They rebuild a stalled seed
  with the builder's grown state captured (wrapping `_grow_from_seed` and `_standing_prefix`), then try every
  placement at the layer above the grown top, with the inventory left and with any catalog part. The write-up states
  what they measured.

The small-part arms inside connected growth (section "Connected growth with the small parts kept"), at 901af33 or
later, after the runs above and ee's small-part sweep (`m12b_complete.md`):

```
python -m brickwfc.experiments.complete --out out/m12b_complete --steps sweep sweep-report \
    --arms creserve csmall1 creserve80 csmall1_80 --workers 5 --report-name sweep_connected_small
python -m brickwfc.experiments.complete --out out/m12b_complete --steps sweep-report \
    --arms usable connected creserve csmall1 usable80 connected80 creserve80 csmall1_80 --report-name sweep_connected_small
```

- **Runtime:** 36 runs of 50 candidates on 5 workers, about 2.5 hours; resumable. The second command overwrites the
  first's 4-arm report with the joined one, in about 15 minutes.
- **Report outputs:** `sweep_connected_small.json` is copied to `results/m12b_connected_sweep_connected_small.json`,
  and the two sheets are scaled to 40% under the same names.
- **Stall causes and `m12b_connected_complete_chair.png`:** one-off scripts, as above. The stall rebuild passes the
  arm's small-part option. The figure writes seed 1 and seed 43 of `sweep/creserve80/5891-1/chair` with their
  missing-cell maps (`alt.output.write_build`, `complete.missing_png`).


### `results/m12c_select.md` (M12c completeness-first selection), with `m12c_select.json`

A re-rank of the cached creserve and creserve80 candidates (see `m12b_connected.md`); it generates nothing. At
m12c-select or later:

```
python -m brickwfc.experiments.select --sweep out/m12b_complete --out results/m12c_select
```

- **Runtime:** about 1 minute on one process.
- **Outputs:** `results/m12c_select.json` (every pair under the old rule, the volume bar and the surface bar); the
  printed table is the write-up's, with the surface-bar columns folded into a note (identical to the volume bar's).
- **Check:** the driver stops if the old rule does not reproduce a run's selected seed in its `stats.json`.

### `results/m12c_hollow_sizing.md` (M12c hollow targets at the solid's scale, sizing only), with `m12c_hollow_sizing.json`

Sizes creserve's and creserve80's solid targets on the 9 sweep pairs and cuts 1- and 2-cell shells from them at their
scale; generates nothing. At m12c-hollow or later, with the sweep's creserve runs in `out/m12b_complete/sweep/` (for the
check that the solid targets are theirs):

```
python -m brickwfc.experiments.complete --out out/m12b_complete --steps hollow-sizing
```

- **Runtime:** about 4 minutes on one process (18 usable sizings, 36 shells); resumable (one json per pair under
  `hollow_sizing/`).
- **Outputs:** `hollow_sizing.json` is copied to `results/m12c_hollow_sizing.json`; the table in `hollow_sizing.md` is
  the write-up's.

### `results/m12c_colour_measure.md` (M12c colour coherence of our builds vs the real sets), with `m12c_colour_measure.json`, `m12c_colour_measure.png`

Measures the 28 real sets and the selected creserve / creserve80 builds of the completeness sweep (plus the complete
chair); generates nothing. At m12c-colour or later, with those runs in `out/m12b_complete/sweep/`:

```
python -m brickwfc.experiments.coherence --sweep out/m12b_complete --results results/m12c_colour_measure
```

- **Runtime:** about 5 minutes on one process (1 with the real sets cached under `out/m12c_colour/`; resumable).
- **Outputs:** `results/m12c_colour_measure.json` and `.png`; the tables in `out/m12c_colour/tables.md` are the
  write-up's.

### `results/m12c_recolour.md` (M12c recolouring within part types on the cached selections), with `m12c_recolour.json`, `m12c_recolour.png`, `m12c_recolour_chair.png`

Recolours the builds of `m12c_colour_measure.md` (the selected creserve / creserve80 builds and the complete chair),
seeded as the pipeline's `--recolor`, and measures them before and after; generates nothing. At m12c-recolour or later:

```
python -m brickwfc.experiments.coherence --recolor --sweep out/m12b_complete --results results/m12c_recolour
```

- **Runtime:** about 1 minute on one process with the real sets cached under `out/m12c_colour/` (5 without).
- **Outputs:** `results/m12c_recolour.json`, `.png` and `_chair.png`; the table in `out/m12c_colour/recolor_tables.md`
  is the write-up's.

### `results/m12c_bench_plan.md` (M12c wider bench: plan, sizing dry run, run-time estimate), with `m12c_bench_plan.json`

Sizes the 54 bench pairs (`examples/m12c_bench.json`) under the creserve and creserve80 arms and fits the run-time model
on the cached creserve / creserve80 runs in `out/m12b_complete/sweep/`; generates nothing. At m12c-bench or later:

```
python -m brickwfc.experiments.complete --out out/m12b_complete --steps bench-plan --pairs examples/m12c_bench.json
```

- **Runtime:** about 15 minutes on one process; resumable (one json per pair and arm under `bench_sizing/`).
- **Outputs:** `bench_plan.json` is copied to `results/m12c_bench_plan.json`; the table in `bench_plan.md` is the
  write-up's.

### `results/m12c_stall_6378_chair.md` (M12c diagnosis: connected growth on the cut 6378-1 chair target)

A diagnosis of cached runs (`out/m12b_complete/sweep/creserve70|creserve60/6378-1/chair`, made at 007e6dd); it generates
nothing. The replays come from one-off scripts. Each rebuilds a cached seed with the pipeline's builder
(`alt.candidates.d2_builder` on `complete.replay_setup`) and wraps `_grow_from_seed` and `_standing_prefix` to record
the grown structure, the per-prefix balance and the ground parts. The wrappers draw nothing, and every replay is checked
identical to its cached build. The piece counts come from `scipy.ndimage.label` on each run's cache-key mask. The bench
scan sizes the 54 bench pairs under creserve and creserve80; `bench-plan` now reports the same `pieces` column.

### `results/m12b_size.md` (M12c size below 0.8), with `m12b_size.json`, `m12b_size_sheet.png`, `m12b_size_sheet_usable.png`

The size arms (creserve and the default at 0.9 / 0.7 / 0.6; the other slacks are the cached arms above), the size report
and the completeness-first re-rank, at m12c-size (007e6dd for the runs; the report after the merge of main 044b8f6):

```
python -m brickwfc.experiments.complete --out out/m12b_complete --steps sweep \
    --arms creserve90 creserve70 creserve60 usable70 usable60 --workers 5 --n 50
python -m brickwfc.experiments.complete --out out/m12b_complete --steps size-report
python -m brickwfc.experiments.select --arms creserve90 creserve70 creserve60 usable70 usable60 --out out/m12c_size_select
```

- **Runtime:** 45 runs of 50 candidates on 5 workers, 3 h 17 min; resumable. The report takes about 10 minutes.
- **Report outputs:** `size.md` / `.json` (the `.json` is copied to `results/m12b_size.json`), `size_sheet_creserve.png`
  and `size_sheet_usable.png` (scaled to 40% as `results/m12b_size_sheet.png` and `_usable.png`), and the complete
  candidates under `complete_candidates/`. The write-up marks the 6378-1 chair rows as a cut target by hand.

### `results/m12c_hollow.md` (M12c hollow targets at the solid's scale, run), with `m12c_hollow_sweep.md` / `.json`

The first step of the overnight queue (main 06e484c, 2026-10-11 night; 1 h 57 on 5 workers):

```
python -m brickwfc.experiments.complete --out out/m12b_complete --steps sweep --arms hollow1 hollow1_80 --workers 5
python -m brickwfc.experiments.complete --out out/m12b_complete --steps sweep-report \
    --arms creserve hollow1 creserve80 hollow1_80 --report-name sweep_hollow
```

- `sweep_hollow.md` / `.json` are copied to `results/m12c_hollow_sweep.md` / `.json`; the write-up reads them.

### `results/m12c_stall_6378_chair.md`, dated section 2026-10-12, with `m12c_chair_6378_size.md` / `.json`, `m12c_chair_6378_size_sheet.png`

The reconnected 6378-1 chair under cregrow (creserve's flags + `--regrow`) and the usable controls at 1.0–0.6 (second
and third steps of the queue; 12 min + the report):

```
python -m brickwfc.experiments.complete --out out/m12c_reconnected --steps sweep --workers 5 \
    --arms cregrow cregrow90 cregrow80 cregrow70 cregrow60 usable usable90 usable80 usable70 usable60 \
    --pairs examples/m12c_chair_6378.json
python -m brickwfc.experiments.complete --out out/m12c_reconnected --steps size-report --pairs examples/m12c_chair_6378.json
```

- `size.md` / `.json` → `results/m12c_chair_6378_size.md` / `.json`; `size_sheet_cregrow.png` →
  `results/m12c_chair_6378_size_sheet.png`; the complete candidate under `complete_candidates/`.

### `results/m12c_bench.md` (M12c wider bench at 0.6 and 0.8), with `results/m12c_bench_sweep_0.6.md` and `results/m12c_bench_sweep_0.8.md` (+ `.json`), `m12c_bench_sheet_0.6.png` / `_0.8.png`

The rest of the queue (`bash scripts/overnight_m12c.sh 0.6 0.8`; the bench steps 23:10–06:18, resumable). Per slack
(`bench60` shown; `bench80` the same):

```
python -m brickwfc.experiments.complete --out out/m12c_bench --steps sweep --arms bench60 \
    --pairs examples/m12c_bench_new.json --workers 5                      # the 45 new pairs, smallest sets first
python -m brickwfc.experiments.complete --out out/m12c_bench --steps sweep --arms bench60 --workers 5   # the 9 sweep pairs
python -m brickwfc.experiments.complete --out out/m12c_bench --steps sweep-report --arms bench60 \
    --pairs examples/m12c_bench.json --report-name sweep_bench_0.6
python -m brickwfc.experiments.select --sweep out/m12c_bench --arms bench60 --pairs examples/m12c_bench.json \
    --out out/m12c_bench/select_0.6
python -m brickwfc.experiments.coherence --sweep out/m12c_bench --arms bench60 --pairs examples/m12c_bench.json \
    --results out/m12c_bench/coherence_0.6
```

- **Runtime:** 2.0 h (0.6) and 3.3 h (0.8) for the 45 new pairs, 30 and 42 min for the 9 sweep pairs, on 5 workers.
- The select and coherence steps failed in the queue (a `with_suffix` naming bug and an all-stall run with no selection;
  both fixed the next morning) and were rerun from the cached runs. `sweep_bench_*.md` / `.json` are copied to
  `results/`; the bench sheets come from a one-off script over each run's selected preview
  (`results/m12c_bench_sheet_*.png`); the aggregate numbers in the write-up are computed from the `.json` tables and each
  run's `stats.json`.
- **Replay after the verify-stage fix** (a complete build exempt from the size and fill floors): the select driver
  rerun on every cached run (`--out out/m12c_refloor/...`) prints `rerun with ... selects seed X, the run selected Y`
  where a stored pick changes and records both seeds (`stored_seed`, `replayed_seed`).

### `results/m12d_missing_parts.md` (M12d: the parts the catalog cannot place, ranked)

Seconds for the 28 sets, a few seconds more for all local models (`--all`); Rebrickable's `parts.csv.gz` supplies the
names (download `https://cdn.rebrickable.com/media/downloads/parts.csv.gz` into `data/rebrickable/`; without it names
print as `?`):

```
python -m brickwfc.experiments.missing_parts --sets-file results/sets_selection.json --out results/m12d_missing_parts.md
python -m brickwfc.experiments.missing_parts --all --out out/m12d_missing_all.md
```

The counts are at the catalog the command runs with (the file header names how many files it knows), so the ranking
changes with every M12d batch; the one on main at d15e46b is the 88-part one that chose the batches.

### `results/m12d_catalog.md` (M12d: the catalog extended to the real sets' parts)

Coverage (seconds per set list; `--data` where the OMR models are):

```
python -m brickwfc.experiments.coverage --on-grid --sets-file results/sets_selection.json --out out/m12d_cov/m10
python -m brickwfc.experiments.coverage --on-grid --out out/m12d_cov/omr20
python -m brickwfc.experiments.coverage --on-grid --sets $(ls data/omr | sed 's/\.mpd$//') --out out/m12d_cov/all
```

`results/m12d_coverage_*.json` are the three runs' `coverage.json`. Style statistics v3 (a few minutes, one process) and
the check that the M12b catalog reproduces v2:

```
python -m brickwfc.experiments.style --learn-only v3
python -m brickwfc.experiments.style --learn-only v2 --catalog m12b --stats-dir out/v2check
```

Part geometry facts (the placement-test rows) come from `python -m brickwfc.ldraw.library PART --cache data/ldraw`, with
the library's `complete.zip` unpacked under `data/ldraw` (`parts/` and `p/`, lower-case paths); the catalog check for
Studio is `python -m brickwfc.bricks.catalog_check`.

## Not run yet

Commands for results that are still to be run (the drivers are on main):

- **M13 budget curve**:
  `python -m brickwfc.experiments.budget_curve --out out/m13_budget`.
  - Defaults: 3 sets, 10 seeds, budgets up to 600 s.
  - WFC on 2 workers takes up to 3 x 10 x 600 s / 2, about 2.5 hours, as a worst case.
  - Resumable. Run it on an otherwise idle machine, because wall times are the result.
