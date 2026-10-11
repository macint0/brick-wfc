# M12c — hollow targets at the solid's scale: measured, not adopted

Overnight 2026-10-11/12 (first step of `scripts/overnight_m12c.sh`; 1 h 57 on 5 workers). Arms `hollow1` and
`hollow1_80` = creserve's flags + `--hollow 1 --hollow-scale solid --bar surface` at slack 1.0 and 0.8, 50 candidates on
the 9 pairs of the completeness sweep, compared with `creserve` / `creserve80` on the same seeds. Raw table:
`m12c_hollow_sweep.md` (+ `.json`). The sizing-only expectation was in `m12c_hollow_sizing.md`: a 1-cell shell at the
solid's scale keeps the object's size and frees a median 25% of the part budget.

## Result: worse on 15 of 18 comparisons, 0 complete, and the thin sets stall outright

| pairs | hollow 1 better / worse on the 8 compared quantities (selected build) | selected fill, base → hollow | valid, base → hollow | complete |
|---|---|---|---|---|
| at 1.0 | better on 1 pair (6378-1 chair, 5/3), worse on 8 (1/7, 1/6, 2/5, 3/5, 1/7, 1/7, 1/7, 1/7) | 81–94% → 6–90% | 37–50 → 15–50 | 0 / 0 |
| at 0.8 | better on 0 pairs (3/5, 3/5, 2/6, 1/7, 1/6, 2/5, 2/6, 0/8, 0/8) | 86–98% → 19–90% | 38–50 → 24–50 | 0 / 0 |

- **Total stalls on the shells of the two larger sets:** the 5891-1 chair and table and the 4956-1 chair (and at 0.8 the
  4956-1 table) stall on 50 of 50 candidates (fill 6–25%, largest hole 1200–3100 cells). A 1-cell shell is a 1-stud wall
  on a 1-plate floor; connected growth from a ground seed cannot climb it with the parts these sets have, and the regrow
  flag was not in these arms. The 6378-1 pairs (small and blocky) and the cars keep going but lose 10–20 fill points.
- **Where the shell holds, it does not pay:** on the 6378-1 chair at 1.0 the largest hole shrinks (96 → 41) at the cost
  of 15 valid builds; everywhere else holes grow and validity, tips and fill fall. The freed budget is large parts; the
  shell wants more small parts than the solid did (every remnant now sits on an exposed face).
- **Cost:** 1.3–3.5× the time per candidate on the cars (18–85 s vs 7–36 s: many more failed placements per cell).

**Decision (cf):** `--hollow-scale solid` stays a flag, off; hollow targets are not part of the size rule. The surface bar
(interior cells invisible) remains the right measure for *solid* builds and is reported next to the volume bar in
every table. If hollowing is revisited it needs the regrow flag, a 2-cell shell and a part-supply check first
(`m12c_hollow_sizing.md` lists the risks that came true here).

## Reproduce

```
python -m brickwfc.experiments.complete --out out/m12b_complete --steps sweep --arms hollow1 hollow1_80 --workers 5
python -m brickwfc.experiments.complete --out out/m12b_complete --steps sweep-report --arms creserve hollow1 creserve80 hollow1_80 --report-name sweep_hollow
```
