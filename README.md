# brick-wfc: alternate brick builds from a real inventory

Give it the parts of a real brick set (a set number, an LDraw model, or a parts list) and, optionally, a target
shape. It generates new alternate builds that use only those parts, and it guarantees the following by
construction, not by filtering afterwards:

- every part rests on a stud;
- no part is used more often than the set has it;
- the build stays inside the target shape;
- the build does not tip over on a table;
- the build is one piece.

The style is learned from 28 official building sets. A generate, verify, dedupe, judge, select funnel keeps the best
candidates, and each one comes out as an LDraw file with one building step per layer. The project started as
constraint-aware Wave Function Collapse (WFC); a bottom-up decoder turned out better on every measure, so WFC is kept
as the compared method (see [results/](results/) and [paper/](paper/)).

## Install

Python 3.11+.

```
pip install -e ".[dev]"
```

Dependencies: `numpy`, `Pillow`, `scipy`, `trimesh` (the mesh voxelizer for `.obj`/`.stl` targets), and `pytest`
for the tests. Run the tests with `pytest`.

PyTorch is used only in `training/`, to train the learned proposal model; it is not a dependency of the package,
which runs the trained model with numpy on the CPU. Training runs on a local GPU (an RTX 3060 Laptop, 6 GB, in about
an hour), with CUDA PyTorch in a separate throwaway venv:

```
python -m venv <venv>
<venv>/Scripts/pip install numpy torch --index-url https://download.pytorch.org/whl/cu124
<venv>/Scripts/python training/train.py --data data/tokens --out out/proposal_run2 --batch 64 --steps 7000 \
    --set-share 0.05 --val-sets 6378-1 31048-1
```

Use only the cu124 index: adding PyPI as an extra index makes pip pick a CPU-only wheel. On Colab instead (optional):
`training/train.ipynb`.

## Make alternate builds

```
python -m brickwfc.alt 6372-1 --n 200 --k 8
```

`INPUT` is one of the following:

- an OMR set number such as `6372-1`, downloaded once to `data/omr/`;
- an `.mpd`/`.ldr` model;
- a `.csv` parts list, one `part file, LDraw color code, count` per line;
- any other set number: a set without an OMR model falls back to its Rebrickable inventory (no model needed), and
  `rebrickable:6372-1` forces this. On the 28 style sets, Rebrickable and OMR inventories agree to 0.95 on average
  ([m12c_rebrickable.md](results/m12c_rebrickable.md)).

Inventories are read with the full 88-part catalog (plates, bricks, tiles, lookalikes, 2 corners, 22 slopes);
`--catalog m8` reads them with the 63 parts from before M12b.

Main options:

| option | meaning |
|---|---|
| `--n` / `--k` | candidates to generate / builds to select (defaults 200 / 8) |
| `--shape` | target shape, scaled to the inventory's volume (below) |
| `--generator d2\|wfc` | the bottom-up decoder (default) or constrained WFC (compared method) |
| `--workers` | processes for generation (default: CPU count - 2); `--wfc-workers` caps WFC (memory) |
| `--no-balance`, `--no-connect`, `--no-bridge` | switch off the tip-over check, the one-piece pass, the bridging preference |
| `--max-clutch` | limit on the required clutch per stud in the physics check (default: unbounded) |
| `--hollow N` | 3D target: a shell N cells thick plus internal pillars (default 0: solid) |
| `--supports` | 3D target: add support columns under overhangs that are out of a part's reach |
| `--no-open-tops` | with a target: let tiles cap cells that have target cells above them (as before M12b) |
| `--style-version v1\|v2` | learned style statistics: v2 (default) includes slopes and corners; v1 is M10's |
| `--seed`, `--out`, `--fresh` | first seed, output folder, discard cached candidates |

`--shape` takes four kinds of input:

1. **A primitive**: `block`, `pyramid`, `arch`, `mushroom`, `ring`.
2. **A top-down silhouette image**: one pixel per stud, where opaque or dark pixels are inside. It is extruded
   `--shape-height` plates. `--height-map` (grey = height in plates) and `--color-map` (preferred colors) are
   optional and must be the same size as the silhouette.
3. **A model**: an `.ldr`/`.mpd` file or an OMR set number, as solid columns by default (`--shape-exact` keeps the
   exact cells).
4. **A true 3D target**: a BrickGPT structure `brickgpt:<structure id>` from the StableText2Brick test split, or a
   watertight `.obj`/`.stl` mesh, voxelized (`--voxels`, `--mesh-up`). `--shape-columns` turns either into solid
   columns.

With a target, open tops are on by default: a tile or a covered brick top may not sit where the target continues
above it, so thin stems (table legs, chair posts) are not capped.

Example with a silhouette and a color map:

```
python -m brickwfc.alt 6372-1 --shape examples/spaceship_silhouette.png \
    --height-map examples/spaceship_heights.png --color-map examples/spaceship_colors.png
```

The spaceship images are in `examples/` (written by `experiments/demo.py`).

### Where the output goes

Everything goes to `out/alt/<input name>/`, or to `--out` if given. `out/` is gitignored.

| file | contents |
|---|---|
| `build_01.ldr` ... | the selected builds, one `0 STEP` per layer, bottom to top |
| `build_01.png` ... | isometric previews |
| `sheet.png` | all previews on one contact sheet |
| `stats.json` | funnel stage counts, check failures, timing, the selected builds' numbers |
| `candidates.jsonl` | every candidate as it is generated |

Because `candidates.jsonl` keeps every candidate, a killed run resumes: rerun the same command.

### Open a build

Open the `.ldr` files in any LDraw viewer, for example BrickLink Studio, LDView or LeoCAD. The `0 STEP` lines play
back as building instructions in the viewers that support steps.

## Data sources and licenses

Everything downloaded goes to `data/`, which is gitignored and never committed.

| source | used for | where | license / terms |
|---|---|---|---|
| [LDraw Official Model Repository](https://library.ldraw.org/omr) | set models: inventories, learned style, model targets | `data/omr/` | per file, see each file's `!LICENSE` header: most are "Redistributable under CCAL version 2.0" (CC BY 2.0), a few "Free for non-commercial use" |
| [StableText2Brick](https://huggingface.co/datasets/AvaLovelace/StableText2Brick) (BrickGPT's data) | 3D targets, head-to-head, training data for the learned proposal | `data/brickgpt/` | MIT, per the dataset card |
| [Rebrickable downloads](https://rebrickable.com/downloads/) | inventories of sets without an OMR model | `data/rebrickable/` | free bulk CSV downloads; see Rebrickable's terms of use (check) |
| LDraw parts library | not downloaded; parts are identified by their LDraw file names only | | |

The trademark of the brick manufacturer is not used in this project's names or outputs.

## Milestones

Each line points to the write-up with its numbers. [docs/reproduce.md](docs/reproduce.md) gives the command that
regenerates each one.

| | milestone | result |
|---|---|---|
| M0-M3 | 2D WFC, rules learned from an example, funnel v0 | (no results file) |
| M4-M5 | 3D grid, multi-cell parts, `.ldr` export | (no results file) |
| M6 | stability-aware WFC vs post-filter vs bottom-up | [m6_stability.md](results/m6_stability.md) |
| M7 | physics-based verifier (LP, table vs baseplate) | [m7_physics.md](results/m7_physics.md) |
| M8 | part catalog: 63 plates, bricks, tiles, lookalikes | [m8_parts.md](results/m8_parts.md) |
| M9 | inventory constraint (plates of 10 sets) | [m9_inventory.md](results/m9_inventory.md) |
| M9b | inventory with the full catalog | [m9b_inventory_catalog.md](results/m9b_inventory_catalog.md) |
| M9b | the 28 building sets for style | [sets_selection.md](results/sets_selection.md) |
| M10 | learned style and the size-matched judge | [m10_style.md](results/m10_style.md) |
| M11 | target shapes, quick test (shape only) | [m11_shape_quick.md](results/m11_shape_quick.md) |
| M11 | target shapes with inventories (10 sets x 5 shapes) | [m11_shape_inventory.md](results/m11_shape_inventory.md) |
| M12 | the alternate-build pipeline: tip-over check, one piece, image/model targets, six-set demo | [m12_pipeline.md](results/m12_pipeline.md) |
| M12b | 3D targets: BrickGPT structures, meshes, hollow targets, BrickGPT head-to-head | [m12b_brickgpt.md](results/m12b_brickgpt.md) |
| M12b | overhangs: open tops (default), support columns, clutch limits | [m12b_overhangs_tables.md](results/m12b_overhangs_tables.md) |
| M12b | 88-part catalog with 2 corners and 22 slopes: recognized share of the 28 style sets 61% → 69% (on the grid 49% → 57%), of the 20 OMR sets 51% → 57%; style statistics v2 | [m12b_catalog.md](results/m12b_catalog.md) |
| M12b | learned proposal: token data, two training runs on a local GPU, run 2 chosen (comparison with the statistics still running) | [m12b_tokens.md](results/m12b_tokens.md), [m12b_proposal_training.md](results/m12b_proposal_training.md) |
| M12c | inventories from Rebrickable for any set number, checked against 28 OMR models | [m12c_rebrickable.md](results/m12c_rebrickable.md) |
| M13 | paper tables, diversity, budget curve, user-study helper | [m13_tables.md](results/m13_tables.md), [m13_diversity.md](results/m13_diversity.md) |

## Layout

```
src/brickwfc/   wfc.py, tileset.py (WFC core); bricks/ (parts, decoder, physics, style, inventory, shapes);
                alt/ (the pipeline); funnel/ (verify, dedupe, judge, select, diversity); ldraw/ (IO, OMR fetch);
                experiments/ (drivers for the results)
training/       the learned proposal model: train.py (PyTorch, separate venv), train.ipynb (Colab), parity.py
tests/          pytest
results/        write-ups and summary data of every experiment
paper/          LaTeX sources (powershell -File paper/build.ps1)
docs/           reproduce.md
```
