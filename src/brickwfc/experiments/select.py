"""M12c: completeness-first selection, rerun on cached sweep candidates (no generation).

    python -m brickwfc.experiments.select --sweep out/m12b_complete --data data/omr --out results/m12c_select
    python -m brickwfc.experiments.select --arms creserve90 creserve70 creserve60 usable70 usable60 --out out/m12c_size_select

For each arm (``--arms``: any arm folders under ``<sweep>/sweep/``, default creserve and creserve80) and each of the 9
sweep pairs (``experiments/complete.py``: ``SWEEP_SETS`` x ``OBJECTS``; a pair with no finished run is skipped and
listed), the pipeline's own funnel (``pipeline.run_funnel``) runs on the cached candidates
(``<sweep>/sweep/<arm>/<set>/<object>/candidates.jsonl``) with the run's config (stats.json) under three rules:

  old      score order only (``complete_first=False``)
  volume   complete first, volume bar (fill >= 97%, largest hole <= 4, surface >= 98%): the new default
  surface  complete first, surface bar (surface >= 98%, largest surface hole <= 4)

Each run is checked first: the rule it was selected with (``stored_rule``: score order for a run made before
complete-first existed, else its own complete-first setting and bar) must reproduce the seed in its stats.json.
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


def stored_rule(saved: dict) -> dict:
    """The selection settings a run used, from its stats.json config: runs from before complete-first (no such key)
    selected by score only; later runs by their own setting (and bar, kept from the config)."""
    return {"complete_first": bool(saved.get("complete_first", False))}


def selected_row(report, context: Context, mask) -> dict | None:
    if not report.selected:
        return None
    chosen = report.selected[0]
    filled = occupancy(chosen.candidate.placed, context.grid)
    done = completeness(filled, mask)
    return {"seed": chosen.candidate.seed, "judge": chosen.judge, "complete": chosen.complete,
            "fill_pct": 100 * fill(filled, mask), "largest_hole": done.largest_hole,
            "surface_pct": 100 * done.surface, "largest_surface_hole": done.largest_surface_hole,
            "unique": report.stages[2].survivors, "complete_unique": report.complete}


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
    as_run = stored_rule(stats["config"])
    again = selected_row(run_funnel(candidates, context, style, replace(config, **as_run), 0.0), context, mask)
    saved = stats["selected"][0]["seed"] if stats["selected"] else None
    if (again and again["seed"]) != saved:
        raise SystemExit(f"{directory}: rerun with {as_run} selects seed {again and again['seed']}, the run "
                         f"selected {saved}")
    cell = {"candidates": len(candidates), "valid": sum(c.valid for c in candidates), "stored_rule": as_run}
    for rule, changes in RULES.items():
        cell[rule] = selected_row(run_funnel(candidates, context, style, replace(config, **changes), 0.0), context,
                                  mask)
    return cell


def table(cells: list[dict]) -> str:
    def sel(c: dict | None) -> str:
        if c is None:
            return "- | no selection | - | -"
        return (f"{c['seed']} | {c['fill_pct']:.1f} / {c['largest_hole']} / {c['surface_pct']:.1f} / "
                f"{c['largest_surface_hole']} | {c['judge']:.3f} | {'yes' if c['complete'] else 'no'}")

    lines = ["| arm | object | set | unique | complete (vol / surf) | old: seed | fill / hole / surface / surf. hole | "
             "judge | complete | new (volume bar): seed | fill / hole / surface / surf. hole | judge | complete | "
             "surface bar: seed | fill / hole / surface / surf. hole | judge | complete |",
             "|---|---|---|---:|---:|---:|---|---:|---|---:|---|---:|---|---:|---|---:|---|"]
    for c in cells:
        first = c["old"] or {}
        lines.append(f"| {c['arm']} | {c['object']} | {c['set']} | {first.get('unique', 0)} | "
                     f"{(c['volume'] or {}).get('complete_unique', 0)} / {(c['surface'] or {}).get('complete_unique', 0)} | "
                     f"{sel(c['old'])} | {sel(c['volume'])} | {sel(c['surface'])} |")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.select", description=__doc__.splitlines()[0])
    parser.add_argument("--sweep", type=Path, default=Path("out/m12b_complete"), help="the completeness sweep's --out")
    parser.add_argument("--data", type=Path, default=DATA_DIR, help="OMR download cache")
    parser.add_argument("--arms", nargs="+", default=list(ARMS),
                        help="arm folders under <sweep>/sweep/ (any names; default: " + " ".join(ARMS) + ")")
    parser.add_argument("--out", type=Path, default=Path("out/m12c_select/select"), help="writes <out>.json")
    args = parser.parse_args(argv)
    cells, missing = [], []
    for arm in args.arms:
        for obj in OBJECTS:
            for set_number in SWEEP_SETS:
                run = Path("sweep", arm, set_number, obj)  # under --sweep
                if not (args.sweep / run / "stats.json").exists():  # not run, or not finished
                    missing.append(run.as_posix())
                    continue
                cell = {"arm": arm, "object": obj, "set": set_number, "run": run.as_posix()}
                cell |= rerank(args.sweep / run, args.data)
                cells.append(cell)
                print(f"{arm} {obj} {set_number}: " + ", ".join(
                    f"{rule} seed {cell[rule]['seed'] if cell[rule] else '-'}" for rule in RULES), flush=True)
    if missing:
        print(f"no finished run, skipped: {', '.join(missing)}")
    watched = next((c for c in cells if (c["arm"], c["set"], c["object"]) == WATCH[:3]), None)
    summary = {"cells": cells, "missing": missing}
    if watched is not None:
        summary["watched"] = {"arm": WATCH[0], "set": WATCH[1], "object": WATCH[2], "seed": WATCH[3],
                              **{rule: (watched[rule] or {}).get("seed") == WATCH[3] for rule in RULES}}
        print(f"{' '.join(map(str, WATCH))} selected: " + ", ".join(f"{r} {summary['watched'][r]}" for r in RULES))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix(".json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(table(cells))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
