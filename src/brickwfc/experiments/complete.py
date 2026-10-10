"""M12b completeness: how complete the builds are, and why target cells stay empty.

    python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps final
    python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps trace --per-pair 10 --workers 5

Reads finished pipeline runs (no generation): the chair and table on the six M12 demo sets
(``m12b_sizing_fig/<set>/<object>_default``) and the car on four (``m12b_sizing/<set>/car_cover``).

``final`` (final state): per pair, over the valid candidates and the selected build, fill, holes (6-connected
components of unfilled target cells: count, largest, total), surface completeness (share of the target's exposed
cells, ``features.exposed``: a face open to the outside, the ground not counted, that are filled), and the share
of unfilled cells on that surface versus inside; a missing map per selected build (the build with its unfilled
target cells in red).

``trace`` (causes as the builder saw them): the selected build and the next valid candidates in seed order are
replayed with a trace on the builder (``BottomUpBuilder.trace``; it draws nothing, and each replay is checked
identical to the cached build). Every unfilled target cell gets the cause of its last visit:

  inventory  some placement covering it fits and keeps its cluster standing, but only with a part that is used up
  support    no stud within a part's reach below, or no placement that fits the free space has a stud under it
  balance    placements fit, but every one tips its cluster over
  repair     it was filled before a connect repair returned its part (the cause of the refill's miss is kept too)
  skipped    the solid-share draw passed it over, and no later part covered it
  geometry   no part fits the free space there (target too narrow, open-top or tile rules)
  unvisited  no visit recorded
  missed     a remaining part fits and balances (should not happen; counted to show that)
"""

from __future__ import annotations

import argparse
import functools
import json
import math
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import fields
from pathlib import Path
from typing import Sequence

import numpy as np
from scipy import ndimage

from brickwfc.alt.candidates import Candidate, Context, d2_builder
from brickwfc.alt.features import exposed, occupancy
from brickwfc.alt.inputs import learned_style, load_source
from brickwfc.alt.pipeline import AltConfig, cache_key, make_context, make_target, sized_target
from brickwfc.alt.pipeline import main as pipeline_main
from brickwfc.bricks.bottomup import BottomUpBuilder, _FitMap
from brickwfc.bricks.build import placed_colors, slope_profiles
from brickwfc.bricks.inventory import fits_inside, part_cells
from brickwfc.bricks.parts import CATALOG, PlacedPart, extract_parts
from brickwfc.bricks.shapes import surface
from brickwfc.bricks.style import StyleBias, styled_tileset
from brickwfc.bricks.support import studded
from brickwfc.experiments.demo import labeled_sheet
from brickwfc.experiments.style import InlineExecutor
from brickwfc.render3d import save_voxels_png

SETS = ("6378-1", "5891-1", "4956-1", "374-1", "7743-1", "10182-1")  # the M12 demo sets
OBJECTS = ("chair", "table", "car")
MISSING_RGB = (230, 30, 30)
CAUSES = ("inventory", "support", "balance", "repair", "skipped", "geometry", "unvisited", "missed")
VISIT_CAUSES = ("inventory", "support", "balance", "skipped", "geometry", "missed")  # what a visit can record


def run_dir(runs: Path, set_number: str, obj: str) -> Path:
    if obj == "car":
        return runs / "m12b_sizing" / set_number / "car_cover"
    return runs / "m12b_sizing_fig" / set_number / ("a712684f_default" if obj == "chair" else "858f0955_default")


def pairs(runs: Path) -> list[tuple[str, str, Path]]:
    """(set, object, run folder) of every pair that has a run, objects outer."""
    found = [(s, o, run_dir(runs, s, o)) for o in OBJECTS for s in SETS]
    return [p for p in found if (p[2] / "stats.json").exists()]


def load_run(directory: Path) -> tuple[dict, dict, list[Candidate]]:
    """(cache key, stats.json, candidates in seed order)."""
    lines = (directory / "candidates.jsonl").read_text(encoding="utf-8").splitlines()
    key = json.loads(lines[0])["key"]
    candidates = sorted((Candidate.from_json(json.loads(line)) for line in lines[1:] if line.strip()),
                        key=lambda c: c.seed)
    return key, json.loads((directory / "stats.json").read_text(encoding="utf-8")), candidates


def key_mask(key: dict) -> np.ndarray:
    """The run's target mask, as its cache key records it."""
    mask = np.zeros(key["grid"], dtype=bool)
    cells = np.array(key["mask"], dtype=np.int64).reshape(-1, 3)
    mask[tuple(cells.T)] = True
    return mask


def completeness(filled: np.ndarray, mask: np.ndarray) -> dict:
    """Fill, holes and surface completeness of a build (``filled``) against its target (``mask``)."""
    missing = mask & ~filled
    labels, count = ndimage.label(missing)
    sizes = np.bincount(labels.ravel())[1:] if count else np.zeros(0, dtype=np.int64)
    skin = exposed(mask)
    unfilled = int(missing.sum())
    return {
        "fill_pct": 100 * float((filled & mask).sum() / mask.sum()),
        "holes": int(count), "largest_hole": int(sizes.max()) if count else 0, "unfilled": unfilled,
        "surface_pct": 100 * float((filled & skin).sum() / skin.sum()),
        "unfilled_on_surface_pct": 100 * float((missing & skin).sum() / unfilled) if unfilled else 0.0,
    }


def complete(row: dict) -> bool:
    """Mac's bar for a complete build (cf, 2026-10-10): fill >= 97%, no hole over 4 cells, surface >= 98%."""
    return row["fill_pct"] >= 97 and row["largest_hole"] <= 4 and row["surface_pct"] >= 98


def missing_png(placed: Sequence[PlacedPart], mask: np.ndarray, path: Path) -> Path:
    """The build in grey (its parts' brightness kept; many sets have red parts) with its unfilled target cells
    drawn in red."""
    shape = mask.shape
    filled = occupancy(placed, shape)
    missing = mask & ~filled
    colors = placed_colors(list(placed), shape).astype(np.float64)
    grey = 0.35 * colors.mean(axis=-1, keepdims=True) + 0.55 * 255
    colors = np.repeat(grey, 3, axis=-1).round().astype(np.uint8)
    colors[missing] = MISSING_RGB
    profiles = slope_profiles(list(placed), shape)
    tops, bottoms = (None, None) if profiles is None else profiles
    save_voxels_png(filled | missing, colors, path, studded(list(placed), shape), tops, bottoms)
    return path


def mean(values: Sequence[float]) -> float:
    return float(np.mean(values)) if len(values) else math.nan


# Final state ----------------------------------------------------------------------------------------------


def final_pair(set_number: str, obj: str, directory: Path, out: Path) -> dict:
    key, stats, candidates = load_run(directory)
    mask = key_mask(key)
    selected = stats["selected"][0]["seed"] if stats["selected"] else None
    rows = {}
    for c in candidates:
        if c.valid:
            rows[c.seed] = completeness(occupancy(c.placed, mask.shape), mask) | {"parts": len(c.placed)}
    valid = list(rows.values())
    summary = {"set": set_number, "object": obj, "run": directory.as_posix(), "target_cells": int(mask.sum()),
               "surface_cells": int(exposed(mask).sum()), "valid": len(valid), "candidates": len(candidates),
               "selected_seed": selected, "complete": sum(complete(r) for r in valid)}
    for name in ("fill_pct", "holes", "largest_hole", "unfilled", "surface_pct", "unfilled_on_surface_pct"):
        summary[f"mean_{name}"] = mean([r[name] for r in valid])
    if selected is not None:
        chosen = next(c for c in candidates if c.seed == selected)
        summary["selected"] = rows[selected]
        summary["missing_png"] = missing_png(chosen.placed, mask, out / "missing" / f"{obj}_{set_number}.png").as_posix()
    return summary


def final_report(rows: list[dict]) -> str:
    lines = ["| object | set | target cells | valid | complete | fill % (sel / mean) | holes (sel / mean) | "
             "largest hole (sel / mean) | unfilled cells (sel) | surface % (sel / mean) | unfilled on surface % (sel / mean) |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        s = r.get("selected", {})
        lines.append(
            f"| {r['object']} | {r['set']} | {r['target_cells']} | {r['valid']}/{r['candidates']} | {r['complete']} | "
            f"{s.get('fill_pct', math.nan):.1f} / {r['mean_fill_pct']:.1f} | {s.get('holes', 0)} / {r['mean_holes']:.1f} | "
            f"{s.get('largest_hole', 0)} / {r['mean_largest_hole']:.0f} | {s.get('unfilled', 0)} | "
            f"{s.get('surface_pct', math.nan):.1f} / {r['mean_surface_pct']:.1f} | "
            f"{s.get('unfilled_on_surface_pct', math.nan):.0f} / {r['mean_unfilled_on_surface_pct']:.0f} |")
    return "\n".join(lines)


def missing_sheet(rows: list[dict], out: Path) -> Path:
    """Objects as rows, sets as columns; a blank where a pair has no run."""
    by_pair = {(r["object"], r["set"]): r for r in rows}
    blank = out / "missing" / "none.png"
    blank.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image

    Image.new("RGB", (8, 8), (255, 255, 255)).save(blank)
    images, labels = [], []
    for obj in OBJECTS:
        for set_number in SETS:
            r = by_pair.get((obj, set_number))
            if r is None or "missing_png" not in r:
                images.append(blank)
                labels.append(f"{obj}, {set_number}: no run")
                continue
            s = r["selected"]
            images.append(Path(r["missing_png"]))
            labels.append(f"{obj}, {set_number}: fill {s['fill_pct']:.0f}%\n{s['holes']} holes, largest "
                          f"{s['largest_hole']}\nsurface {s['surface_pct']:.0f}%")
    path = out / "missing_sheet.png"
    labeled_sheet(images, labels, path, columns=len(SETS), width=600)
    return path


def step_final(args: argparse.Namespace) -> None:
    rows = [final_pair(s, o, d, args.out) for s, o, d in pairs(args.runs)]
    (args.out / "final.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    sheet = missing_sheet(rows, args.out)
    (args.out / "final.md").write_text(final_report(rows) + "\n", encoding="utf-8")
    print(final_report(rows))
    print(f"wrote final.json, final.md, {sheet}")


# Traced replay --------------------------------------------------------------------------------------------


class Trace:
    """``BottomUpBuilder.trace``: the cause of each watched cell's last visit, and the cells filled before a repair.
    Only cells in ``watch`` (the cached build's unfilled target cells) are classified."""

    def __init__(self, watch: np.ndarray) -> None:
        self.watch = watch
        self.cause = np.full(watch.shape, -1, dtype=np.int8)  # index into VISIT_CAUSES
        self.before_repair = np.zeros(watch.shape, dtype=bool)
        self.studs_everywhere = np.ones(watch.shape, dtype=bool)
        self.epoch = 0  # bumped at every repair (a new state)
        self.maps: tuple | None = None  # (epoch, parts placed, layer, full fit map, space fit map)
        self.at_holes: dict | None = None  # inventory left when the last hole pass started
        self.final = None  # the builder's final state
        self.used_up: set[str] = set()  # the last classify's parts that fit under every rule but are used up

    def skipped(self, state, y: int, z: int, x: int) -> None:
        if self.watch[y, z, x]:
            self.cause[y, z, x] = VISIT_CAUSES.index("skipped")

    def repaired(self, state) -> None:
        self.before_repair |= state.filled
        self.epoch += 1

    def holes(self, state) -> None:
        self.at_holes = None if state.remaining is None else dict(state.remaining)  # the last hole pass's start

    def finished(self, state) -> None:
        self.final = state

    def failed(self, builder: BottomUpBuilder, state, allowed: np.ndarray, reachable: np.ndarray,
               y: int, z: int, x: int) -> None:
        if self.watch[y, z, x]:
            self.cause[y, z, x] = VISIT_CAUSES.index(self.classify(builder, state, allowed, reachable, y, z, x))

    def fit_maps(self, builder: BottomUpBuilder, state, allowed: np.ndarray, y: int,
                 hang: bool = False) -> tuple[_FitMap, _FitMap]:
        """Fit maps of layer ``y`` as the build stands: every rule, and every rule but support (``hang``: a part
        may also hang from the part above, as in the hole pass with hang)."""
        stamp = (self.epoch, len(state.placed), y, hang, id(state))
        if self.maps is None or self.maps[:5] != stamp:
            studless = builder._studless_top if builder.open_tops else None
            open_bottom = state.open_bottom if builder.open_bottoms else None
            full = _FitMap(state.filled, state.studs, allowed, y, studless, open_bottom,
                           state.open_bottom if hang else None)
            space = _FitMap(state.filled, self.studs_everywhere, allowed, y, studless, open_bottom)
            self.maps = (*stamp, full, space)
        return self.maps[5], self.maps[6]

    def classify(self, builder: BottomUpBuilder, state, allowed: np.ndarray, reachable: np.ndarray,
                 y: int, z: int, x: int, hang: bool = False) -> str:
        if not reachable[z, x]:
            return "support"
        full, space = self.fit_maps(builder, state, allowed, y, hang)
        hang_bottom = state.open_bottom if hang else None
        self.used_up = set()
        open_bottom = state.open_bottom if builder.open_bottoms else None
        remaining = state.remaining
        fits_space = tips = used_up = False
        for shape, colors in builder.shape_colors.items():
            left = remaining is None or any(remaining.get((shape.part.name, c.name), 0) > 0 for c in colors)
            cells = builder.cell_masks.get(shape)
            if cells is None:
                full_map, space_map = full.corners(shape), space.corners(shape)
            for dz, dx in shape.footprint:
                part = PlacedPart(shape, colors[0], y, x - dx, z - dz)
                if cells is None:
                    inside = 0 <= part.z < full_map.shape[0] and 0 <= part.x < full_map.shape[1]
                    fits = inside and bool(full_map[part.z, part.x])
                    roomy = 0 <= part.z < space_map.shape[0] and 0 <= part.x < space_map.shape[1] \
                        and bool(space_map[part.z, part.x])
                else:
                    args = (cells, state.filled)
                    fits = builder._fits_cells(part, *args, state.studs, allowed, open_bottom, builder.open_tops,
                                               hang_bottom)
                    roomy = builder._fits_cells(part, *args, self.studs_everywhere, allowed, open_bottom,
                                                builder.open_tops)
                fits_space |= roomy
                if not fits:
                    continue
                links = builder._links(part, state.owner) if hang else builder._below(part, state.owner)
                if state.balance is None or state.balance.can_add(part, links):
                    if left:
                        return "missed"
                    used_up = True
                    self.used_up.add(shape.part.name)
                    break  # this shape would do; try the others (a remaining one may fit)
                tips = True
        if used_up:
            return "inventory"
        if tips:
            return "balance"
        return "support" if fits_space else "geometry"

    def causes(self, final_filled: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(cause index into CAUSES, last visit's cause index into CAUSES or -1) per watched cell, -1 elsewhere."""
        visit = np.where(self.cause >= 0, np.array([CAUSES.index(c) for c in VISIT_CAUSES])[self.cause.clip(0)], -1)
        cause = np.where(visit >= 0, visit, CAUSES.index("unvisited"))
        cause = np.where(self.before_repair & ~final_filled, CAUSES.index("repair"), cause)
        return np.where(self.watch, cause, -1), np.where(self.watch, visit, -1)


@functools.lru_cache(maxsize=1)
def replay_setup(directory: str) -> tuple[Context, object, StyleBias]:
    """The run's context (rebuilt from its stats.json; its cache key must equal the cached one), tileset and bias."""
    key, stats, _ = load_run(Path(directory))
    known = {f.name for f in fields(AltConfig)}
    saved = {"holes": False, "hang": False, "sizing": "box"} | stats["config"]  # as before these settings existed
    config = AltConfig(**{k: v for k, v in saved.items() if k in known})
    source = load_source(key["source"])
    style, label = learned_style(source.name)
    context = make_context(source, style, config, make_target(source, config))
    if cache_key(source, label, context) != key:
        raise SystemExit(f"{directory}: the rebuilt context does not match the cached candidates")
    parts = styled_tileset(context.inventory, context.colors, context.empty_weight_per_part, context.stats)
    return context, parts, StyleBias(context.stats, parts, context.strength)


def replay(directory: str, seed: int) -> dict:
    """Replay one cached candidate with a trace; the causes of its unfilled target cells."""
    context, parts, bias = replay_setup(directory)
    _, _, candidates = load_run(Path(directory))
    cached = next(c for c in candidates if c.seed == seed)
    mask = context.mask
    final = occupancy(cached.placed, mask.shape)
    trace = Trace(mask & ~final)
    builder = BottomUpBuilder(parts, any_offset=True, style=bias, balanced=context.balanced, bridge=context.bridge,
                              connect=context.connect, connect_rounds=context.connect_rounds,
                              open_tops=context.open_tops, order=context.order, skin=context.skin,
                              skin_power=context.skin_power)
    builder.trace = trace
    grid = builder.build(context.grid, np.random.default_rng(seed), context.inventory, mask, context.preferred,
                         context.plane)
    placed, _ = extract_parts(grid, parts)
    if sorted(map(placement, placed)) != sorted(map(placement, cached.placed)):
        raise SystemExit(f"{directory} seed {seed}: the traced replay differs from the cached build")
    cause, visit = trace.causes(final)
    skin = surface(mask)
    counts = {c: int((cause == i).sum()) for i, c in enumerate(CAUSES)}
    on_surface = {c: int(((cause == i) & skin).sum()) for i, c in enumerate(CAUSES)}
    repair_refill = {c: int(((cause == CAUSES.index("repair")) & (visit == i)).sum()) for i, c in enumerate(CAUSES)}
    cells = [[*map(int, cell), int(cause[tuple(cell)])] for cell in np.argwhere(cause >= 0)]
    return {"seed": seed, "unfilled": int((cause >= 0).sum()), "causes": counts, "on_surface": on_surface,
            "repair_refill": repair_refill, "cells": cells}


def placement(part: PlacedPart) -> tuple:
    return part.shape.part.name, part.shape.turn, part.color.name, part.layer, part.x, part.z


def trace_seeds(directory: Path, per_pair: int) -> list[int]:
    """The selected build, then the lowest-seed other valid candidates, ``per_pair`` in all."""
    _, stats, candidates = load_run(directory)
    selected = [stats["selected"][0]["seed"]] if stats["selected"] else []
    others = [c.seed for c in candidates if c.valid and c.seed not in selected]
    return (selected + others)[:per_pair]


def step_trace(args: argparse.Namespace) -> None:
    traces = args.out / "traces"
    traces.mkdir(parents=True, exist_ok=True)
    jobs = []
    for set_number, obj, directory in pairs(args.runs):
        path = traces / f"{obj}_{set_number}.jsonl"
        done = {json.loads(line)["seed"] for line in path.read_text(encoding="utf-8").splitlines()} if path.exists() else set()
        jobs += [(path, directory.as_posix(), seed) for seed in trace_seeds(directory, args.per_pair) if seed not in done]
    print(f"{len(jobs)} replays to run", flush=True)
    with ProcessPoolExecutor(args.workers) if args.workers > 1 else InlineExecutor() as pool:
        futures = [(path, pool.submit(replay, directory, seed)) for path, directory, seed in jobs]
        for i, (path, future) in enumerate(futures, 1):  # collected in job order: resumable, same files for any workers
            row = future.result()
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            print(f"  {i}/{len(futures)} {path.stem} seed {row['seed']}: {row['causes']}", flush=True)


# Trace report ---------------------------------------------------------------------------------------------


def trace_rows(args: argparse.Namespace) -> list[dict]:
    """Per pair: the traced builds' causes, pooled, and the selected build's."""
    rows = []
    for set_number, obj, directory in pairs(args.runs):
        path = args.out / "traces" / f"{obj}_{set_number}.jsonl"
        if not path.exists():
            continue
        builds = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        key, stats, candidates = load_run(directory)
        selected = stats["selected"][0]["seed"] if stats["selected"] else None
        pooled = {k: {c: sum(b[k][c] for b in builds) for c in CAUSES} for k in ("causes", "on_surface", "repair_refill")}
        rows.append({"set": set_number, "object": obj, "builds": len(builds),
                     "unfilled": sum(b["unfilled"] for b in builds), **pooled,
                     "above": above_counts(builds, {c.seed: c for c in candidates}, key_mask(key).shape),
                     "selected": next((b for b in builds if b["seed"] == selected), None)})
    return rows


def above_counts(builds: list[dict], candidates: dict[int, Candidate], shape: tuple[int, int, int]) -> dict:
    """Per cause (support, repair): [cells, with a placed part 1 cell up, with one 1 or 2 cells up] in the final
    build: what a part hanging from the part above could reach."""
    counts = {c: [0, 0, 0] for c in ("support", "repair")}
    for b in builds:
        filled = occupancy(candidates[b["seed"]].placed, shape)
        up1 = np.zeros_like(filled)
        up1[:-1] = filled[1:]
        up2 = up1.copy()
        up2[:-2] |= filled[2:]
        for y, z, x, cause in b["cells"]:
            if CAUSES[cause] in counts:
                t = counts[CAUSES[cause]]
                t[0] += 1
                t[1] += bool(up1[y, z, x])
                t[2] += bool(up2[y, z, x])
    return counts


def above_report(rows: list[dict]) -> str:
    lines = ["| object | set | support cells | part 1 up % | part 1-2 up % | repair cells | part 1 up % | part 1-2 up % |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        s, p = r["above"]["support"], r["above"]["repair"]
        lines.append(f"| {r['object']} | {r['set']} | {s[0]} | {pct(s[1], s[0])} | {pct(s[2], s[0])} | {p[0]} | "
                     f"{pct(p[1], p[0])} | {pct(p[2], p[0])} |")
    return "\n".join(lines)


SHOWN = ("support", "repair", "inventory", "skipped", "balance", "geometry", "missed")


def pct(part: float, whole: float) -> str:
    return f"{100 * part / whole:.0f}" if whole else "-"


def trace_report(rows: list[dict]) -> str:
    head = " | ".join(f"{c} %" for c in SHOWN)
    lines = [f"| object | set | builds | unfilled / build | {head} | on surface % | repair refill: support / inventory / skipped % |",
             "|---|---|---:|---:|" + "---:|" * len(SHOWN) + "---:|---:|"]
    total = {c: 0 for c in CAUSES}
    for r in rows:
        u = r["unfilled"]
        for c in CAUSES:
            total[c] += r["causes"][c] / u if u else 0  # each pair weighs the same
        refill, rep = r["repair_refill"], r["causes"]["repair"]
        lines.append(f"| {r['object']} | {r['set']} | {r['builds']} | {u / r['builds']:.0f} | "
                     + " | ".join(pct(r["causes"][c], u) for c in SHOWN)
                     + f" | {pct(sum(r['on_surface'].values()), u)} | "
                     f"{pct(refill['support'], rep)} / {pct(refill['inventory'], rep)} / {pct(refill['skipped'], rep)} |")
    n = len(rows)
    lines.append("| **mean of pairs** | | | | " + " | ".join(f"{100 * total[c] / n:.0f}" for c in SHOWN) + " | | |")
    return "\n".join(lines)


def surface_split(rows: list[dict]) -> str:
    """Per cause, the share of its cells on the target's surface (pooled over every pair)."""
    lines = ["| cause | cells | on surface % |", "|---|---:|---:|"]
    for c in CAUSES:
        cells = sum(r["causes"][c] for r in rows)
        if cells:
            lines.append(f"| {c} | {cells} | {pct(sum(r['on_surface'][c] for r in rows), cells)} |")
    return "\n".join(lines)


def step_report(args: argparse.Namespace) -> None:
    rows = trace_rows(args)
    (args.out / "trace.json").write_text(json.dumps([{k: v for k, v in r.items() if k != "selected"} for r in rows],
                                                    indent=2), encoding="utf-8")
    text = trace_report(rows) + "\n\n" + surface_split(rows) + "\n\n" + above_report(rows) + "\n"
    (args.out / "trace.md").write_text(text, encoding="utf-8")
    print(text)


# Holes: why the hole pass leaves cells empty ----------------------------------------------------------------

# Why no part fits at an unfilled target cell of the final build, under the hole pass's rules (hanging support with
# hang) and the inventory left: inventory, balance and geometry as in the trace; unreachable: no stud below and no
# part above within reach; support: within reach, but no part covering the cell rests or hangs there; ground: a part
# fits on the ground layer, which the last connect round's hole pass does not visit; missed: a part fits (none
# expected: the pass ends when nothing fits).
FINAL_CAUSES = ("inventory", "balance", "support", "unreachable", "geometry", "ground", "missed")
HOLE_BINS = ((1, 1), (2, 4), (5, 16), (17, 64), (65, None))  # hole sizes in cells, inclusive
SMALL_HOLE = 4  # holes up to this many cells get the smallest part that fits them


def hole_bin(size: int) -> str:
    return next(f"{lo}" if lo == hi else f"{lo}+" if hi is None else f"{lo}-{hi}"
                for lo, hi in HOLE_BINS if size >= lo and (hi is None or size <= hi))


def small_parts(size: int) -> list:
    """Catalog parts of at most ``size`` cells, smallest first."""
    return sorted((part for part in CATALOG.values() if part_cells(part) <= size), key=lambda p: (part_cells(p), p.name))


def final_causes(builder: BottomUpBuilder, trace: Trace, mask: np.ndarray) -> tuple[np.ndarray, dict]:
    """(per unfilled target cell of the traced build's final state, its index into FINAL_CAUSES, -1 elsewhere; per
    inventory cell, the names of the parts that would fit there under every rule but are used up)."""
    state = trace.final
    cause = np.full(mask.shape, -1, dtype=np.int8)
    wanted = {}
    for y in np.unique(np.argwhere(mask & ~state.filled)[:, 0]):
        reach = builder._reachable(state.studs, y)
        if builder.hang:
            reach = reach | builder._hang_reachable(state, y)
        anywhere = np.ones_like(reach)
        for z, x in np.argwhere(mask[y] & ~state.filled[y]).tolist():
            if not reach[z, x]:
                name = "unreachable"
            else:
                name = trace.classify(builder, state, mask, anywhere, y, z, x, hang=builder.hang)
                if name == "missed" and y == 0:
                    name = "ground"
                if name == "inventory":
                    wanted[(int(y), z, x)] = sorted(trace.used_up)
            cause[y, z, x] = FINAL_CAUSES.index(name)
    return cause, wanted


def holes_of(filled: np.ndarray, mask: np.ndarray, cause: np.ndarray, at_holes: dict | None,
             remaining: dict | None, wanted: dict | None = None) -> tuple[list[dict], list[dict]]:
    """(per size bin: holes and cells, per hole of at most SMALL_HOLE cells: the smallest catalog parts that fit
    inside its space, how many parts that fit its space the inventory had when the last hole pass started and at
    the end, the used-up parts that would fit its cells under every rule, how many of those the inventory had when
    the last hole pass started, and its cells' causes)."""
    labels, count = ndimage.label(mask & ~filled)
    sizes = np.bincount(labels.ravel(), minlength=count + 1)[1:]
    bins = []
    for lo, hi in HOLE_BINS:
        chosen = (sizes >= lo) & (sizes <= (hi if hi is not None else sizes.max(initial=0)))
        bins.append({"bin": hole_bin(lo), "holes": int(chosen.sum()), "cells": int(sizes[chosen].sum())})
    small = []
    candidates = small_parts(SMALL_HOLE)
    for index, region in enumerate(ndimage.find_objects(labels), 1):
        if sizes[index - 1] > SMALL_HOLE:
            continue
        hole = labels[region] == index
        fitting = [part for part in candidates if part_cells(part) <= hole.sum() and fits_inside(part, hole)]
        smallest = [p.name for p in fitting if part_cells(p) == part_cells(fitting[0])] if fitting else []
        names = {p.name for p in fitting}

        def held(inventory: dict | None) -> int | None:
            return None if inventory is None else sum(n for (name, _), n in inventory.items() if name in names)

        cells = np.argwhere(labels == index)
        needed = sorted({name for c in cells.tolist() for name in (wanted or {}).get(tuple(c), [])})
        small.append({"size": int(sizes[index - 1]), "smallest": smallest, "fitting": sorted(names),
                      "at_holes": held(at_holes), "at_end": held(remaining), "wanted": needed,
                      "wanted_at_holes": None if at_holes is None else
                      sum(n for (name, _), n in at_holes.items() if name in needed),
                      "causes": sorted(FINAL_CAUSES[cause[tuple(c)]] for c in cells),
                      "layers": sorted({int(c[0]) for c in cells})})
    return bins, small


def replay_final(directory: str, seed: int) -> dict:
    """Replay one cached candidate with a trace; why its unfilled target cells stayed empty, and its holes."""
    context, parts, bias = replay_setup(directory)
    _, _, candidates = load_run(Path(directory))
    cached = next(c for c in candidates if c.seed == seed)
    mask = context.mask
    final = occupancy(cached.placed, mask.shape)
    trace = Trace(mask & ~final)
    builder = d2_builder(context, parts, bias)
    builder.trace = trace
    grid = builder.build(context.grid, np.random.default_rng(seed), context.inventory, mask, context.preferred,
                         context.plane)
    placed, _ = extract_parts(grid, parts)
    if sorted(map(placement, placed)) != sorted(map(placement, cached.placed)) or \
            not np.array_equal(trace.final.filled, final):
        raise SystemExit(f"{directory} seed {seed}: the traced replay differs from the cached build")
    cause, wanted = final_causes(builder, trace, mask)
    skin = exposed(mask)
    bins, small = holes_of(final, mask, cause, trace.at_holes, trace.final.remaining, wanted)
    left = trace.final.remaining
    needed = Counter(name for names in wanted.values() for name in names)

    def count(inventory: dict | None, name: str) -> int | None:
        return None if inventory is None else sum(n for (part, _), n in inventory.items() if part == name)
    return {"seed": seed, "unfilled": int((cause >= 0).sum()),
            "causes": {c: int((cause == i).sum()) for i, c in enumerate(FINAL_CAUSES)},
            "on_surface": {c: int(((cause == i) & skin).sum()) for i, c in enumerate(FINAL_CAUSES)},
            "parts_left_at_holes": None if trace.at_holes is None else sum(trace.at_holes.values()),
            "parts_left_at_end": None if left is None else sum(left.values()),
            "bins": bins, "small": small, "completeness": completeness(final, mask),
            "wanted": [{"part": name, "cells": cells, "in_set": count(context.inventory, name),
                        "at_holes": count(trace.at_holes, name)} for name, cells in needed.most_common()]}


def holes_report(rows: list[dict]) -> str:
    shown = [c for c in FINAL_CAUSES if any(r["causes"][c] for r in rows)]
    lines = ["Why the selected builds' unfilled target cells stayed empty (share of unfilled cells; on the surface in "
             "brackets):", "",
             "| object | set | fill % | unfilled | " + " | ".join(shown) + " | parts left (hole pass start / end) |",
             "|---|---|---:|---:|" + "---:|" * len(shown) + "---:|"]
    for r in rows:
        n = max(1, r["unfilled"])
        causes = " | ".join(f"{100 * r['causes'][c] / n:.0f} ({100 * r['on_surface'][c] / n:.0f})" for c in shown)
        lines.append(f"| {r['object']} | {r['set']} | {r['completeness']['fill_pct']:.1f} | {r['unfilled']} | {causes} | "
                     f"{r['parts_left_at_holes']} / {r['parts_left_at_end']} |")
    labels = [hole_bin(lo) for lo, _ in HOLE_BINS]
    lines += ["", "Holes by size (holes; share of unfilled cells):", "",
              "| object | set | holes | " + " | ".join(f"{b} cells" for b in labels) + " |",
              "|---|---|---:|" + "---:|" * len(labels)]
    for r in rows:
        n = max(1, r["unfilled"])
        cells = " | ".join(f"{b['holes']}; {100 * b['cells'] / n:.0f}%" for b in r["bins"])
        lines.append(f"| {r['object']} | {r['set']} | {sum(b['holes'] for b in r['bins'])} | {cells} |")
    lines += ["", f"Holes of 1-{SMALL_HOLE} cells: the smallest catalog part that fits inside each, whether the inventory "
              "had a part that fits it when the last hole pass started and at the end, and why its cells stayed empty:",
              "", "| object | set | small holes | smallest part (holes) | had a part that fits the space, at hole pass "
              "start / end | used-up part that fits under every rule (holes) | had it at hole pass start | causes of "
              "their cells |", "|---|---|---:|---|---:|---|---:|---|"]
    for r in rows:
        small = r["small"]
        smallest = Counter("/".join(h["smallest"]) or "none" for h in small)
        causes = Counter(c for h in small for c in h["causes"])
        needed = Counter("/".join(h["wanted"]) for h in small if h["wanted"])
        lines.append(f"| {r['object']} | {r['set']} | {len(small)} | "
                     f"{', '.join(f'{k} ({v})' for k, v in smallest.most_common())} | "
                     f"{sum(bool(h['at_holes']) for h in small)} / {sum(bool(h['at_end']) for h in small)} | "
                     f"{', '.join(f'{k} ({v})' for k, v in needed.most_common()) or '-'} | "
                     f"{sum(bool(h['wanted_at_holes']) for h in small)} | "
                     f"{', '.join(f'{k} {v}' for k, v in causes.most_common())} |")
    lines += ["", "Inventory cells: the parts that would fit there under every rule but were used up (cells naming the "
              "part; the set's count; left when the last hole pass started), the five most named:", "",
              "| object | set | inventory cells | parts |", "|---|---|---:|---|"]
    for r in rows:
        parts = "; ".join(f"{w['part']} {w['cells']} ({w['in_set']}; {w['at_holes']})" for w in r["wanted"][:5])
        lines.append(f"| {r['object']} | {r['set']} | {r['causes']['inventory']} | {parts} |")
    return "\n".join(lines)


def step_holes(args: argparse.Namespace) -> None:
    """The ``--arm``'s selected builds, replayed with a trace (identity asserted): causes, hole sizes, small holes."""
    jobs = []
    for obj in OBJECTS:
        for set_number in SWEEP_SETS:
            directory = arm_dir(args.out, args.arm, set_number, obj, args.runs)
            if not (directory / "stats.json").exists():
                print(f"{args.arm} {obj} {set_number}: no run", flush=True)
                continue
            _, stats, _ = load_run(directory)
            if stats["selected"]:
                jobs.append((obj, set_number, directory.as_posix(), stats["selected"][0]["seed"]))
    rows = []
    with ProcessPoolExecutor(args.workers) if args.workers > 1 else InlineExecutor() as pool:
        futures = [(obj, set_number, pool.submit(replay_final, directory, seed))
                   for obj, set_number, directory, seed in jobs]
        for obj, set_number, future in futures:  # in job order: the same file for any workers
            rows.append({"object": obj, "set": set_number, "arm": args.arm} | future.result())
            print(f"  {obj} {set_number}: {rows[-1]['causes']}", flush=True)
    (args.out / f"holes_{args.arm}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    text = holes_report(rows) + "\n"
    (args.out / f"holes_{args.arm}.md").write_text(text, encoding="utf-8")
    print(text)


# Sweep: sizing and the hole pass ----------------------------------------------------------------------------

SWEEP_SETS = ("6378-1", "5891-1", "4956-1")
STRUCTURES = {"chair": "a712684f-8e79-4ecd-81de-11aef42b50d4", "table": "858f0955-846e-4138-84d9-df66b66eddc2",
              "car": "4b15b71c-f400-4e54-a118-f0c2afba6e17"}
HANG = ["--holes", "--hang"]
ARMS = {  # name: (title, pipeline flags; explicit, since the defaults changed after the sweep); "old" is the
    # cached pre-fix run (run_dir), not run again
    "old": ("old base (pre-fix)", []),
    "base": ("base", ["--sizing", "fillable", "--no-holes"]),
    "hang": ("hang", ["--sizing", "fillable", *HANG]),
    "usable": ("usable + hang", ["--sizing", "usable", *HANG]),
    "usable90": ("usable 0.9 + hang", ["--sizing", "usable", "--fill-slack", "0.9", *HANG]),
    "usable80": ("usable 0.8 + hang", ["--sizing", "usable", "--fill-slack", "0.8", *HANG]),
}


def arm_dir(out: Path, arm: str, set_number: str, obj: str, runs: Path) -> Path:
    return run_dir(runs, set_number, obj) if arm == "old" else out / "sweep" / arm / set_number / obj


def arm_config(arm: str, obj: str, **changes) -> AltConfig:
    flags = ARMS[arm][1]
    sizing = flags[flags.index("--sizing") + 1] if "--sizing" in flags else "fillable"
    slack = float(flags[flags.index("--fill-slack") + 1]) if "--fill-slack" in flags else 1.0
    return AltConfig(shape="brickgpt:" + STRUCTURES[obj], sizing=sizing, fill_slack=slack, **changes)


def same_target(arm: str, other: str, set_number: str, obj: str) -> bool:
    """Whether two arms' targets (and so, with the same flags, their candidates) are the same for this pair."""
    source = load_source(set_number)
    a, _ = sized_target(source, arm_config(arm, obj))
    b, _ = sized_target(source, arm_config(other, obj))
    return a.mask.shape == b.mask.shape and bool((a.mask == b.mask).all())


def step_sweep(args: argparse.Namespace) -> None:
    """The arms' pipeline runs, one after another (each on ``--workers``); resumable (the pipeline's cache). The
    usable arm is run only where usable sizing changes the target: elsewhere it is the hang arm."""
    for arm in ARMS:
        if arm == "old":
            continue
        for obj in OBJECTS:
            for set_number in SWEEP_SETS:
                out = arm_dir(args.out, arm, set_number, obj, args.runs)
                if arm == "usable" and same_target("usable", "hang", set_number, obj):
                    print(f"{arm} {obj} {set_number}: same target as hang, not run", flush=True)
                    continue
                stats = out / "stats.json"
                if stats.exists() and json.loads(stats.read_text(encoding="utf-8"))["requested"] == args.n:
                    continue
                argv = [set_number, "--shape", "brickgpt:" + STRUCTURES[obj], "--n", str(args.n), "--k", "1",
                        "--workers", str(args.workers), "--out", str(out), *ARMS[arm][1]]
                print(f"{arm} {obj} {set_number}: python -m brickwfc.alt {' '.join(argv)}", flush=True)
                pipeline_main(argv)


def sweep_cell(args: argparse.Namespace, arm: str, set_number: str, obj: str) -> dict | None:
    """One arm x pair: completeness of the valid candidates and the selected build, and the run's numbers."""
    directory = arm_dir(args.out, arm, set_number, obj, args.runs)
    alias = None
    if arm == "usable" and not (directory / "stats.json").exists() and same_target("usable", "hang", set_number, obj):
        alias, directory = "hang", arm_dir(args.out, "hang", set_number, obj, args.runs)
    if not (directory / "stats.json").exists():
        return None
    key, stats, candidates = load_run(directory)
    mask = key_mask(key)
    source = load_source(set_number)
    config_arm = "base" if arm == "old" else arm
    _, sizing = sized_target(source, arm_config(config_arm, obj))
    obj_target, _ = sized_target(source, arm_config(config_arm, obj, supports=False))
    valid = [c for c in candidates if c.valid]
    rows = {c.seed: completeness(occupancy(c.placed, mask.shape), mask) for c in valid}
    selected = stats["selected"][0] if stats["selected"] else None
    cell = {"arm": arm, "set": set_number, "object": obj, "run": directory.as_posix(), "same_as": alias,
            "target_cells": int(mask.sum()), "object_cells": int(obj_target.mask.sum()), "sizing": sizing,
            "valid": len(valid), "candidates": len(candidates),
            "s_per_candidate": stats["generation_cpu_s"] / max(1, len(candidates)),
            "complete": sum(complete(r) for r in rows.values())}
    for name in ("fill_pct", "holes", "largest_hole", "surface_pct"):
        cell[f"mean_{name}"] = mean([r[name] for r in rows.values()])
    if selected is not None:
        chosen = next(c for c in candidates if c.seed == selected["seed"])
        cell["selected"] = rows[selected["seed"]] | {"seed": selected["seed"], "parts": selected["parts"],
                                                     "utilization_pct": selected["utilization_pct"],
                                                     "clutch": selected["clutch"]}
        cell["selected"]["complete"] = complete(cell["selected"])
        cell["preview"] = (directory / selected["png"]).as_posix()
        path = args.out / "sweep_missing" / f"{obj}_{set_number}_{arm}.png"
        cell["missing_png"] = missing_png(chosen.placed, mask, path).as_posix()
    return cell


def sweep_report(cells: list[dict]) -> str:
    lines = ["| object | set | arm | target cells | object cells | valid | complete | fill % (sel / mean) | "
             "holes (sel / mean) | largest hole (sel / mean) | surface % (sel / mean) | parts (sel) | used % (sel) | "
             "s / candidate |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c in cells:
        s = c.get("selected", {})
        title = ARMS[c["arm"]][0] + (f" (= {ARMS[c['same_as']][0]})" if c["same_as"] else "")
        lines.append(
            f"| {c['object']} | {c['set']} | {title} | {c['target_cells']} | {c['object_cells']} | "
            f"{c['valid']}/{c['candidates']} | {c['complete']} | "
            f"{s.get('fill_pct', math.nan):.1f} / {c['mean_fill_pct']:.1f} | "
            f"{s.get('holes', 0)} / {c['mean_holes']:.1f} | {s.get('largest_hole', 0)} / {c['mean_largest_hole']:.0f} | "
            f"{s.get('surface_pct', math.nan):.1f} / {c['mean_surface_pct']:.1f} | {s.get('parts', 0)} | "
            f"{s.get('utilization_pct', math.nan):.0f} | {c['s_per_candidate']:.1f} |")
    return "\n".join(lines)


def sweep_sheets(cells: list[dict], out: Path) -> list[Path]:
    """Two sheets, pairs as rows and arms as columns: the selected builds' previews, and their missing maps."""
    from PIL import Image

    by_key = {(c["object"], c["set"], c["arm"]): c for c in cells}
    blank = out / "sweep_missing" / "none.png"
    blank.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), (255, 255, 255)).save(blank)
    paths = []
    for which, name in (("preview", "sweep_previews.png"), ("missing_png", "sweep_missing.png")):
        images, labels = [], []
        for obj in OBJECTS:
            for set_number in SWEEP_SETS:
                for arm in ARMS:
                    c = by_key.get((obj, set_number, arm))
                    if c is None or which not in c:
                        images.append(blank)
                        labels.append(f"{obj} {set_number}\n{ARMS[arm][0]}: no run")
                        continue
                    s = c["selected"]
                    images.append(Path(c[which]))
                    labels.append(f"{obj} {set_number}, {ARMS[arm][0]}\nfill {s['fill_pct']:.0f}%, surface "
                                  f"{s['surface_pct']:.0f}%\nlargest hole {s['largest_hole']}, {s['parts']} parts")
        path = out / name
        labeled_sheet(images, labels, path, columns=len(ARMS), width=500)
        paths.append(path)
    return paths


def step_sweep_report(args: argparse.Namespace) -> None:
    cells = [c for obj in OBJECTS for set_number in SWEEP_SETS for arm in ARMS
             if (c := sweep_cell(args, arm, set_number, obj)) is not None]
    (args.out / "sweep.json").write_text(json.dumps(cells, indent=2), encoding="utf-8")
    sheets = sweep_sheets(cells, args.out)
    text = sweep_report(cells) + "\n"
    (args.out / "sweep.md").write_text(text, encoding="utf-8")
    print(text)
    print("wrote sweep.json, sweep.md, " + ", ".join(p.name for p in sheets))


def step_old_vs_base(args: argparse.Namespace) -> None:
    """Old (cached, pre-fix) vs fixed base on the sweep's pairs, same seeds and targets: the valid candidates' mean
    fill +- SE, the difference in SE units, valid counts. A pair whose base target has changed since (the 5891-1
    chair: the moment key, 49d5739) takes its base run from ``sweep_premoment/base``, run before that change."""
    rows = []
    for obj in OBJECTS:
        for set_number in SWEEP_SETS:
            base = args.out / "sweep_premoment" / "base" / set_number / obj
            if not base.exists():
                base = arm_dir(args.out, "base", set_number, obj, args.runs)
            row, masks = {"object": obj, "set": set_number}, []
            for arm, directory in (("old", run_dir(args.runs, set_number, obj)), ("base", base)):
                key, _, candidates = load_run(directory)
                mask = key_mask(key)
                masks.append(mask)
                fills = np.array([completeness(occupancy(c.placed, mask.shape), mask)["fill_pct"]
                                  for c in candidates if c.valid])
                row[arm] = {"run": directory.as_posix(), "valid": len(fills), "n": len(candidates),
                            "mean": float(fills.mean()), "se": float(fills.std(ddof=1) / math.sqrt(len(fills)))}
            if masks[0].shape != masks[1].shape or not (masks[0] == masks[1]).all():
                raise SystemExit(f"{obj} {set_number}: the old and base runs have different targets")
            row["delta"] = row["base"]["mean"] - row["old"]["mean"]
            row["z"] = row["delta"] / math.hypot(row["base"]["se"], row["old"]["se"])
            rows.append(row)
            print(f"{obj} {set_number}: {row['old']['mean']:.1f} -> {row['base']['mean']:.1f} ({row['z']:+.1f} SE)",
                  flush=True)
    (args.out / "old_vs_base.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.complete", description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=Path, default=Path("out"), help="folder holding m12b_sizing_fig and m12b_sizing")
    parser.add_argument("--out", type=Path, default=Path("out/m12b_complete"))
    parser.add_argument("--steps", nargs="+", default=["final"], choices=["final", "trace", "report", "sweep", "sweep-report", "holes", "old-vs-base"])
    parser.add_argument("--per-pair", type=int, default=10, help="trace: builds replayed per pair (selected first)")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--n", type=int, default=50, help="sweep: candidates per run")
    parser.add_argument("--arm", default="usable80", help="holes: the sweep arm whose selected builds to diagnose")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    if "final" in args.steps:
        step_final(args)
    if "trace" in args.steps:
        step_trace(args)
    if "report" in args.steps:
        step_report(args)
    if "sweep" in args.steps:
        step_sweep(args)
    if "sweep-report" in args.steps:
        step_sweep_report(args)
    if "holes" in args.steps:
        step_holes(args)
    if "old-vs-base" in args.steps:
        step_old_vs_base(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
