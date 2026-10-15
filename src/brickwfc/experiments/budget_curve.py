"""M13: WFC builds finished vs time budget, with the bottom-up builder (D2) at its real time next to it.

    python -m brickwfc.experiments.budget_curve --out out/m13_budget [--sets ...] [--seeds 10]

Setup as in M9b (``experiments.inventory --catalog full --height 12``): a set's parts in the full catalog,
a grid of ``--room`` x their volume, WFC with the support and inventory constraints and bounded
backtracking (``B_inventory``), and D2 (bottom-up, any offset) on the same inventory. Default sets: the
three smallest of M9b (WFC finished 4/20 within 30 s on one of them and 0/20 on the rest).

Each WFC build runs once with the largest budget and records when it finished. Without a time limit WFC's
result depends only on the seed, and the limit only stops a run, so the builds finished within a smaller
budget b are exactly the runs that finished by b: one run per seed gives every budget's count. Wall times
depend on the machine's load, so the table states the worker counts; run it with the machine otherwise
idle. Each WFC run also records its attempts (restarts after a contradiction), backtracks and cells
collapsed at the end, so a slow build can be told apart as "stuck in backtracking" (many backtracks or
attempts) or "slow per collapse" (few collapses per second).

Writes ``runs.jsonl`` (appended per build, resumed), ``results.md`` (per set and generator: builds finished
within each budget, median finish time, the WFC counters), ``curve.csv`` (share finished vs time, per
generator, on a log time grid) and ``curve.png`` (that curve, drawn with Pillow: matplotlib is not a
dependency).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.inventory import Inventory, InventoryConstraint, inventory_coverage, inventory_from_mpd, overuse, utilization
from brickwfc.bricks.parts import CATALOG, PartSet, extract_parts, part_tileset, wfc_inventory
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.support import is_stable
from brickwfc.experiments.inventory import grid_for
from brickwfc.ldraw.fetch import fetch_set
from brickwfc.wfc import run

GENERATORS = ("WFC_B", "D2")
BUDGETS = (30.0, 120.0, 300.0, 600.0)
DEFAULT_SETS = ("10037-1", "10015-1", "10128-1")  # M9b's smallest: 78, 108, 124 parts


@dataclass(frozen=True)
class Job:
    set_number: str
    generator: str
    seed: int
    data: str
    height: int
    room: float
    max_attempts: int
    max_backtracks: int
    budget_s: float


@dataclass(frozen=True)
class BuildRecord:
    set_number: str
    generator: str
    seed: int
    finished: bool
    seconds: float  # time to finish, or to stop at the budget
    valid: bool
    utilization: float
    parts: int
    attempts: int
    contradictions: int
    backtracks: int
    cells_collapsed: int

    @property
    def collapses_per_s(self) -> float:
        return self.cells_collapsed / self.seconds if self.seconds > 0 else 0.0


def setup(set_number: str, data: Path, height: int, room: float) -> tuple[Inventory, PartSet, tuple[int, int, int]]:
    """M9b's full-catalog setup for one set."""
    text = fetch_set(set_number, data).read_text(encoding="utf-8", errors="replace")
    inventory, _, colors = inventory_from_mpd(text)
    inventory = wfc_inventory(inventory)  # M12d: only parts WFC can place soundly
    part_list = [CATALOG[name] for name in sorted({name for name, _ in inventory})]
    shape = grid_for(inventory, height, room)
    parts = part_tileset(part_list, colors, len(part_list) * (room - 1), coverage=inventory_coverage(inventory))
    return inventory, parts, shape


def check(grid: np.ndarray | None, parts: PartSet, inventory: Inventory) -> tuple[bool, float, int]:
    """(valid: whole parts, supported, within the inventory; utilization; parts placed)."""
    if grid is None:
        return False, 0.0, 0
    placed, errors = extract_parts(grid, parts)
    valid = not errors and not overuse(placed, inventory) and is_stable(placed, parts.solid[grid])
    return valid, utilization(placed, inventory), len(placed)


def run_job(job: Job) -> BuildRecord:
    inventory, parts, shape = setup(job.set_number, Path(job.data), job.height, job.room)
    if job.generator == "D2":
        start = time.perf_counter()
        grid = BottomUpBuilder(parts, any_offset=True).build(shape, np.random.default_rng(job.seed), inventory)
        seconds = time.perf_counter() - start
        return BuildRecord(job.set_number, job.generator, job.seed, True, seconds, *check(grid, parts, inventory), 1, 0, 0, 0)
    constraints = [SupportConstraint(parts), InventoryConstraint(parts, inventory)]
    result = run(parts.tileset, shape, job.seed, job.max_attempts, constraints, job.max_backtracks, job.budget_s)
    s = result.stats
    return BuildRecord(job.set_number, job.generator, job.seed, result.grid is not None, s.wall_time_s,
                       *check(result.grid, parts, inventory), s.attempts, s.contradictions, s.backtracks, s.cells_collapsed)


# Curve and tables ---------------------------------------------------------------------------------------


def finished_share(records: Sequence[BuildRecord], t: float) -> float:
    """Share of builds that finished within ``t`` seconds."""
    return sum(r.finished and r.seconds <= t for r in records) / len(records) if records else 0.0


def time_grid(t_max: float, per_decade: int = 10, t_min: float = 0.01) -> np.ndarray:
    """Log-spaced times from ``t_min`` to exactly ``t_max``, about ``per_decade`` per factor of 10."""
    return np.geomspace(t_min, t_max, math.ceil(math.log10(t_max / t_min) * per_decade) + 1)


def curve_rows(records: Sequence[BuildRecord], t_max: float) -> list[tuple[str, float, float]]:
    rows = []
    for generator in GENERATORS:
        mine = [r for r in records if r.generator == generator]
        rows += [(generator, float(t), 100 * finished_share(mine, t)) for t in time_grid(t_max)] if mine else []
    return rows


def draw_curve(rows: Sequence[tuple[str, float, float]], budgets: Sequence[float], path: Path,
               size: tuple[int, int] = (720, 420)) -> None:
    """Share finished (%) vs time (log axis), one line per generator, budgets as dashed verticals."""
    width, height = size
    left, right, top, bottom = 60, 20, 20, 50
    image = Image.new("RGB", size, (255, 255, 255))
    draw = ImageDraw.Draw(image)
    times = [t for _, t, _ in rows]
    t_min, t_max = min(times), max(times)
    x_of = lambda t: left + (width - left - right) * math.log10(t / t_min) / math.log10(t_max / t_min)  # noqa: E731
    y_of = lambda p: top + (height - top - bottom) * (1 - p / 100)  # noqa: E731
    axis, grid = (60, 60, 60), (225, 225, 225)
    for p in range(0, 101, 25):
        draw.line([(left, y_of(p)), (width - right, y_of(p))], fill=grid)
        draw.text((left - 34, y_of(p) - 6), f"{p}%", fill=axis)
    decade = 10 ** math.ceil(math.log10(t_min))
    while decade <= t_max:
        draw.line([(x_of(decade), top), (x_of(decade), height - bottom)], fill=grid)
        draw.text((x_of(decade) - 10, height - bottom + 6), f"{decade:g}s", fill=axis)
        decade *= 10
    for b in budgets:
        if t_min <= b <= t_max:
            x = x_of(b)
            for y in range(top, height - bottom, 8):
                draw.line([(x, y), (x, y + 4)], fill=(150, 150, 150))
            draw.text((x + 2, top), f"{b:g}", fill=(120, 120, 120))
    draw.line([(left, top), (left, height - bottom), (width - right, height - bottom)], fill=axis)
    colors = {"WFC_B": (200, 60, 40), "D2": (40, 90, 200)}
    for i, generator in enumerate(GENERATORS):
        points = [(x_of(t), y_of(p)) for g, t, p in rows if g == generator]
        if len(points) > 1:
            draw.line(points, fill=colors[generator], width=3)
            draw.text((width - right - 140, top + 16 + 16 * i), generator, fill=colors[generator])
    draw.text((left + 4, height - 18), "time (log scale); share of builds finished", fill=axis)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def table(records: Sequence[BuildRecord], sets: Sequence[str], budgets: Sequence[float], workers: int,
          wfc_workers: int) -> str:
    lines = [f"Load: {workers} worker processes in all, {wfc_workers} for WFC, on {os.cpu_count()} logical CPUs.", "",
             "| set | generator | builds | " + " | ".join(f"finished ≤ {b:g} s" for b in budgets)
             + " | median finish s | valid % of finished | mean attempts | mean backtracks | collapses/s |",
             "|---|---|---|" + "---|" * len(budgets) + "---|---|---|---|---|"]
    for s in sets:
        for generator in GENERATORS:
            mine = [r for r in records if r.set_number == s and r.generator == generator]
            if not mine:
                continue
            done = [r for r in mine if r.finished]
            median = f"{statistics.median(r.seconds for r in done):.2f}" if done else "—"
            valid = f"{100 * sum(r.valid for r in done) / len(done):.0f}" if done else "—"
            counts = " | ".join(f"{sum(r.finished and r.seconds <= b for r in mine)}/{len(mine)}" for b in budgets)
            wfc = generator != "D2"
            extra = (f"{statistics.fmean(r.attempts for r in mine):.1f} | {statistics.fmean(r.backtracks for r in mine):.0f} | "
                     f"{statistics.fmean(r.collapses_per_s for r in mine):.0f}") if wfc else "— | — | —"
            lines.append(f"| {s} | {generator} | {len(mine)} | {counts} | {median} | {valid} | {extra} |")
    return "\n".join(lines) + "\n"


def load_records(path: Path) -> list[BuildRecord]:
    return [BuildRecord(**json.loads(line)) for line in path.open(encoding="utf-8") if line.strip()] if path.exists() else []


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.budget_curve", description=__doc__.splitlines()[0])
    parser.add_argument("--sets", nargs="+", default=list(DEFAULT_SETS))
    parser.add_argument("--data", type=Path, default=Path("data/omr"))
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--budgets", type=float, nargs="+", default=list(BUDGETS), help="seconds; WFC runs to the largest")
    parser.add_argument("--height", type=int, default=12, help="grid height in plates (M9b's)")
    parser.add_argument("--room", type=float, default=1.5)
    parser.add_argument("--max-attempts", type=int, default=100)
    parser.add_argument("--max-backtracks", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 3) - 2), help="processes for D2 builds")
    parser.add_argument("--wfc-workers", type=int, default=2, help="processes for WFC builds (memory-heavy)")
    parser.add_argument("--out", type=Path, default=Path("out/m13_budget"))
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    runs = args.out / "runs.jsonl"
    records = load_records(runs)
    done = {(r.set_number, r.generator, r.seed) for r in records}
    budget = max(args.budgets)
    plan = {g: [Job(s, g, seed, str(args.data), args.height, args.room, args.max_attempts, args.max_backtracks, budget)
                for s in args.sets for seed in range(args.seeds) if (s, g, seed) not in done] for g in GENERATORS}
    for generator, workers in (("D2", args.workers), ("WFC_B", args.wfc_workers)):
        jobs = plan[generator]
        print(f"{generator}: {len(jobs)} builds to run with {workers} workers", flush=True)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for job, record in zip(jobs, pool.map(run_job, jobs)):  # map keeps plan order
                records.append(record)
                with runs.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(record)) + "\n")
                print(f"{job.set_number} {generator} seed {job.seed}: {'finished' if record.finished else 'stopped'} "
                      f"in {record.seconds:.1f}s", flush=True)

    rows = curve_rows(records, budget)
    (args.out / "curve.csv").write_text("generator,seconds,finished_pct\n"
                                        + "".join(f"{g},{t:.4g},{p:.2f}\n" for g, t, p in rows), encoding="utf-8")
    draw_curve(rows, args.budgets, args.out / "curve.png")
    text = table(records, args.sets, args.budgets, args.workers, args.wfc_workers)
    (args.out / "results.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
