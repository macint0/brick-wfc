# brick-wfc — alternate brick builds with constraint-aware Wave Function Collapse

## Context

Side project by Mac (final-year CPE student, graphics/rendering focus). Long-term target: a short paper /
workshop paper.

**Goal:** given a parts inventory (an existing set, or any collection of bricks) and optionally a target
shape, generate **new alternate builds** that use only those parts, stand up, and look good. Style is
learned from real official sets; physical and inventory guarantees come from constraints.

**Research contribution we're aiming for:** push hard constraints into WFC's *propagation* step, so invalid
builds are pruned during generation instead of filtered afterwards:
- **stability** — every part is supported (M6), checked against a physics-based verifier (M7);
- **inventory** — never use more of a part than the input provides (M9);
- **shape** — stay inside a target shape (M11).

Learning from real sets (M10) supplies taste: part/color statistics, local placement rules, and a judge.
The generate → verify → dedupe → judge → select funnel (M3) picks the best candidates.

**WFC is on trial, not assumed.** A random bottom-up builder (`bricks/bottomup.py`, baseline D) satisfies
the support rule trivially, so every experiment reports it next to WFC, and the funnel treats the
generator as pluggable. **Decision checkpoint after M9 + M11:** if the bottom-up builder matches WFC on
stability, inventory use, shape fill and style at lower cost, WFC stops being the centrepiece and the
paper becomes about alternate builds + the funnel, comparing generators. If WFC wins under the combined
constraints (its propagation sees dead ends early), that is the paper's main result.

**Checkpoint status (2026-10-07, after M6, M7, M9 and the M11 quick test):** the bottom-up builder matches or
beats WFC on stability, physics, inventory validity/utilization and speed (10–100×). WFC's only measured
win is filling shapes with large overhangs (at the cost of grip).

**Decision (Mac, 2026-10-08): pivot.** The bottom-up builder is the main generator; WFC (with its
constraints) is a compared method. The paper is about alternate builds from an inventory + the funnel,
comparing generators. Keep reporting WFC next to the bottom-up builder in every experiment. The full M11
run (shape + inventory) confirmed it: the any-offset bottom-up builder (D2) beats WFC there too.

**Notes (2026-10-08):**
- **3D check done:** Mac opened `out/check/orientation_check.ldr` and the M5/M6 builds in a viewer; the
  part orientation (3023/3020 long along LDraw X) and the builds look right.
- Package is installed editable (`pip install -e ".[dev]"`); no `PYTHONPATH=src` needed.
- Mac's PC runs low on memory during long experiments; experiments are resumable — rerun the same command.

**Positioning vs BrickGPT** (closest prior work): BrickGPT generates from *text* with a fine-tuned LLM
trained on ShapeNet-derived builds, and enforces stability by *rollback* (98.8% stable, ~40 s/build on GPU).
We generate from an *inventory* (+ optional shape), learn from *real official sets*, guarantee constraints
*by construction*, and run in well under a second per candidate on CPU without training.

Inspiration (credit, not a citation source): "Generate, Filter, Judge, Select" essay —
https://content.moldandyeast.com/forage/y6fmx6n4

## Working rules for Claude Code

- Work **one milestone at a time**. When a milestone's "Done when" passes, stop and summarize; don't start the next one unasked.
- Python 3.11+, `numpy`, `Pillow`, `scipy` (LP solver for physics, M7+), `pytest`. Ask before adding any other dependency.
- Every random choice goes through a seeded `numpy.random.Generator` passed in explicitly. Same seed → same output.
- Type hints, small modules, no global state. Prefer clear code over clever code — this will be read by reviewers.
- Every milestone ships with tests. Run `pytest` before declaring done.
- Log per-run stats: attempts, contradictions, cells collapsed, wall time. These become paper metrics later.
- Don't use the LEGO trademark in names, package, or output branding. Use "brick".
- Commit after each milestone. No Claude co-author / session trailers in commits or PRs.
- Long experiments must save results incrementally and be resumable (runs can be killed under memory pressure).
- Experiments run in parallel across seeds/sets (`ProcessPoolExecutor`, `--workers`, default `cpu_count - 2`;
  Mac's PC: 12 logical cores, 16 GB). Output must be identical to a serial run (per-seed `Generator`, results
  written in plan order). Memory-heavy WFC jobs get their own smaller cap (`--wfc-workers`).
- Downloaded third-party models (LDraw OMR) live in `data/` (gitignored); never commit them.

## Repo layout

```
brick-wfc/
  CLAUDE.md
  pyproject.toml
  src/brickwfc/
    wfc.py          # core solver: domains, entropy, collapse, propagate, Constraint hook
    tileset.py      # tiles, topology (2D/3D), adjacency rules, border masks, weights
    learn.py        # learn rules/weights from 2D example grids
    gridio.py       # 2D grid CSV/PNG IO
    render2d.py     # 2D grid -> PNG, contact sheets
    render3d.py     # isometric preview of 3D builds
    funnel/         # features, verify, dedupe, judge, select, pipeline
    bricks/         # parts, multi-cell tiles, support/stability, voxelize, learning from sets
    ldraw/          # .ldr export, .mpd parsing, OMR fetch
    experiments/    # drivers that produce the paper's tables
  examples/         # tiny example maps / rule JSONs
  tests/
  data/             # downloaded OMR models (gitignored)
  out/              # generated images and results (gitignored)
```

## Core WFC spec (M1 must follow this)

- Grid of cells; each cell has a **domain**: boolean array `domain[y, x, t]` over tile ids `t`.
- Start: all True. Done: every cell has exactly one True.
- **Adjacency:** `compat[d][t]` = boolean mask of tiles allowed in direction `d` (N/E/S/W) next to tile `t`. Rules must be symmetric (if A allows B to the east, B allows A to the west) — validate on load.
- **Observe:** choose the uncollapsed cell with **lowest weighted Shannon entropy**
  $H = \log\sum w_t - \frac{\sum w_t \log w_t}{\sum w_t}$ over remaining tiles; break ties with tiny seeded noise.
- **Collapse:** sample one remaining tile with probability ∝ weight `w_t`.
- **Propagate:** queue-based (AC-3 style). Pop a cell, for each neighbor remove tiles not supported by any remaining tile in the popped cell; if the neighbor's domain shrank, push it.
- **Contradiction:** any domain becomes empty → restart with the next seed (max attempts configurable). Backtracking is a later optimization, not M1.
- **Non-pairwise constraints** (M6+): objects implementing `Constraint.prune(wave, changed)` run after AC-3 inside `Wave.settle`, alternating with AC-3 until a fixpoint. They must be sound: only remove tiles that cannot appear in any valid completion.

## Milestones

### Done

- **M0 — Setup.** Package skeleton, pytest, `.gitignore`.
- **M1 — 2D WFC, hand-written rules.** Terrain tileset, CLI, tests (a)–(d), 100-run benchmark.
- **M2 — Learn rules + weights from an example.** Learning from an M1 output recovers the exact rule set.
- **M3 — Funnel v0 (2D).** One command runs generate → verify → dedupe → judge → select with stage counts.
- **M4 — 3D grid, 1×1 plates.** Support as a vertical adjacency rule; `.ldr` export; isometric preview.
- **M5 — Multi-cell parts.** 1×1, 1×2, 2×2, 2×4 plates; integrity via adjacency + border masks; 100-build integrity test.
- **M6 — Stability-aware propagation.** `SupportConstraint` in propagation; A–D comparison over 1000 seeds
  (`results/m6_stability.md`). Post-filtering fails at scale; B is 100% stable but the bottom-up
  baseline D is too, 27× faster.
- **M7 — Physics-based verifier.** `bricks/physics.py` (LP: required clutch per stud; table or baseplate);
  physics columns for A–D (`results/m7_physics.md`). The ≥1-stud rule overstates stability; all
  failures are tip-overs; B depends on grip more than D. Follow-ups listed there (tip-over check in
  propagation, cantilever limits).
- **M9 — Inventory constraint.** `bricks/inventory.py` (`InventoryConstraint`), bounded backtracking in
  `wfc.solve_attempt`, 10 real sets (`results/m9_inventory.md`). Post-filter 1.5% valid; WFC + inventory
  100% valid, 93% of parts used, 1.4 s/build; bottom-up 100% valid, 99.9% used, 99% physically stable,
  0.014 s/build.
- **M11 — Target shape.** `bricks/shapes.py` (`ShapeConstraint`, primitives, `sized_for` scales a shape to an
  inventory's volume, IoU), bottom-up `allowed` mask. Quick test, shape only (`results/m11_shape_quick.md`),
  and shape + inventory on 10 sets × 5 shapes (`experiments/shape_inventory.py`,
  `results/m11_shape_inventory.md`): every build valid for every generator. WFC beats the original
  bottom-up builder D on fill (73% vs 68%), but `BottomUpBuilder(any_offset=True)` (**D2**: a part may
  cover the visited cell with any of its cells) beats both: 78% fill, best utilization and physics, 20×
  faster than WFC. WFC keeps a small edge on overhangs (mushroom 53% vs 50%) at the cost of grip.
  **Use D2 as the bottom-up generator from here on**; D stays for reproducing earlier tables.
  Not done: shapes from an `.ldr` model or heightmap PNG (only primitives so far).
- **M8 — Part library.** `parts.CATALOG`: 63 rectangular plates, bricks (3 layers) and tiles (no studs),
  including lookalikes (2877, 6141, 2412b, …) kept as their own parts. Integrity in all 6 directions, nothing
  on tiles, support needs a stud, physics knows bricks and tiles. Usable share of the 20 OMR sets: 8% → 51%
  (`results/m8_parts.md`, `experiments/coverage.py`). Bottom-up builds full inventories (746 parts) in 2–5 s;
  WFC does not scale to full inventories yet. `PLATE_FILES` keeps M7/M9/M11 reproducible.
  Mac checked `out/check/catalog_check.ldr` in Studio (2026-10-08): sizes and orientations look right.
- **M9b — Inventory with the full catalog + set selection.** `experiments/inventory.py --catalog full`
  (`results/m9b_inventory_catalog.md`): builds use 35–67% of each set's parts; bottom-up D/D2 100% valid,
  99.5% used, up to 746 parts in ≤ 4.4 s; WFC + inventory (`wfc.run(time_limit_s=30)`) 2.5% valid, 0/20 on
  7 of 8 sets (late inventory dead ends + raw cost; fixes listed there, not attempted). D2 stands 83.5%
  (bricks tip over more). `experiments/sets.py`: 28 building sets for M10 (≥ 50% recognized, ≥ 50 parts,
  ≥ 50% of recognized parts on the grid, no re-releases; `results/sets_selection.md`).
- **M10 — Learned style.** `bricks/style.py`: contact statistics from 28 real sets (P(part on part),
  P(part beside part), same-color rates, support counts, part/color frequencies), `StyleBias` (likelihood
  ratios; `BottomUpBuilder(style=)`, `wfc.run(bias=)`), and the judge = -divergence of a build's contact
  statistics from the learned ones (a per-contact likelihood is gamed by repetition; the divergence is
  size-dependent, so compare size-matched: `style.size_matched`). `experiments/style.py` (4-fold CV, 21
  training sets, parallel workers; `results/m10_style.md`): learned style moves builds closer to held-out
  sets for D2 (23/28 sets with X's parts, 25/28 without counts) and WFC (12/13). Under the judge, D2 beats
  WFC on 13/13 sets at ~1/100 of the time. Contacts help more than frequencies when counts are fixed.
- **M12 — Alternate-build pipeline.** `python -m brickwfc.alt SET|parts.csv|model.mpd [--shape ...] [--n] [--k]`
  (`src/brickwfc/alt/`): generate with D2 + learned style → verify (integrity, inventory, support, shape, physics
  on a table, size floor, one piece) → dedupe → judge (size-matched) → select top-k; writes `build_XX.ldr` with one
  `0 STEP` per layer, previews, `sheet.png`, `stats.json`. Mac stepped through a build in Studio (2026-10-08).
  Pipeline defaults, each by construction in `BottomUpBuilder`: `balanced=True` (no cluster's centre of mass
  outside its ground hull; `bricks/balance.py`, exact vs the LP; physics pass 7% → 100%), `connect=True` with
  `--connect-rounds 10` (keep the largest stud-connected cluster, return the rest, refill; one-piece 0.5% → 100%),
  physical-cube default grid. `physics.table_clutch`: exact tip-over shortcut + IPM LP (146 s → 5 s worst case).
  Shapes: primitive, silhouette PNG (+ height map, + color map → preferred colors), `.ldr`/set number (heightfield
  unless `--shape-exact`). Demo (`experiments/demo.py`, `results/m12_demo_sheet.png`): one spaceship from six sets
  (1978–2010, 203–1514 parts): 100% valid, fill 52–74%, utilization 66–92%; WFC 0/50 within 30 s. Write-up and open
  points: `results/m12_pipeline.md` (connectivity costs 2–20 fill points, most on 1-wide-brick sets; up to 140 s per
  candidate on the largest set; `--max-clutch` uncalibrated).

### M12b — 3D targets and looks (Mac, 2026-10-08: builds are recognizable but not good enough)
Order matters; commit each step with a before/after figure on the same six demo sets.
1. **True 3D targets.** Inputs are extruded heightfields today; the generator is already 3D. Add: a loader for
   BrickGPT's published structures as target masks (fairest head-to-head: same object, their unlimited bricks vs
   our real inventory); a mesh voxelizer (`trimesh`, approved by Mac) for `.obj`/`.stl` at a chosen resolution,
   scaled to the inventory; `--hollow` (shell of 2 cells + internal supports); overhang handling measured (fill,
   stability) with `--max-clutch` and/or builder-added support columns.
2. **Mirror symmetry** in the bottom-up builder (mirrored pairs when the inventory has two; fallback to single).
3. **Clean skins**: prefer the largest fitting part on exposed surfaces, align seams across rows.
4. **Slopes and corner parts** in the catalog (sloped top face accepts nothing; L-shaped footprints).
Not now: style-bias tuning, color logic, WFC. **Done when:** the six-set demo re-rendered with a 3D target
looks clearly better side by side, every build still valid/stable/one piece, and the per-set coverage rises.

### M13 — Experiments for the paper
- Baselines: random bottom-up placement (D), plain WFC + post-filter, constraint-aware WFC, BrickGPT
  outputs where comparable (shape-only, no inventory). Apply the decision checkpoint above.
- Metrics: valid %, stable % (simple + physics), inventory utilization, shape IoU, time per accepted
  design, diversity (mean pairwise distance, effective number of distinct designs), contradiction rate.
- Small user study: pairwise rankings of alternate builds (Bradley–Terry).

## References

- WFC (Gumin): https://github.com/mxgmn/WaveFunctionCollapse
- Model synthesis (Merrell) — WFC's precursor: https://en.wikipedia.org/wiki/Model_synthesis
- Large-scale WFC: https://arxiv.org/abs/2308.07307
- Legolization — optimizing brick designs for stability: https://www.researchgate.net/publication/283432969_Legolization_optimizing_LEGO_designs
- BrickGPT — stable, buildable brick designs from text (ICCV 2025): https://arxiv.org/abs/2505.05469
- LDraw file format: https://www.ldraw.org/article/218.html
- LDraw Official Model Repository: https://library.ldraw.org/omr
