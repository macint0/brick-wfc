# M12b — connected growth on the completeness sweep

The connected growth order (`--order connected`, merged 0863884) on ee's 9 sweep pairs (sets 6378-1, 5891-1, 4956-1 ×
chair, table, car), next to the default arm at the same slack:

| arm | flags | pairs with |
|---|---|---|
| connected | `--sizing usable --holes --hang --order connected` | default (`usable + hang`) |
| connected90 | the same with `--fill-slack 0.9` | default at 0.9 (`usable 0.9 + hang`) |
| connected80 | the same with `--fill-slack 0.8` | default at 0.8 (`usable 0.8 + hang`) |

"Default" is the pipeline's default with a 3D target since e0933bb: usable sizing with the hanging hole pass, random
order. The tables name it by its sweep arm (`usable + hang`). Where usable sizing does not change the target, the
default arm is ee's hang arm (`= hang`).

Each connected arm runs on the same target and the same seeds (0–49) as the default at its slack. Every run uses 50
candidates on 5 workers, with the pipeline's other defaults: supports, max clutch 1111, balance, 10 connect rounds,
open tops. The same runs, with ee's other arms, are in `m12b_complete.md`.

Definitions:
- **Complete:** fill ≥ 97%, no hole over 4 cells, surface ≥ 98% (Mac's bar).
- **Stalled:** a seed ending under 50% fill.
- **Tips filled:** the share of the target's tip cells filled, where tip cells are the far ends of its lowest third:
  casters, feet, wheel corners.

Targets are at 49d5739, after ee's two fixes to the thin-aware scale: the post is no longer cut, and it goes under its
load (§ Runs).

## Result

**Adoption.** No arm makes the selected build complete on any pair, so none meets the adoption rule.
- Not one of the 2,700 candidates across the 54 cells (27 default, 27 connected) is complete.
- The best selected build per pair reaches 84–96% fill and 84–95% surface, with a largest hole of 14–305 cells.
  - It is connected80's on 8 of the 9 pairs, and default 0.8's on the 5891-1 table.
  - The closest to complete is connected80 on the 5891-1 chair: fill 96.4%, largest hole 14, surface 95.5%.
- Completeness is still bounded by the inventory and by what fits, as `m12b_complete.md` found for the other arms.

**Connected vs default, selected builds (27 cells).** Connected is more complete on most cells, without losing
validity:

| metric | connected better | worse | equal |
|---|---:|---:|---:|
| fill | 23 | 3 | 1 |
| surface | 23 | 4 | 0 |
| tips filled | 26 | 1 | 0 |
| holes | 18 | 7 | 2 |
| largest hole | 17 | 9 | 1 |

- **Fill gains** reach +8.4 points (5891-1 chair at 0.8) and +8.9 (4956-1 chair at 0.9).
- **Tips filled:** casters, feet and wheel corners go from 40–94% to 70–100%. Under the default, a chair's base is
  where the build stays incomplete; connected growth reaches the feet along the arms and hangs them down.
- **Valid candidates:** 1263 connected vs 1246 default out of 1350.
  - Chairs: 411 vs 408. Tables: 414 vs 393. Cars: 438 vs 445.
- **Fill losses**, 3 cells, none a stall (§ The two losses):
  - 6378-1 chair at 1.0: 88.6 → 86.3.
  - 4956-1 table at 1.0: 81.5 → 77.1.
  - 5891-1 table at 0.8: 93.3 → 92.5.
  - At 0.9, the first two pairs' connected builds win (+3.8 and +6.0 fill).
- **Largest hole, cars:** worse on 6 of the 9 car cells (e.g. 5891-1 at 0.9: 34 → 74), while their fill and surface
  are better on all but the 6378-1 car at 1.0 (fill equal). Connected cars leave one larger gap rather than several
  small ones.
- **Time:** s / candidate lower on chairs and tables, higher on most cars.
  - 5891-1 chair: 75 → 25 s. 4956-1 chair: 81 → 38 s.
  - 5891-1 car at 0.9: 21 → 35 s.
- **Clutch** of the selected builds stays within the 1111 cap by construction. It is higher under connected on many
  cells: 662 vs 64 on the 5891-1 chair at 1.0. Connected spreads hung arms and feet off one structure.

**Stalls do not cost a selected build.** cf's criterion was whether a selected connected build loses to its default
counterpart because of a stall. No such cell exists, so multi-seed growth is not the next task by that rule.
- **Where stalls happen:** 24 of 450 chair candidates and 33 of 450 table candidates; no car stalls. Under the default,
  only 1 of 1350 candidates stalls (5891-1 table at 0.8).
- **What they cost:** the mean fill over valid builds.
  - 5891-1 chair at 1.0: 83.6 default → 78.6 connected, against a selected build of 84.9 → 92.3.
  - 6378-1 table at 1.0: 69.9 → 65.5.

**Verdict** (cf, 2026-10-10): connected stays a flag, not the default. At the default slack it makes the selected
build more complete on 7 of 9 pairs and less on two (§ The two losses). At 0.8 it wins 8 of 9, and it gives the
closest build to the bar so far: the 5891-1 chair at 96.4% fill, largest hole 14, surface 95.5%. It is the strongest
single lever on chairs.

## The two losses

**4956-1 table at 1.0** (fill 81.5 → 77.1, largest hole 253 → 873). This table is a pedestal table:
- a base with 4 feet;
- a central post, 2 × 3 cells at layer 54;
- a round top, 8 layers thick (layers 55–62, 350–400 cells per layer).

The selected connected build (seed 17) has all 4 feet (95–98% of their tip cells) and the whole post. It reaches the
top's highest layer, so the top was crossed. What it misses is the top's underside: layer 55, the top's lowest layer,
is 27% filled, and it overhangs the post on every side. Above that, each layer of the top is 74–77% filled, missing
its rim.

The underside joins the rim's holes into one face-connected hole of 873 cells, from layer 53 to 62. The default's
selected build (seed 36) fills most of the underside (73%) but leaves its two highest layers open: a hole of 253 cells at layers
58–62. It also stands on 3 feet: one foot's tips are 36% filled. So the two builds miss different things, and the
connected one misses more cells.

It is not a stall: the build is at 77% fill, and a stall is a seed under 50%. Over all valid builds connected is
ahead on this pair:
- mean fill 77.5% vs 75.0%;
- every foot filled (≥ 50% of its tips) in 32 of 39 valid builds, against 9 of 39 under the default.

**6378-1 chair at 1.0** (tips 62 → 38%). The selected builds differ by the judge's choice, which does not see tips.
The chair has 5 casters (tip regions):

| | selected build: casters with ≥ 50% of their tips filled | mean over valid builds |
|---|---|---|
| default | 3 of 5 | 1.9 of 5 |
| connected | 2 of 5 | 3.2 of 5 |

Over the valid builds, tips filled average 69% under connected against 34% under the default.

The selected connected build (seed 21) misses its 3 casters for cause 1 above. Rebuilt with the grown state captured,
it has free target cells on the arms toward them on layers 0–7, but no placement fits on any of those layers with any
catalog part. Growth crossed the hub to one more caster, and the stair-stepped arms to the other three stayed
unreachable.

Under the default, a caster is built as its own stack from the ground. The connect repair keeps the largest piece and
refills, and the hanging hole pass joins what it can. The selected default build happens to keep three casters.

## Per pair

Per arm, the selected build and the mean over valid builds (sel / mean). The stalled column lists the layers the
stalled builds top out at (layer: count).

| object | set | arm | target cells | object cells | valid | complete | fill % (sel / mean) | holes (sel / mean) | largest hole (sel / mean) | surface % (sel / mean) | parts (sel) | used % (sel) | s / candidate | tips filled % (sel / mean) | clutch (sel) | stalled (top layers) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| chair | 6378-1 | usable + hang | 1326 | 1314 | 49/50 | 0 | 88.6 / 84.4 | 33 / 28.7 | 34 / 49 | 87.0 / 82.4 | 180 | 88 | 10.3 | 62 / 34 | 6 | 0 |
| chair | 6378-1 | connected + usable + hang | 1326 | 1314 | 49/50 | 0 | 86.3 / 86.7 | 32 / 24.7 | 33 / 61 | 84.0 / 84.5 | 182 | 89 | 4.0 | 38 / 69 | 182 | 0 |
| chair | 6378-1 | usable 0.9 + hang | 1204 | 1192 | 50/50 | 0 | 88.1 / 84.9 | 24 / 23.7 | 38 / 53 | 85.7 / 82.0 | 166 | 81 | 6.0 | 49 / 29 | 85 | 0 |
| chair | 6378-1 | connected + usable 0.9 + hang | 1204 | 1192 | 49/50 | 0 | 91.9 / 87.8 | 13 / 22.3 | 35 / 38 | 90.4 / 85.4 | 179 | 88 | 5.6 | 70 / 56 | 50 | 0 |
| chair | 6378-1 | usable 0.8 + hang | 1138 | 1126 | 50/50 | 0 | 90.6 / 85.7 | 17 / 19.8 | 35 / 52 | 89.1 / 83.4 | 163 | 80 | 11.8 | 42 / 31 | 176 | 0 |
| chair | 6378-1 | connected + usable 0.8 + hang | 1138 | 1126 | 50/50 | 0 | 92.7 / 88.0 | 18 / 20.1 | 35 / 38 | 91.4 / 86.0 | 172 | 84 | 4.2 | 75 / 56 | 160 | 0 |
| chair | 5891-1 | usable + hang (= hang) | 2784 | 2772 | 50/50 | 0 | 84.9 / 83.6 | 62 / 54.6 | 172 / 142 | 81.5 / 79.7 | 335 | 73 | 75.2 | 45 / 33 | 64 | 0 |
| chair | 5891-1 | connected + usable + hang | 2784 | 2772 | 49/50 | 0 | 92.3 / 78.6 | 41 / 44.6 | 38 / 382 | 90.9 / 77.0 | 342 | 74 | 25.3 | 82 / 80 | 662 | 6 (9: 6) |
| chair | 5891-1 | usable 0.9 + hang | 2621 | 2609 | 47/50 | 0 | 87.5 / 81.1 | 37 / 47.2 | 76 / 133 | 84.5 / 77.6 | 316 | 69 | 84.3 | 41 / 38 | 893 | 0 |
| chair | 5891-1 | connected + usable 0.9 + hang | 2621 | 2609 | 45/50 | 0 | 92.6 / 87.0 | 38 / 46.9 | 32 / 112 | 90.8 / 85.2 | 335 | 73 | 25.9 | 83 / 80 | 749 | 1 (9) |
| chair | 5891-1 | usable 0.8 + hang | 2323 | 2311 | 44/50 | 0 | 88.0 / 81.9 | 43 / 46.4 | 49 / 95 | 85.1 / 78.6 | 305 | 66 | 50.9 | 73 / 41 | 361 | 0 |
| chair | 5891-1 | connected + usable 0.8 + hang | 2323 | 2311 | 44/50 | 0 | 96.4 / 77.3 | 24 / 34.8 | 14 / 391 | 95.5 / 75.9 | 306 | 67 | 29.3 | 100 / 76 | 601 | 7 (6, 9: 6) |
| chair | 4956-1 | usable + hang (= hang) | 4334 | 4318 | 41/50 | 0 | 77.7 / 74.2 | 43 / 40.9 | 363 / 367 | 72.6 / 69.1 | 367 | 64 | 81.3 | 40 / 40 | 363 | 0 |
| chair | 4956-1 | connected + usable + hang | 4334 | 4318 | 47/50 | 0 | 83.9 / 73.7 | 33 / 32.7 | 293 / 749 | 80.2 / 70.2 | 392 | 68 | 38.3 | 100 / 86 | 166 | 5 (11: 5) |
| chair | 4956-1 | usable 0.9 + hang | 3892 | 3880 | 39/50 | 0 | 80.8 / 76.4 | 50 / 42.3 | 302 / 281 | 77.9 / 71.6 | 374 | 65 | 74.1 | 55 / 38 | 226 | 0 |
| chair | 4956-1 | connected + usable 0.9 + hang | 3892 | 3880 | 38/50 | 0 | 89.7 / 84.7 | 35 / 38.6 | 67 / 170 | 88.6 / 82.7 | 376 | 66 | 32.6 | 98 / 91 | 666 | 0 |
| chair | 4956-1 | usable 0.8 + hang | 3480 | 3468 | 38/50 | 0 | 83.0 / 76.2 | 53 / 38.6 | 122 / 271 | 78.7 / 72.0 | 336 | 59 | 66.8 | 45 / 42 | 530 | 0 |
| chair | 4956-1 | connected + usable 0.8 + hang | 3480 | 3468 | 40/50 | 0 | 91.2 / 77.4 | 39 / 36.3 | 69 / 485 | 89.4 / 75.3 | 366 | 64 | 37.4 | 95 / 85 | 454 | 5 (10: 3, 20: 2) |
| table | 6378-1 | usable + hang (= hang) | 1748 | 1748 | 48/50 | 0 | 78.5 / 69.9 | 16 / 28.5 | 96 / 134 | 76.4 / 62.2 | 196 | 96 | 9.0 | 70 / 35 | 48 | 0 |
| table | 6378-1 | connected + usable + hang | 1748 | 1748 | 49/50 | 0 | 81.4 / 65.5 | 16 / 17.4 | 131 / 406 | 83.7 / 67.3 | 200 | 98 | 5.9 | 99 / 76 | 66 | 11 (8, 28, 32, 34: 2, 35, 38: 2, 39: 2, 40) |
| table | 6378-1 | usable 0.9 + hang | 1576 | 1576 | 50/50 | 0 | 80.5 / 74.0 | 22 / 30.2 | 92 / 112 | 77.7 / 67.4 | 183 | 90 | 8.0 | 63 / 39 | 45 | 0 |
| table | 6378-1 | connected + usable 0.9 + hang | 1576 | 1576 | 47/50 | 0 | 83.7 / 70.7 | 18 / 19.9 | 89 / 273 | 85.0 / 71.5 | 190 | 93 | 5.4 | 100 / 78 | 486 | 8 (25, 27, 29, 31, 35, 38: 3) |
| table | 6378-1 | usable 0.8 + hang | 1344 | 1344 | 49/50 | 0 | 83.9 / 77.3 | 36 / 26.9 | 92 / 93 | 79.1 / 69.3 | 173 | 85 | 6.2 | 69 / 36 | 44 | 0 |
| table | 6378-1 | connected + usable 0.8 + hang | 1344 | 1344 | 50/50 | 0 | 88.0 / 79.0 | 22 / 21.7 | 82 / 135 | 88.4 / 77.4 | 186 | 91 | 7.7 | 100 / 78 | 105 | 3 (7, 29: 2) |
| table | 5891-1 | usable + hang (= hang) | 2880 | 2880 | 39/50 | 0 | 87.1 / 79.3 | 40 / 47.5 | 108 / 192 | 81.3 / 71.1 | 350 | 76 | 44.7 | 67 / 45 | 489 | 0 |
| table | 5891-1 | connected + usable + hang | 2880 | 2880 | 46/50 | 0 | 88.9 / 81.3 | 56 / 44.2 | 94 / 273 | 89.1 / 81.1 | 345 | 75 | 33.6 | 100 / 89 | 103 | 4 (38, 42, 43, 44) |
| table | 5891-1 | usable 0.9 + hang | 2570 | 2570 | 42/50 | 0 | 88.5 / 79.4 | 43 / 38.1 | 114 / 155 | 82.7 / 71.7 | 306 | 67 | 38.4 | 51 / 45 | 121 | 0 |
| table | 5891-1 | connected + usable 0.9 + hang | 2570 | 2570 | 47/50 | 0 | 91.0 / 76.4 | 43 / 25.4 | 42 / 414 | 89.9 / 76.2 | 330 | 72 | 28.6 | 100 / 89 | 339 | 5 (38, 42, 43, 44, 47) |
| table | 5891-1 | usable 0.8 + hang | 2328 | 2328 | 43/50 | 0 | 93.3 / 81.6 | 36 / 38.2 | 29 / 163 | 91.1 / 75.3 | 320 | 70 | 31.6 | 94 / 54 | 962 | 1 (32) |
| table | 5891-1 | connected + usable 0.8 + hang | 2328 | 2328 | 49/50 | 0 | 92.5 / 86.4 | 43 / 39.1 | 15 / 142 | 91.9 / 85.2 | 302 | 66 | 37.8 | 100 / 89 | 71 | 2 (9: 2) |
| table | 4956-1 | usable + hang (= hang) | 4414 | 4414 | 39/50 | 0 | 81.5 / 75.0 | 41 / 31.3 | 253 / 671 | 78.4 / 67.5 | 412 | 72 | 61.4 | 79 / 69 | 432 | 0 |
| table | 4956-1 | connected + usable + hang | 4414 | 4414 | 39/50 | 0 | 77.1 / 77.5 | 36 / 33.8 | 873 / 680 | 70.2 / 71.1 | 420 | 73 | 49.7 | 97 / 94 | 589 | 0 |
| table | 4956-1 | usable 0.9 + hang | 4008 | 4008 | 42/50 | 0 | 78.4 / 76.6 | 20 / 28.3 | 689 / 503 | 76.9 / 69.6 | 386 | 67 | 55.0 | 93 / 70 | 462 | 0 |
| table | 4956-1 | connected + usable 0.9 + hang | 4008 | 4008 | 45/50 | 0 | 84.4 / 80.5 | 42 / 35.3 | 147 / 458 | 76.8 / 74.7 | 408 | 71 | 41.1 | 98 / 96 | 142 | 0 |
| table | 4956-1 | usable 0.8 + hang | 3627 | 3627 | 41/50 | 0 | 84.9 / 77.8 | 29 / 30.0 | 351 / 425 | 85.4 / 71.6 | 387 | 68 | 49.5 | 94 / 68 | 140 | 0 |
| table | 4956-1 | connected + usable 0.8 + hang | 3627 | 3627 | 42/50 | 0 | 86.5 / 79.1 | 39 / 21.0 | 82 / 507 | 83.9 / 74.4 | 363 | 63 | 43.2 | 100 / 97 | 82 | 0 |
| car | 6378-1 | usable + hang (= hang) | 1721 | 1689 | 50/50 | 0 | 75.8 / 73.3 | 24 / 26.5 | 194 / 189 | 74.0 / 70.0 | 197 | 97 | 4.5 | 79 / 68 | 33 | 0 |
| car | 6378-1 | connected + usable + hang | 1721 | 1689 | 50/50 | 0 | 75.8 / 75.3 | 21 / 25.6 | 174 / 218 | 75.5 / 74.4 | 197 | 97 | 5.6 | 97 / 93 | 432 | 0 |
| car | 6378-1 | usable 0.9 + hang | 1494 | 1470 | 50/50 | 0 | 81.6 / 76.9 | 33 / 27.7 | 44 / 121 | 75.4 / 74.9 | 187 | 92 | 4.1 | 70 / 71 | 10 | 0 |
| car | 6378-1 | connected + usable 0.9 + hang | 1494 | 1470 | 50/50 | 0 | 85.3 / 81.7 | 38 / 25.8 | 59 / 119 | 86.2 / 82.4 | 191 | 94 | 6.7 | 98 / 96 | 12 | 0 |
| car | 6378-1 | usable 0.8 + hang | 1380 | 1356 | 50/50 | 0 | 84.1 / 78.3 | 32 / 28.2 | 49 / 96 | 82.0 / 76.5 | 186 | 91 | 3.7 | 86 / 76 | 11 | 0 |
| car | 6378-1 | connected + usable 0.8 + hang | 1380 | 1356 | 50/50 | 0 | 87.0 / 82.7 | 25 / 25.7 | 88 / 92 | 86.9 / 82.6 | 188 | 92 | 3.6 | 97 / 96 | 295 | 0 |
| car | 5891-1 | usable + hang (= hang) | 2807 | 2775 | 50/50 | 0 | 84.8 / 82.2 | 69 / 55.9 | 75 / 129 | 81.4 / 79.0 | 348 | 76 | 16.8 | 81 / 77 | 72 | 0 |
| car | 5891-1 | connected + usable + hang | 2807 | 2775 | 50/50 | 0 | 89.8 / 86.0 | 48 / 52.1 | 107 / 129 | 89.2 / 86.1 | 341 | 74 | 22.1 | 97 / 97 | 216 | 0 |
| car | 5891-1 | usable 0.9 + hang | 2627 | 2595 | 50/50 | 0 | 87.5 / 83.0 | 63 / 55.5 | 34 / 105 | 84.5 / 80.5 | 340 | 74 | 20.8 | 80 / 75 | 72 | 0 |
| car | 5891-1 | connected + usable 0.9 + hang | 2627 | 2595 | 50/50 | 0 | 89.4 / 87.2 | 51 / 52.2 | 74 / 87 | 87.4 / 86.7 | 345 | 75 | 34.8 | 99 / 97 | 79 | 0 |
| car | 5891-1 | usable 0.8 + hang | 2357 | 2325 | 50/50 | 0 | 87.2 / 84.9 | 55 / 51.2 | 22 / 69 | 85.4 / 82.3 | 315 | 68 | 13.9 | 85 / 81 | 138 | 0 |
| car | 5891-1 | connected + usable 0.8 + hang | 2357 | 2325 | 50/50 | 0 | 92.0 / 87.9 | 30 / 48.1 | 42 / 77 | 92.7 / 87.5 | 313 | 68 | 19.9 | 100 / 98 | 622 | 0 |
| car | 4956-1 | usable + hang (= hang) | 4554 | 4474 | 46/50 | 0 | 76.8 / 74.9 | 39 / 33.8 | 527 / 585 | 73.0 / 72.2 | 390 | 68 | 50.9 | 85 / 77 | 403 | 0 |
| car | 4956-1 | connected + usable + hang | 4554 | 4474 | 44/50 | 0 | 82.5 / 79.2 | 35 / 39.2 | 413 / 596 | 84.0 / 79.6 | 406 | 71 | 41.0 | 99 / 94 | 141 | 0 |
| car | 4956-1 | usable 0.9 + hang | 4032 | 3952 | 49/50 | 0 | 78.3 / 76.0 | 38 / 33.7 | 255 / 466 | 72.6 / 73.2 | 375 | 65 | 40.9 | 74 / 78 | 336 | 0 |
| car | 4956-1 | connected + usable 0.9 + hang | 4032 | 3952 | 47/50 | 0 | 82.8 / 79.5 | 36 / 37.0 | 423 / 497 | 85.4 / 80.6 | 370 | 65 | 57.1 | 93 / 95 | 604 | 0 |
| car | 4956-1 | usable 0.8 + hang | 3512 | 3480 | 50/50 | 0 | 81.4 / 78.3 | 43 / 36.6 | 260 / 289 | 79.5 / 73.9 | 356 | 62 | 29.9 | 81 / 73 | 216 | 0 |
| car | 4956-1 | connected + usable 0.8 + hang | 3512 | 3480 | 47/50 | 0 | 84.0 / 83.2 | 34 / 39.6 | 305 / 285 | 83.5 / 81.2 | 354 | 62 | 27.4 | 98 / 94 | 542 | 0 |

Sheets:
- `m12b_connected_sweep_previews.png`: the selected builds, pairs as rows, default and connected at each slack as
  columns.
- `m12b_connected_sweep_missing.png`: their missing maps, with unfilled target cells in red.

## Connected vs default, selected builds

Same target, same seeds. + means connected is better, - means worse. Valid counts candidates out of 50, and
s / candidate is generation CPU time. The last two columns count the stalled seeds (default → connected) and the
metrics where connected is better / worse.

| object | set | base -> arm | fill % | holes | largest hole | surface % | tips filled % | valid | s / candidate | complete (sel) | stalled | better / worse |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| chair | 6378-1 | usable + hang -> connected + usable + hang | 88.6 -> 86.3 - | 33 -> 32 + | 34 -> 33 + | 87.0 -> 84.0 - | 62 -> 38 - | 49 -> 49 = | 10.3 -> 4.0 + | 0 -> 0 | 0 -> 0 | 3 / 3 |
| chair | 5891-1 | usable + hang -> connected + usable + hang | 84.9 -> 92.3 + | 62 -> 41 + | 172 -> 38 + | 81.5 -> 90.9 + | 45 -> 82 + | 50 -> 49 - | 75.2 -> 25.3 + | 0 -> 0 | 0 -> 6 | 6 / 1 |
| chair | 4956-1 | usable + hang -> connected + usable + hang | 77.7 -> 83.9 + | 43 -> 33 + | 363 -> 293 + | 72.6 -> 80.2 + | 40 -> 100 + | 41 -> 47 + | 81.3 -> 38.3 + | 0 -> 0 | 0 -> 5 | 7 / 0 |
| table | 6378-1 | usable + hang -> connected + usable + hang | 78.5 -> 81.4 + | 16 -> 16 = | 96 -> 131 - | 76.4 -> 83.7 + | 70 -> 99 + | 48 -> 49 + | 9.0 -> 5.9 + | 0 -> 0 | 0 -> 11 | 5 / 1 |
| table | 5891-1 | usable + hang -> connected + usable + hang | 87.1 -> 88.9 + | 40 -> 56 - | 108 -> 94 + | 81.3 -> 89.1 + | 67 -> 100 + | 39 -> 46 + | 44.7 -> 33.6 + | 0 -> 0 | 0 -> 4 | 6 / 1 |
| table | 4956-1 | usable + hang -> connected + usable + hang | 81.5 -> 77.1 - | 41 -> 36 + | 253 -> 873 - | 78.4 -> 70.2 - | 79 -> 97 + | 39 -> 39 = | 61.4 -> 49.7 + | 0 -> 0 | 0 -> 0 | 3 / 3 |
| car | 6378-1 | usable + hang -> connected + usable + hang | 75.8 -> 75.8 = | 24 -> 21 + | 194 -> 174 + | 74.0 -> 75.5 + | 79 -> 97 + | 50 -> 50 = | 4.5 -> 5.6 - | 0 -> 0 | 0 -> 0 | 4 / 1 |
| car | 5891-1 | usable + hang -> connected + usable + hang | 84.8 -> 89.8 + | 69 -> 48 + | 75 -> 107 - | 81.4 -> 89.2 + | 81 -> 97 + | 50 -> 50 = | 16.8 -> 22.1 - | 0 -> 0 | 0 -> 0 | 4 / 2 |
| car | 4956-1 | usable + hang -> connected + usable + hang | 76.8 -> 82.5 + | 39 -> 35 + | 527 -> 413 + | 73.0 -> 84.0 + | 85 -> 99 + | 46 -> 44 - | 50.9 -> 41.0 + | 0 -> 0 | 0 -> 0 | 6 / 1 |
| chair | 6378-1 | usable 0.9 + hang -> connected + usable 0.9 + hang | 88.1 -> 91.9 + | 24 -> 13 + | 38 -> 35 + | 85.7 -> 90.4 + | 49 -> 70 + | 50 -> 49 - | 6.0 -> 5.6 + | 0 -> 0 | 0 -> 0 | 6 / 1 |
| chair | 5891-1 | usable 0.9 + hang -> connected + usable 0.9 + hang | 87.5 -> 92.6 + | 37 -> 38 - | 76 -> 32 + | 84.5 -> 90.8 + | 41 -> 83 + | 47 -> 45 - | 84.3 -> 25.9 + | 0 -> 0 | 0 -> 1 | 5 / 2 |
| chair | 4956-1 | usable 0.9 + hang -> connected + usable 0.9 + hang | 80.8 -> 89.7 + | 50 -> 35 + | 302 -> 67 + | 77.9 -> 88.6 + | 55 -> 98 + | 39 -> 38 - | 74.1 -> 32.6 + | 0 -> 0 | 0 -> 0 | 6 / 1 |
| table | 6378-1 | usable 0.9 + hang -> connected + usable 0.9 + hang | 80.5 -> 83.7 + | 22 -> 18 + | 92 -> 89 + | 77.7 -> 85.0 + | 63 -> 100 + | 50 -> 47 - | 8.0 -> 5.4 + | 0 -> 0 | 0 -> 8 | 6 / 1 |
| table | 5891-1 | usable 0.9 + hang -> connected + usable 0.9 + hang | 88.5 -> 91.0 + | 43 -> 43 = | 114 -> 42 + | 82.7 -> 89.9 + | 51 -> 100 + | 42 -> 47 + | 38.4 -> 28.6 + | 0 -> 0 | 0 -> 5 | 6 / 0 |
| table | 4956-1 | usable 0.9 + hang -> connected + usable 0.9 + hang | 78.4 -> 84.4 + | 20 -> 42 - | 689 -> 147 + | 76.9 -> 76.8 - | 93 -> 98 + | 42 -> 45 + | 55.0 -> 41.1 + | 0 -> 0 | 0 -> 0 | 5 / 2 |
| car | 6378-1 | usable 0.9 + hang -> connected + usable 0.9 + hang | 81.6 -> 85.3 + | 33 -> 38 - | 44 -> 59 - | 75.4 -> 86.2 + | 70 -> 98 + | 50 -> 50 = | 4.1 -> 6.7 - | 0 -> 0 | 0 -> 0 | 3 / 3 |
| car | 5891-1 | usable 0.9 + hang -> connected + usable 0.9 + hang | 87.5 -> 89.4 + | 63 -> 51 + | 34 -> 74 - | 84.5 -> 87.4 + | 80 -> 99 + | 50 -> 50 = | 20.8 -> 34.8 - | 0 -> 0 | 0 -> 0 | 4 / 2 |
| car | 4956-1 | usable 0.9 + hang -> connected + usable 0.9 + hang | 78.3 -> 82.8 + | 38 -> 36 + | 255 -> 423 - | 72.6 -> 85.4 + | 74 -> 93 + | 49 -> 47 - | 40.9 -> 57.1 - | 0 -> 0 | 0 -> 0 | 4 / 3 |
| chair | 6378-1 | usable 0.8 + hang -> connected + usable 0.8 + hang | 90.6 -> 92.7 + | 17 -> 18 - | 35 -> 35 = | 89.1 -> 91.4 + | 42 -> 75 + | 50 -> 50 = | 11.8 -> 4.2 + | 0 -> 0 | 0 -> 0 | 4 / 1 |
| chair | 5891-1 | usable 0.8 + hang -> connected + usable 0.8 + hang | 88.0 -> 96.4 + | 43 -> 24 + | 49 -> 14 + | 85.1 -> 95.5 + | 73 -> 100 + | 44 -> 44 = | 50.9 -> 29.3 + | 0 -> 0 | 0 -> 7 | 6 / 0 |
| chair | 4956-1 | usable 0.8 + hang -> connected + usable 0.8 + hang | 83.0 -> 91.2 + | 53 -> 39 + | 122 -> 69 + | 78.7 -> 89.4 + | 45 -> 95 + | 38 -> 40 + | 66.8 -> 37.4 + | 0 -> 0 | 0 -> 5 | 7 / 0 |
| table | 6378-1 | usable 0.8 + hang -> connected + usable 0.8 + hang | 83.9 -> 88.0 + | 36 -> 22 + | 92 -> 82 + | 79.1 -> 88.4 + | 69 -> 100 + | 49 -> 50 + | 6.2 -> 7.7 - | 0 -> 0 | 0 -> 3 | 6 / 1 |
| table | 5891-1 | usable 0.8 + hang -> connected + usable 0.8 + hang | 93.3 -> 92.5 - | 36 -> 43 - | 29 -> 15 + | 91.1 -> 91.9 + | 94 -> 100 + | 43 -> 49 + | 31.6 -> 37.8 - | 0 -> 0 | 1 -> 2 | 4 / 3 |
| table | 4956-1 | usable 0.8 + hang -> connected + usable 0.8 + hang | 84.9 -> 86.5 + | 29 -> 39 - | 351 -> 82 + | 85.4 -> 83.9 - | 94 -> 100 + | 41 -> 42 + | 49.5 -> 43.2 + | 0 -> 0 | 0 -> 0 | 5 / 2 |
| car | 6378-1 | usable 0.8 + hang -> connected + usable 0.8 + hang | 84.1 -> 87.0 + | 32 -> 25 + | 49 -> 88 - | 82.0 -> 86.9 + | 86 -> 97 + | 50 -> 50 = | 3.7 -> 3.6 + | 0 -> 0 | 0 -> 0 | 5 / 1 |
| car | 5891-1 | usable 0.8 + hang -> connected + usable 0.8 + hang | 87.2 -> 92.0 + | 55 -> 30 + | 22 -> 42 - | 85.4 -> 92.7 + | 85 -> 100 + | 50 -> 50 = | 13.9 -> 19.9 - | 0 -> 0 | 0 -> 0 | 4 / 2 |
| car | 4956-1 | usable 0.8 + hang -> connected + usable 0.8 + hang | 81.4 -> 84.0 + | 43 -> 34 + | 260 -> 305 - | 79.5 -> 83.5 + | 81 -> 98 + | 50 -> 47 - | 29.9 -> 27.4 + | 0 -> 0 | 0 -> 0 | 5 / 2 |

## Stalls

| pair | connected (1.0) | connected90 | connected80 | default, any slack |
|---|---|---|---|---|
| chair 6378-1 | 0 | 0 | 0 | 0 |
| chair 5891-1 | 6 (layer 9) | 1 (9) | 7 (6, 9 × 6) | 0 |
| chair 4956-1 | 5 (11) | 0 | 5 (10 × 3, 20 × 2) | 0 |
| table 6378-1 | 11 (8, 28–40) | 8 (25–38) | 3 (7, 29 × 2) | 0 |
| table 5891-1 | 4 (38–44) | 5 (38–47) | 2 (9 × 2) | 1 at 0.8 (32) |
| table 4956-1 | 0 | 0 | 0 | 0 |
| cars | 0 | 0 | 0 | 0 |

Each stalled seed was rebuilt with the builder's state captured after growth: the parts grown, the standing prefix the
balance keeps, and every placement at the layer above the grown top. Placements were tried two ways: with the inventory
left, and with any part in the builder's catalog. Every rebuild matches its cached run. In none of them is the
balance cut the cause: the standing prefix always keeps every grown part. There are two causes.

**1. A base: no part fits anywhere.** This is 26 seeds:
- 5891-1 chair: 14, all of its stalls (6 at 1.0, 1 at 0.9, 7 at 0.8).
- 4956-1 chair: 8 (5 at 1.0, 3 at 0.8).
- 6378-1 table: 2 (1.0 and 0.8).
- 5891-1 table at 0.8: 2.

On the tables, growth stops at layers 7–9, where the target joins the legs low down; there it meets the chair's
block.

The chair's base is a set of caster columns: 24 cells at layers 0–3 of the 5891-1 target. At layer 4 it widens into
diagonal arms 1–2 cells wide, stair-stepped toward the hub (24 → 65 cells). Above the hub a 2-cell post runs from layer
10 to layer 26.

Connected growth starts from one ground region, the largest, and the nearest the footprint's centre among those. Every
other caster has to be reached along the arms and hung down to the ground. To step onto an arm, a part must sit on a
stud of the structure built so far and reach out over the arm's empty cells. A part's footprint must have a stud below
it, and it may not sit over a studless top.

In the stalled seeds, the seed column was built of parts that stay inside it. Each layer covers the studs of the layer
below, so no free stud is left under any arm cell. Nothing is placed above the arms, so nothing can hang there either.
- Growth tops out at the top of the base: layer 9 (5891-1), 10 or 11 (4956-1).
- Only 3–9 of that layer's 49–77 cells are filled.
- At the post's layer, nothing fits, either with the inventory left (431–555 parts) or with any catalog part.

`m12b_connected_stall_map.png` shows this layer by layer for one seed of the first pass (5891-1 chair, seed 7, on its
pre-49d5739 target). Blue cells are part cells with a stud on top, grey cells are part cells without one, and red
cells are empty target cells. The rebuilt seeds on the 49d5739 target show the same picture.
- **Not the post:** growth never reaches it.
- **Not the balance cut.**

So a post-first rule has nothing to act on, and a longer hang reach has nothing to hang from. Two fixes would act on
the cause:
- **Multi-seed growth:** seed every ground region, and let the arms meet at the hub, as in the real chair.
- **A preference at an overhang layer for parts that leave a free stud on the overhang side.**

**2. A thin leg or post: the inventory runs out of parts that fit it.** This is 31 seeds:
- 6378-1 table: 20 (10 at 1.0, 8 at 0.9, 2 at 0.8).
- 5891-1 table: 9 (4 at 1.0, 5 at 0.9).
- 4956-1 chair: 2 at 0.8.

The build climbs one 2 × 2 table leg, or the chair's post, for 106–184 parts. It stops below the top: at layers 25–40
on the 6378-1 table (top at 42), 38–47 on the 5891-1 table (top at 48), and layer 20 of the 4956-1 chair's post. There
the leg's cells have studs below them.
- With the inventory left (78–392 parts), nothing fits there.
- With any catalog part, 27–101 placements fit: 1 × 1 and 1 × 2 plates and bricks, 2 × 2 bricks and plates.

The parts that fit the leg's section are used up, and the other legs and the top were never started: the remaining
legs hang from the top, and the top needs the leg. Multi-seed growth would not fix this. It would need either:
- the narrow parts kept for the narrow sections, or
- the top reached from wider parts that cantilever across.

ee measured the reserve and did not adopt it (`m12b_sizing.md`: "parts reserved for thin sections").

**Both fixes are held** (cf, 2026-10-10): no stall costs a selected build. No change to the order until a selected
connected build loses to the default because of one.

## Runs

- **First pass:** 27 cells at 41c9406 (m12b-connected = main 0863884 + ee's 59cbfdc).
  - At 07:20 a pool worker was killed under memory pressure while two generation jobs shared the machine. The pass
    ended with `BrokenProcessPool`.
  - 24 cells had finished. The 3 connected80 cars had not started (0 cached candidates).
  - Every finished cell is a complete run from the cache, so the crash does not affect them.
- **Second pass**, at 49d5739 merged into m12b-connected (6dac174), alone on the machine.
  - It ran the 3 cars and every connected cell whose mask changed under ee's two scale fixes.
  - The 4 changed cells' old runs are in `out/m12b_complete/sweep_premoment/`.

| cell | target cells (old → 49d5739) | change |
|---|---|---|
| connected, 6378-1 chair | 1353 → 1326 | post no longer cut (0dbb3b6), then the moment key (49d5739) |
| connected80, 6378-1 chair | 1073 → 1138 | post no longer cut (0dbb3b6) |
| connected, 5891-1 chair | 2859 → 2784 | moment key (49d5739) |
| connected90, 5891-1 chair | 2603 → 2621 | moment key (49d5739) |

- **The other 23 cells** have masks byte-identical to their cache keys under 49d5739. The builder did not change
  (BUILDER_VERSION 2): ee's merge adds only trace hooks, which draw nothing from the generator.
- **After main e0933bb** (usable sizing and the hanging hole pass as 3D-target defaults) was merged in, the cache key
  that each cell's pipeline command computes was checked against its cached key. All 27 are identical.
- **The old 6378-1 chair cells.** On the cut-post target its connected cells measured the bug: all 50 seeds stalled
  at 8.9% fill. With the post back, none stalls.

## Reproduce

See `docs/reproduce.md` (§ `results/m12b_connected.md`).
