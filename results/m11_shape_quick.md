# M11 quick test — filling a target shape: WFC vs the bottom-up builder

Reproduce (about 4 minutes; resumable):

```
python -m brickwfc.experiments.shape --seeds 100 --out out/m11
```

Raw data: `m11_shape_quick_summary.json` (this folder). This is the quick test agreed as the WFC decision
checkpoint; it uses target shapes only (no inventory). The full M11 milestone (shape + a real set's parts)
is not done.

## Setup

- Grid 8×8 studs × 6 plates; plates 1×1, 1×2, 2×2, 2×4 in red and blue; empty weight 0.2 (both
  generators try to fill the shape).
- Shapes (`bricks/shapes.py`): **block** (whole grid), **pyramid** (stepped), **arch** (two 2-stud-wide
  pillars at the ends + a 2-layer span on top), **mushroom** (central 2×2 stem + full-width 2-layer cap:
  a large overhang), **ring** (hollow tower, 2-stud walls).
- **B_wfc**: WFC + support + `ShapeConstraint` (cells outside the shape stay empty), up to 1000 backtracks.
  **D_bottom_up**: random bottom-up placement; parts must lie entirely inside the shape.
- Fill = share of the shape's cells that are solid. Physics on a table (`bricks/physics.py`).

## Results (100 seeds each)

| shape | condition | fill % | min fill % | stable % | phys. any clutch % | phys. clutch ≤10 % | time/run (s) |
|---|---|---|---|---|---|---|---|
| block | B_wfc | 93.4 | 89.8 | 100 | 98 | 97 | 0.546 |
| block | D_bottom_up | **97.1** | 95.1 | 100 | 100 | 100 | 0.024 |
| pyramid | B_wfc | 93.3 | 86.7 | 100 | 100 | 100 | 0.187 |
| pyramid | D_bottom_up | **97.3** | 92.5 | 100 | 98 | 98 | 0.008 |
| arch | B_wfc | **90.4** | 83.2 | 100 | 93 | 54 | 0.331 |
| arch | D_bottom_up | 87.7 | 78.9 | 100 | 89 | 46 | 0.019 |
| mushroom | B_wfc | **55.1** | 40.3 | 100 | 82 | 5 | 0.155 |
| mushroom | D_bottom_up | 41.4 | 25.0 | 100 | 78 | 32 | 0.016 |
| ring | B_wfc | 92.7 | 86.1 | 100 | 100 | 100 | 0.393 |
| ring | D_bottom_up | **96.6** | 92.0 | 100 | 99 | 99 | 0.020 |

No build placed a cell outside its shape; every build was whole and satisfied the support rule.

Timing note: by mistake two copies of this run executed at the same time, each writing all 1000 runs
(`out/m11/runs.jsonl` has every record twice). Builds are seeded, and the two copies agree on every
non-timing field. Times above are from `summary.json` and were measured under that doubled load, equally
for both conditions, so ratios hold but absolute times are somewhat high.

## Findings

1. **Shapes that are supported from below (block, pyramid, ring): the bottom-up builder wins.** It fills
   ~4 points more of the shape and is 10–25× faster, with equal physical stability.
2. **Shapes with overhangs (arch, mushroom): WFC fills more.** +2.7 points on the arch, **+13.7 points on
   the mushroom** (55.1% vs 41.4%), with slightly higher "stands with some clutch" rates. This is the first
   measurement where WFC beats the baseline: its look-ahead plans the cap/span as a whole, while the
   greedy builder commits layer by layer and leaves gaps it can no longer bridge.
3. **But WFC's extra fill relies on grip.** On the mushroom only 5% of WFC builds stand with clutch ≤10 vs
   32% for bottom-up: WFC fills the cap with long cantilevers held by a few studs.
4. **Caveat:** the bottom-up builder is deliberately simple (random cell order, one pass per layer). A
   smarter greedy (prefer large parts that reach supports, several passes) might close the overhang gap,
   so this edge is not yet robust.

## What this means for the decision checkpoint

Across M6 (support), M7 (physics), M9 (inventory) and this test, WFC wins only on **covering large
overhangs**, and pays for it in speed (~10×) and in how much grip its builds need. Everywhere else the
bottom-up builder is better. See the summary in `CLAUDE.md`.
