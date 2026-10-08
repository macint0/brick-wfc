"""Alternate builds from a set or a parts list (M12): generate -> verify -> dedupe -> judge -> select.

    python -m brickwfc.alt 6372-1 --n 200 --k 8
    python -m brickwfc.alt my_parts.csv --shape pyramid --out out/alt/mine
    python -m brickwfc.alt 6372-1 --shape ship.png --color-map ship_colors.png

Input: an OMR set number, an .mpd/.ldr model or a .csv parts list (``inputs.py``). Style: the M10
statistics, from the fold that held the set out if it is one of the M10 sets, else from all of them.

  generate  ``--n`` candidates, seeds ``--seed`` .. ``--seed + n - 1``, with the bottom-up builder D2
            and the learned style bias (or ``--generator wfc``), in parallel (``candidates.py``)
  verify    integrity, inventory, support, shape, physics on a table (``candidates.py``), then a size
            floor: candidates with fewer contact events than the ``--min-size-quantile`` quantile of the
            verified ones fail "too_small", so one tiny build cannot shrink every judge sample; with a
            target shape, a fill floor: candidates filling less than ``--fill-floor`` x the 90th
            percentile of the verified ones' fill fail "low_fill" (M12b)
  dedupe    near-duplicates in feature space (``features.py``, ``funnel.dedupe``)
  judge     minus the divergence of the build's contact statistics from the learned ones (``style``),
            size-matched: every build subsampled to the smallest one's number of contact events
  select    top ``--k`` by judge + ``--diversity`` x distance to the builds already picked
            (``funnel.select``); judge scores are standardized and feature distances divided by their
            median, so the two terms are on comparable scales. With a target shape the score is
            z(judge) + ``--fill-weight`` x z(fill) (M12b; 0 restores judge only)

Without a target shape, the grid is a cube in millimetres (2.5 plates tall per stud of width) with
volume ``--room`` x the inventory's; ``--height`` fixes the height instead (M10's grid: ``--height 12``). With
``--shape`` (a primitive, a silhouette image with optional ``--height-map`` and ``--color-map``, a
model, a BrickGPT structure or a mesh; ``target.py``), the shape is scaled to the inventory's volume and the generators are told to fill
it. Writes, under ``--out``: build_NN.ldr (one
``0 STEP`` per layer, bottom to top), build_NN.png, sheet.png, stats.json, and candidates.jsonl (every
candidate as it is generated, so a killed run resumes: rerun the same command).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from brickwfc.alt.candidates import GENERATORS, VERIFY_VERSION, Candidate, Context, generate
from brickwfc.alt.features import feature_vector, occupancy
from brickwfc.alt.inputs import (CATALOGS, DATA_DIR, SETS_FILE, STYLE_DIR, STYLE_FILES, STYLE_VERSION, Source,
                                 learned_style, load_source)
from brickwfc.alt.output import layer_steps, write_build, write_sheet
from brickwfc.alt.target import Target, load_target
from brickwfc.bricks.inventory import inventory_cells, utilization
from brickwfc.bricks.shapes import SHAPES, fill, iou
from brickwfc.bricks.style import StyleStats, events, matched_divergence
from brickwfc.bricks.voxelize import voxelize
from brickwfc.experiments.inventory import grid_for
from brickwfc.experiments.style import InlineExecutor
from brickwfc.funnel.dedupe import dedupe
from brickwfc.funnel.pipeline import StageStats, format_stages
from brickwfc.funnel.select import select
from brickwfc.ldraw.export import PLATE_LDU, STUD_LDU
from brickwfc.ldraw.mpd import flatten

SHAPE_EMPTY_WEIGHT = 0.05  # per part type: a solid share of ~95%, so the builders try to fill the shape
CHUNKS_PER_WORKER = 4
PLATES_PER_STUD = STUD_LDU / PLATE_LDU  # 2.5: plate layers per stud of width, for a cube in millimetres


@dataclass(frozen=True)
class AltConfig:
    n: int = 200
    k: int = 8
    seed: int = 0
    generator: str = "d2"
    height: int | None = None  # plates (no target shape); None: a cube, see cube_grid
    room: float = 1.5  # grid volume / inventory volume (no target shape)
    balanced: bool = True
    bridge: bool = True
    connect: bool = True
    connect_rounds: int = 10  # repair rounds (see bottomup); 1 reproduces the step-2b table
    shape: str | None = None  # see target.py
    height_map: str | None = None
    color_map: str | None = None
    shape_height: int = 6  # plates, for a silhouette without a height map
    shape_exact: bool = False  # a model shape keeps its exact cells (overhangs) instead of solid columns
    shape_columns: bool = False  # a 3D target (BrickGPT structure, mesh) becomes solid columns (its heightfield)
    voxels: int = 32  # mesh target: cells along its longest side before scaling
    mesh_up: str = "y"
    hollow: int = 0  # 3D target: shell thickness in cells, plus internal pillars (0: solid)
    supports: bool = False  # 3D target: support columns under overhangs out of a part's reach
    support_height: int = 0  # with supports: only columns at most this many cells tall (0: any)
    open_tops: bool = True  # with a target shape: studless top cells only under empty target cells
    strength: float = 1.0  # exponent on the learned style weights
    max_clutch: float = math.inf  # physics: keep builds needing at most this clutch per stud
    wfc_time_limit_s: float = 30.0
    min_size_quantile: float = 0.1
    fill_floor: float = 0.5  # with a target: fail builds filling < this x the 90th-percentile fill (0: off)
    fill_weight: float = 1.0  # with a target: selection score z(judge) + this x z(fill) (0: judge only)
    judge_draws: int = 5
    dedupe_threshold: float = 0.05
    diversity: float = 0.5


@dataclass(frozen=True)
class Selected:
    candidate: Candidate
    judge: float


@dataclass
class FunnelReport:
    requested: int
    stages: list[StageStats]
    check_failures: dict[str, int]
    size_floor: int  # contact events
    judge_size: int  # contact events every judged build was subsampled to
    selected: list[Selected]
    candidates: list[Candidate]


def cube_grid(cells: float, room: float) -> tuple[int, int, int]:
    """(Y, Z, X) of a cube in millimetres (a plate is 0.4 studs tall, so 2.5 plates per stud of width)
    with volume about ``room`` x ``cells``."""
    volume = room * cells
    side = max(2, math.ceil((volume / PLATES_PER_STUD) ** (1 / 3)))
    return (max(1, math.ceil(volume / side**2)), side, side)


def make_target(source: Source, config: AltConfig, data_dir: Path = DATA_DIR) -> Target | None:
    if config.shape is None:
        return None
    return load_target(config.shape, inventory_cells(source.inventory), source.colors,
                       Path(config.height_map) if config.height_map else None,
                       Path(config.color_map) if config.color_map else None, config.shape_height, data_dir,
                       config.shape_exact, config.shape_columns, voxels=config.voxels, up=config.mesh_up,
                       hollow=config.hollow, supports=config.supports, support_height=config.support_height)


def make_context(source: Source, stats: StyleStats, config: AltConfig, target: Target | None = None) -> Context:
    if target is None:
        grid = (cube_grid(inventory_cells(source.inventory), config.room) if config.height is None
                else grid_for(source.inventory, config.height, config.room))
        mask = preferred = None
        empty = config.room - 1
    else:
        mask, preferred = target.mask, target.preferred
        grid, empty = mask.shape, SHAPE_EMPTY_WEIGHT
    return Context(source.inventory, source.colors, stats, grid, mask, preferred, empty, config.strength,
                   config.generator, config.max_clutch, config.wfc_time_limit_s, config.balanced,
                   config.bridge, config.connect, config.connect_rounds, config.open_tops and target is not None)


# Generation, resumable ---------------------------------------------------------------------------


def cache_key(source: Source, style_label: str, context: Context) -> dict:
    """What a cached candidate depends on (besides its seed); normalized through JSON."""
    key = {
        "source": source.name, "inventory": sorted([*k, v] for k, v in source.inventory.items()), "style": style_label,
        "grid": list(context.grid), "mask": None if context.mask is None else np.argwhere(context.mask).tolist(),
        "preferred": None if context.preferred is None else context.preferred.tolist(),
        "empty_weight_per_part": context.empty_weight_per_part, "strength": context.strength,
        "generator": context.generator, "balanced": context.balanced, "bridge": context.bridge,
        "connect": context.connect, "connect_rounds": context.connect_rounds,        "verify_version": VERIFY_VERSION, "max_clutch": context.max_clutch,
        "wfc_time_limit_s": context.wfc_time_limit_s,
    }
    if context.open_tops:  # only when on, so caches from before the rule stay valid
        key["open_tops"] = True
    return json.loads(json.dumps(key))


def load_cache(path: Path, key: dict) -> dict[int, Candidate]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or json.loads(lines[0]).get("key") != key:
        raise SystemExit(f"{path} holds candidates of a different setup; pass --fresh or choose another --out")
    candidates = (Candidate.from_json(json.loads(line)) for line in lines[1:] if line.strip())
    return {c.seed: c for c in candidates}


def generate_all(context: Context, seeds: Sequence[int], cache: Path, key: dict, workers: int) -> list[Candidate]:
    """Candidates for ``seeds``, reusing and extending ``cache``; returned in seed order."""
    done = load_cache(cache, key)
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"key": key}) + "\n", encoding="utf-8")
    pending = [s for s in seeds if s not in done]
    size = max(1, math.ceil(len(pending) / (workers * CHUNKS_PER_WORKER)))
    chunks = [pending[i : i + size] for i in range(0, len(pending), size)]
    with ProcessPoolExecutor(workers) if workers > 1 else InlineExecutor() as pool:
        futures = [pool.submit(generate, context, chunk) for chunk in chunks]
        for i, future in enumerate(futures):  # collected in seed order: the cache is the same for any worker count
            batch = future.result()
            with cache.open("a", encoding="utf-8") as f:
                f.writelines(json.dumps(c.to_json()) + "\n" for c in batch)
            done.update((c.seed, c) for c in batch)
            if (i + 1) % workers == 0 or i + 1 == len(futures):
                print(f"  generated {sum(s in done for s in seeds)}/{len(seeds)}", flush=True)
    return [done[s] for s in seeds]


# The rest of the funnel ----------------------------------------------------------------------------


def standardized(values: np.ndarray) -> np.ndarray:
    """z-scores (0 everywhere when the values are all equal)."""
    return (values - values.mean()) / (values.std() or 1.0)


def run_funnel(candidates: list[Candidate], context: Context, stats: StyleStats, config: AltConfig,
               generate_seconds: float) -> FunnelReport:
    stages = [StageStats("generate", sum("generate" not in c.failed for c in candidates), generate_seconds)]
    failures = dict(Counter(name for c in candidates for name in c.failed))

    clock = time.perf_counter()
    valid = [c for c in candidates if c.valid]
    found = {c.seed: events(c.placed) for c in valid}
    floor = int(np.quantile([found[c.seed].count for c in valid], config.min_size_quantile, method="lower")) if valid else 0
    verified = [c for c in valid if found[c.seed].count >= floor]
    if len(verified) < len(valid):
        failures["too_small"] = len(valid) - len(verified)
    # With a target shape: how much of it each build fills, and a floor relative to the best builds, so a
    # stub that happens to match the style statistics is not selected over builds that fill the shape.
    filled_share: dict[int, float] = {}
    if context.mask is not None and verified:
        filled_share = {c.seed: fill(occupancy(c.placed, context.grid), context.mask) for c in verified}
        fill_floor = config.fill_floor * float(np.quantile(list(filled_share.values()), 0.9))
        kept = [c for c in verified if filled_share[c.seed] >= fill_floor]
        if len(kept) < len(verified):
            failures["low_fill"] = len(verified) - len(kept)
        verified = kept
    stages.append(StageStats("verify", len(verified), time.perf_counter() - clock))

    clock = time.perf_counter()
    colors = [color.name for color in context.colors]
    features = np.array([feature_vector(c.placed, context.grid, colors) for c in verified])
    features = features.reshape(len(verified), features.shape[1] if verified else 0)
    kept = dedupe(features, config.dedupe_threshold)
    unique, features = [verified[i] for i in kept], features[kept]
    stages.append(StageStats("dedupe", len(unique), time.perf_counter() - clock))

    clock = time.perf_counter()
    size = min((found[c.seed].count for c in unique), default=0)
    scores = np.array([-matched_divergence(found[c.seed], size, stats, np.random.default_rng([0, c.seed]),
                                           config.judge_draws) for c in unique])
    stages.append(StageStats("judge", len(unique), time.perf_counter() - clock))

    clock = time.perf_counter()
    picks: list[int] = []
    if unique:
        z = standardized(scores)
        if filled_share and config.fill_weight:  # with a target: judge and fill, both standardized
            z = z + config.fill_weight * standardized(np.array([filled_share[c.seed] for c in unique]))
        distances = np.linalg.norm(features[:, None] - features[None, :], axis=-1)[np.triu_indices(len(unique), 1)]
        scale = float(np.median(distances)) if distances.size and np.median(distances) > 0 else 1.0
        picks = select(z, features / scale, config.k, config.diversity)
    stages.append(StageStats("select", len(picks), time.perf_counter() - clock))
    selected = [Selected(unique[i], float(scores[i])) for i in picks]
    return FunnelReport(len(candidates), stages, failures, floor, size, selected, candidates)


def real_model_judge(source: Source, stats: StyleStats, size: int, draws: int) -> tuple[float, int] | None:
    """The real model's judge (its on-grid parts, voxelized) at the builds' judge size, or at its own size
    if it is smaller; None without a model or with no on-grid parts."""
    if source.model is None:
        return None
    placed, _ = voxelize(flatten(source.model))
    if not placed:
        return None
    found = events(placed)
    if found.count == 0:
        return None
    return -matched_divergence(found, size, stats, np.random.default_rng([1]), draws), min(size, found.count)


# Output -----------------------------------------------------------------------------------------------


def write_outputs(source: Source, context: Context, report: FunnelReport, out: Path) -> list[dict]:
    rows, previews = [], []
    for rank, chosen in enumerate(report.selected, 1):
        c = chosen.candidate
        ldr, png = write_build(c.placed, context.grid, out / f"build_{rank:02d}",
                               f"Alternate build {rank} from {source.name} (seed {c.seed})")
        previews.append(png)
        row = {"rank": rank, "seed": c.seed, "ldr": ldr.name, "png": png.name, "parts": len(c.placed),
               "clusters": c.clusters,
               "steps": len(layer_steps(c.placed)), "judge": chosen.judge, "clutch": c.clutch,
               "utilization_pct": 100 * utilization(list(c.placed), source.inventory),
               "seconds": c.seconds, "physics_seconds": c.physics_seconds}
        if context.mask is not None:
            filled = occupancy(c.placed, context.grid)
            row.update(fill_pct=100 * fill(filled, context.mask), iou=iou(filled, context.mask))
        rows.append(row)
    if previews:
        write_sheet(previews, out / "sheet.png")
    return rows


def format_selected(rows: list[dict]) -> str:
    lines = ["rank  seed  parts  used%   judge   clutch  steps"]
    lines += [f"{r['rank']:4d} {r['seed']:5d} {r['parts']:6d} {r['utilization_pct']:6.1f} {r['judge']:7.3f} "
              f"{r['clutch']:8.1f} {r['steps']:6d}" for r in rows]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    defaults = AltConfig()
    parser = argparse.ArgumentParser(prog="python -m brickwfc.alt", description=__doc__.splitlines()[0])
    parser.add_argument("input", help="OMR set number (e.g. 6372-1), .mpd/.ldr model, or .csv parts list")
    parser.add_argument("--shape", help=f"target shape, scaled to the inventory's volume: one of {sorted(SHAPES)}, "
                        "a silhouette image, an .ldr/.mpd model or a set number, a BrickGPT structure "
                        "(brickgpt:<structure id> or a .txt in its format), or a watertight .obj/.stl/.ply/.off mesh")
    parser.add_argument("--height-map", help="grey image, same size as the silhouette: height in plates")
    parser.add_argument("--color-map", help="color image, same size as the silhouette: preferred colors")
    parser.add_argument("--shape-height", type=int, default=defaults.shape_height,
                        help="plates, for a silhouette without a height map")
    parser.add_argument("--shape-exact", action="store_true",
                        help="model shape: keep its exact cells (overhangs, rooms) instead of solid columns")
    parser.add_argument("--shape-columns", action="store_true",
                        help="3D target (brickgpt:<id>, .txt or mesh): solid columns (its heightfield) instead of its cells")
    parser.add_argument("--voxels", type=int, default=defaults.voxels,
                        help="mesh target: cells along its longest side before scaling (detail kept)")
    parser.add_argument("--mesh-up", choices=("y", "z"), default=defaults.mesh_up, help="mesh target: up axis")
    parser.add_argument("--hollow", type=int, default=defaults.hollow,
                        help="3D target: a shell this many cells thick plus internal pillars (0: solid)")
    parser.add_argument("--no-open-tops", action="store_true",
                        help="with a target shape: let studless tops (tiles) sit under target cells (as before M12b 1d)")
    parser.add_argument("--supports", action="store_true",
                        help="3D target: add support columns under overhangs out of a part's reach (extra cells)")
    parser.add_argument("--support-height", type=int, default=defaults.support_height,
                        help="with --supports: only columns at most this many cells (plates) tall (0: any)")
    parser.add_argument("--k", type=int, default=defaults.k, help="builds to select")
    parser.add_argument("--n", type=int, default=defaults.n, help="candidates to generate")
    parser.add_argument("--seed", type=int, default=defaults.seed)
    parser.add_argument("--generator", choices=GENERATORS, default=defaults.generator)
    parser.add_argument("--height", type=int, default=defaults.height,
                        help="grid height in plates (no --shape; default: a cube)")
    parser.add_argument("--no-balance", action="store_true", help="d2 without the tip-over check (as in M9b-M11)")
    parser.add_argument("--no-bridge", action="store_true", help="d2 without the preference for joining clusters")
    parser.add_argument("--no-connect", action="store_true", help="d2 without the pass that makes builds one piece")
    parser.add_argument("--connect-rounds", type=int, default=defaults.connect_rounds,
                        help="repair rounds of the connect pass (1: as in step 2b)")
    parser.add_argument("--room", type=float, default=defaults.room, help="grid volume / inventory volume (no --shape)")
    parser.add_argument("--strength", type=float, default=defaults.strength, help="exponent on the style weights")
    parser.add_argument("--max-clutch", type=float, default=defaults.max_clutch, help="physics limit per stud")
    parser.add_argument("--wfc-time-limit", type=float, default=defaults.wfc_time_limit_s, help="seconds per WFC build")
    parser.add_argument("--min-size-quantile", type=float, default=defaults.min_size_quantile)
    parser.add_argument("--fill-floor", type=float, default=defaults.fill_floor,
                        help="target shape: fail builds filling less than this x the 90th-percentile fill (0: off)")
    parser.add_argument("--fill-weight", type=float, default=defaults.fill_weight,
                        help="target shape: selection score z(judge) + this x z(fill) (0: judge only)")
    parser.add_argument("--dedupe-threshold", type=float, default=defaults.dedupe_threshold)
    parser.add_argument("--diversity", type=float, default=defaults.diversity, help="lambda in selection")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 3) - 2))
    parser.add_argument("--wfc-workers", type=int, default=2, help="worker cap for --generator wfc (memory-heavy)")
    parser.add_argument("--data", type=Path, default=DATA_DIR, help="OMR download cache")
    parser.add_argument("--style-dir", type=Path, default=STYLE_DIR)
    parser.add_argument("--style-version", choices=sorted(STYLE_FILES), default=STYLE_VERSION,
                        help="M10 style statistics: v1 (M8 catalog, M10-M12 tables) or v2 (relearned with slopes)")
    parser.add_argument("--catalog", choices=sorted(CATALOGS), default="full",
                        help="parts the inventory is read with: full (corners, slopes) or m8 (before M12b)")
    parser.add_argument("--sets-file", type=Path, default=SETS_FILE)
    parser.add_argument("--out", type=Path, help="output directory (default out/alt/<input name>)")
    parser.add_argument("--fresh", action="store_true", help="discard cached candidates")
    args = parser.parse_args(argv)

    start = time.perf_counter()
    config = AltConfig(
        n=args.n, k=args.k, seed=args.seed, generator=args.generator, height=args.height, room=args.room,
        balanced=not args.no_balance, bridge=not args.no_balance and not args.no_bridge,
        connect=not args.no_connect, connect_rounds=args.connect_rounds,
        shape=args.shape, height_map=args.height_map, color_map=args.color_map, shape_height=args.shape_height,
        shape_exact=args.shape_exact, shape_columns=args.shape_columns, voxels=args.voxels, mesh_up=args.mesh_up,
        hollow=args.hollow, supports=args.supports, support_height=args.support_height, open_tops=not args.no_open_tops,
        strength=args.strength, max_clutch=args.max_clutch, wfc_time_limit_s=args.wfc_time_limit,
        min_size_quantile=args.min_size_quantile, fill_floor=args.fill_floor, fill_weight=args.fill_weight,
        dedupe_threshold=args.dedupe_threshold, diversity=args.diversity,
    )
    source = load_source(args.input, args.data, catalog=args.catalog)
    stats, style_label = learned_style(source.name, args.style_dir, args.sets_file, args.style_version)
    out = args.out or Path("out/alt") / source.name
    ignored_top = sorted(source.ignored.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    print(f"{source.name}: {source.recognized_parts} parts recognized, {source.ignored_parts} ignored"
          + (f" (most common: {', '.join(f'{p} x{n}' for p, n in ignored_top[:5])})" if ignored_top else ""))
    print(f"style: {style_label}")

    target = make_target(source, config, args.data)
    if target is not None:
        print(f"shape: {target.description}, {int(target.mask.sum())} cells, grid {target.mask.shape} (Y, Z, X)")
    context = make_context(source, stats, config, target)
    cache = out / "candidates.jsonl"
    if args.fresh and cache.exists():
        cache.unlink()
    workers = min(args.workers, args.wfc_workers) if config.generator == "wfc" else args.workers
    clock = time.perf_counter()
    seeds = range(config.seed, config.seed + config.n)
    candidates = generate_all(context, seeds, cache, cache_key(source, style_label, context), workers)
    report = run_funnel(candidates, context, stats, config, time.perf_counter() - clock)
    real = real_model_judge(source, stats, report.judge_size, config.judge_draws)
    rows = write_outputs(source, context, report, out)
    print(format_stages(report.requested, report.stages, report.check_failures))
    print(format_selected(rows))

    clutches = [c.clutch for c in candidates if not math.isnan(c.clutch)]
    stats_json = {
        "input": {"name": source.name, "recognized_parts": source.recognized_parts,
                  "ignored_parts": source.ignored_parts, "ignored_top": ignored_top,
                  "colors": [c.name for c in source.colors], "inventory_cells": inventory_cells(source.inventory)},
        "style": style_label, "config": asdict(config), "grid_YZX": list(context.grid),
        "shape": None if target is None else target.description,
        "shape_cells": None if context.mask is None else int(context.mask.sum()),
        "requested": report.requested, "stages": [asdict(s) for s in report.stages],
        "check_failures": report.check_failures, "size_floor_events": report.size_floor,
        "judge_size_events": report.judge_size,
        "real_model_judge": None if real is None else {"judge": real[0], "events": real[1]},
        "generation_cpu_s": sum(c.seconds for c in candidates),
        "physics_cpu_s": sum(c.physics_seconds for c in candidates),
        "physics_checked": len(clutches), "physics_stable": sum(math.isfinite(v) for v in clutches),
        "clusters_per_build_median": float(np.median([c.clusters for c in candidates])),
        "connected": sum(c.clusters == 1 for c in candidates),
        "wall_time_s": time.perf_counter() - start,
        "selected": rows,
    }
    (out / "stats.json").write_text(json.dumps(stats_json, indent=2), encoding="utf-8")
    print(f"wrote {len(rows)} builds, sheet.png and stats.json to {out}")
    return 0 if rows else 1
