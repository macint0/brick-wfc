# brick-wfc — stability-aware Wave Function Collapse for brick structures

## Context

Side project by Mac (final-year CPE student, graphics/rendering focus). Goal: a generator that produces
LEGO-style brick builds using Wave Function Collapse (WFC), wrapped in a generate → verify → dedupe →
judge → select funnel. Long-term target: a short paper / workshop paper.

**Research contribution we're aiming for:** make WFC *stability-aware* — push physical support /
connectivity constraints into WFC's propagation step so unstable builds are pruned during generation,
not filtered afterwards. Everything else (funnel, judges) is supporting infrastructure.

Inspiration (credit, not a citation source): "Generate, Filter, Judge, Select" essay —
https://content.moldandyeast.com/forage/y6fmx6n4

## Working rules for Claude Code

- Work **one milestone at a time**. When a milestone's "Done when" passes, stop and summarize; don't start the next one unasked.
- Python 3.11+, `numpy`, `Pillow`, `pytest`. Ask before adding any other dependency.
- Every random choice goes through a seeded `numpy.random.Generator` passed in explicitly. Same seed → same output.
- Type hints, small modules, no global state. Prefer clear code over clever code — this will be read by reviewers.
- Every milestone ships with tests. Run `pytest` before declaring done.
- Log per-run stats: attempts, contradictions, cells collapsed, wall time. These become paper metrics later.
- Don't use the LEGO trademark in names, package, or output branding. Use "brick".

## Repo layout (target)

```
brick-wfc/
  CLAUDE.md
  pyproject.toml
  src/brickwfc/
    wfc.py          # core solver: domains, entropy, collapse, propagate
    tileset.py      # tiles, adjacency rules, weights (hand-written or learned)
    learn.py        # learn rules/weights from example grids (later: LDraw)
    render2d.py     # grid -> PNG
    funnel/         # verify.py, dedupe.py, judge.py, select.py
    bricks/         # 3D: parts, multi-cell tiles, stability (M4+)
    ldraw/          # .ldr/.mpd parsing (M7)
  examples/         # tiny example maps / rule JSONs
  tests/
  out/              # generated images (gitignored)
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

## Milestones

### M0 — Setup
`pyproject.toml`, package skeleton, pytest running, `.gitignore` (`out/`).
**Done when:** `pytest` passes on an empty smoke test.

### M1 — 2D WFC, hand-written rules
- Tileset from JSON: tile names, colors, weights, adjacency pairs.
- Example tileset: water / sand / grass / forest (water–sand, sand–grass, grass–forest allowed; same–same allowed; water–grass, water–forest, sand–forest NOT allowed).
- CLI: `python -m brickwfc.run --tiles examples/terrain.json --size 32x32 --seed 1 --out out/m1.png`.
**Done when:**
- Tests: (a) every finished grid satisfies every adjacency rule; (b) 1D sanity case: 3 cells, tiles W/S/F, rules W–S, S–F (+ same–same) — collapsing cell 0 to W removes F from cell 1; (c) same seed → identical output; (d) contradiction triggers a restart and is counted.
- 100 runs at 32×32 complete; print success rate, mean attempts, mean time.

### M2 — Learn rules + weights from an example
- Input: a small example grid (PNG where each color = a tile, or a CSV of tile ids).
- Learn: tile frequencies → weights; observed neighbor pairs → adjacency rules.
**Done when:** learning from an M1 output and regenerating gives the same rule set; outputs visually resemble the example.

### M3 — Funnel v0 (2D)
- **Generate** N designs (default 1000).
- **Verify:** hard checks with a signed margin (e.g. "all land tiles form one connected region" via BFS; margin = size of largest region / total land).
- **Dedupe:** feature vector (tile histogram + region count + perimeter); drop if L2 distance to any kept design < threshold.
- **Judge:** heuristic score function (pluggable interface so an LLM/learned judge can replace it later).
- **Select:** greedy top-k (default 12) maximizing `score + λ · min_distance_to_selected`.
- Output: contact-sheet PNG of the k picks + a stats JSON (counts surviving each stage).
**Done when:** one command runs the whole funnel and prints the stage-by-stage counts.

### M4 — 3D grid, 1×1 plates
- 3D grid at stud resolution: `x, z` = studs, `y` = plate layers. Tiles = empty or 1×1 plate (by color).
- Constraint: a non-empty cell at layer > 0 must have a non-empty cell directly below (simple support).
- Export to LDraw `.ldr` so builds open in LeoCAD / Stud.io. Units: 1 stud = 20 LDU, plate = 8 LDU, brick = 24 LDU; **LDraw −Y is up**.
**Done when:** generated `.ldr` files open correctly in a viewer; no floating plates.

### M5 — Multi-cell parts
- Tile = (part, local offset inside the part, rotation). Parts: 1×1, 1×2, 2×2, 2×4 plates (bricks later).
- Adjacency rules guarantee pieces are whole (offset (0,0) of a 1×2 must have offset (1,0) of the same 1×2 to its east, etc.).
**Done when:** every exported part is complete; tests check piece integrity on 100 random builds.

### M6 — Stability-aware propagation (the research part)
- Move support/connectivity constraints *into propagation*: prune tiles that would leave a part unsupported or disconnected from the ground.
- Keep a post-hoc stability verifier as ground truth (start simple: every part overlaps ≥1 stud with a part below or the ground; later a static-equilibrium check — see Legolization / BrickGPT).
- Compare: (A) plain WFC + post-filter vs (B) stability-aware WFC. Metrics: stable-design rate, contradictions/restarts, time per stable design.
**Done when:** a results table for A vs B over ≥1000 seeds.

### M7 — Learn from real sets (LDraw OMR)
- Parse `.ldr` / `.mpd` from the LDraw Official Model Repository, voxelize to the M5 tile representation, learn weights/rules.
**Done when:** weights learned from ≥10 official sets; generated builds use the learned distribution.

### M8 — Experiments for the paper
- Baselines: random placement, unconstrained WFC, stability-aware WFC, (optional) BrickGPT outputs.
- Metrics: valid %, stable %, buildable %, time per design, diversity (mean pairwise distance, effective number of distinct designs), contradiction rate.
- Optional: small user study ranking outputs pairwise (Bradley–Terry).

## References

- WFC (Gumin): https://github.com/mxgmn/WaveFunctionCollapse
- Model synthesis (Merrell) — WFC's precursor: https://en.wikipedia.org/wiki/Model_synthesis
- Large-scale WFC: https://arxiv.org/abs/2308.07307
- Legolization — optimizing brick designs for stability: https://www.researchgate.net/publication/283432969_Legolization_optimizing_LEGO_designs
- BrickGPT — stable, buildable brick designs from text (ICCV 2025): https://arxiv.org/abs/2505.05469
- LDraw file format: https://www.ldraw.org/article/218.html
- LDraw Official Model Repository: https://library.ldraw.org/omr
