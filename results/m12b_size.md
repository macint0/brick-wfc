# M12c — size below 0.8 with the reserve inside connected growth

Question (cf, 2026-10-10 night): the remnant demand is 1.5–2× the sets' small-part supply at 0.8–1.0. Does a smaller
target complete, and what is the largest size each set can complete? The new arms extend two families down to slack 0.6:
creserve (`--order connected --reserve-small`, `results/m12b_connected.md`) and the default (`usable + hang`). They run on
the same 9 sweep pairs, 50 candidates each, seeds 0–49, 5 workers:

| family | 1.0 | 0.9 | 0.8 | 0.7 | 0.6 |
|---|---|---|---|---|---|
| creserve (`--sizing usable --holes --hang --order connected --reserve-small --fill-slack s`) | creserve | **creserve90** | creserve80 | **creserve70** | **creserve60** |
| default (`--sizing usable --holes --hang --fill-slack s`) | usable | usable90 | usable80 | **usable70** | **usable60** |

- **Arms:** bold arms are new in this sweep. The others are the cached runs of `m12b_connected.md` and
  `m12b_complete.md`.
- **Targets:** at each slack both families have the same target (the target cells column below).
- **Bars**, as in M12c:
  - volume: fill ≥ 97%, largest hole ≤ 4, surface ≥ 98%;
  - surface: surface ≥ 98%, largest surface hole ≤ 4.

**The 6378-1 chair is a cut target (pre-reconnect).** Resampling cut its caster arms into separate pieces at every slack
(`results/m12c_stall_6378_chair.md`), so connected growth stalls there:
- creserve70: all 50 candidates at 3.5% fill;
- creserve60: 31 of 50 under half.

Its rows are marked and say nothing about size. The overnight queue reruns it on the reconnected target.

A run counts as stalled when most of its candidates end under 50% fill (`complete.stalled_cell`). Stalled runs are left
out of the largest-slack rule.

## Result

**Size is the lever, with the reserve inside growth. The default does not complete at any size.**

**creserve**, on the 8 uncut pairs:

| | 1.0 | 0.9 | 0.8 | 0.7 | 0.6 |
|---|---:|---:|---:|---:|---:|
| complete candidates (volume / surface bar) | 0 / 0 | 0 / 0 | 1 / 1 | 1 / 1 | **15 / 18** |
| mean selected fill % | 87.6 | 88.8 | 91.0 | 95.3 | **97.5** |
| mean selected largest hole | 149 | 136 | 91 | 46 | **16** |
| mean selected surface % | 86.4 | 87.4 | 89.2 | 94.3 | **97.1** |

**Default (`usable + hang`):** 0 complete candidates of 1,881 valid, at every slack (8 pairs × 5 slacks). From 1.0 to 0.6
the mean selected fill goes 80.9 → 89.1 and the largest hole 224 → 58. Shrinking alone does not reach the bar; the order
and the reserve do.

**Cost:** creserve is faster at every slack. From 1.0 to 0.6 it takes 27.4 → 16.0 s per candidate, against 43.0 → 27.1 for
the default. It keeps as many valid candidates (386 vs 390 of 400 at 0.6).

**The largest size the set can complete.** For the creserve family: the largest slack with a complete candidate, and with
a complete selected build. The default completes nothing, so it has no row.

| pair | any candidate complete | selected complete (stored rule: score order) | selected complete (completeness-first, volume / surface bar) | best selected build where none is complete |
|---|---:|---:|---:|---|
| chair 6378-1 | cut target (pre-reconnect) | — | — | 95.4 / 12 / 94.6 at 0.6, on the cut target |
| chair 5891-1 | 0.8 (1 candidate) | none | 0.8 / 0.8 | 0.6: 99.2 / 6 / 99.0 (misses on the 6-cell hole) |
| chair 4956-1 | none to 0.6 | none | none | 0.6: 95.3 / 20 / 94.0 |
| table 6378-1 | **0.7** (1; 10 at 0.6) | **0.7** | 0.7 / 0.7 (0.6 also, seed 5) | |
| table 5891-1 | **0.6** (4) | **0.6** | 0.6 / 0.6 | |
| table 4956-1 | none to 0.6 | none | none | 0.6: 98.8 / 24 / 98.1 |
| car 6378-1 | 0.6, surface bar only (1) | none | none / 0.6 | 0.6: 96.3 / 20 / 95.3 |
| car 5891-1 | **0.6** (1 volume, 3 surface) | **0.6** | 0.6 / 0.6 | |
| car 4956-1 | none to 0.6 | none | none | 0.6: 94.5 / 39 / 94.5 |

Builds are given as fill % / largest hole / surface %. The 5891-1 chair is the creserve80 seed 1 of
`m12b_connected.md`. Under completeness-first it is the selected build (`results/m12c_select.md`).

The rule, stated per pair:
- **6378-1 table:** completes at 0.7 of its set's volume.
- **5891-1 table and car:** complete at 0.6.
- **5891-1 chair:** 0.8, from one candidate of 50. It does not complete again at 0.7 or 0.6, where the selected builds
  miss by a 13-cell and a 6-cell hole: one complete candidate is luck, cf's point.
- **6378-1 car:** 0.6, on the surface bar only.
- **4956-1 chair, table and car:** none down to 0.6. 4956-1 is the largest set, 4334–4554 target cells at 1.0. Its
  selected builds still improve steadily (table fill 84.1 → 98.8).

So "the largest size the set can complete" lies inside 0.6–0.8 for 4–5 of the 8 uncut pairs. For the 4956-1 objects it is
below 0.6, or does not exist.

**Selection.** These runs were made at 007e6dd, before completeness-first selection, so their stored picks use score
order. They were re-ranked with no generation, at main 044b8f6:

```
python -m brickwfc.experiments.select --arms creserve90 creserve70 creserve60 usable70 usable60 --out out/m12c_size_select
```

Every stored pick reproduces under the old rule.
- **Volume bar:** one pick changes. creserve60 6378-1 table goes from seed 26 (97.9 / 8 / 97.2) to seed 5 (99.0 / 4 / 98.6,
  complete).
- **Surface bar:** that pick changes too, and so does creserve60 6378-1 car, from seed 25 to seed 22 (97.9 / 12 / 98.3,
  largest surface hole 3).

With completeness-first as the default, the selected build is complete wherever a complete candidate exists in these runs.
The one exception is the 6378-1 car under the volume bar, where no complete candidate exists.

## Per pair and slack

The selected-build columns are the stored pick (score order). Means are over valid candidates. The stalled column counts
candidates under 50% fill.

| object | set | family | slack | target cells | valid | fill % (mean) | largest hole (mean) | surface % (mean) | largest surface hole (mean) | fill % (sel) | largest hole (sel) | surface % (sel) | largest surface hole (sel) | complete (sel, vol / surf) | candidates meeting the bar (vol / surf) | s / candidate | stalled |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| chair (cut target, pre-reconnect) | 6378-1 | creserve | 1.0 | 1326 | 49/50 | 86.5 | 82 | 84.2 | 82 | 88.9 | 96 | 87.0 | 96 | no / no | 0 / 0 | 4.4 | 0 |
| chair (cut target, pre-reconnect) | 6378-1 | creserve | 0.9 | 1204 | 49/50 | 89.9 | 41 | 87.8 | 41 | 94.3 | 35 | 93.0 | 35 | no / no | 0 / 0 | 4.7 | 0 |
| chair (cut target, pre-reconnect) | 6378-1 | creserve | 0.8 | 1138 | 50/50 | 91.4 | 38 | 90.0 | 38 | 94.5 | 35 | 93.4 | 35 | no / no | 0 / 0 | 3.6 | 0 |
| chair (cut target, pre-reconnect) | 6378-1 | creserve | 0.7 | 979 | 50/50 | 3.4 | 943 | 4.1 | 628 | 3.7 | 943 | 4.5 | 628 | no / no | 0 / 0 | 2.2 | 50 (run stalled) |
| chair (cut target, pre-reconnect) | 6378-1 | creserve | 0.6 | 799 | 37/50 | 18.1 | 623 | 18.2 | 455 | 95.4 | 12 | 94.6 | 12 | no / no | 0 / 0 | 3.1 | 31 (run stalled) |
| chair (cut target, pre-reconnect) | 6378-1 | usable | 1.0 | 1326 | 49/50 | 84.4 | 49 | 82.4 | 48 | 88.6 | 34 | 87.0 | 30 | no / no | 0 / 0 | 10.3 | 0 |
| chair (cut target, pre-reconnect) | 6378-1 | usable | 0.9 | 1204 | 50/50 | 84.9 | 53 | 82.0 | 53 | 88.1 | 38 | 85.7 | 38 | no / no | 0 / 0 | 6.0 | 0 |
| chair (cut target, pre-reconnect) | 6378-1 | usable | 0.8 | 1138 | 50/50 | 85.7 | 52 | 83.4 | 52 | 90.6 | 35 | 89.1 | 35 | no / no | 0 / 0 | 11.8 | 0 |
| chair (cut target, pre-reconnect) | 6378-1 | usable | 0.7 | 979 | 50/50 | 85.2 | 46 | 82.3 | 46 | 87.3 | 36 | 84.6 | 36 | no / no | 0 / 0 | 6.4 | 0 |
| chair (cut target, pre-reconnect) | 6378-1 | usable | 0.6 | 799 | 32/50 | 61.1 | 264 | 60.7 | 194 | 96.5 | 12 | 95.9 | 12 | no / no | 0 / 0 | 9.2 | 11 |
| chair | 5891-1 | creserve | 1.0 | 2784 | 50/50 | 82.8 | 313 | 81.2 | 192 | 93.6 | 18 | 92.8 | 13 | no / no | 0 / 0 | 29.6 | 5 |
| chair | 5891-1 | creserve | 0.9 | 2621 | 42/50 | 90.7 | 50 | 88.8 | 44 | 93.1 | 25 | 92.1 | 25 | no / no | 0 / 0 | 30.8 | 0 |
| chair | 5891-1 | creserve | 0.8 | 2323 | 48/50 | 67.6 | 690 | 66.7 | 394 | 98.5 | 7 | 98.0 | 7 | no / no | 1 / 1 | 17.1 | 14 |
| chair | 5891-1 | creserve | 0.7 | 1974 | 50/50 | 87.1 | 176 | 85.3 | 126 | 98.5 | 13 | 98.1 | 13 | no / no | 0 / 0 | 16.8 | 3 |
| chair | 5891-1 | creserve | 0.6 | 1737 | 50/50 | 94.2 | 46 | 93.0 | 46 | 99.2 | 6 | 99.0 | 6 | no / no | 0 / 0 | 14.2 | 0 |
| chair | 5891-1 | usable | 1.0 | 2784 | 50/50 | 83.6 | 142 | 79.7 | 132 | 84.9 | 172 | 81.5 | 160 | no / no | 0 / 0 | 75.2 | 0 |
| chair | 5891-1 | usable | 0.9 | 2621 | 47/50 | 81.1 | 133 | 77.6 | 120 | 87.5 | 76 | 84.5 | 70 | no / no | 0 / 0 | 84.3 | 0 |
| chair | 5891-1 | usable | 0.8 | 2323 | 44/50 | 81.9 | 95 | 78.6 | 86 | 88.0 | 49 | 85.1 | 49 | no / no | 0 / 0 | 50.9 | 0 |
| chair | 5891-1 | usable | 0.7 | 1974 | 49/50 | 88.2 | 60 | 85.8 | 60 | 94.0 | 36 | 92.4 | 36 | no / no | 0 / 0 | 38.2 | 0 |
| chair | 5891-1 | usable | 0.6 | 1737 | 50/50 | 89.0 | 68 | 86.9 | 65 | 94.1 | 12 | 93.0 | 12 | no / no | 0 / 0 | 29.2 | 0 |
| chair | 4956-1 | creserve | 1.0 | 4334 | 47/50 | 78.4 | 565 | 74.6 | 349 | 86.6 | 244 | 82.1 | 228 | no / no | 0 / 0 | 39.0 | 3 |
| chair | 4956-1 | creserve | 0.9 | 3892 | 28/50 | 84.9 | 242 | 82.6 | 163 | 88.6 | 86 | 86.3 | 66 | no / no | 0 / 0 | 35.5 | 0 |
| chair | 4956-1 | creserve | 0.8 | 3480 | 42/50 | 81.6 | 423 | 79.0 | 257 | 89.9 | 80 | 87.6 | 77 | no / no | 0 / 0 | 22.7 | 4 |
| chair | 4956-1 | creserve | 0.7 | 3022 | 41/50 | 88.8 | 111 | 86.5 | 88 | 94.0 | 28 | 92.6 | 28 | no / no | 0 / 0 | 26.4 | 0 |
| chair | 4956-1 | creserve | 0.6 | 2617 | 45/50 | 90.7 | 63 | 88.6 | 52 | 95.3 | 20 | 94.0 | 20 | no / no | 0 / 0 | 23.0 | 0 |
| chair | 4956-1 | usable | 1.0 | 4334 | 41/50 | 74.2 | 367 | 69.1 | 289 | 77.7 | 363 | 72.6 | 314 | no / no | 0 / 0 | 81.3 | 0 |
| chair | 4956-1 | usable | 0.9 | 3892 | 39/50 | 76.4 | 281 | 71.6 | 219 | 80.8 | 302 | 77.9 | 286 | no / no | 0 / 0 | 74.1 | 0 |
| chair | 4956-1 | usable | 0.8 | 3480 | 38/50 | 76.2 | 271 | 72.0 | 193 | 83.0 | 122 | 78.7 | 95 | no / no | 0 / 0 | 66.8 | 0 |
| chair | 4956-1 | usable | 0.7 | 3022 | 49/50 | 80.6 | 173 | 76.9 | 148 | 85.2 | 85 | 82.8 | 85 | no / no | 0 / 0 | 60.7 | 0 |
| chair | 4956-1 | usable | 0.6 | 2617 | 47/50 | 80.1 | 141 | 76.5 | 116 | 86.9 | 56 | 84.0 | 56 | no / no | 0 / 0 | 65.8 | 0 |
| table | 6378-1 | creserve | 1.0 | 1748 | 50/50 | 69.5 | 302 | 69.4 | 171 | 81.4 | 119 | 84.5 | 23 | no / no | 0 / 0 | 6.1 | 7 |
| table | 6378-1 | creserve | 0.9 | 1576 | 49/50 | 73.3 | 239 | 71.8 | 142 | 81.5 | 96 | 79.8 | 96 | no / no | 0 / 0 | 6.5 | 5 |
| table | 6378-1 | creserve | 0.8 | 1344 | 50/50 | 81.5 | 128 | 79.3 | 82 | 86.5 | 76 | 82.7 | 76 | no / no | 0 / 0 | 4.5 | 2 |
| table | 6378-1 | creserve | 0.7 | 1122 | 50/50 | 88.7 | 73 | 86.6 | 47 | 99.4 | 1 | 99.1 | 1 | yes / yes | 1 / 1 | 3.9 | 2 |
| table | 6378-1 | creserve | 0.6 | 770 | 50/50 | 94.2 | 24 | 92.7 | 24 | 97.9 | 8 | 97.2 | 8 | no / no | 10 / 10 | 2.8 | 0 |
| table | 6378-1 | usable | 1.0 | 1748 | 48/50 | 69.9 | 134 | 62.2 | 112 | 78.5 | 96 | 76.4 | 96 | no / no | 0 / 0 | 9.0 | 0 |
| table | 6378-1 | usable | 0.9 | 1576 | 50/50 | 74.0 | 112 | 67.4 | 105 | 80.5 | 92 | 77.7 | 33 | no / no | 0 / 0 | 8.0 | 0 |
| table | 6378-1 | usable | 0.8 | 1344 | 49/50 | 77.3 | 93 | 69.3 | 91 | 83.9 | 92 | 79.1 | 92 | no / no | 0 / 0 | 6.2 | 0 |
| table | 6378-1 | usable | 0.7 | 1122 | 49/50 | 85.1 | 54 | 79.1 | 52 | 94.0 | 8 | 91.7 | 8 | no / no | 0 / 0 | 5.8 | 0 |
| table | 6378-1 | usable | 0.6 | 770 | 50/50 | 86.9 | 42 | 83.0 | 42 | 94.4 | 34 | 92.6 | 34 | no / no | 0 / 0 | 3.7 | 0 |
| table | 5891-1 | creserve | 1.0 | 2880 | 48/50 | 89.3 | 79 | 88.1 | 58 | 91.9 | 15 | 90.7 | 15 | no / no | 0 / 0 | 29.0 | 0 |
| table | 5891-1 | creserve | 0.9 | 2570 | 50/50 | 82.5 | 277 | 81.7 | 106 | 92.3 | 31 | 90.7 | 20 | no / no | 0 / 0 | 32.5 | 0 |
| table | 5891-1 | creserve | 0.8 | 2328 | 48/50 | 89.9 | 132 | 89.0 | 59 | 96.0 | 9 | 95.9 | 9 | no / no | 0 / 0 | 21.8 | 2 |
| table | 5891-1 | creserve | 0.7 | 1980 | 50/50 | 85.3 | 191 | 81.3 | 110 | 94.4 | 40 | 94.5 | 21 | no / no | 0 / 0 | 20.8 | 3 |
| table | 5891-1 | creserve | 0.6 | 1770 | 50/50 | 85.7 | 198 | 82.5 | 109 | 99.4 | 3 | 99.1 | 3 | yes / yes | 4 / 4 | 17.7 | 4 |
| table | 5891-1 | usable | 1.0 | 2880 | 39/50 | 79.3 | 192 | 71.1 | 153 | 87.1 | 108 | 81.3 | 108 | no / no | 0 / 0 | 44.7 | 0 |
| table | 5891-1 | usable | 0.9 | 2570 | 42/50 | 79.4 | 155 | 71.7 | 142 | 88.5 | 114 | 82.7 | 114 | no / no | 0 / 0 | 38.4 | 0 |
| table | 5891-1 | usable | 0.8 | 2328 | 43/50 | 81.6 | 163 | 75.3 | 124 | 93.3 | 29 | 91.1 | 29 | no / no | 0 / 0 | 31.6 | 1 |
| table | 5891-1 | usable | 0.7 | 1980 | 49/50 | 81.2 | 110 | 71.7 | 108 | 85.8 | 108 | 79.9 | 108 | no / no | 0 / 0 | 27.4 | 0 |
| table | 5891-1 | usable | 0.6 | 1770 | 48/50 | 80.6 | 113 | 71.2 | 108 | 84.6 | 108 | 75.9 | 108 | no / no | 0 / 0 | 25.7 | 0 |
| table | 4956-1 | creserve | 1.0 | 4414 | 37/50 | 80.2 | 598 | 75.3 | 365 | 84.1 | 307 | 78.3 | 254 | no / no | 0 / 0 | 48.9 | 0 |
| table | 4956-1 | creserve | 0.9 | 4008 | 42/50 | 82.0 | 415 | 77.7 | 265 | 83.0 | 603 | 78.3 | 409 | no / no | 0 / 0 | 44.9 | 0 |
| table | 4956-1 | creserve | 0.8 | 3627 | 38/50 | 81.4 | 443 | 77.0 | 282 | 86.4 | 390 | 80.1 | 312 | no / no | 0 / 0 | 34.8 | 0 |
| table | 4956-1 | creserve | 0.7 | 2947 | 40/50 | 84.3 | 277 | 80.7 | 148 | 96.1 | 57 | 93.4 | 51 | no / no | 0 / 0 | 30.3 | 2 |
| table | 4956-1 | creserve | 0.6 | 2570 | 41/50 | 75.4 | 529 | 74.8 | 221 | 98.8 | 24 | 98.1 | 24 | no / no | 0 / 0 | 32.9 | 2 |
| table | 4956-1 | usable | 1.0 | 4414 | 39/50 | 75.0 | 671 | 67.5 | 377 | 81.5 | 253 | 78.4 | 57 | no / no | 0 / 0 | 61.4 | 0 |
| table | 4956-1 | usable | 0.9 | 4008 | 42/50 | 76.6 | 503 | 69.6 | 301 | 78.4 | 689 | 76.9 | 354 | no / no | 0 / 0 | 55.0 | 0 |
| table | 4956-1 | usable | 0.8 | 3627 | 41/50 | 77.8 | 425 | 71.6 | 268 | 84.9 | 351 | 85.4 | 172 | no / no | 0 / 0 | 49.5 | 0 |
| table | 4956-1 | usable | 0.7 | 2947 | 48/50 | 78.5 | 239 | 68.8 | 188 | 87.3 | 138 | 84.0 | 97 | no / no | 0 / 0 | 56.4 | 0 |
| table | 4956-1 | usable | 0.6 | 2570 | 45/50 | 76.2 | 248 | 67.2 | 208 | 84.8 | 164 | 81.8 | 164 | no / no | 0 / 0 | 52.0 | 0 |
| car | 6378-1 | creserve | 1.0 | 1721 | 50/50 | 75.8 | 264 | 75.5 | 78 | 87.4 | 92 | 86.5 | 56 | no / no | 0 / 0 | 6.6 | 0 |
| car | 6378-1 | creserve | 0.9 | 1494 | 50/50 | 83.4 | 144 | 84.6 | 43 | 89.1 | 73 | 88.8 | 36 | no / no | 0 / 0 | 4.0 | 0 |
| car | 6378-1 | creserve | 0.8 | 1380 | 50/50 | 85.3 | 97 | 86.7 | 32 | 87.6 | 75 | 87.5 | 28 | no / no | 0 / 0 | 3.1 | 0 |
| car | 6378-1 | creserve | 0.7 | 1166 | 50/50 | 90.4 | 48 | 90.5 | 19 | 95.5 | 11 | 94.1 | 5 | no / no | 0 / 0 | 3.2 | 0 |
| car | 6378-1 | creserve | 0.6 | 947 | 50/50 | 91.5 | 41 | 90.6 | 23 | 96.3 | 20 | 95.3 | 20 | no / no | 0 / 1 | 2.8 | 0 |
| car | 6378-1 | usable | 1.0 | 1721 | 50/50 | 73.3 | 189 | 70.0 | 93 | 75.8 | 194 | 74.0 | 41 | no / no | 0 / 0 | 4.5 | 0 |
| car | 6378-1 | usable | 0.9 | 1494 | 50/50 | 76.9 | 121 | 74.9 | 45 | 81.6 | 44 | 75.4 | 42 | no / no | 0 / 0 | 4.1 | 0 |
| car | 6378-1 | usable | 0.8 | 1380 | 50/50 | 78.3 | 96 | 76.5 | 39 | 84.1 | 49 | 82.0 | 18 | no / no | 0 / 0 | 3.7 | 0 |
| car | 6378-1 | usable | 0.7 | 1166 | 50/50 | 83.2 | 48 | 80.5 | 26 | 86.4 | 37 | 86.7 | 21 | no / no | 0 / 0 | 3.6 | 0 |
| car | 6378-1 | usable | 0.6 | 947 | 50/50 | 85.4 | 33 | 83.8 | 20 | 89.9 | 24 | 89.0 | 24 | no / no | 0 / 0 | 2.2 | 0 |
| car | 5891-1 | creserve | 1.0 | 2807 | 49/50 | 87.5 | 131 | 88.0 | 33 | 92.5 | 53 | 93.1 | 14 | no / no | 0 / 0 | 24.0 | 0 |
| car | 5891-1 | creserve | 0.9 | 2627 | 50/50 | 88.5 | 100 | 88.6 | 29 | 95.8 | 15 | 95.0 | 8 | no / no | 0 / 0 | 23.7 | 0 |
| car | 5891-1 | creserve | 0.8 | 2357 | 50/50 | 89.4 | 81 | 89.1 | 23 | 92.3 | 31 | 91.0 | 15 | no / no | 0 / 0 | 18.1 | 0 |
| car | 5891-1 | creserve | 0.7 | 2005 | 50/50 | 94.1 | 29 | 93.8 | 14 | 97.0 | 11 | 96.0 | 5 | no / no | 0 / 0 | 15.7 | 0 |
| car | 5891-1 | creserve | 0.6 | 1761 | 50/50 | 94.9 | 29 | 95.0 | 11 | 98.8 | 4 | 99.2 | 3 | yes / yes | 1 / 3 | 13.7 | 0 |
| car | 5891-1 | usable | 1.0 | 2807 | 50/50 | 82.2 | 129 | 79.0 | 60 | 84.8 | 75 | 81.4 | 31 | no / no | 0 / 0 | 16.8 | 0 |
| car | 5891-1 | usable | 0.9 | 2627 | 50/50 | 83.0 | 105 | 80.5 | 46 | 87.5 | 34 | 84.5 | 24 | no / no | 0 / 0 | 20.8 | 0 |
| car | 5891-1 | usable | 0.8 | 2357 | 50/50 | 84.9 | 69 | 82.3 | 35 | 87.2 | 22 | 85.4 | 20 | no / no | 0 / 0 | 13.9 | 0 |
| car | 5891-1 | usable | 0.7 | 2005 | 50/50 | 87.8 | 48 | 85.8 | 27 | 89.3 | 49 | 87.9 | 31 | no / no | 0 / 0 | 15.5 | 0 |
| car | 5891-1 | usable | 0.6 | 1761 | 50/50 | 89.6 | 30 | 88.1 | 21 | 92.6 | 15 | 92.0 | 12 | no / no | 0 / 0 | 10.9 | 0 |
| car | 4956-1 | creserve | 1.0 | 4554 | 46/50 | 80.0 | 645 | 80.8 | 95 | 83.4 | 345 | 83.1 | 38 | no / no | 0 / 0 | 35.9 | 0 |
| car | 4956-1 | creserve | 0.9 | 4032 | 45/50 | 82.1 | 467 | 83.0 | 80 | 86.9 | 160 | 88.5 | 37 | no / no | 0 / 0 | 36.5 | 0 |
| car | 4956-1 | creserve | 0.8 | 3512 | 48/50 | 84.4 | 288 | 82.5 | 66 | 91.1 | 59 | 90.7 | 26 | no / no | 0 / 0 | 25.2 | 0 |
| car | 4956-1 | creserve | 0.7 | 3134 | 49/50 | 83.2 | 331 | 81.6 | 74 | 87.7 | 204 | 86.8 | 42 | no / no | 0 / 0 | 28.1 | 0 |
| car | 4956-1 | creserve | 0.6 | 2628 | 50/50 | 89.8 | 119 | 89.5 | 35 | 94.5 | 39 | 94.5 | 16 | no / no | 0 / 0 | 21.0 | 0 |
| car | 4956-1 | usable | 1.0 | 4554 | 46/50 | 74.9 | 585 | 72.2 | 166 | 76.8 | 527 | 73.0 | 75 | no / no | 0 / 0 | 50.9 | 0 |
| car | 4956-1 | usable | 0.9 | 4032 | 49/50 | 76.0 | 466 | 73.2 | 138 | 78.3 | 255 | 72.6 | 96 | no / no | 0 / 0 | 40.9 | 0 |
| car | 4956-1 | usable | 0.8 | 3512 | 50/50 | 78.3 | 289 | 73.9 | 94 | 81.4 | 260 | 79.5 | 93 | no / no | 0 / 0 | 29.9 | 0 |
| car | 4956-1 | usable | 0.7 | 3134 | 50/50 | 77.7 | 255 | 73.1 | 112 | 80.5 | 159 | 74.8 | 96 | no / no | 0 / 0 | 38.6 | 0 |
| car | 4956-1 | usable | 0.6 | 2628 | 50/50 | 82.4 | 140 | 79.1 | 66 | 85.4 | 47 | 83.9 | 34 | no / no | 0 / 0 | 27.4 | 0 |

| object | set | family | largest slack, any candidate complete (vol / surf) | largest slack, selected complete (vol / surf) | candidates meeting the volume bar (1.0 / 0.9 / 0.8 / 0.7 / 0.6) | candidates meeting the surface bar | stalled runs (left out) |
|---|---|---|---:|---:|---:|---:|---:|
| chair (cut target, pre-reconnect) | 6378-1 | creserve | none / none | none / none | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 | 0.7, 0.6 |
| chair (cut target, pre-reconnect) | 6378-1 | usable | none / none | none / none | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 | none |
| chair | 5891-1 | creserve | 0.8 / 0.8 | none / none | 0 / 0 / 1 / 0 / 0 | 0 / 0 / 1 / 0 / 0 | none |
| chair | 5891-1 | usable | none / none | none / none | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 | none |
| chair | 4956-1 | creserve | none / none | none / none | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 | none |
| chair | 4956-1 | usable | none / none | none / none | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 | none |
| table | 6378-1 | creserve | 0.7 / 0.7 | 0.7 / 0.7 | 0 / 0 / 0 / 1 / 10 | 0 / 0 / 0 / 1 / 10 | none |
| table | 6378-1 | usable | none / none | none / none | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 | none |
| table | 5891-1 | creserve | 0.6 / 0.6 | 0.6 / 0.6 | 0 / 0 / 0 / 0 / 4 | 0 / 0 / 0 / 0 / 4 | none |
| table | 5891-1 | usable | none / none | none / none | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 | none |
| table | 4956-1 | creserve | none / none | none / none | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 | none |
| table | 4956-1 | usable | none / none | none / none | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 | none |
| car | 6378-1 | creserve | none / 0.6 | none / none | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 1 | none |
| car | 6378-1 | usable | none / none | none / none | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 | none |
| car | 5891-1 | creserve | 0.6 / 0.6 | 0.6 / 0.6 | 0 / 0 / 0 / 0 / 1 | 0 / 0 / 0 / 0 / 3 | none |
| car | 5891-1 | usable | none / none | none / none | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 | none |
| car | 4956-1 | creserve | none / none | none / none | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 | none |
| car | 4956-1 | usable | none / none | none / none | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 | none |

Selected builds compared, creserve vs the default at each slack, and creserve from one slack to the next (`SIZE_COMPARE`).
+ means the second arm is better, - worse. Across slacks the targets differ, so those rows show the size trade, not a
paired test:

| object | set | base -> arm | same target | fill % | holes | largest hole | surface % | largest surface hole | tips filled % | valid | s / candidate | complete (sel, vol / surf) | stalled | better / worse |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| chair (cut target, pre-reconnect) | 6378-1 | usable + hang -> connected + reserve-small | yes | 88.6 -> 88.9 + | 33 -> 15 + | 34 -> 96 - | 87.0 -> 87.0 = | 30 -> 96 - | 62 -> 88 + | 49 -> 49 = | 10.3 -> 4.4 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 4 / 2 |
| chair | 5891-1 | usable + hang -> connected + reserve-small | yes | 84.9 -> 93.6 + | 62 -> 39 + | 172 -> 18 + | 81.5 -> 92.8 + | 160 -> 13 + | 45 -> 93 + | 50 -> 50 = | 75.2 -> 29.6 + | 0 / 0 -> 0 / 0 | 0 -> 5 | 7 / 0 |
| chair | 4956-1 | usable + hang -> connected + reserve-small | yes | 77.7 -> 86.6 + | 43 -> 22 + | 363 -> 244 + | 72.6 -> 82.1 + | 314 -> 228 + | 40 -> 99 + | 41 -> 47 + | 81.3 -> 39.0 + | 0 / 0 -> 0 / 0 | 0 -> 3 | 8 / 0 |
| table | 6378-1 | usable + hang -> connected + reserve-small | yes | 78.5 -> 81.4 + | 16 -> 22 - | 96 -> 119 - | 76.4 -> 84.5 + | 96 -> 23 + | 70 -> 100 + | 48 -> 50 + | 9.0 -> 6.1 + | 0 / 0 -> 0 / 0 | 0 -> 7 | 6 / 2 |
| table | 5891-1 | usable + hang -> connected + reserve-small | yes | 87.1 -> 91.9 + | 40 -> 55 - | 108 -> 15 + | 81.3 -> 90.7 + | 108 -> 15 + | 67 -> 100 + | 39 -> 48 + | 44.7 -> 29.0 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 1 |
| table | 4956-1 | usable + hang -> connected + reserve-small | yes | 81.5 -> 84.1 + | 41 -> 31 + | 253 -> 307 - | 78.4 -> 78.3 - | 57 -> 254 - | 79 -> 100 + | 39 -> 37 - | 61.4 -> 48.9 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 4 / 4 |
| car | 6378-1 | usable + hang -> connected + reserve-small | yes | 75.8 -> 87.4 + | 24 -> 20 + | 194 -> 92 + | 74.0 -> 86.5 + | 41 -> 56 - | 79 -> 97 + | 50 -> 50 = | 4.5 -> 6.6 - | 0 / 0 -> 0 / 0 | 0 -> 0 | 5 / 2 |
| car | 5891-1 | usable + hang -> connected + reserve-small | yes | 84.8 -> 92.5 + | 69 -> 40 + | 75 -> 53 + | 81.4 -> 93.1 + | 31 -> 14 + | 81 -> 99 + | 50 -> 49 - | 16.8 -> 24.0 - | 0 / 0 -> 0 / 0 | 0 -> 0 | 6 / 2 |
| car | 4956-1 | usable + hang -> connected + reserve-small | yes | 76.8 -> 83.4 + | 39 -> 34 + | 527 -> 345 + | 73.0 -> 83.1 + | 75 -> 38 + | 85 -> 96 + | 46 -> 46 = | 50.9 -> 35.9 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 0 |
| chair (cut target, pre-reconnect) | 6378-1 | usable 0.9 + hang -> connected + reserve-small, 0.9 | yes | 88.1 -> 94.3 + | 24 -> 14 + | 38 -> 35 + | 85.7 -> 93.0 + | 38 -> 35 + | 49 -> 61 + | 50 -> 49 - | 6.0 -> 4.7 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 1 |
| chair | 5891-1 | usable 0.9 + hang -> connected + reserve-small, 0.9 | yes | 87.5 -> 93.1 + | 37 -> 27 + | 76 -> 25 + | 84.5 -> 92.1 + | 70 -> 25 + | 41 -> 100 + | 47 -> 42 - | 84.3 -> 30.8 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 1 |
| chair | 4956-1 | usable 0.9 + hang -> connected + reserve-small, 0.9 | yes | 80.8 -> 88.6 + | 50 -> 21 + | 302 -> 86 + | 77.9 -> 86.3 + | 286 -> 66 + | 55 -> 100 + | 39 -> 28 - | 74.1 -> 35.5 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 1 |
| table | 6378-1 | usable 0.9 + hang -> connected + reserve-small, 0.9 | yes | 80.5 -> 81.5 + | 22 -> 22 = | 92 -> 96 - | 77.7 -> 79.8 + | 33 -> 96 - | 63 -> 75 + | 50 -> 49 - | 8.0 -> 6.5 + | 0 / 0 -> 0 / 0 | 0 -> 5 | 4 / 3 |
| table | 5891-1 | usable 0.9 + hang -> connected + reserve-small, 0.9 | yes | 88.5 -> 92.3 + | 43 -> 37 + | 114 -> 31 + | 82.7 -> 90.7 + | 114 -> 20 + | 51 -> 99 + | 42 -> 50 + | 38.4 -> 32.5 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 8 / 0 |
| table | 4956-1 | usable 0.9 + hang -> connected + reserve-small, 0.9 | yes | 78.4 -> 83.0 + | 20 -> 27 - | 689 -> 603 + | 76.9 -> 78.3 + | 354 -> 409 - | 93 -> 97 + | 42 -> 42 = | 55.0 -> 44.9 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 5 / 2 |
| car | 6378-1 | usable 0.9 + hang -> connected + reserve-small, 0.9 | yes | 81.6 -> 89.1 + | 33 -> 13 + | 44 -> 73 - | 75.4 -> 88.8 + | 42 -> 36 + | 70 -> 100 + | 50 -> 50 = | 4.1 -> 4.0 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 6 / 1 |
| car | 5891-1 | usable 0.9 + hang -> connected + reserve-small, 0.9 | yes | 87.5 -> 95.8 + | 63 -> 40 + | 34 -> 15 + | 84.5 -> 95.0 + | 24 -> 8 + | 80 -> 100 + | 50 -> 50 = | 20.8 -> 23.7 - | 0 / 0 -> 0 / 0 | 0 -> 0 | 6 / 1 |
| car | 4956-1 | usable 0.9 + hang -> connected + reserve-small, 0.9 | yes | 78.3 -> 86.9 + | 38 -> 14 + | 255 -> 160 + | 72.6 -> 88.5 + | 96 -> 37 + | 74 -> 99 + | 49 -> 45 - | 40.9 -> 36.5 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 1 |
| chair (cut target, pre-reconnect) | 6378-1 | usable 0.8 + hang -> connected + reserve-small, 0.8 | yes | 90.6 -> 94.5 + | 17 -> 10 + | 35 -> 35 = | 89.1 -> 93.4 + | 35 -> 35 = | 42 -> 61 + | 50 -> 50 = | 11.8 -> 3.6 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 5 / 0 |
| chair | 5891-1 | usable 0.8 + hang -> connected + reserve-small, 0.8 | yes | 88.0 -> 98.5 + | 43 -> 13 + | 49 -> 7 + | 85.1 -> 98.0 + | 49 -> 7 + | 73 -> 100 + | 44 -> 48 + | 50.9 -> 17.1 + | 0 / 0 -> 0 / 0 | 0 -> 14 | 8 / 0 |
| chair | 4956-1 | usable 0.8 + hang -> connected + reserve-small, 0.8 | yes | 83.0 -> 89.9 + | 53 -> 28 + | 122 -> 80 + | 78.7 -> 87.6 + | 95 -> 77 + | 45 -> 100 + | 38 -> 42 + | 66.8 -> 22.7 + | 0 / 0 -> 0 / 0 | 0 -> 4 | 8 / 0 |
| table | 6378-1 | usable 0.8 + hang -> connected + reserve-small, 0.8 | yes | 83.9 -> 86.5 + | 36 -> 22 + | 92 -> 76 + | 79.1 -> 82.7 + | 92 -> 76 + | 69 -> 82 + | 49 -> 50 + | 6.2 -> 4.5 + | 0 / 0 -> 0 / 0 | 0 -> 2 | 8 / 0 |
| table | 5891-1 | usable 0.8 + hang -> connected + reserve-small, 0.8 | yes | 93.3 -> 96.0 + | 36 -> 31 + | 29 -> 9 + | 91.1 -> 95.9 + | 29 -> 9 + | 94 -> 100 + | 43 -> 48 + | 31.6 -> 21.8 + | 0 / 0 -> 0 / 0 | 1 -> 2 | 8 / 0 |
| table | 4956-1 | usable 0.8 + hang -> connected + reserve-small, 0.8 | yes | 84.9 -> 86.4 + | 29 -> 7 + | 351 -> 390 - | 85.4 -> 80.1 - | 172 -> 312 - | 94 -> 99 + | 41 -> 38 - | 49.5 -> 34.8 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 4 / 4 |
| car | 6378-1 | usable 0.8 + hang -> connected + reserve-small, 0.8 | yes | 84.1 -> 87.6 + | 32 -> 12 + | 49 -> 75 - | 82.0 -> 87.5 + | 18 -> 28 - | 86 -> 100 + | 50 -> 50 = | 3.7 -> 3.1 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 5 / 2 |
| car | 5891-1 | usable 0.8 + hang -> connected + reserve-small, 0.8 | yes | 87.2 -> 92.3 + | 55 -> 47 + | 22 -> 31 - | 85.4 -> 91.0 + | 20 -> 15 + | 85 -> 100 + | 50 -> 50 = | 13.9 -> 18.1 - | 0 / 0 -> 0 / 0 | 0 -> 0 | 5 / 2 |
| car | 4956-1 | usable 0.8 + hang -> connected + reserve-small, 0.8 | yes | 81.4 -> 91.1 + | 43 -> 19 + | 260 -> 59 + | 79.5 -> 90.7 + | 93 -> 26 + | 81 -> 100 + | 50 -> 48 - | 29.9 -> 25.2 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 1 |
| chair (cut target, pre-reconnect) | 6378-1 | usable 0.7 + hang -> connected + reserve-small, 0.7 | yes | 87.3 -> 3.7 - | 16 -> 1 + | 36 -> 943 - | 84.6 -> 4.5 - | 36 -> 628 - | 27 -> 36 + | 50 -> 50 = | 6.4 -> 2.2 + | 0 / 0 -> 0 / 0 | 0 -> 50 | 3 / 4 |
| chair | 5891-1 | usable 0.7 + hang -> connected + reserve-small, 0.7 | yes | 94.0 -> 98.5 + | 12 -> 9 + | 36 -> 13 + | 92.4 -> 98.1 + | 36 -> 13 + | 43 -> 98 + | 49 -> 50 + | 38.2 -> 16.8 + | 0 / 0 -> 0 / 0 | 0 -> 3 | 8 / 0 |
| chair | 4956-1 | usable 0.7 + hang -> connected + reserve-small, 0.7 | yes | 85.2 -> 94.0 + | 37 -> 26 + | 85 -> 28 + | 82.8 -> 92.6 + | 85 -> 28 + | 59 -> 90 + | 49 -> 41 - | 60.7 -> 26.4 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 1 |
| table | 6378-1 | usable 0.7 + hang -> connected + reserve-small, 0.7 | yes | 94.0 -> 99.4 + | 24 -> 7 + | 8 -> 1 + | 91.7 -> 99.1 + | 8 -> 1 + | 93 -> 100 + | 49 -> 50 + | 5.8 -> 3.9 + | 0 / 0 -> 1 / 1 | 0 -> 2 | 8 / 0 |
| table | 5891-1 | usable 0.7 + hang -> connected + reserve-small, 0.7 | yes | 85.8 -> 94.4 + | 39 -> 23 + | 108 -> 40 + | 79.9 -> 94.5 + | 108 -> 21 + | 50 -> 100 + | 49 -> 50 + | 27.4 -> 20.8 + | 0 / 0 -> 0 / 0 | 0 -> 3 | 8 / 0 |
| table | 4956-1 | usable 0.7 + hang -> connected + reserve-small, 0.7 | yes | 87.3 -> 96.1 + | 16 -> 16 = | 138 -> 57 + | 84.0 -> 93.4 + | 97 -> 51 + | 90 -> 100 + | 48 -> 40 - | 56.4 -> 30.3 + | 0 / 0 -> 0 / 0 | 0 -> 2 | 6 / 1 |
| car | 6378-1 | usable 0.7 + hang -> connected + reserve-small, 0.7 | yes | 86.4 -> 95.5 + | 29 -> 15 + | 37 -> 11 + | 86.7 -> 94.1 + | 21 -> 5 + | 89 -> 98 + | 50 -> 50 = | 3.6 -> 3.2 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 0 |
| car | 5891-1 | usable 0.7 + hang -> connected + reserve-small, 0.7 | yes | 89.3 -> 97.0 + | 32 -> 19 + | 49 -> 11 + | 87.9 -> 96.0 + | 31 -> 5 + | 89 -> 100 + | 50 -> 50 = | 15.5 -> 15.7 - | 0 / 0 -> 0 / 0 | 0 -> 0 | 6 / 1 |
| car | 4956-1 | usable 0.7 + hang -> connected + reserve-small, 0.7 | yes | 80.5 -> 87.7 + | 47 -> 23 + | 159 -> 204 - | 74.8 -> 86.8 + | 96 -> 42 + | 77 -> 100 + | 50 -> 49 - | 38.6 -> 28.1 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 6 / 2 |
| chair (cut target, pre-reconnect) | 6378-1 | usable 0.6 + hang -> connected + reserve-small, 0.6 | yes | 96.5 -> 95.4 - | 8 -> 11 - | 12 -> 12 = | 95.9 -> 94.6 - | 12 -> 12 = | 66 -> 59 - | 32 -> 37 + | 9.2 -> 3.1 + | 0 / 0 -> 0 / 0 | 11 -> 31 | 2 / 4 |
| chair | 5891-1 | usable 0.6 + hang -> connected + reserve-small, 0.6 | yes | 94.1 -> 99.2 + | 36 -> 5 + | 12 -> 6 + | 93.0 -> 99.0 + | 12 -> 6 + | 86 -> 100 + | 50 -> 50 = | 29.2 -> 14.2 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 0 |
| chair | 4956-1 | usable 0.6 + hang -> connected + reserve-small, 0.6 | yes | 86.9 -> 95.3 + | 46 -> 25 + | 56 -> 20 + | 84.0 -> 94.0 + | 56 -> 20 + | 52 -> 98 + | 47 -> 45 - | 65.8 -> 23.0 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 1 |
| table | 6378-1 | usable 0.6 + hang -> connected + reserve-small, 0.6 | yes | 94.4 -> 97.9 + | 3 -> 3 = | 34 -> 8 + | 92.6 -> 97.2 + | 34 -> 8 + | 78 -> 100 + | 50 -> 50 = | 3.7 -> 2.8 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 6 / 0 |
| table | 5891-1 | usable 0.6 + hang -> connected + reserve-small, 0.6 | yes | 84.6 -> 99.4 + | 22 -> 4 + | 108 -> 3 + | 75.9 -> 99.1 + | 108 -> 3 + | 31 -> 100 + | 48 -> 50 + | 25.7 -> 17.7 + | 0 / 0 -> 1 / 1 | 0 -> 4 | 8 / 0 |
| table | 4956-1 | usable 0.6 + hang -> connected + reserve-small, 0.6 | yes | 84.8 -> 98.8 + | 18 -> 2 + | 164 -> 24 + | 81.8 -> 98.1 + | 164 -> 24 + | 70 -> 100 + | 45 -> 41 - | 52.0 -> 32.9 + | 0 / 0 -> 0 / 0 | 0 -> 2 | 7 / 1 |
| car | 6378-1 | usable 0.6 + hang -> connected + reserve-small, 0.6 | yes | 89.9 -> 96.3 + | 29 -> 6 + | 24 -> 20 + | 89.0 -> 95.3 + | 24 -> 20 + | 90 -> 90 = | 50 -> 50 = | 2.2 -> 2.8 - | 0 / 0 -> 0 / 0 | 0 -> 0 | 5 / 1 |
| car | 5891-1 | usable 0.6 + hang -> connected + reserve-small, 0.6 | yes | 92.6 -> 98.8 + | 32 -> 13 + | 15 -> 4 + | 92.0 -> 99.2 + | 12 -> 3 + | 91 -> 100 + | 50 -> 50 = | 10.9 -> 13.7 - | 0 / 0 -> 1 / 1 | 0 -> 0 | 6 / 1 |
| car | 4956-1 | usable 0.6 + hang -> connected + reserve-small, 0.6 | yes | 85.4 -> 94.5 + | 33 -> 23 + | 47 -> 39 + | 83.9 -> 94.5 + | 34 -> 16 + | 80 -> 99 + | 50 -> 50 = | 27.4 -> 21.0 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 0 |
| chair (cut target, pre-reconnect) | 6378-1 | connected + reserve-small -> connected + reserve-small, 0.9 | no | 88.9 -> 94.3 + | 15 -> 14 + | 96 -> 35 + | 87.0 -> 93.0 + | 96 -> 35 + | 88 -> 61 - | 49 -> 49 = | 4.4 -> 4.7 - | 0 / 0 -> 0 / 0 | 0 -> 0 | 5 / 2 |
| chair | 5891-1 | connected + reserve-small -> connected + reserve-small, 0.9 | no | 93.6 -> 93.1 - | 39 -> 27 + | 18 -> 25 - | 92.8 -> 92.1 - | 13 -> 25 - | 93 -> 100 + | 50 -> 42 - | 29.6 -> 30.8 - | 0 / 0 -> 0 / 0 | 5 -> 0 | 2 / 6 |
| chair | 4956-1 | connected + reserve-small -> connected + reserve-small, 0.9 | no | 86.6 -> 88.6 + | 22 -> 21 + | 244 -> 86 + | 82.1 -> 86.3 + | 228 -> 66 + | 99 -> 100 + | 47 -> 28 - | 39.0 -> 35.5 + | 0 / 0 -> 0 / 0 | 3 -> 0 | 7 / 1 |
| table | 6378-1 | connected + reserve-small -> connected + reserve-small, 0.9 | no | 81.4 -> 81.5 + | 22 -> 22 = | 119 -> 96 + | 84.5 -> 79.8 - | 23 -> 96 - | 100 -> 75 - | 50 -> 49 - | 6.1 -> 6.5 - | 0 / 0 -> 0 / 0 | 7 -> 5 | 2 / 5 |
| table | 5891-1 | connected + reserve-small -> connected + reserve-small, 0.9 | no | 91.9 -> 92.3 + | 55 -> 37 + | 15 -> 31 - | 90.7 -> 90.7 + | 15 -> 20 - | 100 -> 99 - | 48 -> 50 + | 29.0 -> 32.5 - | 0 / 0 -> 0 / 0 | 0 -> 0 | 4 / 4 |
| table | 4956-1 | connected + reserve-small -> connected + reserve-small, 0.9 | no | 84.1 -> 83.0 - | 31 -> 27 + | 307 -> 603 - | 78.3 -> 78.3 + | 254 -> 409 - | 100 -> 97 - | 37 -> 42 + | 48.9 -> 44.9 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 4 / 4 |
| car | 6378-1 | connected + reserve-small -> connected + reserve-small, 0.9 | no | 87.4 -> 89.1 + | 20 -> 13 + | 92 -> 73 + | 86.5 -> 88.8 + | 56 -> 36 + | 97 -> 100 + | 50 -> 50 = | 6.6 -> 4.0 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 0 |
| car | 5891-1 | connected + reserve-small -> connected + reserve-small, 0.9 | no | 92.5 -> 95.8 + | 40 -> 40 = | 53 -> 15 + | 93.1 -> 95.0 + | 14 -> 8 + | 99 -> 100 + | 49 -> 50 + | 24.0 -> 23.7 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 0 |
| car | 4956-1 | connected + reserve-small -> connected + reserve-small, 0.9 | no | 83.4 -> 86.9 + | 34 -> 14 + | 345 -> 160 + | 83.1 -> 88.5 + | 38 -> 37 + | 96 -> 99 + | 46 -> 45 - | 35.9 -> 36.5 - | 0 / 0 -> 0 / 0 | 0 -> 0 | 6 / 2 |
| chair (cut target, pre-reconnect) | 6378-1 | connected + reserve-small, 0.9 -> connected + reserve-small, 0.8 | no | 94.3 -> 94.5 + | 14 -> 10 + | 35 -> 35 = | 93.0 -> 93.4 + | 35 -> 35 = | 61 -> 61 = | 49 -> 50 + | 4.7 -> 3.6 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 5 / 0 |
| chair | 5891-1 | connected + reserve-small, 0.9 -> connected + reserve-small, 0.8 | no | 93.1 -> 98.5 + | 27 -> 13 + | 25 -> 7 + | 92.1 -> 98.0 + | 25 -> 7 + | 100 -> 100 = | 42 -> 48 + | 30.8 -> 17.1 + | 0 / 0 -> 0 / 0 | 0 -> 14 | 7 / 0 |
| chair | 4956-1 | connected + reserve-small, 0.9 -> connected + reserve-small, 0.8 | no | 88.6 -> 89.9 + | 21 -> 28 - | 86 -> 80 + | 86.3 -> 87.6 + | 66 -> 77 - | 100 -> 100 - | 28 -> 42 + | 35.5 -> 22.7 + | 0 / 0 -> 0 / 0 | 0 -> 4 | 5 / 3 |
| table | 6378-1 | connected + reserve-small, 0.9 -> connected + reserve-small, 0.8 | no | 81.5 -> 86.5 + | 22 -> 22 = | 96 -> 76 + | 79.8 -> 82.7 + | 96 -> 76 + | 75 -> 82 + | 49 -> 50 + | 6.5 -> 4.5 + | 0 / 0 -> 0 / 0 | 5 -> 2 | 7 / 0 |
| table | 5891-1 | connected + reserve-small, 0.9 -> connected + reserve-small, 0.8 | no | 92.3 -> 96.0 + | 37 -> 31 + | 31 -> 9 + | 90.7 -> 95.9 + | 20 -> 9 + | 99 -> 100 + | 50 -> 48 - | 32.5 -> 21.8 + | 0 / 0 -> 0 / 0 | 0 -> 2 | 7 / 1 |
| table | 4956-1 | connected + reserve-small, 0.9 -> connected + reserve-small, 0.8 | no | 83.0 -> 86.4 + | 27 -> 7 + | 603 -> 390 + | 78.3 -> 80.1 + | 409 -> 312 + | 97 -> 99 + | 42 -> 38 - | 44.9 -> 34.8 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 1 |
| car | 6378-1 | connected + reserve-small, 0.9 -> connected + reserve-small, 0.8 | no | 89.1 -> 87.6 - | 13 -> 12 + | 73 -> 75 - | 88.8 -> 87.5 - | 36 -> 28 + | 100 -> 100 = | 50 -> 50 = | 4.0 -> 3.1 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 3 / 3 |
| car | 5891-1 | connected + reserve-small, 0.9 -> connected + reserve-small, 0.8 | no | 95.8 -> 92.3 - | 40 -> 47 - | 15 -> 31 - | 95.0 -> 91.0 - | 8 -> 15 - | 100 -> 100 = | 50 -> 50 = | 23.7 -> 18.1 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 1 / 5 |
| car | 4956-1 | connected + reserve-small, 0.9 -> connected + reserve-small, 0.8 | no | 86.9 -> 91.1 + | 14 -> 19 - | 160 -> 59 + | 88.5 -> 90.7 + | 37 -> 26 + | 99 -> 100 + | 45 -> 48 + | 36.5 -> 25.2 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 1 |
| chair (cut target, pre-reconnect) | 6378-1 | connected + reserve-small -> connected + reserve-small, 0.8 | no | 88.9 -> 94.5 + | 15 -> 10 + | 96 -> 35 + | 87.0 -> 93.4 + | 96 -> 35 + | 88 -> 61 - | 49 -> 50 + | 4.4 -> 3.6 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 1 |
| chair | 5891-1 | connected + reserve-small -> connected + reserve-small, 0.8 | no | 93.6 -> 98.5 + | 39 -> 13 + | 18 -> 7 + | 92.8 -> 98.0 + | 13 -> 7 + | 93 -> 100 + | 50 -> 48 - | 29.6 -> 17.1 + | 0 / 0 -> 0 / 0 | 5 -> 14 | 7 / 1 |
| chair | 4956-1 | connected + reserve-small -> connected + reserve-small, 0.8 | no | 86.6 -> 89.9 + | 22 -> 28 - | 244 -> 80 + | 82.1 -> 87.6 + | 228 -> 77 + | 99 -> 100 + | 47 -> 42 - | 39.0 -> 22.7 + | 0 / 0 -> 0 / 0 | 3 -> 4 | 6 / 2 |
| table | 6378-1 | connected + reserve-small -> connected + reserve-small, 0.8 | no | 81.4 -> 86.5 + | 22 -> 22 = | 119 -> 76 + | 84.5 -> 82.7 - | 23 -> 76 - | 100 -> 82 - | 50 -> 50 = | 6.1 -> 4.5 + | 0 / 0 -> 0 / 0 | 7 -> 2 | 3 / 3 |
| table | 5891-1 | connected + reserve-small -> connected + reserve-small, 0.8 | no | 91.9 -> 96.0 + | 55 -> 31 + | 15 -> 9 + | 90.7 -> 95.9 + | 15 -> 9 + | 100 -> 100 = | 48 -> 48 = | 29.0 -> 21.8 + | 0 / 0 -> 0 / 0 | 0 -> 2 | 6 / 0 |
| table | 4956-1 | connected + reserve-small -> connected + reserve-small, 0.8 | no | 84.1 -> 86.4 + | 31 -> 7 + | 307 -> 390 - | 78.3 -> 80.1 + | 254 -> 312 - | 100 -> 99 - | 37 -> 38 + | 48.9 -> 34.8 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 5 / 3 |
| car | 6378-1 | connected + reserve-small -> connected + reserve-small, 0.8 | no | 87.4 -> 87.6 + | 20 -> 12 + | 92 -> 75 + | 86.5 -> 87.5 + | 56 -> 28 + | 97 -> 100 + | 50 -> 50 = | 6.6 -> 3.1 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 7 / 0 |
| car | 5891-1 | connected + reserve-small -> connected + reserve-small, 0.8 | no | 92.5 -> 92.3 - | 40 -> 47 - | 53 -> 31 + | 93.1 -> 91.0 - | 14 -> 15 - | 99 -> 100 + | 49 -> 50 + | 24.0 -> 18.1 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 4 / 4 |
| car | 4956-1 | connected + reserve-small -> connected + reserve-small, 0.8 | no | 83.4 -> 91.1 + | 34 -> 19 + | 345 -> 59 + | 83.1 -> 90.7 + | 38 -> 26 + | 96 -> 100 + | 46 -> 48 + | 35.9 -> 25.2 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 8 / 0 |
| chair (cut target, pre-reconnect) | 6378-1 | connected + reserve-small, 0.8 -> connected + reserve-small, 0.7 | no | 94.5 -> 3.7 - | 10 -> 1 + | 35 -> 943 - | 93.4 -> 4.5 - | 35 -> 628 - | 61 -> 36 - | 50 -> 50 = | 3.6 -> 2.2 + | 0 / 0 -> 0 / 0 | 0 -> 50 | 2 / 5 |
| chair | 5891-1 | connected + reserve-small, 0.8 -> connected + reserve-small, 0.7 | no | 98.5 -> 98.5 + | 13 -> 9 + | 7 -> 13 - | 98.0 -> 98.1 + | 7 -> 13 - | 100 -> 98 - | 48 -> 50 + | 17.1 -> 16.8 + | 0 / 0 -> 0 / 0 | 14 -> 3 | 5 / 3 |
| chair | 4956-1 | connected + reserve-small, 0.8 -> connected + reserve-small, 0.7 | no | 89.9 -> 94.0 + | 28 -> 26 + | 80 -> 28 + | 87.6 -> 92.6 + | 77 -> 28 + | 100 -> 90 - | 42 -> 41 - | 22.7 -> 26.4 - | 0 / 0 -> 0 / 0 | 4 -> 0 | 5 / 3 |
| table | 6378-1 | connected + reserve-small, 0.8 -> connected + reserve-small, 0.7 | no | 86.5 -> 99.4 + | 22 -> 7 + | 76 -> 1 + | 82.7 -> 99.1 + | 76 -> 1 + | 82 -> 100 + | 50 -> 50 = | 4.5 -> 3.9 + | 0 / 0 -> 1 / 1 | 2 -> 2 | 7 / 0 |
| table | 5891-1 | connected + reserve-small, 0.8 -> connected + reserve-small, 0.7 | no | 96.0 -> 94.4 - | 31 -> 23 + | 9 -> 40 - | 95.9 -> 94.5 - | 9 -> 21 - | 100 -> 100 = | 48 -> 50 + | 21.8 -> 20.8 + | 0 / 0 -> 0 / 0 | 2 -> 3 | 3 / 4 |
| table | 4956-1 | connected + reserve-small, 0.8 -> connected + reserve-small, 0.7 | no | 86.4 -> 96.1 + | 7 -> 16 - | 390 -> 57 + | 80.1 -> 93.4 + | 312 -> 51 + | 99 -> 100 + | 38 -> 40 + | 34.8 -> 30.3 + | 0 / 0 -> 0 / 0 | 0 -> 2 | 7 / 1 |
| car | 6378-1 | connected + reserve-small, 0.8 -> connected + reserve-small, 0.7 | no | 87.6 -> 95.5 + | 12 -> 15 - | 75 -> 11 + | 87.5 -> 94.1 + | 28 -> 5 + | 100 -> 98 - | 50 -> 50 = | 3.1 -> 3.2 - | 0 / 0 -> 0 / 0 | 0 -> 0 | 4 / 3 |
| car | 5891-1 | connected + reserve-small, 0.8 -> connected + reserve-small, 0.7 | no | 92.3 -> 97.0 + | 47 -> 19 + | 31 -> 11 + | 91.0 -> 96.0 + | 15 -> 5 + | 100 -> 100 = | 50 -> 50 = | 18.1 -> 15.7 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 6 / 0 |
| car | 4956-1 | connected + reserve-small, 0.8 -> connected + reserve-small, 0.7 | no | 91.1 -> 87.7 - | 19 -> 23 - | 59 -> 204 - | 90.7 -> 86.8 - | 26 -> 42 - | 100 -> 100 - | 48 -> 49 + | 25.2 -> 28.1 - | 0 / 0 -> 0 / 0 | 0 -> 0 | 1 / 7 |
| chair (cut target, pre-reconnect) | 6378-1 | connected + reserve-small, 0.7 -> connected + reserve-small, 0.6 | no | 3.7 -> 95.4 + | 1 -> 11 - | 943 -> 12 + | 4.5 -> 94.6 + | 628 -> 12 + | 36 -> 59 + | 50 -> 37 - | 2.2 -> 3.1 - | 0 / 0 -> 0 / 0 | 50 -> 31 | 5 / 3 |
| chair | 5891-1 | connected + reserve-small, 0.7 -> connected + reserve-small, 0.6 | no | 98.5 -> 99.2 + | 9 -> 5 + | 13 -> 6 + | 98.1 -> 99.0 + | 13 -> 6 + | 98 -> 100 + | 50 -> 50 = | 16.8 -> 14.2 + | 0 / 0 -> 0 / 0 | 3 -> 0 | 7 / 0 |
| chair | 4956-1 | connected + reserve-small, 0.7 -> connected + reserve-small, 0.6 | no | 94.0 -> 95.3 + | 26 -> 25 + | 28 -> 20 + | 92.6 -> 94.0 + | 28 -> 20 + | 90 -> 98 + | 41 -> 45 + | 26.4 -> 23.0 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 8 / 0 |
| table | 6378-1 | connected + reserve-small, 0.7 -> connected + reserve-small, 0.6 | no | 99.4 -> 97.9 - | 7 -> 3 + | 1 -> 8 - | 99.1 -> 97.2 - | 1 -> 8 - | 100 -> 100 = | 50 -> 50 = | 3.9 -> 2.8 + | 1 / 1 -> 0 / 0 | 2 -> 0 | 2 / 4 |
| table | 5891-1 | connected + reserve-small, 0.7 -> connected + reserve-small, 0.6 | no | 94.4 -> 99.4 + | 23 -> 4 + | 40 -> 3 + | 94.5 -> 99.1 + | 21 -> 3 + | 100 -> 100 = | 50 -> 50 = | 20.8 -> 17.7 + | 0 / 0 -> 1 / 1 | 3 -> 4 | 6 / 0 |
| table | 4956-1 | connected + reserve-small, 0.7 -> connected + reserve-small, 0.6 | no | 96.1 -> 98.8 + | 16 -> 2 + | 57 -> 24 + | 93.4 -> 98.1 + | 51 -> 24 + | 100 -> 100 = | 40 -> 41 + | 30.3 -> 32.9 - | 0 / 0 -> 0 / 0 | 2 -> 2 | 6 / 1 |
| car | 6378-1 | connected + reserve-small, 0.7 -> connected + reserve-small, 0.6 | no | 95.5 -> 96.3 + | 15 -> 6 + | 11 -> 20 - | 94.1 -> 95.3 + | 5 -> 20 - | 98 -> 90 - | 50 -> 50 = | 3.2 -> 2.8 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 4 / 3 |
| car | 5891-1 | connected + reserve-small, 0.7 -> connected + reserve-small, 0.6 | no | 97.0 -> 98.8 + | 19 -> 13 + | 11 -> 4 + | 96.0 -> 99.2 + | 5 -> 3 + | 100 -> 100 = | 50 -> 50 = | 15.7 -> 13.7 + | 0 / 0 -> 1 / 1 | 0 -> 0 | 6 / 0 |
| car | 4956-1 | connected + reserve-small, 0.7 -> connected + reserve-small, 0.6 | no | 87.7 -> 94.5 + | 23 -> 23 = | 204 -> 39 + | 86.8 -> 94.5 + | 42 -> 16 + | 100 -> 99 - | 49 -> 50 + | 28.1 -> 21.0 + | 0 / 0 -> 0 / 0 | 0 -> 0 | 6 / 1 |

## Selected builds across sizes

- **`m12b_size_sheet.png`:** the creserve family's selected builds, scaled to 40%. Pairs are rows; slack 1.0 → 0.6 runs
  across the columns. The label above each build gives fill, surface, largest hole, target cells, and how many valid
  candidates are complete.
- **`m12b_size_sheet_usable.png`:** the same for the default.

The complete builds look like their objects: the 6378-1 table at 0.7 (99.4 / 1 / 99.1), and the 5891-1 table and car at
0.6. Their colours are still a mottle (`results/m12c_colour_measure.md`).

**Complete candidates** are in `out/m12b_complete/complete_candidates/`, counted under either bar. Each has an .ldr with one
step per layer, a preview and a missing map. 20 come from these arms:
- table_6378-1_creserve70_seed11;
- table_6378-1_creserve60 seeds 1, 5, 6, 8, 17, 18, 24, 27, 32, 39;
- table_5891-1_creserve60 seeds 10, 15, 18, 48;
- car_5891-1_creserve60 seeds 22, 28, 44;
- car_6378-1_creserve60_seed22 (surface bar only).

The folder also holds the creserve80 chair: seed 1, and seed 43, its old pick, both from before.

## Runs

- **Code:** the 45 runs ran from the m12c-size worktree at 007e6dd (main 75696d2 plus the arms).
  - The builder is unchanged, so the cached arms of the other slacks are directly comparable: same seeds, same targets
    per slack.
  - The report ran at m12c-size after merging main 044b8f6 (the bar-aware size report), plus the stalled-run marking.
  - The reconnect fix in 044b8f6 changes only the cut 6378-1 chair targets. The report reads each run's own mask from its
    cache key, so no row changed.
- **Timing:** 17:01–20:18 on 5 workers, exit code 0, no crash, so no resume was needed.

  | arm | wall time (min) | generation CPU (h) |
  |---|---:|---:|
  | creserve90 | 45 | 3.1 |
  | creserve70 | 29 | 2.1 |
  | creserve60 | 27 | 1.8 |
  | usable70 | 51 | 3.5 |
  | usable60 | 45 | 3.1 |

  Another session's pytest ran briefly at the start.
- **Target cells per slack:** logged by the sweep (`out/m12b_complete/size_sweep.log`); they are the target cells column
  above.
- **Outputs:**
  - `out/m12b_complete/size.md`;
  - `size.json`, copied to `results/m12b_size.json`;
  - `size_sheet_creserve.png` and `size_sheet_usable.png`;
  - `out/m12c_size_select.json`, the re-rank.

## Reproduce

```
python -m brickwfc.experiments.complete --out out/m12b_complete --steps sweep \
    --arms creserve90 creserve70 creserve60 usable70 usable60 --workers 5 --n 50
python -m brickwfc.experiments.complete --out out/m12b_complete --steps size-report
python -m brickwfc.experiments.select --arms creserve90 creserve70 creserve60 usable70 usable60 --out out/m12c_size_select
```

The other slacks' arms (creserve, creserve80, usable, usable90, usable80) must already be in `out/m12b_complete/sweep/`
(see `m12b_complete.md` and `m12b_connected.md`).
