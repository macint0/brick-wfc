"""M12b step 1a: BrickGPT's structures as true 3D targets, and a head-to-head on their data.

    python -m brickwfc.experiments.brickgpt --out out/m12b_brickgpt [--steps 1a 1c]

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

Step 1c (``--steps 1c``): the same objects and sets hollowed (``--hollow``, default 2: a 2-cell shell plus
internal pillars), against their solid runs; the same inventory then makes a larger object, so besides fill
we report its size and the share of its outer surface the build covers. Figure: the object hollowing
enlarges most (the vessel) on the demo sets, solid | hollow.

Step 1d (``--steps 1d``): overhangs. The overhang loss is the share of target cells a build leaves empty
with nothing built under them (``shapes.unsupported_empty``). Remedies, kept if they recover fill with
every build still standing: (i) a clutch limit calibrated to real bricks (StableLego's per-knob friction
capacity, 0.98 N, over the weight of a plate cell from its measured 2x4 brick mass, 2.16 g), turned into
the cantilever length it allows with our physics model, and applied to the exact runs' builds (their
clutch is cached); (ii) support columns under overhangs out of a part's reach (``--supports``), extra
cells outside the object, so fill and IoU are measured against the object without them; (iii) open tops
(the pipeline default from 1d on; ``--no-open-tops`` before): studless top cells only under empty target
cells, so tiles cannot cap thin parts (the cause of the table's and chair's low builds on 10182-1). Runs
of the other variants pass ``--no-open-tops`` so they match the 1a runs. Figure: the table, exact | open
tops, on the demo sets.

Runs reuse the pipeline's candidate cache, so a killed run resumes. Writes, under ``--out``: step 1a
``results.md``, ``summary.json``, ``objects.png`` (their structure, then our best build per set, per object)
and ``before_after.png``; step 1c ``hollow.md``, ``hollow_summary.json`` and ``hollow_before_after.png``;
step 1d ``overhangs.md``, ``overhangs_summary.json`` and ``overhangs_before_after.png``.
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
from brickwfc.alt.target import BRICKGPT_PREFIX, Target, load_target
from brickwfc.bricks import brickgpt
from brickwfc.bricks.balance import clusters
from brickwfc.bricks.colors import color_for_code
from brickwfc.bricks.inventory import inventory_cells, utilization
from brickwfc.bricks.physics import table_clutch
from brickwfc.bricks.parts import CATALOG, PlacedPart, Shape
from brickwfc.bricks.physics import required_clutch
from brickwfc.bricks.shapes import fill, iou, surface, unsupported_empty
from brickwfc.experiments.demo import SETS as DEMO_SETS
from brickwfc.experiments.demo import labeled_sheet, load_run
from brickwfc.render3d import save_voxels_png

SETS = ("6378-1", "5891-1", "10182-1")
FIGURE_CATEGORY = "03001627"  # chair
HOLLOW_FIGURE_CATEGORY = "04530566"  # vessel: hollowing enlarges it most of the six
OVERHANG_FIGURE_CATEGORY = "04379243"  # table: the most overhang loss of the six
# Real clutch in our units (plate-cell weights per stud), from StableLego (arXiv 2402.10711), the analysis
# BrickGPT uses: friction capacity T = 0.98 N per knob; a 2x4 brick (24 plate cells) weighs 2.16 g.
FRICTION_CAPACITY_N = 0.98
PLATE_CELL_WEIGHT_N = 2.16e-3 / 24 * 9.8
REAL_CLUTCH = FRICTION_CAPACITY_N / PLATE_CELL_WEIGHT_N  # about 1111
CLUTCH_LIMITS = (math.inf, REAL_CLUTCH, 100.0, 30.0, 10.0)
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


def variant_args(variant: str) -> list[str]:
    """Pipeline arguments of a target variant: "exact", "columns", "hollow<N>", "supports" (as run before
    open tops, M12b 1d (iii), so they match the 1a runs), or "opentops" (exact with open tops on)."""
    if variant == "opentops":
        return []
    before = ["--no-open-tops"]
    if variant == "exact":
        return before
    if variant == "columns":
        return [*before, "--shape-columns"]
    if variant.startswith("hollow"):
        return [*before, "--hollow", variant.removeprefix("hollow")]
    if variant == "supports":
        return [*before, "--supports"]
    raise ValueError(f"unknown variant {variant!r}")


def target_for(set_number: str, structure: brickgpt.Structure, variant: str) -> Target:
    source = load_source(set_number)
    hollow = int(variant.removeprefix("hollow")) if variant.startswith("hollow") else 0  # opentops: as exact
    return load_target(BRICKGPT_PREFIX + structure.structure_id, inventory_cells(source.inventory),
                       source.colors, columns=variant == "columns", hollow=hollow, supports=variant == "supports")


def run_ours(set_number: str, structure: brickgpt.Structure, out: Path, n: int, workers: int | None,
             variant: str = "exact") -> Path:
    directory = out / set_number / f"{short(structure)}_{variant}"
    args = [set_number, "--shape", BRICKGPT_PREFIX + structure.structure_id, "--n", str(n), "--k", "1",
            "--out", str(directory), *variant_args(variant)]
    args += ["--workers", str(workers)] if workers else []
    alt_main(args)
    return directory


def ours(set_number: str, structure: brickgpt.Structure, directory: Path, variant: str = "exact") -> dict:
    candidates, stats = load_run(directory)
    source = load_source(set_number)
    target = target_for(set_number, structure, variant)
    outer = surface(target.mask)
    built = [c for c in candidates if "generate" not in c.failed]
    valid = [c for c in candidates if c.valid]
    filled = [occupancy(c.placed, target.mask.shape) for c in valid]
    mean = lambda values: statistics.mean(values) if values else math.nan  # noqa: E731
    best = stats["selected"][0] if stats["selected"] else {}
    best_filled = next((f for f, c in zip(filled, valid) if best and c.seed == best["seed"]), None)
    # The object itself (without support columns), on the same grid, for the overhang measures.
    obj = target_for(set_number, structure, "exact").mask if variant == "supports" else target.mask
    extra = {}
    if variant in ("exact", "supports", "opentops"):
        extra = {
            "object_cells": int(obj.sum()),
            "object_fill_pct": 100 * mean([fill(f, obj) for f in filled]),
            "object_iou": mean([iou(f, obj) for f in filled]),
            "overhang_loss_pct": 100 * mean([unsupported_empty(f, obj).sum() / obj.sum() for f in filled]),
            "outside_cells": mean([float((f & ~obj).sum()) for f in filled]),
            "valid_clutch": [c.clutch for c in valid],
            "valid_object_fill": [fill(f, obj) for f in filled],
        }
    return {**extra,
        "set": set_number, "structure_id": structure.structure_id, "category": category(structure),
        "variant": variant, "columns": variant == "columns", "inventory_parts": source.recognized_parts,
        "candidates": len(candidates), "surface_cells": int(outer.sum()),
        "surface_pct": 100 * mean([fill(f, outer) for f in filled]),
        "best_surface_pct": math.nan if best_filled is None else 100 * fill(best_filled, outer),
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
    their_clutch = {o["structure_id"]: o["clutch"] for o in objects}
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
              "| fill % | IoU | utilization % | best: parts | best: fill % | best: clutch | their clutch | best: pieces "
              "| s/candidate |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        y, z, x = r["grid_YZX"]
        lines.append(f"| {r['category']} | {r['set']} | {r['inventory_parts']} | {x}x{z}x{y} | {r['target_cells']} | "
                     f"{r['valid_pct']:.0f} | {r['physics_pct']:.0f} | {r['connected_pct']:.0f} | "
                     f"{f(r['fill_pct'], '{:.1f}')} | {f(r['iou'], '{:.2f}')} | {f(r['utilization_pct'], '{:.1f}')} | "
                     f"{r['best_parts']} | {f(r['best_fill_pct'], '{:.1f}')} | {f(r['best_clutch'], '{:.1f}')} | "
                     f"{f(their_clutch[r['structure_id']], '{:.1f}')} | {r['best_clusters']} | "
                     f"{r['seconds_per_candidate']:.2f} |")
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


def hollow_table(rows: list[dict]) -> str:
    """Solid vs hollow runs of the same object and set, side by side."""
    lines = ["| object | set | target | grid (WxDxH) | target cells | surface cells | valid % | physics % | one piece % "
             "| fill % | surface covered % | best: parts | best: surface covered % | s/candidate |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        y, z, x = r["grid_YZX"]
        lines.append(f"| {r['category']} | {r['set']} | {r['variant']} | {x}x{z}x{y} | {r['target_cells']} | "
                     f"{r['surface_cells']} | {r['valid_pct']:.0f} | {r['physics_pct']:.0f} | {r['connected_pct']:.0f} | "
                     f"{f(r['fill_pct'], '{:.1f}')} | {f(r['surface_pct'], '{:.1f}')} | {r['best_parts']} | "
                     f"{f(r['best_surface_pct'], '{:.1f}')} | {r['seconds_per_candidate']:.2f} |")
    return "\n".join(lines)


def cantilever_clutch(length: int, kind: str = "plate") -> float:
    """Required clutch per stud of a 1 x ``length`` part held by one stud: its first stud on a 1 x 1 brick
    standing on a baseplate, the rest sticking out (``length`` - 1 studs). Baseplate, so only the joints count."""
    column = PlacedPart(Shape(CATALOG["brick1x1"], False), GRAY, 0, 0, 0)
    arm = PlacedPart(Shape(CATALOG[f"{kind}1x{length}"], False), GRAY, 3, 0, 0)
    return required_clutch([column, arm], (3 + arm.shape.size_y, 1, length), baseplate=True)


def calibration_table() -> str:
    lengths = (2, 3, 4, 6, 8)
    lines = [f"Real clutch: {FRICTION_CAPACITY_N} N per knob / {PLATE_CELL_WEIGHT_N * 1e3:.3f} mN per plate cell "
             f"= **{REAL_CLUTCH:.0f}** plate-cell weights per stud.", "",
             "| part held by one stud | " + " | ".join(f"1x{n} ({n - 1} out)" for n in lengths) + " |",
             "|---|" + "---|" * len(lengths)]
    for kind in ("plate", "brick"):
        values = [cantilever_clutch(n, kind) for n in lengths]
        lines.append(f"| {kind} | " + " | ".join(f"{v:.1f}" for v in values) + " |")
    return "\n".join(lines)


def clutch_limit_table(rows: list[dict]) -> str:
    """Remedy (i): the exact runs' valid builds under each clutch limit: share standing, their mean fill."""
    head = " | ".join(f"≤ {c:.0f}: stand % / fill %" if math.isfinite(c) else "any clutch: stand % / fill %"
                      for c in CLUTCH_LIMITS)
    lines = [f"| object | set | {head} |", "|---|---|" + "---|" * len(CLUTCH_LIMITS)]
    for r in rows:
        cells = []
        for limit in CLUTCH_LIMITS:
            kept = [v for c, v in zip(r["valid_clutch"], r["valid_object_fill"]) if c <= limit]
            share = 100 * len(kept) / len(r["valid_clutch"]) if r["valid_clutch"] else math.nan
            cells.append(f"{f(share, '{:.0f}')} / {f(100 * statistics.mean(kept) if kept else math.nan, '{:.1f}')}")
        lines.append(f"| {r['category']} | {r['set']} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def overhang_table(rows: list[dict]) -> str:
    lines = ["| object | set | target | object cells | support cells (% of object) | valid % | physics % | one piece % "
             "| object fill % | object IoU | overhang loss % | built outside object (cells) | best: parts "
             "| s/candidate |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        support = r["target_cells"] - r["object_cells"]
        lines.append(f"| {r['category']} | {r['set']} | {r['variant']} | {r['object_cells']} | "
                     f"{support} ({100 * support / r['object_cells']:.0f}%) | {r['valid_pct']:.0f} | {r['physics_pct']:.0f} | "
                     f"{r['connected_pct']:.0f} | {f(r['object_fill_pct'], '{:.1f}')} | {f(r['object_iou'], '{:.2f}')} | "
                     f"{f(r['overhang_loss_pct'], '{:.1f}')} | {f(r['outside_cells'], '{:.0f}')} | {r['best_parts']} | "
                     f"{r['seconds_per_candidate']:.2f} |")
    return "\n".join(lines)


def target_png(structure: brickgpt.Structure, set_number: str, variant: str, path: Path) -> Path:
    target = target_for(set_number, structure, variant)
    save_voxels_png(target.mask, np.broadcast_to(np.array(TARGET_RGB, dtype=np.uint8), (*target.mask.shape, 3)), path)
    return path


def blank(path: Path) -> Path:
    Image.new("RGB", (8, 8), (255, 255, 255)).save(path)
    return path


def build_label(r: dict) -> str:
    return (f"{r['set']}: {r['best_parts']} of {r['inventory_parts']} parts\nfill {r['best_fill_pct']:.0f}%, "
            f"stands: {stands(r['best_clutch'])}, pieces: {r['best_clusters']}")


def before_after(structure: brickgpt.Structure, runs: list[dict], variants: tuple[str, str], titles: tuple[str, str],
                 target_set: str, out: Path, path: Path) -> None:
    """A two-column figure: the two targets (at ``target_set``'s scale), then per set the best build of each
    variant (``runs`` in set order, before then after). Empty cells keep the columns aligned."""
    images = [target_png(structure, target_set, v, out / f"target_{short(structure)}_{v}.png") for v in variants]
    labels = list(titles)
    for r in runs:
        if r["best_png"]:
            images.append(Path(r["best_png"]))
            labels.append(build_label(r))
        else:
            images.append(blank(out / "none.png"))
            labels.append(f"{r['set']}: no valid build")
    labeled_sheet(images, labels, path, columns=2)


def step_1a(picked: list[brickgpt.Structure], args: argparse.Namespace) -> None:
    objects = [theirs(s, args.out / "brickgpt") for s in picked]
    rows = [ours(set_number, s, run_ours(set_number, s, args.out, args.n, args.workers))
            for s in picked for set_number in args.sets]
    chair = next((s for s in picked if s.category_id == FIGURE_CATEGORY), picked[0])
    figure = [ours(set_number, chair, run_ours(set_number, chair, args.out, args.n, args.workers, variant), variant)
              for set_number in args.figure_sets for variant in ("columns", "exact")]

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
    before_after(chair, figure, ("columns", "exact"),
                 ("before: target as solid columns\n(heightfield, scaled to each set)",
                  "after: target as exact 3D cells\n(scaled to each set)"),
                 args.figure_sets[-1], args.out, args.out / "before_after.png")


def step_1c(picked: list[brickgpt.Structure], args: argparse.Namespace) -> None:
    hollow = f"hollow{args.hollow}"
    rows = [ours(set_number, s, run_ours(set_number, s, args.out, args.n, args.workers, variant), variant)
            for s in picked for set_number in args.sets for variant in ("exact", hollow)]
    vessel = next((s for s in picked if s.category_id == HOLLOW_FIGURE_CATEGORY), picked[0])
    figure = [ours(set_number, vessel, run_ours(set_number, vessel, args.out, args.n, args.workers, variant), variant)
              for set_number in args.figure_sets for variant in ("exact", hollow)]
    (args.out / "hollow_summary.json").write_text(json.dumps({"ours": rows, "before_after": figure}, indent=2),
                                                  encoding="utf-8")
    text = f"{hollow_table(rows)}\n\n### Figure runs ({category(vessel)})\n\n{hollow_table(figure)}\n"
    (args.out / "hollow.md").write_text(text, encoding="utf-8")
    print(text)
    before_after(vessel, figure, ("exact", hollow),
                 ("before: solid target\n(exact cells, scaled to each set)",
                  f"after: hollow target ({args.hollow}-cell shell + pillars)\n(same volume: a larger object)"),
                 args.figure_sets[-1], args.out, args.out / "hollow_before_after.png")


def step_1d(picked: list[brickgpt.Structure], args: argparse.Namespace) -> None:
    rows = [ours(set_number, s, run_ours(set_number, s, args.out, args.n, args.workers, variant), variant)
            for s in picked for set_number in args.sets for variant in ("exact", "opentops", "supports")]
    table = next((s for s in picked if s.category_id == OVERHANG_FIGURE_CATEGORY), picked[0])
    figure = [ours(set_number, table, run_ours(set_number, table, args.out, args.n, args.workers, variant), variant)
              for set_number in args.figure_sets for variant in ("exact", "opentops")]
    (args.out / "overhangs_summary.json").write_text(json.dumps({"ours": rows, "before_after": figure}, indent=2),
                                                     encoding="utf-8")
    exact = [r for r in rows if r["variant"] == "exact"]
    text = (f"### Calibration\n\n{calibration_table()}\n\n### (i) Clutch limits on the exact runs\n\n"
            f"{clutch_limit_table(exact)}\n\n### (ii) Support columns and (iii) open tops vs exact\n\n"
            f"{overhang_table(rows)}\n\n"
            f"### Figure runs ({category(table)})\n\n{overhang_table(figure)}\n")
    (args.out / "overhangs.md").write_text(text, encoding="utf-8")
    print(text)
    before_after(table, figure, ("exact", "opentops"),
                 ("before: exact target\n(tiles may cap thin parts)",
                  "after: open tops\n(studless tops only under empty target cells)"),
                 args.figure_sets[-1], args.out, args.out / "overhangs_before_after.png")


STEPS = {"1a": step_1a, "1c": step_1c, "1d": step_1d}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.brickgpt", description=__doc__.splitlines()[0])
    parser.add_argument("--steps", nargs="+", choices=sorted(STEPS), default=["1a"])
    parser.add_argument("--sets", nargs="+", default=list(SETS), help="sets for the head-to-head")
    parser.add_argument("--figure-sets", nargs="+", default=list(DEMO_SETS), help="sets for the before/after figure")
    parser.add_argument("--categories", type=int, default=6)
    parser.add_argument("--n", type=int, default=50, help="candidates per run")
    parser.add_argument("--hollow", type=int, default=2, help="step 1c: shell thickness in cells")
    parser.add_argument("--workers", type=int, help="passed to the pipeline")
    parser.add_argument("--data", type=Path, default=brickgpt.DATA_DIR)
    parser.add_argument("--out", type=Path, default=Path("out/m12b_brickgpt"))
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    picked = pick_objects(brickgpt.load_split("test", args.data), args.categories)
    for step in args.steps:
        STEPS[step](picked, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
