# M12e: the OMR training pool

`python -m brickwfc.ldraw.omr_crawl --out data/omr` then `python -m brickwfc.experiments.omr_pool --data data/omr` (reruns in one command when `parts.CATALOG` changes; the measurement is cached per catalog fingerprint). Catalog: **183 parts**, fingerprint `475df2114737`.

## The repository

- OMR sets in the index: **1470**; models listed: **1833** (1470 main models, 363 official alternates).
- Models on disk: **1821**; failed downloads: 12; unreadable: 0.

## Every model on the current catalog

| models | part instances | recognized | recognized % | on grid | on grid % of parts | on grid % of recognized |
|---|---|---|---|---|---|---|
| 1821 | 692047 | 344646 | 49.8 | 202066 | 29.2 | 58.6 |

**Parts not on the grid, as a share of all part instances** (per model in the pool file: `unrecognized_pct`, `off_grid_total_pct` = `tilted_pct` + `off_stud_grid_pct` + `overlapping_pct` + `accessory_off_pct`). Tilted = not a quarter turn about the vertical (sideways, upside down, angled); off the stud grid = a recognized part at a fractional stud or plate offset (jumper offsets); accessory = glass, a pane or a door held by a frame that is itself off the grid. On grid counts the accessories kept frames hold, as `coverage --on-grid` does.

| models | unrecognized | off grid, all causes | tilted | off the stud grid | overlapping | accessory | on grid | median model: unrecognized / off grid |
|---|---|---|---|---|---|---|---|---|
| every readable model (1821) | 50.2% | 20.6% | 15.7% | 4.5% | 0.3% | 0.1% | 29.2% | 46.3% / 13.8% |
| pool (582) | 27.1% | 19.7% | 13.7% | 5.3% | 0.6% | 0.1% | 53.2% | 32.6% / 14.8% |

Per model, 10th / 50th / 90th percentile: parts 31 / 139 / 922 (max 10717); recognized % 4 / 54 / 81 (max 100); on-grid % of recognized 0 / 62 / 96 (max 100).

## Selection

`experiments/sets.py`'s criteria loosened to size: no theme filter, **>= 50% recognized**, **>= 50% of the recognized parts on the grid**, **>= 20 on-grid parts**, **not a flat panel** (<= 9 plates tall over >= 1024 square studs: the mosaics), no re-releases (identical recognized inventory; the oldest set keeps it; alternates of one set never collide).

| reason | models |
|---|---|
| < 50% recognized | 774 |
| yes | 582 |
| < 50% on grid | 305 |
| < 20 on-grid parts | 105 |
| re-release | 46 |
| flat panel (mosaic) | 9 |

**Pool: 582 models from 457 sets** (435 main, 147 alternates); **228479 part instances, 166619 recognized (72.9%), 121521 on the grid** (53.2% of the instances). On-grid parts per model 27 / 94 / 448 (max 3493).
- Larger than the token grid (64 x 64 studs x 192 plates): 14 models (the export crops them; `experiments/export_tokens.py`).
- Demo sets (held out of training by the export): 6378-1 in the pool, 31048-1 in the pool.

## Decisions (session B, 2026-10-15)

- **No theme filter.** `experiments/sets.py` kept building themes (the 28 M10 sets). The model learns which parts go where, and vehicles, castles and trains place the same plates, bricks, slopes and tiles. The coverage thresholds already drop builds made mostly of parts the catalog lacks (Technic, minifigures, wheels): the pool's themes are listed below.
- **The M10 thresholds are kept** (>= 50% recognized, >= 50% of the recognized parts on the grid). The size floor is lowered from 50 parts to 20 on-grid parts: that is the loosening to size. A small model is a short sequence, not a wrong one.
- **Flat panels are dropped.** These are the mosaics: 2,400–10,500 1 x 1 plates and tiles 8 plates tall. They would have been 22% of the pool's on-grid parts while teaching a picture, not a build. The rule is geometric (<= 9 plates over >= 1024 square studs). On this catalog it catches exactly those 9 models; a low car or train is narrow, so it is not caught.
- **Official alternates are kept** as their own sequences (`main` false, `alternate_of` = their set). More builds per inventory is what the model should learn. The export splits by set number, so a held-out set holds out its alternates too.
- **Re-releases** (the same recognized inventory under a later set number) are dropped; the oldest set keeps it, as in `experiments/sets.py`.
- **Off the grid, by cause, in the pool:** tilted 13.7% vs off the stud grid 5.3% of all part instances. Tilted parts (sideways, upside down, angled) are 2.6x the jumper-offset kind. If sideways building were supported, those parts would be the gain.

## Pool by theme

| theme | models | on-grid parts |
|---|---|---|
| Creator > Creator 3-in-1 | 116 | 20553 |
| Modular Buildings | 13 | 19002 |
| Creator > Creator Expert | 11 | 13020 |
| Architecture | 23 | 10253 |
| Town > Classic Town | 62 | 5541 |
| Icons | 4 | 4783 |
| Factory | 18 | 2958 |
| Friends | 17 | 2727 |
| Harry Potter | 7 | 2556 |
| Train > 9V | 17 | 2366 |
| Universal Building Set | 21 | 2064 |
| Model Team | 6 | 1939 |
| Creator > Designer Sets | 26 | 1800 |
| Star Wars > Ultimate Collector Series | 1 | 1560 |
| Other | 1 | 1521 |
| Super Heroes DC > Batman > UCS | 2 | 1488 |
| Train > 4.5V | 12 | 1454 |
| Star Wars | 15 | 1332 |
| Ideas and CUUSOO | 3 | 1262 |
| Brickheadz | 22 | 1157 |
| Promotional > Bricktober | 8 | 1134 |
| Pirates > Pirates I | 3 | 1098 |
| Architecture > Skylines | 6 | 1077 |
| Super Heroes Marvel > Avengers | 1 | 1030 |
| Racers | 26 | 910 |
| Hobby Sets | 4 | 909 |
| Modular Buildings > Mini | 1 | 901 |
| Space > Space Police III | 6 | 878 |
| Castle > Lion Knights | 5 | 819 |
| Technic > Expert Builder | 7 | 818 |
| Train > 12V | 7 | 794 |
| Castle > Black Falcons | 3 | 741 |
| Seasonal > Christmas > Creator | 1 | 633 |
| City > Traffic | 7 | 623 |
| Minecraft | 2 | 592 |
| Western | 3 | 566 |
| Castle > Black Knights | 2 | 515 |
| Castle > Knights Kingdom II | 1 | 472 |
| Fabuland | 8 | 444 |
| Speed Champions | 4 | 417 |
| Boat | 7 | 404 |
| City > Police | 4 | 399 |
| Creator | 11 | 369 |
| Racers > Ferrari | 2 | 369 |
| Pharaoh's Quest | 1 | 348 |
| Space > Classic Space | 4 | 339 |
| Promotional | 7 | 337 |
| Elves | 2 | 299 |
| City > Trains | 1 | 251 |
| Legoland > Building | 3 | 249 |
| Exclusive | 1 | 244 |
| Brand Store | 1 | 243 |
| Town > Launch Command | 2 | 222 |
| Space > Space Police I | 3 | 219 |
| Space > Unitron | 2 | 212 |
| Town > Paradisa | 2 | 210 |
| The Hobbit and Lord of the Rings > The Lord of the Rings | 1 | 174 |
| Legoland > Space | 1 | 173 |
| Super Heroes DC > Batman | 2 | 164 |
| City > Farm | 1 | 162 |
| Space > Spyrius | 1 | 137 |
| Train | 1 | 132 |
| Space > Space Police II | 1 | 127 |
| Homemaker | 1 | 112 |
| City > Construction | 2 | 106 |
| Adventurers > Dino Island | 1 | 96 |
| Technic > Universal Building Set | 2 | 92 |
| Space > Blacktron I | 1 | 86 |
| Universal Building Set > Basic | 1 | 82 |
| Town > World City | 1 | 79 |
| Space > Blacktron II | 1 | 78 |
| City > Cargo | 1 | 70 |
| Seasonal > Chinese (Lunar) New Year | 1 | 43 |
| Seasonal > Thanksgiving | 1 | 34 |
| Town | 1 | 31 |
| Legoland > Vehicle | 1 | 31 |
| Seasonal > Advent > Friends | 1 | 24 |
| Legoland > Construction | 1 | 23 |
| Monster Fighters | 1 | 22 |
| Seasonal > Halloween | 1 | 22 |

## Most common parts the catalog misses (all readable models)

| part | instances |
|---|---|
| 2780.dat | 22882 |
| 166.dat | 16839 |
| 77.dat | 12102 |
| 6558.dat | 9633 |
| 932.dat | 7900 |
| 43093.dat | 4957 |
| 754.dat | 2779 |
| 756.dat | 2743 |
| 71533k03.dat | 2063 |
| 4274.dat | 2012 |
| 80.dat | 1991 |
| 3673.dat | 1882 |
| 3820.dat | 1853 |
| 3713.dat | 1739 |
| 4519.dat | 1592 |
| 32062.dat | 1528 |
| 32054.dat | 1391 |
| 22885.dat | 1330 |
| 57518.dat | 991 |
| 4265a.dat | 879 |
| 3749.dat | 828 |
| 6536.dat | 810 |
| 3873.dat | 778 |
| 3641.dat | 736 |
| 4624.dat | 728 |

(Per model only its five most common missing parts are kept, so this undercounts the tail.)
