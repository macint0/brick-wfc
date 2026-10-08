"""M12b step 2: tables, handicap counts, a side-by-side sheet and a determinism check for the proposal comparison.

    python -m brickwfc.experiments.proposal_report --dir out/m12b_proposal --weights data/models/proposal_run2.npz \\
        --figure-set 6370-1 --figure results/m12b_proposal_before_after.png --json results/m12b_proposal_summary.json

Reads the logged builds of ``experiments.proposal`` (``runs.jsonl``: metrics, placed parts, out-of-vocabulary
counts) and builds nothing, except ``--spot-check`` builds: they are rebuilt from their seeds with the driver's
own ``run_job`` and must give the logged parts and judge exactly. The rebuild uses the driver's defaults (grid
height, room, strengths); runs made with other values are not checkable this way.
Prints the tables as Markdown; the sheet shows one set's build of each condition with the same seed.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Sequence

from brickwfc.bricks.build import save_preview
from brickwfc.bricks.inventory import usage
from brickwfc.bricks.style import StyleStats
from brickwfc.bricks.tokens import Vocab
from brickwfc.bricks.voxelize import voxelize
from brickwfc.experiments.demo import labeled_sheet
from brickwfc.experiments.inventory import grid_for
from brickwfc.experiments.proposal import CONDITIONS, Job, placed_from_json, run_job, style_file
from brickwfc.ldraw.fetch import fetch_set
from brickwfc.ldraw.mpd import flatten

HEIGHT, ROOM, STRENGTH, PROPOSAL_STRENGTH = 12, 1.5, 1.0, 1.0  # the driver's defaults


def mean_sd(values: Sequence[float]) -> tuple[float, float]:
    return statistics.fmean(values), statistics.stdev(values) if len(values) > 1 else 0.0


def per_set(rows: list[dict], sets: Sequence[str]) -> list[dict]:
    """One summary per (set, condition), in ``sets`` order."""
    out = []
    for s in sets:
        for condition in CONDITIONS:
            mine = [r for r in rows if r["set_number"] == s and r["condition"] == condition]
            if not mine:
                continue
            judge, judge_sd = mean_sd([r["matched_judge"] for r in mine])
            out.append({
                "set": s, "condition": condition, "builds": len(mine),
                "valid_pct": 100 * statistics.fmean(r["valid"] for r in mine),
                "parts": statistics.fmean(r["parts"] for r in mine),
                "utilization_pct": 100 * statistics.fmean(r["utilization"] for r in mine),
                "matched_judge": judge, "matched_judge_sd": judge_sd,
                "matched_ceiling": statistics.fmean(r["matched_ceiling"] for r in mine),
                "distance": statistics.fmean(r["distance"] for r in mine),
                "outside_vocab": statistics.fmean(r["outside_vocab"] for r in mine),
                "seconds": statistics.fmean(r["wall_time_s"] for r in mine),
            })
    return out


def comparisons(summaries: list[dict], sets: Sequence[str]) -> list[dict]:
    """Per pair of conditions: on how many sets the first has the higher mean size-matched judge, and the mean
    difference over sets."""
    by = {(r["set"], r["condition"]): r for r in summaries}
    out = []
    for a, b in (("proposal_raster", "stats_raster"), ("proposal_raster", "stats_random"), ("stats_raster", "stats_random")):
        diffs = [by[s, a]["matched_judge"] - by[s, b]["matched_judge"] for s in sets if (s, a) in by and (s, b) in by]
        if diffs:
            out.append({"a": a, "b": b, "sets": len(diffs), "a_higher": sum(d > 0 for d in diffs),
                        "mean_difference": statistics.fmean(diffs)})
    return out


def handicap(models: dict[str, list], vocab: Vocab) -> dict[str, dict]:
    """Per set: parts in the inventory, and how many of them the model's vocabulary cannot express."""
    return {s: {"parts": len(real), "outside_vocab": sum(vocab.shape(p.shape) is None for p in real)}
            for s, real in models.items()}


def markdown(summaries: list[dict], pairs: list[dict], counts: dict[str, dict]) -> str:
    lines = ["| set | condition | builds | valid % | utilization % | size-matched judge (sd) | real ceiling | "
             "distance to set | outside vocab / build | s/build |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in summaries:
        lines.append(f"| {r['set']} | {r['condition']} | {r['builds']} | {r['valid_pct']:.0f} | {r['utilization_pct']:.1f} | "
                     f"{r['matched_judge']:.4f} ({r['matched_judge_sd']:.4f}) | {r['matched_ceiling']:.4f} | "
                     f"{r['distance']:.4f} | {r['outside_vocab']:.1f} | {r['seconds']:.2f} |")
    complete = {s for s in {r["set"] for r in summaries}
                if all(any(r["set"] == s and r["condition"] == c for r in summaries) for c in CONDITIONS)}
    lines += ["", f"Means over the {len(complete)} sets with every condition:", "",
              "| condition | sets | builds | valid % | utilization % | size-matched judge | outside vocab / build | s/build |",
              "|---|---|---|---|---|---|---|---|"]
    for condition in CONDITIONS:
        mine = [r for r in summaries if r["condition"] == condition and r["set"] in complete]
        if mine:
            mean = lambda key: statistics.fmean(r[key] for r in mine)  # noqa: E731
            lines.append(f"| {condition} | {len(mine)} | {sum(r['builds'] for r in mine)} | {mean('valid_pct'):.0f} | "
                         f"{mean('utilization_pct'):.1f} | {mean('matched_judge'):.4f} | {mean('outside_vocab'):.1f} | "
                         f"{mean('seconds'):.2f} |")
    lines += ["", "| set | parts in inventory | outside the model's vocabulary | share % |", "|---|---|---|---|"]
    for s, c in counts.items():
        lines.append(f"| {s} | {c['parts']} | {c['outside_vocab']} | {100 * c['outside_vocab'] / c['parts']:.0f} |")
    lines += [""] + [f"- {p['a']} has the higher size-matched judge than {p['b']} on {p['a_higher']}/{p['sets']} sets "
                     f"(mean difference {p['mean_difference']:+.4f})" for p in pairs]
    return "\n".join(lines) + "\n"


def spot_check(rows: list[dict], keys: Sequence[tuple[str, str, int]], models: dict[str, list], stats: StyleStats,
               weights: Path) -> list[str]:
    """Rebuild logged builds from their seeds; a mismatch in parts or judge is reported."""
    problems = []
    for s, condition, seed in keys:
        logged = next(r for r in rows if (r["set_number"], r["condition"], r["seed"]) == (s, condition, seed))
        again = run_job(Job(s, logged["fold"], condition, seed, tuple(models[s]), stats, str(weights), HEIGHT, ROOM,
                            STRENGTH, PROPOSAL_STRENGTH))
        if again["placed"] != logged["placed"] or again["matched_judge"] != logged["matched_judge"]:
            problems.append(f"{s} {condition} seed {seed}")
    return problems


def sheet(rows: list[dict], set_number: str, seed: int, real: list, directory: Path, out: Path) -> None:
    shape = grid_for(dict(usage(real)), HEIGHT, ROOM)
    images, labels = [], []
    for condition in CONDITIONS:
        row = next(r for r in rows if (r["set_number"], r["condition"], r["seed"]) == (set_number, condition, seed))
        path = directory / "previews" / f"{set_number}_{condition}_{seed}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        save_preview(placed_from_json(row["placed"]), shape, path)
        images.append(path)
        labels.append(f"{set_number}, seed {seed}: {condition}\n{row['parts']} parts, {row['outside_vocab']} outside the "
                      f"model's vocabulary\nsize-matched judge {row['matched_judge']:.4f}")
    out.parent.mkdir(parents=True, exist_ok=True)
    labeled_sheet(images, labels, out, columns=len(images))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.proposal_report", description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=Path("out/m12b_proposal"))
    parser.add_argument("--weights", type=Path, required=True, help="the run's proposal.npz (vocab.json next to it)")
    parser.add_argument("--data", type=Path, default=Path("data/omr"))
    parser.add_argument("--style-dir", type=Path, default=Path("results/m10_style_stats"))
    parser.add_argument("--figure-set", help="set of the side-by-side sheet (default: none)")
    parser.add_argument("--figure-seed", type=int, default=0)
    parser.add_argument("--figure", type=Path, default=Path("results/m12b_proposal_before_after.png"))
    parser.add_argument("--spot-check", type=int, default=3, help="rebuild the first N builds of the smallest set")
    parser.add_argument("--json", type=Path, help="write the summaries here")
    args = parser.parse_args(argv)

    rows = [json.loads(line) for line in (args.dir / "runs.jsonl").open(encoding="utf-8")]
    versions = {r["style_version"] for r in rows}
    if len(versions) != 1:
        parser.error(f"builds with several style versions: {sorted(versions)}")
    models = {s: voxelize(flatten(fetch_set(s, args.data).read_text(encoding="utf-8", errors="replace")))[0]
              for s in dict.fromkeys(r["set_number"] for r in rows)}
    sets = sorted(models, key=lambda s: len(models[s]))
    summaries = per_set(rows, sets)
    pairs = comparisons(summaries, sets)
    counts = handicap({s: models[s] for s in sets}, Vocab.load(args.weights.with_name("vocab.json")))
    print(f"style statistics {versions.pop()}, {len(rows)} builds\n")
    print(markdown(summaries, pairs, counts))

    if args.spot_check:
        stats = StyleStats.load(style_file(args.style_dir, rows[0]["fold"], rows[0]["style_version"]))
        keys = [(sets[0], condition, seed) for seed in range(math.ceil(args.spot_check / len(CONDITIONS)))
                for condition in CONDITIONS][: args.spot_check]
        problems = spot_check(rows, keys, models, stats, args.weights)
        print(f"determinism spot check, {len(keys)} rebuilt: " + ("all identical" if not problems else
                                                                   "DIFFERENT: " + ", ".join(problems)))
    if args.figure_set:
        sheet(rows, args.figure_set, args.figure_seed, models[args.figure_set], args.dir, args.figure)
        print(f"wrote {args.figure}")
    if args.json:
        args.json.write_text(json.dumps({"summaries": summaries, "comparisons": pairs, "handicap": counts}, indent=1),
                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
