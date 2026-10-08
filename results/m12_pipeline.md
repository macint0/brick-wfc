# M12 — Alternate-build pipeline

**Done.** `python -m brickwfc.alt SET` produces k alternate builds for a real set, as `.ldr` files with
one `0 STEP` per layer. Mac stepped through `out/alt/10182-1/build_01.ldr` in Studio on 2026-10-08 and the
instructions play back correctly. Every selected build fits the set's inventory, is whole, is supported,
stands on a table (finite required clutch), and is one piece. A target shape is optional: a primitive, a
silhouette image (with height and color maps), or a model.

`python -m brickwfc.alt SET|parts.csv|model.mpd [--shape ...] [--n 200] [--k 8]`: generate (D2 + learned
style) → verify (integrity, inventory, support, shape, physics on a table, size floor) → dedupe → judge
(size-matched style divergence) → select (diversity-aware top-k). Writes `.ldr` files with one `0 STEP` per
layer, isometric previews, a contact sheet and `stats.json`.

## Step 1b — tip-overs

### Diagnosis

On 10182-1, 186 of 200 step-1 candidates needed infinite clutch (`physics.required_clutch = inf`).

**What infinite clutch means.** When we only ask whether *some* clutch is enough, the per-stud clutch is
unbounded. A stud contact can then pass any vertical force and any tilting moment, so parts joined through
studs act as one rigid body (a *cluster*), and only the table is push-only. A build therefore needs finite
clutch iff every cluster's centre of mass lies in the convex hull of its ground contacts.
`bricks/balance.py` computes this exactly with union-find and a 2D hull. `physics.tipping_clusters`
returns the failing clusters. It agrees with the LP on 240/240 pipeline candidates (200 from 10182-1, 40
from 6372-1) and on 40 random builds in the tests. A local cantilever can make the required clutch large,
but never infinite.

**Failing clusters** (step-1 candidates):

| set | builds with inf clutch | tipping clusters / failing build | cluster size (parts, median) | share of build (median / max) | on a single ground part | COM outside hull (studs, median / max) | clusters per build (median) |
|---|---|---|---|---|---|---|---|
| 10182-1 | 186/200 | 2.65 | 5 | 0.3% / 1.5% | 93% | 0.50 / 5.23 | 84 |
| 6372-1 (n=40) | 10/40 | 1.1 | 4 | 3.0% / 4.5% | 100% | 0.15 / 0.70 | 11 |

So the failures are neither (i) the whole build tipping over (no tipping cluster is more than 1.5% of its
build) nor (ii) a cantilever inside a connected structure. They are **(iii) small separate stacks**: a few
parts standing on one ground part, carrying a part that overhangs the base. This happens because D2 builds
are not one connected object. A 10182-1 build falls apart into a median of 84 separate clusters if lifted.

### Fix

`BottomUpBuilder(balanced=True)` keeps the clusters while it places parts (`balance.Balance`). It refuses a
part (and tries the next offset or part) if that part would push its merged cluster's centre of mass outside
the cluster's ground hull. Each cluster is checked after every change, so every build needs finite clutch
by construction. The flag is off by default, so the M9b–M11 tables reproduce; the pipeline turns it on
(`--no-balance` switches it off).

The no-shape default grid also changed from M10's 12-plate grid (35×35×12 for 10182-1) to a cube in cells:
side = height = ⌈∛(room × inventory cells)⌉. `--height 12` restores the old grid.

### Before / after (same 200 seeds per condition; `experiments/balance.py`)

| set | condition | grid (WxDxH) | physics pass % | valid % | utilization % | clusters/build | median clutch (finite) | judge (size-matched) | s/build |
|---|---|---|---|---|---|---|---|---|---|
| 6372-1 | M10 grid, no check | 12x12x12 | 76.0 | 76.0 | 100.0 | 9 | 9.0 | -0.279 | 0.39 |
| 6372-1 | M10 grid + check | 12x12x12 | **100.0** | 100.0 | 100.0 | 9 | 9.0 | -0.278 | 0.42 |
| 6372-1 | cube, no check | 12x12x12 | 76.0 | 76.0 | 100.0 | 9 | 9.0 | -0.279 | 0.43 |
| 6372-1 | cube + check (new default) | 12x12x12 | **100.0** | 100.0 | 100.0 | 9 | 9.0 | -0.278 | 0.42 |
| 10182-1 | M10 grid, no check | 35x35x12 | 7.0 | 7.0 | 100.0 | 82 | 144.0 | -0.266 | 13.48 |
| 10182-1 | M10 grid + check | 35x35x12 | **100.0** | 100.0 | 100.0 | 82 | 144.0 | -0.268 | 13.37 |
| 10182-1 | cube, no check | 25x25x25 | 64.5 | 64.5 | 100.0 | 31 | 160.4 | -0.253 | 13.90 |
| 10182-1 | cube + check (new default) | 25x25x25 | **100.0** | 100.0 | 100.0 | 32 | 192.0 | -0.254 | 14.30 |

- The check takes physics from 7% / 76% to 100% on both sets. Utilization (100%) is unchanged, the judge is
  unchanged (within ±0.002), and time per build is unchanged.
- For 134 parts, M10's grid was already a 12×12×12 cube, so on 6372-1 the grid change is a no-op. On
  10182-1 the cube by itself lifts physics from 7% to 64.5%, cuts clusters per build from 82 to 31, and
  improves the judge (−0.266 → −0.254).
- s/build is with 10 builds in parallel. A single 10182-1 build alone takes about 4.4 s.
- Valid % here counts every check but the size floor, which drops the smallest 10% by design.

### Open points

- **Builds are piles, not objects.** Even the cube builds are 32 separate clusters. A connectivity check
  (one cluster, or a minimum share in the largest) would be the next rule if alternate builds should be
  liftable.
- **A cube in cells is flat in reality.** A plate is 0.4 studs tall, so a 25×25×25-cell grid is 200 × 200 × 80 mm.
  Changed in step 2: the default is now a cube in millimetres (height in plates ≈ 2.5 × side; 10182-1:
  18 × 18 studs × 44 plates).
- The required clutch of the remaining builds is large (median 192 plate-cell weights per stud on 10182-1),
  so cantilevers are long. With realistic clutch limits (`--max-clutch`) that becomes the binding
  constraint.
- The WFC generator in the pipeline has no balance check (it stays a compared method). This is one reason
  its physics pass rate is lower than D2's.

## Step 2 — target shapes from images and models

`--shape` now also takes:
- a **silhouette image**: top-down, one pixel per stud, opaque or dark pixels inside. It is extruded
  `--shape-height` plates and the footprint is scaled to the inventory's volume. With `--height-map`
  (grey value = plates), the whole shape is scaled uniformly instead.
- an **.ldr/.mpd model or a set number**: voxelized (catalog parts on the stud grid), each column filled from
  the ground to its top cell, then scaled uniformly. Solid columns lose the model's overhangs and interior
  voids (rooms), so a model shape becomes a heightfield. `--shape-exact` keeps the exact voxel cells instead.
- `--color-map`, an image aligned with the silhouette: each column prefers the nearest inventory color.
  The builder tries that color's parts first and falls back to its normal sampler (WFC: the same preference
  as a sampling bias).

Code: `bricks/shapes.py` (`column_heights`, `from_heights`, `from_model`, `preferred_colors`, `resample`,
`bounds`), `alt/target.py`, and `BottomUpBuilder.build(preferred=)`.

Why solid columns are the default (measured with the step-2 code, before 2b): 6372-1's parts built into
6380-1's shape (40 seeds) reach 76–84% fill using 90–94% of the parts (judge −0.27). From the voxelized cells alone (sparse walls and fragments)
they reach only 37–49% fill, using 61–72% of the parts (judge −0.32).

## Step 2b — one liftable piece

A build must be **one cluster** of stud-connected parts. Verify now fails builds with more clusters as
`disconnected`, and `stats.json` reports per-build cluster counts. With the tip-over check alone, 94–100% of
builds are several pieces (median 4 clusters on 6372-1, 15 on 10182-1). The extra clusters are small
stragglers: the largest cluster holds 88–97% of the parts.

Two rules in `BottomUpBuilder` (both on in the pipeline; `--no-bridge`, `--no-connect`):
- **bridge**: a part tries all its offsets at the visited cell and takes the one that rests on the most
  distinct clusters.
- **connect** (repair pass): keep the largest cluster, return the other clusters' parts to the inventory,
  and fill again on layers ≥ 1 only. Every part placed there rests on the kept cluster, so the build is one
  piece by construction. The pass can put a part under an existing overhang, so the builder now also refuses
  a tile with anything directly above it. In the main pass that never happens: builds there are
  bit-identical to before for the default, any-offset and balanced settings.
  The pass re-samples with the same seeded generator, so builds stay deterministic. The test
  `test_resume_and_workers_give_the_same_candidates` (workers=1 vs 2, and a resumed cache) runs with the
  repair pass on and gives identical candidates.

Gap-filling with leftover parts (the fallback first considered) would not work: utilization is already
~100%, so no parts are left.

Same 200 seeds per condition, default grid (a cube in millimetres) with the tip-over check
(`experiments/balance.py --study connect`; `results/m12_connect_summary.json`):

| set | condition | grid (WxDxH) | physics % | valid % | utilization % | clusters/build | connected % | median clutch | judge (size-matched) | s/build |
|---|---|---|---|---|---|---|---|---|---|---|
| 6372-1 | tip-over check only | 9x9x21 | 100 | 5.5 | 99.3 | 4 | 5.5 | 9.8 | -0.263 | 0.54 |
| 6372-1 | + bridge | 9x9x21 | 100 | 7.0 | 99.3 | 4 | 7.0 | 10.2 | -0.262 | 0.57 |
| 6372-1 | + connect | 9x9x21 | 100 | **100** | 99.3 | 1 | **100** | 9.0 | -0.264 | 0.91 |
| 6372-1 | + bridge + connect (default) | 9x9x21 | 100 | **100** | 99.3 | 1 | **100** | 10.5 | -0.263 | 0.93 |
| 10182-1 | tip-over check only | 18x18x44 | 100 | 0.5 | 99.9 | 15 | 0.5 | 214.5 | -0.246 | 13.2 |
| 10182-1 | + bridge | 18x18x44 | 100 | 0.0 | 100.0 | 13 | 0.0 | 215.9 | — | 13.8 |
| 10182-1 | + connect | 18x18x44 | 100 | **100** | 100.0 | 1 | **100** | 212.5 | -0.247 | 17.0 |
| 10182-1 | + bridge + connect (default) | 18x18x44 | 100 | **100** | 100.0 | 1 | **100** | 209.0 | -0.246 | 17.0 |

- The repair pass makes every build one piece on both sets. Utilization, judge and the required clutch are
  unchanged; generation takes ~30% longer on 10182-1.
- The bridging preference on its own barely matters (connected 5.5% → 7.0% on 6372-1, 0.5% → 0% on
  10182-1). It stays on but could be dropped.
- Judge: "—" means no valid build to judge.
- s/build is generation plus physics, with 10 builds in parallel.

**Physics speed.** On the taller default grid (10182-1: 44 plates), the default HiGHS solver took 79 s
mean and 470 s max per build. `physics.table_clutch` (used by the pipeline) returns inf when a cluster
tips (exact, no LP), and otherwise solves the LP by interior point, falling back to the default solver
if that fails. It agrees with `required_clutch` to 7e-15 (relative) on 80 cached candidates, including
feasibility on all of them. The slowest build went from 146 s to 4.6 s. `required_clutch` itself is
unchanged, so M7–M11 reproduce.

## Step 3 — one spaceship, six sets

`experiments/demo.py`. The target is a top-down spaceship: a silhouette, a height map in whole bricks
(wings 3 plates, fuselage and fins 6, cockpit 9) and a color map (`examples/spaceship_*.png`). It is
scaled to each set's inventory volume. Per set: D2 (100 candidates, k = 4), D2 without the connect pass
(100, to show what the one-piece rule costs), and WFC with the support, inventory and shape constraints
(10 candidates, 30 s cap, only on sets of at most 400 parts; its backtracking history needs ~1.5 GB per
worker on 10182-1). Defaults: tip-over check, bridge, connect with 10 rounds (see below).
Figure: `results/m12_demo_sheet.png` (the target, then the top-judged build per set). Data:
`results/m12_demo_summary.json`.

| set (year) | generator | parts | grid (WxDxH) | built % | stands % | one piece % | valid % | fill % | IoU | utilization % | best judge | s/candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 374-1 (1978) | D2 | 219 | 40x26x8 | 100 | 100 | 100 | **100** | 59.5 | 0.59 | 66.1 | -0.300 | 10.6 |
| | D2, no connect | | | 100 | 100 | 0 | 0 | 79.5 | 0.80 | 93.2 | — | 1.4 |
| | WFC | | | 0 | — | — | 0 | — | — | — | — | 30.2 |
| 6378-1 (1986) | D2 | 203 | 37x25x7 | 100 | 100 | 100 | **100** | 69.9 | 0.70 | 91.6 | -0.340 | 15.3 |
| | D2, no connect | | | 100 | 100 | 0 | 0 | 71.7 | 0.72 | 94.6 | — | 2.1 |
| | WFC | | | 0 | — | — | 0 | — | — | — | — | 31.7 |
| 7743-1 (2008) | D2 | 279 | 40x26x8 | 100 | 100 | 100 | **100** | 63.0 | 0.63 | 79.3 | -0.336 | 34.8 |
| | D2, no connect | | | 100 | 100 | 0 | 0 | 71.9 | 0.72 | 92.9 | — | 4.0 |
| | WFC | | | 0 | — | — | 0 | — | — | — | — | 118.9 |
| 5891-1 (2010) | D2 | 323 | 43x28x8 | 100 | 100 | 100 | **100** | 65.1 | 0.65 | 81.2 | -0.340 | 22.6 |
| | D2, no connect | | | 100 | 100 | 0 | 0 | 76.8 | 0.77 | 92.6 | — | 2.7 |
| | WFC | | | 0 | — | — | 0 | — | — | — | — | 30.3 |
| 4956-1 (2007) | D2 | 397 | 50x32x10 | 100 | 100 | 100 | **100** | 52.3 | 0.52 | 74.1 | -0.314 | 48.5 |
| | D2, no connect | | | 100 | 100 | 0 | 0 | 61.6 | 0.62 | 88.6 | — | 6.4 |
| | WFC | | | 0 | — | — | 0 | — | — | — | — | 112.5 |
| 10182-1 (2007) | D2 | 1514 | 68x43x13 | 100 | 100 | 100 | **100** | 74.3 | 0.74 | 84.4 | -0.234 | 139.9 |
| | D2, no connect | | | 100 | 100 | 0 | 0 | 81.4 | 0.81 | 96.2 | — | 21.3 |
| | WFC | | | not run (memory) | | | | | | | | |

Fill, IoU and utilization are over builds that pass every check but connectivity (for D2 these are the
valid builds). s/candidate is generation plus physics, with 10 in parallel (WFC: 2).

- **D2: every candidate is valid on every set.** It stands, is one piece, and stays within inventory and
  shape. Fill is 52–74% and utilization 66–92% of the recognized parts. The color map shows on every
  set, mapped to its nearest inventory colors (e.g. 7743-1's blue-and-white wings).
- **The one-piece rule costs 2–20 points of fill** (6378-1: 72 → 70; 374-1: 80 → 60) and 3–27 points of
  utilization. The cost is highest for inventories of mostly 1-wide bricks: those link only along their
  length, and there are few wide plates to tie rows together.
- **WFC builds nothing**: 0 of 50 candidates finish within the cap on the five sets it ran on, as expected
  from M9b (WFC + inventory at full-catalog scale). The cap is checked between WFC steps, so a run can
  overshoot it (up to 119 s). WFC also has no tip-over or connect pass, so even a finished WFC build might
  not stand or be one piece.

**Connect rounds.** With one repair round (step 2b), the flat spaceship splits into 50–100 clusters and
the build keeps only the largest. Fill on 7743-1 falls to 37% and utilization to 45%. More rounds place
the returned parts anywhere again (they may join the kept cluster or each other) and keep the largest
cluster again; the last round refills layers ≥ 1 only, so one piece stays guaranteed. 7743-1, 8 seeds,
1/3/6/10/16 rounds: fill 37/51/61/65/66%, utilization 45/62/78/83/84%. Time grows with the rounds, so
the pipeline default is 10 (`--connect-rounds`). The builder default stays 1, so the step-2b study
reproduces.

## Open points after M12

- **Better bridging.** Choose wide parts where they join clusters (the bridge preference only picks among
  one part's offsets), or keep a cap of wide plates for the top layers. Either would recover more of the
  fill the one-piece rule costs.
- **Time.** Up to 140 s per candidate on 10182-1 with 10 repair rounds (10 in parallel). It is fine for
  k-of-100, but slow for sweeps.
- **Clutch.** Median required clutch is 9–210 plate-cell weights per stud, depending on the set. It is
  unbounded for now; M13 calibrates `--max-clutch`.
- **Shapes.** Model shapes are heightfields by default (`--shape-exact` keeps the exact cells).
