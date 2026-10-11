"""M12c: completeness-first selection, rerun on cached sweep candidates (no generation).

    python -m brickwfc.experiments.select --sweep out/m12b_complete --data data/omr --out results/m12c_select

For each arm (``--arms``, default creserve and creserve80) and each of its 9 sweep pairs
(``experiments/complete.py``: ``SWEEP_SETS`` x ``OBJECTS``), the pipeline's own funnel (``pipeline.run_funnel``) runs
on the cached candidates (``<sweep>/sweep/<arm>/<set>/<object>/candidates.jsonl``) with the run's config
(stats.json) under three rules:

  old      score order only (``complete_first=False``): what the sweep selected (checked against its stats.json)
  volume   complete first, volume bar (fill >= 97%, largest hole <= 4, surface >= 98%): the new default
  surface  complete first, surface bar (surface >= 98%, largest surface hole <= 4)

The context is the cached one: the target mask and grid from the cache key, the colors and style of the set (the
key's style label and inventory are checked). Writes ``<out>.json`` (every pair, every rule) and prints the table.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import fields, replace
from pathlib import Path
from typing import Sequence

from brickwfc.alt.candidates import Context
from brickwfc.alt.features import completeness, occupancy
from brickwfc.alt.inputs import DATA_DIR, learned_style, load_source
from brickwfc.alt.pipeline import SHAPE_EMPTY_WEIGHT, AltConfig, run_funnel
from brickwfc.bricks.shapes import fill
from brickwfc.experiments.complete import OBJECTS, SWEEP_SETS, key_mask, load_run

ARMS = ("creserve", "creserve80")
RULES = {"old": dict(complete_first=False), "volume": dict(complete_first=True, bar="volume"),
         "surface": dict(complete_first=True, bar="surface")}
WATCH = ("creserve80", "5891-1", "chair", 1)  # the first complete candidate (results/m12b_connected.md)


def rerank(directory: Path, data: Path) -> dict:
    """One arm x pair: the selected build under each rule, and how many unique builds meet each bar."""
    key, stats, candidates = load_run(directory)
    source = load_source(key["source"], data)
    style, label = learned_style(source.name)
    if label != key["style"] or sorted([*k, v] for k, v in source.inventory.items()) != key["inventory"]:
        raise SystemExit(f"{directory}: the set's inventory or style differs from the cached candidates'")
    mask = key_mask(key)
    context = Context(source.inventory, source.colors, style, tuple(key["grid"]), mask, None, SHAPE_EMPTY_WEIGHT)
    known = {f.name for f in fields(AltConfig)}
    config = AltConfig(**{k: v for k, v in stats["config"].items() if k in known})
    cell = {"candidates": len(candidates), "valid": sum(c.valid for c in candidates)}
    for rule, changes in RULES.items():
        report = run_funnel(candidates, context, style, replace(config, **changes), 0.0)
        chosen = report.selected[0]
        filled = occupancy(chosen.candidate.placed, context.grid)
        done = completeness(filled, mask)
        cell[rule] = {"seed": chosen.candidate.seed, "judge": chosen.judge, "complete": chosen.complete,
                      "fill_pct": 100 * fill(filled, mask), "largest_hole": done.largest_hole,
                      "surface_pct": 100 * done.surface, "largest_surface_hole": done.largest_surface_hole,
                      "unique": report.stages[2].survivors, "complete_unique": report.complete}
    saved = stats["selected"][0]["seed"]
    if cell["old"]["seed"] != saved:
        raise SystemExit(f"{directory}: the old rule selects seed {cell['old']['seed']}, the sweep selected {saved}")
    return cell


def table(cells: list[dict]) -> str:
    def sel(c: dict) -> str:
        return (f"{c['seed']} | {c['fill_pct']:.1f} / {c['largest_hole']} / {c['surface_pct']:.1f} / "
                f"{c['largest_surface_hole']} | {c['judge']:.3f} | {'yes' if c['complete'] else 'no'}")

    lines = ["| arm | object | set | unique | complete (vol / surf) | old: seed | fill / hole / surface / surf. hole | "
             "judge | complete | new (volume bar): seed | fill / hole / surface / surf. hole | judge | complete | "
             "surface bar: seed | fill / hole / surface / surf. hole | judge | complete |",
             "|---|---|---|---:|---:|---:|---|---:|---|---:|---|---:|---|---:|---|---:|---|"]
    for c in cells:
        lines.append(f"| {c['arm']} | {c['object']} | {c['set']} | {c['old']['unique']} | "
                     f"{c['volume']['complete_unique']} / {c['surface']['complete_unique']} | "
                     f"{sel(c['old'])} | {sel(c['volume'])} | {sel(c['surface'])} |")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.select", description=__doc__.splitlines()[0])
    parser.add_argument("--sweep", type=Path, default=Path("out/m12b_complete"), help="the completeness sweep's --out")
    parser.add_argument("--data", type=Path, default=DATA_DIR, help="OMR download cache")
    parser.add_argument("--arms", nargs="+", default=list(ARMS))
    parser.add_argument("--out", type=Path, default=Path("results/m12c_select"), help="writes <out>.json")
    args = parser.parse_args(argv)
    cells = []
    for arm in args.arms:
        for obj in OBJECTS:
            for set_number in SWEEP_SETS:
                run = Path("sweep", arm, set_number, obj)  # under --sweep
                cell = {"arm": arm, "object": obj, "set": set_number, "run": run.as_posix()}
                cell |= rerank(args.sweep / run, args.data)
                cells.append(cell)
                print(f"{arm} {obj} {set_number}: old seed {cell['old']['seed']}, new seed {cell['volume']['seed']}, "
                      f"surface-bar seed {cell['surface']['seed']}", flush=True)
    watched = next((c for c in cells if (c["arm"], c["set"], c["object"]) == WATCH[:3]), None)
    summary = {"cells": cells}
    if watched is not None:
        summary["watched"] = {"arm": WATCH[0], "set": WATCH[1], "object": WATCH[2], "seed": WATCH[3],
                              **{rule: watched[rule]["seed"] == WATCH[3] for rule in RULES}}
        print(f"{' '.join(map(str, WATCH))} selected: " + ", ".join(f"{r} {summary['watched'][r]}" for r in RULES))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix(".json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(table(cells))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
