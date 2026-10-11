# M12c: completeness-first selection (re-rank of cached candidates)

**Question.** If the select stage ranks the builds that meet the completeness bar before the rest, which build does
each sweep pair select, and does the 5891-1 chair's complete candidate (creserve80, seed 1) get selected?

**Answer.** Yes: the new rule selects seed 1 on the 5891-1 chair at creserve80. It is the only pair of the 18 whose
selection changes, because it is the only pair with a complete candidate. Of the 850 valid candidates, it is the only
complete one under either bar. The surface bar selects exactly what the volume bar selects on all 18 pairs.

## What changed (code)

- **Bar** (`alt/features.py`: `Bar`, `completeness`). The thresholds are `AltConfig.complete_fill` (0.97),
  `complete_hole` (4) and `complete_surface` (0.98).
  - `--bar volume` (default): fill ≥ 97%, largest hole ≤ 4 cells, surface ≥ 98%. This is cf's working bar.
  - `--bar surface`: surface ≥ 98% and largest surface hole ≤ 4 cells. Fill and interior holes do not count.
- **Largest surface hole.** `completeness` now also reports `largest_surface_hole`. It is the largest face-connected
  component of the empty exposed cells, labelled on their own. Two empty surface cells joined only through an empty
  interior cell are two surface holes.
- **Selection** (`alt/pipeline.py: run_funnel`, `funnel/select.py: select(tiers=)`). With a target and
  `complete_first=True` (the default), the builds that meet the bar are picked before the rest.
  - The score is unchanged: z(judge) + fill_weight × z(fill), standardized over all unique builds. Within the complete
    group and within the rest, the order is that score.
  - The diversity bonus still counts, against every pick so far, across both groups.
  - Complete builds also go first into dedupe, so a complete build is kept over an incomplete near-duplicate. This
    changed no unique count here.
  - `--no-complete-first` restores the old order.
- **Outputs.** The pipeline prints the rule, the bar and how many unique builds meet it. Each selected row in
  `stats.json` gains `complete` and `largest_surface_hole`, and the file gains `complete_unique`.

## Method

`python -m brickwfc.experiments.select` reads the cached candidates of the creserve and creserve80 arms
(`out/m12b_complete/sweep/<arm>/<set>/<object>/`, 9 pairs each, 50 candidates per run) and generates nothing.
- **Funnel.** It reruns the pipeline's own funnel (`run_funnel`) with each run's config (k = 1), under three rules:
  old (score only), new with the volume bar, and new with the surface bar.
- **Context.** The target mask and grid come from the cache key. The colors and style come from the set; the key's
  style label and inventory are checked.
- **Check.** The old rule reproduces the selected seed in every run's `stats.json` (18/18). The driver stops if not.

## Result

Selected build per pair: fill % / largest hole / surface % / largest surface hole. Unique: builds after verify and
dedupe. Complete: unique builds that meet the volume / surface bar. The surface bar's selection is the volume bar's on
every pair, so it has no column of its own (`m12c_select.json` has it).

| arm | object | set | unique | complete (vol / surf) | old: seed | fill / hole / surface / surf. hole | judge | new: seed | fill / hole / surface / surf. hole | judge | complete |
|---|---|---|---:|---:|---:|---|---:|---:|---|---:|---|
| creserve | chair | 6378-1 | 45 | 0 / 0 | 45 | 88.9 / 96 / 87.0 / 96 | −0.291 | 45 | same | same | no |
| creserve | chair | 5891-1 | 45 | 0 / 0 | 46 | 93.6 / 18 / 92.8 / 13 | −0.322 | 46 | same | same | no |
| creserve | chair | 4956-1 | 43 | 0 / 0 | 14 | 86.6 / 244 / 82.1 / 228 | −0.255 | 14 | same | same | no |
| creserve | table | 6378-1 | 43 | 0 / 0 | 43 | 81.4 / 119 / 84.5 / 23 | −0.323 | 43 | same | same | no |
| creserve | table | 5891-1 | 43 | 0 / 0 | 19 | 91.9 / 15 / 90.7 / 15 | −0.334 | 19 | same | same | no |
| creserve | table | 4956-1 | 34 | 0 / 0 | 28 | 84.1 / 307 / 78.3 / 254 | −0.273 | 28 | same | same | no |
| creserve | car | 6378-1 | 46 | 0 / 0 | 46 | 87.4 / 92 / 86.5 / 56 | −0.347 | 46 | same | same | no |
| creserve | car | 5891-1 | 45 | 0 / 0 | 42 | 92.5 / 53 / 93.1 / 14 | −0.328 | 42 | same | same | no |
| creserve | car | 4956-1 | 42 | 0 / 0 | 17 | 83.4 / 345 / 83.1 / 38 | −0.259 | 17 | same | same | no |
| creserve80 | chair | 6378-1 | 45 | 0 / 0 | 25 | 94.5 / 35 / 93.4 / 35 | −0.308 | 25 | same | same | no |
| **creserve80** | **chair** | **5891-1** | 34 | **1 / 1** | 43 | 98.5 / 7 / 98.0 / 7 | −0.294 | **1** | **98.7 / 4 / 98.3 / 4** | −0.351 | **yes** |
| creserve80 | chair | 4956-1 | 38 | 0 / 0 | 49 | 89.9 / 80 / 87.6 / 77 | −0.233 | 49 | same | same | no |
| creserve80 | table | 6378-1 | 46 | 0 / 0 | 37 | 86.5 / 76 / 82.7 / 76 | −0.298 | 37 | same | same | no |
| creserve80 | table | 5891-1 | 42 | 0 / 0 | 1 | 96.0 / 9 / 95.9 / 9 | −0.347 | 1 | same | same | no |
| creserve80 | table | 4956-1 | 35 | 0 / 0 | 30 | 86.4 / 390 / 80.1 / 312 | −0.253 | 30 | same | same | no |
| creserve80 | car | 6378-1 | 46 | 0 / 0 | 11 | 87.6 / 75 / 87.5 / 28 | −0.304 | 11 | same | same | no |
| creserve80 | car | 5891-1 | 46 | 0 / 0 | 29 | 92.3 / 31 / 91.0 / 15 | −0.326 | 29 | same | same | no |
| creserve80 | car | 4956-1 | 44 | 0 / 0 | 19 | 91.1 / 59 / 90.7 / 26 | −0.253 | 19 | same | same | no |

## Reading

- **The rule does what it says.** It moves the one complete build to the top, at a judge cost of 0.057 (−0.294 →
  −0.351). On the other 17 pairs nothing is complete, so the old and new selections are identical by construction.
  The rule does not make builds more complete; only the generator can.
- **The surface bar is not looser here.** Its binding threshold is the surface share. Every old selection except the
  creserve80 5891-1 chair's is at 78–96% surface, under 98%. That chair's old pick, seed 43, is at 98.0% but fails on
  its 7-cell surface hole. The largest surface hole is smaller than the largest hole on 12 of the 18 old selections
  (the cars most: 4956-1 creserve 345 → 38), so some holes are mostly interior. But where the surface share is under
  98%, the bar fails on it either way.
- **No ranking inside "incomplete" by distance to the bar.** The rest are ranked by judge + fill as before. A ranking by
  how close a build is to the bar (for example surface first) was not asked for and is not built.

## Reproduce

See `docs/reproduce.md` (§ `results/m12c_select.md`).
