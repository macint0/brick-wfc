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
  *Still to do: open the generated `.ldr` files in LeoCAD / Stud.io to confirm they look right.*
- **M5 — Multi-cell parts.** 1×1, 1×2, 2×2, 2×4 plates; integrity via adjacency + border masks; 100-build integrity test.
- **M6 — Stability-aware propagation.** `SupportConstraint` in propagation; A–D comparison over 1000 seeds
  (`results/m6_stability.md`). Post-filtering fails at scale; B is 100% stable but the bottom-up
  baseline D is too, 27× faster.
- **M7 — Physics-based verifier.** `bricks/physics.py` (LP: required clutch per stud; table or baseplate);
  physics columns for A–D (`results/m7_physics.md`). The ≥1-stud rule overstates stability; all
  failures are tip-overs; B depends on grip more than D. Follow-ups listed there (tip-over check in
  propagation, cantilever limits).

### M8 — Part library: bricks, plates, tiles
- Common sizes: bricks and plates 1×1, 1×2, 1×4, 2×2, 2×4 (+ 1×6, 2×6 if cheap); tiles 1×1, 1×2, 2×2.
- Bricks span 3 plate layers → vertical integrity rules, like M5's horizontal ones.
- Tiles have no studs → nothing may sit on top of a tile.
- No slopes yet (non-box geometry); revisit later.
**Done when:** integrity + stability tests pass on 100 random builds per part family; `.ldr` exports
use the right part files and heights (brick = 24 LDU).

### M9 — Inventory constraint
- Input: a parts list — a set from the OMR (`.mpd` → part/color counts via `ldraw/mpd.py`) or a JSON list.
  Parts outside the supported library are reported and ignored.
- `InventoryConstraint`: count placed parts per (part, color) via their anchor cells; when a count hits its
  limit, prune that (part, color)'s tiles everywhere.
- Metrics: inventory utilization % (parts used / parts available), stable %, restarts.
**Done when:** on ≥10 real sets, every generated build stays within the inventory (verified post hoc), with
utilization reported.

### M10 — Learn from real sets
- Reuse the M7-in-progress code (fetch, flatten, voxelize, coverage weights).
- Learn: part/color weights; directional co-occurrence (which part/color sits next to or on which) as
  soft weights; a learned judge scoring "looks like a real set" (start simple: likelihood under the learned
  co-occurrence statistics).
- Pick plate/brick-heavy sets on purpose (Town / City buildings, Creator) and report how much of each
  set is recognized.
- Optional: use `0 STEP` data (present in some OMR files) — e.g. sub-assembly statistics.
**Done when:** weights, rules and judge are learned from ≥20 sets, and generated builds score closer to
real sets than uniform-weight builds under held-out statistics.

### M11 — Target shape
- Input: a voxel shape on the stud/plate grid — from an `.ldr` model, a heightmap PNG, or simple
  primitives.
- Constraint: solid only inside the shape; encourage filling it (weights near the shape surface).
- Metrics: shape IoU / fill %, plus everything above.
**Done when:** "build shape S from set X's parts" produces stable, inventory-feasible builds with reported
IoU.

### M12 — Alternate-build pipeline
- One command: set number or parts list (+ optional shape) → 3D funnel (generate → verify stability,
  inventory, integrity → dedupe → judge → select top-k).
- Output: `.ldr` files with `0 STEP` building instructions (layer by layer), isometric previews, contact
  sheet, stats JSON.
**Done when:** the command produces k alternate builds for a given set with instructions that open in a viewer.

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
