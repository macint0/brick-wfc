# M12c: Rebrickable inventories vs the OMR models (28 M10 sets)

`python -m brickwfc.experiments.rebrickable_check`. Inventories over the part catalog; agreement = weighted Jaccard sum min / sum max of the counts (1 = identical).

**Agreement over 28 sets:** per (part, color) mean 0.953 (median 0.981); per part 0.969; per color 0.964. Catalog parts: OMR 15533, Rebrickable 15696.

| set | name | year | inventory version | OMR parts | Rebrickable parts | agreement | parts only | colors only |
|---|---|---|---|---|---|---|---|---|
| 349-1 | Swiss Chalet | 1971 | 1 | 46 | 46 | 1.000 | 1.000 | 1.000 |
| 374-1 | Fire Station | 1978 | 1 | 219 | 221 | 0.938 | 0.938 | 0.991 |
| 377-1 | Shell Service Station | 1978 | 1 | 139 | 140 | 0.924 | 0.924 | 0.993 |
| 361-2 | Garage | 1979 | 1 | 52 | 50 | 0.925 | 0.925 | 0.962 |
| 6363-1 | Auto Service Station | 1980 | 1 | 95 | 93 | 0.979 | 0.979 | 0.979 |
| 6382-1 | Fire Station | 1981 | 1 | 212 | 214 | 0.991 | 0.991 | 0.991 |
| 6362-1 | Post Office | 1982 | 1 | 82 | 87 | 0.920 | 0.920 | 0.920 |
| 6372-1 | Town House | 1982 | 1 | 134 | 137 | 0.978 | 0.978 | 0.978 |
| 6370-1 | Weekend Home | 1985 | 2 | 94 | 96 | 0.939 | 0.939 | 0.979 |
| 6378-1 | Shell Service Station | 1986 | 1 | 203 | 209 | 0.962 | 0.962 | 0.971 |
| 6380-1 | Emergency Treatment Center | 1987 | 2 | 181 | 185 | 0.926 | 0.926 | 0.957 |
| 10182-1 | Cafe Corner | 2007 | 1 | 1514 | 1513 | 0.981 | 0.999 | 0.982 |
| 10190-1 | Market Street | 2007 | 1 | 989 | 988 | 0.991 | 0.995 | 0.995 |
| 4954-1 | Model Town House | 2007 | 1 | 774 | 774 | 0.997 | 0.997 | 1.000 |
| 4956-1 | House | 2007 | 2 | 397 | 478 | 0.831 | 0.831 | 0.831 |
| 10185-1 | Green Grocer | 2008 | 2 | 1533 | 1541 | 0.991 | 0.991 | 0.995 |
| 7743-1 | Police Command Center | 2008 | 2 | 279 | 282 | 0.989 | 0.989 | 0.989 |
| 7796-1 | House | 2008 | 1 | 49 | 49 | 1.000 | 1.000 | 1.000 |
| 10197-1 | Fire Brigade | 2009 | 1 | 1418 | 1420 | 0.992 | 0.994 | 0.996 |
| 5891-1 | Apple Tree House | 2010 | 2 | 323 | 325 | 0.982 | 0.982 | 0.994 |
| 10218-1 | Pet Shop | 2011 | 2 | 1258 | 1267 | 0.991 | 0.991 | 0.993 |
| 5766-1 | Log Cabin | 2011 | 1 | 203 | 204 | 0.976 | 0.976 | 0.995 |
| 5771-1 | Hillside House | 2011 | 1 | 422 | 426 | 0.986 | 0.991 | 0.991 |
| 10224-1 | Town Hall | 2012 | 1 | 1792 | 1799 | 0.996 | 0.996 | 0.996 |
| 31009-1 | Small Cottage | 2013 | 1 | 160 | 164 | 0.976 | 0.976 | 0.976 |
| 10243-1 | Parisian Restaurant | 2014 | 2 | 1423 | 1437 | 0.990 | 0.990 | 0.990 |
| 31048-1 | Lakeside Lodge | 2016 | 1 | 201 | 202 | 0.985 | 0.985 | 0.995 |
| 10264-1 | Corner Garage | 2019 | 2 | 1341 | 1349 | 0.553 | 0.979 | 0.565 |

## Sets below 0.9 agreement

- 4956-1 (0.831): plate1x1_6141 black +16, plate1x2 white +12, plate1x8 white +9, tile1x1 light_gray +6, plate4x6 red +5
- 10264-1 (0.553): brick1x4 ldraw484 +54, brick1x4 ldraw84 -54, brick1x2 ldraw484 +48, brick1x2 ldraw84 -48, brick1x6 ldraw484 +47

## Systematic part differences (colors pooled)

| name | Rebrickable - OMR (all sets) | sets with more | sets with fewer |
|---|---|---|---|
| tile1x2 | +33 | 13 | 0 |
| tile1x1_2555 | +21 | 3 | 0 |
| plate1x1_6141 | +18 | 2 | 0 |
| brick2x2_3941 | +15 | 7 | 0 |
| plate1x2 | +15 | 2 | 0 |
| brick2x2_6143 | -13 | 0 | 6 |
| tile2x2 | +12 | 7 | 0 |
| brick1x1_3062a | +11 | 2 | 0 |
| brick1x1_3062b | -11 | 0 | 2 |
| tile1x1 | +10 | 4 | 3 |
| plate1x8 | +9 | 1 | 0 |
| plate4x6 | +7 | 1 | 0 |
| tile1x4 | +7 | 3 | 0 |
| plate1x1 | +6 | 4 | 1 |
| brick1x2 | +5 | 4 | 2 |

## Systematic color differences (parts pooled)

| name | Rebrickable - OMR (all sets) | sets with more | sets with fewer |
|---|---|---|---|
| ldraw484 | +363 | 1 | 0 |
| ldraw84 | -360 | 0 | 1 |
| white | +79 | 14 | 0 |
| light_gray | +24 | 7 | 2 |
| black | +21 | 7 | 2 |
| ldraw73 | +11 | 3 | 0 |
| red | +11 | 3 | 1 |
| ldraw9 | -9 | 0 | 1 |
| dark_gray | +7 | 2 | 1 |
| reddish_brown | +5 | 3 | 0 |
| ldraw80 | +4 | 2 | 1 |
| dark_tan | +3 | 3 | 0 |
| green | +3 | 3 | 0 |
| ldraw128 | -3 | 0 | 1 |
| ldraw322 | -2 | 0 | 1 |

## Mapping notes

Colors guessed by nearest RGB (Rebrickable name -> our color: parts): none.

Parts found through a print/mold parent (top): 12825 -> 2555: 23, 3003a -> 3003: 16, 3009b -> 3009: 14, 3069bpr0099 -> 3069b: 13, 3002a -> 3002: 10, 15712 -> 2555: 8, 3008b -> 3008: 7, 3069bpr0055 -> 3069b: 6, 3001a -> 3001: 4, 3068bpr0061 -> 3068b: 3, 2431pr0032 -> 2431: 3, 3069bpr0030 -> 3069b: 3, 3069bpr0100 -> 3069b: 3, 3941pr0002 -> 3941: 2, 3068bpr0197 -> 3068b: 2.

Rebrickable parts not in the catalog (top, all sets): 54200: 279, 32028: 234, 4216: 221, 2357: 198, 2420: 188, 3794a: 169, 30136: 158, 60592: 154, 3037: 153, 60601: 149.
