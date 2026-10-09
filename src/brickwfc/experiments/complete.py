"""M12b completeness: how complete the builds are, and why target cells stay empty.

    python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps final
    python -m brickwfc.experiments.complete --runs out --out out/m12b_complete --steps trace --per-pair 10 --workers 5

Reads finished pipeline runs (no generation): the chair and table on the six M12 demo sets
(``m12b_sizing_fig/<set>/<object>_default``) and the car on four (``m12b_sizing/<set>/car_cover``).

``final`` (final state): per pair, over the valid candidates and the selected build, fill, holes (6-connected
components of unfilled target cells: count, largest, total), surface completeness (share of the target's outer
surface cells, ``shapes.surface``, that are filled), and the share of unfilled cells on the surface versus inside;
a missing map per selected build (the build with its unfilled target cells in red).

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
from concurrent.futures import ProcessPoolExecutor
from dataclasses import fields
from pathlib import Path
from typing import Sequence

import numpy as np
from scipy import ndimage

from brickwfc.alt.candidates import Candidate, Context
from brickwfc.alt.features import occupancy
from brickwfc.alt.inputs import learned_style, load_source
from brickwfc.alt.pipeline import AltConfig, cache_key, make_context, make_target
from brickwfc.bricks.bottomup import BottomUpBuilder, _FitMap
from brickwfc.bricks.build import placed_colors, slope_profiles
from brickwfc.bricks.parts import PlacedPart, extract_parts
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
    skin = surface(mask)
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
               "surface_cells": int(surface(mask).sum()), "valid": len(valid), "candidates": len(candidates),
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

    def skipped(self, state, y: int, z: int, x: int) -> None:
        if self.watch[y, z, x]:
            self.cause[y, z, x] = VISIT_CAUSES.index("skipped")

    def repaired(self, state) -> None:
        self.before_repair |= state.filled
        self.epoch += 1

    def failed(self, builder: BottomUpBuilder, state, allowed: np.ndarray, reachable: np.ndarray,
               y: int, z: int, x: int) -> None:
        if self.watch[y, z, x]:
            self.cause[y, z, x] = VISIT_CAUSES.index(self.classify(builder, state, allowed, reachable, y, z, x))

    def fit_maps(self, builder: BottomUpBuilder, state, allowed: np.ndarray, y: int) -> tuple[_FitMap, _FitMap]:
        """Fit maps of layer ``y`` as the build stands: every rule, and every rule but the stud below."""
        stamp = (self.epoch, len(state.placed), y)
        if self.maps is None or self.maps[:3] != stamp:
            studless = builder._studless_top if builder.open_tops else None
            open_bottom = state.open_bottom if builder.open_bottoms else None
            full = _FitMap(state.filled, state.studs, allowed, y, studless, open_bottom)
            space = _FitMap(state.filled, self.studs_everywhere, allowed, y, studless, open_bottom)
            self.maps = (*stamp, full, space)
        return self.maps[3], self.maps[4]

    def classify(self, builder: BottomUpBuilder, state, allowed: np.ndarray, reachable: np.ndarray,
                 y: int, z: int, x: int) -> str:
        if not reachable[z, x]:
            return "support"
        full, space = self.fit_maps(builder, state, allowed, y)
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
                    fits = builder._fits_cells(part, *args, state.studs, allowed, open_bottom, builder.open_tops)
                    roomy = builder._fits_cells(part, *args, self.studs_everywhere, allowed, open_bottom,
                                                builder.open_tops)
                fits_space |= roomy
                if not fits:
                    continue
                if state.balance is None or state.balance.can_add(part, builder._below(part, state.owner)):
                    if left:
                        return "missed"
                    used_up = True
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
    config = AltConfig(**{k: v for k, v in stats["config"].items() if k in known})
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.complete", description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=Path, default=Path("out"), help="folder holding m12b_sizing_fig and m12b_sizing")
    parser.add_argument("--out", type=Path, default=Path("out/m12b_complete"))
    parser.add_argument("--steps", nargs="+", default=["final"], choices=["final", "trace", "report"])
    parser.add_argument("--per-pair", type=int, default=10, help="trace: builds replayed per pair (selected first)")
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    if "final" in args.steps:
        step_final(args)
    if "trace" in args.steps:
        step_trace(args)
    if "report" in args.steps:
        step_report(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
