"""M12c: colour coherence of our builds' skins against the real sets, measured before anything is built.

    python -m brickwfc.experiments.coherence --sweep out/m12b_complete --data data/omr --results results/m12c_colour_measure

Measures (``bricks.coherence``): the same-colour share of visible part pairs, distinct colours per 4 x 4 skin window,
and the largest one-colour skin region as a share of the skin, on

- the 28 real building sets (``results/sets_selection.json``), voxelized with the full catalog, as in
  ``results/m12b_skins_measure.md`` (a voxelized set holds only its catalog parts on the stud grid; faces next to its
  missing parts count as skin when they are open to the outside);
- the selected build of each creserve and creserve80 run on the 9 sweep pairs (``--sweep``; the seed in its
  stats.json), and the complete chair (creserve80, 5891-1, seed 1; results/m12b_connected.md).

Each is also measured with its colours shuffled among the parts of each part type (``coherence.shuffled``, ``--draws``
seeded draws, mean): the inventory-preserving recolouring space, and its random point. Per pair, the reference is the
real model of the build's own set (same colours) and the 28 sets' median; the largest region depends on size, so its
reference is also the median of the ``--nearest`` real sets closest in skin cells. Writes ``<results>.json`` and
``<results>.png`` (real vs ours vs shuffled, per metric); the tables go to ``<cache>/tables.md``, and per-set
measures are cached under ``--cache`` (resumable).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw

from brickwfc.alt.inputs import DATA_DIR, SETS_FILE
from brickwfc.bricks.coherence import coherence, shuffled
from brickwfc.bricks.parts import BY_FILE, PlacedPart
from brickwfc.bricks.voxelize import grid_shape, voxelize
from brickwfc.experiments.complete import OBJECTS, SWEEP_SETS, load_run
from brickwfc.ldraw.fetch import fetch_set
from brickwfc.ldraw.mpd import flatten

ARMS = ("creserve", "creserve80")
COMPLETE_CHAIR = ("creserve80", "5891-1", "chair", 1)
METRICS = (  # (key, label, higher is more coherent, scale for display)
    ("same_color", "same-colour seams %", True, 100),
    ("colors_per_window", "colours per 4x4 window", False, 1),
    ("largest_region", "largest region % of skin", True, 100),
)


def measure(placed: Sequence[PlacedPart], shape: tuple[int, int, int], draws: int) -> dict:
    """The build's coherence, and the mean over ``draws`` shuffles of its colours."""
    row = asdict(coherence(placed, shape))
    shuffles = [asdict(coherence(shuffled(placed, np.random.default_rng([7, d])), shape)) for d in range(draws)]
    row["shuffled"] = {key: float(np.nanmean([s[key] for s in shuffles])) for key, *_ in METRICS}
    row["parts"] = len(placed)
    return row


def real_row(set_number: str, data: Path, cache: Path, draws: int) -> dict:
    path = cache / f"real_{set_number}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    placed, _ = voxelize(flatten(fetch_set(set_number, data).read_text(encoding="utf-8", errors="replace")), BY_FILE)
    row = {"set": set_number, **measure(placed, grid_shape(placed), draws)}
    path.write_text(json.dumps(row, indent=1), encoding="utf-8")
    return row


def build_row(sweep: Path, arm: str, set_number: str, obj: str, draws: int, seed: int | None = None) -> dict:
    """The selected build of a run (or seed ``seed`` of it)."""
    directory = sweep / "sweep" / arm / set_number / obj
    key, stats, candidates = load_run(directory)
    seed = stats["selected"][0]["seed"] if seed is None else seed
    chosen = next(c for c in candidates if c.seed == seed)
    return {"arm": arm, "set": set_number, "object": obj, "seed": seed,
            **measure(chosen.placed, tuple(key["grid"]), draws)}


def median(values: Sequence[float]) -> float:
    values = [v for v in values if not math.isnan(v)]
    return statistics.median(values) if values else math.nan


def references(build: dict, real: list[dict], nearest: int) -> dict:
    """The build's own set, the real sets' median, and the median of the ``nearest`` real sets in skin cells."""
    own = next(r for r in real if r["set"] == build["set"])
    close = sorted(real, key=lambda r: abs(math.log(r["skin_cells"] / build["skin_cells"])))[:nearest]
    return {"own": {key: own[key] for key, *_ in METRICS} | {"skin_cells": own["skin_cells"]},
            "median": {key: median([r[key] for r in real]) for key, *_ in METRICS},
            "nearest": {key: median([r[key] for r in close]) for key, *_ in METRICS}
            | {"sets": [r["set"] for r in close]}}


def table(builds: list[dict]) -> str:
    def f(value: float, scale: float) -> str:
        return "—" if math.isnan(value) else f"{value * scale:.0f}" if scale == 100 else f"{value * scale:.2f}"

    head = ["| build | parts | skin cells | colours on skin"]
    for _, label, *_ in METRICS:
        head.append(f" | {label}: ours / shuffled / own set / 28 sets")
    lines = ["".join(head) + " | largest region, nearest 5 in size |",
             "|---|---:|---:|---:|---|---|---|---:|"]
    for b in builds:
        name = f"{b['object']} {b['set']}, {b['arm']}" + (f" (seed {b['seed']}, complete)" if b.get("complete") else "")
        cells = [f"{name} | {b['parts']} | {b['skin_cells']} | {b['skin_colors']}"]
        for key, _, _, scale in METRICS:
            r = b["references"]
            cells.append(f"{f(b[key], scale)} / {f(b['shuffled'][key], scale)} / {f(r['own'][key], scale)} / "
                         f"{f(r['median'][key], scale)}")
        cells.append(f(b["references"]["nearest"]["largest_region"], 100))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def real_table(real: list[dict]) -> str:
    lines = ["| set | parts | skin cells | colours on skin | same-colour seams % (shuffled) | colours per 4x4 window "
             "(shuffled) | largest region % of skin (shuffled) |", "|---|---:|---:|---:|---:|---:|---:|"]
    for r in sorted(real, key=lambda r: r["skin_cells"]):
        lines.append(f"| {r['set']} | {r['parts']} | {r['skin_cells']} | {r['skin_colors']} | "
                     f"{100 * r['same_color']:.0f} ({100 * r['shuffled']['same_color']:.0f}) | "
                     f"{r['colors_per_window']:.2f} ({r['shuffled']['colors_per_window']:.2f}) | "
                     f"{100 * r['largest_region']:.0f} ({100 * r['shuffled']['largest_region']:.0f}) |")
    return "\n".join(lines)


def figure(real: list[dict], builds: list[dict], path: Path) -> Path:
    """Per metric, one strip per group (real sets, real shuffled, ours, ours shuffled), a dot per model or build,
    the median as a bar."""
    width, panel, left, pad = 900, 150, 170, 30
    groups = (("real sets", real, False, (70, 70, 70)), ("real, shuffled", real, True, (170, 170, 170)),
              ("ours (selected)", builds, False, (200, 80, 30)), ("ours, shuffled", builds, True, (235, 170, 140)))
    image = Image.new("RGB", (width, len(METRICS) * panel + pad), "white")
    draw = ImageDraw.Draw(image)
    for m, (key, label, higher, scale) in enumerate(METRICS):
        top = m * panel + pad // 2
        values = [g_value(r, key, s) * scale for _, rows, s, _ in groups for r in rows]
        values = [v for v in values if not math.isnan(v)]
        lo, hi = min(values), max(values)
        x = lambda v: left + 10 + (width - left - 50) * (v - lo) / ((hi - lo) or 1)  # noqa: E731
        draw.text((10, top), f"{label} ({'higher' if higher else 'lower'} is more coherent)", fill="black")
        for v in (lo, hi):  # the data's range, at its ends
            draw.text((x(v) - 10, top + panel - 30), f"{v:.2f}" if scale == 1 else f"{v:.0f}", fill="black")
        for g, (name, rows, shuffle, rgb) in enumerate(groups):
            y = top + 25 + g * 25
            draw.text((10, y - 6), name, fill=rgb)
            group = [g_value(r, key, shuffle) * scale for r in rows]
            group = [v for v in group if not math.isnan(v)]
            for v in group:
                draw.ellipse([x(v) - 3, y - 3, x(v) + 3, y + 3], fill=rgb)
            if group:
                mid = x(statistics.median(group))
                draw.line([mid, y - 9, mid, y + 9], fill="black", width=2)
    image.save(path)
    return path


def g_value(row: dict, key: str, shuffle: bool) -> float:
    return row["shuffled"][key] if shuffle else row[key]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.coherence",
                                     description=__doc__.splitlines()[0])
    parser.add_argument("--sweep", type=Path, default=Path("out/m12b_complete"), help="the completeness sweep's --out")
    parser.add_argument("--data", type=Path, default=DATA_DIR, help="OMR download cache")
    parser.add_argument("--sets-file", type=Path, default=SETS_FILE)
    parser.add_argument("--draws", type=int, default=5, help="colour shuffles per build (mean)")
    parser.add_argument("--nearest", type=int, default=5, help="real sets closest in skin cells, for the largest region")
    parser.add_argument("--cache", type=Path, default=Path("out/m12c_colour"))
    parser.add_argument("--results", type=Path, default=Path("results/m12c_colour_measure"),
                        help="writes <results>.json, .png")
    args = parser.parse_args(argv)
    args.cache.mkdir(parents=True, exist_ok=True)
    real = []
    for set_number in json.loads(args.sets_file.read_text(encoding="utf-8"))["selected"]:
        real.append(real_row(set_number, args.data, args.cache, args.draws))
        print(f"real {set_number}: {real[-1]['parts']} parts", flush=True)
    builds = []
    for arm in ARMS:
        for obj in OBJECTS:
            for set_number in SWEEP_SETS:
                builds.append(build_row(args.sweep, arm, set_number, obj, args.draws))
                print(f"{arm} {obj} {set_number}: seed {builds[-1]['seed']}", flush=True)
    arm, set_number, obj, seed = COMPLETE_CHAIR
    builds.append(build_row(args.sweep, arm, set_number, obj, args.draws, seed) | {"complete": True})
    for b in builds:
        b["references"] = references(b, real, args.nearest)
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.with_suffix(".json").write_text(json.dumps({"real": real, "builds": builds}, indent=1),
                                                 encoding="utf-8")
    figure(real, [b for b in builds if not b.get("complete")], args.results.with_suffix(".png"))
    text = table(builds) + "\n\nReal sets:\n\n" + real_table(real) + "\n"
    (args.cache / "tables.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
