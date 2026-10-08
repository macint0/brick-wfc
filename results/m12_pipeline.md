# M12 — Alternate-build pipeline

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
  the ground to its top cell, then scaled uniformly.
- `--color-map`, an image aligned with the silhouette: each column prefers the nearest inventory color.
  The builder tries that color's parts first and falls back to its normal sampler (WFC: the same preference
  as a sampling bias).

Code: `bricks/shapes.py` (`column_heights`, `from_heights`, `from_model`, `preferred_colors`, `resample`,
`bounds`), `alt/target.py`, and `BottomUpBuilder.build(preferred=)`.

Model shapes need the filled columns. 6372-1's parts built into 6380-1's shape (40 seeds) reach 76–84%
fill using 90–94% of the parts (judge −0.27). From the voxelized cells alone (sparse walls and fragments)
they reach only 37–49% fill, using 61–72% of the parts (judge −0.32).
