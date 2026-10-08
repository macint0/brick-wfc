"""M12b step 1a: BrickGPT's structures as true 3D targets, and a head-to-head on their data.

    python -m brickwfc.experiments.brickgpt --out out/m12b_brickgpt

Objects: from the StableText2Brick test split (``bricks.brickgpt``), the median-size structure (by brick
count, ties by id) of each of the ``--categories`` most common categories. This compares against
BrickGPT's *data*, not its model (which needs a GPU, a gated Llama checkpoint and Gurobi): their
structure for an object is built from unlimited bricks of 8 sizes; ours is the alternate-build pipeline
(``alt``: D2, ``--n`` candidates, top-judged build) from one real set's inventory, with the structure's
exact cells as the target, scaled to that inventory's volume. Every brick size they use is a catalog
brick, so their structures convert exactly into our parts and the stability (``physics.table_clutch``)
and piece counts (``balance.clusters``) are the same measurements on both sides.

Also the before/after figure for step 1 on the M12 demo sets: one object (the chair) as solid columns
(``--shape-columns``, the heightfield inputs had before) and as its exact cells.

Runs reuse the pipeline's candidate cache, so a killed run resumes. Writes ``results.md``,
``summary.json``, ``objects.png`` (their structure, then our best build per set, per object) and
``before_after.png`` under ``--out``.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

from brickwfc.alt.features import occupancy
from brickwfc.alt.inputs import load_source
from brickwfc.alt.output import write_build
from brickwfc.alt.pipeline import main as alt_main
from brickwfc.alt.target import BRICKGPT_PREFIX, load_target
from brickwfc.bricks import brickgpt
from brickwfc.bricks.balance import clusters
from brickwfc.bricks.colors import color_for_code
from brickwfc.bricks.inventory import inventory_cells, utilization
from brickwfc.bricks.physics import table_clutch
from brickwfc.bricks.shapes import fill, iou
from brickwfc.experiments.demo import SETS as DEMO_SETS
from brickwfc.experiments.demo import labeled_sheet, load_run
from brickwfc.render3d import save_voxels_png

SETS = ("6378-1", "5891-1", "10182-1")
FIGURE_CATEGORY = "03001627"  # chair
GRAY = color_for_code(71)  # light bluish gray, for their structures
TARGET_RGB = (160, 165, 169)
CATEGORIES = {  # ShapeNetCore synset ids in the StableText2Brick test split
    "04379243": "table", "03001627": "chair", "02958343": "car", "04256520": "sofa", "04530566": "vessel",
    "02828884": "bench", "02924116": "bus", "03467517": "guitar", "02876657": "bottle", "04468005": "train",
    "02871439": "bookshelf", "03593526": "jar", "03991062": "pot", "02818832": "bed", "03797390": "mug",
    "03928116": "piano", "04460130": "tower", "02880940": "bowl", "02801938": "basket", "02942699": "camera",
    "02843684": "birdhouse",
}


def category(structure: brickgpt.Structure) -> str:
    return CATEGORIES.get(structure.category_id, structure.category_id)


def pick_objects(structures: Sequence[brickgpt.Structure], categories: int = 6) -> list[brickgpt.Structure]:
    """The median-size structure (by brick count, ties by id) of each of the most common categories."""
    counts = Counter(s.category_id for s in structures)
    picked = []
    for cat in sorted(counts, key=lambda c: (-counts[c], c))[:categories]:
        members = sorted((s for s in structures if s.category_id == cat), key=lambda s: (len(s.bricks), s.structure_id))
        picked.append(members[len(members) // 2])
    return picked


def short(structure: brickgpt.Structure) -> str:
    return structure.structure_id[:8]


def theirs(structure: brickgpt.Structure, out: Path) -> dict:
    """Our measurements of their structure, and their own stability scores; renders it to ``out``."""
    placed = brickgpt.to_placed(structure.bricks, GRAY)
    grid = brickgpt.occupancy(structure.bricks).shape
    _, png = write_build(placed, grid, out / f"brickgpt_{short(structure)}",
                         f"StableText2Brick structure {structure.structure_id} ({category(structure)})")
    xs = [x for b in structure.bricks for x in (b.x, b.x + b.h)]
    ys = [y for b in structure.bricks for y in (b.y, b.y + b.w)]
    scores = np.array(structure.scores)
    return {
        "structure_id": structure.structure_id, "object_id": structure.object_id, "category": category(structure),
        "caption": structure.captions[0] if structure.captions else "", "bricks": len(placed),
        "size_studs": [max(xs) - min(xs), max(ys) - min(ys)], "height_bricks": max(b.z for b in structure.bricks) + 1,
        "cells": int(brickgpt.occupancy(structure.bricks).sum()),
        "clutch": table_clutch(placed, grid), "clusters": len(clusters(placed)),
        "score_min": float(scores.min()), "score_positive_pct": float(100 * (scores > 0).mean()), "png": str(png),
    }


def run_ours(set_number: str, structure: brickgpt.Structure, out: Path, n: int, workers: int | None,
             columns: bool = False) -> Path:
    directory = out / set_number / f"{short(structure)}_{'columns' if columns else 'exact'}"
    args = [set_number, "--shape", BRICKGPT_PREFIX + structure.structure_id, "--n", str(n), "--k", "1",
            "--out", str(directory)]
    args += ["--shape-columns"] if columns else []
    args += ["--workers", str(workers)] if workers else []
    alt_main(args)
    return directory


def ours(set_number: str, structure: brickgpt.Structure, directory: Path, columns: bool = False) -> dict:
    candidates, stats = load_run(directory)
    source = load_source(set_number)
    target = load_target(BRICKGPT_PREFIX + structure.structure_id, inventory_cells(source.inventory),
                         source.colors, columns=columns)
    built = [c for c in candidates if "generate" not in c.failed]
    valid = [c for c in candidates if c.valid]
    filled = [occupancy(c.placed, target.mask.shape) for c in valid]
    mean = lambda values: statistics.mean(values) if values else math.nan  # noqa: E731
    best = stats["selected"][0] if stats["selected"] else {}
    return {
        "set": set_number, "structure_id": structure.structure_id, "category": category(structure),
        "columns": columns, "inventory_parts": source.recognized_parts, "candidates": len(candidates),
        "grid_YZX": stats["grid_YZX"], "target_cells": int(target.mask.sum()),
        "valid_pct": 100 * len(valid) / len(candidates),
        "physics_pct": 100 * mean([float("physics" not in c.failed) for c in built]),
        "connected_pct": 100 * mean([float(c.clusters == 1) for c in built]),
        "fill_pct": 100 * mean([fill(f, target.mask) for f in filled]),
        "iou": mean([iou(f, target.mask) for f in filled]),
        "utilization_pct": 100 * mean([utilization(list(c.placed), source.inventory) for c in valid]),
        "best_parts": best.get("parts", 0), "best_fill_pct": best.get("fill_pct", math.nan),
        "best_iou": best.get("iou", math.nan), "best_clutch": best.get("clutch", math.nan),
        "best_clusters": best.get("clusters", 0),
        "best_png": str(directory / best["png"]) if best else None,
        "seconds_per_candidate": mean([c.seconds + c.physics_seconds for c in candidates]),
        "check_failures": stats["check_failures"],
    }


def f(value: float, fmt: str) -> str:
    return "—" if value is None or (isinstance(value, float) and math.isnan(value)) else fmt.format(value)


def stands(clutch: float) -> str:
    return "yes" if math.isfinite(clutch) else "no"


def tables(objects: list[dict], rows: list[dict], figure: list[dict]) -> str:
    lines = ["### Their structures (StableText2Brick test split, unlimited bricks)", "",
             "| object | id | bricks | size (studs x studs x bricks) | cells | stands (ours) | clutch | pieces "
             "| their score: min | their score: bricks > 0 % |", "|---|---|---|---|---|---|---|---|---|---|"]
    for o in objects:
        lines.append(f"| {o['category']} | {o['structure_id'][:8]} | {o['bricks']} | "
                     f"{o['size_studs'][0]}x{o['size_studs'][1]}x{o['height_bricks']} | {o['cells']} | "
                     f"{stands(o['clutch'])} | {f(o['clutch'], '{:.1f}')} | {o['clusters']} | {o['score_min']:.3f} | "
                     f"{o['score_positive_pct']:.0f} |")
    lines += ["", "### Ours (D2 + learned style from one set's inventory; the structure's exact cells as target)", "",
              "| object | set | inventory parts | grid (WxDxH) | target cells | valid % | physics % | one piece % "
              "| fill % | IoU | utilization % | best: parts | best: fill % | best: clutch | best: pieces | s/candidate |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        y, z, x = r["grid_YZX"]
        lines.append(f"| {r['category']} | {r['set']} | {r['inventory_parts']} | {x}x{z}x{y} | {r['target_cells']} | "
                     f"{r['valid_pct']:.0f} | {r['physics_pct']:.0f} | {r['connected_pct']:.0f} | "
                     f"{f(r['fill_pct'], '{:.1f}')} | {f(r['iou'], '{:.2f}')} | {f(r['utilization_pct'], '{:.1f}')} | "
                     f"{r['best_parts']} | {f(r['best_fill_pct'], '{:.1f}')} | {f(r['best_clutch'], '{:.1f}')} | "
                     f"{r['best_clusters']} | {r['seconds_per_candidate']:.2f} |")
    lines += ["", "### Before / after on the demo sets (chair; before: solid columns, after: exact cells)", "",
              "| set | target | grid (WxDxH) | target cells | valid % | fill % | IoU | best: parts | best: fill % "
              "| best: clutch | s/candidate |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in figure:
        y, z, x = r["grid_YZX"]
        lines.append(f"| {r['set']} | {'columns' if r['columns'] else 'exact'} | {x}x{z}x{y} | {r['target_cells']} | "
                     f"{r['valid_pct']:.0f} | {f(r['fill_pct'], '{:.1f}')} | {f(r['iou'], '{:.2f}')} | "
                     f"{r['best_parts']} | {f(r['best_fill_pct'], '{:.1f}')} | {f(r['best_clutch'], '{:.1f}')} | "
                     f"{r['seconds_per_candidate']:.2f} |")
    return "\n".join(lines)


def target_png(structure: brickgpt.Structure, set_number: str, columns: bool, path: Path) -> Path:
    source = load_source(set_number)
    target = load_target(BRICKGPT_PREFIX + structure.structure_id, inventory_cells(source.inventory),
                         source.colors, columns=columns)
    save_voxels_png(target.mask, np.broadcast_to(np.array(TARGET_RGB, dtype=np.uint8), (*target.mask.shape, 3)), path)
    return path


def blank(path: Path) -> Path:
    Image.new("RGB", (8, 8), (255, 255, 255)).save(path)
    return path


def build_label(r: dict) -> str:
    return (f"{r['set']}: {r['best_parts']} of {r['inventory_parts']} parts\nfill {r['best_fill_pct']:.0f}%, "
            f"stands: {stands(r['best_clutch'])}, pieces: {r['best_clusters']}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.brickgpt", description=__doc__.splitlines()[0])
    parser.add_argument("--sets", nargs="+", default=list(SETS), help="sets for the head-to-head")
    parser.add_argument("--figure-sets", nargs="+", default=list(DEMO_SETS), help="sets for the before/after figure")
    parser.add_argument("--categories", type=int, default=6)
    parser.add_argument("--n", type=int, default=50, help="candidates per run")
    parser.add_argument("--workers", type=int, help="passed to the pipeline")
    parser.add_argument("--data", type=Path, default=brickgpt.DATA_DIR)
    parser.add_argument("--out", type=Path, default=Path("out/m12b_brickgpt"))
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    picked = pick_objects(brickgpt.load_split("test", args.data), args.categories)
    objects = [theirs(s, args.out / "brickgpt") for s in picked]
    rows = [ours(set_number, s, run_ours(set_number, s, args.out, args.n, args.workers))
            for s in picked for set_number in args.sets]

    chair = next((s for s in picked if s.category_id == FIGURE_CATEGORY), picked[0])
    figure = []
    for set_number in args.figure_sets:
        for columns in (True, False):
            directory = run_ours(set_number, chair, args.out, args.n, args.workers, columns)
            figure.append(ours(set_number, chair, directory, columns))

    (args.out / "summary.json").write_text(json.dumps({"objects": objects, "ours": rows, "before_after": figure},
                                                      indent=2), encoding="utf-8")
    text = tables(objects, rows, figure) + "\n"
    (args.out / "results.md").write_text(text, encoding="utf-8")
    print(text)

    images, labels = [], []
    for o, s in zip(objects, picked):
        images.append(Path(o["png"]))
        labels.append(f"BrickGPT data: {o['category']}\n{o['bricks']} bricks (unlimited)")
        for r in (r for r in rows if r["structure_id"] == s.structure_id):
            if r["best_png"]:
                images.append(Path(r["best_png"]))
                labels.append(build_label(r))
    labeled_sheet(images, labels, args.out / "objects.png", columns=1 + len(args.sets))

    images = [target_png(chair, args.figure_sets[-1], True, args.out / "target_columns.png"),
              target_png(chair, args.figure_sets[-1], False, args.out / "target_exact.png")]
    labels = ["before: target as solid columns\n(heightfield, scaled to each set)",
              "after: target as exact 3D cells\n(scaled to each set)"]
    for r in figure:  # keep the before | after columns aligned when a run selected nothing
        if r["best_png"]:
            images.append(Path(r["best_png"]))
            labels.append(build_label(r))
        else:
            images.append(blank(args.out / "none.png"))
            labels.append(f"{r['set']}: no valid build")
    labeled_sheet(images, labels, args.out / "before_after.png", columns=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
