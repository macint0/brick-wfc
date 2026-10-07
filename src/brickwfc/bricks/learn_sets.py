"""Learn part and color weights from real sets in the LDraw OMR (M7).

    python -m brickwfc.bricks.learn_sets --out out/m7            (default: 20 sets, fetched to data/omr)

Pipeline: fetch .mpd -> flatten submodels -> voxelize the parts the generator knows into the
M5 tile representation -> count tiles per (shape, color) = learned cell coverage -> generate
stability-aware builds with those weights and compare their part/color mix to the learned one
(and to the default uniform weights as a baseline).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from brickwfc.bricks.__main__ import parse_size3
from brickwfc.bricks.build import export_build
from brickwfc.bricks.colors import BrickColor, color_for_code
from brickwfc.bricks.parts import PLATES, PartSet, PlacedPart, extract_parts, part_tileset
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.support import is_stable
from brickwfc.bricks.voxelize import VoxelizeReport, tile_grid, voxelize
from brickwfc.ldraw.fetch import fetch_set
from brickwfc.ldraw.mpd import flatten
from brickwfc.wfc import run

DEFAULT_SETS = (
    "10013-1 10014-1 10015-1 10016-1 10017-1 10018-1 10019-1 10020-1 10036-1 10037-1 "
    "10124-1 10128-1 10129-1 10133-1 10134-1 10143-1 10156-1 10158-1 10159-1 10170-1"
).split()

Coverage = dict[tuple[str, str], float]  # (shape name, color name) -> cells


def load_set(path: Path) -> tuple[list[PlacedPart], VoxelizeReport]:
    return voxelize(flatten(path.read_text(encoding="utf-8", errors="replace")))


def learn_coverage(models: Sequence[list[PlacedPart]]) -> tuple[Coverage, list[BrickColor]]:
    """Tile counts per (shape, color) over the voxelized models, plus every color seen.

    Counting tiles of the M5 representation equals summing part areas; we count tiles so the
    learned quantity is literally the tile frequency (as in M2).
    """
    colors = sorted({p.color for model in models for p in model}, key=lambda c: c.ldraw)
    parts = part_tileset(list(PLATES.values()), colors)
    coverage: Counter[tuple[str, str]] = Counter()
    for model in models:
        if not model:
            continue
        grid = tile_grid(model, parts)
        for tile, count in zip(*np.unique(grid, return_counts=True)):
            info = parts.infos[tile]
            if info.solid:
                coverage[(info.shape.name, info.color.name)] += int(count)
    return dict(coverage), colors


def top_colors(coverage: Coverage, colors: list[BrickColor], k: int) -> tuple[Coverage, list[BrickColor]]:
    """Restrict to the ``k`` colors covering the most cells (keeps the tileset small)."""
    by_color: Counter[str] = Counter()
    for (_, color), cells in coverage.items():
        by_color[color] += cells
    keep = [name for name, _ in by_color.most_common(k)]
    kept_colors = [c for c in colors if c.name in keep]
    return {key: v for key, v in coverage.items() if key[1] in keep}, kept_colors


def shares(coverage: Mapping[tuple[str, str], float], index: int) -> dict[str, float]:
    """Share of cells per part type (index 0, rotations merged) or per color (index 1)."""
    totals: Counter[str] = Counter()
    for key, cells in coverage.items():
        name = key[0].removesuffix("_r90") if index == 0 else key[1]
        totals[name] += cells
    whole = sum(totals.values())
    return {name: cells / whole for name, cells in sorted(totals.items())}


def l1(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    return sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in set(a) | set(b))


def generated_coverage(parts: PartSet, shape: tuple[int, int, int], seeds: range, out_dir: Path | None) -> tuple[Coverage, int]:
    """Generate stability-aware builds and count their cells per (shape, color); also count stable ones."""
    constraint = SupportConstraint(parts)
    coverage: Counter[tuple[str, str]] = Counter()
    stable = 0
    for seed in seeds:
        result = run(parts.tileset, shape, seed, constraints=[constraint])
        if result.grid is None:
            continue
        placed, _ = extract_parts(result.grid, parts)
        stable += is_stable(placed, parts.solid[result.grid])
        for p in placed:
            coverage[(p.shape.name, p.color.name)] += len(p.cells())
        if out_dir is not None and seed == seeds[0]:
            stem = out_dir / f"learned_seed{seed}"
            export_build(result.grid, placed, parts, stem.with_suffix(".ldr"), stem.with_suffix(".png"), f"brickwfc learned seed {seed}")
    return dict(coverage), stable


def format_shares(title: str, learned: dict[str, float], generated: dict[str, float], baseline: dict[str, float]) -> str:
    lines = [f"{title:<16} {'learned':>8} {'generated':>10} {'uniform':>8}"]
    for name in sorted(set(learned) | set(generated) | set(baseline), key=lambda n: -learned.get(n, 0)):
        lines.append(f"{name:<16} {learned.get(name, 0):8.3f} {generated.get(name, 0):10.3f} {baseline.get(name, 0):8.3f}")
    lines.append(f"{'L1 to learned':<16} {'':>8} {l1(generated, learned):10.3f} {l1(baseline, learned):8.3f}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.bricks.learn_sets", description=__doc__.splitlines()[0])
    parser.add_argument("--sets", nargs="+", default=list(DEFAULT_SETS))
    parser.add_argument("--data", type=Path, default=Path("data/omr"))
    parser.add_argument("--top-colors", type=int, default=6)
    parser.add_argument("--size", type=parse_size3, default=(5, 8, 8), help="WIDTHxDEPTHxHEIGHT of generated builds")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, default=Path("out/m7"))
    args = parser.parse_args(argv)

    models, reports = [], {}
    for set_number in args.sets:
        placed, report = load_set(fetch_set(set_number, args.data))
        models.append(placed)
        reports[set_number] = asdict(report)
        print(f"{set_number}: {report.total_parts:5d} parts, kept {report.kept:4d} "
              f"(unrecognized {report.unrecognized}, tilted {report.tilted}, off-grid {report.off_grid}, overlapping {report.overlapping})")
    sets_used = sum(1 for m in models if m)
    coverage, colors = learn_coverage(models)
    coverage, colors = top_colors(coverage, colors, args.top_colors)
    print(f"learned from {sets_used} sets with recognized parts; {sum(len(m) for m in models)} parts; "
          f"colors {[c.name for c in colors]}")

    args.out.mkdir(parents=True, exist_ok=True)
    learned = part_tileset(list(PLATES.values()), colors, coverage=coverage)
    uniform = part_tileset(list(PLATES.values()), colors)
    seeds = range(args.seed, args.seed + args.runs)
    generated, stable = generated_coverage(learned, args.size, seeds, args.out)
    baseline, _ = generated_coverage(uniform, args.size, seeds, None)

    text = "\n\n".join([
        format_shares("part type", shares(coverage, 0), shares(generated, 0), shares(baseline, 0)),
        format_shares("color", shares(coverage, 1), shares(generated, 1), shares(baseline, 1)),
    ])
    print(text)
    print(f"generated {len(seeds)} builds with learned weights, {stable} stable")
    (args.out / "learned.json").write_text(json.dumps({
        "sets": args.sets,
        "sets_with_recognized_parts": sets_used,
        "colors": [c.name for c in colors],
        "coverage": [{"shape": s, "color": c, "cells": v} for (s, c), v in sorted(coverage.items())],
        "voxelize_reports": reports,
    }, indent=2), encoding="utf-8")
    (args.out / "distribution.txt").write_text(text + "\n", encoding="utf-8")
    print(f"wrote {args.out}/learned.json, distribution.txt, learned_seed{args.seed}.ldr/.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
