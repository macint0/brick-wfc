"""M9 experiment: building from a real set's parts.

    python -m brickwfc.experiments.inventory --seeds 30 --out out/m9

For each set, the inventory is the set's 1x1/1x2/2x2/2x4 plates (by color). Builds go in a grid of
height ``--height`` plates whose volume is ``--room`` x the inventory's cell volume, so the inventory,
not the grid, limits the build. The empty tile's weight is set so the expected solid share of the grid
is 1/room (i.e. about the inventory's volume). Conditions (same seeds, same weights):

  A_filter     WFC + support constraint; inventory checked only afterwards
  B_inventory  WFC + support + inventory constraints in propagation, with backtracking
  D_bottom_up  random bottom-up placement that skips used-up parts (no WFC)
  D2_bottom_up_any_offset  the same, but a part may cover the visited cell with any of its cells (M11)

``--catalog plates`` (default, M9) uses the set's four plate types only; ``--catalog full`` (M8) uses
every part of the set that is in ``parts.CATALOG`` (plates, bricks, tiles and lookalikes).
``--time-limit`` caps each WFC build (a build that hits it counts as "timed out"), and ``--wfc-max-mb``
skips WFC on sets whose backtracking history (``wfc.BACKTRACK_DEPTH`` domain copies) would need more
memory than that; such sets get a "not run (memory)" row instead of being left out.

A build is **valid** if it is within the inventory and satisfies the support rule; physics (on a
table) is reported separately. Results are saved after each (set, condition) and resumed.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.inventory import (
    Inventory,
    InventoryConstraint,
    inventory_cells,
    inventory_coverage,
    PLATE_FILES,
    inventory_from_mpd,
    overuse,
    utilization,
)
from brickwfc.bricks.parts import CATALOG, PLATES, PartSet, extract_parts, part_tileset
from brickwfc.bricks.physics import required_clutch
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.support import is_stable
from brickwfc.ldraw.fetch import fetch_set
from brickwfc.experiments.coverage import SetCoverage, set_coverage
from brickwfc.wfc import BACKTRACK_DEPTH, run

CONDITIONS = ("A_filter", "B_inventory", "D_bottom_up", "D2_bottom_up_any_offset")
# Sets with >= 20 of the generator's plates, excluding the three largest (10018, 10129, 10143), where
# one WFC build takes 20 s to minutes.
DEFAULT_SETS = "10015-1 10019-1 10020-1 10037-1 10124-1 10128-1 10133-1 10134-1 10159-1 10170-1".split()


@dataclass(frozen=True)
class RunRecord:
    set_number: str
    condition: str
    seed: int
    success: bool
    within_inventory: bool
    stable: bool
    required_clutch: float
    utilization: float
    parts: int
    attempts: int
    backtracks: int
    wall_time_s: float
    timed_out: bool = False


def grid_for(inventory: Inventory, height: int, room: float) -> tuple[int, int, int]:
    """(Y, Z, X): ``height`` plates tall, square footprint, volume about ``room`` x the inventory's cells."""
    side = max(2, math.ceil(math.sqrt(room * inventory_cells(inventory) / height)))
    return (height, side, side)


Build = Callable[[int], tuple[np.ndarray | None, int, int, float, bool]]  # seed -> (grid, attempts, backtracks, seconds, timed out)


def make_generator(
    condition: str, parts: PartSet, inventory: Inventory, shape: tuple[int, int, int], max_attempts: int, max_backtracks: int,
    time_limit_s: float | None = None,
) -> Build:
    if condition.startswith("D"):
        builder = BottomUpBuilder(parts, any_offset=condition == "D2_bottom_up_any_offset")

        def build(seed: int) -> tuple[np.ndarray | None, int, int, float, bool]:
            start = time.perf_counter()
            grid = builder.build(shape, np.random.default_rng(seed), inventory)
            return grid, 1, 0, time.perf_counter() - start, False

        return build

    constraints = [SupportConstraint(parts)]
    backtracks = 0
    if condition == "B_inventory":
        constraints.append(InventoryConstraint(parts, inventory))
        backtracks = max_backtracks

    def build(seed: int) -> tuple[np.ndarray | None, int, int, float, bool]:
        result = run(parts.tileset, shape, seed, max_attempts, constraints, backtracks, time_limit_s)
        stats = result.stats
        return result.grid, stats.attempts, stats.backtracks, stats.wall_time_s, stats.timed_out

    return build


def run_one(set_number: str, condition: str, seed: int, parts: PartSet, inventory: Inventory, build: Build) -> RunRecord:
    grid, attempts, backtracks, seconds, timed_out = build(seed)
    if grid is None:
        return RunRecord(set_number, condition, seed, False, False, False, math.inf, 0.0, 0, attempts, backtracks, seconds,
                         timed_out)
    placed, _ = extract_parts(grid, parts)
    return RunRecord(
        set_number, condition, seed, True, not overuse(placed, inventory), is_stable(placed, parts.solid[grid]),
        required_clutch(placed, grid.shape), utilization(placed, inventory), len(placed), attempts, backtracks, seconds,
    )


def set_info(inventory: Inventory, shape: tuple[int, int, int], coverage: SetCoverage, time_limit_s: float | None) -> dict:
    """Columns that describe the set and the setup rather than a condition's results."""
    used = sum(inventory.values())
    return {
        "inventory_parts": used,
        "set_parts": coverage.parts,
        "recognized_pct": 100 * used / coverage.parts if coverage.parts else 0.0,
        "left_out": coverage.parts - used,
        "grid_WxDxH": f"{shape[2]}x{shape[1]}x{shape[0]}",
        "time_limit_s": time_limit_s,
    }


def not_run(set_number: str, condition: str, seeds: int, info: dict, reason: str) -> dict:
    return {"set": set_number, "condition": condition, "seeds": seeds, **info, "status": reason}


def summarize(records: list[RunRecord], info: dict) -> dict:
    n = len(records)
    built = [r for r in records if r.success]
    valid = sum(r.within_inventory and r.stable for r in records)
    total_time = sum(r.wall_time_s for r in records)
    return {
        "set": records[0].set_number,
        "condition": records[0].condition,
        "seeds": n,
        **info,
        "status": "ok",
        "finished": len(built),
        "timed_out": sum(r.timed_out for r in records),
        "time_per_finished_s": statistics.mean(r.wall_time_s for r in built) if built else math.nan,
        "success_pct": 100 * len(built) / n,
        "within_inventory_pct": 100 * sum(r.within_inventory for r in records) / n,
        "valid_pct": 100 * valid / n,
        "physics_any_clutch_pct": 100 * sum(math.isfinite(r.required_clutch) for r in records) / n,
        "physics_clutch10_pct": 100 * sum(r.required_clutch <= 10 for r in records) / n,
        "utilization_pct": 100 * statistics.mean(r.utilization for r in built) if built else 0.0,
        "attempts_per_run": statistics.mean(r.attempts for r in records),
        "backtracks_per_run": statistics.mean(r.backtracks for r in records),
        "time_per_run_s": total_time / n,
        "time_per_valid_s": total_time / valid if valid else math.inf,
    }


SETUP_COLUMNS = [
    ("set", "set", "{}"), ("condition", "condition", "{}"), ("parts", "inventory_parts", "{}"),
    ("grid", "grid_WxDxH", "{}"), ("seeds", "seeds", "{}"),
]
FULL_CATALOG_COLUMNS = [  # M9b: how much of the set is used, and WFC's time cap
    ("set parts", "set_parts", "{}"), ("recognized %", "recognized_pct", "{:.0f}"), ("left out", "left_out", "{}"),
    ("cap (s)", "time_limit_s", "{}"), ("finished", "finished", "{}"), ("timed out", "timed_out", "{}"),
    ("time/finished (s)", "time_per_finished_s", "{:.2f}"),
]
COLUMNS = SETUP_COLUMNS + [
    ("within inventory %", "within_inventory_pct", "{:.1f}"),
    ("valid %", "valid_pct", "{:.1f}"), ("phys. any clutch %", "physics_any_clutch_pct", "{:.1f}"),
    ("phys. clutch <=10 %", "physics_clutch10_pct", "{:.1f}"), ("utilization %", "utilization_pct", "{:.1f}"),
    ("attempts/run", "attempts_per_run", "{:.2f}"), ("backtracks/run", "backtracks_per_run", "{:.1f}"),
    ("time/run (s)", "time_per_run_s", "{:.3f}"),
    ("time/valid (s)", "time_per_valid_s", "{:.3f}"),
]


def markdown_table(summaries: list[dict], full_catalog: bool = False) -> str:
    """Per-set rows; rows that were not run show their reason under "finished" and dashes elsewhere."""
    split = len(SETUP_COLUMNS)
    columns = COLUMNS[:split] + (FULL_CATALOG_COLUMNS if full_catalog else []) + COLUMNS[split:]
    setup = {key for _, key, _ in SETUP_COLUMNS + FULL_CATALOG_COLUMNS[:4]}
    lines = ["| " + " | ".join(title for title, _, _ in columns) + " |", "|" + "---|" * len(columns)]
    for s in summaries:
        status = s.get("status", "ok")
        cells = []
        for _, key, fmt in columns:
            value = s.get(key)
            if status != "ok" and key not in setup:
                cells.append(status if key == "finished" else "—")
            elif value is None or (isinstance(value, float) and math.isnan(value)):
                cells.append("—")
            else:
                cells.append(fmt.format(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def overall(summaries: list[dict]) -> str:
    """Per-condition means over sets (each set weighted equally)."""
    lines = ["| condition | sets | within inventory % | valid % | phys. any clutch % | utilization % | attempts/run | time/run (s) |",
             "|---|---|---|---|---|---|---|---|"]
    for condition in CONDITIONS:
        rows = [s for s in summaries if s["condition"] == condition and s.get("status", "ok") == "ok"]
        if not rows:
            continue
        def mean(key: str, rows: list[dict] = rows) -> float:
            return statistics.mean(r[key] for r in rows)

        lines.append(
            f"| {condition} | {len(rows)} | {mean('within_inventory_pct'):.1f} | {mean('valid_pct'):.1f} "
            f"| {mean('physics_any_clutch_pct'):.1f} | {mean('utilization_pct'):.1f} | {mean('attempts_per_run'):.2f} "
            f"| {mean('time_per_run_s'):.3f} |"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.inventory", description=__doc__.splitlines()[0])
    parser.add_argument("--sets", nargs="+", default=list(DEFAULT_SETS))
    parser.add_argument("--data", type=Path, default=Path("data/omr"))
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--height", type=int, default=6, help="grid height in plates")
    parser.add_argument("--room", type=float, default=1.5, help="grid volume / inventory volume")
    parser.add_argument("--conditions", nargs="+", default=list(CONDITIONS[:3]), choices=CONDITIONS)
    parser.add_argument("--catalog", choices=["plates", "full"], default="plates", help="which of the set's parts to use")
    parser.add_argument("--time-limit", type=float, default=None, help="seconds per WFC build (default: none)")
    parser.add_argument("--wfc-max-mb", type=float, default=None,
                        help="skip WFC where the backtracking history would exceed this many MB (default: never skip)")
    parser.add_argument("--max-attempts", type=int, default=100)
    parser.add_argument("--max-backtracks", type=int, default=1000, help="per WFC attempt (B_inventory only)")
    parser.add_argument("--out", type=Path, default=Path("out/m9"))
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    summary_path, runs_path = args.out / "summary.json", args.out / "runs.jsonl"
    summaries: list[dict] = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else []
    done = {(s["set"], s["condition"], s["seeds"]) for s in summaries}
    for set_number in args.sets:
        text = fetch_set(set_number, args.data).read_text(encoding="utf-8", errors="replace")
        if args.catalog == "plates":
            inventory, unsupported, colors = inventory_from_mpd(text, PLATE_FILES)
            part_list = list(PLATES.values())
        else:
            inventory, unsupported, colors = inventory_from_mpd(text)
            part_list = [CATALOG[name] for name in sorted({name for name, _ in inventory})]
        shape = grid_for(inventory, args.height, args.room)
        # Solid tiles' weights sum to len(part_list); this empty weight makes the solid prior 1/room.
        empty_weight = len(part_list) * (args.room - 1)
        parts = part_tileset(part_list, colors, empty_weight, coverage=inventory_coverage(inventory))
        coverage = set_coverage(set_number, text)
        # Backtracking keeps BACKTRACK_DEPTH copies of the (cells x tiles) bool domain.
        history_mb = BACKTRACK_DEPTH * math.prod(shape) * len(parts.infos) / 1e6
        for condition in args.conditions:
            if (set_number, condition, args.seeds) in done:
                print(f"{set_number} {condition}: already done, skipping", flush=True)
                continue
            wfc = condition in ("A_filter", "B_inventory")
            time_limit = args.time_limit if wfc else None
            info = set_info(inventory, shape, coverage, time_limit)
            if condition == "B_inventory" and args.wfc_max_mb is not None and history_mb > args.wfc_max_mb:
                summaries.append(not_run(set_number, condition, args.seeds, info, f"not run (memory: {history_mb:.0f} MB)"))
                summary_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
                print(f"{set_number} {condition}: not run, backtracking would need {history_mb:.0f} MB", flush=True)
                continue
            build = make_generator(condition, parts, inventory, shape, args.max_attempts, args.max_backtracks, time_limit)
            start = time.perf_counter()
            batch = [run_one(set_number, condition, seed, parts, inventory, build) for seed in range(args.seeds)]
            summaries.append(summarize(batch, info))
            with runs_path.open("a", encoding="utf-8") as runs_file:
                runs_file.writelines(json.dumps(asdict(r)) + "\n" for r in batch)
            summary_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
            s = summaries[-1]
            print(f"{set_number} {condition}: valid {s['valid_pct']:.1f}%, within inventory {s['within_inventory_pct']:.1f}%, "
                  f"utilization {s['utilization_pct']:.1f}%, finished {s['finished']}/{s['seeds']} "
                  f"in {time.perf_counter() - start:.1f}s", flush=True)

    order = {name: i for i, name in enumerate(args.sets)}
    summaries.sort(key=lambda s: (order.get(s["set"], len(order)), s["set"], CONDITIONS.index(s["condition"])))
    text = "## Per set\n\n" + markdown_table(summaries, full_catalog=args.catalog == "full") + "\n\n## Mean over sets\n\n" + overall(summaries) + "\n"
    print(text)
    (args.out / "results.md").write_text(text, encoding="utf-8")
    print(f"wrote {args.out}/results.md, summary.json, runs.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
