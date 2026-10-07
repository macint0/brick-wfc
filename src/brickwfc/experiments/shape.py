"""M11 quick test: filling a target shape — WFC vs the bottom-up builder.

    python -m brickwfc.experiments.shape --seeds 100 --out out/m11

Both generators use the same parts, colors and weights, with a low empty weight so they try to fill
the shape, and both keep every part inside it. Conditions:

  B_wfc        WFC + support + shape constraints, with backtracking
  D_bottom_up  random bottom-up placement of supported parts inside the shape (no WFC)

Fill = share of the shape's cells that end up solid. Results are saved after each (shape, condition).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from brickwfc.bricks.__main__ import parse_size3
from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import PLATES, PartSet, extract_parts, part_tileset
from brickwfc.bricks.physics import required_clutch
from brickwfc.bricks.shapes import SHAPES, Mask, ShapeConstraint, fill, outside
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.support import is_stable
from brickwfc.wfc import run

CONDITIONS = ("B_wfc", "D_bottom_up")


@dataclass(frozen=True)
class RunRecord:
    shape: str
    condition: str
    seed: int
    success: bool
    fill: float
    outside: int
    stable: bool
    required_clutch: float
    attempts: int
    backtracks: int
    wall_time_s: float


def run_one(shape_name: str, condition: str, seed: int, parts: PartSet, mask: Mask, max_backtracks: int) -> RunRecord:
    if condition == "D_bottom_up":
        start = time.perf_counter()
        grid = BottomUpBuilder(parts).build(mask.shape, np.random.default_rng(seed), allowed=mask)
        attempts, backtracks, seconds = 1, 0, time.perf_counter() - start
    else:
        constraints = [SupportConstraint(parts), ShapeConstraint(parts, mask)]
        result = run(parts.tileset, mask.shape, seed, constraints=constraints, max_backtracks=max_backtracks)
        grid, attempts, backtracks, seconds = result.grid, result.stats.attempts, result.stats.backtracks, result.stats.wall_time_s
    if grid is None:
        return RunRecord(shape_name, condition, seed, False, 0.0, 0, False, math.inf, attempts, backtracks, seconds)
    placed, _ = extract_parts(grid, parts)
    filled = parts.solid[grid]
    return RunRecord(
        shape_name, condition, seed, True, fill(filled, mask), outside(filled, mask), is_stable(placed, filled),
        required_clutch(placed, grid.shape), attempts, backtracks, seconds,
    )


def summarize(records: list[RunRecord]) -> dict:
    n = len(records)
    built = [r for r in records if r.success]
    return {
        "shape": records[0].shape,
        "condition": records[0].condition,
        "seeds": n,
        "success_pct": 100 * len(built) / n,
        "mean_fill_pct": 100 * statistics.mean(r.fill for r in built) if built else 0.0,
        "min_fill_pct": 100 * min(r.fill for r in built) if built else 0.0,
        "cells_outside": sum(r.outside for r in records),
        "stable_pct": 100 * sum(r.stable for r in records) / n,
        "physics_any_clutch_pct": 100 * sum(math.isfinite(r.required_clutch) for r in records) / n,
        "physics_clutch10_pct": 100 * sum(r.required_clutch <= 10 for r in records) / n,
        "attempts_per_run": statistics.mean(r.attempts for r in records),
        "backtracks_per_run": statistics.mean(r.backtracks for r in records),
        "time_per_run_s": statistics.mean(r.wall_time_s for r in records),
    }


COLUMNS = [
    ("shape", "shape", "{}"), ("condition", "condition", "{}"), ("seeds", "seeds", "{}"),
    ("success %", "success_pct", "{:.1f}"), ("fill %", "mean_fill_pct", "{:.1f}"), ("min fill %", "min_fill_pct", "{:.1f}"),
    ("cells outside", "cells_outside", "{}"), ("stable %", "stable_pct", "{:.1f}"),
    ("phys. any clutch %", "physics_any_clutch_pct", "{:.1f}"), ("phys. clutch <=10 %", "physics_clutch10_pct", "{:.1f}"),
    ("attempts/run", "attempts_per_run", "{:.2f}"), ("backtracks/run", "backtracks_per_run", "{:.1f}"),
    ("time/run (s)", "time_per_run_s", "{:.3f}"),
]


def markdown_table(summaries: list[dict]) -> str:
    lines = ["| " + " | ".join(title for title, _, _ in COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    lines += ["| " + " | ".join(fmt.format(s[key]) for _, key, fmt in COLUMNS) + " |" for s in summaries]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.shape", description=__doc__.splitlines()[0])
    parser.add_argument("--shapes", nargs="+", default=list(SHAPES), choices=list(SHAPES))
    parser.add_argument("--size", type=parse_size3, default=(6, 8, 8), help="WIDTHxDEPTHxHEIGHT (default 8x8x6)")
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--empty-weight", type=float, default=0.2, help="low, so generators try to fill the shape")
    parser.add_argument("--max-backtracks", type=int, default=1000)
    parser.add_argument("--conditions", nargs="+", default=list(CONDITIONS), choices=CONDITIONS)
    parser.add_argument("--out", type=Path, default=Path("out/m11"))
    args = parser.parse_args(argv)

    parts = part_tileset(list(PLATES.values()), colors_by_name(["red", "blue"]), args.empty_weight)
    args.out.mkdir(parents=True, exist_ok=True)
    summary_path, runs_path = args.out / "summary.json", args.out / "runs.jsonl"
    summaries: list[dict] = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else []
    done = {(s["shape"], s["condition"], s["seeds"]) for s in summaries}
    for shape_name in args.shapes:
        mask = SHAPES[shape_name](*args.size)
        for condition in args.conditions:
            if (shape_name, condition, args.seeds) in done:
                print(f"{shape_name} {condition}: already done, skipping", flush=True)
                continue
            start = time.perf_counter()
            batch = [run_one(shape_name, condition, seed, parts, mask, args.max_backtracks) for seed in range(args.seeds)]
            summaries.append(summarize(batch))
            with runs_path.open("a", encoding="utf-8") as runs_file:
                runs_file.writelines(json.dumps(asdict(r)) + "\n" for r in batch)
            summary_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
            s = summaries[-1]
            print(f"{shape_name} {condition}: fill {s['mean_fill_pct']:.1f}%, stable {s['stable_pct']:.1f}%, "
                  f"physics {s['physics_any_clutch_pct']:.1f}% in {time.perf_counter() - start:.1f}s", flush=True)

    order = {name: i for i, name in enumerate(args.shapes)}
    summaries.sort(key=lambda s: (order.get(s["shape"], len(order)), CONDITIONS.index(s["condition"])))
    table = markdown_table(summaries)
    print(table)
    (args.out / "results.md").write_text(table + "\n", encoding="utf-8")
    print(f"wrote {args.out}/results.md, summary.json, runs.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
