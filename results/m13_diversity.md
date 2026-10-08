# M13: diversity of the generators' candidates

`python -m brickwfc.experiments.diversity_pass` (`funnel/diversity.py`). Per alt run: the effective number of distinct designs (Leinster-Cobbold order 1, threshold = the run's dedupe threshold) among the verified candidates and among the selected top-k; share = effective / designs.

## Per generator (mean over runs)

| generator | runs | verified per run | effective share % | mean distance | selected: effective share % |
|---|---|---|---|---|---|
| d2_noconnect | 3 | 8 | 100.0 | 0.356 | 100.0 |
| pipeline | 22 | 81 | 99.9 | 0.615 | 100.0 |
| pipeline_wfc | 0 | — | — | — | — |

The share at the dedupe threshold is close to 100% almost everywhere: at that distance nearly every verified candidate is distinct. The profile below (share % at larger thresholds) is what separates runs; compare generators only on runs of the same setup.

## Per run

| run | generator | candidates | valid | verified | effective | share % | mean distance | share % @0.05 | share % @0.1 | share % @0.2 | share % @0.3 | share % @0.5 | selected | selected effective |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| out/alt/10182-1 | pipeline | 200 | 14 | 13 | 13.0 | 100 | 0.336 | 100 | 100 | 100 | 27 | 8 | 8 | 8.0 |
| out/m12_2b/10182-1/balance | d2_noconnect | 200 | 1 | 1 | 1.0 | 100 | 0.000 | 100 | 100 | 100 | 100 | 100 | 1 | 1.0 |
| out/m12_2b/10182-1/balance_bridge | d2_noconnect | 200 | 0 | 0 | 0.0 | — | 0.000 | — | — | — | — | — | 0 | 0.0 |
| out/m12_2b/10182-1/balance_bridge_connect | pipeline | 200 | 200 | 181 | 181.0 | 100 | 0.820 | 100 | 100 | 100 | 100 | 64 | 8 | 8.0 |
| out/m12_2b/10182-1/balance_connect | pipeline | 200 | 200 | 181 | 181.0 | 100 | 0.828 | 100 | 100 | 100 | 100 | 65 | 8 | 8.0 |
| out/m12_2b/6372-1/balance | d2_noconnect | 200 | 11 | 10 | 10.0 | 100 | 0.590 | 100 | 100 | 100 | 100 | 39 | 8 | 8.0 |
| out/m12_2b/6372-1/balance_bridge | d2_noconnect | 200 | 14 | 13 | 13.0 | 100 | 0.477 | 100 | 100 | 100 | 90 | 12 | 8 | 8.0 |
| out/m12_2b/6372-1/balance_bridge_connect | pipeline | 200 | 200 | 181 | 181.0 | 100 | 0.557 | 100 | 100 | 98 | 40 | 2 | 8 | 8.0 |
| out/m12_2b/6372-1/balance_connect | pipeline | 200 | 200 | 181 | 181.0 | 100 | 0.582 | 100 | 100 | 99 | 45 | 2 | 8 | 8.0 |
| out/m12_demo/10182-1/d2 | pipeline | 100 | 100 | 91 | 89.6 | 98 | 0.151 | 98 | 8 | 1 | 1 | 1 | 4 | 4.0 |
| out/m12_demo/10182-1/d2_no_connect | d2_noconnect | 100 | 0 | 0 | 0.0 | — | 0.000 | — | — | — | — | — | 0 | 0.0 |
| out/m12_demo/374-1/d2 | pipeline | 100 | 100 | 91 | 91.0 | 100 | 0.252 | 100 | 90 | 5 | 2 | 1 | 4 | 4.0 |
| out/m12_demo/374-1/d2_no_connect | d2_noconnect | 100 | 0 | 0 | 0.0 | — | 0.000 | — | — | — | — | — | 0 | 0.0 |
| out/m12_demo/374-1/wfc | pipeline_wfc | 10 | 0 | 0 | 0.0 | — | 0.000 | — | — | — | — | — | 0 | 0.0 |
| out/m12_demo/4956-1/d2 | pipeline | 100 | 100 | 91 | 91.0 | 100 | 0.255 | 100 | 85 | 5 | 2 | 1 | 4 | 4.0 |
| out/m12_demo/4956-1/d2_no_connect | d2_noconnect | 100 | 0 | 0 | 0.0 | — | 0.000 | — | — | — | — | — | 0 | 0.0 |
| out/m12_demo/4956-1/wfc | pipeline_wfc | 10 | 0 | 0 | 0.0 | — | 0.000 | — | — | — | — | — | 0 | 0.0 |
| out/m12_demo/5891-1/d2 | pipeline | 100 | 100 | 92 | 92.0 | 100 | 0.231 | 100 | 65 | 4 | 1 | 1 | 4 | 4.0 |
| out/m12_demo/5891-1/d2_no_connect | d2_noconnect | 100 | 0 | 0 | 0.0 | — | 0.000 | — | — | — | — | — | 0 | 0.0 |
| out/m12_demo/5891-1/wfc | pipeline_wfc | 10 | 0 | 0 | 0.0 | — | 0.000 | — | — | — | — | — | 0 | 0.0 |
| out/m12_demo/6378-1/d2 | pipeline | 100 | 100 | 91 | 91.0 | 100 | 0.273 | 100 | 55 | 6 | 2 | 1 | 4 | 4.0 |
| out/m12_demo/6378-1/d2_no_connect | d2_noconnect | 100 | 0 | 0 | 0.0 | — | 0.000 | — | — | — | — | — | 0 | 0.0 |
| out/m12_demo/6378-1/wfc | pipeline_wfc | 10 | 0 | 0 | 0.0 | — | 0.000 | — | — | — | — | — | 0 | 0.0 |
| out/m12_demo/7743-1/d2 | pipeline | 100 | 100 | 91 | 91.0 | 100 | 0.305 | 100 | 96 | 9 | 2 | 1 | 4 | 4.0 |
| out/m12_demo/7743-1/d2_no_connect | d2_noconnect | 100 | 0 | 0 | 0.0 | — | 0.000 | — | — | — | — | — | 0 | 0.0 |
| out/m12_demo/7743-1/wfc | pipeline_wfc | 10 | 0 | 0 | 0.0 | — | 0.000 | — | — | — | — | — | 0 | 0.0 |
| out/m12b_brickgpt/10182-1/4b15b71c_exact | pipeline | 50 | 50 | 46 | 46.0 | 100 | 0.370 | 100 | 100 | 100 | 15 | 2 | 1 | 1.0 |
| out/m12b_brickgpt/10182-1/858f0955_exact | pipeline | 50 | 50 | 46 | 46.0 | 100 | 1.824 | 100 | 66 | 15 | 7 | 5 | 1 | 1.0 |
| out/m12b_brickgpt/10182-1/a712684f_exact | pipeline | 50 | 50 | 46 | 46.0 | 100 | 1.670 | 100 | 100 | 37 | 23 | 6 | 1 | 1.0 |
| out/m12b_brickgpt/5891-1/4b15b71c_exact | pipeline | 50 | 50 | 46 | 46.0 | 100 | 0.465 | 100 | 100 | 100 | 44 | 4 | 1 | 1.0 |
| out/m12b_brickgpt/5891-1/858f0955_exact | pipeline | 50 | 50 | 46 | 46.0 | 100 | 1.160 | 100 | 97 | 23 | 7 | 5 | 1 | 1.0 |
| out/m12b_brickgpt/5891-1/a712684f_exact | pipeline | 50 | 50 | 46 | 46.0 | 100 | 0.596 | 100 | 100 | 94 | 67 | 7 | 1 | 1.0 |
| out/m12b_brickgpt/5891-1/d1137e5f_exact | pipeline | 50 | 50 | 46 | 46.0 | 100 | 0.284 | 100 | 97 | 22 | 4 | 2 | 1 | 1.0 |
| out/m12b_brickgpt/6378-1/4b15b71c_exact | pipeline | 50 | 50 | 46 | 46.0 | 100 | 0.548 | 100 | 100 | 100 | 69 | 6 | 1 | 1.0 |
| out/m12b_brickgpt/6378-1/858f0955_exact | pipeline | 50 | 50 | 46 | 46.0 | 100 | 0.561 | 100 | 100 | 70 | 9 | 3 | 1 | 1.0 |
| out/m12b_brickgpt/6378-1/a712684f_exact | pipeline | 50 | 50 | 46 | 46.0 | 100 | 1.147 | 100 | 100 | 91 | 30 | 5 | 1 | 1.0 |
| out/m12b_brickgpt/6378-1/d1137e5f_exact | pipeline | 50 | 50 | 46 | 46.0 | 100 | 0.316 | 100 | 100 | 43 | 5 | 2 | 1 | 1.0 |
