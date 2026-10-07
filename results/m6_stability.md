# M6 — stability-aware WFC vs post-filtering vs a bottom-up baseline

Reproduce (about 16 minutes on the machine below; resumable):

```
python -m brickwfc.experiments.stability --seeds 1000 --sizes 4x4x2 4x4x3 8x8x6 --out out/m6
```

Raw data: `m6_stability_summary.json` (this folder); per-run records are written to `out/m6/runs.jsonl`.

## Setup

- Parts: plates 1×1, 1×2, 2×2, 2×4 (both orientations), colors red and blue, default weights
  (each part type covers a similar share of cells; empty weight 1.0). Grid sizes are width × depth ×
  height in studs × studs × plates.
- Seeds 0–999 for every condition and size; each run allows up to 100 WFC attempts.
- Ground truth (`support.is_stable`): every part sits on layer 0 or overlaps ≥ 1 stud with a solid cell
  directly below. This implies every part connects down to the ground. It is **not** a physics check
  (see M7).
- Machine: Intel Core (family 6 model 141), 12 threads, Python 3.12.4, single process.

Conditions:

| | generator | how stability is handled |
|---|---|---|
| A_plain | WFC | not at all during generation; unstable builds are filtered afterwards |
| B_aware | WFC + `SupportConstraint` | part-level support pruned/forced inside propagation |
| C_per_cell | WFC | M4's local rule: every stud needs a solid cell below (no overhangs possible) |
| D_bottom_up | random bottom-up placement, no WFC | a part is placed only where it rests on something |

## Results (1000 seeds each)

| size (WxDxH) | condition | seeds | stable % | restarts/run | time/run (s) | time/stable (s) | parts/design | overhangs/design | fill % | broken parts |
|---|---|---|---|---|---|---|---|---|---|---|
| 4x4x2 | A_plain | 1000 | 19.6 | 0.00 | 0.011 | 0.055 | 14.3 | 2.7 | 69.7 | 0 |
| 4x4x2 | B_aware | 1000 | 100.0 | 0.00 | 0.023 | 0.023 | 14.9 | 1.4 | 73.2 | 0 |
| 4x4x2 | C_per_cell | 1000 | 100.0 | 0.00 | 0.011 | 0.011 | 15.8 | 0.0 | 73.8 | 0 |
| 4x4x2 | D_bottom_up | 1000 | 100.0 | 0.00 | 0.002 | 0.002 | 18.4 | 1.1 | 86.8 | 0 |
| 4x4x3 | A_plain | 1000 | 3.9 | 0.00 | 0.016 | 0.420 | 21.5 | 5.6 | 69.7 | 0 |
| 4x4x3 | B_aware | 1000 | 100.0 | 0.00 | 0.044 | 0.044 | 22.0 | 3.1 | 73.8 | 0 |
| 4x4x3 | C_per_cell | 1000 | 100.0 | 0.00 | 0.017 | 0.017 | 24.4 | 0.0 | 75.5 | 0 |
| 4x4x3 | D_bottom_up | 1000 | 100.0 | 0.00 | 0.003 | 0.003 | 27.1 | 2.3 | 86.3 | 0 |
| 8x8x6 | A_plain | 1000 | 0.0 | 0.00 | 0.183 | inf | 161.9 | 49.3 | 73.3 | 0 |
| 8x8x6 | B_aware | 1000 | 100.0 | 0.01 | 0.533 | 0.533 | 161.8 | 32.6 | 76.6 | 0 |
| 8x8x6 | C_per_cell | 1000 | 100.0 | 0.00 | 0.187 | 0.187 | 201.6 | 0.0 | 85.6 | 0 |
| 8x8x6 | D_bottom_up | 1000 | 100.0 | 0.00 | 0.020 | 0.020 | 199.3 | 23.4 | 87.8 | 0 |

"Overhangs" are parts above layer 0 with at least one stud over empty space (still supported elsewhere).

## Findings

1. **Post-filtering does not scale.** Plain WFC's stable rate falls from 19.6% (4×4×2) to 3.9% (4×4×3)
   to 0 of 1000 (8×8×6): with ~160 parts, some part almost always floats. Filtering afterwards can't
   produce stable builds at realistic sizes.
2. **Stability-aware propagation fixes this completely.** B is stable in 100% of runs at every size,
   needed restarts in only 0.01 runs on average at 8×8×6 (the forcing step avoids most dead ends), and
   costs ~2.9× plain WFC per run (0.53 s vs 0.18 s at 8×8×6).
3. **It keeps overhangs, unlike the local rule.** C is also 100% stable and as fast as A, but can never
   overhang. B keeps 20% of parts overhanging (32.6 of 161.8) vs 30% in unfiltered A.
4. **But a bottom-up baseline is just as stable and 27× faster.** D places parts only where they rest on
   something, so it is stable by construction too, at 0.020 s per 8×8×6 build. It also overhangs
   (12% of parts) and fills more of the grid (88% vs 77%). **On the support rule alone, WFC is not
   justified.** Its possible advantages — learned style, and look-ahead under combined inventory and
   shape constraints — are untested here; that is the decision checkpoint after M9 + M11 (see `CLAUDE.md`).

## Caveats

- "Stable" is the ≥1-stud support rule, not physical equilibrium; long cantilevers can pass it. M7 adds a
  physics-based verifier and will re-score every condition.
- Fill differs between conditions (D and C are denser), so per-design counts are not directly comparable;
  ratios (overhangs per part) are fairer.
- Timings are single-run wall clock on one machine; relative speeds matter more than absolute ones.
