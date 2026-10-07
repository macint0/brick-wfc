"""Generate 3D builds of 1x1 plates and export them as LDraw files.

    python -m brickwfc.bricks --size 12x12x8 --seed 1 --runs 5 --out out/m4
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

from brickwfc.bricks.build import export_plates
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.plates import plate_tileset
from brickwfc.bricks.support import floating_cells
from brickwfc.wfc import run


def parse_size3(text: str) -> tuple[int, int, int]:
    """``WIDTHxDEPTHxHEIGHT`` in studs, studs, plates -> grid shape (height, depth, width)."""
    try:
        width, depth, height = (int(v) for v in text.lower().split("x"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected WIDTHxDEPTHxHEIGHT like 12x12x8, got {text!r}") from None
    return height, depth, width


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.bricks", description=__doc__.splitlines()[0])
    parser.add_argument("--size", type=parse_size3, default=(8, 12, 12), help="WIDTHxDEPTHxHEIGHT (default 12x12x8)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--colors", default="red,white,blue,yellow", help="comma-separated color names")
    parser.add_argument("--empty-weight", type=float, default=4.0)
    parser.add_argument("--out", type=Path, default=Path("out/bricks"))
    args = parser.parse_args(argv)

    plates = plate_tileset(colors_by_name(args.colors.split(",")), empty_weight=args.empty_weight)
    times, floating_total, failures = [], 0, 0
    for seed in range(args.seed, args.seed + args.runs):
        result = run(plates.tileset, args.size, seed)
        times.append(result.stats.wall_time_s)
        if result.grid is None:
            failures += 1
            continue
        floating = int(floating_cells(plates.solid[result.grid]).sum())
        floating_total += floating
        stem = args.out / f"plates_seed{seed}"
        export_plates(result.grid, plates, stem.with_suffix(".ldr"), stem.with_suffix(".png"), f"brickwfc plates seed {seed}")
        count = int(plates.solid[result.grid].sum())
        print(f"seed={seed} plates={count} floating={floating} attempts={result.stats.attempts} "
              f"time={result.stats.wall_time_s:.2f}s -> {stem}.ldr")
    print(f"runs={args.runs} failures={failures} floating plates total={floating_total} "
          f"mean time={statistics.mean(times):.2f}s")
    return 0 if failures == 0 and floating_total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
