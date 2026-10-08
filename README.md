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

Dependencies: `numpy`, `Pillow`, `scipy`, and `pytest` for the tests. `trimesh` is approved for the mesh voxelizer
(3D `.obj`/`.stl` targets) and is added to `pyproject.toml` with that step (check). PyTorch is used only in
`training/`, on Colab, to train the learned proposal; it is not a dependency of the package (check:
`training/` arrives with the m12b-proposal branch). Run the tests with `pytest`.

## Make alternate builds

```
python -m brickwfc.alt 6372-1 --n 200 --k 8
```

`INPUT` is one of the following:

- an OMR set number such as `6372-1`, downloaded once to `data/omr/`;
- an `.mpd`/`.ldr` model;
- a `.csv` parts list, one `part file, LDraw color code, count` per line;
- a set without an OMR model, which falls back to its Rebrickable inventory; `rebrickable:6372-1` forces this
  (check: arrives with the m12c-rebrickable branch).

Main options:

| option | meaning |
|---|---|
| `--n` / `--k` | candidates to generate / builds to select (defaults 200 / 8) |
| `--shape` | target shape, scaled to the inventory's volume (below) |
| `--generator d2\|wfc` | the bottom-up decoder (default) or constrained WFC (compared method) |
| `--workers` | processes for generation (default: CPU count - 2); `--wfc-workers` caps WFC (memory) |
| `--no-balance`, `--no-connect`, `--no-bridge` | switch off the tip-over check, the one-piece pass, the bridging preference |
| `--max-clutch` | limit on the required clutch per stud in the physics check (default: unbounded) |
| `--seed`, `--out`, `--fresh` | first seed, output folder, discard cached candidates |

`--shape` takes three kinds of input:

1. **A primitive**: `block`, `pyramid`, `arch`, `mushroom`, `ring`.
2. **A top-down silhouette image**: one pixel per stud, where opaque or dark pixels are inside. It is extruded
   `--shape-height` plates. `--height-map` (grey = height in plates) and `--color-map` (preferred colors) are
   optional and must be the same size as the silhouette.
3. **A model**: an `.ldr`/`.mpd` file or an OMR set number, as solid columns by default (`--shape-exact` keeps the
   exact cells), or a BrickGPT structure `brickgpt:<structure id>` from the StableText2Brick test split (a true 3D
   target; `--shape-columns` turns it into solid columns).

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
| M12b | 3D targets, learned proposal, slopes and corners (in progress) | (check: m12b results files as they merge) |
| M12c | inventories from Rebrickable, checked against 28 OMR models | (check: `results/m12c_rebrickable.md` after merge) |
| M13 | paper tables, diversity, budget curve, user-study helper | [m13_tables.md](results/m13_tables.md), [m13_diversity.md](results/m13_diversity.md) |

## Layout

```
src/brickwfc/   wfc.py, tileset.py (WFC core); bricks/ (parts, decoder, physics, style, inventory, shapes);
                alt/ (the pipeline); funnel/ (verify, dedupe, judge, select, diversity); ldraw/ (IO, OMR fetch);
                experiments/ (drivers for the results)
tests/          pytest
results/        write-ups and summary data of every experiment
paper/          LaTeX sources (powershell -File paper/build.ps1)
docs/           reproduce.md
```
