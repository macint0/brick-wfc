"""M12b step 2: learned proposal vs statistics under the M10 judge, on the sets held out of training.

    python -m brickwfc.experiments.proposal --weights data/models/proposal.npz --out out/m12b_proposal
    python -m brickwfc.experiments.proposal --random-weights --seeds 1 --out out/m12b_proposal_smoke

Sets: fold ``--fold`` of M10's cross-validation (by default fold 0, the fold ``export_tokens`` holds out of the
model's training data), so neither the statistics (M10's fold file) nor the model has seen the set it
rebuilds. Every build is M10's ``D2_inventory`` with the learned contact style: the bottom-up builder (any
offset) using exactly the set's parts. Conditions:

  stats_random     statistics only, cells of a layer visited in random order (M10's builder)
  stats_raster     statistics only, raster order: the control, so a gain of the model is not the order's
  proposal_raster  statistics x the learned proposal (``--proposal-strength``), raster order

Metrics as in M10 (``experiments.style.evaluate``): validity, utilization, the judge and the size-matched
judge against the real model, the distance to the set's own statistics, time.
``--random-weights`` uses an untrained model (a smoke test of the plumbing; its numbers mean nothing).
Results are appended per build to ``runs.jsonl`` and resumed; ``--workers`` processes (default 3).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.parts import PlacedPart
from brickwfc.bricks.proposal import Proposal, random_weights
from brickwfc.bricks.style import StyleBias, StyleStats, events
from brickwfc.bricks.tokens import Vocab, build_vocab
from brickwfc.bricks.voxelize import voxelize
from brickwfc.experiments.inventory import grid_for
from brickwfc.experiments.style import InlineExecutor, evaluate, folds, setup
from brickwfc.ldraw.fetch import fetch_set
from brickwfc.ldraw.mpd import flatten

CONDITIONS = ("stats_random", "stats_raster", "proposal_raster")


@dataclass(frozen=True)
class Job:
    set_number: str
    fold: int
    condition: str
    seed: int
    real: tuple[PlacedPart, ...]
    stats: StyleStats
    weights: str  # path of proposal.npz, or "" for random weights
    height: int
    room: float
    strength: float
    proposal_strength: float


def load_proposal(weights: str) -> Proposal:
    if weights:
        return Proposal.load(Path(weights))
    vocab = build_vocab()
    return Proposal(random_weights(vocab, np.random.default_rng(0), d_model=64, layers=2, heads=4, max_len=1024), vocab)


def run_job(job: Job) -> dict:
    real = list(job.real)
    inventory, parts = setup(real, job.room - 1, job.stats)
    shape = grid_for(inventory, job.height, job.room)
    proposal = load_proposal(job.weights) if job.condition.startswith("proposal") else None
    builder = BottomUpBuilder(parts, any_offset=True, style=StyleBias(job.stats, parts, job.strength),
                              order=job.condition.split("_")[1], proposal=proposal,
                              proposal_strength=job.proposal_strength)
    start = time.perf_counter()
    grid = builder.build(shape, np.random.default_rng(job.seed), inventory)
    seconds = time.perf_counter() - start
    record = evaluate(job.set_number, job.fold, job.condition, "contacts", job.seed, grid, False, seconds, parts,
                      inventory, job.stats, StyleStats().add(real), events(real))
    return asdict(record)


def summary_table(rows: list[dict], sets: Sequence[str]) -> str:
    lines = ["| condition | builds | valid % | utilization % | judge | size-matched judge | real ceiling | "
             "distance to set | s/build |", "|---|---|---|---|---|---|---|---|---|"]
    for condition in CONDITIONS:
        mine = [r for r in rows if r["condition"] == condition and r["set_number"] in sets]
        if not mine:
            continue
        mean = lambda key: statistics.fmean(r[key] for r in mine)  # noqa: E731
        lines.append(f"| {condition} | {len(mine)} | {100 * mean('valid'):.0f} | {100 * mean('utilization'):.1f} | "
                     f"{mean('judge'):.4f} | {mean('matched_judge'):.4f} | {mean('matched_ceiling'):.4f} | "
                     f"{mean('distance'):.4f} | {mean('wall_time_s'):.2f} |")
    wins = []
    for a, b in (("proposal_raster", "stats_raster"), ("proposal_raster", "stats_random"), ("stats_raster", "stats_random")):
        per_set = []
        for s in sets:
            va = [r["matched_judge"] for r in rows if r["set_number"] == s and r["condition"] == a]
            vb = [r["matched_judge"] for r in rows if r["set_number"] == s and r["condition"] == b]
            if va and vb:
                per_set.append(statistics.fmean(va) > statistics.fmean(vb))
        if per_set:
            wins.append(f"{a} beats {b} (size-matched judge, mean over seeds) on {sum(per_set)}/{len(per_set)} sets")
    return "\n".join(lines + [""] + [f"- {w}" for w in wins]) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.proposal", description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--weights", type=Path, help="proposal.npz from training/train.py (vocab.json next to it)")
    group.add_argument("--random-weights", action="store_true", help="untrained model: a smoke test")
    parser.add_argument("--sets-file", type=Path, default=Path("results/sets_selection.json"))
    parser.add_argument("--style-dir", type=Path, default=Path("results/m10_style_stats"))
    parser.add_argument("--data", type=Path, default=Path("data/omr"))
    parser.add_argument("--fold", type=int, default=0)
    parser.add_argument("--sets", nargs="*", help="only these sets of the fold")
    parser.add_argument("--conditions", nargs="+", default=list(CONDITIONS), choices=CONDITIONS)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--height", type=int, default=12, help="grid height in plates (M10's)")
    parser.add_argument("--room", type=float, default=1.5, help="grid volume / inventory volume (M10's)")
    parser.add_argument("--strength", type=float, default=1.0, help="exponent on the learned style weights")
    parser.add_argument("--proposal-strength", type=float, default=1.0, help="exponent on the model's weights")
    parser.add_argument("--workers", type=int, default=min(3, max(1, (os.cpu_count() or 3) - 2)))
    parser.add_argument("--out", type=Path, default=Path("out/m12b_proposal"))
    args = parser.parse_args(argv)

    all_sets = json.loads(args.sets_file.read_text(encoding="utf-8"))["selected"]
    sets = [s for s in folds(all_sets, 4, 0)[args.fold] if not args.sets or s in args.sets]
    stats = StyleStats.load(args.style_dir / f"style_fold{args.fold}.json")
    if args.weights:
        Vocab.load(args.weights.with_name("vocab.json"))  # fail early if it is missing
    models = {s: voxelize(flatten(fetch_set(s, args.data).read_text(encoding="utf-8", errors="replace")))[0] for s in sets}

    args.out.mkdir(parents=True, exist_ok=True)
    runs = args.out / "runs.jsonl"
    rows = [json.loads(line) for line in runs.open(encoding="utf-8")] if runs.exists() else []
    done = {(r["set_number"], r["condition"], r["seed"]) for r in rows}
    jobs = [Job(s, args.fold, c, seed, tuple(models[s]), stats, str(args.weights or ""), args.height, args.room,
                args.strength, args.proposal_strength)
            for s in sets for c in args.conditions for seed in range(args.seeds) if (s, c, seed) not in done]
    print(f"{len(jobs)} builds to run ({len(done)} done) on {len(sets)} sets: {' '.join(sets)}")
    executor = InlineExecutor() if args.workers == 1 else ProcessPoolExecutor(max_workers=args.workers)
    with executor:
        for job, row in zip(jobs, executor.map(run_job, jobs)):
            rows.append(row)
            with runs.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            print(f"{job.set_number} {job.condition} seed {job.seed}: valid {row['valid']} judge {row['matched_judge']:.4f} "
                  f"{row['wall_time_s']:.1f}s", flush=True)
    table = summary_table(rows, sets)
    (args.out / "summary.md").write_text(table, encoding="utf-8")
    print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
