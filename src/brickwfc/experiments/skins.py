"""M12b step 3: clean skins and mirror symmetry, measured before anything is built.

    python -m brickwfc.experiments.skins --steps measure

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

from brickwfc.alt.candidates import Candidate
from brickwfc.bricks import brickgpt
from brickwfc.bricks.colors import color_for_code
from brickwfc.bricks.parts import BY_FILE, PlacedPart
from brickwfc.bricks.skin import SIZE_CLASSES, Skin, skin
from brickwfc.bricks.symmetry import Plane, mirror_part, part_symmetry, plane_on
from brickwfc.bricks.voxelize import grid_shape, voxelize
from brickwfc.experiments.brickgpt import SETS, target_for
from brickwfc.experiments.demo import load_run
from brickwfc.ldraw.fetch import fetch_set
from brickwfc.ldraw.mpd import flatten

OBJECTS = {"chair": "a712684f", "table": "858f0955", "car": "4b15b71c"}
GRAY = color_for_code(71)


def best_plane(mask: np.ndarray) -> Plane:
    """The better of the two vertical planes through the middle of the mask's extent (any score)."""
    return max((plane_on(mask, axis) for axis in (1, 2)), key=lambda p: p.score)


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
    mask = target_for(set_number, structure, "default").mask
    obj = target_for(set_number, structure, "exact").mask
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


def f(value: float | None, fmt: str = "{:.2f}") -> str:
    return "—" if value is None or (isinstance(value, float) and math.isnan(value)) else fmt.format(value)


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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.skins", description=__doc__.splitlines()[0])
    parser.add_argument("--steps", nargs="+", choices=("measure",), default=["measure"])
    parser.add_argument("--sets", nargs="+", default=list(SETS))
    parser.add_argument("--runs", type=Path, default=Path("out/m12b_brickgpt_v2"))
    parser.add_argument("--data", type=Path, default=Path("data/omr"))
    parser.add_argument("--brickgpt-data", type=Path, default=brickgpt.DATA_DIR)
    parser.add_argument("--sets-file", type=Path, default=Path("results/sets_selection.json"))
    parser.add_argument("--results", type=Path, default=Path("results/m12b_skins_measure.md"))
    args = parser.parse_args(argv)
    if "measure" in args.steps:
        step_measure(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
