# M12c: why connected growth stalls on the 6378-1 chair at 0.7 and 0.6

**Question.** creserve70 on the 6378-1 chair has all 50 candidates at about 3.4% fill, all "valid". creserve60 has 31 of
50 under 50%. Why?

**Answer.** It is not a base block and not the small-part supply. Nearest-neighbour resampling cuts the chair's
diagonal caster arms: an arm whose rows touch the hub only at a corner, not along a face, becomes a separate piece of
the target. Every scale of this chair is cut, from 1.0 to 0.6: the target is 2 pieces at 1.0–0.7 and 4 at 0.6. The two
failures are two consequences of that.
- **0.7:** the seed rule (the largest ground region) picks a caster on the cut-off island, 36 of the target's 979
  cells. Growth cannot leave the island, so every seed stops at layer 6 with 3–10 parts.
- **0.6:** two of the target's four ground regions are islands, so the main piece has two feet on the ground. When the growth hangs
  no part down to the second foot (30 of 50 seeds), the whole grown chair stands on one caster and tips: 87–92% fill,
  up to layer 39. The balance cut-back then keeps only its first 3 parts, which stand.
- **The broader cost:** the 6378-1 chair has never been completable in any arm. The island, 11–36 cells, is never
  built, so the largest hole is always at least 11 cells and the bar of 4 is out of reach.

## Evidence

All of it comes from replays of cached candidates with observers on the builder's `_grow_from_seed` and
`_standing_prefix`. The observers draw nothing, and every replay is identical to its cached build. Single process,
no generation.

**The target** (from each run's cache key):

| slack | grid (YxZxX) | cells | pieces | thinnest section | seed region (the largest ground region) |
|---|---|---:|---:|---:|---|
| 1.0 | 48x11x12 | 1326 | 2 (1315 + 11) | 1 | on the main piece |
| 0.8 | 43x10x11 | 1138 | 2 (1103 + 35) | 2 | on the main piece |
| 0.7 | 42x9x10 | 979 | 2 (943 + 36) | 1 | **on the 36-cell island**: 4 cells at z1–2, x0–1 (the hub's column under it is 3 cells) |
| 0.6 | 40x9x10 | 799 | 4 (778 + 12 + 7 + 2) | 1 | on the main piece: 4 cells at z3–4, x8–9 |

All 20 split targets among the 184 cached runs (every arm) are this chair.

**0.7 (creserve70).**
- **The cut:** layers 3–6 (the arms) have row z3 at x2–3 and row z4 at x4–9, which meet only at a corner. Cells (3, 3)
  and (4, 4) are diagonal.
- **The seed:** a 1×2 brick at layer 0, z1, x0 (seeds 0 and 1) or z2, x0 (seed 2).
- **The growth:** it climbs that caster and its arm, places 7–10 parts and stops at layer 6. Every prefix stands, so the
  cut-back removes nothing.
- **The first cell the growth cannot reach:** (layer 3, z4, x4), the hub cell diagonal to the arm's end.
- **The rest:** neither the post (layers 7–41, a 1×2 column at z4, x4–5) nor the seat can be reached. The hole pass
  must join the structure, and the connect repair has nothing to join.

**0.6 (creserve60).**
- **The feet on the main piece:** the 2×2 caster at z3–4, x8–9 (the seed's) and a 1×2 caster at z6–7, x1. The other
  two ground regions, z1, x0–1 and z8, x6, are islands.
- **Over all 50 seeds:**

| grown chair | reached the second foot | did not |
|---|---:|---:|
| stands (whole build kept) | 19 | 1 |
| tips (cut back to the first 3 parts) | 0 | 30 |

- **The 30:** their growth reached 87–92% fill and layer 34–39 (seeds 6 and 15 replayed), and the cut-back kept 3
  parts. The hole pass, which checks balance at every placement, then adds about 5. That gives about 4% fill and top
  layer 6, every one "valid".
- **The good seeds** (8, 11) reach the second foot by hanging from the arm and keep all 145–147 parts.
- **The 31st stall** is seed 29. Its growth itself stopped after 8 parts on the seed's caster. Not diagnosed further.

## The verify stage

The fill floor is relative: 0.5 × the run's 90th-percentile fill. In a run where every candidate stalls (0.7) the
floor is about 1.8%, so 3.7% passes, the run selects a stub, and the sweep's "valid" column says 50/50.
- **Fix (built):** `--min-fill F` (`AltConfig.min_fill`, default 0, so nothing changes). It adds an absolute floor: a
  candidate filling less than F of the target fails `low_fill`, and a run where every candidate stalls selects
  nothing. Test: `test_fill_select.py::test_min_fill_fails_a_run_where_every_build_stalls`.
- **Suggested value:** 0.5, the sweep's existing `STALL_FILL`.
- **Already reported:** the sweep report's `stalled` column (candidates under 50% fill) shows these runs: 50 at 0.7,
  31 at 0.6.

## Fixes (sketched, not built: each changes targets or generation while Session B's sweep runs)

1. **Reconnect the target after resampling** (the root fix; `shapes.scaled_to`, before supports and hollowing).
   - **Why not a scale choice:** within ±5% / ±10% of each slack's volume there is one one-piece scale factor at 1.0,
     one at 0.9 (in the ±10% band only), and none at 0.8–0.6.
   - **The fix:** while the mask has more than one face-connected piece, add an empty cell face-adjacent to two pieces.
     For a sound joint, add it in every layer the two pieces share.
   - **Measured on the 5 cached creserve targets:** one bridging cell per target reconnects it at 1.0–0.7, and three
     at 0.6.
   - **Size:** about 20 lines and a test.
   - **Cost:** it changes only targets that are cut today (all 20 cached ones are this chair), but those runs'
     cache keys change, so they rerun.
2. **Seed on the main piece** (`BottomUpBuilder._grow_from_seed`). Rank the ground regions of the target's largest
   piece only.
   - **Size:** about 8 lines.
   - **Effect:** it is identical on one-piece targets and would have saved 0.7 from the total stall. The island would
     still be missing.
   - **Status:** a guard if (1) is not taken, moot after it. It changes generation for cut targets, so it needs
     `BUILDER_VERSION` 3.
3. **The one-foot chair at 0.6** is the same cut. With (1), the cut-off feet join the main piece again.
   - **If tipping persists:** when the grown structure does not stand, run the hole pass, which hangs feet down to the
     ground, on the uncut structure before cutting back.
   - **Status:** not sketched further until (1) is measured.

## For the bench run

The bench dry run (`m12c_bench_plan.md`) checked for empty layers but not for pieces. `bench-plan` now reports a
`pieces` column, bold when more than 1. A sizing-only scan of the 108 bench targets finds 8 cut, all chairs on the four
smallest sets:

| object | set | slack | pieces | seed region on the main piece | ground regions on the main piece |
|---|---|---:|---:|---|---|
| chair | 7796-1 | 1.0 | 4 (211 + 6 + 1 + 1) | yes | 1 of 2 |
| chair | 6370-1 | 1.0 | 4 (778 + 12 + 7 + 2) | yes | 2 of 4 |
| chair | 6372-1 | 1.0 | 2 (1116 + 35) | yes | 5 of 6 |
| chair | 6378-1 | 1.0 | 2 (1315 + 11) | yes | 5 of 6 |
| chair | 7796-1 | 0.8 | 3 (171 + 3 + 3) | yes | 1 of 2 |
| chair | 6370-1 | 0.8 | 4 (663 + 12 + 5 + 2) | yes | 2 of 4 |
| chair | 6372-1 | 0.8 | 2 (905 + 36) | **no** (the 0.7 stall again) | 5 of 6 |
| chair | 6378-1 | 0.8 | 2 (1103 + 35) | yes | 5 of 6 |

Expect, unless fix (1) goes in first:
- **6372-1 chair at 0.8:** a total stall.
- **6370-1 and 7796-1 chairs:** one- or two-foot tipping, as at 0.6.
- **All 8 chairs:** never complete.

The other 100 bench targets are one piece.
