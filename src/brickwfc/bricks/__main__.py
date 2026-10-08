"""Generate 3D plate builds and export them as LDraw files.

    python -m brickwfc.bricks --size 12x12x8 --seed 1 --runs 5 --out out/m5
    python -m brickwfc.bricks --parts plate1x1 --support cell --out out/m4     (M4: 1x1 plates only)
    python -m brickwfc.bricks --parts plate2x4,brick1x2,brick2x2,tile1x2 --max-backtracks 500 --out out/m8

--support: none (no rule), cell (every stud needs a solid cell below), aware (part-level
support enforced during propagation, M6).
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

from brickwfc.bricks.build import export_build
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import CATALOG, PLATES, extract_parts, part_tileset
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.support import overhanging_parts, unsupported_parts
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
    parser.add_argument("--parts", default=",".join(PLATES), help="comma-separated catalog names, e.g. plate2x4,brick1x2,tile2x2 "
                        "(default: the four M5 plates; see parts.CATALOG)")
    parser.add_argument("--colors", default="red,white,blue,yellow", help="comma-separated color names")
    parser.add_argument("--empty-weight", type=float, default=1.0)
    parser.add_argument("--support", choices=["none", "cell", "aware"], default="aware")
    parser.add_argument("--max-backtracks", type=int, default=0, help="per attempt; try 500 with bricks and tiles")
    parser.add_argument("--out", type=Path, default=Path("out/bricks"))
    args = parser.parse_args(argv)

    part_list = [CATALOG[name] for name in args.parts.split(",")]
    rule = "cell" if args.support == "cell" else "none"
    parts = part_tileset(part_list, colors_by_name(args.colors.split(",")), args.empty_weight, rule)
    constraints = [SupportConstraint(parts)] if args.support == "aware" else []
    times, unsupported_total, broken_total, failures = [], 0, 0, 0
    for seed in range(args.seed, args.seed + args.runs):
        result = run(parts.tileset, args.size, seed, constraints=constraints, max_backtracks=args.max_backtracks)
        times.append(result.stats.wall_time_s)
        if result.grid is None:
            failures += 1
            continue
        placed, errors = extract_parts(result.grid, parts)
        filled = parts.solid[result.grid]
        unsupported = len(unsupported_parts(placed, filled))
        unsupported_total += unsupported
        broken_total += len(errors)
        stem = args.out / f"build_seed{seed}"
        export_build(result.grid, placed, parts, stem.with_suffix(".ldr"), stem.with_suffix(".png"), f"brickwfc build seed {seed}")
        print(f"seed={seed} parts={len(placed)} broken={len(errors)} unsupported={unsupported} "
              f"overhanging={len(overhanging_parts(placed, filled))} "
              f"attempts={result.stats.attempts} time={result.stats.wall_time_s:.2f}s -> {stem}.ldr")
    print(f"runs={args.runs} failures={failures} broken parts={broken_total} unsupported parts={unsupported_total} "
          f"mean time={statistics.mean(times):.2f}s")
    return 0 if failures == 0 and broken_total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
