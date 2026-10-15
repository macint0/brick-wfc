"""M10: does learned style bring generated builds closer to real sets? WFC vs bottom-up (D2).

    python -m brickwfc.experiments.style --out out/m10

Sets: the building sets chosen by ``experiments.sets`` (``results/sets_selection.json``), voxelized with
the full catalog. 4-fold cross-validation: each set is held out once, and style statistics
(``bricks.style``) are learned from the other sets (21 per fold for the 28 selected sets, so >= 20).

For a held-out set X, the input is the parts of X's real model that lie on the stud grid (so the real
model is itself a valid build from that input), and X's real model is the reference. Each condition
runs with three styles (an ablation):

  uniform      every (part, color) of X equally likely per part placed; no contact bias
  frequencies  part-type and color frequencies learned from the training sets (restricted to X's
               parts and colors); no contact bias
  contacts     learned frequencies + the learned contact bias (``StyleBias``)

Conditions:

  D2_inventory  bottom-up builder (any offset) using exactly X's parts: the real task
  D2_free       the same builder without part counts (same part/color mix, counts not enforced)
  WFC_free      WFC + support constraint, same weights, no counts; only for sets with at most
                ``--wfc-max-parts`` parts, with a time cap per build (WFC + inventory times out at this
                scale, see results/m9b_inventory_catalog.md)

Metrics per build: the judge (``style.judge``: minus the divergence from the fold's learned
statistics; because the divergence shrinks with size, each build is also judged *size-matched*: build
and real held-out model both subsampled to the smaller one's number of contact events, the real model's
score being the ceiling), the mean log-likelihood per contact
(reported only: it is gamed by repetitive builds), the distance to X's own statistics (held-out
statistics), validity (whole parts, supported), part overuse, inventory utilization, time. The
judge sanity check scores degenerate builds against the real models. Results are saved after each
(set, condition, style) and resumed.

Builds run in parallel, one job per (set, condition, style, seed): ``--workers`` processes in all
(default: CPU count - 2), of which ``--wfc-workers`` (default 2) run WFC jobs, which need more
memory; WFC is skipped where its backtracking history would exceed ``--wfc-max-mb``. Every job has
its own seed and results are collected in a fixed order, so the output does not depend on the
number of workers (apart from wall times).

Learning only (M12b): ``--learn-only VERSION`` skips the builds and writes each fold's statistics to
``--stats-dir`` as ``style_fold{i}_VERSION.json``, with a ``"catalog"`` field naming the catalog the sets
were voxelized with (``--catalog``: ``full``, today's ``parts.CATALOG``, or ``m8``, the M8 catalog the
M10 run used). The M10 files (``style_fold{i}.json``) are left as they are, so M10/M12 tables reproduce:

    python -m brickwfc.experiments.style --learn-only v2 --stats-dir results/m10_style_stats
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import time
from concurrent.futures import Executor, Future, ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.inventory import Inventory, overuse, usage, utilization
from brickwfc.bricks.parts import BY_FILE, CATALOG, M8_FILES, M12B_FILES, PartSet, PlacedPart, Shape, extract_parts
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.style import (
    Events,
    StyleBias,
    StyleStats,
    distance,
    events,
    judge,
    matched_divergence,
    merged,
    size_matched,
    styled_tileset,
)
from brickwfc.bricks.support import is_stable
from scipy.stats import spearmanr
from brickwfc.bricks.voxelize import voxelize
from brickwfc.experiments.inventory import grid_for
from brickwfc.ldraw.fetch import fetch_set
from brickwfc.ldraw.mpd import flatten
from brickwfc.wfc import BACKTRACK_DEPTH, run

CONDITIONS = ("D2_inventory", "D2_free", "WFC_free")
STYLES = ("uniform", "frequencies", "contacts")


@dataclass(frozen=True)
class Record:
    set_number: str
    fold: int
    condition: str
    style: str
    seed: int
    success: bool
    timed_out: bool
    valid: bool  # whole parts, every part supported
    parts: int
    overuse: int  # parts used beyond X's counts (0 for D2_inventory)
    utilization: float
    judge: float
    matched_judge: float  # the build's judge at the common size (see ``style.size_matched``)
    matched_ceiling: float  # the real model's judge at the common size
    matched_size: int  # judge terms
    likelihood: float
    judge_vertical: float
    judge_horizontal: float
    judge_color: float
    judge_support: float
    distance: float
    distance_vertical: float
    distance_horizontal: float
    distance_support: float
    wall_time_s: float


def folds(sets: Sequence[str], k: int, seed: int) -> list[list[str]]:
    order = [sets[i] for i in np.random.default_rng(seed).permutation(len(sets))]
    return [order[i::k] for i in range(k)]


def setup(real: list[PlacedPart], empty_weight_per_part: float, stats: StyleStats | None = None) -> tuple[Inventory, PartSet]:
    """X's inventory (its real model's parts) and ``style.styled_tileset`` over its (part, color) pairs."""
    inventory = dict(usage(real))
    colors = sorted({p.color for p in real}, key=lambda c: c.ldraw)
    return inventory, styled_tileset(inventory, colors, empty_weight_per_part, stats)


def evaluate(set_number: str, fold: int, condition: str, style: str, seed: int, grid: np.ndarray | None, timed_out: bool,
             seconds: float, parts: PartSet, inventory: Inventory, stats: StyleStats, real_stats: StyleStats,
             real_events: Events) -> Record:
    if grid is None:
        nan = math.nan
        return Record(set_number, fold, condition, style, seed, False, timed_out, False, 0, 0, 0.0,
                      nan, nan, nan, 0, nan, nan, nan, nan, nan, nan, nan, nan, nan, seconds)
    placed, errors = extract_parts(grid, parts)
    score = judge(placed, stats)
    matched, ceiling, size = size_matched(events(placed), real_events, stats, np.random.default_rng([seed, score.events]))
    gap = distance(StyleStats().add(placed), real_stats)
    return Record(
        set_number, fold, condition, style, seed, True, False, not errors and is_stable(placed, parts.solid[grid]),
        len(placed), sum(overuse(placed, inventory).values()), utilization(placed, inventory),
        score.total, matched, ceiling, size, score.likelihood, score.vertical, score.horizontal, score.color, score.support,
        gap["mean"], gap["vertical_js"], gap["horizontal_js"], gap["support_js"], seconds,
    )


def summarize(records: list[Record], real_judge: float) -> dict:
    built = [r for r in records if r.success]

    def mean(key: str) -> float:
        return statistics.mean(getattr(r, key) for r in built) if built else math.nan

    return {
        "set": records[0].set_number, "fold": records[0].fold, "condition": records[0].condition,
        "style": records[0].style, "seeds": len(records), "status": "ok", "finished": len(built),
        "timed_out": sum(r.timed_out for r in records), "valid_pct": 100 * sum(r.valid for r in records) / len(records),
        "parts": mean("parts"), "overuse": mean("overuse"), "utilization_pct": 100 * mean("utilization"),
        "judge": mean("judge"), "real_judge": real_judge, "judge_gap": real_judge - mean("judge"),
        "matched_judge": mean("matched_judge"), "matched_ceiling": mean("matched_ceiling"),
        "matched_gap": mean("matched_ceiling") - mean("matched_judge"), "matched_size": mean("matched_size"),
        "likelihood": mean("likelihood"),
        "distance": mean("distance"), "distance_vertical": mean("distance_vertical"),
        "distance_horizontal": mean("distance_horizontal"), "distance_support": mean("distance_support"),
        "time_per_build_s": statistics.mean(r.wall_time_s for r in records),
    }


def condition_table(summaries: list[dict]) -> str:
    """Means over the sets on which a condition ran with every style (paired). "Closer than uniform"
    counts sets where that style's builds are closer to the real model's own statistics than uniform's.
    Judges: full build vs full real model, and size-matched (both subsampled to the smaller one's number
    of contact events); "gap" is the size-matched real judge (the ceiling) minus the build's."""
    lines = ["| condition | style | sets | valid % | judge | real judge | judge, size-matched | real judge, size-matched "
             "| gap to real (size-matched) | likelihood | distance to real | closer than uniform (sets) | time/build (s) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    ok = [s for s in summaries if s["status"] == "ok" and s["finished"]]
    for condition in CONDITIONS:
        rows = {style: {s["set"]: s for s in ok if s["condition"] == condition and s["style"] == style} for style in STYLES}
        paired = sorted(set.intersection(*(set(r) for r in rows.values())))
        if not paired:
            continue
        for style in STYLES:
            rs = [rows[style][s] for s in paired]
            m = lambda key: statistics.mean(r[key] for r in rs)  # noqa: E731
            closer = ""
            if style != "uniform":
                closer = f"{sum(rows[style][s]['distance'] < rows['uniform'][s]['distance'] for s in paired)}/{len(paired)}"
            lines.append(f"| {condition} | {style} | {len(paired)} | {m('valid_pct'):.1f} | {m('judge'):.3f} | "
                         f"{m('real_judge'):.3f} | {m('matched_judge'):.3f} | {m('matched_ceiling'):.3f} | "
                         f"{m('matched_gap'):.3f} | "
                         f"{m('likelihood'):.3f} | {m('distance'):.3f} | "
                         f"{closer} | {m('time_per_build_s'):.2f} |")
    return "\n".join(lines)


def degenerate_builds() -> dict[str, list[PlacedPart]]:
    """Repetitive builds that a per-contact likelihood would rank above real sets."""
    red, blue = colors_by_name(["red", "blue"])

    def p(name: str, layer: int, x: int = 0, z: int = 0, color=red) -> PlacedPart:
        return PlacedPart(Shape(CATALOG[name], False), color, layer, x, z)

    return {
        "tower of 20 2x4 bricks": [p("brick2x4", 3 * i) for i in range(20)],
        "tower of 20 1x2 bricks": [p("brick1x2", 3 * i) for i in range(20)],
        "sheet of 25 2x4 plates": [p("plate2x4", 0, 4 * i, 2 * j) for i in range(5) for j in range(5)],
        "6 stacked sheets of 1x2 plates": [p("plate1x2", y, 2 * i, j) for y in range(6) for i in range(4) for j in range(4)],
        "running-bond wall of 1x2 bricks": [p("brick1x2", 3 * y, 2 * i + y % 2) for y in range(6) for i in range(5)],
        "same wall in two colors": [p("brick1x2", 3 * y, 2 * i + y % 2, 0, red if (i + y) % 3 else blue)
                                    for y in range(6) for i in range(5)],
    }


def size_table(per_model: dict[str, StyleStats], real_events: dict[str, Events], sets: Sequence[str]) -> str:
    """Each real model's judge (learned from all other sets) against its number of contact events."""
    rows = []
    for s in sets:
        others = merged([per_model[o] for o in sets if o != s])
        rows.append((real_events[s].count, -distance(per_model[s], others)["mean"], s))
    rows.sort()
    rho = spearmanr([r[0] for r in rows], [r[1] for r in rows]).statistic
    lines = [f"Spearman correlation between size (judge terms) and judge over the {len(rows)} real models: "
             f"**{rho:.2f}**.", "", "| set | judge terms | judge |", "|---|---|---|"]
    lines += [f"| {s} | {n} | {j:.3f} |" for n, j, s in rows]
    return "\n".join(lines)


def sanity_table(per_model: dict[str, StyleStats], real_events: dict[str, Events], sets: Sequence[str], draws: int = 5) -> str:
    """Degenerate builds (judged against all sets) vs real models (each judged against all other sets),
    with the real models subsampled to the degenerate build's size."""
    everything = merged([per_model[s] for s in sets])
    loo = {s: merged([per_model[o] for o in sets if o != s]) for s in sets}
    lines = ["| build | judge terms | judge | real models at this size: min / median / max | likelihood |",
             "|---|---|---|---|---|"]
    for name, build in degenerate_builds().items():
        score = judge(build, everything)
        real = sorted(-matched_divergence(real_events[s], score.events, loo[s], np.random.default_rng(i), draws)
                      for i, s in enumerate(sets))
        lines.append(f"| {name} | {score.events} | {score.total:.3f} | {real[0]:.3f} / {real[len(real) // 2]:.3f} / "
                     f"{real[-1]:.3f} | {score.likelihood:.3f} |")
    return "\n".join(lines)


def set_table(summaries: list[dict]) -> str:
    lines = ["| set | fold | condition | style | finished | valid % | parts | overuse | utilization % | judge | "
             "real judge | distance | time/build (s) |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in summaries:
        if s["status"] != "ok":
            lines.append(f"| {s['set']} | {s['fold']} | {s['condition']} | {s['style']} | {s['status']} |"
                         + " — |" * 8)
            continue
        f = lambda v, fmt: "—" if v is None or (isinstance(v, float) and math.isnan(v)) else fmt.format(v)  # noqa: E731
        lines.append(f"| {s['set']} | {s['fold']} | {s['condition']} | {s['style']} | {s['finished']}/{s['seeds']} | "
                     f"{s['valid_pct']:.0f} | {f(s['parts'], '{:.0f}')} | {f(s['overuse'], '{:.0f}')} | "
                     f"{f(s['utilization_pct'], '{:.0f}')} | {f(s['judge'], '{:.3f}')} | {s['real_judge']:.3f} | "
                     f"{f(s['distance'], '{:.3f}')} | {s['time_per_build_s']:.2f} |")
    return "\n".join(lines)


@dataclass(frozen=True)
class Job:
    """One build: everything a worker process needs (picklable, no shared state)."""

    set_number: str
    fold: int
    condition: str
    style: str
    seed: int
    real: tuple[PlacedPart, ...]
    stats: StyleStats  # learned from the fold's training sets
    real_stats: StyleStats
    real_events: Events
    height: int
    room: float
    strength: float
    time_limit_s: float


def run_job(job: Job) -> Record:
    real = list(job.real)
    if job.condition == "WFC_free":  # M12d: WFC builds from the parts it can place soundly (parts.Part.wfc)
        real = [p for p in real if p.shape.part.wfc]
    inventory, parts = setup(real, job.room - 1, job.stats if job.style != "uniform" else None)
    shape = grid_for(inventory, job.height, job.room)
    bias = StyleBias(job.stats, parts, job.strength) if job.style == "contacts" else None
    start = time.perf_counter()
    timed_out = False
    if job.condition == "WFC_free":
        result = run(parts.tileset, shape, job.seed, 20, [SupportConstraint(parts)], 1000, job.time_limit_s,
                     bias.for_tiles if bias else None)
        grid, timed_out = result.grid, result.stats.timed_out
    else:
        builder = BottomUpBuilder(parts, any_offset=True, style=bias)
        counts = inventory if job.condition == "D2_inventory" else None
        grid = builder.build(shape, np.random.default_rng(job.seed), counts)
    return evaluate(job.set_number, job.fold, job.condition, job.style, job.seed, grid, timed_out,
                    time.perf_counter() - start, parts, inventory, job.stats, job.real_stats, job.real_events)


class InlineExecutor(Executor):
    """Runs jobs in this process when submitted (``--workers 1``; also easy to debug)."""

    def submit(self, fn, /, *args, **kwargs) -> Future:  # type: ignore[override]
        future: Future = Future()
        future.set_result(fn(*args, **kwargs))
        return future


def wfc_history_mb(real: list[PlacedPart], height: int, room: float) -> float:
    """Memory of WFC's backtracking history (BACKTRACK_DEPTH copies of the cells x tiles domain)."""
    inventory, parts = setup(real, room - 1)
    return BACKTRACK_DEPTH * math.prod(grid_for(inventory, height, room)) * len(parts.infos) / 1e6


CATALOG_NAMES = {"full": "m12d", "m12b": "m12b", "m8": "m8"}  # catalog version written into learned statistics


def learn_only(sets: Sequence[str], per_model: dict[str, StyleStats], k: int, fold_seed: int, version: str,
               catalog: str, out: Path) -> int:
    """Write each fold's statistics (learned without its held-out sets) as ``style_fold{i}_{version}.json``."""
    out.mkdir(parents=True, exist_ok=True)
    for fold, held_out in enumerate(folds(sets, k, fold_seed)):
        stats = merged([per_model[s] for s in sets if s not in held_out])
        path = out / f"style_fold{fold}_{version}.json"
        path.write_text(json.dumps({**stats.to_json(), "catalog": CATALOG_NAMES[catalog]}), encoding="utf-8")
        print(f"wrote {path}: {len(sets) - len(held_out)} sets, {int(stats.parts.sum())} parts")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.style", description=__doc__.splitlines()[0])
    parser.add_argument("--sets-file", type=Path, default=Path("results/sets_selection.json"))
    parser.add_argument("--data", type=Path, default=Path("data/omr"))
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--fold-seed", type=int, default=0)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--wfc-seeds", type=int, default=3)
    parser.add_argument("--height", type=int, default=12, help="grid height in plates")
    parser.add_argument("--room", type=float, default=1.5, help="grid volume / inventory volume")
    parser.add_argument("--strength", type=float, default=1.0, help="exponent on the learned style weights")
    parser.add_argument("--conditions", nargs="+", default=list(CONDITIONS), choices=CONDITIONS)
    parser.add_argument("--wfc-max-parts", type=int, default=250)
    parser.add_argument("--wfc-max-mb", type=float, default=1000.0, help="skip WFC where backtracking needs more")
    parser.add_argument("--time-limit", type=float, default=120.0, help="seconds per WFC build")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 3) - 2), help="processes in all")
    parser.add_argument("--wfc-workers", type=int, default=2, help="processes for WFC jobs (memory-heavy)")
    parser.add_argument("--out", type=Path, default=Path("out/m10"))
    parser.add_argument("--catalog", choices=("full", "m12b", "m8"), default="full", help="parts the sets are voxelized with")
    parser.add_argument("--learn-only", metavar="VERSION", help="only write each fold's statistics, tagged VERSION")
    parser.add_argument("--stats-dir", type=Path, default=Path("results/m10_style_stats"), help="for --learn-only")
    args = parser.parse_args(argv)

    sets = json.loads(args.sets_file.read_text(encoding="utf-8"))["selected"]
    known = {"full": BY_FILE, "m12b": M12B_FILES, "m8": M8_FILES}[args.catalog]
    models = {s: voxelize(flatten(fetch_set(s, args.data).read_text(encoding="utf-8", errors="replace")), known)[0]
              for s in sets}
    per_model = {s: StyleStats().add(m) for s, m in models.items()}
    if args.learn_only:
        return learn_only(sets, per_model, args.folds, args.fold_seed, args.learn_only, args.catalog, args.stats_dir)
    real_events = {s: events(m) for s, m in models.items()}
    args.out.mkdir(parents=True, exist_ok=True)
    summary_path, runs_path = args.out / "summary.json", args.out / "runs.jsonl"
    summaries: list[dict] = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else []
    done = {(s["set"], s["condition"], s["style"]) for s in summaries}

    # Plan every batch in a fixed order; a batch is (set, condition, style) with its seeds, or a "not run" row.
    plan: list[tuple[dict, list[Job]]] = []
    for fold, held_out in enumerate(folds(sets, args.folds, args.fold_seed)):
        stats = merged([per_model[s] for s in sets if s not in held_out])
        stats.save(args.out / f"style_fold{fold}.json")
        for set_number in held_out:
            real = models[set_number]
            real_judge = judge(real, stats).total
            for condition in args.conditions:
                skip = ""
                if condition == "WFC_free" and len(real) > args.wfc_max_parts:
                    skip = f"not run ({len(real)} parts)"
                elif condition == "WFC_free" and wfc_history_mb(real, args.height, args.room) > args.wfc_max_mb:
                    skip = f"not run (memory: {wfc_history_mb(real, args.height, args.room):.0f} MB)"
                seeds = args.wfc_seeds if condition == "WFC_free" else args.seeds
                for style in STYLES:
                    if (set_number, condition, style) in done:
                        continue
                    head = {"set": set_number, "fold": fold, "condition": condition, "style": style, "seeds": seeds,
                            "real_judge": real_judge, "status": skip or "ok"}
                    jobs = [] if skip else [
                        Job(set_number, fold, condition, style, seed, tuple(real), stats, per_model[set_number],
                            real_events[set_number], args.height, args.room, args.strength, args.time_limit)
                        for seed in range(seeds)
                    ]
                    plan.append((head, jobs))

    wfc_workers = min(args.wfc_workers, args.workers)
    other_workers = max(1, args.workers - wfc_workers)
    parallel = args.workers > 1
    with (ProcessPoolExecutor(other_workers) if parallel else InlineExecutor()) as pool, \
         (ProcessPoolExecutor(wfc_workers) if parallel and wfc_workers else InlineExecutor()) as wfc_pool:
        # With worker processes, submit everything now and collect batch by batch in plan order.
        submitted = [] if not parallel else [
            [(wfc_pool if job.condition == "WFC_free" else pool).submit(run_job, job) for job in jobs]
            for _, jobs in plan
        ]
        for index, (head, jobs) in enumerate(plan):
            if head["status"] != "ok":
                summaries.append({**head, "finished": 0})
            else:
                futures = submitted[index] if parallel else [pool.submit(run_job, job) for job in jobs]
                batch = [future.result() for future in futures]
                summaries.append(summarize(batch, head["real_judge"]))
                with runs_path.open("a", encoding="utf-8") as runs_file:
                    runs_file.writelines(json.dumps(asdict(r)) + "\n" for r in batch)
                s = summaries[-1]
                print(f"{head['set']} {head['condition']} {head['style']}: judge {s['judge']:.3f} "
                      f"(real {head['real_judge']:.3f}); size-matched {s['matched_judge']:.3f} vs real "
                      f"{s['matched_ceiling']:.3f}, "
                      f"distance {s['distance']:.3f}, finished {s['finished']}/{s['seeds']}, "
                      f"{s['time_per_build_s']:.1f}s/build", flush=True)
            summary_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")

    order = {s: i for i, s in enumerate(sets)}
    summaries.sort(key=lambda s: (order.get(s["set"], len(order)), CONDITIONS.index(s["condition"]), STYLES.index(s["style"])))
    text = ("## By condition (paired over sets)\n\n" + condition_table(summaries)
            + "\n\n## Judge sanity check (size-matched)\n\n" + sanity_table(per_model, real_events, sets)
            + "\n\n## Judge vs size of real models\n\n" + size_table(per_model, real_events, sets)
            + "\n\n## Per set\n\n" + set_table(summaries) + "\n")
    (args.out / "results.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
