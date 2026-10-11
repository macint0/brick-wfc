"""M12b completeness: how complete the builds are, and why target cells stay empty.

    python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps final
    python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps trace --per-pair 10 --workers 5
    python -m brickwfc.experiments.complete --out out/m12b_complete --steps sweep sweep-report --arms ...

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

``sweep`` runs the arms (``ARMS``; ``--arms`` picks some) on the 9 sweep pairs; ``sweep-report`` writes their
table, previews and missing maps (``--report-name``, default ``sweep``). Besides completeness it reports the
selected build's clutch, the share of the target's tip cells filled (``tip_cells``: the far ends of the low
structure, a chair's casters, a table's feet, a car's wheel corners) and how many candidates stalled (``STALL_FILL``:
fill under half the target; single-seed growth that could not get across) with the layers their builds top out at.
Where a report holds both arms of a ``COMPARE`` pair, it also compares their selected builds metric by metric
(``compare_report``; same seeds, and a column says whether the two targets are the same).

``size-report`` reads the size arms (``SIZE_FAMILIES``: creserve and the default from slack 1.0 down to 0.6): per pair,
family and slack the valid candidates' mean completeness, the selected build's, the candidates meeting the bar and the
time per candidate; per pair and family the largest slack at which any candidate, and the selected build, is complete
(``size.md``, ``size.json``, ``size_sheet_<family>.png``); complete candidates go to ``complete_candidates/``.

Completeness is counted under both bars (``complete``; ``features.Bar``): the volume bar (fill, largest hole, surface)
and the surface bar (surface share and largest surface hole: interior cells are invisible), side by side in every
report. The hollow arms (``HOLLOW_ARMS``: creserve's flags with a shell cut from the solid target at the solid's scale,
``--hollow-scale solid``, selected on the surface bar) are judged on the surface; their ``HOLLOW_COMPARE`` pairs against
creserve compare different targets (the same object, its interior removed).

``hollow-sizing`` (no generation) sizes creserve's and creserve80's solid targets on the 9 pairs, cuts a shell of each
thickness in ``HOLLOW_THICKNESSES`` from them at their scale, and reports per pair the cells kept, the exposed cells
(equal to the solid's when the void is enclosed), the part budget against the shell's cells and the parts that fit
nowhere in the shell (``hollow_sizing.md``, ``.json``; one json per pair under ``hollow_sizing/``, so it resumes).
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import math
import re
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import fields, replace
from pathlib import Path
from typing import Sequence

import numpy as np
from scipy import ndimage

from brickwfc.alt.candidates import Candidate, Context, d2_builder
from brickwfc.alt.features import Bar, exposed, largest_component, occupancy
from brickwfc.alt.inputs import DATA_DIR, learned_style, load_source
from brickwfc.alt.pipeline import (AltConfig, cache_key, make_context, make_target, resolve, scaled_target, sized_target,
                                   solid_scale_shell)
from brickwfc.alt.pipeline import main as pipeline_main
from brickwfc.bricks.bottomup import SMALL_CELLS, BottomUpBuilder, _FitMap
from brickwfc.bricks.build import placed_colors, slope_profiles
from brickwfc.bricks.inventory import fits_inside, part_cells, target_volume
from brickwfc.bricks.parts import CATALOG, PlacedPart, extract_parts, shapes_of
from brickwfc.bricks.shapes import overhang_moment, surface, thinnest_section
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
        "largest_surface_hole": largest_component(missing & skin),
        "unfilled_on_surface_pct": 100 * float((missing & skin).sum() / unfilled) if unfilled else 0.0,
    }


BAR = Bar()  # the default thresholds (``features.Bar``), as in the pipeline


def complete(row: dict, bar: str = "volume") -> bool:
    """Whether a build (a ``completeness`` row, in %) meets the bar (cf, 2026-10-10; ``features.Bar``). ``volume``:
    fill >= 97%, no hole over 4 cells, surface >= 98%; ``surface`` (M12c, for hollow targets: interior cells are
    invisible): surface >= 98%, no surface hole over 4 cells."""
    if bar == "surface":
        return row["surface_pct"] >= 100 * BAR.surface and row["largest_surface_hole"] <= BAR.largest_hole
    return (row["fill_pct"] >= 100 * BAR.fill and row["largest_hole"] <= BAR.largest_hole
            and row["surface_pct"] >= 100 * BAR.surface)


def bars_text(volume: object, surface: object) -> str:
    """A count or flag under the volume bar and the surface bar, side by side."""
    def text(value: object) -> str:
        return ("yes" if value else "no") if isinstance(value, bool) else str(value)

    return f"{text(volume)} / {text(surface)}"


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


def traced_replay(directory: str, seed: int) -> tuple[Context, BottomUpBuilder, Trace, Candidate, np.ndarray]:
    """One cached candidate replayed with a trace, checked identical to the cached build: its context, the builder,
    the trace, the cached candidate and its filled cells."""
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
    return context, builder, trace, cached, final


def replay_final(directory: str, seed: int) -> dict:
    """Replay one cached candidate with a trace; why its unfilled target cells stayed empty, and its holes."""
    context, builder, trace, cached, final = traced_replay(directory, seed)
    mask = context.mask
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
STRUCTURES = {  # BrickGPT test-split structures: the median-size one of each of the six most common categories
    # (experiments/brickgpt.py: pick_objects; results/m12b_brickgpt.md)
    "chair": "a712684f-8e79-4ecd-81de-11aef42b50d4", "table": "858f0955-846e-4138-84d9-df66b66eddc2",
    "car": "4b15b71c-f400-4e54-a118-f0c2afba6e17", "sofa": "d1137e5f-7455-4287-9369-eed134020de7",
    "vessel": "5c5f88b6-9e68-4df9-bf09-f8e7c2b38c47", "bench": "365bf4bd-7e5f-4c53-aac5-77859e9e796b"}
PAIRS = tuple((s, o) for o in OBJECTS for s in SWEEP_SETS)  # the 9 sweep pairs (set, object), objects outer


def load_pairs(path: Path | None) -> tuple[tuple[str, str], ...]:
    """(set, object) pairs from a JSON file, or ``PAIRS`` without one. The file holds either ``"pairs"``: a list of
    [set, object], or ``"sets"`` and ``"objects"``: every pair of them, objects outer (as ``PAIRS``). Objects are keys
    of ``STRUCTURES``; sets are set numbers ("6378-1"); a pair may appear once."""
    if path is None:
        return PAIRS
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "pairs" in data:
        if "sets" in data or "objects" in data:
            raise ValueError(f"{path}: give either pairs or sets and objects, not both")
        pairs = [tuple(pair) for pair in data["pairs"]]
    else:
        pairs = [(s, o) for o in data["objects"] for s in data["sets"]]
    if not pairs:
        raise ValueError(f"{path}: no pairs")
    for pair in pairs:
        if len(pair) != 2 or not all(isinstance(x, str) for x in pair):
            raise ValueError(f"{path}: a pair is [set, object], not {list(pair)}")
        set_number, obj = pair
        if obj not in STRUCTURES:
            raise ValueError(f"{path}: unknown object {obj!r} (known: {', '.join(STRUCTURES)})")
        if not re.fullmatch(r"\d+-\d+", set_number):
            raise ValueError(f"{path}: {set_number!r} is not a set number like 6378-1")
    if len(set(pairs)) < len(pairs):
        raise ValueError(f"{path}: a pair appears twice")
    return tuple(pairs)


def pair_order(cells: Sequence[dict]) -> list[tuple[str, str]]:
    """The (set, object) pairs of ``cells`` in the order they first appear (the order the steps built them in)."""
    return list(dict.fromkeys((c["set"], c["object"]) for c in cells))
HANG = ["--holes", "--hang"]
ARMS = {  # name: (title, pipeline flags; explicit, since the defaults changed after the sweep); "old" is the
    # cached pre-fix run (run_dir), not run again
    "old": ("old base (pre-fix)", []),
    "base": ("base", ["--sizing", "fillable", "--no-holes"]),
    "hang": ("hang", ["--sizing", "fillable", *HANG]),
    "usable": ("usable + hang", ["--sizing", "usable", *HANG]),
    "usable90": ("usable 0.9 + hang", ["--sizing", "usable", "--fill-slack", "0.9", *HANG]),
    "usable80": ("usable 0.8 + hang", ["--sizing", "usable", "--fill-slack", "0.8", *HANG]),
    # The connected growth order (bricks/bottomup.py) on the usable targets, to join the arms above.
    "connected": ("connected + usable + hang", ["--sizing", "usable", *HANG, "--order", "connected"]),
    "connected90": ("connected + usable 0.9 + hang",
                    ["--sizing", "usable", "--fill-slack", "0.9", *HANG, "--order", "connected"]),
    "connected80": ("connected + usable 0.8 + hang",
                    ["--sizing", "usable", "--fill-slack", "0.8", *HANG, "--order", "connected"]),
    # small parts kept for the hole pass (M12b completeness, cf 2026-10-10), at the defaults (usable 1.0 + hang) and
    # at slack 0.8; compared with "usable" and "usable80"
    "reserve": ("reserve-small", ["--sizing", "usable", *HANG, "--reserve-small"]),
    "small1": ("small-last 1", ["--sizing", "usable", *HANG, "--small-last", "1"]),
    "small2": ("small-last 2", ["--sizing", "usable", *HANG, "--small-last", "2"]),
    "reserve80": ("reserve-small 0.8", ["--sizing", "usable", "--fill-slack", "0.8", *HANG, "--reserve-small"]),
    "small1_80": ("small-last 1, 0.8", ["--sizing", "usable", "--fill-slack", "0.8", *HANG, "--small-last", "1"]),
    "small2_80": ("small-last 2, 0.8", ["--sizing", "usable", "--fill-slack", "0.8", *HANG, "--small-last", "2"]),
    # connected growth with the small parts kept (cf, 2026-10-10): each pairs with the arm above with the same option
    # and with the connected arm of its slack
    "creserve": ("connected + reserve-small", ["--sizing", "usable", *HANG, "--order", "connected", "--reserve-small"]),
    "csmall1": ("connected + small-last 1",
                ["--sizing", "usable", *HANG, "--order", "connected", "--small-last", "1"]),
    "csmall2": ("connected + small-last 2",
                ["--sizing", "usable", *HANG, "--order", "connected", "--small-last", "2"]),
    "creserve80": ("connected + reserve-small, 0.8",
                   ["--sizing", "usable", "--fill-slack", "0.8", *HANG, "--order", "connected", "--reserve-small"]),
    "csmall1_80": ("connected + small-last 1, 0.8",
                   ["--sizing", "usable", "--fill-slack", "0.8", *HANG, "--order", "connected", "--small-last", "1"]),
    "csmall2_80": ("connected + small-last 2, 0.8",
                   ["--sizing", "usable", "--fill-slack", "0.8", *HANG, "--order", "connected", "--small-last", "2"]),
    # size below 0.8 with the reserve inside connected growth (cf, 2026-10-11: the largest size the set can complete),
    # with the default at the same slack as the control
    "creserve90": ("connected + reserve-small, 0.9",
                   ["--sizing", "usable", "--fill-slack", "0.9", *HANG, "--order", "connected", "--reserve-small"]),
    "creserve70": ("connected + reserve-small, 0.7",
                   ["--sizing", "usable", "--fill-slack", "0.7", *HANG, "--order", "connected", "--reserve-small"]),
    "creserve60": ("connected + reserve-small, 0.6",
                   ["--sizing", "usable", "--fill-slack", "0.6", *HANG, "--order", "connected", "--reserve-small"]),
    "usable70": ("usable 0.7 + hang", ["--sizing", "usable", "--fill-slack", "0.7", *HANG]),
    "usable60": ("usable 0.6 + hang", ["--sizing", "usable", "--fill-slack", "0.6", *HANG]),
    # hollow targets judged on the surface (cf, 2026-10-10 night: interior cells are invisible): creserve's flags, a
    # 1- or 2-cell shell with internal pillars cut from creserve's solid target at its scale (``--hollow-scale solid``:
    # the same object, the interior's parts left over; results/m12c_hollow_sizing.md) and the surface bar at selection
    **{f"hollow{t}{suffix}": (f"connected + reserve-small{title}, hollow {t} at the solid's scale, surface bar",
                              ["--sizing", "usable", *slack, *HANG, "--order", "connected", "--reserve-small",
                               "--hollow", str(t), "--hollow-scale", "solid", "--bar", "surface"])
       for suffix, title, slack in (("", "", []), ("_80", ", 0.8", ["--fill-slack", "0.8"])) for t in (1, 2)},
    # connected growth that stalls is grown again from the next ground region (M12c, results/m12c_stall_6378_chair.md):
    # creserve at each slack + --regrow; a pair whose growth never stalls builds the same candidates as creserve
    **{f"cregrow{suffix}": (f"connected + reserve-small{title}, regrow",
                            ["--sizing", "usable", *slack, *HANG, "--order", "connected", "--reserve-small", "--regrow"])
       for suffix, title, slack in (("", "", []), ("80", ", 0.8", ["--fill-slack", "0.8"]),
                                    ("70", ", 0.7", ["--fill-slack", "0.7"]), ("60", ", 0.6", ["--fill-slack", "0.6"]))},
}
HOLLOW_ARMS = ("hollow1", "hollow2", "hollow1_80", "hollow2_80")
REGROW_COMPARE = (("creserve", "cregrow"), ("creserve80", "cregrow80"), ("creserve70", "cregrow70"),
                  ("creserve60", "cregrow60"))  # same targets, same seeds
HOLLOW_COMPARE = (("creserve", "hollow1"), ("creserve", "hollow2"), ("hollow2", "hollow1"),  # the same object, less
                  ("creserve80", "hollow1_80"), ("creserve80", "hollow2_80"), ("hollow2_80", "hollow1_80"))
SIZE_COMPARE = (  # size: the default vs creserve at each slack, then creserve from one slack to the next smaller
    ("usable", "creserve"), ("usable90", "creserve90"), ("usable80", "creserve80"), ("usable70", "creserve70"),
    ("usable60", "creserve60"), ("creserve", "creserve90"), ("creserve90", "creserve80"), ("creserve", "creserve80"),
    ("creserve80", "creserve70"), ("creserve70", "creserve60"))
SMALL_ARMS = ("usable", "reserve", "small1", "small2", "usable80", "reserve80", "small1_80", "small2_80")
COMPARE = (("usable", "connected"), ("usable90", "connected90"), ("usable80", "connected80"),
           # connected growth with the small parts kept: vs the same option in random order, and vs plain connected
           ("reserve", "creserve"), ("small1", "csmall1"), ("small2", "csmall2"), ("reserve80", "creserve80"),
           ("small1_80", "csmall1_80"), ("small2_80", "csmall2_80"), ("connected", "creserve"),
           ("connected", "csmall1"), ("connected", "csmall2"), ("connected80", "creserve80"),
           ("connected80", "csmall1_80"), ("connected80", "csmall2_80"),
           # and vs the default at their slack (cf, 2026-10-10: the adoption rule's comparison)
           ("usable", "creserve"), ("usable", "csmall1"), ("usable", "csmall2"), ("usable80", "creserve80"),
           ("usable80", "csmall1_80"), ("usable80", "csmall2_80"))
COMPARE += tuple(pair for pair in SIZE_COMPARE + HOLLOW_COMPARE + REGROW_COMPARE if pair not in COMPARE)
CONNECTED_SMALL_ARMS = ("connected", "creserve", "csmall1", "csmall2", "connected80", "creserve80", "csmall1_80",
                        "csmall2_80")
STALL_FILL = 50.0  # a candidate under this fill % of its target stalled
TIP_HEIGHT = 1 / 3  # tip cells: in the lowest third of the target's height ...
TIP_RADIUS = 2 / 3  # ... and at least this share of the farthest such cell's distance from their centroid


def tip_cells(mask: np.ndarray) -> np.ndarray:
    """The target's tip cells: among its cells in the lowest ``TIP_HEIGHT`` of its height, those at least
    ``TIP_RADIUS`` of the largest horizontal distance from their centroid (casters, feet, wheel corners)."""
    ys = np.nonzero(mask.any(axis=(1, 2)))[0]
    low = mask.copy()
    low[ys.min() + max(1, round(TIP_HEIGHT * (ys.max() - ys.min() + 1))):] = False
    cells = np.argwhere(low)
    centre = cells[:, 1:].mean(axis=0)
    distance = np.hypot(*(cells[:, 1:] - centre).T)
    tips = np.zeros_like(mask)
    far = cells[distance >= TIP_RADIUS * distance.max()]
    tips[tuple(far.T)] = True
    return tips


def tips_filled_pct(filled: np.ndarray, tips: np.ndarray) -> float:
    return 100 * float((filled & tips).sum() / tips.sum()) if tips.any() else math.nan


def arm_dir(out: Path, arm: str, set_number: str, obj: str, runs: Path) -> Path:
    return run_dir(runs, set_number, obj) if arm == "old" else out / "sweep" / arm / set_number / obj


def arm_config(arm: str, obj: str, **changes) -> AltConfig:
    """The arm's target settings (sizing, slack, hollow shell) and the bar it is selected on."""
    flags = ARMS[arm][1]
    sizing = flags[flags.index("--sizing") + 1] if "--sizing" in flags else "fillable"
    slack = float(flags[flags.index("--fill-slack") + 1]) if "--fill-slack" in flags else 1.0
    shell = int(flags[flags.index("--hollow") + 1]) if "--hollow" in flags else 0
    scale = flags[flags.index("--hollow-scale") + 1] if "--hollow-scale" in flags else "shell"
    bar = flags[flags.index("--bar") + 1] if "--bar" in flags else "volume"
    return AltConfig(shape="brickgpt:" + STRUCTURES[obj], sizing=sizing, fill_slack=slack, hollow=shell,
                     hollow_scale=scale, bar=bar, **changes)


def target_hash(mask: np.ndarray) -> str:
    """A short fingerprint of a target mask (its shape and cells), to tell whether two runs built the same target."""
    return hashlib.sha256(repr(mask.shape).encode() + np.packbits(mask).tobytes()).hexdigest()[:16]


def same_target(arm: str, other: str, set_number: str, obj: str) -> bool:
    """Whether two arms' targets (and so, with the same flags, their candidates) are the same for this pair."""
    source = load_source(set_number)
    a, _ = sized_target(source, arm_config(arm, obj))
    b, _ = sized_target(source, arm_config(other, obj))
    return a.mask.shape == b.mask.shape and bool((a.mask == b.mask).all())


def step_sweep(args: argparse.Namespace) -> None:
    """The arms' pipeline runs, one after another (each on ``--workers``); resumable (the pipeline's cache). The
    usable arm is run only where usable sizing changes the target: elsewhere it is the hang arm."""
    for arm in args.arms or ARMS:
        if arm == "old":
            continue
        for set_number, obj in args.pairs:
            out = arm_dir(args.out, arm, set_number, obj, args.runs)
            if arm == "usable" and same_target("usable", "hang", set_number, obj):
                print(f"{arm} {obj} {set_number}: same target as hang, not run", flush=True)
                continue
            stats = out / "stats.json"
            if stats.exists() and json.loads(stats.read_text(encoding="utf-8"))["requested"] == args.n:
                continue
            target, _ = sized_target(load_source(set_number), arm_config(arm, obj))
            print(f"{arm} {obj} {set_number}: slack {arm_config(arm, obj).fill_slack}, "
                  f"target cells {int(target.mask.sum())}", flush=True)
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
    tips = tip_cells(mask)
    rows = {}
    for c in valid:
        filled = occupancy(c.placed, mask.shape)
        rows[c.seed] = completeness(filled, mask) | {"tips_pct": tips_filled_pct(filled, tips)}
    selected = stats["selected"][0] if stats["selected"] else None
    stall_tops = Counter(top_layer(c.placed) for c in candidates
                         if 100 * (occupancy(c.placed, mask.shape) & mask).sum() < STALL_FILL * mask.sum())
    cell = {"arm": arm, "set": set_number, "object": obj, "run": directory.as_posix(), "same_as": alias,
            "target_cells": int(mask.sum()), "target_hash": target_hash(mask), "object_cells": int(obj_target.mask.sum()),
            "sizing": sizing,
            "valid": len(valid), "candidates": len(candidates),
            "s_per_candidate": stats["generation_cpu_s"] / max(1, len(candidates)),
            "bar": arm_config(config_arm, obj).bar,  # the bar the run selected on
            "complete": sum(complete(r) for r in rows.values()),
            "complete_seeds": sorted(seed for seed, r in rows.items() if complete(r)),
            "complete_surface": sum(complete(r, "surface") for r in rows.values()),
            "complete_surface_seeds": sorted(seed for seed, r in rows.items() if complete(r, "surface")),
            "tip_cells": int(tips.sum()),
            "stalled": sum(stall_tops.values()), "stalled_valid": sum(r["fill_pct"] < STALL_FILL for r in rows.values()),
            "stall_tops": sorted(stall_tops.items())}
    for name in ("fill_pct", "holes", "largest_hole", "surface_pct", "largest_surface_hole", "tips_pct"):
        cell[f"mean_{name}"] = mean([r[name] for r in rows.values()])
    if selected is not None:
        chosen = next(c for c in candidates if c.seed == selected["seed"])
        cell["selected"] = rows[selected["seed"]] | {"seed": selected["seed"], "parts": selected["parts"],
                                                     "utilization_pct": selected["utilization_pct"],
                                                     "clutch": selected["clutch"], "judge": selected["judge"]}
        cell["selected"]["complete"] = complete(cell["selected"])
        cell["selected"]["complete_surface"] = complete(cell["selected"], "surface")
        cell["preview"] = (directory / selected["png"]).as_posix()
        path = args.out / "sweep_missing" / f"{obj}_{set_number}_{arm}.png"
        cell["missing_png"] = missing_png(chosen.placed, mask, path).as_posix()
    return cell


def sweep_report(cells: list[dict]) -> str:
    lines = ["| object | set | arm | target cells | object cells | valid | complete (vol / surf) | "
             "selected complete (vol / surf) | fill % (sel / mean) | holes (sel / mean) | largest hole (sel / mean) | "
             "surface % (sel / mean) | largest surface hole (sel / mean) | parts (sel) | used % (sel) | judge (sel) | "
             "s / candidate | tips filled % (sel / mean) | clutch (sel) | stalled (top layers) |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c in cells:
        s = c.get("selected", {})
        title = ARMS[c["arm"]][0] + (f" (= {ARMS[c['same_as']][0]})" if c["same_as"] else "")
        lines.append(
            f"| {c['object']} | {c['set']} | {title} | {c['target_cells']} | {c['object_cells']} | "
            f"{c['valid']}/{c['candidates']} | {bars_text(c['complete'], c.get('complete_surface', 0))} | "
            f"{bars_text(s.get('complete', False), s.get('complete_surface', False))} | "
            f"{s.get('fill_pct', math.nan):.1f} / {c['mean_fill_pct']:.1f} | "
            f"{s.get('holes', 0)} / {c['mean_holes']:.1f} | {s.get('largest_hole', 0)} / {c['mean_largest_hole']:.0f} | "
            f"{s.get('surface_pct', math.nan):.1f} / {c['mean_surface_pct']:.1f} | "
            f"{s.get('largest_surface_hole', 0)} / {c.get('mean_largest_surface_hole', math.nan):.0f} | "
            f"{s.get('parts', 0)} | "
            f"{s.get('utilization_pct', math.nan):.0f} | {s.get('judge', math.nan):.4f} | {c['s_per_candidate']:.1f} | "
            f"{s.get('tips_pct', math.nan):.0f} / {c.get('mean_tips_pct', math.nan):.0f} | "
            f"{s.get('clutch', math.nan):.0f} | {c.get('stalled', 0)}{stall_tops_text(c.get('stall_tops', []))} |")
    return "\n".join(lines)


def top_layer(placed: Sequence[PlacedPart]) -> int:
    """The highest layer a build reaches (-1 if empty)."""
    return max((cell[0] for p in placed for cell in p.cells()), default=-1)


def stall_tops_text(tops: Sequence[Sequence[int]]) -> str:
    if not tops:
        return ""
    return " (" + ", ".join(f"{y}" if n == 1 else f"{y}: {n}" for y, n in tops) + ")"


COMPARED = (  # (label, value of a sweep cell, higher is better, format)
    ("fill %", lambda c: c["selected"]["fill_pct"], True, ".1f"),
    ("holes", lambda c: c["selected"]["holes"], False, ".0f"),
    ("largest hole", lambda c: c["selected"]["largest_hole"], False, ".0f"),
    ("surface %", lambda c: c["selected"]["surface_pct"], True, ".1f"),
    ("largest surface hole", lambda c: c["selected"]["largest_surface_hole"], False, ".0f"),
    ("tips filled %", lambda c: c["selected"]["tips_pct"], True, ".0f"),
    ("valid", lambda c: c["valid"], True, ".0f"),
    ("s / candidate", lambda c: c["s_per_candidate"], False, ".1f"),
)


def compare_report(cells: list[dict], pairs: Sequence[tuple[str, str]] = COMPARE) -> str:
    """Per pair and per (base, arm) in ``pairs`` present in ``cells``: whether the two runs had the same target
    (``target_hash``; "-" if unknown), the selected builds' metrics, base -> arm, marked + where the arm is better,
    - where worse, = where equal; and the count of each. Where the targets differ (another slack, a hollow), the
    metrics are each against its own target."""
    by_key = {(c["arm"], c["object"], c["set"]): c for c in cells}
    lines = ["| object | set | base -> arm | same target | " + " | ".join(name for name, *_ in COMPARED)
             + " | complete (sel, vol / surf) | stalled | better / worse |",
             "|---|---|---|---|" + "---:|" * (len(COMPARED) + 3)]
    for base, arm in pairs:
        for set_number, obj in pair_order(cells):
            a, b = by_key.get((base, obj, set_number)), by_key.get((arm, obj, set_number))
            if a is None or b is None or "selected" not in a or "selected" not in b:
                continue
            row, better, worse = [], 0, 0
            for _, value, higher, spec in COMPARED:
                x, y = value(a), value(b)
                if math.isclose(x, y, abs_tol=1e-9):
                    mark = "="
                elif (y > x) == higher:
                    mark, better = "+", better + 1
                else:
                    mark, worse = "-", worse + 1
                row.append(f"{x:{spec}} -> {y:{spec}} {mark}")
            same = ("-" if a.get("target_hash") is None or b.get("target_hash") is None
                    else "yes" if a["target_hash"] == b["target_hash"] else "no")
            lines.append(f"| {obj} | {set_number} | {ARMS[base][0]} -> {ARMS[arm][0]} | {same} | " + " | ".join(row)
                         + f" | {bars_text(int(a['selected']['complete']), int(a['selected']['complete_surface']))} -> "
                         f"{bars_text(int(b['selected']['complete']), int(b['selected']['complete_surface']))} | "
                         f"{a.get('stalled', 0)} -> {b.get('stalled', 0)} | {better} / {worse} |")
    return "\n".join(lines) if len(lines) > 2 else ""


def sweep_sheets(cells: list[dict], out: Path, arms: Sequence[str] = tuple(ARMS), name: str = "sweep") -> list[Path]:
    """Two sheets, pairs as rows and ``arms`` as columns: the selected builds' previews, and their missing maps."""
    from PIL import Image

    by_key = {(c["object"], c["set"], c["arm"]): c for c in cells}
    blank = out / "sweep_missing" / "none.png"
    blank.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), (255, 255, 255)).save(blank)
    paths = []
    for which, sheet in (("preview", f"{name}_previews.png"), ("missing_png", f"{name}_missing.png")):
        images, labels = [], []
        for set_number, obj in pair_order(cells):
            for arm in arms:
                c = by_key.get((obj, set_number, arm))
                if c is None or which not in c:
                    images.append(blank)
                    labels.append(f"{obj} {set_number}\n{ARMS[arm][0]}: no run")
                    continue
                s = c["selected"]
                images.append(Path(c[which]))
                labels.append(f"{obj} {set_number}, {ARMS[arm][0]}\nfill {s['fill_pct']:.0f}%, surface "
                              f"{s['surface_pct']:.0f}%\nlargest hole {s['largest_hole']} (surface "
                              f"{s['largest_surface_hole']}), {s['parts']} parts")
        path = out / sheet
        labeled_sheet(images, labels, path, columns=len(arms), width=500)
        paths.append(path)
    return paths


def step_sweep_report(args: argparse.Namespace) -> None:
    arms = args.arms or list(ARMS)
    cells = [c for set_number, obj in args.pairs for arm in arms
             if (c := sweep_cell(args, arm, set_number, obj)) is not None]
    name = args.report_name
    (args.out / f"{name}.json").write_text(json.dumps(cells, indent=2), encoding="utf-8")
    sheets = sweep_sheets(cells, args.out, arms, name)
    text = sweep_report(cells) + "\n"
    if compared := compare_report(cells):
        text += "\nSelected builds compared (same seeds; + the second arm better, - worse; each against its own target):\n\n"
        text += compared + "\n"
    (args.out / f"{name}.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote {name}.json, {name}.md, " + ", ".join(p.name for p in sheets))


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


# Small-part budget: cells only small parts can fill, against the set's small parts --------------------------

BUDGET_SLACKS = tuple(round(1.0 - 0.05 * i, 2) for i in range(9))  # 1.0 .. 0.6
BUDGET_ARMS = ("usable80", "reserve80")  # the diagnosed arms (holes_<arm>.json)


def shape_kernel(shape) -> np.ndarray:
    """A shape's cells in its bounding box (y, z, x), as ``inventory.fits_inside`` erodes with."""
    kernel = np.zeros((shape.size_y, shape.size_z, shape.size_x), dtype=bool)
    for dz, dx in shape.footprint:
        kernel[:, dz, dx] = True
    return kernel


def covered_by(mask: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """The cells of ``mask`` that some placement of ``kernel`` (any position, entirely inside ``mask``) covers. The
    kernel's bounding box must be tight, as a shape's is."""
    out = np.zeros_like(mask)
    if any(k > n for k, n in zip(kernel.shape, mask.shape)):
        return out
    span = tuple(n - k + 1 for n, k in zip(mask.shape, kernel.shape))  # positions of the kernel's corner
    offsets = [tuple(k) for k in np.argwhere(kernel)]
    fits = np.ones(span, dtype=bool)
    for y, z, x in offsets:
        fits &= mask[y:y + span[0], z:z + span[1], x:x + span[2]]
    for y, z, x in offsets:
        out[y:y + span[0], z:z + span[1], x:x + span[2]] |= fits
    return out


def is_small(name: str) -> bool:
    return part_cells(CATALOG[name]) <= SMALL_CELLS


def small_only(mask: np.ndarray, inventory: dict) -> np.ndarray:
    """The target cells no placement of a larger-than-``SMALL_CELLS`` part of the inventory covers inside the target
    (every orientation; the shape check only, as ``inventory.unusable``)."""
    covered = np.zeros_like(mask)
    for name in sorted({part for part, _ in inventory}):
        if not is_small(name):
            for shape in shapes_of([CATALOG[name]]):
                covered |= covered_by(mask, shape_kernel(shape))
    return mask & ~covered


def small_supply(inventory: dict) -> dict:
    """The inventory's small parts (at most ``SMALL_CELLS`` cells): count and cells."""
    small = {key: n for key, n in inventory.items() if is_small(key[0])}
    return {"parts": sum(small.values()), "cells": sum(n * part_cells(CATALOG[key[0]]) for key, n in small.items())}


def budget_targets() -> list[dict]:
    """Per sweep pair and fill slack (usable sizing): target cells and small-only cells, with the set's supply."""
    rows = []
    for obj in OBJECTS:
        for set_number in SWEEP_SETS:
            source = load_source(set_number)
            supply = small_supply(source.inventory)
            for slack in BUDGET_SLACKS:
                target, details = sized_target(source, AltConfig(shape="brickgpt:" + STRUCTURES[obj], sizing="usable",
                                                                 fill_slack=slack))
                rows.append({"object": obj, "set": set_number, "slack": slack, "target_cells": int(target.mask.sum()),
                             "small_only": int(small_only(target.mask, source.inventory).sum()),
                             "supply_cells": supply["cells"], "supply_parts": supply["parts"],
                             "left_out": details.get("left_out", {})})
                print(f"  {obj} {set_number} {slack}: {rows[-1]['target_cells']} cells, {rows[-1]['small_only']} "
                      f"small-only", flush=True)
    return rows


def replay_budget(directory: str, seed: int) -> dict:
    """One diagnosed build replayed: its empty cells that want a used-up small part, and where its small parts went,
    against the target's small-only cells."""
    context, builder, trace, cached, final = traced_replay(directory, seed)
    mask = context.mask
    cause, wanted = final_causes(builder, trace, mask)
    only = small_only(mask, context.inventory)
    want_small = [c for c, names in wanted.items() if any(is_small(name) for name in names)]
    placed_small = occupancy([p for p in cached.placed if is_small(p.shape.part.name)], mask.shape)
    return {"seed": seed, "target_cells": int(mask.sum()), "small_only": int(only.sum()),
            "unfilled": int((cause >= 0).sum()), "inventory": int((cause == FINAL_CAUSES.index("inventory")).sum()),
            "want_small": len(want_small), "want_small_in_small_only": sum(bool(only[c]) for c in want_small),
            "small_placed_cells": int(placed_small.sum()),
            "small_placed_in_small_only": int((placed_small & only).sum()),
            "supply_cells": small_supply(context.inventory)["cells"]}


def budget_report(result: dict) -> str:
    rows = result["targets"]
    slacks = sorted({r["slack"] for r in rows}, reverse=True)
    by = {(r["object"], r["set"], r["slack"]): r for r in rows}
    lines = ["Target cells / small-only cells (cells no placement of a part larger than "
             f"{SMALL_CELLS} cells in the set covers inside the target), usable sizing at each fill slack:", "",
             "| object | set | supply (cells) | " + " | ".join(f"{s:.2f}" for s in slacks) + " |",
             "|---|---|---:|" + "---:|" * len(slacks)]
    for obj in OBJECTS:
        for set_number in SWEEP_SETS:
            cells = [by[(obj, set_number, s)] for s in slacks]
            lines.append(f"| {obj} | {set_number} | {cells[0]['supply_cells']} | " +
                         " | ".join(f"{c['target_cells']} / {c['small_only']}" for c in cells) + " |")
    lines += ["", "Diagnosed builds: empty cells wanting a used-up small part, small parts placed (cells), and how many "
              "of either lie on small-only cells:", "",
              "| arm | object | set | small-only | unfilled | inventory | want a small part (on small-only) | "
              "small parts placed, cells (on small-only) | supply, cells |", "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in result.get("replays", []):
        lines.append(f"| {r['arm']} | {r['object']} | {r['set']} | {r['small_only']} | {r['unfilled']} | "
                     f"{r['inventory']} | {r['want_small']} ({r['want_small_in_small_only']}) | "
                     f"{r['small_placed_cells']} ({r['small_placed_in_small_only']}) | {r['supply_cells']} |")
    return "\n".join(lines)


def step_small_only(args: argparse.Namespace) -> None:
    """The small-part budget test (no generation): small-only cells per pair and slack, and the diagnosed builds'
    small-part demand replayed against them."""
    result = {"targets": budget_targets(), "replays": []}
    jobs = []
    for arm in BUDGET_ARMS:
        for r in json.loads((args.out / f"holes_{arm}.json").read_text(encoding="utf-8")):
            jobs.append((arm, r["object"], r["set"], arm_dir(args.out, arm, r["set"], r["object"], args.runs).as_posix(),
                         r["seed"]))
    with ProcessPoolExecutor(args.workers) if args.workers > 1 else InlineExecutor() as pool:
        futures = [(arm, obj, set_number, pool.submit(replay_budget, directory, seed))
                   for arm, obj, set_number, directory, seed in jobs]
        for arm, obj, set_number, future in futures:  # in job order
            result["replays"].append({"arm": arm, "object": obj, "set": set_number} | future.result())
            print(f"  {arm} {obj} {set_number}: {result['replays'][-1]}", flush=True)
    (args.out / "small_only.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    text = budget_report(result) + "\n"
    (args.out / "small_only.md").write_text(text, encoding="utf-8")
    print(text)


# Remnants: could a placement that left an unfillable remnant have done otherwise? ---------------------------

NEIGHBOURS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
REMNANT_OUTCOMES = ("fillable after", "alternative covers it", "alternative leaves it fillable", "no alternative")


class PassTrace(Trace):
    """The trace, plus the pass each placement is made in: main or holes, and the connect round."""

    def __init__(self, watch: np.ndarray) -> None:
        super().__init__(watch)
        self.round, self.phase = 0, "main"

    def repaired(self, state) -> None:
        super().repaired(state)
        self.round, self.phase = self.round + 1, "main"

    def holes(self, state) -> None:
        super().holes(state)
        self.phase = "holes"

    def label(self) -> str:
        return self.phase if self.round == 0 else f"{self.phase} {self.round}"


class Snapshot:
    """A build state's arrays and inventory (copied), optionally with one more part; no balance, so a fit checked
    on it is optimistic about balance."""

    def __init__(self, state, part: PlacedPart | None = None) -> None:
        self.filled, self.studs = state.filled.copy(), state.studs.copy()
        self.open_bottom, self.owner = state.open_bottom.copy(), state.owner.copy()
        self.remaining = None if state.remaining is None else dict(state.remaining)
        self.balance = None
        if part is not None:
            for cell in part.cells():
                self.filled[cell] = True
            for cell in part.stud_cells():
                self.studs[cell] = True
            for cell in set(part.bottom_cells()) - set(part.seated_cells()):
                self.open_bottom[cell] = True
            if self.remaining is not None:
                self.remaining[(part.shape.part.name, part.color.name)] -= 1


def held_shapes(builder: BottomUpBuilder, remaining: dict | None) -> list:
    """(shape, a color of it the inventory still holds, its cells as (dy, dz, dx)), smallest shapes first."""
    out = []
    for shape, colors in builder.shape_colors.items():
        left = [c for c in colors if remaining is None or remaining.get((shape.part.name, c.name), 0) > 0]
        if left:
            out.append((shape, left[0], np.argwhere(shape_kernel(shape))))
    return sorted(out, key=lambda held: len(held[2]))


def fillable(builder: BottomUpBuilder, state, mask: np.ndarray, cell: tuple, hang: bool) -> bool:
    """Whether a part the inventory holds covers ``cell`` in a placement that passes every rule as ``state`` stands
    (``hang``: hanging allowed, as in the later hole passes)."""
    if state.filled[cell]:
        return False
    for shape, color, cells in held_shapes(builder, state.remaining):
        for dy, dz, dx in cells:
            if builder._fits_now(PlacedPart(shape, color, cell[0] - dy, cell[2] - dx, cell[1] - dz), state, mask, hang):
                return True
    return False


def alternatives(builder: BottomUpBuilder, state, mask: np.ndarray, part: PlacedPart, visit: tuple,
                 hang: bool) -> list[PlacedPart]:
    """Every other placement the builder could have made at the visited cell then: any part the inventory held, any
    offset covering the cell with the part's bottom layer, every rule as the builder checks it."""
    y, z, x = visit
    out = []
    for shape, colors in builder.shape_colors.items():
        left = [c for c in colors if state.remaining is None or state.remaining.get((shape.part.name, c.name), 0) > 0]
        if not left:
            continue
        for dz, dx in shape.footprint:
            alt = PlacedPart(shape, left[0], y, x - dx, z - dz)
            if (alt.shape, alt.layer, alt.x, alt.z) != (part.shape, part.layer, part.x, part.z) and \
                    builder._fits_now(alt, state, mask, hang):
                out.append(alt)
    return out


def logged_replay(directory: str, seed: int, on_put=None) -> tuple:
    """A cached build replayed with a ``PassTrace`` and a log of its new placements (part, visited cell, pass label),
    checked identical to the cached build. ``on_put(index, state, part, visit, before)`` runs before and after each
    new placement is recorded (it must not change the state or draw). (context, builder, trace, log, filled)."""
    context, parts, bias = replay_setup(directory)
    _, _, candidates = load_run(Path(directory))
    cached = next(c for c in candidates if c.seed == seed)
    mask = context.mask
    final = occupancy(cached.placed, mask.shape)
    trace = PassTrace(mask & ~final)
    builder = d2_builder(context, parts, bias)
    builder.trace = trace
    log, last = [], {}
    place, put = builder._place, builder._put

    def logged_place(part_shape, color, y, z, x, *rest, **options):
        part = place(part_shape, color, y, z, x, *rest, **options)
        if part is not None:
            last["part"], last["visit"] = part, (y, z, x)
        return part

    def logged_put(state, part, links=None):
        new = last.get("part") is part  # else a kept part put back after a connect repair
        if new:
            log.append((part, last.pop("visit"), trace.label()))
            last.clear()
            if on_put is not None:
                on_put(len(log) - 1, state, part, log[-1][1], True)
        put(state, part, links)
        if new and on_put is not None:
            on_put(len(log) - 1, state, part, log[-1][1], False)

    builder._place, builder._put = logged_place, logged_put
    grid = builder.build(context.grid, np.random.default_rng(seed), context.inventory, mask, context.preferred,
                         context.plane)
    placed, _ = extract_parts(grid, parts)
    if sorted(map(placement, placed)) != sorted(map(placement, cached.placed)):
        raise SystemExit(f"{directory} seed {seed}: the logged replay differs from the cached build")
    return context, builder, trace, log, final


def pass_kind(label: str) -> str:
    return "holes" if label.startswith("holes") else "main" if label == "main" else "connect"


def strip_width(free: np.ndarray, cell: tuple) -> int:
    """The narrower of the free runs through ``cell`` along z and along x in its layer (3 for 3 or more)."""
    runs = []
    for axis in (1, 2):
        n = 1
        for step in (1, -1):
            at = list(cell)
            while True:
                at[axis] += step
                if not 0 <= at[axis] < free.shape[axis] or not free[tuple(at)]:
                    break
                n += 1
        runs.append(n)
    return min(min(runs), 3)


def replay_remnants(directory: str, seed: int) -> dict:
    """The bound of a remnant-aware placement score on one build. Remnants: the empty cells that want a used-up small
    part. Each is charged to the placement that left it: the last placed of the final parts next to it (or, inside a
    larger hole, next to the hole). A second replay stops at each such placement and asks whether, right after it,
    some part the inventory held could still fill the remnant under every rule (then the remnant was used up later,
    not made here); else whether another placement at the same visited cell (any part held, any offset, every rule)
    covers it, or leaves it fillable by a part held then (fit checked without balance: optimistic)."""
    context, builder, trace, log, final = logged_replay(directory, seed)
    mask = context.mask
    _, wanted = final_causes(builder, trace, mask)
    remnant = sorted(c for c, names in wanted.items() if any(is_small(name) for name in names))
    state = trace.final
    index = {part: i for i, (part, _, _) in enumerate(log)}  # the latest placement of an equal part is the kept one
    placed_at = [index[part] for part in state.placed]
    labels, _ = ndimage.label(mask & ~final)
    charged: dict[int, list] = {}
    in_hole, alone = 0, 0
    for cell in remnant:
        owners = {int(state.owner[tuple(np.add(cell, d))]) for d in NEIGHBOURS
                  if all(0 <= c < n for c, n in zip(np.add(cell, d), mask.shape))} - {-1}
        if not owners:
            in_hole += 1
            hole = labels == labels[cell]
            owners = set(np.unique(state.owner[ndimage.binary_dilation(hole) & ~hole]).tolist()) - {-1}
        if not owners:  # a hole no part touches: nothing to charge
            alone += 1
            continue
        charged.setdefault(max(placed_at[i] for i in owners), []).append(cell)
    hang = builder.holes and builder.hang
    found: dict[int, dict] = {}

    def on_put(i: int, current, part: PlacedPart, visit: tuple, before: bool) -> None:
        if i not in charged:
            return
        cells = charged[i]
        if before:
            alts = alternatives(builder, current, mask, part, visit, hang and log[i][2].startswith("holes"))
            found[i] = {"alternatives": alts, "before": Snapshot(current),
                        "covers": {c for c in cells if any(c in set(a.cells()) for a in alts)}}
            return
        f = found[i]
        f["after"] = {c for c in cells if fillable(builder, current, mask, c, hang)}
        f["leaves"] = {c for c in cells if c not in f["covers"] and c not in f["after"] and
                       any(fillable(builder, Snapshot(f["before"], a), mask, c, hang) for a in f["alternatives"])}
        f["count"] = len(f.pop("alternatives"))
        del f["before"]

    logged_replay(directory, seed, on_put)
    outcome = {kind: Counter() for kind in ("main", "connect", "holes")}
    for i, cells in charged.items():
        f = found[i]
        for cell in cells:
            o = ("fillable after" if cell in f["after"] else "alternative covers it" if cell in f["covers"] else
                 "alternative leaves it fillable" if cell in f["leaves"] else "no alternative")
            outcome[pass_kind(log[i][2])][o] += 1
    free = mask & ~final
    names = sorted({name for name, _ in context.inventory})
    fits_hole: dict[int, bool] = {}
    for cell in remnant:
        hole = int(labels[cell])
        if hole not in fits_hole:
            region = ndimage.find_objects((labels == hole).astype(int))[0]
            fits_hole[hole] = any(fits_inside(CATALOG[name], (labels == hole)[region]) for name in names)
    return {"seed": seed, "remnant": len(remnant), "in_hole": in_hole, "alone": alone, "placements": len(log),
            "charged_placements": len(charged),
            "outcome": {kind: {o: counts[o] for o in REMNANT_OUTCOMES} for kind, counts in outcome.items()},
            "width": dict(sorted(Counter(strip_width(free, cell) for cell in remnant).items())),
            "no_set_part_fits": sum(not fits_hole[int(labels[cell])] for cell in remnant)}


def remnants_report(rows: list[dict]) -> str:
    lines = ["Remnants (empty cells that want a used-up small part), by the pass of the placement that left them, and "
             "what was possible right after it / at it (alone: in a hole no part touches, not charged):", "",
             "| arm | object | set | remnants | alone | main / connect / holes | " + " | ".join(REMNANT_OUTCOMES) +
             " | bound (covers + leaves) | width 1 / 2 / 3+ | no set part fits |",
             "|---|---|---|---:|---:|---|" + "---:|" * len(REMNANT_OUTCOMES) + "---:|---|---:|"]
    for r in rows:
        total = {o: sum(r["outcome"][k][o] for k in r["outcome"]) for o in REMNANT_OUTCOMES}
        passes = " / ".join(str(sum(r["outcome"][k].values())) for k in ("main", "connect", "holes"))
        bound = total["alternative covers it"] + total["alternative leaves it fillable"]
        widths = " / ".join(str(r["width"].get(w, 0)) for w in (1, 2, 3))
        lines.append(f"| {r['arm']} | {r['object']} | {r['set']} | {r['remnant']} | {r['alone']} | {passes} | " +
                     " | ".join(str(total[o]) for o in REMNANT_OUTCOMES) +
                     f" | {bound} ({100 * bound / max(1, r['remnant']):.0f}%) | {widths} | {r['no_set_part_fits']} |")
    return "\n".join(lines)


def step_remnants(args: argparse.Namespace) -> None:
    """The remnant bound on the diagnosed builds (``BUDGET_ARMS``), replayed twice each (no generation)."""
    jobs = []
    for arm in BUDGET_ARMS:
        for r in json.loads((args.out / f"holes_{arm}.json").read_text(encoding="utf-8")):
            jobs.append((arm, r["object"], r["set"], arm_dir(args.out, arm, r["set"], r["object"], args.runs).as_posix(),
                         r["seed"]))
    rows = []
    with ProcessPoolExecutor(args.workers) if args.workers > 1 else InlineExecutor() as pool:
        futures = [(arm, obj, set_number, pool.submit(replay_remnants, directory, seed))
                   for arm, obj, set_number, directory, seed in jobs]
        for arm, obj, set_number, future in futures:  # in job order
            rows.append({"arm": arm, "object": obj, "set": set_number} | future.result())
            print(f"  {arm} {obj} {set_number}: {rows[-1]['remnant']} remnants, {rows[-1]['outcome']}", flush=True)
    (args.out / "remnants.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    text = remnants_report(rows) + "\n"
    (args.out / "remnants.md").write_text(text, encoding="utf-8")
    print(text)


# Size: the largest target the set completes -----------------------------------------------------------------

SIZE_FAMILIES = {  # family: its arms from the largest target to the smallest, with their slacks
    "creserve": (("creserve", 1.0), ("creserve90", 0.9), ("creserve80", 0.8), ("creserve70", 0.7), ("creserve60", 0.6)),
    "usable": (("usable", 1.0), ("usable90", 0.9), ("usable80", 0.8), ("usable70", 0.7), ("usable60", 0.6)),
}


def size_rows(cells: list[dict]) -> list[dict]:
    """One row per pair, family and slack present in ``cells`` (sweep cells): the target, the valid candidates' mean
    completeness, the selected build's, how many candidates meet the bar, and the time per candidate."""
    by_key = {(c["arm"], c["object"], c["set"]): c for c in cells}
    rows = []
    for set_number, obj in pair_order(cells):
        for family, arms in SIZE_FAMILIES.items():
            for arm, slack in arms:
                c = by_key.get((arm, obj, set_number))
                if c is None:
                    continue
                s = c.get("selected", {})
                rows.append({
                    "object": obj, "set": set_number, "family": family, "slack": slack, "arm": arm,
                    "target_cells": c["target_cells"], "valid": c["valid"], "candidates": c["candidates"],
                    "mean_fill_pct": c["mean_fill_pct"], "mean_largest_hole": c["mean_largest_hole"],
                    "mean_surface_pct": c["mean_surface_pct"],
                    "mean_largest_surface_hole": c.get("mean_largest_surface_hole", math.nan),
                    "complete": c["complete"], "complete_seeds": c.get("complete_seeds", []),
                    "complete_surface": c.get("complete_surface", 0),
                    "complete_surface_seeds": c.get("complete_surface_seeds", []),
                    "s_per_candidate": c["s_per_candidate"],
                    "selected_seed": s.get("seed"), "selected_fill_pct": s.get("fill_pct", math.nan),
                    "selected_largest_hole": s.get("largest_hole"),
                    "selected_surface_pct": s.get("surface_pct", math.nan),
                    "selected_largest_surface_hole": s.get("largest_surface_hole"),
                    "selected_complete": bool(s) and complete(s),
                    "selected_complete_surface": bool(s) and complete(s, "surface")})
    return rows


def size_rules(rows: list[dict]) -> list[dict]:
    """Per pair and family: the largest slack at which any candidate is complete, and at which the selected build
    is (None: at no slack run), with the slacks that were run; under the volume bar and, with ``_surface`` keys, the
    surface bar."""
    rules = {}
    for r in rows:
        rule = rules.setdefault((r["object"], r["set"], r["family"]),
                                {"object": r["object"], "set": r["set"], "family": r["family"], "slacks": [],
                                 "complete_by_slack": {}, "any_complete": None, "selected_complete": None,
                                 "complete_surface_by_slack": {}, "any_complete_surface": None,
                                 "selected_complete_surface": None})
        rule["slacks"].append(r["slack"])
        for suffix in ("", "_surface"):
            rule[f"complete{suffix}_by_slack"][r["slack"]] = r[f"complete{suffix}"]
            for flag, key in ((r[f"complete{suffix}"], f"any_complete{suffix}"),
                              (r[f"selected_complete{suffix}"], f"selected_complete{suffix}")):
                if flag and (rule[key] is None or r["slack"] > rule[key]):
                    rule[key] = r["slack"]
    return list(rules.values())


def size_report(rows: list[dict]) -> str:
    """The per pair, family and slack table, then the per pair largest complete slacks."""
    lines = ["| object | set | family | slack | target cells | valid | fill % (mean) | largest hole (mean) | "
             "surface % (mean) | largest surface hole (mean) | fill % (sel) | largest hole (sel) | surface % (sel) | "
             "largest surface hole (sel) | complete (sel, vol / surf) | candidates meeting the bar (vol / surf) | "
             "s / candidate |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        hole = "" if r["selected_largest_hole"] is None else str(r["selected_largest_hole"])
        surface_hole = "" if r.get("selected_largest_surface_hole") is None else str(r["selected_largest_surface_hole"])
        lines.append(
            f"| {r['object']} | {r['set']} | {r['family']} | {r['slack']:.1f} | {r['target_cells']} | "
            f"{r['valid']}/{r['candidates']} | {r['mean_fill_pct']:.1f} | {r['mean_largest_hole']:.0f} | "
            f"{r['mean_surface_pct']:.1f} | {r['mean_largest_surface_hole']:.0f} | {r['selected_fill_pct']:.1f} | "
            f"{hole} | {r['selected_surface_pct']:.1f} | {surface_hole} | "
            f"{bars_text(r['selected_complete'], r['selected_complete_surface'])} | "
            f"{bars_text(r['complete'], r['complete_surface'])} | {r['s_per_candidate']:.1f} |")
    slacks = sorted({r["slack"] for r in rows}, reverse=True)
    lines += ["", "| object | set | family | largest slack, any candidate complete (vol / surf) | largest slack, "
              "selected complete (vol / surf) | candidates meeting the volume bar (" + " / ".join(f"{s:.1f}" for s in slacks)
              + ") | candidates meeting the surface bar |",
              "|---|---|---|---:|---:|---:|---:|"]
    for rule in size_rules(rows):
        counts = {suffix: " / ".join(str(rule[f"complete{suffix}_by_slack"].get(s, "-")) for s in slacks)
                  for suffix in ("", "_surface")}
        lines.append(f"| {rule['object']} | {rule['set']} | {rule['family']} | "
                     f"{bars_text(slack_text(rule['any_complete']), slack_text(rule['any_complete_surface']))} | "
                     f"{bars_text(slack_text(rule['selected_complete']), slack_text(rule['selected_complete_surface']))}"
                     f" | {counts['']} | {counts['_surface']} |")
    return "\n".join(lines)


def slack_text(slack: float | None) -> str:
    return "none" if slack is None else f"{slack:.1f}"


def save_complete_candidates(cells: list[dict], out: Path) -> list[Path]:
    """Each complete candidate of ``cells`` (under either bar) as <object>_<set>_<arm>_seedNN.ldr (+ preview and missing map) under
    ``out``; files already there are kept."""
    from brickwfc.alt.output import write_build

    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for c in cells:
        seeds = sorted({*c.get("complete_seeds", []), *c.get("complete_surface_seeds", [])})  # either bar
        if not seeds:
            continue
        key, _, candidates = load_run(Path(c["run"]))
        mask = key_mask(key)
        for seed in seeds:
            stem = out / f"{c['object']}_{c['set']}_{c['arm']}_seed{seed:02d}"
            if not stem.with_suffix(".ldr").exists():
                chosen = next(x for x in candidates if x.seed == seed)
                write_build(chosen.placed, mask.shape, stem,
                            f"Complete {c['object']} from {c['set']} ({c['arm']}, seed {seed})")
                missing_png(chosen.placed, mask, stem.with_name(stem.name + "_missing.png"))
            paths.append(stem.with_suffix(".ldr"))
    return paths


def size_sheet(cells: list[dict], out: Path, family: str, path: Path) -> Path:
    """The selected builds of ``family``, pairs as rows and slacks (largest first) as columns."""
    from PIL import Image

    by_key = {(c["arm"], c["object"], c["set"]): c for c in cells}
    blank = out / "sweep_missing" / "none.png"
    blank.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), (255, 255, 255)).save(blank)
    images, labels = [], []
    for set_number, obj in pair_order(cells):
        for arm, slack in SIZE_FAMILIES[family]:
            c = by_key.get((arm, obj, set_number))
            if c is None or "preview" not in c:
                images.append(blank)
                labels.append(f"{obj} {set_number}, {slack:.1f}\nno run")
                continue
            s = c["selected"]
            images.append(Path(c["preview"]))
            done = [name for name, flag in (("vol", s["complete"]), ("surf", s["complete_surface"])) if flag]
            labels.append(f"{obj} {set_number}, {slack:.1f}{', COMPLETE (' + ' + '.join(done) + ')' if done else ''}\n"
                          f"fill {s['fill_pct']:.1f}%, surface {s['surface_pct']:.1f}%\n"
                          f"largest hole {s['largest_hole']} (surface {s['largest_surface_hole']}), "
                          f"{c['target_cells']} cells\n"
                          f"{c['complete']} / {c['complete_surface']} of {c['valid']} valid complete (vol / surf)")
    labeled_sheet(images, labels, path, columns=len(SIZE_FAMILIES[family]), width=500)
    return path


def step_size_report(args: argparse.Namespace) -> None:
    """The size sweep's tables (``size_report``) and compare pairs, a sheet per family, and the complete candidates
    saved under ``complete_candidates/``."""
    arms = [arm for family in SIZE_FAMILIES.values() for arm, _ in family]
    cells = [c for set_number, obj in args.pairs for arm in arms
             if (c := sweep_cell(args, arm, set_number, obj)) is not None]
    rows = size_rows(cells)
    saved = save_complete_candidates(cells, args.out / "complete_candidates")
    sheets = [size_sheet(cells, args.out, family, args.out / f"size_sheet_{family}.png") for family in SIZE_FAMILIES]
    (args.out / "size.json").write_text(json.dumps({"rows": rows, "rules": size_rules(rows), "cells": cells},
                                                   indent=1), encoding="utf-8")
    text = size_report(rows) + "\n"
    if compared := compare_report(cells, SIZE_COMPARE):
        text += "\nSelected builds compared (+ the second arm better, - worse):\n\n" + compared + "\n"
    (args.out / "size.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote size.json, size.md, {', '.join(p.name for p in sheets)}; {len(saved)} complete candidates", flush=True)


# Hollow targets at the solid's scale: sizing only -------------------------------------------------------------

HOLLOW_SIZING_ARMS = ("creserve", "creserve80")  # the solid targets the hollow arms are cut from
HOLLOW_THICKNESSES = (1, 2)


def hollow_sizing_cell(arm: str, set_number: str, obj: str, out: Path) -> dict:
    """One pair at one slack: the solid target (checked against the arm's cached run, if any) and a shell of each
    thickness cut from it at its scale (``pipeline.solid_scale_shell``)."""
    source = load_source(set_number)
    config = arm_config(arm, obj)
    solid, details = sized_target(source, config)
    cached = arm_dir(out, arm, set_number, obj, Path("out")) / "candidates.jsonl"
    same = None
    if cached.exists():
        with cached.open(encoding="utf-8") as f:
            cached_mask = key_mask(json.loads(f.readline())["key"])
        same = cached_mask.shape == solid.mask.shape and bool((cached_mask == solid.mask).all())
    outer = exposed(solid.mask)
    cell = {"arm": arm, "set": set_number, "object": obj, "slack": config.fill_slack,
            "solid_cells": int(solid.mask.sum()), "solid_exposed": int(outer.sum()), "grid": list(solid.mask.shape),
            "same_as_cached": same, "left_out": details.get("left_out", {}), "shells": []}
    for thickness in HOLLOW_THICKNESSES:
        shell, info = solid_scale_shell(source, replace(config, hollow=thickness, hollow_scale="solid"), DATA_DIR,
                                        (solid, details))
        h = info["hollow"]
        cell["shells"].append(h | {
            "kept_pct": 100 * h["cells"] / h["solid_cells"], "exposed": int(exposed(shell.mask).sum()),
            "enclosed": bool((exposed(shell.mask) == outer).all()),
            "spare_cells": h["budget_cells"] - h["cells"], "spare_pct": 100 * (h["budget_cells"] - h["cells"]) / h["budget_cells"]})
    return cell


def hollow_sizing_report(cells: list[dict]) -> str:
    lines = ["| object | set | slack | solid cells | exposed | part budget (cells) | hollow | cells kept (%) | exposed "
             "(shell) | void enclosed | budget - shell cells (% of budget) | fit nowhere in the shell (cells) |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|"]
    for c in cells:
        for h in c["shells"]:
            nowhere = ", ".join(f"{name} x{n}" for name, n in h["fit_nowhere"].items())
            lines.append(f"| {c['object']} | {c['set']} | {c['slack']:.1f} | {c['solid_cells']} | {c['solid_exposed']} | "
                         f"{h['budget_cells']} | {h['thickness']} | {h['cells']} ({h['kept_pct']:.0f}) | {h['exposed']} | "
                         f"{'yes' if h['enclosed'] else 'no'} | {h['spare_cells']} ({h['spare_pct']:.0f}) | "
                         f"{h['fit_nowhere_cells']}{f' ({nowhere})' if nowhere else ''} |")
    return "\n".join(lines)


def step_hollow_sizing(args: argparse.Namespace) -> None:
    folder = args.out / "hollow_sizing"
    folder.mkdir(parents=True, exist_ok=True)
    cells = []
    for arm in HOLLOW_SIZING_ARMS:
        for set_number, obj in args.pairs:
            path = folder / f"{arm}_{set_number}_{obj}.json"
            if not path.exists():
                path.write_text(json.dumps(hollow_sizing_cell(arm, set_number, obj, args.out), indent=1),
                                encoding="utf-8")
            cells.append(json.loads(path.read_text(encoding="utf-8")))
            print(f"{arm} {obj} {set_number}: done", flush=True)
    text = hollow_sizing_report(cells) + "\n"
    (args.out / "hollow_sizing.json").write_text(json.dumps(cells, indent=1), encoding="utf-8")
    (args.out / "hollow_sizing.md").write_text(text, encoding="utf-8")
    print(text)


# Bench: a wider set of pairs, sized before the run (M12c step 5) ---------------------------------------------

BENCH_ARMS = ("creserve", "creserve80")  # the arms the bench is planned for (the size rule picks one later)
BENCH_WORKERS = 5


def bench_sizing_cell(arm: str, set_number: str, obj: str) -> dict:
    """One pair's target under ``arm``, sized as the run would size it (no generation): its cells, the object's
    (without support columns), the usable sizing's left-out parts, the thin-aware scale's result on the object
    (its thinnest horizontal section, 0 if the scale cut it in two, and its overhang moment), and the target's
    face-connected pieces (more than one: resampling cut an arm off; connected growth cannot reach it, and a seed on
    it stalls the run, results/m12c_stall_6378_chair.md)."""
    source = load_source(set_number)
    config = resolve(arm_config(arm, obj))
    clock = time.perf_counter()
    target, details = sized_target(source, config)
    obj_mask = scaled_target(source, replace(config, supports=False), details["volume"], DATA_DIR).mask
    seconds = time.perf_counter() - clock
    same_grid = obj_mask.shape == target.mask.shape
    return {"arm": arm, "set": set_number, "object": obj, "slack": config.fill_slack,
            "inventory_parts": int(sum(source.inventory.values())),
            "inventory_cells": target_volume(source.inventory, "fillable"), "grid": list(target.mask.shape),
            "target_cells": int(target.mask.sum()), "object_cells": int(obj_mask.sum()),
            "support_cells": int((target.mask & ~obj_mask).sum()) if same_grid else None,
            "left_out": details.get("left_out", {}), "left_out_cells": details.get("left_out_cells", 0),
            "rounds": details.get("rounds"), "settled": details.get("settled"),
            "thinnest_section": thinnest_section(obj_mask), "overhang_moment": overhang_moment(obj_mask),
            "pieces": int(ndimage.label(target.mask)[1]), "reconnected": details.get("reconnected", 0),
            "sizing_s": seconds}


def run_seconds(out: Path, arms: Sequence[str] = BENCH_ARMS) -> list[dict]:
    """Every finished run of ``arms`` under ``out``/sweep: its target cells, CPU seconds per candidate (generation and
    physics) and wall seconds."""
    runs = []
    for arm in arms:
        for path in sorted((out / "sweep" / arm).glob("*/*/stats.json")):
            stats = json.loads(path.read_text(encoding="utf-8"))
            cpu = stats["generation_cpu_s"] + stats["physics_cpu_s"]
            runs.append({"arm": arm, "run": path.parent.as_posix(), "target_cells": stats["shape_cells"],
                         "candidates": stats["requested"], "cpu_s_per_candidate": cpu / stats["requested"],
                         "wall_s": stats["wall_time_s"], "parallel_overhead": stats["wall_time_s"] * BENCH_WORKERS / cpu})
    return runs


def time_model(runs: Sequence[dict]) -> dict:
    """CPU seconds per candidate = a x target cells ** b, fitted in log-log to ``runs``, and the median ratio of a run's
    wall time to its CPU time over ``BENCH_WORKERS`` workers (the parallel overhead)."""
    cells = np.log([r["target_cells"] for r in runs])
    seconds = np.log([r["cpu_s_per_candidate"] for r in runs])
    b, log_a = np.polyfit(cells, seconds, 1)
    residual = seconds - (log_a + b * cells)
    return {"a": float(np.exp(log_a)), "b": float(b), "runs": len(runs),
            "cells_range": [int(min(r["target_cells"] for r in runs)), int(max(r["target_cells"] for r in runs))],
            "log_residual_sd": float(residual.std()),
            "parallel_overhead": float(np.median([r["parallel_overhead"] for r in runs]))}


def predicted_minutes(model: dict, target_cells: int, candidates: int = 50) -> float:
    """Wall minutes of a run of ``candidates`` on ``BENCH_WORKERS`` workers under ``model``."""
    per_candidate = model["a"] * target_cells ** model["b"]
    return candidates * per_candidate / BENCH_WORKERS * model["parallel_overhead"] / 60


def bench_report(cells: Sequence[dict], model: dict, n: int) -> str:
    lines = ["| object | set | slack | inventory parts | grid (YxZxX) | target cells | object cells | support cells | "
             "left out (cells) | usable rounds | thinnest section | overhang moment | pieces | reconnected | "
             "est. minutes |", "|---|---|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|"]
    for c in cells:
        left = ", ".join(f"{name} x{k}" for name, k in c["left_out"].items())
        lines.append(f"| {c['object']} | {c['set']} | {c['slack']:.1f} | {c['inventory_parts']} | "
                     f"{'x'.join(map(str, c['grid']))} | {c['target_cells']} | {c['object_cells']} | "
                     f"{'—' if c['support_cells'] is None else c['support_cells']} | "
                     f"{c['left_out_cells']}{f' ({left})' if left else ''} | {c['rounds']} | "
                     f"{'**0 (cut)**' if c['thinnest_section'] == 0 else c['thinnest_section']} | "
                     f"{c['overhang_moment']:.0f} | {pieces_text(c.get('pieces'))} | {c.get('reconnected', '—')} | "
                     f"{predicted_minutes(model, c['target_cells'], n):.1f} |")
    totals = []
    for arm in dict.fromkeys(c["arm"] for c in cells):
        minutes = sum(predicted_minutes(model, c["target_cells"], n) for c in cells if c["arm"] == arm)
        totals.append(f"{arm}: {sum(c['arm'] == arm for c in cells)} pairs, {minutes / 60:.1f} h")
    lines += ["", f"Time model: CPU s per candidate = {model['a']:.3g} x target cells ^ {model['b']:.2f} (fitted on "
              f"{model['runs']} runs, {model['cells_range'][0]}-{model['cells_range'][1]} cells, log residual sd "
              f"{model['log_residual_sd']:.2f}), x {model['parallel_overhead']:.2f} parallel overhead, {n} candidates on "
              f"{BENCH_WORKERS} workers. Totals: " + "; ".join(totals) + "."]
    return "\n".join(lines)


def pieces_text(pieces: int | None) -> str:
    """A target's face-connected pieces for the table: bold when the target is cut, "—" if not recorded."""
    return "—" if pieces is None else f"**{pieces}**" if pieces > 1 else str(pieces)


def step_bench_plan(args: argparse.Namespace) -> None:
    """Sizing only, for ``args.pairs`` under ``BENCH_ARMS``: one json per pair and arm under ``bench_sizing/``
    (resumable), then the table with an estimated run time per pair (``time_model`` on the cached runs of the arms)."""
    folder = args.out / "bench_sizing"
    folder.mkdir(parents=True, exist_ok=True)
    cells = []
    for arm in BENCH_ARMS:
        for set_number, obj in args.pairs:
            path = folder / f"{arm}_{set_number}_{obj}.json"
            if not path.exists():
                path.write_text(json.dumps(bench_sizing_cell(arm, set_number, obj), indent=1), encoding="utf-8")
            cells.append(json.loads(path.read_text(encoding="utf-8")))
            print(f"{arm} {obj} {set_number}: {cells[-1]['target_cells']} cells", flush=True)
    runs = run_seconds(args.out)
    model = time_model(runs)
    text = bench_report(cells, model, args.n) + "\n"
    (args.out / "bench_plan.json").write_text(json.dumps({"cells": cells, "model": model, "runs": runs}, indent=1),
                                               encoding="utf-8")
    (args.out / "bench_plan.md").write_text(text, encoding="utf-8")
    print(text)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.complete", description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=Path, default=Path("out"), help="folder holding m12b_sizing_fig and m12b_sizing")
    parser.add_argument("--out", type=Path, default=Path("out/m12b_complete"))
    parser.add_argument("--steps", nargs="+", default=["final"], choices=["final", "trace", "report", "sweep", "sweep-report", "holes", "old-vs-base",
                                                                           "small-only", "remnants", "size-report",
                                                                           "hollow-sizing", "bench-plan"])
    parser.add_argument("--per-pair", type=int, default=10, help="trace: builds replayed per pair (selected first)")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--n", type=int, default=50, help="sweep: candidates per run")
    parser.add_argument("--arm", default="usable80", help="holes: the sweep arm whose selected builds to diagnose")
    parser.add_argument("--arms", nargs="+", choices=list(ARMS), help="sweep, sweep-report: these arms (default: all; "
                        "the small-part comparison: " + " ".join(SMALL_ARMS) + ")")
    parser.add_argument("--report-name", default="sweep", help="sweep-report: file names (<name>.md, .json, sheets)")
    parser.add_argument("--pairs", type=Path, help="sweep, sweep-report, size-report, hollow-sizing, bench-plan: a JSON "
                        "file of (set, object) pairs (``load_pairs``; e.g. examples/m12c_bench.json); default: the 9 "
                        "sweep pairs")
    args = parser.parse_args(argv)
    args.pairs = load_pairs(args.pairs)
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
    if "small-only" in args.steps:
        step_small_only(args)
    if "remnants" in args.steps:
        step_remnants(args)
    if "size-report" in args.steps:
        step_size_report(args)
    if "hollow-sizing" in args.steps:
        step_hollow_sizing(args)
    if "bench-plan" in args.steps:
        step_bench_plan(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
