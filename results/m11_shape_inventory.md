# M11 — building a target shape from a real set's parts (10 OMR sets × 5 shapes)

Reproduce (about 11 minutes of build time; resumable — skips finished set × shape × condition batches):

```
python -m brickwfc.experiments.shape_inventory --seeds 20 --export 2 --out out/m11_full
```

Raw data: `m11_shape_inventory_summary.json` (this folder). `--export 2` writes the first two builds of
every batch as `.ldr` + `.png` to `out/m11_full/builds/` (600 files).

## Setup

- **Inventory**: the set's 1×1 / 1×2 / 2×2 / 2×4 plates by color, as in M9 (same 10 sets).
- **Target shape**: the five M11 shapes (block, pyramid, arch, mushroom, ring), scaled per set by
  `shapes.sized_for` so the shape's volume is close to the inventory's cell volume: square footprint, height
  3–8 plates (6 preferred, within 10% of the volume), pillars and stems a quarter of the footprint wide
  (at least 2 studs). Each shape has a minimum footprint that keeps its character (gap under the arch,
  overhang around the stem, hole in the ring), so for the smallest sets the arch and ring are larger than
  the inventory. **Max fill** = min(1, inventory cells / shape cells) is the volume bound on fill.
- **Weights**: tiles for the set's (part, color) pairs weighted by the cells they cover (M9); empty weight
  0.2, so all generators try to fill the shape.
- **Conditions** (20 seeds per set and shape; same seeds and weights):
  - **B_wfc**: WFC + `SupportConstraint` + `ShapeConstraint` + `InventoryConstraint` in propagation,
    up to 1000 backtracks per attempt.
  - **D_bottom_up**: the bottom-up builder used in M6–M11 (a part is tried only with its min corner on the
    visited cell), inside the shape, skipping used-up parts.
  - **D2_bottom_up_any_offset** (new): the same builder, but a part may cover the visited cell with any of
    its cells, so it can reach into a gap from the left or front (`BottomUpBuilder(any_offset=True)`).
- **Valid** = whole parts, within the inventory, nothing outside the shape, support rule satisfied.
  **Fill** = share of the shape's cells that are solid; **IoU** = |solid ∩ shape| / |solid ∪ shape| (equal
  to fill here, because no build places anything outside the shape). Physics on a table (`bricks/physics.py`).

## Results

Every one of the 3000 builds is valid (100% in every row); no build placed a cell outside its shape.

### Mean over sets, per shape

| shape | condition | sets | valid % | fill % | max fill % | IoU % | utilization % | phys. any clutch % | phys. clutch <=10 % | attempts/run | time/run (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| block | B_wfc | 10 | 100.0 | 76.1 | 99.2 | 76.1 | 88.1 | 94.5 | 93.5 | 1.04 | 0.551 |
| block | D_bottom_up | 10 | 100.0 | 73.7 | 99.2 | 73.7 | 87.2 | 100.0 | 99.0 | 1.00 | 0.015 |
| block | D2_bottom_up_any_offset | 10 | 100.0 | 82.7 | 99.2 | 82.7 | 90.3 | 99.5 | 98.5 | 1.00 | 0.021 |
| pyramid | B_wfc | 10 | 100.0 | 81.3 | 97.3 | 81.3 | 89.2 | 98.5 | 98.0 | 1.00 | 0.301 |
| pyramid | D_bottom_up | 10 | 100.0 | 74.9 | 97.3 | 74.9 | 86.6 | 100.0 | 100.0 | 1.00 | 0.016 |
| pyramid | D2_bottom_up_any_offset | 10 | 100.0 | 86.5 | 97.3 | 86.5 | 90.8 | 100.0 | 100.0 | 1.00 | 0.021 |
| arch | B_wfc | 10 | 100.0 | 76.7 | 90.6 | 76.7 | 91.6 | 95.5 | 85.0 | 1.00 | 0.275 |
| arch | D_bottom_up | 10 | 100.0 | 73.5 | 90.6 | 73.5 | 90.2 | 97.0 | 82.5 | 1.00 | 0.017 |
| arch | D2_bottom_up_any_offset | 10 | 100.0 | 83.4 | 90.6 | 83.4 | 94.6 | 99.0 | 90.5 | 1.00 | 0.021 |
| mushroom | B_wfc | 10 | 100.0 | 53.2 | 94.4 | 53.2 | 50.2 | 82.5 | 24.0 | 1.08 | 0.927 |
| mushroom | D_bottom_up | 10 | 100.0 | 40.7 | 94.4 | 40.7 | 47.2 | 92.0 | 42.5 | 1.00 | 0.030 |
| mushroom | D2_bottom_up_any_offset | 10 | 100.0 | 49.9 | 94.4 | 49.9 | 46.4 | 93.5 | 38.0 | 1.00 | 0.072 |
| ring | B_wfc | 10 | 100.0 | 77.9 | 89.5 | 77.9 | 93.7 | 98.0 | 95.5 | 1.15 | 1.042 |
| ring | D_bottom_up | 10 | 100.0 | 77.2 | 89.5 | 77.2 | 93.5 | 99.5 | 97.0 | 1.00 | 0.016 |
| ring | D2_bottom_up_any_offset | 10 | 100.0 | 86.3 | 89.5 | 86.3 | 97.6 | 100.0 | 98.5 | 1.00 | 0.017 |

### Mean over sets and shapes

| shapes | condition | sets | valid % | fill % | max fill % | IoU % | utilization % | phys. any clutch % | phys. clutch <=10 % | attempts/run | time/run (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | B_wfc | 10 | 100.0 | 73.0 | 94.2 | 73.0 | 82.6 | 93.8 | 79.2 | 1.05 | 0.619 |
| all | D_bottom_up | 10 | 100.0 | 68.0 | 94.2 | 68.0 | 81.0 | 97.7 | 84.2 | 1.00 | 0.019 |
| all | D2_bottom_up_any_offset | 10 | 100.0 | 77.7 | 94.2 | 77.7 | 83.9 | 98.4 | 85.1 | 1.00 | 0.031 |

Means are over sets, each set weighted equally. Fill = IoU in every row.

## Findings

1. **Shape + inventory together is solved by construction by both generators.** All 3000 builds are valid;
   post-filtering is not needed (M9 already showed a post-filter for the inventory alone keeps 1.5%).
2. **With shape + inventory together, plain WFC beats the original bottom-up builder on fill** (73.0% vs
   68.0% overall; better on every shape). This is the effect the decision checkpoint asked about: with
   few parts of each kind, *where* a part goes matters, and WFC considers every placement that covers a
   cell while D only tries one.
3. **But the gap was the baseline's weakness, not WFC's look-ahead.** Letting the bottom-up builder place
   a part at any offset (D2, a few lines of code) gives the highest fill on four of five shapes
   (77.7% overall vs WFC's 73.0%), the highest utilization (83.9% vs 82.6%), better physics (98.4% stand
   with some clutch vs 93.8%), and is 20× faster (0.031 s vs 0.62 s per build). Per (set, shape) pair, D2
   fills more than WFC (by >1 point) in 36 of 50, WFC in 8, ties in 6.
4. **Overhangs remain WFC's one edge.** On the mushroom WFC fills 53.2% vs D2's 49.9% (and 40.7% for D), as in
   the quick test, but again by leaning on grip: 24% of WFC mushrooms stand with clutch ≤10 vs 38% for D2.
   Mushroom fill is low for everyone (max 94%): a greedy layer-by-layer builder can't plan a cap, and
   WFC's caps are physically weak.
5. **Speed outliers are WFC's.** WFC's time per build ranges 0.04–7.4 s per batch (10015 ring: 2.4 attempts
   per build; 10134 mushroom: 6.1 s); the bottom-up builders stay at or under 0.23 s.

**Caveats.** Max fill is a *volume* bound and ignores part geometry: e.g. set 10037's block is 3×3 studs
(7 plates tall), where its six 2×4 plates (48 of 70 cells) cannot fit at all, so every generator fills
~35%. Fill between generators is comparable; fill against max fill is not a packing-optimality measure.

## What this means

The pivot holds under the combined constraints: the stronger bottom-up builder (D2) matches or beats WFC
on validity, fill, utilization and physics at ~20× lower cost. Two follow-ups for the paper: use D2 as the
bottom-up generator from here on (D is kept only so earlier tables reproduce), and treat overhang-heavy
shapes as the case where look-ahead could still help — a planner for caps/spans that respects grip limits
is open.

## Per set and shape

| set | shape | condition | parts | grid | shape cells | max fill % | valid % | fill % | min fill % | IoU % | utilization % | phys. any clutch % | phys. clutch <=10 % | attempts/run | backtracks/run | time/run (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10015-1 | block | B_wfc | 24 | 3x3x6 | 54 | 100.0 | 100.0 | 80.6 | 77.8 | 80.6 | 90.6 | 95.0 | 95.0 | 1.00 | 1.0 | 0.038 |
| 10015-1 | block | D_bottom_up | 24 | 3x3x6 | 54 | 100.0 | 100.0 | 81.1 | 77.8 | 81.1 | 91.2 | 100.0 | 100.0 | 1.00 | 0.0 | 0.004 |
| 10015-1 | block | D2_bottom_up_any_offset | 24 | 3x3x6 | 54 | 100.0 | 100.0 | 81.3 | 77.8 | 81.3 | 91.5 | 100.0 | 100.0 | 1.00 | 0.0 | 0.005 |
| 10015-1 | pyramid | B_wfc | 24 | 6x6x6 | 56 | 100.0 | 100.0 | 83.4 | 78.6 | 83.4 | 90.4 | 100.0 | 100.0 | 1.00 | 0.3 | 0.080 |
| 10015-1 | pyramid | D_bottom_up | 24 | 6x6x6 | 56 | 100.0 | 100.0 | 82.9 | 78.6 | 82.9 | 91.0 | 100.0 | 100.0 | 1.00 | 0.0 | 0.004 |
| 10015-1 | pyramid | D2_bottom_up_any_offset | 24 | 6x6x6 | 56 | 100.0 | 100.0 | 93.0 | 78.6 | 93.0 | 88.5 | 100.0 | 100.0 | 1.00 | 0.0 | 0.003 |
| 10015-1 | arch | B_wfc | 24 | 6x6x3 | 96 | 62.5 | 100.0 | 62.5 | 62.5 | 62.5 | 100.0 | 95.0 | 95.0 | 1.00 | 10.6 | 0.106 |
| 10015-1 | arch | D_bottom_up | 24 | 6x6x3 | 96 | 62.5 | 100.0 | 62.5 | 62.5 | 62.5 | 100.0 | 100.0 | 100.0 | 1.00 | 0.0 | 0.006 |
| 10015-1 | arch | D2_bottom_up_any_offset | 24 | 6x6x3 | 96 | 62.5 | 100.0 | 62.5 | 62.5 | 62.5 | 100.0 | 95.0 | 90.0 | 1.00 | 0.0 | 0.008 |
| 10015-1 | mushroom | B_wfc | 24 | 6x6x3 | 76 | 78.9 | 100.0 | 52.1 | 36.8 | 52.1 | 57.5 | 95.0 | 90.0 | 1.00 | 0.1 | 0.069 |
| 10015-1 | mushroom | D_bottom_up | 24 | 6x6x3 | 76 | 78.9 | 100.0 | 42.6 | 15.8 | 42.6 | 45.0 | 100.0 | 80.0 | 1.00 | 0.0 | 0.007 |
| 10015-1 | mushroom | D2_bottom_up_any_offset | 24 | 6x6x3 | 76 | 78.9 | 100.0 | 47.0 | 31.6 | 47.0 | 50.0 | 75.0 | 70.0 | 1.00 | 0.0 | 0.012 |
| 10015-1 | ring | B_wfc | 24 | 6x6x3 | 96 | 62.5 | 100.0 | 62.1 | 54.2 | 62.1 | 99.8 | 95.0 | 95.0 | 2.40 | 1445.2 | 7.416 |
| 10015-1 | ring | D_bottom_up | 24 | 6x6x3 | 96 | 62.5 | 100.0 | 62.5 | 62.5 | 62.5 | 100.0 | 95.0 | 95.0 | 1.00 | 0.0 | 0.006 |
| 10015-1 | ring | D2_bottom_up_any_offset | 24 | 6x6x3 | 96 | 62.5 | 100.0 | 62.5 | 62.5 | 62.5 | 100.0 | 100.0 | 100.0 | 1.00 | 0.0 | 0.007 |
| 10019-1 | block | B_wfc | 81 | 7x7x6 | 294 | 100.0 | 100.0 | 81.3 | 76.2 | 81.3 | 88.8 | 100.0 | 100.0 | 1.00 | 18.6 | 0.527 |
| 10019-1 | block | D_bottom_up | 81 | 7x7x6 | 294 | 100.0 | 100.0 | 79.9 | 73.5 | 79.9 | 89.3 | 100.0 | 100.0 | 1.00 | 0.0 | 0.022 |
| 10019-1 | block | D2_bottom_up_any_offset | 81 | 7x7x6 | 294 | 100.0 | 100.0 | 90.2 | 87.1 | 90.2 | 92.5 | 100.0 | 100.0 | 1.00 | 0.0 | 0.032 |
| 10019-1 | pyramid | B_wfc | 81 | 11x11x6 | 286 | 100.0 | 100.0 | 82.7 | 76.9 | 82.7 | 87.9 | 100.0 | 100.0 | 1.00 | 0.8 | 0.548 |
| 10019-1 | pyramid | D_bottom_up | 81 | 11x11x6 | 286 | 100.0 | 100.0 | 78.2 | 75.5 | 78.2 | 87.1 | 100.0 | 100.0 | 1.00 | 0.0 | 0.026 |
| 10019-1 | pyramid | D2_bottom_up_any_offset | 81 | 11x11x6 | 286 | 100.0 | 100.0 | 89.7 | 83.9 | 89.7 | 90.9 | 100.0 | 100.0 | 1.00 | 0.0 | 0.038 |
| 10019-1 | arch | B_wfc | 81 | 9x9x6 | 306 | 99.3 | 100.0 | 81.5 | 75.8 | 81.5 | 89.2 | 95.0 | 65.0 | 1.00 | 0.6 | 0.493 |
| 10019-1 | arch | D_bottom_up | 81 | 9x9x6 | 306 | 99.3 | 100.0 | 73.9 | 62.7 | 73.9 | 86.4 | 95.0 | 30.0 | 1.00 | 0.0 | 0.032 |
| 10019-1 | arch | D2_bottom_up_any_offset | 81 | 9x9x6 | 306 | 99.3 | 100.0 | 87.5 | 82.4 | 87.5 | 91.7 | 100.0 | 80.0 | 1.00 | 0.0 | 0.039 |
| 10019-1 | mushroom | B_wfc | 81 | 12x12x6 | 324 | 93.8 | 100.0 | 47.9 | 43.8 | 47.9 | 45.9 | 100.0 | 0.0 | 1.15 | 150.8 | 1.731 |
| 10019-1 | mushroom | D_bottom_up | 81 | 12x12x6 | 324 | 93.8 | 100.0 | 33.9 | 28.4 | 33.9 | 38.2 | 95.0 | 10.0 | 1.00 | 0.0 | 0.062 |
| 10019-1 | mushroom | D2_bottom_up_any_offset | 81 | 12x12x6 | 324 | 93.8 | 100.0 | 39.4 | 27.2 | 39.4 | 38.8 | 100.0 | 5.0 | 1.00 | 0.0 | 0.167 |
| 10019-1 | ring | B_wfc | 81 | 8x8x6 | 288 | 100.0 | 100.0 | 80.8 | 75.0 | 80.8 | 87.7 | 100.0 | 100.0 | 1.00 | 1.6 | 0.472 |
| 10019-1 | ring | D_bottom_up | 81 | 8x8x6 | 288 | 100.0 | 100.0 | 83.5 | 77.8 | 83.5 | 90.0 | 100.0 | 95.0 | 1.00 | 0.0 | 0.028 |
| 10019-1 | ring | D2_bottom_up_any_offset | 81 | 8x8x6 | 288 | 100.0 | 100.0 | 95.0 | 91.7 | 95.0 | 94.7 | 100.0 | 100.0 | 1.00 | 0.0 | 0.025 |
| 10020-1 | block | B_wfc | 66 | 6x6x5 | 180 | 100.0 | 100.0 | 84.6 | 74.4 | 84.6 | 94.1 | 95.0 | 95.0 | 1.00 | 0.5 | 0.307 |
| 10020-1 | block | D_bottom_up | 66 | 6x6x5 | 180 | 100.0 | 100.0 | 83.8 | 70.0 | 83.8 | 94.0 | 100.0 | 100.0 | 1.00 | 0.0 | 0.014 |
| 10020-1 | block | D2_bottom_up_any_offset | 66 | 6x6x5 | 180 | 100.0 | 100.0 | 94.4 | 90.0 | 94.4 | 97.0 | 100.0 | 100.0 | 1.00 | 0.0 | 0.017 |
| 10020-1 | pyramid | B_wfc | 66 | 9x9x6 | 165 | 100.0 | 100.0 | 86.5 | 81.2 | 86.5 | 91.5 | 100.0 | 95.0 | 1.00 | 2.1 | 0.337 |
| 10020-1 | pyramid | D_bottom_up | 66 | 9x9x6 | 165 | 100.0 | 100.0 | 81.6 | 76.4 | 81.6 | 91.0 | 100.0 | 100.0 | 1.00 | 0.0 | 0.015 |
| 10020-1 | pyramid | D2_bottom_up_any_offset | 66 | 9x9x6 | 165 | 100.0 | 100.0 | 93.9 | 81.2 | 93.9 | 94.0 | 100.0 | 100.0 | 1.00 | 0.0 | 0.019 |
| 10020-1 | arch | B_wfc | 66 | 6x6x6 | 168 | 100.0 | 100.0 | 81.7 | 72.6 | 81.7 | 90.6 | 100.0 | 90.0 | 1.00 | 0.8 | 0.300 |
| 10020-1 | arch | D_bottom_up | 66 | 6x6x6 | 168 | 100.0 | 100.0 | 81.4 | 75.0 | 81.4 | 91.4 | 100.0 | 100.0 | 1.00 | 0.0 | 0.018 |
| 10020-1 | arch | D2_bottom_up_any_offset | 66 | 6x6x6 | 168 | 100.0 | 100.0 | 94.6 | 89.3 | 94.6 | 92.9 | 100.0 | 100.0 | 1.00 | 0.0 | 0.018 |
| 10020-1 | mushroom | B_wfc | 66 | 9x9x6 | 178 | 100.0 | 100.0 | 53.0 | 43.3 | 53.0 | 39.0 | 65.0 | 0.0 | 1.00 | 0.2 | 0.250 |
| 10020-1 | mushroom | D_bottom_up | 66 | 9x9x6 | 178 | 100.0 | 100.0 | 36.8 | 22.5 | 36.8 | 36.0 | 95.0 | 15.0 | 1.00 | 0.0 | 0.032 |
| 10020-1 | mushroom | D2_bottom_up_any_offset | 66 | 9x9x6 | 178 | 100.0 | 100.0 | 47.5 | 25.3 | 47.5 | 33.8 | 95.0 | 15.0 | 1.00 | 0.0 | 0.071 |
| 10020-1 | ring | B_wfc | 66 | 6x6x6 | 192 | 94.8 | 100.0 | 81.8 | 71.9 | 81.8 | 95.1 | 100.0 | 100.0 | 1.00 | 1.4 | 0.337 |
| 10020-1 | ring | D_bottom_up | 66 | 6x6x6 | 192 | 94.8 | 100.0 | 82.9 | 74.0 | 82.9 | 95.7 | 100.0 | 95.0 | 1.00 | 0.0 | 0.018 |
| 10020-1 | ring | D2_bottom_up_any_offset | 66 | 6x6x6 | 192 | 94.8 | 100.0 | 93.0 | 86.5 | 93.0 | 99.3 | 100.0 | 100.0 | 1.00 | 0.0 | 0.018 |
| 10037-1 | block | B_wfc | 20 | 3x3x7 | 63 | 100.0 | 100.0 | 34.6 | 28.6 | 34.6 | 69.8 | 65.0 | 65.0 | 1.35 | 641.0 | 2.783 |
| 10037-1 | block | D_bottom_up | 20 | 3x3x7 | 63 | 100.0 | 100.0 | 34.9 | 34.9 | 34.9 | 70.0 | 100.0 | 100.0 | 1.00 | 0.0 | 0.008 |
| 10037-1 | block | D2_bottom_up_any_offset | 20 | 3x3x7 | 63 | 100.0 | 100.0 | 34.9 | 34.9 | 34.9 | 70.0 | 95.0 | 95.0 | 1.00 | 0.0 | 0.019 |
| 10037-1 | pyramid | B_wfc | 20 | 7x7x3 | 83 | 84.3 | 100.0 | 72.3 | 55.4 | 72.3 | 93.8 | 85.0 | 85.0 | 1.00 | 0.5 | 0.105 |
| 10037-1 | pyramid | D_bottom_up | 20 | 7x7x3 | 83 | 84.3 | 100.0 | 60.7 | 55.4 | 60.7 | 87.8 | 100.0 | 100.0 | 1.00 | 0.0 | 0.007 |
| 10037-1 | pyramid | D2_bottom_up_any_offset | 20 | 7x7x3 | 83 | 84.3 | 100.0 | 74.7 | 65.1 | 74.7 | 95.0 | 100.0 | 100.0 | 1.00 | 0.0 | 0.008 |
| 10037-1 | arch | B_wfc | 20 | 6x6x3 | 96 | 72.9 | 100.0 | 67.5 | 56.2 | 67.5 | 96.2 | 90.0 | 80.0 | 1.00 | 0.1 | 0.118 |
| 10037-1 | arch | D_bottom_up | 20 | 6x6x3 | 96 | 72.9 | 100.0 | 68.8 | 56.2 | 68.8 | 97.5 | 100.0 | 95.0 | 1.00 | 0.0 | 0.008 |
| 10037-1 | arch | D2_bottom_up_any_offset | 20 | 6x6x3 | 96 | 72.9 | 100.0 | 72.9 | 72.9 | 72.9 | 100.0 | 95.0 | 95.0 | 1.00 | 0.0 | 0.009 |
| 10037-1 | mushroom | B_wfc | 20 | 6x6x3 | 76 | 92.1 | 100.0 | 58.6 | 31.6 | 58.6 | 59.2 | 65.0 | 50.0 | 1.00 | 0.0 | 0.071 |
| 10037-1 | mushroom | D_bottom_up | 20 | 6x6x3 | 76 | 92.1 | 100.0 | 49.1 | 31.6 | 49.1 | 57.2 | 80.0 | 75.0 | 1.00 | 0.0 | 0.008 |
| 10037-1 | mushroom | D2_bottom_up_any_offset | 20 | 6x6x3 | 76 | 92.1 | 100.0 | 59.6 | 34.2 | 59.6 | 58.8 | 75.0 | 70.0 | 1.00 | 0.0 | 0.016 |
| 10037-1 | ring | B_wfc | 20 | 6x6x3 | 96 | 72.9 | 100.0 | 69.6 | 56.2 | 69.6 | 98.0 | 95.0 | 90.0 | 1.00 | 8.0 | 0.157 |
| 10037-1 | ring | D_bottom_up | 20 | 6x6x3 | 96 | 72.9 | 100.0 | 71.2 | 64.6 | 71.2 | 99.0 | 100.0 | 100.0 | 1.00 | 0.0 | 0.007 |
| 10037-1 | ring | D2_bottom_up_any_offset | 20 | 6x6x3 | 96 | 72.9 | 100.0 | 72.9 | 72.9 | 72.9 | 100.0 | 100.0 | 100.0 | 1.00 | 0.0 | 0.008 |
| 10124-1 | block | B_wfc | 44 | 5x5x7 | 175 | 100.0 | 100.0 | 72.5 | 68.6 | 72.5 | 85.3 | 100.0 | 100.0 | 1.00 | 6.2 | 0.251 |
| 10124-1 | block | D_bottom_up | 44 | 5x5x7 | 175 | 100.0 | 100.0 | 71.9 | 64.0 | 71.9 | 85.5 | 100.0 | 100.0 | 1.00 | 0.0 | 0.015 |
| 10124-1 | block | D2_bottom_up_any_offset | 44 | 5x5x7 | 175 | 100.0 | 100.0 | 79.7 | 75.4 | 79.7 | 87.7 | 100.0 | 90.0 | 1.00 | 0.0 | 0.023 |
| 10124-1 | pyramid | B_wfc | 44 | 9x9x6 | 165 | 100.0 | 100.0 | 80.0 | 72.7 | 80.0 | 86.4 | 100.0 | 100.0 | 1.00 | 0.5 | 0.297 |
| 10124-1 | pyramid | D_bottom_up | 44 | 9x9x6 | 165 | 100.0 | 100.0 | 72.8 | 63.0 | 72.8 | 82.8 | 100.0 | 100.0 | 1.00 | 0.0 | 0.014 |
| 10124-1 | pyramid | D2_bottom_up_any_offset | 44 | 9x9x6 | 165 | 100.0 | 100.0 | 85.0 | 75.2 | 85.0 | 86.8 | 100.0 | 100.0 | 1.00 | 0.0 | 0.022 |
| 10124-1 | arch | B_wfc | 44 | 6x6x6 | 168 | 100.0 | 100.0 | 78.8 | 71.4 | 78.8 | 85.9 | 95.0 | 80.0 | 1.00 | 0.6 | 0.233 |
| 10124-1 | arch | D_bottom_up | 44 | 6x6x6 | 168 | 100.0 | 100.0 | 76.2 | 66.7 | 76.2 | 86.1 | 100.0 | 100.0 | 1.00 | 0.0 | 0.014 |
| 10124-1 | arch | D2_bottom_up_any_offset | 44 | 6x6x6 | 168 | 100.0 | 100.0 | 89.0 | 76.2 | 89.0 | 91.8 | 100.0 | 100.0 | 1.00 | 0.0 | 0.016 |
| 10124-1 | mushroom | B_wfc | 44 | 9x9x6 | 178 | 98.9 | 100.0 | 53.5 | 44.4 | 53.5 | 48.5 | 70.0 | 0.0 | 1.00 | 0.3 | 0.224 |
| 10124-1 | mushroom | D_bottom_up | 44 | 9x9x6 | 178 | 98.9 | 100.0 | 36.2 | 25.3 | 36.2 | 46.7 | 85.0 | 20.0 | 1.00 | 0.0 | 0.027 |
| 10124-1 | mushroom | D2_bottom_up_any_offset | 44 | 9x9x6 | 178 | 98.9 | 100.0 | 46.9 | 23.6 | 46.9 | 43.1 | 100.0 | 10.0 | 1.00 | 0.0 | 0.058 |
| 10124-1 | ring | B_wfc | 44 | 6x6x6 | 192 | 91.7 | 100.0 | 80.0 | 62.5 | 80.0 | 93.4 | 100.0 | 100.0 | 1.00 | 2.0 | 0.270 |
| 10124-1 | ring | D_bottom_up | 44 | 6x6x6 | 192 | 91.7 | 100.0 | 78.1 | 70.8 | 78.1 | 92.6 | 100.0 | 100.0 | 1.00 | 0.0 | 0.016 |
| 10124-1 | ring | D2_bottom_up_any_offset | 44 | 6x6x6 | 192 | 91.7 | 100.0 | 90.6 | 87.5 | 90.6 | 99.4 | 100.0 | 95.0 | 1.00 | 0.0 | 0.016 |
| 10128-1 | block | B_wfc | 26 | 4x4x6 | 96 | 97.9 | 100.0 | 80.4 | 62.5 | 80.4 | 90.4 | 100.0 | 100.0 | 1.00 | 0.7 | 0.155 |
| 10128-1 | block | D_bottom_up | 26 | 4x4x6 | 96 | 97.9 | 100.0 | 74.8 | 68.8 | 74.8 | 87.9 | 100.0 | 100.0 | 1.00 | 0.0 | 0.013 |
| 10128-1 | block | D2_bottom_up_any_offset | 26 | 4x4x6 | 96 | 97.9 | 100.0 | 91.0 | 77.1 | 91.0 | 95.2 | 100.0 | 100.0 | 1.00 | 0.0 | 0.009 |
| 10128-1 | pyramid | B_wfc | 26 | 7x7x4 | 84 | 100.0 | 100.0 | 77.4 | 69.0 | 77.4 | 79.6 | 100.0 | 100.0 | 1.00 | 0.0 | 0.161 |
| 10128-1 | pyramid | D_bottom_up | 26 | 7x7x4 | 84 | 100.0 | 100.0 | 67.1 | 59.5 | 67.1 | 73.7 | 100.0 | 100.0 | 1.00 | 0.0 | 0.009 |
| 10128-1 | pyramid | D2_bottom_up_any_offset | 26 | 7x7x4 | 84 | 100.0 | 100.0 | 78.8 | 73.8 | 78.8 | 80.8 | 100.0 | 100.0 | 1.00 | 0.0 | 0.011 |
| 10128-1 | arch | B_wfc | 26 | 6x6x3 | 96 | 97.9 | 100.0 | 79.4 | 70.8 | 79.4 | 87.3 | 100.0 | 100.0 | 1.00 | 0.0 | 0.156 |
| 10128-1 | arch | D_bottom_up | 26 | 6x6x3 | 96 | 97.9 | 100.0 | 70.8 | 56.2 | 70.8 | 80.8 | 90.0 | 90.0 | 1.00 | 0.0 | 0.010 |
| 10128-1 | arch | D2_bottom_up_any_offset | 26 | 6x6x3 | 96 | 97.9 | 100.0 | 83.8 | 72.9 | 83.8 | 90.8 | 100.0 | 100.0 | 1.00 | 0.0 | 0.011 |
| 10128-1 | mushroom | B_wfc | 26 | 6x6x6 | 88 | 100.0 | 100.0 | 62.7 | 43.2 | 62.7 | 59.2 | 90.0 | 55.0 | 1.00 | 0.0 | 0.143 |
| 10128-1 | mushroom | D_bottom_up | 26 | 6x6x6 | 88 | 100.0 | 100.0 | 50.1 | 33.0 | 50.1 | 61.9 | 100.0 | 85.0 | 1.00 | 0.0 | 0.012 |
| 10128-1 | mushroom | D2_bottom_up_any_offset | 26 | 6x6x6 | 88 | 100.0 | 100.0 | 61.3 | 38.6 | 61.3 | 52.9 | 100.0 | 95.0 | 1.00 | 0.0 | 0.021 |
| 10128-1 | ring | B_wfc | 26 | 6x6x3 | 96 | 97.9 | 100.0 | 83.4 | 72.9 | 83.4 | 92.1 | 95.0 | 95.0 | 1.00 | 2.0 | 0.146 |
| 10128-1 | ring | D_bottom_up | 26 | 6x6x3 | 96 | 97.9 | 100.0 | 75.2 | 64.6 | 75.2 | 88.1 | 100.0 | 100.0 | 1.00 | 0.0 | 0.011 |
| 10128-1 | ring | D2_bottom_up_any_offset | 26 | 6x6x3 | 96 | 97.9 | 100.0 | 89.8 | 81.2 | 89.8 | 94.8 | 100.0 | 100.0 | 1.00 | 0.0 | 0.009 |
| 10133-1 | block | B_wfc | 59 | 6x6x5 | 180 | 100.0 | 100.0 | 84.5 | 77.8 | 84.5 | 91.8 | 100.0 | 100.0 | 1.00 | 1.1 | 0.270 |
| 10133-1 | block | D_bottom_up | 59 | 6x6x5 | 180 | 100.0 | 100.0 | 80.7 | 75.6 | 80.7 | 90.6 | 100.0 | 100.0 | 1.00 | 0.0 | 0.016 |
| 10133-1 | block | D2_bottom_up_any_offset | 59 | 6x6x5 | 180 | 100.0 | 100.0 | 94.2 | 88.9 | 94.2 | 92.6 | 100.0 | 100.0 | 1.00 | 0.0 | 0.019 |
| 10133-1 | pyramid | B_wfc | 59 | 10x10x3 | 200 | 94.0 | 100.0 | 82.7 | 76.0 | 82.7 | 94.8 | 100.0 | 100.0 | 1.00 | 1.3 | 0.304 |
| 10133-1 | pyramid | D_bottom_up | 59 | 10x10x3 | 200 | 94.0 | 100.0 | 81.8 | 70.0 | 81.8 | 94.5 | 100.0 | 100.0 | 1.00 | 0.0 | 0.019 |
| 10133-1 | pyramid | D2_bottom_up_any_offset | 59 | 10x10x3 | 200 | 94.0 | 100.0 | 90.6 | 84.0 | 90.6 | 98.1 | 100.0 | 100.0 | 1.00 | 0.0 | 0.023 |
| 10133-1 | arch | B_wfc | 59 | 6x6x7 | 192 | 97.9 | 100.0 | 80.1 | 75.0 | 80.1 | 92.2 | 95.0 | 90.0 | 1.00 | 1.1 | 0.306 |
| 10133-1 | arch | D_bottom_up | 59 | 6x6x7 | 192 | 97.9 | 100.0 | 78.9 | 68.8 | 78.9 | 92.2 | 100.0 | 100.0 | 1.00 | 0.0 | 0.019 |
| 10133-1 | arch | D2_bottom_up_any_offset | 59 | 6x6x7 | 192 | 97.9 | 100.0 | 93.4 | 85.4 | 93.4 | 97.8 | 100.0 | 95.0 | 1.00 | 0.0 | 0.019 |
| 10133-1 | mushroom | B_wfc | 59 | 9x9x6 | 178 | 100.0 | 100.0 | 51.5 | 37.1 | 51.5 | 36.5 | 70.0 | 0.0 | 1.00 | 0.7 | 0.249 |
| 10133-1 | mushroom | D_bottom_up | 59 | 9x9x6 | 178 | 100.0 | 100.0 | 34.6 | 21.3 | 34.6 | 30.4 | 80.0 | 25.0 | 1.00 | 0.0 | 0.035 |
| 10133-1 | mushroom | D2_bottom_up_any_offset | 59 | 9x9x6 | 178 | 100.0 | 100.0 | 45.4 | 22.5 | 45.4 | 32.4 | 90.0 | 5.0 | 1.00 | 0.0 | 0.080 |
| 10133-1 | ring | B_wfc | 59 | 6x6x6 | 192 | 97.9 | 100.0 | 81.7 | 72.9 | 81.7 | 93.2 | 100.0 | 95.0 | 1.00 | 3.2 | 0.295 |
| 10133-1 | ring | D_bottom_up | 59 | 6x6x6 | 192 | 97.9 | 100.0 | 82.9 | 77.1 | 82.9 | 93.9 | 100.0 | 95.0 | 1.00 | 0.0 | 0.020 |
| 10133-1 | ring | D2_bottom_up_any_offset | 59 | 6x6x6 | 192 | 97.9 | 100.0 | 92.9 | 89.6 | 92.9 | 97.3 | 100.0 | 100.0 | 1.00 | 0.0 | 0.020 |
| 10134-1 | block | B_wfc | 64 | 8x8x6 | 384 | 94.3 | 100.0 | 78.7 | 73.4 | 78.7 | 87.7 | 100.0 | 90.0 | 1.00 | 1.6 | 0.560 |
| 10134-1 | block | D_bottom_up | 64 | 8x8x6 | 384 | 94.3 | 100.0 | 70.2 | 65.1 | 70.2 | 81.9 | 100.0 | 95.0 | 1.00 | 0.0 | 0.036 |
| 10134-1 | block | D2_bottom_up_any_offset | 64 | 8x8x6 | 384 | 94.3 | 100.0 | 82.2 | 75.5 | 82.2 | 89.5 | 100.0 | 100.0 | 1.00 | 0.0 | 0.065 |
| 10134-1 | pyramid | B_wfc | 64 | 12x12x6 | 364 | 99.5 | 100.0 | 80.5 | 75.3 | 80.5 | 85.4 | 100.0 | 100.0 | 1.00 | 0.1 | 0.668 |
| 10134-1 | pyramid | D_bottom_up | 64 | 12x12x6 | 364 | 99.5 | 100.0 | 71.8 | 66.5 | 71.8 | 80.3 | 100.0 | 100.0 | 1.00 | 0.0 | 0.038 |
| 10134-1 | pyramid | D2_bottom_up_any_offset | 64 | 12x12x6 | 364 | 99.5 | 100.0 | 83.7 | 77.5 | 83.7 | 88.0 | 100.0 | 100.0 | 1.00 | 0.0 | 0.062 |
| 10134-1 | arch | B_wfc | 64 | 10x10x6 | 360 | 100.0 | 100.0 | 77.9 | 71.7 | 77.9 | 82.7 | 90.0 | 55.0 | 1.00 | 1.1 | 0.530 |
| 10134-1 | arch | D_bottom_up | 64 | 10x10x6 | 360 | 100.0 | 100.0 | 71.2 | 65.0 | 71.2 | 79.1 | 95.0 | 20.0 | 1.00 | 0.0 | 0.037 |
| 10134-1 | arch | D2_bottom_up_any_offset | 64 | 10x10x6 | 360 | 100.0 | 100.0 | 79.4 | 71.7 | 79.4 | 83.0 | 100.0 | 45.0 | 1.00 | 0.0 | 0.067 |
| 10134-1 | mushroom | B_wfc | 64 | 13x13x6 | 374 | 96.8 | 100.0 | 38.8 | 32.6 | 38.8 | 43.4 | 95.0 | 0.0 | 1.70 | 700.9 | 6.120 |
| 10134-1 | mushroom | D_bottom_up | 64 | 13x13x6 | 374 | 96.8 | 100.0 | 29.1 | 20.9 | 29.1 | 39.8 | 100.0 | 15.0 | 1.00 | 0.0 | 0.071 |
| 10134-1 | mushroom | D2_bottom_up_any_offset | 64 | 13x13x6 | 374 | 96.8 | 100.0 | 35.9 | 25.1 | 35.9 | 44.8 | 100.0 | 0.0 | 1.00 | 0.0 | 0.232 |
| 10134-1 | ring | B_wfc | 64 | 10x10x6 | 384 | 94.3 | 100.0 | 77.7 | 70.3 | 77.7 | 87.3 | 100.0 | 85.0 | 1.00 | 1.1 | 0.626 |
| 10134-1 | ring | D_bottom_up | 64 | 10x10x6 | 384 | 94.3 | 100.0 | 78.0 | 71.4 | 78.0 | 87.8 | 100.0 | 90.0 | 1.00 | 0.0 | 0.033 |
| 10134-1 | ring | D2_bottom_up_any_offset | 64 | 10x10x6 | 384 | 94.3 | 100.0 | 88.1 | 83.9 | 88.1 | 95.4 | 100.0 | 90.0 | 1.00 | 0.0 | 0.045 |
| 10159-1 | block | B_wfc | 45 | 5x5x5 | 125 | 100.0 | 100.0 | 78.7 | 71.2 | 78.7 | 87.0 | 95.0 | 95.0 | 1.05 | 50.7 | 0.507 |
| 10159-1 | block | D_bottom_up | 45 | 5x5x5 | 125 | 100.0 | 100.0 | 75.4 | 71.2 | 75.4 | 86.7 | 100.0 | 100.0 | 1.00 | 0.0 | 0.015 |
| 10159-1 | block | D2_bottom_up_any_offset | 45 | 5x5x5 | 125 | 100.0 | 100.0 | 85.9 | 80.8 | 85.9 | 89.8 | 100.0 | 100.0 | 1.00 | 0.0 | 0.018 |
| 10159-1 | pyramid | B_wfc | 45 | 8x8x6 | 120 | 100.0 | 100.0 | 84.0 | 74.2 | 84.0 | 86.2 | 100.0 | 100.0 | 1.00 | 0.1 | 0.348 |
| 10159-1 | pyramid | D_bottom_up | 45 | 8x8x6 | 120 | 100.0 | 100.0 | 79.2 | 64.2 | 79.2 | 85.6 | 100.0 | 100.0 | 1.00 | 0.0 | 0.014 |
| 10159-1 | pyramid | D2_bottom_up_any_offset | 45 | 8x8x6 | 120 | 100.0 | 100.0 | 92.8 | 87.5 | 92.8 | 90.3 | 100.0 | 100.0 | 1.00 | 0.0 | 0.015 |
| 10159-1 | arch | B_wfc | 45 | 6x6x5 | 144 | 92.4 | 100.0 | 80.9 | 72.9 | 80.9 | 94.0 | 100.0 | 100.0 | 1.00 | 0.7 | 0.365 |
| 10159-1 | arch | D_bottom_up | 45 | 6x6x5 | 144 | 92.4 | 100.0 | 76.1 | 64.6 | 76.1 | 91.4 | 95.0 | 95.0 | 1.00 | 0.0 | 0.018 |
| 10159-1 | arch | D2_bottom_up_any_offset | 45 | 6x6x5 | 144 | 92.4 | 100.0 | 88.2 | 81.2 | 88.2 | 97.8 | 100.0 | 100.0 | 1.00 | 0.0 | 0.018 |
| 10159-1 | mushroom | B_wfc | 45 | 8x8x6 | 144 | 92.4 | 100.0 | 53.6 | 45.1 | 53.6 | 52.3 | 90.0 | 0.0 | 1.00 | 0.1 | 0.279 |
| 10159-1 | mushroom | D_bottom_up | 45 | 8x8x6 | 144 | 92.4 | 100.0 | 43.6 | 29.2 | 43.6 | 53.1 | 90.0 | 25.0 | 1.00 | 0.0 | 0.031 |
| 10159-1 | mushroom | D2_bottom_up_any_offset | 45 | 8x8x6 | 144 | 92.4 | 100.0 | 56.6 | 39.6 | 56.6 | 50.8 | 100.0 | 20.0 | 1.00 | 0.0 | 0.048 |
| 10159-1 | ring | B_wfc | 45 | 6x6x4 | 128 | 100.0 | 100.0 | 82.9 | 75.8 | 82.9 | 92.0 | 100.0 | 100.0 | 1.00 | 0.8 | 0.298 |
| 10159-1 | ring | D_bottom_up | 45 | 6x6x4 | 128 | 100.0 | 100.0 | 79.7 | 69.5 | 79.7 | 90.2 | 100.0 | 100.0 | 1.00 | 0.0 | 0.014 |
| 10159-1 | ring | D2_bottom_up_any_offset | 45 | 6x6x4 | 128 | 100.0 | 100.0 | 95.2 | 91.4 | 95.2 | 95.4 | 100.0 | 100.0 | 1.00 | 0.0 | 0.013 |
| 10170-1 | block | B_wfc | 32 | 4x4x5 | 80 | 100.0 | 100.0 | 85.0 | 70.0 | 85.0 | 95.3 | 95.0 | 95.0 | 1.00 | 1.1 | 0.116 |
| 10170-1 | block | D_bottom_up | 32 | 4x4x5 | 80 | 100.0 | 100.0 | 84.0 | 70.0 | 84.0 | 95.0 | 100.0 | 95.0 | 1.00 | 0.0 | 0.008 |
| 10170-1 | block | D2_bottom_up_any_offset | 32 | 4x4x5 | 80 | 100.0 | 100.0 | 92.7 | 80.0 | 92.7 | 96.9 | 100.0 | 100.0 | 1.00 | 0.0 | 0.008 |
| 10170-1 | pyramid | B_wfc | 32 | 7x7x6 | 84 | 95.2 | 100.0 | 83.7 | 76.2 | 83.7 | 96.1 | 100.0 | 100.0 | 1.00 | 1.2 | 0.167 |
| 10170-1 | pyramid | D_bottom_up | 32 | 7x7x6 | 84 | 95.2 | 100.0 | 72.9 | 66.7 | 72.9 | 92.7 | 100.0 | 100.0 | 1.00 | 0.0 | 0.008 |
| 10170-1 | pyramid | D2_bottom_up_any_offset | 32 | 7x7x6 | 84 | 95.2 | 100.0 | 82.4 | 76.2 | 82.4 | 95.8 | 100.0 | 100.0 | 1.00 | 0.0 | 0.012 |
| 10170-1 | arch | B_wfc | 32 | 6x6x3 | 96 | 83.3 | 100.0 | 76.7 | 66.7 | 76.7 | 97.5 | 95.0 | 95.0 | 1.00 | 0.1 | 0.142 |
| 10170-1 | arch | D_bottom_up | 32 | 6x6x3 | 96 | 83.3 | 100.0 | 75.4 | 66.7 | 75.4 | 97.0 | 95.0 | 95.0 | 1.00 | 0.0 | 0.009 |
| 10170-1 | arch | D2_bottom_up_any_offset | 32 | 6x6x3 | 96 | 83.3 | 100.0 | 82.9 | 75.0 | 82.9 | 99.8 | 100.0 | 100.0 | 1.00 | 0.0 | 0.009 |
| 10170-1 | mushroom | B_wfc | 32 | 6x6x6 | 88 | 90.9 | 100.0 | 59.9 | 42.0 | 59.9 | 60.8 | 85.0 | 45.0 | 1.00 | 0.1 | 0.132 |
| 10170-1 | mushroom | D_bottom_up | 32 | 6x6x6 | 88 | 90.9 | 100.0 | 51.5 | 34.1 | 51.5 | 63.9 | 95.0 | 75.0 | 1.00 | 0.0 | 0.011 |
| 10170-1 | mushroom | D2_bottom_up_any_offset | 32 | 6x6x6 | 88 | 90.9 | 100.0 | 59.3 | 40.9 | 59.3 | 58.4 | 100.0 | 90.0 | 1.00 | 0.0 | 0.021 |
| 10170-1 | ring | B_wfc | 32 | 6x6x3 | 96 | 83.3 | 100.0 | 79.6 | 66.7 | 79.6 | 98.6 | 95.0 | 95.0 | 1.05 | 64.5 | 0.408 |
| 10170-1 | ring | D_bottom_up | 32 | 6x6x3 | 96 | 83.3 | 100.0 | 77.9 | 66.7 | 77.9 | 98.0 | 100.0 | 100.0 | 1.00 | 0.0 | 0.009 |
| 10170-1 | ring | D2_bottom_up_any_offset | 32 | 6x6x3 | 96 | 83.3 | 100.0 | 82.9 | 75.0 | 82.9 | 99.8 | 100.0 | 100.0 | 1.00 | 0.0 | 0.008 |
