"""M12b step 3: clean skins and mirror symmetry, measured before anything is built, then before/after.

    python -m brickwfc.experiments.skins --steps measure
    python -m brickwfc.experiments.skins --steps compare --workers 5

Measures (``bricks.skin``, ``bricks.symmetry``) on:

- our builds of the step-1a rerun (``--runs``, default ``out/m12b_brickgpt_v2``: pipeline defaults, 88-part
  catalog), chair, table and car on 6378-1, 5891-1 and 10182-1: every valid candidate and the selected one;
- BrickGPT's own structures of the same objects (one color, bricks only);
- the 28 real building sets (``results/sets_selection.json``), voxelized with the full catalog: the reference
  for skins. A voxelized set holds only its catalog parts on the stud grid; the faces next to its missing
  parts (windows, doors, minifigures) count as skin when they are open to the outside.

Symmetry is measured across each target's best vertical mirror plane (``symmetry.mirror_plane``; the plane of
the object without support columns). "Mirrorable" parts are those whose mirror image lies inside the target
(where the target itself is symmetric), so a partly symmetric target (the chair: a symmetric seat on a
five-arm base) is measured where symmetry is possible.

Writes ``results/m12b_skins_measure.md`` and ``.json`` (``--results``).

``compare``: chair, car and table on the three sets, ``--n`` candidates each, in arms of the pipeline
(``--arms``, default ``ARMS``; ``arm_flags``): base (pipeline defaults; the step-1a rerun's candidates are reused, the pipeline checks their setup
key), ``--skin``, ``--symmetric`` and both. Per arm: valid share, object fill (against the arm's own object,
without support columns; the symmetric arms make a car or table exactly symmetric by adding cells), the judge
size-matched across the arms (every valid candidate subsampled to the smallest one's contact events),
fragmentation, faces per visible part, the mirrored share of mirrorable parts, and seconds per candidate; for
the valid candidates (mean) and the selected build. Runs go to ``--compare-out`` (resumable: rerun the same
command); writes ``results/m12b_skins.md``, ``.json`` and ``m12b_skins_sheet.png`` (the selected build of
each arm, side by side).
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
from pathlib import Path
from typing import Sequence

import numpy as np

from brickwfc.alt.candidates import Candidate
from brickwfc.alt.features import occupancy
from brickwfc.alt.inputs import learned_style, load_source
from brickwfc.alt.pipeline import AltConfig, make_target
from brickwfc.alt.pipeline import main as alt_main
from brickwfc.alt.target import BRICKGPT_PREFIX
from brickwfc.bricks import brickgpt
from brickwfc.bricks.colors import color_for_code
from brickwfc.bricks.parts import BY_FILE, PlacedPart
from brickwfc.bricks.shapes import fill
from brickwfc.bricks.style import events, matched_divergence
from brickwfc.bricks.skin import SIZE_CLASSES, Skin, skin
from brickwfc.bricks.symmetry import Plane, best_plane, mirror_part, part_symmetry
from brickwfc.bricks.voxelize import grid_shape, voxelize
from brickwfc.experiments.brickgpt import SETS, target_for
from brickwfc.experiments.demo import labeled_sheet, load_run
from brickwfc.ldraw.fetch import fetch_set
from brickwfc.ldraw.mpd import flatten

OBJECTS = {"chair": "a712684f", "table": "858f0955", "car": "4b15b71c"}
ARMS = ("base", "skin", "symmetric", "both")
FLAGS = {"base": [], "skin": ["--skin"], "symmetric": ["--symmetric"], "both": ["--skin", "--symmetric"]}


def arm_flags(arm: str) -> list[str]:
    """Pipeline flags of an arm: one of ``FLAGS``, or ``skin_a<a>`` / ``both_a<a>`` (the soft skin preference,
    ``--skin-power a``, alone or with ``--symmetric``)."""
    if arm in FLAGS:
        return FLAGS[arm]
    for prefix in ("skin_a", "both_a"):
        if arm.startswith(prefix):
            return [*FLAGS[prefix[:-2]], "--skin-power", arm.removeprefix(prefix)]
    raise ValueError(f"unknown arm {arm!r}")
JUDGE_DRAWS = 5
GRAY = color_for_code(71)


def mirrorable(placed: Sequence[PlacedPart], plane: Plane, mask: np.ndarray) -> list[bool]:
    """Per part: its mirror image exists and lies inside ``mask``."""
    out = []
    n = mask.shape
    for part in placed:
        image = mirror_part(part, plane)
        out.append(image is not None and all(0 <= c < s for cell in image.cells() for c, s in zip(cell, n))
                   and all(mask[cell] for cell in image.cells()))
    return out


def symmetry_row(placed: Sequence[PlacedPart], plane: Plane, mask: np.ndarray) -> dict:
    """Symmetry measures of a build in ``mask`` (its grid): all parts, and the mirrorable ones only."""
    sym = part_symmetry(placed, plane, mask.shape)
    able = mirrorable(placed, plane, mask)
    kept = [p for p, a in zip(placed, able) if a]
    sym_able = part_symmetry(kept, plane, mask.shape) if kept else None
    # A mirrorable part's mirror must be placed among all parts, not only among the mirrorable ones; it is
    # mirrorable, so its mirror (inside the mask) is mirrorable too: matching within ``kept`` is the same.
    return {"mirrored": sym.parts, "mirrored_color": sym.parts_color, "mirrored_cells": sym.cells, "occupancy": sym.occupancy,
            "mirrorable_share": float(np.mean(able)),
            "mirrorable_mirrored": math.nan if sym_able is None else sym_able.parts,
            "mirrorable_mirrored_color": math.nan if sym_able is None else sym_able.parts_color}


def skin_row(s: Skin) -> dict:
    return {**{f"{k}_share": v for k, v in s.share.items()}, "faces": s.faces, "faces_per_part": s.faces_per_part,
            "top_patch_parts": s.top_patch_parts, "top_patches": s.top_patches,
            "side_patch_parts": s.side_patch_parts, "side_patches": s.side_patches}


def mean_rows(rows: Sequence[dict]) -> dict:
    """Key-wise mean of the numeric fields, ignoring nan."""
    out = {}
    for key in (k for k, v in rows[0].items() if isinstance(v, (int, float))):
        values = [r[key] for r in rows if not (isinstance(r[key], float) and math.isnan(r[key]))]
        out[key] = statistics.mean(values) if values else math.nan
    return out


def measure_run(set_number: str, name: str, structure: brickgpt.Structure, runs: Path) -> dict:
    directory = runs / set_number / f"{structure.structure_id[:8]}_default"
    candidates, stats = load_run(directory)
    sizing = stats["config"].get("sizing", "box")  # the step-1a runs predate M12b sizing
    mask = target_for(set_number, structure, "default", sizing).mask
    obj = target_for(set_number, structure, "exact", sizing).mask
    plane = best_plane(obj)
    valid = [c for c in candidates if c.valid]
    chosen: Candidate | None = next((c for c in valid if stats["selected"] and c.seed == stats["selected"][0]["seed"]), None)
    per = [{**skin_row(skin(c.placed, mask.shape)), **symmetry_row(c.placed, plane, mask)} for c in valid]
    return {"set": set_number, "object": name, "valid": len(valid), "plane": plane.name, "axis": plane.axis,
            "target_score": plane.score, "mean": mean_rows(per) if per else None,
            "selected": None if chosen is None else per[valid.index(chosen)],
            "selected_seed": None if chosen is None else chosen.seed}


def measure_theirs(name: str, structure: brickgpt.Structure) -> dict:
    occupied = brickgpt.occupancy(structure.bricks)
    placed = brickgpt.to_placed(structure.bricks, GRAY)
    plane = best_plane(occupied)
    return {"object": name, "bricks": len(placed), "plane": plane.name, "axis": plane.axis, "target_score": plane.score,
            **skin_row(skin(placed, occupied.shape)), **symmetry_row(placed, plane, occupied)}


def measure_set(set_number: str, data: Path) -> dict:
    placed, _ = voxelize(flatten(fetch_set(set_number, data).read_text(encoding="utf-8", errors="replace")), BY_FILE)
    shape = grid_shape(placed)
    filled = np.zeros(shape, dtype=bool)
    for part in placed:
        for cell in part.cells():
            filled[cell] = True
    plane = best_plane(filled)
    return {"set": set_number, "parts": len(placed), "plane": plane.name, "plane_score": plane.score,
            **skin_row(skin(placed, shape)), **symmetry_row(placed, plane, filled)}


# Report ----------------------------------------------------------------------------------------------------


def f(value: float | None, fmt: str = "{:.2f}", missing: str = "—") -> str:
    return missing if value is None or (isinstance(value, float) and math.isnan(value)) else fmt.format(value)


def skin_cells(r: dict) -> str:
    return (" | ".join(f(100 * r[f"{k}_share"], "{:.0f}") for k in SIZE_CLASSES)
            + f" | {f(r['faces_per_part'], '{:.1f}')} | {f(r['top_patch_parts'])} ({r['top_patches']:.0f})"
            + f" | {f(r['side_patch_parts'])} ({r['side_patches']:.0f})")


def sym_cells(r: dict) -> str:
    return (f"{f(100 * r['mirrored'], '{:.0f}')} | {f(100 * r['mirrored_color'], '{:.0f}')} | "
            f"{f(100 * r['mirrorable_share'], '{:.0f}')} | {f(100 * r['mirrorable_mirrored'], '{:.0f}')} | "
            f"{f(100 * r['occupancy'], '{:.0f}')}")


SKIN_HEAD = ("small % | long % | wide % | faces / visible part | top: parts per 4x4 (windows) | "
             "sides: parts per 4x4 (windows)")
SYM_HEAD = "mirrored parts % | same color % | mirrorable % | mirrored of mirrorable % | cells mirrored %"


def report(rows: list[dict], theirs: list[dict], real: list[dict]) -> str:
    lines = ["# M12b step 3: clean skins and mirror symmetry, measured", "",
             "Measured before building anything (`python -m brickwfc.experiments.skins --steps measure`). Builds: the "
             "step-1a rerun (`out/m12b_brickgpt_v2`, pipeline defaults, 88-part catalog, 50 candidates per run); "
             "*mean* is over the valid candidates, *selected* is the build the funnel picked.", "",
             "**Skin** (`bricks/skin.py`): every cell face open to the outside (not the ground's bottom). Share of "
             "skin faces on small parts (footprint of 1-2 cells), long ones (1 x n, n >= 3) and wide ones "
             "(>= 2 x 2); faces per visible part (higher: cleaner); distinct parts in each 4 x 4-cell window that "
             "is all skin, on top faces of one layer and on side faces of one column of cells (a side window is "
             "4 studs x 4 plates; lower: cleaner, 1 = one part), with the number of such windows.", "",
             "**Symmetry** (`bricks/symmetry.py`): across the target's best vertical mirror plane, the share of "
             "parts whose mirror image (same part, reflected) is also placed, any color / same color; the share "
             "of parts that are *mirrorable* (their mirror image lies inside the target), and the mirrored share "
             "among those; and the share of filled cells whose reflection is filled.", ""]

    lines += ["## Skins", "", "### Real sets (reference: 28 building sets, voxelized, catalog parts only)", "",
              f"| set | parts | {SKIN_HEAD} |", "|---|---|" + "---|" * 6]
    for r in real:
        lines.append(f"| {r['set']} | {r['parts']} | {skin_cells(r)} |")
    lines.append(f"| **mean of 28** | {statistics.mean(r['parts'] for r in real):.0f} | {skin_cells(mean_rows(real))} |")

    lines += ["", "### BrickGPT's structures (bricks only)", "", f"| object | bricks | {SKIN_HEAD} |", "|---|---|" + "---|" * 6]
    for r in theirs:
        lines.append(f"| {r['object']} | {r['bricks']} | {skin_cells(r)} |")

    lines += ["", "### Our builds (step-1a rerun)", "", f"| object | set | valid | which | {SKIN_HEAD} |",
              "|---|---|---|---|" + "---|" * 6]
    for r in rows:
        for which in ("mean", "selected"):
            if r[which] is not None:
                lines.append(f"| {r['object']} | {r['set']} | {r['valid']} | {which} | {skin_cells(r[which])} |")

    lines += ["", "## Mirror symmetry", "", "### Targets", "",
              "| object | their structure: plane (score) | scaled object, per set: plane (score) |", "|---|---|---|"]
    for t in theirs:
        scaled = ", ".join(f"{r['set']}: {r['plane']} ({r['target_score']:.2f})" for r in rows if r["object"] == t["object"])
        lines.append(f"| {t['object']} | {t['plane']} ({t['target_score']:.2f}) | {scaled} |")
    lines += ["", f"| object | source | which | {SYM_HEAD} |", "|---|---|---|" + "---|" * 5]
    for t in theirs:
        lines.append(f"| {t['object']} | BrickGPT | their structure | {sym_cells(t)} |")
        for r in rows:
            if r["object"] == t["object"]:
                for which in ("mean", "selected"):
                    if r[which] is not None:
                        lines.append(f"| {r['object']} | {r['set']} | {which} | {sym_cells(r[which])} |")
    symmetric_sets = [r for r in real if r["plane_score"] >= 0.9]
    lines += ["", f"Real sets with a mirror plane (cells score >= 0.9): {len(symmetric_sets)} of {len(real)}.", "",
              f"| set | plane (score) | {SYM_HEAD} |", "|---|---|" + "---|" * 5]
    for r in symmetric_sets:
        lines.append(f"| {r['set']} | {r['plane']} ({r['plane_score']:.2f}) | {sym_cells(r)} |")
    return "\n".join(lines) + "\n"


def step_measure(args: argparse.Namespace) -> None:
    structures = {name: brickgpt.find(oid, args.brickgpt_data) for name, oid in OBJECTS.items()}
    rows = []
    for name, structure in structures.items():
        for set_number in args.sets:
            rows.append(measure_run(set_number, name, structure, args.runs))
            print(f"  {name} {set_number}: {rows[-1]['valid']} valid", flush=True)
    theirs = [measure_theirs(name, s) for name, s in structures.items()]
    sets = json.loads(args.sets_file.read_text(encoding="utf-8"))["selected"]
    real = []
    for set_number in sets:
        real.append(measure_set(set_number, args.data))
        print(f"  real {set_number}: {real[-1]['parts']} parts", flush=True)
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.with_suffix(".json").write_text(json.dumps({"runs": rows, "theirs": theirs, "real": real}, indent=1),
                                                 encoding="utf-8")
    args.results.write_text(report(rows, theirs, real), encoding="utf-8")
    print(f"wrote {args.results}")


# Before / after ---------------------------------------------------------------------------------------------


def run_arm(set_number: str, structure: brickgpt.Structure, arm: str, args: argparse.Namespace) -> Path:
    """One pipeline run (resumable); the base arm starts from the step-1a rerun's candidates."""
    directory = args.compare_out / set_number / f"{structure.structure_id[:8]}_{arm}"
    cache = directory / "candidates.jsonl"
    reused = args.runs / set_number / f"{structure.structure_id[:8]}_default" / "candidates.jsonl"
    if arm == "base" and not cache.exists() and reused.exists():
        directory.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(reused, cache)
    alt_main([set_number, "--shape", BRICKGPT_PREFIX + structure.structure_id, "--n", str(args.n), "--k", "1",
              "--out", str(directory), "--workers", str(args.workers), *arm_flags(arm)])
    return directory


def arm_masks(set_number: str, structure: brickgpt.Structure, arm: str,
              sizing: str = "fillable") -> tuple[np.ndarray, np.ndarray]:
    """(the arm's target, as built in; its object without support columns). ``sizing`` as the run's (runs before
    M12b sizing: "box")."""
    source = load_source(set_number)
    symmetric = "--symmetric" in arm_flags(arm)
    shape = BRICKGPT_PREFIX + structure.structure_id
    full = make_target(source, AltConfig(shape=shape, symmetric=symmetric, sizing=sizing)).mask
    obj = make_target(source, AltConfig(shape=shape, symmetric=symmetric, supports=False, sizing=sizing)).mask
    return full, obj


def compare_cell(set_number: str, name: str, structure: brickgpt.Structure, args: argparse.Namespace) -> dict:
    """Every arm of one (object, set): per-candidate measures, the judge size-matched across arms."""
    stats, _ = learned_style(set_number)
    loaded = {}
    for arm in args.arms:
        directory = args.compare_out / set_number / f"{structure.structure_id[:8]}_{arm}"
        loaded[arm] = (directory, *load_run(directory))
    found = {(arm, c.seed): events(c.placed) for arm, (_, cands, _) in loaded.items() for c in cands if c.valid}
    size = min((e.count for e in found.values()), default=0)
    arms = {}
    base_sizing = loaded["base"][2]["config"].get("sizing", "box") if "base" in loaded else "fillable"
    _, base_obj = arm_masks(set_number, structure, "base", base_sizing)
    for arm, (directory, candidates, run_stats) in loaded.items():
        full, obj = arm_masks(set_number, structure, arm, run_stats["config"].get("sizing", "box"))
        plane = best_plane(obj)
        valid = [c for c in candidates if c.valid]
        per = []
        for c in valid:
            judge = -matched_divergence(found[(arm, c.seed)], size, stats, np.random.default_rng([0, c.seed]), JUDGE_DRAWS)
            per.append({"judge": judge, "fill": fill(occupancy(c.placed, full.shape), obj),
                        "base_fill": fill(occupancy(c.placed, full.shape), base_obj), "parts_placed": len(c.placed),
                        **skin_row(skin(c.placed, full.shape)), **symmetry_row(c.placed, plane, full)})
        chosen = run_stats["selected"][0]["seed"] if run_stats["selected"] else None
        index = next((i for i, c in enumerate(valid) if c.seed == chosen), None)
        judges = [r["judge"] for r in per]
        arms[arm] = {"valid_pct": 100 * len(valid) / len(candidates), "valid": len(valid), "candidates": len(candidates),
                     "judge_sd": statistics.stdev(judges) if len(judges) > 1 else math.nan,
                     "plane": plane.name, "plane_score": plane.score, "object_cells": int(obj.sum()),
                     "seconds_per_candidate": statistics.mean(c.seconds + c.physics_seconds for c in candidates),
                     "check_failures": run_stats["check_failures"],
                     "mean": mean_rows(per) if per else None, "selected": None if index is None else per[index],
                     "selected_seed": chosen,
                     "png": str(directory / run_stats["selected"][0]["png"]) if run_stats["selected"] else None}
    return {"set": set_number, "object": name, "judge_size": size, "arms": arms}


COMPARE_HEAD = ("| object | set | arm | valid | judge (sd) | fill % | base-object fill % | top: parts per 4x4 | sides: parts per 4x4 | "
                "faces / visible part | mirrored of mirrorable % | same color % | s/candidate |")


def compare_line(cell: dict, arm: str, which: str) -> str:
    a = cell["arms"][arm]
    r = a[which]
    if r is None:
        return f"| {cell['object']} | {cell['set']} | {arm} | {a['valid']}/{a['candidates']} |" + " — |" * 9
    sd = f" ({a['judge_sd']:.4f})" if which == "mean" else ""
    return (f"| {cell['object']} | {cell['set']} | {arm} | {a['valid']}/{a['candidates']} | {r['judge']:.4f}{sd} | "
            f"{100 * r['fill']:.1f} | {100 * r['base_fill']:.1f} | {f(r['top_patch_parts'])} | {f(r['side_patch_parts'])} | "
            f"{f(r['faces_per_part'], '{:.1f}')} | {f(100 * r['mirrorable_mirrored'], '{:.0f}')} | "
            f"{f(100 * r['mirrorable_mirrored_color'], '{:.0f}')} | {a['seconds_per_candidate']:.1f} |")


def delta_table(cells: list[dict]) -> list[str]:
    """Each arm minus base, averaged over the (object, set) cells (means over valid candidates)."""
    keys = ("judge", "fill", "base_fill", "top_patch_parts", "side_patch_parts", "faces_per_part", "mirrorable_mirrored")
    lines = ["| arm | judge | fill (points) | base-object fill (points) | top parts per 4x4 | side parts per 4x4 | faces / visible part | "
             "mirrored of mirrorable (points) | judge up in | fill up in |", "|---|---|---|---|---|---|---|---|---|---|"]
    base_sd = statistics.mean(c["arms"]["base"]["judge_sd"] for c in cells)
    lines.append(f"| (base: judge sd across candidates, mean over cells) | {base_sd:.4f} |" + " |" * 8)
    for arm in cells[0]["arms"]:
        if arm == "base":
            continue
        pairs = [(c["arms"][arm]["mean"], c["arms"]["base"]["mean"]) for c in cells
                 if c["arms"][arm]["mean"] and c["arms"]["base"]["mean"]]
        d = {k: statistics.mean(a[k] - b[k] for a, b in pairs if not math.isnan(a[k] - b[k])) for k in keys}
        up_judge = sum(a["judge"] > b["judge"] for a, b in pairs)
        up_fill = sum(a["fill"] > b["fill"] for a, b in pairs)
        lines.append(f"| {arm} | {d['judge']:+.4f} | {100 * d['fill']:+.1f} | {100 * d['base_fill']:+.1f} | {d['top_patch_parts']:+.2f} | "
                     f"{d['side_patch_parts']:+.2f} | {d['faces_per_part']:+.1f} | {100 * d['mirrorable_mirrored']:+.0f} | "
                     f"{up_judge}/{len(pairs)} | {up_fill}/{len(pairs)} |")
    return lines


def compare_report(cells: list[dict]) -> str:
    lines = ["# M12b step 3: skin preference and symmetric decoding, before / after", "",
             "`python -m brickwfc.experiments.skins --steps compare` (measures: `results/m12b_skins_measure.md`). "
             "Chair, car and table on 6378-1, 5891-1 and 10182-1, 50 candidates per run, pipeline defaults plus the "
             "arm's flags: **base** (the step-1a rerun), **skin** (`--skin`: largest parts first on the target's "
             "surface), **symmetric** (`--symmetric`: the target's mirror plane; a car or table, at least 0.8 symmetric after "
             "scaling, is made exactly symmetric by adding the mirror image of its cells, the chair, 0.71-0.77, is "
             "not; each part's mirror image is placed with it where it fits and the inventory has it), **both**; "
             "**skin_a<a>** / **both_a<a>**: the soft skin preference (`--skin --skin-power a`: choice weights x "
             "cells ** a on skin cells instead of largest first), alone or with `--symmetric`.", "",
             "Judge: size-matched across the arms of a cell (every valid candidate subsampled to the smallest "
             "one's contact events; higher is better). Fill: of the arm's own object (no support columns). "
             "Base-object fill: of the base arm's object, on the same grid (the symmetric arms make a car or table "
             "exactly symmetric by adding the mirror image of its cells, so their own object is 2-15% larger). "
             "Fragmentation: distinct parts per all-skin 4 x 4-cell window (lower is cleaner; — when the build has no "
             "such window on that face, e.g. a stepped roof). Mirrored: share of "
             "mirrorable parts whose mirror image is placed (any color; then same color).", "",
             f"## Change against base (means over valid candidates, averaged over the {len(cells)} cells)", ""]
    lines += delta_table(cells)
    for which, title in (("mean", "Means over valid candidates"), ("selected", "Selected build (k = 1)")):
        lines += ["", f"## {title}", "", COMPARE_HEAD, "|---|---|---|" + "---|" * 10]
        for cell in cells:
            for arm in cell["arms"]:
                lines.append(compare_line(cell, arm, which))
    lines += ["", "## Targets", "", "| object | set | arm | object cells | plane (score) | judge size (events) |",
              "|---|---|---|---|---|---|"]
    for cell in cells:
        for arm, a in cell["arms"].items():
            lines.append(f"| {cell['object']} | {cell['set']} | {arm} | {a['object_cells']} | {a['plane']} "
                         f"({a['plane_score']:.2f}) | {cell['judge_size']} |")
    return "\n".join(lines) + "\n"


def sheet_label(cell: dict, arm: str, r: dict) -> str:
    """Caption of a build on the comparison sheet, ASCII only (the sheet's default font has no em dash); "n/a":
    no all-skin 4 x 4 window on that face (a stepped roof), or nothing mirrorable."""
    return (f"{cell['object']} {cell['set']}: {arm}\nfill {100 * r['fill']:.0f}%, "
            f"top {f(r['top_patch_parts'], '{:.1f}', 'n/a')}, sides {f(r['side_patch_parts'], '{:.1f}', 'n/a')}\n"
            f"mirrored {f(100 * r['mirrorable_mirrored'], '{:.0f}%', 'n/a')}")


def compare_sheet(cells: list[dict], path: Path) -> None:
    images, labels = [], []
    for cell in cells:
        for arm, a in cell["arms"].items():
            r = a["selected"]
            if a["png"] is None or r is None:
                continue
            images.append(Path(a["png"]))
            labels.append(sheet_label(cell, arm, r))
    labeled_sheet(images, labels, path, columns=len(cells[0]["arms"]), width=600)


def step_compare(args: argparse.Namespace) -> None:
    structures = {name: brickgpt.find(OBJECTS[name], args.brickgpt_data) for name in args.objects}
    for set_number in args.sets:  # small sets first: their rows are ready early
        for name, structure in structures.items():
            for arm in args.arms:
                print(f"== {name} {set_number} {arm}", flush=True)
                run_arm(set_number, structure, arm, args)
    cells = [compare_cell(set_number, name, structure, args)
             for name, structure in structures.items() for set_number in args.sets]
    out = args.compare_results
    out.with_suffix(".json").write_text(json.dumps(cells, indent=1), encoding="utf-8")
    out.write_text(compare_report(cells), encoding="utf-8")
    compare_sheet(cells, out.with_name(out.stem + "_sheet.png"))
    print(f"wrote {out}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.skins", description=__doc__.splitlines()[0])
    parser.add_argument("--steps", nargs="+", choices=("measure", "compare"), default=["measure"])
    parser.add_argument("--sets", nargs="+", default=list(SETS))
    parser.add_argument("--runs", type=Path, default=Path("out/m12b_brickgpt_v2"))
    parser.add_argument("--data", type=Path, default=Path("data/omr"))
    parser.add_argument("--brickgpt-data", type=Path, default=brickgpt.DATA_DIR)
    parser.add_argument("--sets-file", type=Path, default=Path("results/sets_selection.json"))
    parser.add_argument("--results", type=Path, default=Path("results/m12b_skins_measure.md"))
    parser.add_argument("--objects", nargs="+", choices=sorted(OBJECTS), default=["chair", "car", "table"])
    parser.add_argument("--n", type=int, default=50, help="compare: candidates per run")
    parser.add_argument("--arms", nargs="+", default=list(ARMS),
                        help="compare: base, skin, symmetric, both, skin_a<a>, both_a<a> (soft skin, --skin-power a)")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--compare-out", type=Path, default=Path("out/m12b_skins"))
    parser.add_argument("--compare-results", type=Path, default=Path("results/m12b_skins.md"))
    args = parser.parse_args(argv)
    if "measure" in args.steps:
        step_measure(args)
    if "compare" in args.steps:
        step_compare(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
