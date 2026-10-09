# M12b step 3: the symmetrize threshold after M12b sizing

*Note (2026-10-10): the builds here predate the `_fit_key` fix (60b3a3b, `builder_version` 2: a tile that failed at a cell no longer makes the builder skip the plate of its box). The fix moves pair means by less than 2 SE (old vs fixed base on 9 pairs in [`m12b_complete.md`](m12b_complete.md)); a rerun would give different individual builds.*

`python -m brickwfc.experiments.skins --steps threshold`. The symmetry score of each scaled object (BrickGPT's chair, car and table at each set's volume, before support columns and symmetrization; best vertical plane through the middle of its extent) under the box sizing of the step-3 runs (`results/m12b_skins.md`) and the fillable sizing after M12b sizing (`results/m12b_sizing.md`, the default). With `--symmetric`, an object whose score reaches the threshold is made exactly symmetric by adding the mirror image of its cells; *added* is what that adds under fillable sizing.

| object | set | box: cells | box: plane (score) | fillable: cells | fillable: plane (score) | added (cells) | added % | symmetrized at 0.8 | symmetrized at 0.83 |
|---|---|---|---|---|---|---|---|---|---|
| chair | 6378-1 | 1725 | x = 6 (0.708) | 1725 | x = 6 (0.708) | 504 | 29 | no | no |
| car | 6378-1 | 1689 | x = 4 (0.848) | 1689 | x = 4 (0.848) | 257 | 15 | yes | yes |
| table | 6378-1 | 1706 | x = 8.5 (0.977) | 1748 | z = 8.5 (0.977) | 40 | 2 | yes | yes |
| chair | 5891-1 | 4688 | x = 8 (0.773) | 2847 | x = 7 (0.806) | 552 | 19 | yes (crosses) | no |
| car | 5891-1 | 4613 | x = 5.5 (0.923) | 2775 | x = 4.5 (0.865) | 375 | 14 | yes | yes |
| table | 5891-1 | 4632 | z = 11.5 (0.979) | 2880 | z = 9.5 (0.976) | 70 | 2 | yes | yes |
| chair | 10182-1 | 10656 | x = 11 (0.745) | 10045 | x = 10.5 (0.778) | 2235 | 22 | no | no |
| car | 10182-1 | 10704 | x = 7.5 (0.970) | 9526 | x = 7 (0.909) | 869 | 9 | yes | yes |
| table | 10182-1 | 10609 | x = 15 (0.921) | 10100 | z = 15 (0.976) | 240 | 2 | yes | yes |

Fillable sizing: chairs score at most 0.806, cars and tables at least 0.848. The threshold 0.83 sits between them with margins of 0.024 and 0.018: a fitted threshold on 9 pairs, not a property of the objects.

## The crossing pair: the 5891-1 chair, symmetrized

Before fillable sizing, the 5891-1 chair scored 0.773, under the old 0.8. It now scores 0.806, so at 0.8 `--symmetric` would symmetrize it. It has no mirror plane: its base is a five-arm star. Symmetrizing across x = 7 adds the mirror image of each arm, taking the object from 2847 to 3399 cells (+552, +19%; with support columns, 2859 → 3423). The added cells are:

- 342 in the base (layers 0-9, 21-65 object cells per layer, plus 21-51 added): the five feet become ten;
- 17 in the stem, one cell per layer (2 → 3 wide);
- about 9 per layer in the seat and about 10 per layer in the back.

To see what that does, base, symmetric and both ran under fillable sizing with 50 candidates each, the symmetric arms forced to the old threshold (`--symmetrize-min-score 0.8`). This run is evidence for the threshold, not a default. The reproduce command is in `docs/reproduce.md`; the outputs are `m12b_symmetry_threshold_chair.json` and `m12b_symmetry_threshold_chair.png`, the selected build of each arm side by side.

| arm | valid | judge (sd) | fill % | base-object fill % | top / side parts per 4x4 | mirrored of mirrorable % | s/candidate |
|---|---|---|---|---|---|---|---|
| base | 46/50 | -0.3570 (0.0120) | 67.6 | 67.6 | 7.34 / 3.95 | 10 | 63.0 |
| symmetric | 49/50 | -0.3792 (0.0138) | 68.2 | 71.4 | 6.83 / 3.51 | 32 | 35.6 |
| both | 49/50 | -0.3766 (0.0126) | 67.9 | 71.5 | 4.44 / 3.46 | 33 | 30.5 |
| selected base | | -0.3455 | 78.9 | 78.9 | 5.82 / 4.42 | 5 | |
| selected symmetric | | -0.3564 | 72.1 | 74.9 | 10.20 / 3.17 | 23 | |
| selected both | | -0.3500 | 69.8 | 72.8 | 4.06 / 3.26 | 22 | |

Means are over valid candidates. The judge is size-matched across the three arms (1682 contact events). Fill is measured against each arm's own object; base-object fill is measured against the unsymmetrized 2847-cell chair.

**The doubled-base chair builds and is acceptable to look at.**

- Every arm has at least 46/50 valid candidates (the symmetric arms 49/50), and every selected build stands as one piece.
- The symmetric arm's base reads as a denser spoked star; the both arm's base is a filled cross-shaped platform.
- The cost is about 2 sd of judge (-0.022 symmetric, -0.020 both, against a candidate sd of 0.012), and the selected build's fill drops 7-9 points.

**The threshold still goes to 0.83.** A five-arm base has no mirror plane, and the symmetrized object, with ten feet, is no longer BrickGPT's chair. Symmetrizing should change a target only where scaling broke a symmetry the object has: the cars, 0.85-0.97, and the tables, 0.98. At 0.83 no chair is symmetrized on any of the three sets, and every car and table still is.

## Notes for later (M13, if symmetry becomes a default)

- The score gate is a fitted threshold: margins of 0.024 (chairs at most 0.806) and 0.018 (cars and tables at least 0.848) on 9 pairs. A new object or set can land between them.
- Union symmetrization adds 9-15% cells to the cars (2% to the tables), and the symmetric arm loses fill on cars (`results/m12b_skins.md`).
- The alternative to measure is intersection symmetrization: drop the unmirrored cells instead of adding their mirror images.
