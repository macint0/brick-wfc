"""Learn tile weights and adjacency rules from an example grid (M2).

    python -m brickwfc.learn --example out/m1.png --tiles examples/terrain.json \\
        --out-tiles out/learned.json --regen out/m2.png --size 32x32 --seed 1

Weights are tile frequencies; rules are exactly the directional neighbor pairs seen in the example.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from brickwfc.gridio import read_grid_csv, read_grid_png
from brickwfc.render2d import contact_sheet, render
from brickwfc.run import parse_size
from brickwfc.tileset import RGB, Tileset, load_tileset, neighbor_pairs, save_tileset, to_hex_color
from brickwfc.wfc import run


@dataclass(frozen=True)
class Example:
    """An example grid plus the names and colors of the tile ids it uses."""

    grid: np.ndarray  # (H, W) tile ids
    names: tuple[str, ...]
    colors: tuple[RGB, ...]


def learn_tileset(example: Example) -> Tileset:
    """Learn a tileset from an example grid.

    Tiles that never appear are dropped (a zero weight would make them unusable anyway), so the
    learned tile order is the example's order restricted to tiles that occur.
    """
    counts = np.bincount(example.grid.ravel(), minlength=len(example.names))
    present = np.nonzero(counts)[0]
    remap = np.full(len(example.names), -1)
    remap[present] = np.arange(len(present))
    grid = remap[example.grid]

    compat = np.zeros((4, len(present), len(present)), dtype=bool)
    for d in range(4):
        src, dst = neighbor_pairs(grid, d)
        compat[d, src.ravel(), dst.ravel()] = True

    return Tileset(
        names=tuple(example.names[i] for i in present),
        colors=tuple(example.colors[i] for i in present),
        weights=counts[present] / counts.sum(),
        compat=compat,
    )


def example_from_png(path: str | Path, reference: Tileset | None = None, scale: int | None = None) -> Example:
    """Load a PNG example. With a reference tileset, colors map to its tile ids and names;
    otherwise each distinct color becomes a tile named after its hex code."""
    grid, palette = read_grid_png(path, scale)
    if reference is None:
        return Example(grid, tuple(to_hex_color(c) for c in palette), tuple(palette))
    color_to_id = {color: i for i, color in enumerate(reference.colors)}
    unknown = [to_hex_color(c) for c in palette if c not in color_to_id]
    if unknown:
        raise ValueError(f"{path}: colors {unknown} are not in the reference tileset")
    ids = np.array([color_to_id[c] for c in palette])
    return Example(ids[grid], reference.names, reference.colors)


def example_from_csv(path: str | Path, reference: Tileset) -> Example:
    """Load a CSV of tile ids; ids index into ``reference``."""
    grid = read_grid_csv(path)
    if grid.min() < 0 or grid.max() >= reference.num_tiles:
        raise ValueError(f"{path}: tile ids must be in 0..{reference.num_tiles - 1}")
    return Example(grid, reference.names, reference.colors)


def learned_grid(example: Example, learned: Tileset) -> np.ndarray:
    """The example grid re-expressed in the learned tileset's tile ids."""
    ids = np.array([learned.names.index(n) if n in learned.names else -1 for n in example.names])
    return ids[example.grid]


def histogram(grid: np.ndarray, num_tiles: int) -> np.ndarray:
    counts = np.bincount(grid.ravel(), minlength=num_tiles)
    return counts / counts.sum()


def format_rule_diff(learned: Tileset, reference: Tileset) -> str:
    learned_rules, reference_rules = learned.rules(), reference.rules()
    if learned_rules == reference_rules:
        return f"rules match reference ({len(learned_rules)} directional rules)"
    missing = sorted(reference_rules - learned_rules)
    extra = sorted(learned_rules - reference_rules)
    return f"rules DIFFER from reference: missing {missing}, extra {extra}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.learn", description=__doc__.splitlines()[0])
    parser.add_argument("--example", type=Path, required=True, help="example grid (.png or .csv)")
    parser.add_argument("--tiles", type=Path, help="reference tileset for names/colors (required for .csv)")
    parser.add_argument("--scale", type=int, help="pixels per cell in a PNG example (default: auto-detect)")
    parser.add_argument("--out-tiles", type=Path, help="write the learned tileset JSON here")
    parser.add_argument("--regen", type=Path, help="regenerate with the learned tileset and save a PNG here")
    parser.add_argument("--size", type=parse_size, help="WIDTHxHEIGHT for --regen (default: example size)")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    reference = load_tileset(args.tiles) if args.tiles else None
    if args.example.suffix.lower() == ".csv":
        if reference is None:
            parser.error("--tiles is required for a CSV example")
        example = example_from_csv(args.example, reference)
    else:
        example = example_from_png(args.example, reference, args.scale)

    learned = learn_tileset(example)
    height, width = example.grid.shape
    print(f"example: {width}x{height}, {learned.num_tiles} tiles")
    for name, weight in zip(learned.names, learned.weights):
        print(f"  {name:>10}  weight {weight:.3f}")
    if reference is not None:
        print(format_rule_diff(learned, reference))
    if args.out_tiles:
        save_tileset(learned, args.out_tiles)
        print(f"wrote {args.out_tiles}")

    if args.regen:
        width, height = args.size or (width, height)
        result = run(learned, height, width, args.seed)
        if result.grid is None:
            print(f"regeneration failed after {result.stats.attempts} attempts")
            return 1
        example_grid = learned_grid(example, learned)
        args.regen.parent.mkdir(parents=True, exist_ok=True)
        contact_sheet([render(example_grid, learned), render(result.grid, learned)], columns=2).save(args.regen)
        diff = np.abs(histogram(example_grid, learned.num_tiles) - histogram(result.grid, learned.num_tiles)).sum()
        print(f"regenerated {width}x{height} (attempts={result.stats.attempts}); histogram L1 distance to example: {diff:.3f}")
        print(f"wrote {args.regen} (left: example, right: regenerated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
