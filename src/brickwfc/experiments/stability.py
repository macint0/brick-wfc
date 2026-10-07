"""M6 experiment: plain WFC + post-filter vs stability-aware WFC (vs a non-WFC baseline).

    python -m brickwfc.experiments.stability --seeds 1000 --sizes 4x4x2 4x4x3 8x8x6 --out out/m6

Conditions (all use the same parts, colors, weights, and seeds):
  A  plain      no support rule during generation; unstable designs are filtered afterwards
  B  aware      part-level support enforced in propagation (bricks/stability.py)
  C  per-cell   M4's local rule (every stud needs a solid cell below): stable but no overhangs
  D  bottom-up  no WFC: random bottom-up placement of supported parts (bricks/bottomup.py)

Ground truth for every condition is ``support.is_stable``.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from brickwfc.bricks.__main__ import parse_size3
from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import PLATES, PartSet, extract_parts, part_tileset
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.support import is_stable, overhanging_parts
from brickwfc.wfc import run

CONDITIONS = ("A_plain", "B_aware", "C_per_cell", "D_bottom_up")


@dataclass(frozen=True)
class RunRecord:
    condition: str
    size: str
    seed: int
    success: bool  # the generator produced a build (WFC: within max attempts)
    stable: bool
    attempts: int
    contradictions: int
    wall_time_s: float
    parts: int
    overhanging_parts: int
    broken_parts: int
    fill: float


@dataclass(frozen=True)
class Generated:
    grid: np.ndarray | None  # None if the generator gave up
    attempts: int
    contradictions: int
    wall_time_s: float


Generator = Callable[[int], Generated]  # seed -> build


def setup(condition: str, colors: list[str], shape: tuple[int, int, int], max_attempts: int) -> tuple[PartSet, Generator]:
    """The part set (for decoding builds) and the generator for one condition."""
    support = "cell" if condition == "C_per_cell" else "none"
    parts = part_tileset(list(PLATES.values()), colors_by_name(colors), support=support)
    if condition == "D_bottom_up":
        builder = BottomUpBuilder(parts)

        def generate(seed: int) -> Generated:
            start = time.perf_counter()
            grid = builder.build(shape, np.random.default_rng(seed))
            return Generated(grid, 1, 0, time.perf_counter() - start)

        return parts, generate

    constraints = (SupportConstraint(parts),) if condition == "B_aware" else ()

    def generate(seed: int) -> Generated:
        result = run(parts.tileset, shape, seed, max_attempts, constraints)
        stats = result.stats
        return Generated(result.grid, stats.attempts, stats.contradictions, stats.wall_time_s)

    return parts, generate


def run_one(condition: str, size: str, seed: int, parts: PartSet, generate: Generator) -> RunRecord:
    built = generate(seed)
    if built.grid is None:
        return RunRecord(condition, size, seed, False, False, built.attempts, built.contradictions, built.wall_time_s, 0, 0, 0, 0.0)
    placed, errors = extract_parts(built.grid, parts)
    filled = parts.solid[built.grid]
    return RunRecord(
        condition, size, seed, True, is_stable(placed, filled), built.attempts, built.contradictions,
        built.wall_time_s, len(placed), len(overhanging_parts(placed, filled)), len(errors), float(filled.mean()),
    )


def summarize(records: list[RunRecord]) -> dict[str, float | int | str]:
    stable = sum(r.stable for r in records)
    total_time = sum(r.wall_time_s for r in records)
    built = [r for r in records if r.success]
    return {
        "condition": records[0].condition,
        "size": records[0].size,
        "seeds": len(records),
        "wfc_success_pct": 100 * len(built) / len(records),
        "stable_pct": 100 * stable / len(records),
        "restarts_per_run": statistics.mean(r.contradictions for r in records),
        "time_per_run_s": total_time / len(records),
        "time_per_stable_s": total_time / stable if stable else float("inf"),
        "parts_per_design": statistics.mean(r.parts for r in built) if built else 0.0,
        "overhangs_per_design": statistics.mean(r.overhanging_parts for r in built) if built else 0.0,
        "fill_pct": 100 * statistics.mean(r.fill for r in built) if built else 0.0,
        "broken_parts": sum(r.broken_parts for r in records),
    }


def markdown_table(summaries: list[dict]) -> str:
    header = ("| size (WxDxH) | condition | seeds | stable % | restarts/run | time/run (s) | time/stable (s) "
              "| parts/design | overhangs/design | fill % | broken parts |")
    columns = header.count("|") - 1
    lines = [header, "|" + "---|" * columns]
    for s in summaries:
        per_stable = "inf" if s["time_per_stable_s"] == float("inf") else f"{s['time_per_stable_s']:.3f}"
        lines.append(
            f"| {s['size']} | {s['condition']} | {s['seeds']} | {s['stable_pct']:.1f} | {s['restarts_per_run']:.2f} "
            f"| {s['time_per_run_s']:.3f} | {per_stable} | {s['parts_per_design']:.1f} "
            f"| {s['overhangs_per_design']:.1f} | {s['fill_pct']:.1f} | {s['broken_parts']} |"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.stability", description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=1000)
    parser.add_argument("--sizes", nargs="+", default=["4x4x2", "4x4x3", "8x8x6"], help="WIDTHxDEPTHxHEIGHT")
    parser.add_argument("--conditions", nargs="+", default=list(CONDITIONS), choices=CONDITIONS)
    parser.add_argument("--colors", default="red,blue")
    parser.add_argument("--max-attempts", type=int, default=100)
    parser.add_argument("--out", type=Path, default=Path("out/m6"))
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    summary_path, runs_path = args.out / "summary.json", args.out / "runs.jsonl"
    # Results are saved after every (size, condition), so an interrupted run can be resumed:
    # finished (size, condition, seeds) combinations already in summary.json are skipped.
    summaries: list[dict] = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else []
    done = {(s["size"], s["condition"], s["seeds"]) for s in summaries}
    for size in args.sizes:
        shape = parse_size3(size)
        for condition in args.conditions:
            if (size, condition, args.seeds) in done:
                print(f"{size} {condition}: already done, skipping", flush=True)
                continue
            parts, generate = setup(condition, args.colors.split(","), shape, args.max_attempts)
            start = time.perf_counter()
            batch = [run_one(condition, size, seed, parts, generate) for seed in range(args.seeds)]
            summaries.append(summarize(batch))
            with runs_path.open("a", encoding="utf-8") as runs_file:
                runs_file.writelines(json.dumps(asdict(r)) + "\n" for r in batch)
            summary_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
            print(f"{size} {condition}: stable {summaries[-1]['stable_pct']:.1f}% in {time.perf_counter() - start:.1f}s", flush=True)

    # Group rows by size (in the order given), then condition, whatever order they were run in.
    size_order = {size: i for i, size in enumerate(args.sizes)}
    summaries.sort(key=lambda s: (size_order.get(s["size"], len(size_order)), s["size"], s["condition"]))
    table = markdown_table(summaries)
    print(table)
    (args.out / "results.md").write_text(table + "\n", encoding="utf-8")
    print(f"wrote {args.out}/results.md, summary.json, runs.jsonl")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
