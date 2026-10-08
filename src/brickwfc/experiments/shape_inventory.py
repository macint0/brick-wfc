"""M11: build a target shape from a real set's parts — WFC vs the bottom-up builder.

    python -m brickwfc.experiments.shape_inventory --seeds 20 --out out/m11_full

For each set, the inventory is the set's 1x1/1x2/2x2/2x4 plates (by color), as in M9. Each target
shape is scaled (``shapes.sized_for``) so its volume is about the inventory's cell volume, so a
perfect build uses every part and fills the whole shape. Conditions (same seeds, same weights):

  B_wfc        WFC + support + shape + inventory constraints in propagation, with backtracking
  D_bottom_up  random bottom-up placement of supported parts inside the shape, skipping used-up parts
  D2_bottom_up_any_offset  the same, but a part may cover the visited cell with any of its cells
                           (not only its min corner), so it can reach into gaps

A build is **valid** if it is within the inventory, inside the shape, whole, and satisfies the support
rule; physics (on a table) is reported separately. Results are saved after each (set, shape,
condition) and resumed; ``--export N`` also writes the first N builds of each as .ldr + .png.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.build import export_build
from brickwfc.bricks.inventory import (
    Inventory,
    InventoryConstraint,
    inventory_cells,
    inventory_coverage,
    inventory_from_mpd,
    overuse,
    utilization,
)
from brickwfc.bricks.parts import PLATES, PartSet, extract_parts, part_tileset
from brickwfc.bricks.physics import required_clutch
from brickwfc.bricks.shapes import SHAPES, Mask, ShapeConstraint, fill, iou, outside, sized_for
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.support import is_stable
from brickwfc.experiments.inventory import DEFAULT_SETS
from brickwfc.ldraw.fetch import fetch_set
from brickwfc.wfc import run

CONDITIONS = ("B_wfc", "D_bottom_up", "D2_bottom_up_any_offset")


@dataclass(frozen=True)
class RunRecord:
    set_number: str
    shape: str
    condition: str
    seed: int
    success: bool
    whole: bool
    within_inventory: bool
    stable: bool
    outside: int
    fill: float
    iou: float
    utilization: float
    required_clutch: float
    parts: int
    attempts: int
    backtracks: int
    wall_time_s: float

    @property
    def valid(self) -> bool:
        return self.success and self.whole and self.within_inventory and self.stable and self.outside == 0


Build = Callable[[int], tuple[np.ndarray | None, int, int, float]]  # seed -> (grid, attempts, backtracks, seconds)


def make_generator(
    condition: str, parts: PartSet, inventory: Inventory, mask: Mask, max_attempts: int, max_backtracks: int
) -> Build:
    if condition.startswith("D"):
        builder = BottomUpBuilder(parts, any_offset=condition == "D2_bottom_up_any_offset")

        def build(seed: int) -> tuple[np.ndarray | None, int, int, float]:
            start = time.perf_counter()
            grid = builder.build(mask.shape, np.random.default_rng(seed), inventory, allowed=mask)
            return grid, 1, 0, time.perf_counter() - start

        return build

    constraints = [SupportConstraint(parts), ShapeConstraint(parts, mask), InventoryConstraint(parts, inventory)]

    def build(seed: int) -> tuple[np.ndarray | None, int, int, float]:
        result = run(parts.tileset, mask.shape, seed, max_attempts, constraints, max_backtracks)
        return result.grid, result.stats.attempts, result.stats.backtracks, result.stats.wall_time_s

    return build


def evaluate(
    set_number: str, shape_name: str, condition: str, seed: int, grid: np.ndarray | None, parts: PartSet,
    inventory: Inventory, mask: Mask, attempts: int, backtracks: int, seconds: float,
) -> RunRecord:
    if grid is None:
        return RunRecord(set_number, shape_name, condition, seed, False, False, False, False, 0, 0.0, 0.0, 0.0,
                         math.inf, 0, attempts, backtracks, seconds)
    placed, errors = extract_parts(grid, parts)
    filled = parts.solid[grid]
    return RunRecord(
        set_number, shape_name, condition, seed, True, not errors, not overuse(placed, inventory), is_stable(placed, filled),
        outside(filled, mask), fill(filled, mask), iou(filled, mask), utilization(placed, inventory),
        required_clutch(placed, grid.shape), len(placed), attempts, backtracks, seconds,
    )


def summarize(records: list[RunRecord], inventory: Inventory, mask: Mask) -> dict:
    n = len(records)
    built = [r for r in records if r.success]
    valid = sum(r.valid for r in records)
    total_time = sum(r.wall_time_s for r in records)

    def mean_pct(key: str) -> float:
        return 100 * statistics.mean(getattr(r, key) for r in built) if built else 0.0

    return {
        "set": records[0].set_number,
        "shape": records[0].shape,
        "condition": records[0].condition,
        "seeds": n,
        "inventory_parts": sum(inventory.values()),
        "grid_WxDxH": f"{mask.shape[2]}x{mask.shape[1]}x{mask.shape[0]}",
        "shape_cells": int(mask.sum()),
        # The inventory can't fill more than this share of the shape.
        "max_fill_pct": 100 * min(1.0, inventory_cells(inventory) / mask.sum()),
        "success_pct": 100 * len(built) / n,
        "valid_pct": 100 * valid / n,
        "cells_outside": sum(r.outside for r in records),
        "mean_fill_pct": mean_pct("fill"),
        "min_fill_pct": 100 * min(r.fill for r in built) if built else 0.0,
        "mean_iou_pct": mean_pct("iou"),
        "utilization_pct": mean_pct("utilization"),
        "physics_any_clutch_pct": 100 * sum(math.isfinite(r.required_clutch) for r in records) / n,
        "physics_clutch10_pct": 100 * sum(r.required_clutch <= 10 for r in records) / n,
        "attempts_per_run": statistics.mean(r.attempts for r in records),
        "backtracks_per_run": statistics.mean(r.backtracks for r in records),
        "time_per_run_s": total_time / n,
        "time_per_valid_s": total_time / valid if valid else math.inf,
    }


COLUMNS = [
    ("set", "set", "{}"), ("shape", "shape", "{}"), ("condition", "condition", "{}"), ("parts", "inventory_parts", "{}"),
    ("grid", "grid_WxDxH", "{}"), ("shape cells", "shape_cells", "{}"), ("max fill %", "max_fill_pct", "{:.1f}"),
    ("valid %", "valid_pct", "{:.1f}"), ("fill %", "mean_fill_pct", "{:.1f}"), ("min fill %", "min_fill_pct", "{:.1f}"),
    ("IoU %", "mean_iou_pct", "{:.1f}"), ("utilization %", "utilization_pct", "{:.1f}"),
    ("phys. any clutch %", "physics_any_clutch_pct", "{:.1f}"), ("phys. clutch <=10 %", "physics_clutch10_pct", "{:.1f}"),
    ("attempts/run", "attempts_per_run", "{:.2f}"), ("backtracks/run", "backtracks_per_run", "{:.1f}"),
    ("time/run (s)", "time_per_run_s", "{:.3f}"),
]

MEAN_COLUMNS = [
    ("valid %", "valid_pct"), ("fill %", "mean_fill_pct"), ("max fill %", "max_fill_pct"), ("IoU %", "mean_iou_pct"),
    ("utilization %", "utilization_pct"), ("phys. any clutch %", "physics_any_clutch_pct"),
    ("phys. clutch <=10 %", "physics_clutch10_pct"), ("attempts/run", "attempts_per_run"), ("time/run (s)", "time_per_run_s"),
]


def markdown_table(summaries: list[dict]) -> str:
    lines = ["| " + " | ".join(title for title, _, _ in COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    lines += ["| " + " | ".join(fmt.format(s[key]) for _, key, fmt in COLUMNS) + " |" for s in summaries]
    return "\n".join(lines)


def mean_table(summaries: list[dict], group: Callable[[dict], str], title: str) -> str:
    """Means over (set, shape) rows per ``group`` value and condition (each row weighted equally)."""
    lines = [f"| {title} | condition | sets | " + " | ".join(t for t, _ in MEAN_COLUMNS) + " |",
             "|" + "---|" * (3 + len(MEAN_COLUMNS))]
    groups = list(dict.fromkeys(group(s) for s in summaries))
    for value in groups:
        for condition in CONDITIONS:
            rows = [s for s in summaries if group(s) == value and s["condition"] == condition]
            if not rows:
                continue
            means = [statistics.mean(r[key] for r in rows) for _, key in MEAN_COLUMNS]
            cells = [f"{m:.2f}" if key == "attempts_per_run" else f"{m:.3f}" if key == "time_per_run_s" else f"{m:.1f}"
                     for m, (_, key) in zip(means, MEAN_COLUMNS)]
            sets = len({r["set"] for r in rows})
            lines.append(f"| {value} | {condition} | {sets} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.shape_inventory", description=__doc__.splitlines()[0])
    parser.add_argument("--sets", nargs="+", default=list(DEFAULT_SETS))
    parser.add_argument("--shapes", nargs="+", default=list(SHAPES), choices=list(SHAPES))
    parser.add_argument("--data", type=Path, default=Path("data/omr"))
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--volume", type=float, default=1.0, help="target shape volume / inventory volume")
    parser.add_argument("--empty-weight", type=float, default=0.2, help="low, so generators try to fill the shape")
    parser.add_argument("--conditions", nargs="+", default=list(CONDITIONS), choices=CONDITIONS)
    parser.add_argument("--max-attempts", type=int, default=20)
    parser.add_argument("--max-backtracks", type=int, default=1000, help="per WFC attempt")
    parser.add_argument("--export", type=int, default=0, help="write the first N builds of each batch as .ldr + .png")
    parser.add_argument("--out", type=Path, default=Path("out/m11_full"))
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    summary_path, runs_path = args.out / "summary.json", args.out / "runs.jsonl"
    summaries: list[dict] = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else []
    done = {(s["set"], s["shape"], s["condition"], s["seeds"]) for s in summaries}
    for set_number in args.sets:
        text = fetch_set(set_number, args.data).read_text(encoding="utf-8", errors="replace")
        inventory, _, colors = inventory_from_mpd(text)
        parts = part_tileset(list(PLATES.values()), colors, args.empty_weight, coverage=inventory_coverage(inventory))
        for shape_name in args.shapes:
            mask = sized_for(shape_name, args.volume * inventory_cells(inventory))
            for condition in args.conditions:
                if (set_number, shape_name, condition, args.seeds) in done:
                    print(f"{set_number} {shape_name} {condition}: already done, skipping", flush=True)
                    continue
                build = make_generator(condition, parts, inventory, mask, args.max_attempts, args.max_backtracks)
                start = time.perf_counter()
                batch = []
                for seed in range(args.seeds):
                    grid, attempts, backtracks, seconds = build(seed)
                    batch.append(evaluate(set_number, shape_name, condition, seed, grid, parts, inventory, mask,
                                          attempts, backtracks, seconds))
                    if seed < args.export and grid is not None:
                        placed, _ = extract_parts(grid, parts)
                        stem = args.out / "builds" / f"{set_number}_{shape_name}_{condition}_seed{seed}"
                        export_build(grid, placed, parts, stem.with_suffix(".ldr"), stem.with_suffix(".png"),
                                     f"brickwfc {shape_name} from set {set_number} ({condition}, seed {seed})")
                summaries.append(summarize(batch, inventory, mask))
                with runs_path.open("a", encoding="utf-8") as runs_file:
                    runs_file.writelines(json.dumps(asdict(r)) + "\n" for r in batch)
                summary_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
                s = summaries[-1]
                print(f"{set_number} {shape_name} {condition}: valid {s['valid_pct']:.0f}%, fill {s['mean_fill_pct']:.1f}% "
                      f"(max {s['max_fill_pct']:.0f}%), utilization {s['utilization_pct']:.1f}%, "
                      f"physics {s['physics_any_clutch_pct']:.0f}% in {time.perf_counter() - start:.1f}s", flush=True)

    set_order = {name: i for i, name in enumerate(args.sets)}
    shape_order = {name: i for i, name in enumerate(SHAPES)}
    summaries.sort(key=lambda s: (set_order.get(s["set"], len(set_order)), s["set"], shape_order[s["shape"]],
                                  CONDITIONS.index(s["condition"])))
    by_shape = sorted(summaries, key=lambda s: shape_order[s["shape"]])
    text = ("## Mean over sets, per shape\n\n" + mean_table(by_shape, lambda s: s["shape"], "shape")
            + "\n\n## Mean over sets and shapes\n\n" + mean_table(summaries, lambda s: "all", "shapes")
            + "\n\n## Per set and shape\n\n" + markdown_table(summaries) + "\n")
    print(text)
    (args.out / "results.md").write_text(text, encoding="utf-8")
    print(f"wrote {args.out}/results.md, summary.json, runs.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
