# M12d looks — the selected builds before and after the catalog

**Branch `m12d-looks`.** Sheet: `m12d_looks_sheet.png` (pairs as rows, old | new as columns; each cell shows the
selected build as written (recoloured), the same build as generated, and its missing map with unfilled target cells in
red). Numbers: `m12d_looks.json`. Driver: `experiments/looks.py`.

## Setup

- **Pairs:** the 9 sweep pairs (6378-1, 5891-1, 4956-1 × chair, table, car), 50 candidates per pair and arm, seeds 0–49
  in both arms.
- **Flags, the same in both arms:** `--order connected --reserve-small --regrow --skin --symmetric --recolor
  --fill-slack 0.8`. Sizing and the hole pass are the 3D-target defaults (usable sizing, `--holes --hang`). Parts that
  fit nowhere in the build space are left out of the tileset in both arms (the default since the M12d follow-up).
- **Arms:**
  - **old** = `--catalog m12b --style-version v2` (88 parts);
  - **new** = the defaults (183 parts, style v3).
- **Targets differ** where the new catalog recognizes more of the set. At the same slack, more recognized parts mean
  more volume and so a larger object:
  - 5891-1: volume 2306 → 2411–2555 cells;
  - 4956-1: volume 3429–3506 → 3763–3891 cells;
  - 6378-1: volume +3 cells (two jumpers).

  A small change of scale can also move the mirror plane or the resampling phase:
  - the 6378-1 table has 1384 vs 1522 target cells at nearly the same volume, because the plane falls at x = 7.5 vs 8;
  - the 5891-1 chair's plane flips from x to z;
  - the 5891-1 table's plane flips from z to x, and its top has 4 full 4×4 windows instead of 145.

  Only the 6378-1 chair and car have identical targets in both arms. Each build is measured against its own target.
- **Run:**
  - 65 min of pipeline wall time on 5 workers;
  - the low-memory guard killed the run once at 16 of 18 runs; the last pair (4956-1 car) was rerun on 4 workers;
  - the worker count does not change the candidates.
- **Contact judge:** reported, not deciding. The two arms' judges are against different statistics (v2 vs v3), so
  they are not comparable across arms.
- **Recolouring:** replayed exactly as the pipeline did it; the seam share matches the pipeline's in all 18 runs.

## The adoption question

**Does the new catalog change how the selected builds look? A little, and not by the metrics; where it changes them,
it is mostly for the worse.**

- **Same objects, a few new parts.**
  - New parts are 95 of the 2,642 parts in the nine selected builds (3.6%). On 6378-1 they are 0: its only new parts
    are two jumpers, and no selected build uses them.
  - On the 5891-1 and 4956-1 pairs they are 10–21 per build, 3–11% of the skin faces.
- **The preview cannot show them.** The preview renderer draws every part as its cell box (slopes aside), so a window
  frame, a panel, a door rail or a cone looks like a plain brick on the sheet. Glass is not drawn at all. What the
  sheet shows as "different" between the arms is mostly the different target (scale, plane), the different build
  from the same seed, and the colouring, not the new parts. The new parts' look can only be judged in Studio (see
  "For Mac" below).
- **Metrics on the selected build, old → new, new better / worse / equal over the 9 pairs:**
  - fill 5 / 4 / 0;
  - largest hole 4 / 4 / 1;
  - surface 6 / 3 / 0;
  - distinct parts per top 4×4 window 3 / 6 / 0 (cleaner tops are fewer parts per window);
  - per side window 8 / 1 / 0;
  - mirrored share 4 / 4 / 1;
  - same-colour seams after recolouring 1 / 8 / 0;
  - valid candidates 0 / 5 / 4.
- **Means over the valid candidates of each run, averaged over the 9 pairs, old → new:**
  - fill 91.3 → 91.9%;
  - largest hole 125 → 108 cells;
  - surface 89.5 → 91.5%;
  - top parts per window 5.06 → 4.99;
  - side parts per window 3.69 → 3.62;
  - mirrored 36.8 → 34.1%;
  - distinct part names 37.0 → 41.2;
  - valid candidates 430 → 417 of 450.
- **Completeness is lost.**
  - Complete candidates: **21 → 3** of the valid ones.
  - Old completes on the 6378-1 chair (3), the 5891-1 chair (13) and the 5891-1 table (5). New completes on the 6378-1
    chair (2) and the 6378-1 car (1).
  - Selected builds complete: 3 → 2.
  - The 5891-1 pairs lose most: their targets grow 5–11% at the same slack (more recognized parts, more volume), and
    the new parts are large and hard to pack (1×4×3 windows, 1×4×6 door frame). The 5891-1 table's selected build
    falls from 99.7% fill / hole 2 to 88.2% / hole 203; its target flipped plane, as above.
- **Colour is worse.**
  - Same-colour seams are lower on 8 of 9 pairs both before recolouring (mean 44.9 → 41.0%) and after
    (58.1 → 54.8%).
  - A likely reason, not checked: recolouring permutes colours within a part type, and the new catalog splits the
    same number of parts over more types (up to 52 names per build vs 44), so each type has fewer parts to swap.
- **Time:** 14.2 → 21.2 s per candidate on average (generation + physics CPU). That is 0.8–1.1× on 6378-1 and
  1.2–2.0× on the two larger sets, partly because their targets are larger.

## Where the new parts show up: skin vs interior

- **Almost always on the skin.** 92 of the 95 new parts in the selected builds show at least one face outside, against
  85% of all parts in the same builds (2,238 of 2,642). These are thin objects, where most parts touch the skin
  anyway; the new parts touch it a little more often than the average part.
- **What they are:**
  - lookalike boxes: cones 4589, Technic brick 6541, panel 4865a;
  - window and door frames, with their glass fitted in four builds: 7, 8, 3 and 6 pieces;
  - door rails and brackets, whose keep-out faces are open by construction;
  - curved and triple slopes, 1×6 arches, 2×16 plates.
- **So the new parts do sit where the eye would see them.** But in the preview they look like boxes, and the
  colouring treats them as part types of their own.

## Tables

Per pair and arm (sel: the selected build; mean: over the valid candidates):

| object | set | arm | target cells | valid | s / cand. | fill % (sel / mean) | largest hole (sel / mean) | surface % (sel / mean) | complete (sel; valid) | top parts / 4x4 (sel / mean) | side parts / 4x4 (sel / mean) | mirrored % (sel / mean) | mirrored of mirrorable % (sel) | seams % (raw -> recoloured) | part names (sel / mean) | new parts: placed / on skin (sel) | new share of skin faces % (sel / mean) | judge (sel) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| chair | 6378-1 | old | 1149 | 49/50 | 3.1 | 99.3 / 95.3 | 4 / 28 | 99.2 / 94.6 | yes; 3 | 5.67 / 5.11 | 4.02 / 4.18 | 7 / 11 | 19 | 49 -> 62 | 28 / 27.5 | 0 / 0 | 0.0 / 0.0 | -0.3098 |
| chair | 6378-1 | new | 1149 | 49/50 | 3.2 | 98.7 / 95.4 | 4 / 26 | 98.5 / 94.7 | yes; 2 | 6.22 / 4.91 | 4.52 / 4.18 | 7 / 10 | 21 | 42 -> 60 | 28 / 28.0 | 0 / 0 | 0.0 / 0.4 | -0.3400 |
| chair | 5891-1 | old | 2335 | 50/50 | 14.9 | 99.8 / 97.3 | 2 / 36 | 99.8 / 96.5 | yes; 13 | 5.20 / 5.99 | 3.60 / 3.54 | 37 / 32 | 63 | 34 -> 54 | 39 / 37.4 | 0 / 0 | 0.0 / 0.0 | -0.3180 |
| chair | 5891-1 | new | 2625 | 48/50 | 30.0 | 97.1 / 94.7 | 13 / 41 | 96.2 / 93.1 | no; 0 | 7.13 / 5.13 | 3.27 / 3.60 | 18 / 21 | 28 | 31 -> 50 | 46 / 45.1 | 18 / 18 | 10.6 / 10.0 | -0.3439 |
| chair | 4956-1 | old | 3492 | 46/50 | 20.3 | 97.1 / 93.6 | 33 / 95 | 95.8 / 91.5 | no; 0 | 2.71 / 5.27 | 3.42 / 3.23 | 31 / 22 | 46 | 62 -> 67 | 38 / 40.4 | 0 / 0 | 0.0 / 0.0 | -0.2619 |
| chair | 4956-1 | new | 3868 | 41/50 | 30.6 | 97.3 / 93.7 | 36 / 95 | 96.8 / 92.5 | no; 0 | 4.78 / 5.62 | 3.33 / 3.17 | 29 / 20 | 45 | 50 -> 58 | 46 / 46.6 | 19 / 19 | 9.3 / 10.0 | -0.2706 |
| table | 6378-1 | old | 1384 | 50/50 | 3.5 | 91.6 / 86.2 | 92 / 92 | 88.2 / 80.3 | no; 0 | 5.90 / 4.83 | 3.48 / 3.77 | 58 / 50 | 58 | 43 -> 61 | 30 / 29.2 | 0 / 0 | 0.0 / 0.0 | -0.3622 |
| table | 6378-1 | new | 1522 | 50/50 | 2.9 | 98.5 / 91.5 | 7 / 48 | 97.8 / 90.5 | no; 0 | 3.28 / 4.00 | 3.22 / 3.31 | 32 / 26 | 32 | 42 -> 56 | 30 / 30.7 | 0 / 0 | 0.0 / 0.5 | -0.3675 |
| table | 5891-1 | old | 2384 | 49/50 | 18.3 | 99.7 / 94.8 | 2 / 56 | 99.5 / 94.5 | yes; 5 | 5.53 / 6.28 | 4.01 / 3.60 | 44 / 46 | 44 | 33 -> 43 | 41 / 43.0 | 0 / 0 | 0.0 / 0.0 | -0.3843 |
| table | 5891-1 | new | 2422 | 48/50 | 25.0 | 88.2 / 88.2 | 203 / 156 | 86.7 / 87.3 | no; 0 | 5.00 / 6.25 | 3.71 / 3.69 | 49 / 52 | 49 | 32 -> 50 | 43 / 42.6 | 10 / 9 | 3.1 / 3.5 | -0.3565 |
| table | 4956-1 | old | 3704 | 37/50 | 29.3 | 93.5 / 88.5 | 208 / 296 | 89.2 / 83.5 | no; 0 | 5.40 / 5.92 | 3.51 / 3.37 | 35 / 46 | 35 | 55 -> 62 | 44 / 41.5 | 0 / 0 | 0.0 / 0.0 | -0.2835 |
| table | 4956-1 | new | 3850 | 35/50 | 35.9 | 99.0 / 93.5 | 15 / 100 | 98.3 / 90.7 | no; 0 | 7.50 / 6.28 | 3.37 / 3.38 | 47 / 40 | 47 | 52 -> 61 | 47 / 48.6 | 14 / 14 | 5.7 / 7.8 | -0.2820 |
| car | 6378-1 | old | 1428 | 50/50 | 2.1 | 94.3 / 89.8 | 72 / 84 | 94.7 / 90.9 | no; 0 | 1.00 / 2.71 | 4.94 / 3.78 | 58 / 54 | 58 | 46 -> 66 | 27 / 28.8 | 0 / 0 | 0.0 / 0.0 | -0.3447 |
| car | 6378-1 | new | 1428 | 50/50 | 2.4 | 99.9 / 91.4 | 1 / 65 | 99.9 / 92.3 | yes; 1 | 6.53 / 2.69 | 3.92 / 4.00 | 64 / 54 | 64 | 42 -> 59 | 28 / 29.5 | 0 / 0 | 0.0 / 0.3 | -0.3666 |
| car | 5891-1 | old | 2566 | 50/50 | 15.4 | 94.7 / 92.0 | 28 / 63 | 92.7 / 91.7 | no; 0 | 4.93 / 4.86 | 3.59 / 4.33 | 60 / 48 | 60 | 31 -> 50 | 41 / 42.9 | 0 / 0 | 0.0 / 0.0 | -0.3485 |
| car | 5891-1 | new | 2934 | 50/50 | 25.6 | 94.9 / 92.1 | 77 / 69 | 96.0 / 93.4 | no; 0 | 4.78 / 5.15 | 3.58 / 4.05 | 35 / 43 | 35 | 29 -> 41 | 49 / 49.6 | 21 / 19 | 8.9 / 9.3 | -0.3484 |
| car | 4956-1 | old | 3788 | 49/50 | 21.3 | 91.0 / 84.4 | 219 / 376 | 89.9 / 82.5 | no; 0 | 4.25 / 4.58 | 3.52 / 3.39 | 22 / 24 | 22 | 51 -> 59 | 42 / 42.6 | 0 / 0 | 0.0 / 0.0 | -0.2669 |
| car | 4956-1 | new | 4248 | 46/50 | 35.2 | 89.8 / 86.6 | 100 / 374 | 91.2 / 88.6 | no; 0 | 4.96 / 4.86 | 3.49 / 3.24 | 41 / 41 | 41 | 51 -> 58 | 52 / 50.0 | 13 / 13 | 4.4 / 10.7 | -0.2793 |

Selected builds, old -> new (+ new better, - worse):

| object | set | fill % | largest hole | surface % | top parts / 4x4 | side parts / 4x4 | mirrored % | seams % (recoloured) | valid |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| chair | 6378-1 | 99.3 -> 98.7 - | 4 -> 4 = | 99.2 -> 98.5 - | 5.67 -> 6.22 - | 4.02 -> 4.52 - | 7 -> 7 = | 62 -> 60 - | 49 -> 49 = |
| chair | 5891-1 | 99.8 -> 97.1 - | 2 -> 13 - | 99.8 -> 96.2 - | 5.20 -> 7.13 - | 3.60 -> 3.27 + | 37 -> 18 - | 54 -> 50 - | 50 -> 48 - |
| chair | 4956-1 | 97.1 -> 97.3 + | 33 -> 36 - | 95.8 -> 96.8 + | 2.71 -> 4.78 - | 3.42 -> 3.33 + | 31 -> 29 - | 67 -> 58 - | 46 -> 41 - |
| table | 6378-1 | 91.6 -> 98.5 + | 92 -> 7 + | 88.2 -> 97.8 + | 5.90 -> 3.28 + | 3.48 -> 3.22 + | 58 -> 32 - | 61 -> 56 - | 50 -> 50 = |
| table | 5891-1 | 99.7 -> 88.2 - | 2 -> 203 - | 99.5 -> 86.7 - | 5.53 -> 5.00 + | 4.01 -> 3.71 + | 44 -> 49 + | 43 -> 50 + | 49 -> 48 - |
| table | 4956-1 | 93.5 -> 99.0 + | 208 -> 15 + | 89.2 -> 98.3 + | 5.40 -> 7.50 - | 3.51 -> 3.37 + | 35 -> 47 + | 62 -> 61 - | 37 -> 35 - |
| car | 6378-1 | 94.3 -> 99.9 + | 72 -> 1 + | 94.7 -> 99.9 + | 1.00 -> 6.53 - | 4.94 -> 3.92 + | 58 -> 64 + | 66 -> 59 - | 50 -> 50 = |
| car | 5891-1 | 94.7 -> 94.9 + | 28 -> 77 - | 92.7 -> 96.0 + | 4.93 -> 4.78 + | 3.59 -> 3.58 + | 60 -> 35 - | 50 -> 41 - | 50 -> 50 = |
| car | 4956-1 | 91.0 -> 89.8 - | 219 -> 100 + | 89.9 -> 91.2 + | 4.25 -> 4.96 - | 3.52 -> 3.49 + | 22 -> 41 + | 59 -> 58 - | 49 -> 46 - |
| | **new better / worse / equal** | 5 / 4 / 0 | 4 / 4 / 1 | 6 / 3 / 0 | 3 / 6 / 0 | 8 / 1 / 0 | 4 / 4 / 1 | 1 / 8 / 0 | 0 / 5 / 4 |

The new arm's M12d parts in its selected builds, by kind:

| kind | placed | on the skin | part names |
|---|---:|---:|---|
| plain | 3 | 3 | plate2x16 |
| lookalike | 34 | 31 | brick1x1_4589, brick1x1_6541, panel1x2x1_4865a |
| per-cell | 5 | 5 | arch1x6 |
| slope/curved | 9 | 9 | curved1x2x4_6091, slope45triple_1x2 |
| frame | 24 | 24 | doorframe1x4x6_60596, fence1x4x2_3185, window1x2x2_60592, window1x4x3_60594, window1x4x3_6556 |
| keep-out | 20 | 20 | bracket1x2_2x2_44728, doorrail1x2_32028, doorrail1x8_4510 |
| all | 95 | 92 | |

## For Mac

Open these in Studio to judge the new parts with their real geometry:
- `out/m12d_looks/new/5891-1/chair/build_01.ldr`: 18 new parts, frames with 7 glass pieces;
- `out/m12d_looks/new/5891-1/car/build_01.ldr`: 21 new parts, 6 glass;
- `out/m12d_looks/new/4956-1/chair/build_01.ldr`: 19 new parts, door rails, brackets, 8 glass.

The `old/` folders hold the same pairs on the M12b catalog for comparison.

## Read

- **On this bench and these flags, the bigger catalog does not make the selected builds look better by any metric
  we have.**
  - It costs completeness (21 → 3 complete candidates), colour coherence (8/9 worse) and 1.5× the time.
  - Its parts reach the skin, but the previews cannot show them. The eye test on the sheet is mostly a test of
    different targets and colourings.
- **Two confounds are built into "same flags".**
  - The target grows with the recognized volume.
  - Recolouring works within part types.
- **A cleaner test of the catalog alone would:**
  - size both arms to the same volume (e.g. the old arm's);
  - recolour across lookalike types (a cone and a 1×1 brick are interchangeable for colour).

  Neither is run here.
