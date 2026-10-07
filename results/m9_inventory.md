# M9 — building from a real set's parts (10 OMR sets)

Reproduce (resumable; skips finished set × condition pairs):

```
python -m brickwfc.experiments.inventory --seeds 20 --out out/m9
```

Raw data: `m9_inventory_summary.json` (this folder). The first run was stopped by low system memory after
7 sets and resumed to finish the remaining 3.

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

## Mean over sets (each set weighted equally)

| condition | sets | within inventory % | valid % | phys. any clutch % | utilization % | attempts/run | time/run (s) |
|---|---|---|---|---|---|---|---|
| A_filter | 10 | 1.5 | 1.5 | 73.5 | 83.8 | 1.25 | 0.479 |
| B_inventory | 10 | 100.0 | 100.0 | 83.0 | 93.1 | 1.20 | 1.408 |
| D_bottom_up | 10 | 100.0 | 100.0 | 99.0 | 99.9 | 1.00 | 0.014 |

## Per set

| set | condition | parts | grid | seeds | within inventory % | valid % | phys. any clutch % | phys. clutch <=10 % | utilization % | attempts/run | backtracks/run | time/run (s) | time/valid (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10015-1 | A_filter | 24 | 4x4x6 | 20 | 15.0 | 15.0 | 95.0 | 80.0 | 87.5 | 1.60 | 0.0 | 0.126 | 0.840 |
| 10015-1 | B_inventory | 24 | 4x4x6 | 20 | 100.0 | 100.0 | 80.0 | 65.0 | 94.6 | 1.05 | 52.4 | 0.207 | 0.207 |
| 10015-1 | D_bottom_up | 24 | 4x4x6 | 20 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 1.00 | 0.0 | 0.004 | 0.004 |
| 10019-1 | A_filter | 81 | 9x9x6 | 20 | 0.0 | 0.0 | 65.0 | 40.0 | 83.6 | 1.80 | 0.0 | 1.117 | inf |
| 10019-1 | B_inventory | 81 | 9x9x6 | 20 | 100.0 | 100.0 | 95.0 | 35.0 | 90.9 | 1.10 | 121.5 | 1.719 | 1.719 |
| 10019-1 | D_bottom_up | 81 | 9x9x6 | 20 | 100.0 | 100.0 | 100.0 | 90.0 | 100.0 | 1.00 | 0.0 | 0.023 | 0.023 |
| 10020-1 | A_filter | 66 | 7x7x6 | 20 | 0.0 | 0.0 | 70.0 | 55.0 | 88.1 | 1.00 | 0.0 | 0.424 | inf |
| 10020-1 | B_inventory | 66 | 7x7x6 | 20 | 100.0 | 100.0 | 90.0 | 60.0 | 95.7 | 1.50 | 546.3 | 2.178 | 2.178 |
| 10020-1 | D_bottom_up | 66 | 7x7x6 | 20 | 100.0 | 100.0 | 95.0 | 90.0 | 100.0 | 1.00 | 0.0 | 0.014 | 0.014 |
| 10037-1 | A_filter | 20 | 5x5x6 | 20 | 0.0 | 0.0 | 65.0 | 50.0 | 83.8 | 1.05 | 0.0 | 0.213 | inf |
| 10037-1 | B_inventory | 20 | 5x5x6 | 20 | 100.0 | 100.0 | 70.0 | 50.0 | 99.0 | 1.20 | 298.8 | 1.420 | 1.420 |
| 10037-1 | D_bottom_up | 20 | 5x5x6 | 20 | 100.0 | 100.0 | 100.0 | 95.0 | 100.0 | 1.00 | 0.0 | 0.007 | 0.007 |
| 10124-1 | A_filter | 44 | 7x7x6 | 20 | 0.0 | 0.0 | 95.0 | 45.0 | 82.5 | 1.00 | 0.0 | 0.414 | inf |
| 10124-1 | B_inventory | 44 | 7x7x6 | 20 | 100.0 | 100.0 | 80.0 | 45.0 | 91.4 | 1.05 | 53.5 | 0.527 | 0.527 |
| 10124-1 | D_bottom_up | 44 | 7x7x6 | 20 | 100.0 | 100.0 | 100.0 | 90.0 | 100.0 | 1.00 | 0.0 | 0.013 | 0.013 |
| 10128-1 | A_filter | 26 | 5x5x6 | 20 | 0.0 | 0.0 | 65.0 | 50.0 | 77.1 | 1.10 | 0.0 | 0.199 | inf |
| 10128-1 | B_inventory | 26 | 5x5x6 | 20 | 100.0 | 100.0 | 85.0 | 80.0 | 88.3 | 1.00 | 2.7 | 0.210 | 0.210 |
| 10128-1 | D_bottom_up | 26 | 5x5x6 | 20 | 100.0 | 100.0 | 95.0 | 95.0 | 99.4 | 1.00 | 0.0 | 0.007 | 0.007 |
| 10133-1 | A_filter | 59 | 7x7x6 | 20 | 0.0 | 0.0 | 70.0 | 35.0 | 84.0 | 1.25 | 0.0 | 0.469 | inf |
| 10133-1 | B_inventory | 59 | 7x7x6 | 20 | 100.0 | 100.0 | 80.0 | 45.0 | 92.9 | 1.05 | 69.1 | 0.684 | 0.684 |
| 10133-1 | D_bottom_up | 59 | 7x7x6 | 20 | 100.0 | 100.0 | 100.0 | 90.0 | 100.0 | 1.00 | 0.0 | 0.014 | 0.014 |
| 10134-1 | A_filter | 64 | 10x10x6 | 20 | 0.0 | 0.0 | 75.0 | 15.0 | 78.6 | 1.60 | 0.0 | 1.323 | inf |
| 10134-1 | B_inventory | 64 | 10x10x6 | 20 | 100.0 | 100.0 | 85.0 | 10.0 | 86.0 | 1.20 | 203.6 | 2.948 | 2.948 |
| 10134-1 | D_bottom_up | 64 | 10x10x6 | 20 | 100.0 | 100.0 | 100.0 | 85.0 | 100.0 | 1.00 | 0.0 | 0.032 | 0.032 |
| 10159-1 | A_filter | 45 | 6x6x6 | 20 | 0.0 | 0.0 | 60.0 | 35.0 | 80.7 | 1.05 | 0.0 | 0.315 | inf |
| 10159-1 | B_inventory | 45 | 6x6x6 | 20 | 100.0 | 100.0 | 95.0 | 55.0 | 93.8 | 1.30 | 328.0 | 2.161 | 2.161 |
| 10159-1 | D_bottom_up | 45 | 6x6x6 | 20 | 100.0 | 100.0 | 100.0 | 95.0 | 100.0 | 1.00 | 0.0 | 0.015 | 0.015 |
| 10170-1 | A_filter | 32 | 5x5x6 | 20 | 0.0 | 0.0 | 75.0 | 75.0 | 92.0 | 1.05 | 0.0 | 0.188 | inf |
| 10170-1 | B_inventory | 32 | 5x5x6 | 20 | 100.0 | 100.0 | 70.0 | 60.0 | 98.6 | 1.50 | 605.8 | 2.028 | 2.028 |
| 10170-1 | D_bottom_up | 32 | 5x5x6 | 20 | 100.0 | 100.0 | 100.0 | 90.0 | 100.0 | 1.00 | 0.0 | 0.007 | 0.007 |

## Findings

1. **Post-filtering for the inventory fails.** Plain WFC (with support) almost never stays within a set's
   parts: 1.5% of builds on average, 0% on 9 of 10 sets.
2. **The inventory constraint in propagation works, but needs backtracking.** B is within the inventory
   and support-valid in 100% of builds and uses 93.1% of the parts. Without backtracking it restarted
   5–80 times per build (≈1–100 s per build on 10037 / 10129); with up to 1000 backtracks it needs
   ~1.1 attempts. The cause: the count limit is global, so WFC runs out of a part late in a build when a
   cell must still be solid to hold up a part above it.
3. **The bottom-up builder is better on every measure here.** Same 100% validity, 99.9% utilization vs
   93.1%, physically stable 99.0% vs 83.0%, and ~100× faster (0.014 s vs 1.41 s). Because it builds from
   the ground up and can always leave a cell empty, a global part budget costs it nothing.
4. **Decision checkpoint (see `CLAUDE.md`):** with inventory added, WFC still does not beat the simple
   baseline on any metric. Only the target-shape experiment (M11) and learned style (M10) remain as
   places where WFC could win.

## Notes

- The three largest sets (10018, 10129, 10143) are excluded: one WFC build takes 20 s to minutes there.
- Backtracking is chronological and bounded (last 64 collapses, ≤1000 undos per attempt); smarter
  backtracking might narrow the speed gap but not the robustness/utilization gap.
