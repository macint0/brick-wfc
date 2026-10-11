"""M12c overnight queue: the steps ``scripts/overnight_m12c.sh`` runs, as command lines, and their estimated minutes.

    python -m brickwfc.experiments.overnight steps 0.8 1.0      # NAME<TAB>command, one step per line, in order
    python -m brickwfc.experiments.overnight estimate 0.8 1.0   # estimated minutes per step

The slacks are the bench's, in the order to run them (Session B's size report decides them). In order:

1. ``hollow``: hollow1 and hollow1_80 on the 9 sweep pairs (``out/m12b_complete``), then their sweep report against
   creserve / creserve80 (``sweep_hollow``).
2. ``chair``: the reconnected 6378-1 chair (``examples/m12c_chair_6378.json``) under cregrow at 1.0 / 0.8 / 0.7 / 0.6
   (cregrow90 too if that arm exists) and the usable controls at 1.0-0.6, in ``out/m12c_reconnected`` (its targets
   changed, so the cached runs in ``out/m12b_complete`` stay as they are), then the size report.
3. ``bench``: per slack, the bench arm (``bench``, ``bench80``, ...: cregrow + ``--min-fill 0.5``) on the 45 new pairs
   in small-sets-first order (``examples/m12c_bench_new.json``) in ``out/m12c_bench``, then its sweep report
   (``sweep_bench_<slack>``), the select re-rank and the coherence measurement on every bench pair run so far; after
   every slack, the 9 sweep pairs under each slack's arm, and the reports again, so a morning cut-off loses only
   those.

Each heavy step runs on ``WORKERS`` workers and is resumable (a finished run is skipped). Estimates use the bench
plan's time model (``results/m12c_bench_plan.json``) on each run's target cells (the plan's sizing at 1.0 and 0.8,
slack x the 1.0 cells otherwise; the hollow sizing for hollow1); reports are not modelled.
"""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Sequence

from brickwfc.experiments.complete import ARMS, PAIRS, load_pairs, predicted_minutes

WORKERS = 5
COMPLETE = ["python", "-m", "brickwfc.experiments.complete"]
SELECT = ["python", "-m", "brickwfc.experiments.select"]
COHERENCE = ["python", "-m", "brickwfc.experiments.coherence"]
SWEEP_OUT = "out/m12b_complete"
CHAIR_OUT = "out/m12c_reconnected"
BENCH_OUT = "out/m12c_bench"
CHAIR_PAIRS = "examples/m12c_chair_6378.json"
BENCH_NEW = "examples/m12c_bench_new.json"
BENCH_ALL = "examples/m12c_bench.json"
SUFFIX = {1.0: "", 0.9: "90", 0.8: "80", 0.7: "70", 0.6: "60"}  # slack -> arm name suffix
CHAIR_ARMS = ("cregrow", "cregrow90", "cregrow80", "cregrow70", "cregrow60", "usable", "usable90", "usable80",
              "usable70", "usable60")


def bench_arm(slack: float) -> str:
    arm = "bench" + SUFFIX.get(slack, "?")
    if arm not in ARMS:
        raise ValueError(f"no bench arm at slack {slack} (have: "
                         f"{', '.join(str(s) for s, x in SUFFIX.items() if 'bench' + x in ARMS)})")
    return arm


def slack_text(slack: float) -> str:
    return f"{slack:.1f}"


def bench_reports(slack: float, tag: str = "") -> list[tuple[str, list[str]]]:
    arm, name = bench_arm(slack), slack_text(slack)
    return [
        (f"bench-report-{name}{tag}", [*COMPLETE, "--out", BENCH_OUT, "--steps", "sweep-report", "--arms", arm,
                                       "--pairs", BENCH_ALL, "--report-name", f"sweep_bench_{name}"]),
        (f"bench-select-{name}{tag}", [*SELECT, "--sweep", BENCH_OUT, "--arms", arm, "--pairs", BENCH_ALL,
                                       "--out", f"{BENCH_OUT}/select_{name}"]),
        (f"bench-coherence-{name}{tag}", [*COHERENCE, "--sweep", BENCH_OUT, "--arms", arm, "--pairs", BENCH_ALL,
                                          "--results", f"{BENCH_OUT}/coherence_{name}"]),
    ]


def steps(slacks: Sequence[float]) -> list[tuple[str, list[str]]]:
    """(name, argv) of every step, in order."""
    for slack in slacks:
        bench_arm(slack)  # refuse an unknown slack before anything runs
    workers = ["--workers", str(WORKERS)]
    chair_arms = [arm for arm in CHAIR_ARMS if arm in ARMS]
    out = [
        ("hollow-sweep", [*COMPLETE, "--out", SWEEP_OUT, "--steps", "sweep", "--arms", "hollow1", "hollow1_80",
                          *workers]),
        ("hollow-report", [*COMPLETE, "--out", SWEEP_OUT, "--steps", "sweep-report", "--arms", "creserve", "hollow1",
                           "creserve80", "hollow1_80", "--report-name", "sweep_hollow"]),
        ("chair-sweep", [*COMPLETE, "--out", CHAIR_OUT, "--steps", "sweep", "--arms", *chair_arms, "--pairs",
                         CHAIR_PAIRS, *workers]),
        ("chair-size-report", [*COMPLETE, "--out", CHAIR_OUT, "--steps", "size-report", "--pairs", CHAIR_PAIRS]),
    ]
    for slack in slacks:
        out.append((f"bench-sweep-{slack_text(slack)}", [*COMPLETE, "--out", BENCH_OUT, "--steps", "sweep", "--arms",
                                                          bench_arm(slack), "--pairs", BENCH_NEW, *workers]))
        out += bench_reports(slack)
    for slack in slacks:  # the 9 sweep pairs last: the default pairs of the driver
        out.append((f"bench-sweep9-{slack_text(slack)}", [*COMPLETE, "--out", BENCH_OUT, "--steps", "sweep", "--arms",
                                                           bench_arm(slack), *workers]))
    for slack in slacks:
        out += bench_reports(slack, "-final")
    return out


def target_cells(plan: dict) -> dict[tuple[str, str, float], int]:
    """(set, object, slack) -> target cells, from the bench plan's sizing (creserve 1.0, creserve80 0.8)."""
    slack_of = {"creserve": 1.0, "creserve80": 0.8}
    return {(c["set"], c["object"], slack_of[c["arm"]]): c["target_cells"] for c in plan["cells"]}


def cells_at(cells: dict, set_number: str, obj: str, slack: float) -> int:
    return cells.get((set_number, obj, slack), round(cells[(set_number, obj, 1.0)] * slack))


def estimates(slacks: Sequence[float], plan_path: Path = Path("results/m12c_bench_plan.json"),
              hollow_path: Path = Path("results/m12c_hollow_sizing.json")) -> list[tuple[str, float | None]]:
    """(step, estimated wall minutes; None: not modelled) for ``steps(slacks)``."""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    model, cells = plan["model"], target_cells(plan)
    hollow = json.loads(hollow_path.read_text(encoding="utf-8"))
    minutes: dict[str, float] = {
        "hollow-sweep": sum(predicted_minutes(model, h["cells"]) for c in hollow for h in c["shells"]
                            if h["thickness"] == 1),
    }
    chair_slacks = {"cregrow": 1.0, "cregrow90": 0.9, "cregrow80": 0.8, "cregrow70": 0.7, "cregrow60": 0.6,
                    "usable": 1.0, "usable90": 0.9, "usable80": 0.8, "usable70": 0.7, "usable60": 0.6}
    minutes["chair-sweep"] = sum(predicted_minutes(model, cells_at(cells, "6378-1", "chair", chair_slacks[arm]))
                                 for arm in CHAIR_ARMS if arm in ARMS)
    new = load_pairs(Path(BENCH_NEW))
    for slack in slacks:
        name = slack_text(slack)
        minutes[f"bench-sweep-{name}"] = sum(predicted_minutes(model, cells_at(cells, s, o, slack)) for s, o in new)
        minutes[f"bench-sweep9-{name}"] = sum(predicted_minutes(model, cells_at(cells, s, o, slack)) for s, o in PAIRS)
    return [(name, minutes.get(name)) for name, _ in steps(slacks)]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.overnight", description=__doc__.splitlines()[0])
    parser.add_argument("what", choices=("steps", "estimate"))
    parser.add_argument("slacks", nargs="+", type=float, help="bench slacks, in the order to run them")
    args = parser.parse_args(argv)
    if args.what == "steps":
        for name, argv_ in steps(args.slacks):
            print(f"{name}\t{shlex.join(argv_)}")
        return 0
    rows = estimates(args.slacks)
    total = sum(m for _, m in rows if m is not None)
    print("estimated minutes per step (bench plan time model; reports not modelled):")
    for name, m in rows:
        print(f"  {name:28s} {'-' if m is None else round(m):>7}")
    print(f"  {'total (modelled steps)':28s} {total:7.0f} min = {total / 60:.1f} h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
