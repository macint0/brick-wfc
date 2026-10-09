"""M12b step 2, phase 2: learned proposal vs statistics with a target shape (a BrickGPT object), from pipeline runs.

    python -m brickwfc.alt 7796-1 --shape brickgpt:4b15b71c-f400-4e54-a118-f0c2afba6e17 --n 20 \\
        --no-supports --max-clutch inf \\
        --out out/m12b_proposal_shape/7796-1/stats_random                       # and --order raster,
    python -m brickwfc.experiments.proposal_shape --dir out/m12b_proposal_shape \\
        --weights data/models/proposal_run2.npz --figure-set 7796-1             # --order raster --proposal ...

Reads one pipeline run folder per (set, arm) under ``--dir`` (``<set>/<arm>``, arms as in
``experiments.proposal``) and builds nothing. Per set and arm, over the candidates: valid, physics and
one-piece shares; over the valid builds: object fill and IoU against the target, utilization, the M10
size-matched judge against the real set (``style.size_matched``, the set's learned statistics, as in
``experiments.style.evaluate``), and parts outside the model's vocabulary; seconds per candidate (generation +
physics). The sheet shows one set's three arms with the same seed (the first seed valid in all three).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Sequence

import numpy as np

from brickwfc.alt.features import occupancy
from brickwfc.alt.inputs import SETS_FILE, STYLE_DIR, learned_style, load_source
from brickwfc.alt.target import load_target
from brickwfc.bricks.build import save_preview
from brickwfc.bricks.inventory import target_volume, utilization
from brickwfc.bricks.shapes import fill, iou
from brickwfc.bricks.style import StyleStats, distance, events, judge, size_matched
from brickwfc.bricks.tokens import Vocab
from brickwfc.bricks.voxelize import voxelize
from brickwfc.experiments.demo import labeled_sheet, load_run
from brickwfc.experiments.proposal import CONDITIONS
from brickwfc.ldraw.mpd import flatten


def mean(values: Sequence[float]) -> float:
    return statistics.fmean(values) if values else math.nan


def summarize(set_number: str, arm: str, directory: Path, vocab: Vocab, style_dir: Path = STYLE_DIR,
              sets_file: Path = SETS_FILE) -> dict:
    """``set_number``: the run's input (a set number, or a model file)."""
    candidates, stats = load_run(directory)
    source = load_source(set_number)
    style, _ = learned_style(source.name, style_dir, sets_file)
    target = load_target(stats["config"]["shape"], target_volume(source.inventory, stats["config"].get("sizing", "box")),
                         source.colors)
    if int(target.mask.sum()) != stats["shape_cells"]:
        raise ValueError(f"{directory}: target has {int(target.mask.sum())} cells, the run had {stats['shape_cells']}")
    real_parts = voxelize(flatten(source.model))[0]
    real, real_stats = events(real_parts), StyleStats().add(real_parts)
    built = [c for c in candidates if "generate" not in c.failed]
    valid = [c for c in candidates if c.valid]
    filled = [occupancy(c.placed, target.mask.shape) for c in valid]
    judged = [size_matched(events(c.placed), real, style, np.random.default_rng([c.seed, judge(c.placed, style).events]))
              for c in valid]
    return {
        "set": set_number, "arm": arm, "inventory_parts": source.recognized_parts, "candidates": len(candidates),
        "target_cells": stats["shape_cells"], "grid_YZX": stats["grid_YZX"],
        "valid_pct": 100 * len(valid) / len(candidates),
        "physics_pct": 100 * mean([float("physics" not in c.failed) for c in built]),
        "one_piece_pct": 100 * mean([float(c.clusters == 1) for c in built]),
        "fill_pct": 100 * mean([fill(f, target.mask) for f in filled]),
        "fill_pct_sd": 100 * statistics.stdev([fill(f, target.mask) for f in filled]) if len(filled) > 1 else math.nan,
        "iou": mean([iou(f, target.mask) for f in filled]),
        "utilization_pct": 100 * mean([utilization(list(c.placed), source.inventory) for c in valid]),
        "matched_judge": mean([j for j, _, _ in judged]),
        "matched_judge_sd": statistics.stdev([j for j, _, _ in judged]) if len(judged) > 1 else math.nan,
        "matched_ceiling": mean([r for _, r, _ in judged]),
        "distance": mean([distance(StyleStats().add(c.placed), real_stats)["mean"] for c in valid]),
        "parts": mean([len(c.placed) for c in valid]),
        "outside_vocab": mean([sum(vocab.shape(p.shape) is None for p in c.placed) for c in valid]),
        "seconds_per_candidate": mean([c.seconds + c.physics_seconds for c in candidates]),
        "check_failures": stats["check_failures"],
        "valid_seeds": [c.seed for c in valid],
    }


def table(rows: list[dict]) -> str:
    lines = ["| set | arm | candidates | valid % | physics % | one piece % | object fill % (sd) | IoU | utilization % | "
             "size-matched judge (sd) | real ceiling | distance to set | parts | outside vocab / build | s/candidate |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['set']} | {r['arm']} | {r['candidates']} | {r['valid_pct']:.0f} | {r['physics_pct']:.0f} | "
                     f"{r['one_piece_pct']:.0f} | {r['fill_pct']:.1f} ({r['fill_pct_sd']:.1f}) | {r['iou']:.3f} | {r['utilization_pct']:.1f} | "
                     f"{r['matched_judge']:.4f} ({r['matched_judge_sd']:.4f}) | {r['matched_ceiling']:.4f} | {r['distance']:.4f} | "
                     f"{r['parts']:.0f} | {r['outside_vocab']:.1f} | {r['seconds_per_candidate']:.1f} |")
    lines += [""]
    by = {(r["set"], r["arm"]): r for r in rows}
    sets = list(dict.fromkeys(r["set"] for r in rows))
    for a, b in (("proposal_raster", "stats_raster"), ("proposal_raster", "stats_random"), ("stats_raster", "stats_random")):
        both = [s for s in sets if (s, a) in by and (s, b) in by]
        if not both:
            continue
        for key, label in (("matched_judge", "size-matched judge"), ("fill_pct", "object fill"),
                           ("distance", "distance to the set's own statistics (lower is closer)")):
            diffs = [by[s, a][key] - by[s, b][key] for s in both]
            lines.append(f"- {a} vs {b}, {label}: higher on {sum(d > 0 for d in diffs)}/{len(both)} sets "
                         f"(mean difference {statistics.fmean(diffs):+.4f})")
    return "\n".join(lines) + "\n"


def sheet(rows: list[dict], set_dir: Path, set_number: str, out: Path) -> int:
    """The three arms of ``set_number`` (runs in ``set_dir``/<arm>) with the first seed valid in all of them;
    returns that seed."""
    mine = [r for r in rows if r["set"] == set_number]
    seed = min(set.intersection(*(set(r["valid_seeds"]) for r in mine)))
    images, labels = [], []
    for r in mine:
        run = set_dir / r["arm"]
        candidates, stats = load_run(run)
        placed = next(c for c in candidates if c.seed == seed).placed
        path = run / f"seed{seed}_preview.png"
        save_preview(list(placed), tuple(stats["grid_YZX"]), path)
        images.append(path)
        labels.append(f"{set_number}, seed {seed}: {r['arm']}\n{len(placed)} parts\n"
                      f"arm means: fill {r['fill_pct']:.0f}%, judge {r['matched_judge']:.3f}")
    out.parent.mkdir(parents=True, exist_ok=True)
    labeled_sheet(images, labels, out, columns=len(images))
    return seed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.proposal_shape", description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=Path("out/m12b_proposal_shape"))
    parser.add_argument("--weights", type=Path, required=True, help="the model's .npz (vocab.json next to it)")
    parser.add_argument("--figure-set", help="set of the side-by-side sheet (default: none)")
    parser.add_argument("--figure", type=Path, default=Path("results/m12b_proposal_shape.png"))
    parser.add_argument("--json", type=Path, help="write the summaries here")
    args = parser.parse_args(argv)

    vocab = Vocab.load(args.weights.with_name("vocab.json"))
    sets = sorted((d.name for d in args.dir.iterdir() if d.is_dir()),
                  key=lambda s: load_source(s).recognized_parts)
    rows = [summarize(s, arm, args.dir / s / arm, vocab) for s in sets for arm in CONDITIONS
            if (args.dir / s / arm / "stats.json").exists()]
    print(table(rows))
    if args.figure_set:
        seed = sheet(rows, args.dir / args.figure_set, args.figure_set, args.figure)
        print(f"wrote {args.figure} (seed {seed})")
    if args.json:
        args.json.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
