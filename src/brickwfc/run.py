"""Command-line entry point for 2D WFC.

    python -m brickwfc.run --tiles examples/terrain.json --size 32x32 --seed 1 --out out/m1.png
    python -m brickwfc.run --tiles examples/terrain.json --size 32x32 --seed 1 --runs 100 --stats out/m1_stats.json

With ``--runs N``, seeds ``seed .. seed+N-1`` are run and a summary is printed; ``--out`` saves the
grid of the first successful run.
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import asdict
from pathlib import Path

from brickwfc.render2d import save_png
from brickwfc.tileset import load_tileset
from brickwfc.wfc import DEFAULT_MAX_ATTEMPTS, RunStats, run


def parse_size(text: str) -> tuple[int, int]:
    """Parse ``WIDTHxHEIGHT`` (e.g. ``32x32``) into (width, height)."""
    try:
        width, height = (int(part) for part in text.lower().split("x"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected WIDTHxHEIGHT like 32x32, got {text!r}") from None
    if width < 1 or height < 1:
        raise argparse.ArgumentTypeError(f"size must be positive, got {text!r}")
    return width, height


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.run", description=__doc__.splitlines()[0])
    parser.add_argument("--tiles", type=Path, required=True, help="tileset JSON")
    parser.add_argument("--size", type=parse_size, default=(32, 32), help="WIDTHxHEIGHT (default 32x32)")
    parser.add_argument("--seed", type=int, default=0, help="base seed (non-negative)")
    parser.add_argument("--runs", type=int, default=1, help="number of runs, seeds seed..seed+runs-1")
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--out", type=Path, help="PNG path for the first successful grid")
    parser.add_argument("--scale", type=int, default=8, help="pixels per cell in the PNG")
    parser.add_argument("--stats", type=Path, help="write per-run stats as JSON")
    return parser


def format_stats(stats: RunStats) -> str:
    status = "ok" if stats.success else "FAILED"
    return (
        f"seed={stats.seed} {status} attempts={stats.attempts} contradictions={stats.contradictions} "
        f"cells_collapsed={stats.cells_collapsed} time={stats.wall_time_s:.3f}s"
    )


def format_summary(all_stats: list[RunStats]) -> str:
    successes = sum(s.success for s in all_stats)
    return "\n".join(
        [
            f"runs:                {len(all_stats)}",
            f"success rate:        {successes / len(all_stats):.1%} ({successes}/{len(all_stats)})",
            f"mean attempts:       {statistics.mean(s.attempts for s in all_stats):.2f}",
            f"mean contradictions: {statistics.mean(s.contradictions for s in all_stats):.2f}",
            f"mean cells/run:      {statistics.mean(s.cells_collapsed for s in all_stats):.1f}",
            f"mean time:           {statistics.mean(s.wall_time_s for s in all_stats):.3f}s",
            f"total time:          {sum(s.wall_time_s for s in all_stats):.2f}s",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.seed < 0:
        raise SystemExit("--seed must be non-negative")
    if args.runs < 1:
        raise SystemExit("--runs must be >= 1")
    width, height = args.size
    tileset = load_tileset(args.tiles)

    all_stats: list[RunStats] = []
    saved = False
    for i in range(args.runs):
        result = run(tileset, height, width, seed=args.seed + i, max_attempts=args.max_attempts)
        all_stats.append(result.stats)
        if args.runs == 1:
            print(format_stats(result.stats))
        if args.out is not None and result.grid is not None and not saved:
            save_png(result.grid, tileset, args.out, args.scale)
            print(f"wrote {args.out}")
            saved = True

    if args.runs > 1:
        print(format_summary(all_stats))
    if args.stats is not None:
        args.stats.parent.mkdir(parents=True, exist_ok=True)
        args.stats.write_text(json.dumps([asdict(s) for s in all_stats], indent=2), encoding="utf-8")
        print(f"wrote {args.stats}")
    return 0 if any(s.success for s in all_stats) else 1


if __name__ == "__main__":
    raise SystemExit(main())
