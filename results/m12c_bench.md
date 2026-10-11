# M12c — the wider bench: 9 sets × 6 objects at 60% and 80% of the fillable volume

Overnight run of 2026-10-11/12 (`scripts/overnight_m12c.sh 0.6 0.8`, main 06e484c, 5 workers, 9.5 h wall for the whole
queue; log `out/m12b_complete/overnight.log`). This write-up covers the bench; the hollow arms are in
`m12c_hollow.md` and the reconnected 6378-1 chair in `m12c_stall_6378_chair.md` (dated section).

**Setup.** The 54 pairs of `m12c_bench_plan.md`: sets 7796-1, 6370-1, 6372-1, 6378-1, 7743-1, 5891-1, 4956-1, 10190-1,
10182-1 (270–9720 inventory cells) × objects chair, table, car, sofa, vessel, bench (BrickGPT structures). One arm per
slack, `bench60` / `bench80` = `--order connected --reserve-small --holes --hang --sizing usable --regrow --min-fill 0.5
--fill-slack s`, 50 candidates per pair, completeness-first selection under the volume bar (fill ≥ 97%, largest hole ≤ 4
cells, surface ≥ 98%). Raw tables: `m12c_bench_sweep_0.6.md` / `_0.8.md` (+ `.json`); sheets of the selected builds:
`m12c_bench_sheet_0.6.png`, `m12c_bench_sheet_0.8.png`.

## Result

| slack | pairs whose selected build is complete | pairs with any complete candidate | complete candidates (of valid, of 2700) | mean selected fill | median largest hole (sel) | mean selected surface | median s / candidate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.6 | **30 / 54** | 30 / 54 | 433 of 2612 | 96.8% | 4 | 96.4% | 5.6 (max 48) |
| 0.8 | **12 / 54** | 13 / 54 | 108 of 2596 | 93.9% | 16.5 | 92.3% | 10.4 (max 88) |

Completeness-first selection picks a complete build on every pair that has one at 0.6 and on 12 of the 13 at 0.8. The
exception is the 5891-1 chair: its one complete candidate (seed 1, 98.7% fill, largest hole 4, surface 98.3%, the same
build as the complete chair of the earlier sweep) passed every check and was then cut by the verify stage's **relative
size floor** (the smallest 10% of valid builds by contact events fail as "too small", a guard so one tiny build cannot
shrink every judge sample; the complete chair uses the fewest parts of its run, 292 vs a median of 306). Fixed this
morning by construction: a build that meets the bar is exempt from the size and fill floors
(`pipeline.run_funnel`, test `test_a_complete_build_is_never_too_small`); the replay of every cached run with the fixed
stage is in the dated section below.

Largest slack with a complete **selected** build, per pair (0.8 / 0.6 / none):

| set (inventory cells) | chair | table | car | sofa | vessel | bench |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| 7796-1 (270) | stall | stall | – | 0.8 | 0.8 | – |
| 6370-1 (684) | – | – | – | 0.8 | 0.6 | – |
| 6372-1 (1038) | – | – | – | 0.8 | 0.6 | 0.8 |
| 6378-1 (1364) | – | 0.6 | – | 0.6 | 0.8 | 0.6 |
| 7743-1 (1883) | 0.6 | 0.6 | 0.6 | 0.6 | 0.6 | 0.6 |
| 5891-1 (2849) | – | 0.6 | 0.6 | 0.6 | 0.6 | 0.6 |
| 4956-1 (4418) | – | – | – | 0.6 | – | – |
| 10190-1 (7596) | 0.6 | 0.6 | – | 0.6 | – | 0.6 |
| 10182-1 (9720) | 0.8 | 0.8 | 0.8 | 0.8 | 0.8 | 0.8 |

12 pairs complete at 0.8, 21 more at 0.6, 21 at neither (2 of them because every candidate stalls).

**By set.** Completeness tracks the set's size and its parts mix, not its size alone: 10182-1 (the largest, 9720 cells)
completes all six objects at 0.8 and 7743-1 (1883 cells) all six at 0.6, while 4956-1 (4418 cells) completes only the
sofa and 10190-1 (7596 cells) misses the car and the vessel. 4956-1 is the Creator house with the 1-wide-brick-heavy
inventory already known from M12 (connectivity costs there); on it the selected builds sit just under the bar (fill
94.5–98.8%, largest hole 19–39) at every slack, as in the 9-pair size sweep. The three smallest sets (56–161 parts)
complete only a sofa or a vessel; 7796-1's chair and table (136–160 target cells) stall on every seed at both slacks: the
56-part inventory has no small parts to climb a 2-cell post, so each candidate fails the 50% fill floor (`low_fill` 46,
`too_small` 4) and nothing is selected. That floor did its job: the earlier sweep would have selected a 3% stub as
"valid".

**By object (selected complete at 0.6).** sofa 8/9, vessel 6/9, table 5/8, bench 5/9, chair 3/8, car 3/9. Blocky
objects with a flat top complete; chairs (thin post, overhanging seat and back) and cars (undersides, wheel arches)
stay the hard ones. At 0.8 every object completes only on 10182-1 plus a few small-set sofas and vessels.

**How far the incomplete pairs are at 0.6** (selected build): 17 of the 22 are within 3 fill points of the bar with a
largest hole of 6–24 cells (chairs 6378-1 95.3 / 10, 5891-1 99.2 / 6, 4956-1 95.3 / 20; cars 6378-1 96.3 / 20, 10190-1
96.4 / 85; 4956-1 table 98.8 / 24, vessel 97.9 / 19, bench 98.5 / 20). The clear misses are the 6370-1 table (69.0%,
hole 123: the 128-part set cannot fill a 520-cell table's top) and the 7796-1 car (82.1%).

**Validity and stalls.** Valid before the fill floor: median 50/50, minimum 23 (6372-1 chair at 0.6) and 22 (6370-1
chair at 0.8); runs with any stalled candidate 8 of 54 at 0.6 and 5 at 0.8, all on the four smallest sets and almost all
chairs. The report's "valid" column counts the generator's own checks (integrity, inventory, support, physics, one
piece); the fill floors are applied at verify, so an all-stall run shows 50 valid and no selection.

**Time.** Measured against the plan's model (CPU s per candidate = 4.56e-6 × cells^1.93): the 45 new pairs took 2.0 h at
0.6 and 3.3 h at 0.8 on 5 workers (the model said 5.5 h at 0.8 — the connected order with the reserve is faster than the
runs the model was fitted on). The two Modular sets are 60% of the time (10182-1 chair at 0.8: 68 s per candidate,
10190-1 chair 88 s). The nine earlier pairs took 30 min at 0.6 and 42 min at 0.8.

## What it says for the size rule (decision (d))

- One bench slack of 0.8 completes 12 of 54 pairs; 0.6 completes 30. A per-pair rule "largest slack that completes"
  gives 33 complete pairs over the two slacks and keeps the 12 at their larger size; every pair that completes at 0.8
  also completes at 0.6 except three small-set sofas/vessels and the 6378-1 vessel (noise of one selected build).
- 21 pairs complete at neither: the 50 candidates at 0.6 sit mostly within a few fill points and a 6–24-cell hole of
  the bar. Sizes below 0.6 are untested on the bench; the 9-pair sweep found nothing below 0.6 for 4956-1 either, so
  the lever for those pairs is not size alone.
- The two Modular sets complete chairs and tables at 0.6–0.8 where the 9-pair bench had suggested chairs are hard:
  chairs are hard for small inventories, not in general.

## Two driver bugs found by the queue, fixed this morning

- The select and colour drivers wrote `select_0.json` / `coherence_0.json` for `--out out/.../select_0.6`: `Path.with_suffix`
  took `.6` as the suffix, so the 0.8 outputs overwrote the 0.6 ones. Fixed (`select.output_path`,
  `coherence.results_path`, tests in `test_driver_outputs.py`) and both steps rerun from the cached runs.
- The colour driver crashed on a run with no selected build (the all-stall 7796-1 chair and table); it now skips such a
  run and says so.

## 2026-10-12: the verify-stage fix, replayed on every cached run

With a build that meets the bar exempt from the size and fill floors, the select driver replayed the 181 cached runs
(this bench's 108, the 9-pair sweep's 63 across creserve / creserve80 / the size arms and controls, the reconnected
chair's 10; `out/m12c_refloor/*.json`, `stored_seed` vs `replayed_seed`). **12 stored picks change, none for the
worse:**

| runs | picks changed | incomplete → complete | complete → another complete (higher judge) |
|---|---:|---:|---:|
| bench 0.6 (54) | 8 | 0 | 8 |
| bench 0.8 (54) | 3 | 1 (5891-1 chair: 96.6 / 15 / 95.9 → **98.7 / 4 / 98.3**) | 2 |
| 9-pair sweep, creserve + creserve80 (18) | 0 | 0 | 0 |
| size arms + controls (45) | 1 | 1 (creserve60 6378-1 table: 97.9 / 8 → 99.0 / 4) | 0 |
| reconnected chair (10) | 0 | 0 | 0 |

The ten complete → complete changes are builds the floor had cut (fewer parts, so fewer contact events) that outrank the
stored pick on the judge once admitted (judge +0.01 to +0.06; fill and holes within 1 point / 3 cells). With the fix the
bench's 0.8 count is **13 of 54** (12 as run); the 0.6 count stays 30. The tables and sheets above are as run.

## Colour on the bench

`experiments/coherence.py` on the 52 selected builds per slack (the two all-stall runs have none), against each build's
own set and a random within-type shuffle (`out/m12c_bench/coherence_0.6.json` / `_0.8.json`):

| slack | same-colour seams, median: ours / own set / shuffled | worse than the own set | within 11 points of the shuffle | colours per 4×4 window: ours / own / shuffled |
|---:|---|---:|---:|---|
| 0.6 | 41% / 65% / 34% | 50 / 52 | 39 / 52 | 2.34 / 1.35 / 2.50 |
| 0.8 | 42% / 65% / 36% | 50 / 52 | 38 / 52 | 2.33 / 1.35 / 2.44 |

The same picture as on the 18 earlier selections (`m12c_colour_measure.md`): the builder's colouring is near random on
every set, and the gap to the own set is largest on the Town sets and the Modulars (−24 to −43 points) and smallest on
7796-1 and 7743-1 (−0 to −9: few colours in the inventory). The recolouring pass (`--recolor`, decision (b)) was not
run on the bench; it applies after selection and changes no placement, so it can be run on these 104 builds without
generation if Mac wants the bench's colour numbers with it.

## Reproduce

```
bash scripts/overnight_m12c.sh 0.6 0.8                        # the whole queue, resumable
python -m brickwfc.experiments.complete --out out/m12c_bench --steps sweep-report --arms bench60 --pairs examples/m12c_bench.json --report-name sweep_bench_0.6
python -m brickwfc.experiments.select --sweep out/m12c_bench --arms bench60 --pairs examples/m12c_bench.json --out out/m12c_bench/select_0.6
python -m brickwfc.experiments.coherence --sweep out/m12c_bench --arms bench60 --pairs examples/m12c_bench.json --results out/m12c_bench/coherence_0.6
```
