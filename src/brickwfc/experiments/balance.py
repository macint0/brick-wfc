"""M12 step 1b: does the tip-over check (``bricks.balance``) fix the physics yield of the pipeline?

    python -m brickwfc.experiments.balance --sets 6372-1 10182-1 --n 200 --out out/m12_1b

For each set, the alternate-build pipeline (``alt``) runs with the same seeds in four conditions:
``slab`` = M10's grid (12 plates tall, wide footprint) or ``cube`` = the new default grid, each with and
without the tip-over check in the bottom-up builder D2. Every candidate is checked by the physics LP.
Runs reuse the pipeline's candidate cache, so a killed run resumes. Writes ``results.md`` and
``summary.json`` under ``--out``.

Judge: all conditions of a set are judged at one common size (the smallest of the conditions' 10%
quantiles of contact events), so the numbers are comparable across conditions.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Sequence

import numpy as np

from brickwfc.alt.candidates import Candidate
from brickwfc.alt.inputs import learned_style, load_source
from brickwfc.alt.pipeline import main as alt_main
from brickwfc.bricks.balance import clusters
from brickwfc.bricks.inventory import utilization
from brickwfc.bricks.style import events, matched_divergence

CONDITIONS = {
    "slab_nobalance": ["--height", "12", "--no-balance"],
    "slab_balance": ["--height", "12"],
    "cube_nobalance": ["--no-balance"],
    "cube_balance": [],
}


def load(directory: Path) -> tuple[list[Candidate], list[int]]:
    lines = (directory / "candidates.jsonl").read_text(encoding="utf-8").splitlines()[1:]
    grid = json.loads((directory / "stats.json").read_text(encoding="utf-8"))["grid_YZX"]
    return [Candidate.from_json(json.loads(line)) for line in lines if line.strip()], grid


def summarize(set_number: str, runs: dict[str, tuple[list[Candidate], list[int]]], draws: int = 5) -> list[dict]:
    source = load_source(set_number)
    stats, _ = learned_style(source.name)
    counts = {name: {c.seed: events(c.placed) for c in cs if c.valid} for name, (cs, _) in runs.items()}
    floors = [int(np.quantile([e.count for e in found.values()], 0.1, method="lower")) for found in counts.values() if found]
    size = min(floors) if floors else 0
    rows = []
    for name, (candidates, grid) in runs.items():
        checked = [c for c in candidates if not math.isnan(c.clutch)]
        finite = [c for c in checked if math.isfinite(c.clutch)]
        judged = [e for e in counts[name].values() if e.count >= size]
        judges = [-matched_divergence(e, size, stats, np.random.default_rng([0, i]), draws) for i, e in enumerate(judged)]
        rows.append({
            "set": set_number, "condition": name, "grid_YZX": grid, "candidates": len(candidates),
            "physics_pct": 100 * len(finite) / len(checked) if checked else math.nan,
            "valid_pct": 100 * sum(c.valid for c in candidates) / len(candidates),
            "utilization_pct": 100 * statistics.mean(utilization(list(c.placed), source.inventory) for c in candidates),
            "clusters_per_build": statistics.median(len(clusters(list(c.placed))) for c in candidates),
            "median_clutch": statistics.median(c.clutch for c in finite) if finite else math.nan,
            "judge": statistics.mean(judges) if judges else math.nan, "judge_size": size,
            "seconds_per_build": statistics.mean(c.seconds for c in candidates),
        })
    return rows


def table(rows: list[dict]) -> str:
    lines = ["| set | condition | grid (WxDxH) | physics pass % | valid % | utilization % | clusters/build "
             "| median clutch (finite) | judge (size-matched) | s/build |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        y, z, x = r["grid_YZX"]
        lines.append(f"| {r['set']} | {r['condition']} | {x}x{z}x{y} | {r['physics_pct']:.1f} | {r['valid_pct']:.1f} | "
                     f"{r['utilization_pct']:.1f} | {r['clusters_per_build']:.0f} | {r['median_clutch']:.1f} | "
                     f"{r['judge']:.3f} | {r['seconds_per_build']:.2f} |")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.balance", description=__doc__.splitlines()[0])
    parser.add_argument("--sets", nargs="+", default=["6372-1", "10182-1"])
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--workers", type=int, help="passed to the pipeline")
    parser.add_argument("--out", type=Path, default=Path("out/m12_1b"))
    args = parser.parse_args(argv)
    rows = []
    for set_number in args.sets:
        runs = {}
        for name, extra in CONDITIONS.items():
            directory = args.out / set_number / name
            workers = ["--workers", str(args.workers)] if args.workers else []
            alt_main([set_number, "--n", str(args.n), "--out", str(directory), *extra, *workers])
            runs[name] = load(directory)
        rows += summarize(set_number, runs)
    (args.out / "summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    text = table(rows) + "\n"
    (args.out / "results.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
