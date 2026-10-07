"""The full funnel: generate -> verify -> dedupe -> judge -> select.

    python -m brickwfc.funnel --tiles examples/terrain.json --n 1000 --size 32x32 --k 12 --out out/m3
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

from brickwfc.funnel.dedupe import dedupe
from brickwfc.funnel.features import feature_vector
from brickwfc.funnel.judge import Candidate, HeuristicJudge, Judge
from brickwfc.funnel.select import select
from brickwfc.funnel.verify import verify
from brickwfc.render2d import contact_sheet, render
from brickwfc.run import parse_size
from brickwfc.tileset import Tileset, load_tileset
from brickwfc.wfc import DEFAULT_MAX_ATTEMPTS, run


@dataclass(frozen=True)
class FunnelConfig:
    n: int = 1000
    width: int = 32
    height: int = 32
    seed: int = 0  # designs use seeds seed .. seed+n-1
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    water_tiles: tuple[str, ...] = ("water",)  # everything else counts as land
    min_connected: float = 0.9
    land_band: tuple[float, float] = (0.3, 0.9)
    dedupe_threshold: float = 0.05
    k: int = 12
    diversity: float = 1.0


@dataclass(frozen=True)
class StageStats:
    stage: str
    survivors: int  # designs left after this stage
    seconds: float


@dataclass
class FunnelStats:
    requested: int = 0
    stages: list[StageStats] = field(default_factory=list)
    check_failures: dict[str, int] = field(default_factory=dict)
    wfc_contradictions: int = 0
    selected_seeds: list[int] = field(default_factory=list)
    selected_scores: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class FunnelResult:
    selected: list[Candidate]
    stats: FunnelStats


def land_mask(grid: np.ndarray, tileset: Tileset, water_tiles: Sequence[str]) -> np.ndarray:
    water_ids = [tileset.index(name) for name in water_tiles]
    return ~np.isin(grid, water_ids)


def run_funnel(tileset: Tileset, config: FunnelConfig, judge: Judge | None = None) -> FunnelResult:
    judge = judge or HeuristicJudge()
    stats = FunnelStats()

    clock = time.perf_counter()
    generated: list[Candidate] = []
    for seed in range(config.seed, config.seed + config.n):
        result = run(tileset, (config.height, config.width), seed, config.max_attempts)
        stats.wfc_contradictions += result.stats.contradictions
        if result.grid is None:
            continue
        land = land_mask(result.grid, tileset, config.water_tiles)
        generated.append(Candidate(seed, result.grid, land, feature_vector(result.grid, land, tileset.num_tiles)))
    stats.requested = config.n
    stats.stages.append(StageStats("generate", len(generated), time.perf_counter() - clock))

    clock = time.perf_counter()
    verified: list[Candidate] = []
    for candidate in generated:
        checks = verify(candidate.land, config.min_connected, config.land_band)
        for check in checks:
            if not check.passed:
                stats.check_failures[check.name] = stats.check_failures.get(check.name, 0) + 1
        if all(check.passed for check in checks):
            verified.append(candidate)
    stats.stages.append(StageStats("verify", len(verified), time.perf_counter() - clock))

    clock = time.perf_counter()
    features = np.array([c.features for c in verified]).reshape(len(verified), -1)
    kept = dedupe(features, config.dedupe_threshold)
    unique = [verified[i] for i in kept]
    features = features[kept]
    stats.stages.append(StageStats("dedupe", len(unique), time.perf_counter() - clock))

    clock = time.perf_counter()
    scores = np.array([judge.score(c) for c in unique])
    stats.stages.append(StageStats("judge", len(unique), time.perf_counter() - clock))

    clock = time.perf_counter()
    picks = select(scores, features, config.k, config.diversity)
    stats.stages.append(StageStats("select", len(picks), time.perf_counter() - clock))
    stats.selected_seeds = [unique[i].seed for i in picks]
    stats.selected_scores = [float(scores[i]) for i in picks]
    return FunnelResult([unique[i] for i in picks], stats)


def format_counts(stats: FunnelStats) -> str:
    lines = [f"{'requested':>10}: {stats.requested:5d}"]
    previous = stats.requested
    for stage in stats.stages:
        lines.append(f"{stage.stage:>10}: {stage.survivors:5d}  (-{previous - stage.survivors})  {stage.seconds:.2f}s")
        previous = stage.survivors
    if stats.check_failures:
        lines.append("check failures: " + ", ".join(f"{k}={v}" for k, v in stats.check_failures.items()))
    lines.append(f"WFC contradictions: {stats.wfc_contradictions}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    defaults = FunnelConfig()
    parser = argparse.ArgumentParser(prog="python -m brickwfc.funnel", description=__doc__.splitlines()[0])
    parser.add_argument("--tiles", type=Path, required=True)
    parser.add_argument("--n", type=int, default=defaults.n, help="designs to generate")
    parser.add_argument("--size", type=parse_size, default=(defaults.width, defaults.height))
    parser.add_argument("--seed", type=int, default=defaults.seed)
    parser.add_argument("--k", type=int, default=defaults.k, help="designs to select")
    parser.add_argument("--water", nargs="+", default=list(defaults.water_tiles), help="non-land tile names")
    parser.add_argument("--min-connected", type=float, default=defaults.min_connected)
    parser.add_argument("--dedupe-threshold", type=float, default=defaults.dedupe_threshold)
    parser.add_argument("--diversity", type=float, default=defaults.diversity, help="lambda in selection")
    parser.add_argument("--out", type=Path, default=Path("out/funnel"), help="output directory")
    args = parser.parse_args(argv)

    tileset = load_tileset(args.tiles)
    width, height = args.size
    config = FunnelConfig(
        n=args.n, width=width, height=height, seed=args.seed, water_tiles=tuple(args.water),
        min_connected=args.min_connected, dedupe_threshold=args.dedupe_threshold, k=args.k, diversity=args.diversity,
    )
    result = run_funnel(tileset, config)
    print(format_counts(result.stats))

    args.out.mkdir(parents=True, exist_ok=True)
    if result.selected:
        sheet = contact_sheet([render(c.grid, tileset, scale=4) for c in result.selected], columns=4)
        sheet.save(args.out / "selected.png")
        print(f"wrote {args.out / 'selected.png'}")
    report = {"config": asdict(config), **asdict(result.stats)}
    (args.out / "stats.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {args.out / 'stats.json'}")
    return 0 if result.selected else 1
