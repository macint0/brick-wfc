# M9 — building from a real set's parts (partial: 7 of 10 sets)

Reproduce / finish (resumable; skips finished set × condition pairs):

```
python -m brickwfc.experiments.inventory --seeds 20 --out out/m9
```

The run was stopped by low system memory after 7 sets (10134 has only A_filter; 10159 and 10170 did not
run). Raw data for the finished part: `m9_inventory_summary.json` (this folder).

## Setup

- **Inventory**: every 1×1 / 1×2 / 2×2 / 2×4 plate in the set's OMR model, counted per color in any
  position or orientation. Other parts are ignored.
- **Grid**: 6 plates tall, square footprint, volume 1.5× the inventory's cell volume.
- **Weights**: tiles only for (part, color) pairs in the inventory, weighted by the cells they would cover;
  the empty tile's weight is set so the expected solid share of the grid is 1/1.5 ≈ the inventory volume.
  The same weights drive the bottom-up builder.
- **Conditions** (20 seeds per set; same seeds):
  - **A_filter**: WFC + support constraint; inventory checked only afterwards.
  - **B_inventory**: WFC + support + `InventoryConstraint`, with up to 1000 backtracks per attempt
    (without backtracking, restarts made one build take 1–100 s; see below).
  - **D_bottom_up**: random bottom-up placement that skips used-up parts (no WFC).
- **Valid** = within the inventory and satisfies the ≥1-stud support rule. Physics: stands on a table
  with some clutch (`bricks/physics.py`). Utilization = share of the inventory's parts used.

## Mean over the 7 completed sets

| condition | within inventory % | valid % | phys. stable (any clutch) % | utilization % | time/build (s) |
|---|---|---|---|---|---|
| A_filter | 2.1 | 2.1 | 75.0 | 83.8 | 0.423 |
| B_inventory | 100.0 | 100.0 | 82.9 | 93.2 | 0.992 |
| D_bottom_up | 100.0 | 100.0 | 98.6 | 99.9 | 0.012 |

## Per set

| set | condition | parts | grid | within inventory % | valid % | phys. any clutch % | utilization % | attempts/run | backtracks/run | time/run (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| 10015-1 | A_filter | 24 | 4x4x6 | 15 | 15 | 95 | 87.5 | 1.60 | 0.0 | 0.126 |
| 10015-1 | B_inventory | 24 | 4x4x6 | 100 | 100 | 80 | 94.6 | 1.05 | 52.4 | 0.207 |
| 10015-1 | D_bottom_up | 24 | 4x4x6 | 100 | 100 | 100 | 100.0 | 1.00 | 0.0 | 0.004 |
| 10019-1 | A_filter | 81 | 9x9x6 | 0 | 0 | 65 | 83.6 | 1.80 | 0.0 | 1.117 |
| 10019-1 | B_inventory | 81 | 9x9x6 | 100 | 100 | 95 | 90.9 | 1.10 | 121.5 | 1.719 |
| 10019-1 | D_bottom_up | 81 | 9x9x6 | 100 | 100 | 100 | 100.0 | 1.00 | 0.0 | 0.023 |
| 10020-1 | A_filter | 66 | 7x7x6 | 0 | 0 | 70 | 88.1 | 1.00 | 0.0 | 0.424 |
| 10020-1 | B_inventory | 66 | 7x7x6 | 100 | 100 | 90 | 95.7 | 1.50 | 546.3 | 2.178 |
| 10020-1 | D_bottom_up | 66 | 7x7x6 | 100 | 100 | 95 | 100.0 | 1.00 | 0.0 | 0.014 |
| 10037-1 | A_filter | 20 | 5x5x6 | 0 | 0 | 65 | 83.8 | 1.05 | 0.0 | 0.213 |
| 10037-1 | B_inventory | 20 | 5x5x6 | 100 | 100 | 70 | 99.0 | 1.20 | 298.8 | 1.420 |
| 10037-1 | D_bottom_up | 20 | 5x5x6 | 100 | 100 | 100 | 100.0 | 1.00 | 0.0 | 0.007 |
| 10124-1 | A_filter | 44 | 7x7x6 | 0 | 0 | 95 | 82.5 | 1.00 | 0.0 | 0.414 |
| 10124-1 | B_inventory | 44 | 7x7x6 | 100 | 100 | 80 | 91.4 | 1.05 | 53.5 | 0.527 |
| 10124-1 | D_bottom_up | 44 | 7x7x6 | 100 | 100 | 100 | 100.0 | 1.00 | 0.0 | 0.013 |
| 10128-1 | A_filter | 26 | 5x5x6 | 0 | 0 | 65 | 77.1 | 1.10 | 0.0 | 0.199 |
| 10128-1 | B_inventory | 26 | 5x5x6 | 100 | 100 | 85 | 88.3 | 1.00 | 2.7 | 0.210 |
| 10128-1 | D_bottom_up | 26 | 5x5x6 | 100 | 100 | 95 | 99.4 | 1.00 | 0.0 | 0.007 |
| 10133-1 | A_filter | 59 | 7x7x6 | 0 | 0 | 70 | 84.0 | 1.25 | 0.0 | 0.469 |
| 10133-1 | B_inventory | 59 | 7x7x6 | 100 | 100 | 80 | 92.9 | 1.05 | 69.1 | 0.684 |
| 10133-1 | D_bottom_up | 59 | 7x7x6 | 100 | 100 | 100 | 100.0 | 1.00 | 0.0 | 0.014 |
| 10134-1 | A_filter | 64 | 10x10x6 | 0 | 0 | 75 | 78.6 | 1.60 | 0.0 | 1.323 |

## Findings

1. **Post-filtering for the inventory fails.** Plain WFC (with support) almost never stays within a set's
   parts: 2.1% of builds on average, 0% on 6 of 7 sets.
2. **The inventory constraint in propagation works, but needs backtracking.** B is within the inventory
   and support-valid in 100% of builds and uses 93% of the parts. Without backtracking it restarted
   5–80 times per build (≈1–100 s per build on 10037 / 10129); with up to 1000 backtracks it needs
   ~1.1 attempts. The cause: the count limit is global, so WFC runs out of a part late in a build when a
   cell must still be solid to hold up a part above it.
3. **The bottom-up builder is better on every measure here.** Same 100% validity, 99.9% utilization vs
   93.2%, physically stable 98.6% vs 82.9%, and ~80× faster (0.012 s vs 0.99 s). Because it builds from
   the ground up and can always leave a cell empty, a global part budget costs it nothing.
4. **Decision checkpoint (see `CLAUDE.md`):** with inventory added, WFC still does not beat the simple
   baseline on any metric. Only the target-shape experiment (M11) and learned style (M10) remain as
   places where WFC could win.

## Notes

- The three largest sets (10018, 10129, 10143) are excluded: one WFC build takes 20 s to minutes there.
- Backtracking is chronological and bounded (last 64 collapses, ≤1000 undos per attempt); smarter
  backtracking might narrow the speed gap but not the robustness/utilization gap.
