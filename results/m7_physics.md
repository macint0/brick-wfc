# M7 — physics-based stability for the M6 conditions

Reproduce (about 20 minutes; resumable):

```
python -m brickwfc.experiments.stability --seeds 1000 --sizes 4x4x2 4x4x3 8x8x6 --out out/m7
```

Raw data: `m7_physics_summary.json` (this folder). Same setup, seeds and conditions as
`m6_stability.md` (A plain WFC + filter, B stability-aware WFC, C per-cell rule, D random bottom-up).

## Physics model (`bricks/physics.py`)

Vertical forces only, rigid parts, solved as a linear program (`scipy.optimize.linprog`, HiGHS):

- each part weighs one unit per cell it covers, acting at the centre of its footprint;
- where a part rests on a part below or on the ground, **compression** can act anywhere on the shared
  cell (4 push-only forces at its corners), and stud **clutch** can pull the parts together (4 pull-only
  forces on the stud ring, radius 0.3 stud pitches);
- every part must have zero net force and zero net torque about both horizontal axes.

The result per build is the **required clutch per stud**, in plate-cell weights: the smallest grip for
which the build stands. 0 = it stands with no grip at all (pure stacking); inf = no grip helps. Builds
stand **on a table** (the ground pushes but cannot pull) unless stated otherwise. Not modelled:
horizontal/shear forces, friction, part flex, clutch differences between part types.

We report three thresholds rather than one calibrated value: real clutch is large compared with a plate's
weight, but joints also fail by rotating, which this model only approximates, so the useful signal is how
much grip each generator's builds *depend on*.

## Results (1000 seeds each)

| size (WxDxH) | condition | simple rule stable % | phys. stable %, no clutch | phys. stable %, clutch ≤10 | phys. stable %, any clutch | median clutch | time/run (s) | overhangs/design | fill % |
|---|---|---|---|---|---|---|---|---|---|
| 4x4x2 | A_plain | 19.6 | 19.5 | 19.5 | 19.5 | inf | 0.011 | 2.7 | 69.7 |
| 4x4x2 | B_aware | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 0.023 | 1.4 | 73.2 |
| 4x4x2 | C_per_cell | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 0.010 | 0.0 | 73.8 |
| 4x4x2 | D_bottom_up | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 0.002 | 1.1 | 86.8 |
| 4x4x3 | A_plain | 3.9 | 3.7 | 6.4 | 6.4 | inf | 0.016 | 5.6 | 69.7 |
| 4x4x3 | B_aware | 100.0 | 76.3 | 94.5 | 94.6 | 0.0 | 0.044 | 3.1 | 73.8 |
| 4x4x3 | C_per_cell | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 0.017 | 0.0 | 75.5 |
| 4x4x3 | D_bottom_up | 100.0 | 91.8 | 98.4 | 98.4 | 0.0 | 0.003 | 2.3 | 86.3 |
| 8x8x6 | A_plain | 0.0 | 0.0 | 0.0 | 0.0 | inf | 0.183 | 49.3 | 73.3 |
| 8x8x6 | B_aware | 100.0 | 2.9 | 82.5 | 85.6 | 2.0 | 0.519 | 32.6 | 76.6 |
| 8x8x6 | C_per_cell | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 0.194 | 0.0 | 85.6 |
| 8x8x6 | D_bottom_up | 100.0 | 27.1 | 92.4 | 93.2 | 1.0 | 0.019 | 23.4 | 87.8 |

Full table with restarts, part counts and broken-part counts: `out/m7/results.md` after reproducing.

### Table vs baseplate (8x8x6, seeds 0–199)

| condition | table: stands with some clutch | table: clutch ≤10 | baseplate: stands with some clutch | baseplate: clutch ≤10 | baseplate: 95th pct clutch |
|---|---|---|---|---|---|
| B_aware | 87.5% | 83.5% | 100% | 94.0% | 12.6 |
| D_bottom_up | 94.5% | 92.0% | 100% | 97.0% | 7.0 |

## Findings

1. **The ≥1-stud rule overstates stability.** At 8×8×6 it accepts 100% of B and D builds, but on a table
   only 85.6% (B) and 93.2% (D) can stand with any grip. It is also not *necessary*: at 4×4×3 physics
   accepts 6.4% of plain-WFC builds vs 3.9% by the rule, because a part with nothing below can hang from
   a part above it.
2. **Every "cannot stand" build is a tip-over.** On a baseplate (ground can pull) all B and D builds can be
   held. The failure mode is a sub-structure whose weight lies outside its ground contact — a global
   property that local support rules, in propagation or in a bottom-up builder, cannot see.
3. **Stability-aware WFC is the least robust stable generator.** Its overhangs (20% of parts) make builds
   depend on grip: only 2.9% stand without clutch, median required clutch 2.0, vs 27.1% / 1.0 for the
   bottom-up builder. C stands without any clutch in every case but never overhangs.
4. **For the decision checkpoint:** on support and physics alone, the bottom-up baseline (D) is faster,
   denser and physically more robust than stability-aware WFC (B). WFC's case rests entirely on the
   inventory + shape experiments (M9, M11) and learned style (M10).

## Possible follow-ups (not done)

- A tip-over check in propagation: keep each grounded sub-structure's centre of mass over its ground
  contact. It is global, so it would need incremental bookkeeping.
- Penalise long cantilevers in WFC weights, or cap overhang length, to trade expressiveness for robustness.
- Calibrate clutch against measured part weights and pull-off forces.
