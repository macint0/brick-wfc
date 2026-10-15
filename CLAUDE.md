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

**Checkpoint status (2026-10-07, after M6, M7, M9 and the M11 quick test):** the bottom-up builder matches or
beats WFC on stability, physics, inventory validity/utilization and speed (10–100×). WFC's only measured
win is filling shapes with large overhangs (at the cost of grip).

**Decision (Mac, 2026-10-08): pivot.** The bottom-up builder is the main generator; WFC (with its
constraints) is a compared method. The paper is about alternate builds from an inventory + the funnel,
comparing generators. Keep reporting WFC next to the bottom-up builder in every experiment. The full M11
run (shape + inventory) confirmed it: the any-offset bottom-up builder (D2) beats WFC there too.

**Notes (2026-10-08):**
- **3D check done:** Mac opened `out/check/orientation_check.ldr` and the M5/M6 builds in a viewer; the
  part orientation (3023/3020 long along LDraw X) and the builds look right.
- Package is installed editable (`pip install -e ".[dev]"`); no `PYTHONPATH=src` needed.
- Mac's PC runs low on memory during long experiments; experiments are resumable — rerun the same command.

**Positioning vs BrickGPT** (closest prior work): BrickGPT generates from *text* with a fine-tuned LLM
trained on ShapeNet-derived builds, and enforces stability by *rollback* (98.8% stable, ~40 s/build on GPU).
We generate from an *inventory* (+ optional shape), learn from *real official sets*, guarantee constraints
*by construction*, and run in well under a second per candidate on CPU without training.

Inspiration (credit, not a citation source): "Generate, Filter, Judge, Select" essay —
https://content.moldandyeast.com/forage/y6fmx6n4

## Working rules for Claude Code

- **Quality over speed (Mac, 2026-10-09).** Generation time is not a constraint: minutes per candidate and hundreds of
  candidates per run are fine if the selected build gets better. Report time, but never trade build quality for it.
- Work **one milestone at a time**. When a milestone's "Done when" passes, stop and summarize; don't start the next one unasked.
- Python 3.11+, `numpy`, `Pillow`, `scipy` (LP solver for physics, M7+), `pytest`, `trimesh` (mesh voxelizer for 3D
  targets, approved by Mac 2026-10-08 for M12b). Ask before adding any other dependency.
- Every random choice goes through a seeded `numpy.random.Generator` passed in explicitly. Same seed → same output.
- Type hints, small modules, no global state. Prefer clear code over clever code — this will be read by reviewers.
- Every milestone ships with tests. Run `pytest` before declaring done.
- Log per-run stats: attempts, contradictions, cells collapsed, wall time. These become paper metrics later.
- Don't use the LEGO trademark in names, package, or output branding. Use "brick".
- Commit after each milestone. No Claude co-author / session trailers in commits or PRs.
- Long experiments must save results incrementally and be resumable (runs can be killed under memory pressure).
- Experiments run in parallel across seeds/sets (`ProcessPoolExecutor`, `--workers`, default `cpu_count - 2`;
  Mac's PC: 12 logical cores, 16 GB). Output must be identical to a serial run (per-seed `Generator`, results
  written in plan order). Memory-heavy WFC jobs get their own smaller cap (`--wfc-workers`).
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
- **M5 — Multi-cell parts.** 1×1, 1×2, 2×2, 2×4 plates; integrity via adjacency + border masks; 100-build integrity test.
- **M6 — Stability-aware propagation.** `SupportConstraint` in propagation; A–D comparison over 1000 seeds
  (`results/m6_stability.md`). Post-filtering fails at scale; B is 100% stable but the bottom-up
  baseline D is too, 27× faster.
- **M7 — Physics-based verifier.** `bricks/physics.py` (LP: required clutch per stud; table or baseplate);
  physics columns for A–D (`results/m7_physics.md`). The ≥1-stud rule overstates stability; all
  failures are tip-overs; B depends on grip more than D. Follow-ups listed there (tip-over check in
  propagation, cantilever limits).
- **M9 — Inventory constraint.** `bricks/inventory.py` (`InventoryConstraint`), bounded backtracking in
  `wfc.solve_attempt`, 10 real sets (`results/m9_inventory.md`). Post-filter 1.5% valid; WFC + inventory
  100% valid, 93% of parts used, 1.4 s/build; bottom-up 100% valid, 99.9% used, 99% physically stable,
  0.014 s/build.
- **M11 — Target shape.** `bricks/shapes.py` (`ShapeConstraint`, primitives, `sized_for` scales a shape to an
  inventory's volume, IoU), bottom-up `allowed` mask. Quick test, shape only (`results/m11_shape_quick.md`),
  and shape + inventory on 10 sets × 5 shapes (`experiments/shape_inventory.py`,
  `results/m11_shape_inventory.md`): every build valid for every generator. WFC beats the original
  bottom-up builder D on fill (73% vs 68%), but `BottomUpBuilder(any_offset=True)` (**D2**: a part may
  cover the visited cell with any of its cells) beats both: 78% fill, best utilization and physics, 20×
  faster than WFC. WFC keeps a small edge on overhangs (mushroom 53% vs 50%) at the cost of grip.
  **Use D2 as the bottom-up generator from here on**; D stays for reproducing earlier tables.
  Not done: shapes from an `.ldr` model or heightmap PNG (only primitives so far).
- **M8 — Part library.** `parts.CATALOG`: 63 rectangular plates, bricks (3 layers) and tiles (no studs),
  including lookalikes (2877, 6141, 2412b, …) kept as their own parts. Integrity in all 6 directions, nothing
  on tiles, support needs a stud, physics knows bricks and tiles. Usable share of the 20 OMR sets: 8% → 51%
  (`results/m8_parts.md`, `experiments/coverage.py`). Bottom-up builds full inventories (746 parts) in 2–5 s;
  WFC does not scale to full inventories yet. `PLATE_FILES` keeps M7/M9/M11 reproducible.
  Mac checked `out/check/catalog_check.ldr` in Studio (2026-10-08): sizes and orientations look right.
- **M9b — Inventory with the full catalog + set selection.** `experiments/inventory.py --catalog full`
  (`results/m9b_inventory_catalog.md`): builds use 35–67% of each set's parts; bottom-up D/D2 100% valid,
  99.5% used, up to 746 parts in ≤ 4.4 s; WFC + inventory (`wfc.run(time_limit_s=30)`) 2.5% valid, 0/20 on
  7 of 8 sets (late inventory dead ends + raw cost; fixes listed there, not attempted). D2 stands 83.5%
  (bricks tip over more). `experiments/sets.py`: 28 building sets for M10 (≥ 50% recognized, ≥ 50 parts,
  ≥ 50% of recognized parts on the grid, no re-releases; `results/sets_selection.md`).
- **M10 — Learned style.** `bricks/style.py`: contact statistics from 28 real sets (P(part on part),
  P(part beside part), same-color rates, support counts, part/color frequencies), `StyleBias` (likelihood
  ratios; `BottomUpBuilder(style=)`, `wfc.run(bias=)`), and the judge = -divergence of a build's contact
  statistics from the learned ones (a per-contact likelihood is gamed by repetition; the divergence is
  size-dependent, so compare size-matched: `style.size_matched`). `experiments/style.py` (4-fold CV, 21
  training sets, parallel workers; `results/m10_style.md`): learned style moves builds closer to held-out
  sets for D2 (23/28 sets with X's parts, 25/28 without counts) and WFC (12/13). Under the judge, D2 beats
  WFC on 13/13 sets at ~1/100 of the time. Contacts help more than frequencies when counts are fixed.
- **M12 — Alternate-build pipeline.** `python -m brickwfc.alt SET|parts.csv|model.mpd [--shape ...] [--n] [--k]`
  (`src/brickwfc/alt/`): generate with D2 + learned style → verify (integrity, inventory, support, shape, physics
  on a table, size floor, one piece) → dedupe → judge (size-matched) → select top-k; writes `build_XX.ldr` with one
  `0 STEP` per layer, previews, `sheet.png`, `stats.json`. Mac stepped through a build in Studio (2026-10-08).
  Pipeline defaults, each by construction in `BottomUpBuilder`: `balanced=True` (no cluster's centre of mass
  outside its ground hull; `bricks/balance.py`, exact vs the LP; physics pass 7% → 100%), `connect=True` with
  `--connect-rounds 10` (keep the largest stud-connected cluster, return the rest, refill; one-piece 0.5% → 100%),
  physical-cube default grid. `physics.table_clutch`: exact tip-over shortcut + IPM LP (146 s → 5 s worst case).
  Shapes: primitive, silhouette PNG (+ height map, + color map → preferred colors), `.ldr`/set number (heightfield
  unless `--shape-exact`). Demo (`experiments/demo.py`, `results/m12_demo_sheet.png`): one spaceship from six sets
  (1978–2010, 203–1514 parts): 100% valid, fill 52–74%, utilization 66–92%; WFC 0/50 within 30 s. Write-up and open
  points: `results/m12_pipeline.md` (connectivity costs 2–20 fill points, most on 1-wide-brick sets; up to 140 s per
  candidate on the largest set; `--max-clutch` uncalibrated).

### M12b — 3D targets, learned proposal, looks (Mac, 2026-10-08)
Mac's framing: BrickGPT-style generation from a real inventory with a bigger catalog, constraints guaranteed at
decode time. The bottom-up builder is the decoder; the *proposal* in it is pluggable (today: M10 statistics).
**Status (2026-10-09, 22:30):** steps 1–4 done and merged; the "Done when" below holds. **One decision for Mac**
at the end of this entry (defaults for `--skin` / `--symmetric`).
1. **True 3D targets — done** (`results/m12b_brickgpt.md`, `m12b_overhangs_tables.md`, figures
   `m12b_before_after.png`, `m12b_opentops_before_after.png`, `m12b_hollow_before_after.png`).
   `--shape brickgpt:<id>` loads a StableText2Brick structure (`bricks/brickgpt.py`; their data, not their model;
   all 8 brick sizes map 1:1 onto the catalog), `--shape model.stl|.obj` voxelizes a mesh (`bricks/mesh.py`,
   `trimesh`), `--hollow N` keeps a shell. Head-to-head on 6 objects × 3 sets: every build 100% valid / physics /
   one piece; fill 69–85% on car, sofa, vessel, bench; table 54–78%; chair 15–74% (bimodal on the small sets,
   diagnosed: the caster base is too small for the balance mask, arms never meet at the hub, repair keeps one arm;
   `--supports --support-height 6` adds one 3-cell column under the hub: low builds 8/20 → 0/20, mean fill
   0.40 → 0.63, builds within real clutch 14/20 → 19/20 on 6378-1, table builds unchanged). Their table is 3 pieces and their chair needs clutch 816. **Open tops** (a studless top only
   where the target is empty above; `AltConfig.open_tops`, default on, `--no-open-tops`) fixes tiles capping thin
   stems: fill up on all 18 pairs (table 6378-1: 15 → 54%), 1.3–7.6× faster. Support columns (`--supports`) help
   only where the object hangs over nothing (chair, bench). Clutch calibrated from StableLego: a real stud holds
   1111 plate-cell weights; a capped `--max-clutch 1111` binds only on 10182-1 and removes builds instead of
   fixing overhangs. **Open point for Mac:** full chairs need 1427–5212 clutch, above real; `--supports` keeps
   84–100% within 1111. Decide whether `--max-clutch 1111` becomes the pipeline default. Hollow: sound, no clear
   win, off by default.
2. **Learned proposal model — trained, comparison running.** 5 tokens per part (Y, Z, X, shape, color) with a
   BOS/SRC/SCALE/mask-patch prefix (`bricks/tokens.py`, `experiments/export_tokens.py`), transformer
   d256 / 6 layers / 8 heads, 5.16M params, trained on BrickGPT's train split + the real sets on Mac's RTX 3060
   (`training/train.py`; cu124 torch in a scratch venv, not a project dependency; Colab optional). Run 1
   overfit the real sets; run 2 (`--set-share 0.05`, `--val-sets 6378-1 31048-1`, early stop at step 1500) is the
   model: `data/models/proposal_run2.npz` + `vocab.json` (gitignored). numpy inference with a KV cache
   (`bricks/proposal.py`, ~6 ms per cell query), decoded inside `BottomUpBuilder(proposal=)` with every mask.
   Parts outside the vocabulary (slopes, corners) get the uniform fallback. Comparison vs statistics under the
   judge: `experiments/proposal.py` (fold 0, 5 seeds, stats_random / stats_raster / proposal_raster, style v2,
   `results/m12b_proposal.md`). **Inventory-only result: the proposal loses narrowly** (higher judge on 1/7 sets,
   mean −0.0025, 7× the time; the gain over M10's random-order builder is the raster order's, not the model's; an
   independent check against each set's own statistics agrees; 5–30% of each set's parts are outside the
   model's vocabulary, which does not explain the result). **With a target** (car 4b15b71c on the 3 smallest fold-0
   sets, 20 candidates, `--proposal` / `--order` in the pipeline, `results/m12b_proposal_shape.md`): the model wins
   the judge on 2/3 sets (+0.0065 vs the raster control; the judge-free distance confirms one of the two), loses
   fill by 1.4 points, costs 4–20× per candidate; every candidate valid, standing, one piece. Net: the learned
   proposal is not a clear win over statistics at this size (5M params, 1500 steps); the statistics stay the
   no-training baseline and the pipeline default. Step 3 (symmetry, clean skins) is therefore still open:
   measure whether either arm produces them before building anything.
3. **Clean skins and mirror symmetry — done, measured first** (`results/m12b_skins_measure.md`: our skins show 3.6–8.4
   distinct parts per all-skin 4×4 window where real sets show 1.5–4; 7–22% of mirrorable parts have their twin placed,
   real sets 80–100%). `--skin` (`bricks/skin.py`: largest fitting part first on the target's surface) and
   `--symmetric` (`bricks/symmetry.py`: the target's best vertical mirror plane; a car or table ≥ 0.8 symmetric after
   scaling is made exactly symmetric, a chair at 0.71–0.77 is not; parts placed with their mirror image when it fits),
   both **off by default**. 9 set × object pairs × 4 arms, 50 candidates each (`experiments/skins.py --steps compare`,
   `results/m12b_skins.md`, sheet `m12b_skins_sheet.png`): skin +2.4 fill points, −0.7/−0.8 parts per window, judge
   −0.017 (worse on 9/9, the judge sees contact statistics only); symmetric +35 points mirrored, fill −2, judge within
   noise; both: cleanest skins, +31 mirrored, judge −0.021. The 6378-1 table/car under both flags are the first builds
   that look like the object (table 66 → 81% fill, 4.2 → 2.4 parts per top window, 68% mirrored). Cost: on the 5891-1
   chair `--skin` halves the valid builds (big parts cantilevered off the seat fail the clutch cap). A soft preference
   `--skin-power a` (choice weight × cells^a on skin cells; `results/m12b_skins_soft_sweep.md`, `m12b_skins_soft.md`)
   at a=1 gives about half the cleanup at a flat judge but gives back most of the visible gain; the hard sort stays
   what `--skin` does (cf, 2026-10-09: the judge is not the arbiter of looks). Skins numbers are at 3c7ef1e (box sizing,
   lattice supports). Under fillable sizing the 5891-1 chair scores 0.806, so the gate is 0.83 (`--symmetrize-min-score`,
   a fitted threshold: chairs ≤ 0.806, cars and tables ≥ 0.848; `results/m12b_symmetry_threshold.md`); the doubled-base
   chair builds and looks acceptable but is no longer BrickGPT's chair. Union symmetrization adds 9–15% cells to cars;
   an intersection variant is the M13 alternative if symmetry becomes a default.
4. **Slopes and corner parts — done** (`results/m12b_catalog.md`): catalog 63 → 88 parts (corner plates/bricks,
   slopes, inverted, corner and ridge slopes, cheese slopes) with per-cell geometry (footprint, stud cells, seated
   cells; a slope is its bounding box, the sloped face accepts nothing). Style statistics v2 relearned. Recognized
   share of the 28 building sets 61 → 69%, on-grid 49 → 57% (Creator houses up to 90%). Slope-aware preview.
Also landed: `rebrickable:<set>` / any set number as the inventory from Rebrickable's bulk CSVs
(`bricks/rebrickable.py`, `results/m12c_rebrickable.md`); diversity metric for M13 (Leinster–Cobbold, threshold
kernel normalized per setup by the median D2 pair distance, `funnel/diversity.py`, `results/m13_diversity.md`);
paper skeleton in `paper/`. Not now: style-bias tuning, color logic, WFC.
**Decisions (Mac, 2026-10-09 morning):** (a) yes: `--supports --support-height 6` is the default with a 3D target;
(b) yes: `--max-clutch 1111` (real clutch, StableLego calibration) is the pipeline default everywhere; (c) done (fd9015b): 1a/1d rerun on the 88-part catalog
with these defaults, figures redrawn; every valid build within 1111 by construction, chairs 58–81% fill on every set.
(d) close step 2 with the result as is: statistics stay the baseline and the default, the comparison is a paper result,
no more model training now.
**Sizing and supports (merged 3985e76, `results/m12b_sizing.md`, `m12b_sizing_before_after.png`; figures redrawn):** the
rerun's two failures (slope-heavy sets lose 15–24 fill points because a slope counted as its box; the 4956-1 table
starved in its post) and two more found on the way are fixed by construction, as defaults: **fillable sizing**
(`--sizing fillable`; a slope counts its stud cells × 1 layer, studless slopes 0; `--sizing box` is the old path),
**thin-aware scale** (among scale factors within ±5% of the target volume, the one whose thinnest horizontal section is
thickest; nearest-neighbour resampling had thinned the 10182-1 chair's post from 8 cells to 3 and no support column could
reach its seat), and **progressive support cover** (`shapes.with_supports`: 2×2 columns one at a time under the overhang
cell farthest from every held cell until all are within 3 studs; replaces the 4-stud lattice, which put 1–72 cells under
the same chair depending on scale; a single centre column failed at 10182-1 scale). Results, mean fill of valid
candidates: 5891-1 car 61 → 77%, 4956-1 table 25 → 61% (0 → 100% reach the top), 5891-1 chair 58 → 68%, 4956-1 chair
58 → 69%, 10182-1 car 83 → 87%; the others within noise. Known cost: 4956-1 car 73.3 → 72.0 (3 SE), valid 47 → 49.
Measured and not adopted (code removed): parts reserved for thin sections, thin-first order. Support heights 6 and 9 give
identical targets on all six demo objects. Lattice-era numbers are labelled "lattice at fd9015b" in the write-ups.
**Decision for Mac:** make `--skin` and `--symmetric` the defaults for 3D targets? 64 recommends symmetric on, skin as a
flag; cf recommends both on (the eye prefers them, the judge cannot see symmetry), with the 5891-1 chair's stability cost
as the caveat. Nothing changes until Mac decides.
**Done when:** the six-set demo re-rendered with a 3D target looks clearly better side by side (yes:
`m12b_before_after.png`), every build still valid/stable/one piece (yes), the learned proposal is compared to
statistics under the judge (yes, `m12b_proposal.md`, `m12b_proposal_shape.md`), and the per-set coverage rises (yes).

### M12c — Complete objects (Mac, 2026-10-10)
Mac's bar: "the build should be complete first, not a part of a chair but a complete chair." A smaller complete object
beats a larger partial one; completeness before size and looks. Working bar (cf): fill ≥ 97%, no hole larger than 4 cells,
≥ 98% of the exposed surface filled (`alt/features.completeness`; the pipeline prints fill, holes, largest hole, surface).
**Status (2026-10-10, 20:00):** causes measured, four fixes merged, defaults changed, three reorderings measured and kept
as flags; **the first complete candidate exists** (5891-1 chair, reserve inside connected growth at 0.8: 98.7% fill, largest
hole 4, surface 98.3%) and the judge did not select it. The limit for the rest is measured: the sets' small-part supply,
spent on packing remnants that no order or placement rule avoids.
Everything below is in `results/m12b_complete.md` (+ `_trace/_sweep/_holes/_old_vs_base.json`, sheets).
- **Cause trace** (`experiments/complete.py --steps final trace report`, 160 builds, a builder `trace` hook with no rng
  draws): of the empty target cells, 66% had no stud below when visited (overhang undersides), 16% were tips discarded by
  the one-piece repair, 11% ran out of parts or fit nothing, ~1% each balance/geometry/missed. Found on the way and fixed
  (60b3a3b): `_fit_key` ignored studs, so a failed tile made the builder skip the plate of its box under open tops;
  `builder_version: 2` in the cache key; effect on the earlier tables −0.9 to +2.5 fill points (dated notes on five
  write-ups, no reruns).
- **Hanging hole pass** (`--holes --hang`, e910ad2; `support.is_stable(hanging=)`, physics unchanged): after the main
  pass, a part may hang by its studs from a part above. Selected build better on 9/9 pairs vs the base (fill +3 to +20,
  5891-1 table 67 → 87%), largest hole smaller on 8/9, validity unchanged, clutch under the cap.
- **Usable sizing** (`--sizing usable`): parts that fit nowhere inside the scaled target are left out of the volume
  (`inventory.unusable`, erosion per orientation), rescale, fixpoint. Changes one pair (6378-1 chair: four 6×14 plates are
  19% of its volume; 75.6 → 88.6% fill, largest hole 192 → 34), identical to fillable on the other eight.
  `--fill-slack s` (target at s × the volume): 0.8 gains 2.4–15 fill points on the selected build (mean +6) but completes
  nothing (best 5891-1 table 93.3% / hole 29), so slack is a flag, not a default.
- **Thin-aware scale, two fixes** (`shapes.thinnest_section`, `fit_scale`, `overhang_moment`): an empty layer between
  base and top counts as section 0 (resampling had dropped the 6378-1 chair's 2-cell post at two volumes, 9% fill, 50/50
  "valid"), the band widens once to 10% if every factor cuts the shape; and among the thickest factors the one with the
  smallest overhang moment (cells above a section × their centre-of-mass offset beyond its hull, max over layers) wins:
  at 0.9 of the 5891-1 chair's volume the post landed 1.2 studs off the seat's centre of mass, 47/50 builds needed more
  than real clutch (66% of the binding clutch at the seat-on-post joint); with the moment key 47/50 valid. First evidence
  that the scale's resampling phase decides stability. Only 3 of 90 sized targets changed.
- **Hole diagnosis** (`--steps holes`, usable 0.8 builds): the missing 7–19% is mostly out of small parts (≥ 52% of
  empty cells on 8/9 pairs: 1×1, 1×2, 1×3 plates and 2×2 corners, all spent in the main pass before the hole pass starts,
  0 left on every pair while 34–237 larger parts fit nowhere), then support (20–72%: caster tips, table rims, car
  undersides); unreachable 0, shape-impossible ≤ 10%.
- **Connected growth order** (`--order connected`, 0863884, 64; off by default): one piece from a ground seed, lowest
  layer first, balance by the longest standing prefix. Sweep vs the default at 1.0 / 0.9 / 0.8 volume
  (`results/m12b_connected.md`, merged 459e9af): the selected build is more complete on 7/9 pairs at the defaults (chairs
  +6 to +8 fill points, tips filled 40 → 100%) and worse on two (6378-1 chair −2, the judge's pick keeps fewer casters;
  4956-1 table −4, the top's underside over the post stays open), 8/9 at 0.8, where the 5891-1 chair reaches 96.4% fill,
  largest hole 14, surface 95.5% (closest to the bar; 0 of 2700 candidates complete). Stalls (seed under 50% fill, 57 of
  1350) are never the balance cut: 26 are a base block (the seed column covers its own studs, the stair-stepped arms are
  unreachable), 31 ran out of small parts while climbing a thin leg (27–101 placements would fit with any catalog part).
  **Stays a flag** (not better on every pair); the small-plate reserve inside growth is the combination to measure next.
- **Small parts kept for the hole pass** (`--reserve-small`: parts of ≤ 3 cells tried at a main-pass cell only after
  every larger part failed there; `--small-last a`: their choice weight × (cells/4)^a; 8584bed, ee; both off by
  default). 6 arms × 9 pairs × 50 candidates at the defaults and at slack 0.8 (`results/m12b_complete.md`, fourth part,
  merged 26ab91f): **no arm passes the rule** (reserve, the best, 6/9 pairs at 1.0 and 3/9 at 0.8; small-last 1
  5/9 and 3/9; small-last 2 3/9 and 2/9), none complete (0 of 2700). Reserve raises the selected build's fill on 6/9
  (mean +2.1) and on 8/9 at 0.8 (+2.5), fewer holes on 9/9, 0.7× the time, but the largest hole grows on 3/9 and 5/9
  (small holes close, the large ones stay or merge) and 0.8 loses 1–2 valid on 3 pairs. Diagnosis of reserve at 0.8: 0
  small parts left at the last hole pass on 8/9 pairs, as without it; the cells only small parts can fill (rims, stepped
  curves, thin posts) take the whole supply in the main pass (6378-1: 171 small-part cells, 5891-1: 266, 4956-1: 324),
  and the empty cells a used-up part would still fill number 30–509 per build on top. **The limit is the sets'
  small-part supply, not the order**; reordering cannot close it.
- **Small-part budget sizing: does not hold; remnants are packing** (`--steps small-only remnants`, merged 07e7b7b, ee).
  Cells only a small part can fill (no placement of any larger inventory part covers them inside the target) are 0 at
  every slack 1.0–0.6 on 7/9 pairs, at most 25 (0.15 × the supply) on the 6378-1 chair; none of the diagnosed
  shortfall sits on such a cell, so a budget sizing would shrink nothing. The shortfall is remnants of 1–3 cells that
  large parts at arbitrary offsets leave against each other and the boundary: 200–770 small-part cells wanted per build
  vs 171–324 held. Replaying the 18 diagnosed builds, of 3447 remnant cells 49% had no alternative at the placement
  that left them, 33% were fillable then and lost to demand elsewhere, and an alternative placement at the visited cell
  could have covered or kept fillable 17% (8–32% per build, under half on every one), so no remnant-aware score is
  built; every remnant has a width the set has a part for (1-wide 53%). Charged by pass: main 1837, connect 206, hole
  passes 1400.
- **Reserve inside connected growth** (e12b27f, 64; `--order connected --reserve-small` / `--small-last a` now allowed):
  creserve, csmall1 at 1.0 and 0.8 vs connected and the default (`results/m12b_connected.md`, dated section, merged
  after 83ad2ef). **No arm passes the rule** (creserve 4/9 vs connected, 5/9 vs the default; csmall1 1/9, 4/9), but
  creserve's selected build fills more than the default's on 9/9 pairs at both slacks (mean selected fill at 1.0:
  default 81.8, connected 84.2, creserve 87.8; largest hole 202 / 240 / 143; at 0.8: 86.3 / 90.1 / 91.4), judge −0.011
  / −0.002 vs connected, 17 vs 23 s per candidate at 0.8. Out-of-small-parts stalls 18 → 5 (the 5 left: 6378-1 table,
  83–87 parts left and none fits the leg); base-block stalls 25 → 32, not diagnosed. **First complete candidate** of
  3600: creserve80, 5891-1 chair, seed 1 (98.7 / 4 / 98.3, tips 99%, valid), `m12b_connected_complete_chair.png`,
  `out/m12b_complete/complete_candidates/chair_5891-1_creserve80_seed01.ldr`. The select stage ranked it 6th of 34
  (z(judge) + z(fill); its judge is the lowest of the top 8) and picked seed 43 (98.5 / 7 / 98.0).
**Decisions (cf, 2026-10-10, against the pre-stated rule "every pair's selected build more complete, no validity lost";
Mac can reverse):** with a 3D target the pipeline defaults are now `--holes --hang` and `--sizing usable`
(`pipeline.resolve`; `--no-holes`, `--sizing fillable` restore the old path; the earlier drivers pass them explicitly, so
their tables stay reproducible); no slack default. Merged e0933bb, 404 tests.
**For Mac (2026-10-11 morning; nothing runs until then, PC resting):** (1) the select stage: rank candidates that meet
the bar first (then judge + fill as now), which is the bar applied at selection and would have picked the complete chair;
(2) `--order connected --reserve-small` as the default with a 3D target despite failing the strict rule (fill up on 9/9
vs the default, the only arm that produced a complete build; costs: a larger largest hole or 1–3 fewer valid on 4 pairs
per slack, judge −0.01); (3) whether `--fill-slack 0.8` joins it (the complete chair is at 0.8), or a sizing by remnant
demand against the small-part supply (not built; the measured remnants are 200–770 cells per build vs 171–324 held).
Deferred until builds are complete: skin/symmetric defaults.
**cf's read, 2026-10-10 night (Mac: "ok nice"):** one complete build of 3600 is luck, not a method; the unused lever is size
below 0.8 (remnant demand is 1.5–2× the small-part supply at 0.8–1.0; a rule "largest size the set can complete"); the
every-pair adoption rule on one selected build per pair is noise-bound (weigh the mean over valid candidates too); fill
is the wrong quantity (interior cells are invisible: measure surface completeness, re-measure hollow targets on it);
looks have not moved (the complete chair is a colour mottle); nine pairs from three small sets is a narrow bench.
Proposed order, pending Mac: completeness-first selection; size sweep to 0.6 with reserve-in-growth; surface-only bar
with hollow targets; colour and symmetry; widen the bench before paper tables.
**2026-10-11 (Mac: go on the recommendation yes / yes / no slack default; two worker sessions, this one coordinates):**
- **Completeness-first selection — merged d478fd7, default.** `funnel.select(tiers=)`, `alt/features.Bar` (`--bar volume`:
  fill ≥ 97%, largest hole ≤ 4, surface ≥ 98%, the default; `--bar surface`: surface ≥ 98% and largest *surface* hole ≤ 4,
  interior cells invisible; `completeness` reports `largest_surface_hole`), `--no-complete-first` restores score order.
  Complete builds also enter dedupe first. Re-rank of the cached creserve / creserve80 runs with no generation
  (`experiments/select.py`, `results/m12c_select.md`; the old rule reproduces every stored selection, 18/18): the
  5891-1 chair creserve80 seed 1 (98.7 / 4 / 98.3) is now selected, judge −0.294 → −0.351; the only change, since it is the
  only complete candidate of 850 valid. The surface bar picks the same build on all 18 pairs (the binding threshold is the
  surface share, 78–96% on the other old picks), though the largest surface hole is smaller than the largest hole on 12/18
  (4956-1 car 345 → 38: holes are mostly interior).
- **Size sweep below 0.8 — done** (Session B, 17:01–20:18 on 5 workers, no crash; arms creserve90 / 70 / 60 and the
  usable70 / 60 controls, 50 candidates per pair; `results/m12b_size.md`, `m12b_size_sheet.png`). **Size is the
  lever, but only with the reserve inside connected growth.** creserve on the 8 uncut pairs, 1.0 → 0.9 → 0.8 → 0.7 →
  0.6: complete candidates 0 / 0 / 1 / 1 / **15** (18 under the surface bar), mean selected fill 87.6 → 97.5%, largest
  hole 149 → 16, surface 86 → 97%; the default order has 0 complete of 1881 valid at every slack (selected fill 80.9 →
  89.1). Largest completing slack per pair (any candidate): 5891-1 chair 0.8 (one candidate, none below), 6378-1 table
  0.7 (10 candidates at 0.6), 5891-1 table 0.6, 5891-1 car 0.6, 6378-1 car 0.6 surface bar only; **none down to 0.6 on
  the three 4956-1 pairs** (best 94.5–98.8% fill, holes 20–39). Under completeness-first the volume bar changes one
  stored pick (creserve60 6378-1 table → a complete build). creserve is also faster (16–27 s vs 27–43 s per
  candidate). 20 complete candidates saved under `out/m12b_complete/complete_candidates/`.
- creserve as the 3D default waits for the size sweep (decision (2) is yes in principle; the default changes with the
  size rule in one commit).
- **Hollow at the solid's scale — built, not run** (69dc76e; `--hollow-scale solid`: size the solid target as usual, then
  cut the shell at that scale, so the object keeps its size and the interior's parts are freed; `shell` is the old path).
  Sizing-only measurement on the 18 cached targets (`results/m12c_hollow_sizing.md`): hollowing at the inventory's volume
  frees no parts and keeps 82–100% of these thin objects' cells; at the solid's scale hollow 1 keeps 65–90% and frees a
  median 25% of the part budget (12–34%), hollow 2 only 8% (about what slack 0.9 frees); every void enclosed, exposed
  cells unchanged. Arms hollow1 / hollow1_80 (creserve flags + `--hollow 1 --hollow-scale solid --bar surface`) run after
  the size sweep. Risks: 1-stud walls and 1-plate roofs on 2×2 pillars; parts that fit nowhere in the shell eat most of the
  gain on the 6378-1 car; the freed budget is large parts, not the small parts the remnants need.
- **Colour coherence — measured, then the cheap fix built** (36e11bf, 7ec5522). `bricks/coherence.py` on the skin:
  same-colour share of visible part seams, colours per 4×4 window, largest one-colour region (tracks supply, not used).
  Our 18 cached selections vs the 28 real sets (`results/m12c_colour_measure.md`): worse than the own set on 18/18
  (seams median 49% vs 64–71%, 2.05 vs 1.1–1.5 colours per window) and within 1–11 points of a random within-type
  shuffle: the builder's colouring is near random. `bricks/recolor.py` + `--recolor` (**off by default**): simulated
  annealing over colour permutations within part types, applied after select (judge and selection untouched;
  placements and (part, colour) counts kept, so every guarantee holds by construction), 2–4 s per build.
  On the 18 selections + the complete chair (`results/m12c_recolour.md`, `m12c_recolour_chair.png`): seams +16 points
  median (+7 to +25), gap to the own set −22 → −7, colours per window −0.49; the 4956-1 pairs are capped (68–76% of
  their skin on one-colour part types). **Decision for Mac:** `--recolor` on by default with a 3D target (the metrics say
  yes on 18/18; the eye decides from the chair figure). Beyond this space: spare inventory as extra colours, or a
  decode-time colour term.
- **Wider bench — planned, not run** (cdf0a0d; `examples/m12c_bench.json`, `--pairs FILE` on the complete / select /
  coherence drivers, defaults keep the 9 sweep pairs; `results/m12c_bench_plan.md`): 9 sets (7796-1, 6370-1, 6372-1,
  6378-1, 7743-1, 5891-1, 4956-1, 10190-1, 10182-1; 270–9720 inventory cells) × 6 objects (chair, table, car, sofa,
  vessel, bench). Every target sizes cleanly. Time model (CPU s per candidate ∝ cells^1.93, checked on the cached
  runs): the creserve arm on the 45 new pairs is 8.4 h at 1.0, 5.5 h at 0.8; the two Modular sets are two thirds of it.
- **The 6378-1 chair stall, diagnosed and half fixed** (e5d3c48, 2df464e; `results/m12c_stall_6378_chair.md`). The
  early size-sweep arms showed creserve70 6378-1 chair with all 50 candidates at 3.5% fill, every one "valid", and
  creserve60 at 18% mean. Cause (replays with no rng draws): nearest-neighbour resampling cuts the chair's diagonal
  caster arms into separate face-connected pieces at every slack (2 pieces at 1.0–0.7, 4 at 0.6), so the growth seed
  (largest ground region) lands on an island (0.7: total stall) or the chair stands on one foot and tips (0.6: 30/50);
  the chair was never completable in any arm, and 8 of the 108 bench targets (chairs on the 4 smallest sets) are cut
  the same way. Fix by construction: `shapes.reconnect` (in `scale_and_join`, before hollowing and supports) adds the
  fewest bridging cells (+3 to +10); one-piece targets are byte-identical, only cut targets' cache keys change. After
  it the 0.7 chair stalls on 5/10 seeds instead of 50/50 (a one-cell neck is one piece but not a brick joint; the seed
  caster outranks the hub column), so the best of a run is near the bar again. `--min-fill F` (absolute fill floor at
  verify, default 0) stops an all-stall run from selecting a stub; `--regrow` (restart growth from the next ground
  region on a stall) is being built as a flag. The verify stage's relative fill floor was the hole: 0.5 × the run's
  90th-percentile fill is 1.8% when every candidate stalls.
- `--regrow` merged (044b8f6): on a stall, growth restarts from the next ground region with the same Generator;
  non-stalling builds byte-identical; 6378-1 chair at 0.7 and 6372-1 chair at 0.8 stall 5/10 → 0/10 seeds.
- **Overnight run (launched 2026-10-11 night from the main checkout, `scripts/overnight_m12c.sh 0.6 0.8`; log
  `out/m12b_complete/overnight.log`, markers `STEP_DONE` / `STEP_FAILED` / `ALL_DONE`; main's `src/` is frozen until
  it ends):** hollow1 + hollow1_80 on the 9 pairs (surface bar); the reconnected 6378-1 chair at 1.0–0.6 under
  cregrow and the usable controls (`out/m12c_reconnected`); the bench's 45 new pairs at 0.6 then 0.8 under arm
  `bench` = cregrow + `--min-fill 0.5` (`out/m12c_bench`, smallest sets first, the 9 current pairs last), with
  sweep-report, completeness-first re-rank and the colour measurement per slack. Modelled 6–10 h; resumable, rerun
  the same command.
**2026-10-12 morning (the queue ran 20:50–06:18 on 5 workers, every sweep done; cf read it, fixed three things, PC idle):**
- **The bench — run** (`results/m12c_bench.md`, sheets `m12c_bench_sheet_0.6.png` / `_0.8.png`, raw tables
  `m12c_bench_sweep_0.6.md` / `_0.8.md`). Arm `bench` = cregrow + `--min-fill 0.5`, 50 candidates per pair, 54 pairs.
  **At 0.6 the selected build is complete on 30/54 pairs** (433 complete candidates of 2612 valid; mean selected fill
  96.8%, median largest hole 4), **at 0.8 on 12/54** (108 complete; 10182-1 completes all six objects at 0.8, 7743-1
  all six at 0.6). By object at 0.6: sofa 8/9, vessel 6/9, table 5/8, bench 5/9, chair 3/8, car 3/9. By set: the
  three smallest (56–161 parts) one or two each; 7796-1's chair and table (136–160 target cells) stall on every seed
  and the fill floor leaves nothing selected (the right outcome); 4956-1 only the sofa (its other pairs sit at
  94.5–98.8% fill with 19–39-cell holes at every slack, as in the 9-pair sweep); 10190-1 misses the car and vessel.
  Per pair the largest completing slack is 0.8 on 12, 0.6 on 21, none on 21 (17 of those within 3 fill points of the
  bar, largest hole 6–24; the clear misses are the 6370-1 table, 69%, and the 7796-1 car, 82%). Valid before the fill
  floor ≥ 22/50 everywhere; stalls only on the four smallest sets. Time: 2.0 h (0.6) and 3.3 h (0.8) for the 45 new
  pairs, under the plan's model; the Modulars are 60% of it (up to 88 s per candidate).
- **A hole in the funnel, fixed by construction:** the verify stage's relative size floor (the smallest 10% of valid
  builds by contact events fail "too_small", a guard for the judge's samples) cut the complete 5891-1 chair at 0.8
  (seed 1, 98.7 / 4 / 98.3, the fewest parts of its run), so the bench reported a complete candidate that was not
  selected. A build that meets the bar is now exempt from the size and fill floors (`pipeline.run_funnel`, computed
  for every valid build before any floor; `test_a_complete_build_is_never_too_small`). Replaying the 181 cached runs (the bench's 108, the 9-pair sweep's 63, the chair's 10) with the fixed stage changes 12 stored picks: 2 incomplete → complete (the 5891-1 chair at 0.8, so the bench's 0.8 count is 13/54 with the fix, and the creserve60 6378-1 table) and 10 complete → another complete build with a higher judge (the admitted builds use fewer parts); no pick gets worse.
  The re-rank driver now prints and records (`stored_seed` / `replayed_seed`) where a run's stored pick differs from
  the replay instead of exiting.
- **Hollow at the solid's scale — measured, not adopted** (`results/m12c_hollow.md`): hollow1 / hollow1_80 worse on
  15/18 comparisons, 0 complete, and the 5891-1 and 4956-1 chairs and tables stall 50/50 (a 1-stud wall on a 1-plate
  floor cannot be grown with their parts). Stays a flag, off; the surface bar stays as a reported measure on solids.
- **The reconnected 6378-1 chair** (`m12c_stall_6378_chair.md`, dated section; `m12c_chair_6378_size.md`, sheet): no
  stalls at any slack with `--regrow`; **complete at 0.7** (one candidate, 98.8 / 3 / 98.5, selected;
  `out/m12c_reconnected/complete_candidates/`); at 0.6 the casters shrink to one cell and 22/50 tip over; the usable
  control completes nothing. Largest completing slack for the 6378-1 chair: 0.7, as for its table.
- **Colour on the bench:** same-colour seams median 41% vs 65% in the own sets vs 34% shuffled, worse than the own set
  on 50/52 selections at both slacks; same picture as the 18 earlier ones. `--recolor` not run on the bench (it applies
  after selection; can be run on the cached builds without generation).
- Driver fixes (tests in `test_driver_outputs.py`): `select --out x_0.6` and `coherence --results x_0.6` wrote `x_0.json`
  (`Path.with_suffix` took `.6` as the suffix; the 0.8 step overwrote the 0.6 step); the colour driver crashed on a run
  with no selected build (all-stall under the fill floor) and now skips it.
**Decisions for Mac (open):** (a) `--order connected --reserve-small --regrow` as the 3D default (the only order that
  completes anything; faster too; regrow is free when nothing stalls); (b) `--recolor` on by default (metrics 18/18 +
  50/52 on the bench say the colouring is near random; the chair figure is the eye test); (c) `--min-fill 0.5` as a
  verify default (on the bench it kept two all-stall runs from selecting a stub); (d) the size rule for the paper
  tables: one bench slack (0.8 completes 12/54, 0.6 completes 30/54) vs per-pair "largest slack that completes" (12 at
  0.8 + 21 at 0.6; 21 pairs at neither, the small inventories' chairs and cars and everything on 4956-1 but the sofa).
  Nothing changes until Mac decides; every overnight arm passed its flags explicitly.

### M12d — Catalog to the real sets' parts; M12e — proposal model v2 on more data (Mac, 2026-10-15)
Mac's correction (2026-10-15): the builds are complete but still look like boxes in random colours; the two things
asked for since the M12b framing, **a bigger catalog** and **a trained proposal model**, were done minimally (63 → 88
parts; a 5M-parameter model trained 1500 steps on 21 sets and closed after one comparison under a judge that sees
contact statistics only). The five days of completeness sweeps after the 2026-10-10 read were spent on a number nobody
looked at. **No more slack / reserve / hole / hollow experiments.** The completeness work is done enough for the paper.
Aim, in order: (1) the catalog knows the parts real sets are made of; (2) a model trained on hundreds of real sets
places them; (3) the result is judged by eye on rendered sheets and by surface / symmetry / colour metrics, not by the
contact judge. Open decisions from M12c (defaults for connected+reserve+regrow, recolor, min-fill, the size rule) stay
open; nothing changes there now.
- **Ranking of what the catalog cannot place** (`results/m12d_missing_parts.md`, 2026-10-15): the 28 building sets
  have 25,321 part instances, 69.5% recognized; the 7,714 missing are a long tail of 807 files. By kind: window/door
  frames and glass 1185, round 740, minifigure 685, hinge/clip/bar 650, curved slopes 476, Technic 435, jumpers 403,
  modified bricks 233, wheels 221, brackets and side-stud bricks 214, panels 159, plain plates not in the catalog
  (2×16, 4×12, 6×12, 6×16, baseplate 16×32) 115. Across all 93 local OMR models: 66,043 parts, 61.0% recognized.
- **M12d plan (session A, branch `m12d-catalog`):** add in four batches, each committed on its own, geometry read from
  the parts' `.dat` files as in M12b step 4, every new part with a placement test against those facts, M8 builds
  fingerprint-unchanged, `catalog_check.ldr` regenerated for Mac's Studio check, new parts appended after the existing
  ones (style indices). (1) Existing mechanisms: missing plain rectangles and baseplates (a baseplate has no seated
  cells: ground only); lookalike boxes (log 30136 and masonry 98283 bricks, Technic bricks 3700 / 6541 / 32064a, cones
  59900 / 4589, round and quarter tiles 98138 / 25269, round, flower and leaf plates 85861 / 33291 / 32607, rounded
  plate 35480, round-corner plate 30357, panels 6231 / 4865a / 4865b / 87552 / 2362b, seat 4079, macaroni tile 27925);
  per-cell studs (92593); slopes 3678b, 92946, 3300, 3299, alias 3665b; curved bricks as slopes or studless boxes
  (6091 with its one back stud, 50950, 61678, 11477, 15068); arches 3659 / 3455 / 6182 as bricks seated at their end
  cells only (the box stays full: conservative). (2) **Window and door frames with contained glass**: a frame is a box
  with its studs (60592, 3854, 60593, 60608, 60594, 3853, 6556, 30044, 30046, 60596 door frame, fences 30055 / 3633 /
  3185); its glass, door or shutter (60601, 60602, 60623, 57895, …) is a *contained* accessory with no cells of its own,
  placed with the frame, consumed from the inventory with it, exported with it, and counted as recognized when a frame
  covers its position in a real model. (3) **Keep-out cells**: a part may require listed neighbouring cells (relative
  offset and layer range) to stay empty; the builder blocks them once the part is placed, the hole and connect passes
  respect them, WFC leaves these parts out (documented). Door-rail plates 32028 / 4510 / 30586 (rail side), bricks with
  side studs 87087 / 47905 / 30414 and brackets 44728 / 93274 (the hanging face as keep-out; the side studs are
  recorded on the `Part` for sideways building later, unused now), brick with handle 2921. (4) Jumpers 3794a / 3794b /
  15573 / 87580 as plates with a studless top (their centre stud is off our grid; a real model's part on it is off-grid
  and already dropped by the voxelizer). Not added, and why, in the write-up: minifigure parts, Technic pins and
  axles, hinges, clips and bars, wheels and tyres, plants other than the round plates. Expected: recognized share on
  the 28 sets 69.5% → about 80–83% (the addable part of the ranking is roughly 3,000 of the 7,714 missing instances);
  report recognized and on-grid per set (`experiments/coverage.py`, 28 sets, 20 OMR sets, all 93), relearn style
  statistics (v3), write `results/m12d_catalog.md`.
- **Batch 1 merged (bb0f3b3, 580 tests):** catalog 88 → 156 parts. `ldraw.library` resolves a part's `.dat` (from the
  library's `complete.zip`, unpacked under `data/ldraw`, gitignored) into studs, extents and a per-cell map; the
  placement-test rows are generated from those facts and mutation-checked. New: `Part.ground_only` (baseplates 3857 /
  3811: no seated cells, the whole bottom bears on the table via `PlacedPart.contact_cells`), `Part.origin_plates`,
  `Part.__hash__` on (name, file) (hashing a baseplate's cells made one build take 81 s; 4.7 s now), `parts.M12B_FILES`
  for before/after. 6091 / 6005 / 92946 are studless (their stud sits a plate below the box top); 4079, 33291, 32607 and
  2339 skipped (they overhang their cells or stud at several heights). Recognized share on the 28 sets 69 → 75%, on grid
  57 → 60%. Coming in batch 2: a baseplate is placed only on an empty ground layer and nothing else goes on layer 0 with
  it, a build with a baseplate is exported 4 LDU lower (so the `.ldr` is exact and the stud joints sound), WFC leaves
  ground-only parts out; `coverage.PRIMITIVE` drops alphabetic primitives from the denominator. Ranking driver:
  `experiments/missing_parts.py`. Rule learned the hard way: full pytest runs one at a time across sessions (two at once
  plus the crawl ran the PC out of memory and killed the crawl).
- **Batch 2 merged (8a270f3; 619 tests on session A's identical tree, the coordinator's run was reaped by the low-memory
  guard):** catalog 156 → 170: 14 window and door frames and fences (60592, 60593, 2377, 4863, 2493b, 4035, 30044, 60594,
  6556, 60596, 30179, 30055, 3633, 3185; 3853 skipped: its body overhangs its box). `bricks/accessories.py`: 12 glass,
  pane and door files ride in frame slots at the closed poses real models use (inside the frame's box, tested per turn),
  `Source.accessories` by file and colour code, composites add their glass, `write_build` fits accessories after
  selection and writes them in the frame's step, coverage and the voxelizer count an accessory when a recognized frame's
  box holds its origin (Rebrickable inventories do not read accessories yet). Baseplate fix as planned: `_ground_ok`
  (empty layer 0 required, then closed), `parts.build_placements` lowers a baseplate build by 4 LDU on export,
  `Part.wfc` / `parts.wfc_inventory` keep ground-only parts out of WFC tilesets (`SupportConstraint` raises otherwise).
  A baseplate appears in 4/10 inventory-only D2 builds on 6370-1 and 6372-1 and costs ~45 s per build (fit-map reach
  32). `coverage.PRIMITIVE` drops alphabetic primitives (denominator 25,463 → 25,321; the write-up gives both).
  Recognized share on the 28 sets: M12b 70% → **79%**, on grid 57 → 63%.
- **Batch 3 merged (7251b3a, 650 tests):** catalog 170 → 179. `Part.keep_out` = (x, z, first layer, last layer) in the
  part's frame (layers from the part's bottom, negative below it), turned with the part (`Geometry.keep_out`; rails,
  brackets and the handle brick get 4 orientations). `bottomup._keep_ok`: keep-out cells must be above the ground, empty
  and nobody else's keep-out, and the part's own cells not someone's keep-out; `_put` marks `_State.blocked`; `_fit_key`
  carries keep-outs; `extract_parts` reports violations (verify catches them); `symmetry.mirror_shape` reflects them;
  `Part.wfc` False. Parts: door rails 32028 / 4510 (front row, own layer), 30586 (rail beyond its studless second row,
  +4 LDU), side-stud bricks 87087 / 47905 / 30414 (facing cells, layers 1–2; `Part.side_studs` recorded, unused),
  brackets 44728 / 93274 (hanging face: front row, layers −4..0), handle brick 2921. Recognized 79 → **81%**, on grid
  63 → 64%. Baseplate cost measured: 43 vs 25 s and 53 vs 28 s per build with vs without (1.8–1.9×; the rest of the
  earlier 45 s is the 32×32 grid). - **Batch 4 merged (b0238e3, 653 tests):** jumpers 3794a / 3794b / 15573 / 87580 as studless plates (their centre stud
  is off our grid). **Catalog 183 parts; recognized share on the 28 sets 69.5% → 83%, on grid 57 → 65%.** - **Closing work merged (1e2b01d, 655 tests): `results/m12d_catalog.md`.** 28 sets: recognized 69.5 → 82.8%, on grid
  56.9 → 65.3% (`m12d_coverage_m10.json`); 20 OMR sets: 57.1 → 68.1%, on grid 24.7 → 27.5% (`m12d_coverage_omr20.json`);
  the all-crawled-models table follows the crawl. Style statistics **v3** (`m10_style_stats/style_fold*_v3.json`, tagged
  m12d, 16,299 parts; new parts carry 11.6% of the mass) are the pipeline default (`alt.inputs.STYLE_VERSION`);
  `--style-version v2 --catalog m12b` reproduces M12b/M12c (checked: `--learn-only v2 --catalog m12b` gives the v2
  files exactly); `experiments/proposal.py` pinned to v2. Open points there: more round parts and 3853 need geometry
  beyond boxes; accessories are not read from Rebrickable inventories; side studs recorded, unused. **For Mac: open
  `out/check/catalog_check_m12d.ldr` in Studio** (copied from the worktree; or regenerate with
  `python -m brickwfc.bricks.catalog_check`): 183 parts in all orientations, frames with glass in every slot, keep-out
  parts in four turns with their rail / stud / face / handle pointing into the kept-empty gap, markers flush on studs.
- **M12e plan (session B, branch `m12e-data`):** (1) crawl the whole OMR index into `data/omr` (resumable, polite),
  measure every model with the coverage driver (recognized, on-grid) and define the training pool (building sets by
  the `experiments/sets.py` criteria, loosened to size, no re-releases); report sets / parts / on-grid parts; redo the
  measurement once M12d lands. (2) The token export for the pool with the vocabulary built from `parts.CATALOG` at
  export time (`experiments/export_tokens.py`), BrickGPT's splits kept in the mix, held-out sets chosen by Mac's demo
  sets. (3) A Colab notebook plus a checklist (clone, `pip install -e`, Drive-mounted `data/` and checkpoints,
  resumable training with `training/train.py`, periodic checkpoints), a smoke configuration that runs in minutes, and
  the scaled configurations (about 25M parameters, trained to convergence with early stopping on held-out loss).
  Evaluation plan in `results/m12e_training_plan.md`: held-out loss, then builds judged by surface cleanliness, mirror
  share, colour coherence and rendered sheets, with the contact judge reported but not deciding. **Training itself
  waits for the M12d catalog** (the vocabulary changes); Mac runs the notebook on Colab Pro.
- **M12d follow-up merged (84f6d89, 681 tests); M12d complete.** All 1,821 crawled models: recognized 35.0% (M8) /
  39.3% (M12b) / **49.8%** now, on grid 20.7 / 23.2 / **29.2%**; median per model 44.3 → 53.6%; models ≥ 50% recognized
  704 → 1,025, ≥ 80% 87 → 197 (`m12d_coverage_all.json`, `coverage --all`). New parts are placed at their inventory
  share in inventory-only builds (10 seeds × 3 sets); only baseplates larger than the grid go unused. **Parts that fit
  nowhere in the build space are left out of the tileset before building** (`alt.pipeline.buildable`, via
  `inventory.unusable`; utilization still against the full inventory; the cache key records the dropped names):
  4956-1 77 → 14 s and 5891-1 51 → 12 s per build; builds change where a part is dropped (fingerprints in the write-up),
  so M12b/M12c candidates rebuild exactly only with `--catalog m12b --style-version v2 --keep-unfittable` or at d15e46b
  (dated note in `docs/reproduce.md`, pointers on 16 sections).
- **M12e (1) merged (9e5f70b): the OMR crawl and the training pool** (`results/m12e_omr_pool.md`). `ldraw/omr_crawl.py`
  (index at library.ldraw.org/omr/sets?page=N; 1470 sets, 1833 distinct models = 1470 main + 363 official alternates;
  1821 on disk in `data/omr`, 12 answer 404, `crawl_failures.txt`; one request at a time, atomic writes, resumable; the
  full pass took 174 min). `experiments/omr_pool.py` measures every model at the current catalog (cached per catalog
  fingerprint, 31 s): all 1821 models 692,047 part instances, 49.8% recognized, 29.2% on grid; most-missed are Technic
  pins and hoses. **Pool: 582 models from 457 sets** (435 main + 147 alternates, alternates kept as their own sequences
  and marked `alternate_of` so a held-out set holds out its alternates): ≥ 50% recognized, ≥ 50% of recognized on grid,
  ≥ 20 on-grid parts, no re-releases, flat mosaics dropped (≤ 9 plates tall over ≥ 1024 square studs: the 9 Art sets,
  which would have been 22% of the on-grid parts); 228,479 instances, 72.9% recognized, 121,521 on grid (53.2%),
  27 / 94 / 448 on-grid parts per model at the 10th / 50th / 90th percentile. Off-grid split in the pool: tilted 13.7%
  of instances, off the stud grid 5.3%, overlapping 0.6%: **tilted is 2.6× the jumper kind, so sideways building is the
  next catalog step**, not half-stud offsets. Both demo sets are in the pool.
- **M12e (2) merged (3f73bed): token export for the pool** (`export_tokens --pool`, `data/tokens_v2`, gitignored).
  Vocabulary from `parts.CATALOG` at export time: 835 tokens (421 shapes, 78 colours). Train = BrickGPT 42,604
  sequences (4.58M parts) + 432 sets × 8 symmetries = 4,408 sequences (911k parts; real sets are 16.6% of training
  parts, the notebook's default `--set-share`); val = BrickGPT test (4,785); setval = 23 sets (seeded 5%); heldout =
  6378-1 and 31048-1 with its two alternates. 14 oversized models are cropped to 64×64×192 blocks, parts across a block
  edge dropped (251 parts). **Of the pool's 228,479 part instances 52.7% are encoded**, 27.1% have no catalog part,
  19.7% are recognized but off grid, 0.3% ride in frames; per model the median not-encoded share is 48.9% (6378-1:
  167 of 348 parts encoded). So the model learns from about half of each real set; state that next to any "learned
  from real sets" claim. - **M12e (3) merged (55c2ef0, 679 tests): Colab and the plan.** `training/colab_v2.ipynb` (clone via a `GITHUB_TOKEN`
  Colab secret, Colab's CUDA torch, tokens copied from `MyDrive/brick-wfc/tokens_v2` with a catalog-fingerprint check
  against the checkout, resumable run folder on Drive, parity check, loss table; configs smoke 0.65M / base 5.25M /
  scaled 26.2M params (d512 / 8 layers / 8 heads), early stopping patience 5). `training/train.py`: `setval.npz` is the
  real-set validation, selection = mean(BrickGPT val, setval), demo sets reported only; `--patience` kept across
  resumes; atomic checkpoints; prefetched batches (same batches as before). `results/m12e_training_plan.md`: checklist,
  configs, evaluation with the adoption rule stated before any numbers. **For Mac:** upload `data/tokens_v2` (6 files,
  ~16 MB) to Drive as `MyDrive/brick-wfc/tokens_v2`, add the `GITHUB_TOKEN` secret, push main (the notebook clones
  `BRANCH=main`; the catalog fingerprint must be 475df2114737), run the smoke config first.
- Coordinator (this session): merges on main, full pytest per merge, CLAUDE.md; no experiments on the PC.

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
