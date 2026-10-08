# M9b — building from a real set's parts, full part catalog (10 OMR sets)

Reproduce (about 70 minutes, serial; resumable):

```
python -m brickwfc.experiments.inventory --catalog full --height 12 --seeds 20 \
    --conditions B_inventory D_bottom_up D2_bottom_up_any_offset --time-limit 30 --wfc-max-mb 1000 --out out/m9b
```

Raw data: `m9b_inventory_catalog_summary.json`. The M9 table (four plates only, `m9_inventory.md`) is
unchanged and still reproduces with the default `--catalog plates`.

## Setup (what changed from M9)

- **Inventory**: every part of the set in `parts.CATALOG` (M8: 63 plates, bricks, tiles, lookalikes), per
  color. **Recognized %** = those parts / all of the set's parts (LDraw primitives excluded); **left out** =
  the parts the builds cannot use.
- **Grid**: 12 plates tall (bricks are 3), square footprint, volume 1.5× the inventory's cell volume.
- **Conditions** (20 seeds per set):
  - **B_inventory**: WFC + support + inventory constraints, ≤ 1000 backtracks per attempt, **capped at 30 s
    per build** (`wfc.run(time_limit_s=...)`; a build that hits the cap counts as *timed out*). WFC is not
    run where its backtracking history (64 copies of the cells × tiles domain) would need more than 1 GB:
    10019-1 (2.4 GB) and 10134-1 (1.5 GB). Those rows say *not run (memory)* instead of being left out.
  - **D_bottom_up**, **D2_bottom_up_any_offset** (M11): random bottom-up placement, skipping used-up parts.
- Run serially on one core; timings are single-process.

## Mean over sets

| condition | sets | within inventory % | valid % | phys. any clutch % | utilization % | time/run (s) |
|---|---|---|---|---|---|---|
| B_inventory (WFC) | 8 (2 not run) | 2.5 | 2.5 | 1.2 | 10.1 | 29.8 (cap 30) |
| D_bottom_up | 10 | 100.0 | 100.0 | 60.0 | 99.5 | 0.32 |
| D2_bottom_up_any_offset | 10 | 100.0 | 100.0 | 83.5 | 99.5 | 0.99 |

WFC finished 4 of 20 builds on 10015-1 (mean 11.6 s each) and **0 of 20 on every other set** within 30 s.

## Findings

1. **The catalog makes the inventories real.** The builds now use 35–67% of each set's parts (mean 47%;
   M9: 3–15%), 2,868 of 6,540 parts over the 10 sets. 3,672 parts are still left out (slopes, corner
   pieces, Technic, special parts; see `m8_parts.md`).
2. **The bottom-up builders scale; WFC does not.** D and D2 are 100% valid and use 99.5% of the parts on
   every set, including 10019-1 (746 parts, 33×33×12 grid) in 1.2 s (D) and 4.4 s (D2) per build.
3. **Physics is harder with bricks.** Stands with some clutch: D2 83.5%, D 60% (M9, plates only: 99%).
   Bricks make taller, heavier builds, and random placement tips them over more often; D2's denser
   packing helps. Physics is still checked only after generation.
4. **Why WFC fails here (follow-up work, not attempted now).** There are two causes, visible in the
   backtrack counts:
   - **Late dead ends from the inventory constraint** (10015-1, 10037-1: ~950–1090 backtracks per build).
     These sets have many part types with 1–2 copies each. `InventoryConstraint` only removes a part once
     its copies are *placed*, so WFC finds out late that a cell holding something up has no part left.
     With the support constraint alone, WFC builds 10015-1 in 7.7 s.
   - **Raw cost** (the other six sets: ~0–2 backtracks, 1 attempt): the build never finishes. The cost
     per collapse grows with tile count × cells (e.g. 1,039 tiles × 2,352 cells for 10020-1), and the
     support constraint re-checks a whole layer after each change.

   Possible fixes for later: count *committed* plus *forced* parts in the inventory constraint (look-ahead),
   a layer-local support check, and fewer tiles (merge lookalikes for WFC, colors as a separate pass).

## Per set

| set | condition | parts | grid | seeds | set parts | recognized % | left out | cap (s) | finished | timed out | time/finished (s) | within inventory % | valid % | phys. any clutch % | phys. clutch <=10 % | utilization % | attempts/run | backtracks/run | time/run (s) | time/valid (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10015-1 | B_inventory | 108 | 8x8x12 | 20 | 192 | 56 | 84 | 30.0 | 4 | 16 | 11.55 | 20.0 | 20.0 | 10.0 | 0.0 | 80.8 | 1.65 | 948.6 | 26.324 | 131.618 |
| 10015-1 | D_bottom_up | 108 | 8x8x12 | 20 | 192 | 56 | 84 | — | 20 | 0 | 0.05 | 100.0 | 100.0 | 60.0 | 15.0 | 98.1 | 1.00 | 0.0 | 0.054 | 0.054 |
| 10015-1 | D2_bottom_up_any_offset | 108 | 8x8x12 | 20 | 192 | 56 | 84 | — | 20 | 0 | 0.09 | 100.0 | 100.0 | 70.0 | 45.0 | 98.1 | 1.00 | 0.0 | 0.093 | 0.093 |
| 10019-1 | B_inventory | 746 | 33x33x12 | 20 | 1804 | 41 | 1058 | 30.0 | not run (memory: 2442 MB) | — | — | — | — | — | — | — | — | — | — | — |
| 10019-1 | D_bottom_up | 746 | 33x33x12 | 20 | 1804 | 41 | 1058 | — | 20 | 0 | 1.21 | 100.0 | 100.0 | 35.0 | 0.0 | 100.0 | 1.00 | 0.0 | 1.208 | 1.208 |
| 10019-1 | D2_bottom_up_any_offset | 746 | 33x33x12 | 20 | 1804 | 41 | 1058 | — | 20 | 0 | 4.42 | 100.0 | 100.0 | 90.0 | 20.0 | 100.0 | 1.00 | 0.0 | 4.416 | 4.416 |
| 10020-1 | B_inventory | 270 | 14x14x12 | 20 | 444 | 61 | 174 | 30.0 | 0 | 20 | — | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.00 | 0.5 | 30.194 | inf |
| 10020-1 | D_bottom_up | 270 | 14x14x12 | 20 | 444 | 61 | 174 | — | 20 | 0 | 0.20 | 100.0 | 100.0 | 50.0 | 0.0 | 99.9 | 1.00 | 0.0 | 0.199 | 0.199 |
| 10020-1 | D2_bottom_up_any_offset | 270 | 14x14x12 | 20 | 444 | 61 | 174 | — | 20 | 0 | 0.56 | 100.0 | 100.0 | 80.0 | 20.0 | 100.0 | 1.00 | 0.0 | 0.561 | 0.561 |
| 10037-1 | B_inventory | 78 | 7x7x12 | 20 | 221 | 35 | 143 | 30.0 | 0 | 20 | — | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.85 | 1089.2 | 30.013 | inf |
| 10037-1 | D_bottom_up | 78 | 7x7x12 | 20 | 221 | 35 | 143 | — | 20 | 0 | 0.04 | 100.0 | 100.0 | 75.0 | 60.0 | 97.4 | 1.00 | 0.0 | 0.038 | 0.038 |
| 10037-1 | D2_bottom_up_any_offset | 78 | 7x7x12 | 20 | 221 | 35 | 143 | — | 20 | 0 | 0.06 | 100.0 | 100.0 | 100.0 | 90.0 | 97.4 | 1.00 | 0.0 | 0.062 | 0.062 |
| 10124-1 | B_inventory | 252 | 14x14x12 | 20 | 677 | 37 | 425 | 30.0 | 0 | 20 | — | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.00 | 2.4 | 30.059 | inf |
| 10124-1 | D_bottom_up | 252 | 14x14x12 | 20 | 677 | 37 | 425 | — | 20 | 0 | 0.16 | 100.0 | 100.0 | 75.0 | 20.0 | 100.0 | 1.00 | 0.0 | 0.161 | 0.161 |
| 10124-1 | D2_bottom_up_any_offset | 252 | 14x14x12 | 20 | 677 | 37 | 425 | — | 20 | 0 | 0.32 | 100.0 | 100.0 | 95.0 | 25.0 | 100.0 | 1.00 | 0.0 | 0.316 | 0.316 |
| 10128-1 | B_inventory | 124 | 13x13x12 | 20 | 338 | 37 | 214 | 30.0 | 0 | 20 | — | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.00 | 0.6 | 30.048 | inf |
| 10128-1 | D_bottom_up | 124 | 13x13x12 | 20 | 338 | 37 | 214 | — | 20 | 0 | 0.14 | 100.0 | 100.0 | 65.0 | 10.0 | 99.4 | 1.00 | 0.0 | 0.138 | 0.138 |
| 10128-1 | D2_bottom_up_any_offset | 124 | 13x13x12 | 20 | 338 | 37 | 214 | — | 20 | 0 | 0.33 | 100.0 | 100.0 | 85.0 | 25.0 | 99.9 | 1.00 | 0.0 | 0.327 | 0.327 |
| 10133-1 | B_inventory | 252 | 14x14x12 | 20 | 419 | 60 | 167 | 30.0 | 0 | 20 | — | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.00 | 0.8 | 30.126 | inf |
| 10133-1 | D_bottom_up | 252 | 14x14x12 | 20 | 419 | 60 | 167 | — | 20 | 0 | 0.17 | 100.0 | 100.0 | 90.0 | 40.0 | 100.0 | 1.00 | 0.0 | 0.167 | 0.167 |
| 10133-1 | D2_bottom_up_any_offset | 252 | 14x14x12 | 20 | 419 | 60 | 167 | — | 20 | 0 | 0.28 | 100.0 | 100.0 | 100.0 | 50.0 | 100.0 | 1.00 | 0.0 | 0.278 | 0.278 |
| 10134-1 | B_inventory | 542 | 27x27x12 | 20 | 1491 | 36 | 949 | 30.0 | not run (memory: 1465 MB) | — | — | — | — | — | — | — | — | — | — | — |
| 10134-1 | D_bottom_up | 542 | 27x27x12 | 20 | 1491 | 36 | 949 | — | 20 | 0 | 0.80 | 100.0 | 100.0 | 30.0 | 10.0 | 100.0 | 1.00 | 0.0 | 0.797 | 0.797 |
| 10134-1 | D2_bottom_up_any_offset | 542 | 27x27x12 | 20 | 1491 | 36 | 949 | — | 20 | 0 | 3.08 | 100.0 | 100.0 | 60.0 | 0.0 | 100.0 | 1.00 | 0.0 | 3.083 | 3.083 |
| 10159-1 | B_inventory | 252 | 14x14x12 | 20 | 589 | 43 | 337 | 30.0 | 0 | 20 | — | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.00 | 1.3 | 30.082 | inf |
| 10159-1 | D_bottom_up | 252 | 14x14x12 | 20 | 589 | 43 | 337 | — | 20 | 0 | 0.19 | 100.0 | 100.0 | 70.0 | 25.0 | 100.0 | 1.00 | 0.0 | 0.186 | 0.186 |
| 10159-1 | D2_bottom_up_any_offset | 252 | 14x14x12 | 20 | 589 | 43 | 337 | — | 20 | 0 | 0.27 | 100.0 | 100.0 | 75.0 | 50.0 | 100.0 | 1.00 | 0.0 | 0.272 | 0.272 |
| 10170-1 | B_inventory | 244 | 16x16x12 | 20 | 365 | 67 | 121 | 30.0 | 0 | 20 | — | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.00 | 0.0 | 31.781 | inf |
| 10170-1 | D_bottom_up | 244 | 16x16x12 | 20 | 365 | 67 | 121 | — | 20 | 0 | 0.24 | 100.0 | 100.0 | 50.0 | 0.0 | 100.0 | 1.00 | 0.0 | 0.241 | 0.241 |
| 10170-1 | D2_bottom_up_any_offset | 244 | 16x16x12 | 20 | 365 | 67 | 121 | — | 20 | 0 | 0.51 | 100.0 | 100.0 | 80.0 | 10.0 | 100.0 | 1.00 | 0.0 | 0.508 | 0.508 |

