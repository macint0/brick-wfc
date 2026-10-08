# Sets to learn style from (for M10)

Reproduce: `python -m brickwfc.experiments.sets --out out/sets` (fetches into `data/omr/`, cached; raw data:
`sets_selection.json`).

**Why:** M7–M11 used ten sets taken in OMR number order (trains, a UCS ship, the Wright Flyer…), and the
four-plate parts list recognized only 3–15% of each. To learn what real builds look like, we want sets made
mostly of the parts the generators know.

**Candidates (86):** building-type sets in the LDraw OMR (index read on 2026-10-08). That is every set in
Modular Buildings, Creator Expert, Town Plan, Legoland Building, Paradisa, City Center and Universal Building
Set, plus Town / City / Creator / Legoland sets whose names say building (house, shop, station, café…) and
not vehicle. The list is `experiments/sets.py: CANDIDATES`.

**Rule:**
- at least **50%** of the set's parts are in `parts.CATALOG` (`experiments/coverage.py`; LDraw primitives are
  not counted as parts);
- at least **50 parts**;
- at least **50% of its recognized parts on the stud grid** after voxelization (`bricks.voxelize`), since
  style statistics are learned only from those parts;
- not a re-release (identical recognized inventory; the earliest release is kept: 560-1 = 376-2,
  6350-1 = 10036-1, 6376-1 = 10037-1, 1213-2 = 1212-2).

Ten candidates are not at the default OMR file name (HTTP 404) and are skipped: 10232-1, 31153-1, 4886-1,
4996-1 and six Universal Building / Basic sets.

**The on-grid rule** removes three sets that pass the other rules: 364-1 Harbour Scene (20% on grid),
376-2 Town House with Garden (39%) and 10184-1 Town Plan (44%; each of its buildings sits on its own grid).
That leaves 28 sets, so 4-fold cross-validation in M10 trains on 21 sets per fold (≥ 20).

**Result: 28 sets selected**, 51–88% recognized:
- 10 classic Town (1978–1987): fire stations, service stations, garage, post office, town house, weekend home,
  treatment centre.
- 8 Modular Buildings (2007–2019).
- 8 Creator houses (2007–2016).
- 1 City set (7743-1 Police Command Center).
- 1 Legoland set (349-1 Swiss Chalet).

**What the statistics are learned from:** 12595 of the selected sets' 15533 recognized parts
(81%) are on the grid. Of the rest, 2130 are tilted (not a quarter-turn about the vertical:
sideways or upside-down building, angled sub-models), 804 are off the main grid (e.g. sub-models at a
half-stud offset) and 4 overlap another part. Per-set counts are in the *on grid* … *overlapping* columns
below.

## All candidates

| set | name | theme | year | parts | recognized % | on grid | on grid % | tilted | off grid | overlapping | selected |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 7796-1 | House | Creator | 2008 | 56 | 87.5 | 49 | 100 | 0 | 0 | 0 | yes |
| 10182-1 | Cafe Corner | Modular Buildings | 2007 | 2073 | 73.0 | 1179 | 78 | 304 | 30 | 1 | yes |
| 377-1 | Shell Service Station | Town > Classic Town | 1978 | 203 | 68.5 | 116 | 83 | 0 | 23 | 0 | yes |
| 10190-1 | Market Street | Modular Buildings | 2007 | 1484 | 66.6 | 817 | 83 | 78 | 93 | 1 | yes |
| 4954-1 | Model Town House | Creator > Creator 3-in-1 | 2007 | 1174 | 65.9 | 638 | 82 | 89 | 47 | 0 | yes |
| 364-1 | Harbour Scene | Legoland > Harbor | 1975 | 547 | 65.1 | 71 | 20 | 118 | 167 | 0 | < 50% on grid |
| 10224-1 | Town Hall | Modular Buildings | 2012 | 2804 | 63.9 | 1591 | 89 | 134 | 67 | 0 | yes |
| 10185-1 | Green Grocer | Modular Buildings | 2008 | 2405 | 63.7 | 1417 | 92 | 93 | 23 | 0 | yes |
| 6363-1 | Auto Service Station | Town > Classic Town | 1980 | 150 | 63.3 | 68 | 72 | 27 | 0 | 0 | yes |
| 4956-1 | House | Creator > Creator 3-in-1 | 2007 | 629 | 63.1 | 373 | 94 | 21 | 3 | 0 | yes |
| 10218-1 | Pet Shop | Modular Buildings | 2011 | 2042 | 61.6 | 958 | 76 | 125 | 175 | 0 | yes |
| 10197-1 | Fire Brigade | Modular Buildings | 2009 | 2302 | 61.6 | 1081 | 76 | 290 | 46 | 1 | yes |
| 361-2 | Garage | Town > Classic Town | 1979 | 85 | 61.2 | 52 | 100 | 0 | 0 | 0 | yes |
| 374-1 | Fire Station | Town > Classic Town | 1978 | 363 | 60.3 | 213 | 97 | 0 | 6 | 0 | yes |
| 10184-1 | Town Plan | Town > Town Plan | 2008 | 2033 | 60.2 | 538 | 44 | 202 | 483 | 0 | < 50% on grid |
| 5771-1 | Hillside House | Creator > Creator 3-in-1 | 2011 | 703 | 60.0 | 358 | 85 | 38 | 25 | 1 | yes |
| 5891-1 | Apple Tree House | Creator > Creator 3-in-1 | 2010 | 539 | 59.9 | 290 | 90 | 11 | 22 | 0 | yes |
| 31009-1 | Small Cottage | Creator > Creator 3-in-1 | 2013 | 270 | 59.3 | 155 | 97 | 4 | 1 | 0 | yes |
| 6362-1 | Post Office | Town > Classic Town | 1982 | 139 | 59.0 | 62 | 76 | 20 | 0 | 0 | yes |
| 6378-1 | Shell Service Station | Town > Classic Town | 1986 | 348 | 58.3 | 164 | 81 | 15 | 24 | 0 | yes |
| 349-1 | Swiss Chalet | Legoland > Building | 1971 | 80 | 57.5 | 46 | 100 | 0 | 0 | 0 | yes |
| 5766-1 | Log Cabin | Creator > Creator 3-in-1 | 2011 | 360 | 56.4 | 185 | 91 | 18 | 0 | 0 | yes |
| 6372-1 | Town House | Town > Classic Town | 1982 | 239 | 56.1 | 131 | 98 | 0 | 3 | 0 | yes |
| 10243-1 | Parisian Restaurant | Modular Buildings | 2014 | 2593 | 54.9 | 1135 | 80 | 252 | 36 | 0 | yes |
| 376-2 | Town House with Garden | Town > Classic Town | 1978 | 232 | 54.7 | 50 | 39 | 72 | 5 | 0 | < 50% on grid |
| 560-1 | Town House with Garden | Town > Classic Town | 1979 | 232 | 54.7 | 50 | 39 | 72 | 5 | 0 | re-release of 376-2 |
| 31048-1 | Lakeside Lodge | Creator > Creator 3-in-1 | 2016 | 369 | 54.5 | 166 | 83 | 30 | 5 | 0 | yes |
| 6380-1 | Emergency Treatment Center | Town > Classic Town | 1987 | 333 | 54.4 | 115 | 64 | 11 | 55 | 0 | yes |
| 10264-1 | Corner Garage | Modular Buildings | 2019 | 2573 | 52.1 | 848 | 63 | 461 | 32 | 0 | yes |
| 6382-1 | Fire Station | Town > Classic Town | 1981 | 415 | 51.1 | 150 | 71 | 62 | 0 | 0 | yes |
| 7743-1 | Police Command Center | City > Police | 2008 | 547 | 51.0 | 145 | 52 | 46 | 88 | 0 | yes |
| 6370-1 | Weekend Home | Town > Classic Town | 1985 | 185 | 50.8 | 93 | 99 | 1 | 0 | 0 | yes |
| 7641-1 | City Corner | City > Traffic | 2009 | 506 | 49.4 | 112 | 45 | 34 | 104 | 0 | < 50% recognized |
| 6350-1 | Pizza To Go | Town > Classic Town | 1994 | 166 | 49.4 | 59 | 72 | 22 | 0 | 1 | < 50% recognized |
| 10036-1 | Pizza To Go | Town | 2002 | 166 | 49.4 | 59 | 72 | 22 | 0 | 1 | re-release of 6350-1 |
| 6365-1 | Summer Cottage | Town > Classic Town | 1981 | 155 | 49.0 | 74 | 97 | 0 | 2 | 0 | < 50% recognized |
| 6374-1 | Holiday Home | Town > Classic Town | 1983 | 280 | 48.2 | 116 | 86 | 4 | 15 | 0 | < 50% recognized |
| 5770-1 | Lighthouse Island | Creator > Creator 3-in-1 | 2011 | 520 | 48.1 | 211 | 84 | 8 | 30 | 1 | < 50% recognized |
| 6392-1 | Airport | Town > Classic Town | 1985 | 579 | 47.5 | 172 | 63 | 81 | 22 | 0 | < 50% recognized |
| 6384-1 | Police Station | Town > Classic Town | 1983 | 469 | 47.3 | 149 | 67 | 67 | 6 | 0 | < 50% recognized |
| 10246-1 | Detective's Office | Modular Buildings | 2015 | 2608 | 46.8 | 953 | 78 | 87 | 180 | 0 | < 50% recognized |
| 10278-1 | Police Station | Modular Buildings | 2021 | 3480 | 46.6 | 1319 | 81 | 291 | 10 | 0 | < 50% recognized |
| 6552-1 | Rocky River Retreat | Town > Classic Town | 1993 | 243 | 46.1 | 64 | 57 | 8 | 40 | 0 | < 50% recognized |
| 6683-1 | Burger Stand | Town > Classic Town | 1983 | 79 | 45.6 | 34 | 94 | 2 | 0 | 0 | < 50% recognized |
| 6369-1 | Garage | Town > Classic Town | 1985 | 143 | 45.5 | 54 | 83 | 0 | 11 | 0 | < 50% recognized |
| 7637-1 | Farm | City > Farm | 2009 | 652 | 44.8 | 100 | 34 | 39 | 153 | 0 | < 50% recognized |
| 1472-1 | Holiday Home | Town > Classic Town | 1987 | 367 | 43.9 | 62 | 39 | 78 | 21 | 0 | < 50% recognized |
| 1854-1 | House with Roof-Windows (Velux) | Town > Classic Town | 1996 | 147 | 42.9 | 60 | 95 | 3 | 0 | 0 | < 50% recognized |
| 10159-1 | City Airport | City > Airport | 2004 | 589 | 42.8 | 154 | 61 | 58 | 40 | 0 | < 50% recognized |
| 6349-1 | Vacation House | Town > Classic Town | 1988 | 212 | 42.0 | 78 | 88 | 3 | 8 | 0 | < 50% recognized |
| 10270-1 | Bookshop | Modular Buildings | 2020 | 3068 | 41.5 | 1066 | 84 | 185 | 20 | 1 | < 50% recognized |
| 7997-1 | Train Station | City > Trains | 2007 | 415 | 41.4 | 157 | 91 | 4 | 11 | 0 | < 50% recognized |
| 1490-1 | Town Bank | Town > Classic Town | 1988 | 200 | 41.0 | 52 | 63 | 29 | 1 | 0 | < 50% recognized |
| 10251-1 | Brick Bank | Modular Buildings | 2016 | 3362 | 40.2 | 982 | 73 | 107 | 261 | 0 | < 50% recognized |
| 6389-1 | Fire Control Center | Town > Classic Town | 1990 | 639 | 39.9 | 156 | 61 | 88 | 11 | 0 | < 50% recognized |
| 1484-1 | Weetabix Town House | Town > Classic Town | 1987 | 207 | 39.6 | 67 | 82 | 3 | 12 | 0 | < 50% recognized |
| 6689-1 | Post-Station | Town > Classic Town | 1985 | 68 | 38.2 | 25 | 96 | 1 | 0 | 0 | < 50% recognized |
| 6386-1 | Police Command Base | Town > Classic Town | 1986 | 525 | 37.1 | 132 | 68 | 39 | 24 | 0 | < 50% recognized |
| 6416-1 | Poolside Paradise | Town > Paradisa | 1992 | 240 | 37.1 | 75 | 84 | 6 | 8 | 0 | < 50% recognized |
| 6540-1 | Pier Police | Town > Classic Town | 1991 | 429 | 37.1 | 49 | 31 | 60 | 50 | 0 | < 50% recognized |
| 6376-1 | Breezeway Cafe | Town > Classic Town | 1990 | 221 | 35.3 | 71 | 91 | 7 | 0 | 0 | < 50% recognized |
| 10037-1 | Breezeway Cafe | Town | 2002 | 221 | 35.3 | 71 | 91 | 7 | 0 | 0 | re-release of 6376-1 |
| 6414-1 | Dolphin Point | Town > Paradisa | 1995 | 216 | 34.7 | 65 | 87 | 5 | 5 | 0 | < 50% recognized |
| 6562-1 | Gas Stop Shop | Town > Classic Town | 1995 | 288 | 33.0 | 38 | 40 | 57 | 0 | 0 | < 50% recognized |
| 10297-1 | Boutique Hotel | Modular Buildings | 2022 | 4556 | 32.4 | 985 | 67 | 476 | 17 | 0 | < 50% recognized |
| 6479-1 | Emergency Response Center | Town > Res-Q | 1998 | 460 | 32.4 | 0 | 0 | 20 | 129 | 0 | < 50% recognized |
| 6402-1 | Sidewalk Cafe | Town > Paradisa | 1994 | 59 | 32.2 | 18 | 95 | 1 | 0 | 0 | < 50% recognized |
| 6598-1 | Metro PD Station | Town > Classic Town | 1996 | 728 | 31.6 | 77 | 33 | 119 | 34 | 0 | < 50% recognized |
| 30023-1 | Lighthouse | Creator | 2011 | 25 | 20.0 | 4 | 80 | 0 | 1 | 0 | < 50% recognized |
| 6699-1 | Cycle Fix-It Shop | Town > Classic Town | 1987 | 216 | 19.9 | 38 | 88 | 5 | 0 | 0 | < 50% recognized |
| 60216-1 | Downtown Fire Brigade | City > Fire | 2019 | 2209 | 14.4 | 104 | 33 | 199 | 15 | 1 | < 50% recognized |
| 1212-2 | Small House - Left Set | System > Town Plan | 1955 | 59 | 6.8 | 4 | 100 | 0 | 0 | 0 | < 50% recognized |
| 1213-2 | Small House - Right Set | System > Town Plan | 1955 | 59 | 6.8 | 4 | 100 | 0 | 0 | 0 | re-release of 1212-2 |
| 1210-2 | Small Store Set | System > Town Plan | 1955 | 85 | 5.9 | 5 | 100 | 0 | 0 | 0 | < 50% recognized |
| 1211-2 | Small House Set | System > Town Plan | 1955 | 96 | 3.1 | 3 | 100 | 0 | 0 | 0 | < 50% recognized |
| 722-1 | Universal Building Set | Universal Building Set | 1980 | 0 | 0.0 | 0 | — | 0 | 0 | 0 | unavailable (HTTP 404) |
| 733-1 | Universal Building Set | Universal Building Set | 1980 | 0 | 0.0 | 0 | — | 0 | 0 | 0 | unavailable (HTTP 404) |
| 744-1 | Universal Building Set | Universal Building Set | 1980 | 0 | 0.0 | 0 | — | 0 | 0 | 0 | unavailable (HTTP 404) |
| 544-1 | Basic Set | Universal Building Set | 1981 | 0 | 0.0 | 0 | — | 0 | 0 | 0 | unavailable (HTTP 404) |
| 555-2 | Basic Set | Universal Building Set | 1981 | 0 | 0.0 | 0 | — | 0 | 0 | 0 | unavailable (HTTP 404) |
| 566-1 | Basic Set | Universal Building Set | 1981 | 0 | 0.0 | 0 | — | 0 | 0 | 0 | unavailable (HTTP 404) |
| 6360-1 | Weekend Cottage | Town > Classic Town | 1986 | 0 | 0.0 | 0 | — | 0 | 0 | 0 | < 50% recognized |
| 4886-1 | Building Bonanza | Creator > Designer Sets | 2004 | 0 | 0.0 | 0 | — | 0 | 0 | 0 | unavailable (HTTP 404) |
| 4996-1 | Beach House | Creator > Creator 3-in-1 | 2008 | 0 | 0.0 | 0 | — | 0 | 0 | 0 | unavailable (HTTP 404) |
| 10232-1 | Palace Cinema | Modular Buildings | 2013 | 0 | 0.0 | 0 | — | 0 | 0 | 0 | unavailable (HTTP 404) |
| 31153-1 | Modern House | Creator > Creator 3-in-1 | 2024 | 0 | 0.0 | 0 | — | 0 | 0 | 0 | unavailable (HTTP 404) |
