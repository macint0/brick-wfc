# M13: diversity of the generators' candidates

**Rule:** within a setup (same inventory, grid and target), distances are in units of the median pairwise distance among that setup's D2-pipeline candidates, and two designs count as distinct when they are at least 0.5 units apart (half a typical D2 distance).

`python -m brickwfc.experiments.diversity_pass` (`funnel/diversity.py`: effective number of distinct designs, Leinster-Cobbold order 1). Share = effective / designs; normalized mean distance 1 = as spread out as D2 typically is. Setups without a D2-pipeline reference: —.

## Per generator (mean over runs with a unit)

| generator | runs | verified per run | effective share % | normalized mean distance | selected: effective share % |
|---|---|---|---|---|---|
| d2_noconnect | 3 | 8 | 100.0 | 1.00 | 100.0 |
| pipeline | 25 | 77 | 71.4 | 1.19 | 100.0 |
| pipeline_wfc | 0 | — | — | — | — |

## Per run

| run | generator | setup | candidates | valid | verified | unit | share % | normalized mean distance | selected | selected share % |
|---|---|---|---|---|---|---|---|---|---|---|
| out/alt/10182-1 | pipeline | ad3552 | 200 | 14 | 13 | 0.335 | 100 | 1.00 | 8 | 100 |
| out/m12_2b/10182-1/balance | d2_noconnect | efd844 | 200 | 1 | 1 | 0.807 | 100 | — | 1 | 100 |
| out/m12_2b/10182-1/balance_bridge | d2_noconnect | efd844 | 200 | 0 | 0 | 0.807 | — | — | 0 | — |
| out/m12_2b/10182-1/balance_bridge_connect | pipeline | efd844 | 200 | 200 | 181 | 0.807 | 98 | 1.02 | 8 | 100 |
| out/m12_2b/10182-1/balance_connect | pipeline | efd844 | 200 | 200 | 181 | 0.807 | 98 | 1.03 | 8 | 100 |
| out/m12_2b/6372-1/balance | d2_noconnect | 8cb908 | 200 | 11 | 10 | 0.536 | 100 | 1.10 | 8 | 100 |
| out/m12_2b/6372-1/balance_bridge | d2_noconnect | 8cb908 | 200 | 14 | 13 | 0.536 | 100 | 0.89 | 8 | 100 |
| out/m12_2b/6372-1/balance_bridge_connect | pipeline | 8cb908 | 200 | 200 | 181 | 0.536 | 67 | 1.04 | 8 | 100 |
| out/m12_2b/6372-1/balance_connect | pipeline | 8cb908 | 200 | 200 | 181 | 0.536 | 74 | 1.09 | 8 | 100 |
| out/m12_demo/10182-1/d2 | pipeline | 666b85 | 100 | 100 | 91 | 0.145 | 48 | 1.04 | 4 | 100 |
| out/m12_demo/10182-1/d2_no_connect | d2_noconnect | 666b85 | 100 | 0 | 0 | 0.145 | — | — | 0 | — |
| out/m12_demo/374-1/d2 | pipeline | eae787 | 100 | 100 | 91 | 0.242 | 58 | 1.04 | 4 | 100 |
| out/m12_demo/374-1/d2_no_connect | d2_noconnect | eae787 | 100 | 0 | 0 | 0.242 | — | — | 0 | — |
| out/m12_demo/374-1/wfc | pipeline_wfc | eae787 | 10 | 0 | 0 | 0.242 | — | — | 0 | — |
| out/m12_demo/4956-1/d2 | pipeline | f2c099 | 100 | 100 | 91 | 0.235 | 66 | 1.08 | 4 | 100 |
| out/m12_demo/4956-1/d2_no_connect | d2_noconnect | f2c099 | 100 | 0 | 0 | 0.235 | — | — | 0 | — |
| out/m12_demo/4956-1/wfc | pipeline_wfc | f2c099 | 10 | 0 | 0 | 0.235 | — | — | 0 | — |
| out/m12_demo/5891-1/d2 | pipeline | f79978 | 100 | 100 | 92 | 0.224 | 48 | 1.03 | 4 | 100 |
| out/m12_demo/5891-1/d2_no_connect | d2_noconnect | f79978 | 100 | 0 | 0 | 0.224 | — | — | 0 | — |
| out/m12_demo/5891-1/wfc | pipeline_wfc | f79978 | 10 | 0 | 0 | 0.224 | — | — | 0 | — |
| out/m12_demo/6378-1/d2 | pipeline | e30ef4 | 100 | 100 | 91 | 0.281 | 20 | 0.97 | 4 | 100 |
| out/m12_demo/6378-1/d2_no_connect | d2_noconnect | e30ef4 | 100 | 0 | 0 | 0.281 | — | — | 0 | — |
| out/m12_demo/6378-1/wfc | pipeline_wfc | e30ef4 | 10 | 0 | 0 | 0.281 | — | — | 0 | — |
| out/m12_demo/7743-1/d2 | pipeline | 2c5d52 | 100 | 100 | 91 | 0.287 | 40 | 1.06 | 4 | 100 |
| out/m12_demo/7743-1/d2_no_connect | d2_noconnect | 2c5d52 | 100 | 0 | 0 | 0.287 | — | — | 0 | — |
| out/m12_demo/7743-1/wfc | pipeline_wfc | 2c5d52 | 10 | 0 | 0 | 0.287 | — | — | 0 | — |
| out/m12b_brickgpt/10182-1/4b15b71c_exact | pipeline | 9a3298 | 50 | 50 | 46 | 0.357 | 100 | 1.04 | 1 | 100 |
| out/m12b_brickgpt/10182-1/5c5f88b6_exact | pipeline | 45f609 | 0 | 0 | 0 | — | — | — | — | — |
| out/m12b_brickgpt/10182-1/858f0955_exact | pipeline | cf3bc4 | 50 | 50 | 46 | 3.180 | 4 | 0.57 | 1 | 100 |
| out/m12b_brickgpt/10182-1/a712684f_exact | pipeline | 5b8b50 | 50 | 50 | 46 | 2.737 | 4 | 0.61 | 1 | 100 |
| out/m12b_brickgpt/10182-1/d1137e5f_exact | pipeline | 9a921c | 50 | 50 | 46 | 0.231 | 100 | 1.05 | 1 | 100 |
| out/m12b_brickgpt/5891-1/4b15b71c_exact | pipeline | 8fed67 | 50 | 50 | 46 | 0.428 | 100 | 1.09 | 1 | 100 |
| out/m12b_brickgpt/5891-1/5c5f88b6_exact | pipeline | 5a6b0e | 50 | 50 | 46 | 0.326 | 100 | 1.02 | 1 | 100 |
| out/m12b_brickgpt/5891-1/858f0955_exact | pipeline | b96365 | 50 | 50 | 46 | 0.316 | 60 | 3.67 | 1 | 100 |
| out/m12b_brickgpt/5891-1/a712684f_exact | pipeline | 231828 | 50 | 50 | 46 | 0.580 | 74 | 1.03 | 1 | 100 |
| out/m12b_brickgpt/5891-1/d1137e5f_exact | pipeline | d9c5ad | 50 | 50 | 46 | 0.265 | 80 | 1.07 | 1 | 100 |
| out/m12b_brickgpt/6378-1/4b15b71c_exact | pipeline | 679ab5 | 50 | 50 | 46 | 0.523 | 92 | 1.05 | 1 | 100 |
| out/m12b_brickgpt/6378-1/5c5f88b6_exact | pipeline | 26d6e8 | 50 | 50 | 46 | 0.318 | 97 | 1.01 | 1 | 100 |
| out/m12b_brickgpt/6378-1/858f0955_exact | pipeline | b0e3d4 | 50 | 50 | 46 | 0.340 | 90 | 1.65 | 1 | 100 |
| out/m12b_brickgpt/6378-1/a712684f_exact | pipeline | ac553e | 50 | 50 | 46 | 0.460 | 75 | 2.49 | 1 | 100 |
| out/m12b_brickgpt/6378-1/d1137e5f_exact | pipeline | 4c91c2 | 50 | 50 | 46 | 0.305 | 91 | 1.04 | 1 | 100 |

## Appendix: raw profile

Effective share % at raw feature-distance thresholds (not comparable across setups; the dedupe threshold is 0.05).

| run | generator | raw mean distance | @0.05 | @0.1 | @0.2 | @0.3 | @0.5 |
|---|---|---|---|---|---|---|---|
| out/alt/10182-1 | pipeline | 0.336 | 100 | 100 | 100 | 27 | 8 |
| out/m12_2b/10182-1/balance | d2_noconnect | 0.000 | 100 | 100 | 100 | 100 | 100 |
| out/m12_2b/10182-1/balance_bridge | d2_noconnect | 0.000 | — | — | — | — | — |
| out/m12_2b/10182-1/balance_bridge_connect | pipeline | 0.820 | 100 | 100 | 100 | 100 | 64 |
| out/m12_2b/10182-1/balance_connect | pipeline | 0.828 | 100 | 100 | 100 | 100 | 65 |
| out/m12_2b/6372-1/balance | d2_noconnect | 0.590 | 100 | 100 | 100 | 100 | 39 |
| out/m12_2b/6372-1/balance_bridge | d2_noconnect | 0.477 | 100 | 100 | 100 | 90 | 12 |
| out/m12_2b/6372-1/balance_bridge_connect | pipeline | 0.557 | 100 | 100 | 98 | 40 | 2 |
| out/m12_2b/6372-1/balance_connect | pipeline | 0.582 | 100 | 100 | 99 | 45 | 2 |
| out/m12_demo/10182-1/d2 | pipeline | 0.151 | 98 | 8 | 1 | 1 | 1 |
| out/m12_demo/10182-1/d2_no_connect | d2_noconnect | 0.000 | — | — | — | — | — |
| out/m12_demo/374-1/d2 | pipeline | 0.252 | 100 | 90 | 5 | 2 | 1 |
| out/m12_demo/374-1/d2_no_connect | d2_noconnect | 0.000 | — | — | — | — | — |
| out/m12_demo/374-1/wfc | pipeline_wfc | 0.000 | — | — | — | — | — |
| out/m12_demo/4956-1/d2 | pipeline | 0.255 | 100 | 85 | 5 | 2 | 1 |
| out/m12_demo/4956-1/d2_no_connect | d2_noconnect | 0.000 | — | — | — | — | — |
| out/m12_demo/4956-1/wfc | pipeline_wfc | 0.000 | — | — | — | — | — |
| out/m12_demo/5891-1/d2 | pipeline | 0.231 | 100 | 65 | 4 | 1 | 1 |
| out/m12_demo/5891-1/d2_no_connect | d2_noconnect | 0.000 | — | — | — | — | — |
| out/m12_demo/5891-1/wfc | pipeline_wfc | 0.000 | — | — | — | — | — |
| out/m12_demo/6378-1/d2 | pipeline | 0.273 | 100 | 55 | 6 | 2 | 1 |
| out/m12_demo/6378-1/d2_no_connect | d2_noconnect | 0.000 | — | — | — | — | — |
| out/m12_demo/6378-1/wfc | pipeline_wfc | 0.000 | — | — | — | — | — |
| out/m12_demo/7743-1/d2 | pipeline | 0.305 | 100 | 96 | 9 | 2 | 1 |
| out/m12_demo/7743-1/d2_no_connect | d2_noconnect | 0.000 | — | — | — | — | — |
| out/m12_demo/7743-1/wfc | pipeline_wfc | 0.000 | — | — | — | — | — |
| out/m12b_brickgpt/10182-1/4b15b71c_exact | pipeline | 0.370 | 100 | 100 | 100 | 15 | 2 |
| out/m12b_brickgpt/10182-1/5c5f88b6_exact | pipeline | 0.000 | — | — | — | — | — |
| out/m12b_brickgpt/10182-1/858f0955_exact | pipeline | 1.824 | 100 | 66 | 15 | 7 | 5 |
| out/m12b_brickgpt/10182-1/a712684f_exact | pipeline | 1.670 | 100 | 100 | 37 | 23 | 6 |
| out/m12b_brickgpt/10182-1/d1137e5f_exact | pipeline | 0.243 | 100 | 100 | 14 | 3 | 2 |
| out/m12b_brickgpt/5891-1/4b15b71c_exact | pipeline | 0.465 | 100 | 100 | 100 | 44 | 4 |
| out/m12b_brickgpt/5891-1/5c5f88b6_exact | pipeline | 0.332 | 100 | 100 | 73 | 7 | 2 |
| out/m12b_brickgpt/5891-1/858f0955_exact | pipeline | 1.160 | 100 | 97 | 23 | 7 | 5 |
| out/m12b_brickgpt/5891-1/a712684f_exact | pipeline | 0.596 | 100 | 100 | 94 | 67 | 7 |
| out/m12b_brickgpt/5891-1/d1137e5f_exact | pipeline | 0.284 | 100 | 97 | 22 | 4 | 2 |
| out/m12b_brickgpt/6378-1/4b15b71c_exact | pipeline | 0.548 | 100 | 100 | 100 | 69 | 6 |
| out/m12b_brickgpt/6378-1/5c5f88b6_exact | pipeline | 0.319 | 100 | 100 | 65 | 6 | 2 |
| out/m12b_brickgpt/6378-1/858f0955_exact | pipeline | 0.561 | 100 | 100 | 70 | 9 | 3 |
| out/m12b_brickgpt/6378-1/a712684f_exact | pipeline | 1.147 | 100 | 100 | 91 | 30 | 5 |
| out/m12b_brickgpt/6378-1/d1137e5f_exact | pipeline | 0.316 | 100 | 100 | 43 | 5 | 2 |
