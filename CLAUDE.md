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
**Status (2026-10-10, 09:00):** causes measured, four fixes merged, defaults changed; no build meets the bar yet (best
93% fill). Everything below is in `results/m12b_complete.md` (+ `_trace/_sweep/_holes/_old_vs_base.json`, sheets).
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
**Decisions (cf, 2026-10-10, against the pre-stated rule "every pair's selected build more complete, no validity lost";
Mac can reverse):** with a 3D target the pipeline defaults are now `--holes --hang` and `--sizing usable`
(`pipeline.resolve`; `--no-holes`, `--sizing fillable` restore the old path; the earlier drivers pass them explicitly, so
their tables stay reproducible); no slack default. Merged e0933bb, 404 tests.
**Next:** keep small plates for the hole pass (`--reserve-small`: parts of ≤ 3 cells tried last at every cell, so a thin
post still gets them; `--small-last a`: their choice weight × (cells/4)^a; ee, 6 arms × 9 pairs at the defaults and at
slack 0.8), then the same inside connected growth (64). Deferred until builds are complete: skin/symmetric defaults.

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
