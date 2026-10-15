"""M12d looks: the selected builds before and after the M12d catalog, side by side, for the eye.

    python -m brickwfc.experiments.looks --steps run --workers 5
    python -m brickwfc.experiments.looks --steps report

Two arms on the 9 sweep pairs (``complete.PAIRS``: 6378-1, 5891-1, 4956-1 x chair, table, car), ``--n``
candidates each, the same seeds and the same flags but the catalog and the style statistics:

  old   the M12b catalog (88 parts) and style v2: ``--catalog m12b --style-version v2``
  new   the defaults: the M12d catalog (183 parts) and style v3

Both arms run with the looks flags (``LOOKS``): connected growth with the small parts reserved and regrowth on a
stall, skins, symmetry, recolouring, and slack 0.8 (the slack at which the bench's small sets complete); sizing and
the hole pass are the 3D-target defaults (usable, ``--holes --hang``), and parts that fit nowhere in the build space
are left out (the default since M12d) in both. The arms' targets differ where the catalog recognizes more of the
set: more recognized parts, more volume, a larger object.

``run`` runs the pipeline per pair and arm into ``--out`` (resumable: the pipeline's candidate cache; rerun the same
command). ``report`` measures each run (no generation; the recolouring is replayed exactly as the pipeline did it,
``pipeline.RECOLOR_STREAM``) and writes ``--results`` ``.md`` / ``.json`` and ``_sheet.png``:

- valid share, seconds per candidate (generation + physics CPU), the contact judge of the selected build (reported,
  not deciding; v2 and v3 judges are against different statistics, so not comparable across the arms);
- completeness of the selected build and the mean over the valid ones: fill, largest hole, surface (``complete``);
- skins (``bricks.skin``): distinct parts per 4x4 window of skin, top and side; mirrored share of parts across the
  target's mirror plane (``bricks.symmetry.part_symmetry``) and of the mirrorable ones (``skins.symmetry_row``);
- colour (``bricks.coherence``): same-colour share of visible seams, before and after the recolouring;
- parts: distinct part names, and the parts new in M12d (``new_kind``: not in the M12b catalog), how many show on the
  skin (at least one skin face) and their share of the skin faces, by kind.

The sheet has the pairs as rows and old | new as columns; each cell is the selected build as written (recoloured),
the same build as generated (raw colours), and its missing map (unfilled target cells in red).
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

from brickwfc.alt.features import occupancy
from brickwfc.alt.inputs import DATA_DIR, load_source
from brickwfc.alt.pipeline import RECOLOR_STREAM, AltConfig, sized_target
from brickwfc.alt.pipeline import main as pipeline_main
from brickwfc.bricks.build import save_preview
from brickwfc.bricks.coherence import coherence
from brickwfc.bricks.parts import (M12B_FILES, M12D_FRAMES, M12D_JUMPERS, M12D_KEEP_OUT, PlacedPart, _M12D_CELLS,
                                   _M12D_LOOKALIKES, _M12D_PLAIN, _M12D_SLOPES)
from brickwfc.bricks.recolor import recolor
from brickwfc.bricks.skin import DOWN_STEP, SIDE_STEPS, UP_STEP, exposed, exterior, owners, skin
from brickwfc.bricks.symmetry import best_plane
from brickwfc.experiments.complete import (STRUCTURES, complete, completeness, key_mask, load_pairs, load_run,
                                           mean, missing_png)
from brickwfc.experiments.demo import labeled_sheet
from brickwfc.experiments.skins import symmetry_row

LOOKS = ["--order", "connected", "--reserve-small", "--regrow", "--skin", "--symmetric", "--recolor",
         "--fill-slack", "0.8"]
ARMS = {  # name: (title, catalog, style version, the flags that differ)
    "old": ("old: M12b catalog, style v2", "m12b", "v2", ["--catalog", "m12b", "--style-version", "v2"]),
    "new": ("new: M12d catalog, style v3", "full", "v3", []),
}
SLACK = 0.8  # LOOKS' --fill-slack
M12B_NAMES = frozenset(p.name for p in M12B_FILES.values())
KINDS = {  # M12d part name -> kind, in the order the batches added them
    **{p.name: "plain" for p in _M12D_PLAIN}, **{p.name: "lookalike" for p in _M12D_LOOKALIKES},
    **{p.name: "per-cell" for p in _M12D_CELLS}, **{p.name: "slope/curved" for p in _M12D_SLOPES},
    **{p.name: "frame" for p in M12D_FRAMES}, **{p.name: "keep-out" for p in M12D_KEEP_OUT},
    **{p.name: "jumper" for p in M12D_JUMPERS}}
KIND_ORDER = ("plain", "lookalike", "per-cell", "slope/curved", "frame", "keep-out", "jumper")


def arm_flags(arm: str) -> list[str]:
    """The pipeline flags of an arm: the looks flags and the arm's catalog and style."""
    return [*LOOKS, *ARMS[arm][3]]


def run_dir(out: Path, arm: str, set_number: str, obj: str) -> Path:
    return out / arm / set_number / obj


def new_kind(name: str) -> str | None:
    """The M12d kind of a part (``KINDS``), or None for a part the M12b catalog had."""
    return None if name in M12B_NAMES else KINDS.get(name, "other")


def skin_faces_by_part(placed: Sequence[PlacedPart], shape: tuple[int, int, int]) -> Counter[int]:
    """Part index -> its skin faces (faces open to the outside, as ``bricks.skin``; parts with none are absent)."""
    owner = owners(placed, shape)
    filled = owner >= 0
    outside = exterior(filled)
    faces: Counter[int] = Counter()
    for step in (UP_STEP, DOWN_STEP, *SIDE_STEPS):
        faces.update(owner[exposed(filled, outside, step)].tolist())
    return faces


def parts_row(placed: Sequence[PlacedPart], shape: tuple[int, int, int]) -> dict:
    """Distinct part names, the M12d parts among them, and where those show: on the skin or inside only."""
    faces = skin_faces_by_part(placed, shape)
    total = sum(faces.values())
    kinds = [new_kind(p.shape.part.name) for p in placed]
    new = [i for i, k in enumerate(kinds) if k is not None]
    by_kind: dict[str, dict[str, int]] = {}
    for i in new:
        row = by_kind.setdefault(kinds[i], {"placed": 0, "skin": 0})
        row["placed"] += 1
        row["skin"] += i in faces
    return {"parts": len(placed), "names": len({p.shape.part.name for p in placed}),
            "new_names": len({placed[i].shape.part.name for i in new}), "new_parts": len(new),
            "new_on_skin": sum(i in faces for i in new), "skin_parts": len(faces),
            "new_skin_face_pct": 100 * sum(faces[i] for i in new) / total if total else math.nan,
            "new_by_kind": by_kind, "new_names_list": sorted({placed[i].shape.part.name for i in new})}


def build_row(placed: Sequence[PlacedPart], mask: np.ndarray, plane) -> dict:
    """The looks of one build in its target: completeness, skin windows, mirrored share, parts."""
    s = skin(placed, mask.shape)
    sym = symmetry_row(placed, plane, mask)
    done = completeness(occupancy(placed, mask.shape), mask)
    return {**done, "complete": complete(done), "top_window_parts": s.top_patch_parts, "top_windows": s.top_patches,
            "side_window_parts": s.side_patch_parts, "side_windows": s.side_patches,
            "mirrored_pct": 100 * sym["mirrored"], "mirrorable_mirrored_pct": 100 * sym["mirrorable_mirrored"],
            **parts_row(placed, mask.shape)}


MEANS = ("fill_pct", "largest_hole", "surface_pct", "top_window_parts", "side_window_parts", "mirrored_pct",
         "mirrorable_mirrored_pct", "names", "new_parts", "new_on_skin", "new_skin_face_pct")


def nanmean(values: Sequence[float]) -> float:
    """The mean of the values that are numbers (a build with no full 4x4 window of skin has none to count)."""
    return mean([v for v in values if not math.isnan(v)])


def run_plane(arm: str, set_number: str, obj: str, mask: np.ndarray, data: Path = DATA_DIR):
    """The mirror plane the run's target carries (``--symmetric``), checked to be the run's target; the best plane of
    the run's mask if the target cannot be rebuilt identically."""
    config = AltConfig(shape="brickgpt:" + STRUCTURES[obj], fill_slack=SLACK, symmetric=True)
    target, _ = sized_target(load_source(set_number, data, catalog=ARMS[arm][1]), config, data)
    if target.mask.shape == mask.shape and bool((target.mask == mask).all()) and target.plane is not None:
        return target.plane, "run"
    return best_plane(mask), "best of the run's mask"


def look_cell(out: Path, arm: str, set_number: str, obj: str, sheet_dir: Path, data: Path = DATA_DIR) -> dict | None:
    """One arm x pair: the valid candidates' means, the selected build, and its pictures for the sheet."""
    directory = run_dir(out, arm, set_number, obj)
    if not (directory / "stats.json").exists():
        return None
    key, stats, candidates = load_run(directory)
    mask = key_mask(key)
    plane, plane_from = run_plane(arm, set_number, obj, mask, data)
    valid = [c for c in candidates if c.valid]
    rows = {c.seed: build_row(c.placed, mask, plane) for c in valid}
    cell = {"arm": arm, "set": set_number, "object": obj, "run": directory.as_posix(),
            "target_cells": int(mask.sum()), "volume": stats["sizing"].get("volume"), "grid": list(mask.shape), "plane": plane.name,
            "plane_score": plane.score, "plane_from": plane_from, "style": stats["style"],
            "valid": len(valid), "candidates": len(candidates),
            "s_per_candidate": (stats["generation_cpu_s"] + stats["physics_cpu_s"]) / max(1, len(candidates)),
            "left_out": stats["sizing"].get("left_out", {}),
            "complete_valid": sum(r["complete"] for r in rows.values()),
            "mean": {name: nanmean([r[name] for r in rows.values()]) for name in MEANS}}
    if not stats["selected"]:
        return cell
    chosen = stats["selected"][0]
    raw = next(c for c in candidates if c.seed == chosen["seed"]).placed
    done = recolor(raw, mask.shape, np.random.default_rng([chosen["seed"], RECOLOR_STREAM]))
    stem = f"{obj}_{set_number}_{arm}"
    raw_png = sheet_dir / f"{stem}_raw.png"
    save_preview(list(raw), mask.shape, raw_png)
    before, after = coherence(raw, mask.shape), coherence(done.placed, mask.shape)
    cell["selected"] = rows[chosen["seed"]] | {
        "seed": chosen["seed"], "judge": chosen["judge"], "utilization_pct": chosen["utilization_pct"],
        "accessories": chosen.get("accessories", 0), "seams_raw_pct": 100 * before.same_color,
        "seams_pct": 100 * after.same_color, "colors_per_window": after.colors_per_window,
        "recolor_matches_run": "recolor" in chosen and math.isclose(
            100 * after.same_color, chosen["recolor"]["seams_pct_after"], abs_tol=1e-6)}
    cell["pictures"] = [(directory / chosen["png"]).as_posix(), raw_png.as_posix(),
                        missing_png(raw, mask, sheet_dir / f"{stem}_missing.png").as_posix()]
    return cell


def strip(paths: Sequence[str], path: Path, height: int = 420, gap: int = 12) -> Path:
    """The pictures side by side at one height."""
    images = [Image.open(p).convert("RGB") for p in paths]
    images = [im.resize((round(im.width * height / im.height), height), Image.LANCZOS) for im in images]
    out = Image.new("RGB", (sum(im.width for im in images) + gap * (len(images) - 1), height), (255, 255, 255))
    x = 0
    for im in images:
        out.paste(im, (x, 0))
        x += im.width + gap
    out.save(path)
    return path


def cell_label(c: dict) -> str:
    s = c["selected"]
    return (f"{c['object']} {c['set']}, {ARMS[c['arm']][0]}\n"
            f"fill {s['fill_pct']:.0f}%, largest hole {s['largest_hole']}, surface {s['surface_pct']:.0f}%; "
            f"{s['parts']} parts, {s['names']} kinds, {s['new_parts']} new ({s['new_on_skin']} on skin)\n"
            f"recoloured | as generated | missing (red); seams {s['seams_raw_pct']:.0f} -> {s['seams_pct']:.0f}%")


def sheet(cells: list[dict], path: Path, sheet_dir: Path) -> Path:
    """Pairs as rows, the arms as columns; each cell a strip of the selected build's three pictures."""
    by_key = {(c["set"], c["object"], c["arm"]): c for c in cells}
    images, labels = [], []
    blank = sheet_dir / "none.png"
    Image.new("RGB", (8, 8), (255, 255, 255)).save(blank)
    for set_number, obj in dict.fromkeys((c["set"], c["object"]) for c in cells):
        for arm in ARMS:
            c = by_key.get((set_number, obj, arm))
            if c is None or "pictures" not in c:
                images.append(blank)
                labels.append(f"{obj} {set_number}, {ARMS[arm][0]}\nno run" if c is None else
                              f"{obj} {set_number}, {ARMS[arm][0]}\nnothing selected")
                continue
            images.append(strip(c["pictures"], sheet_dir / f"{obj}_{set_number}_{arm}_strip.png"))
            labels.append(cell_label(c))
    labeled_sheet(images, labels, path, columns=len(ARMS), width=1500)
    return path


def f(value: float, spec: str = ".1f") -> str:
    return "—" if value is None or (isinstance(value, float) and math.isnan(value)) else format(value, spec)


def report(cells: list[dict]) -> str:
    """The tables: per pair and arm, the selected build (and the valid means where given)."""
    head = ("| object | set | arm | target cells | valid | s / cand. | fill % (sel / mean) | largest hole (sel / mean) | "
            "surface % (sel / mean) | complete (sel; valid) | top parts / 4x4 (sel / mean) | side parts / 4x4 (sel / "
            "mean) | mirrored % (sel / mean) | mirrored of mirrorable % (sel) | seams % (raw -> recoloured) | "
            "part names (sel / mean) | new parts: placed / on skin (sel) | new share of skin faces % (sel / mean) | "
            "judge (sel) |")
    lines = [head, "|---|---|---|" + "---:|" * (head.count("|") - 4)]
    for c in cells:
        s, m = c.get("selected"), c["mean"]
        if s is None:
            lines.append(f"| {c['object']} | {c['set']} | {c['arm']} | {c['target_cells']} | "
                         f"{c['valid']}/{c['candidates']} | {c['s_per_candidate']:.1f} |" + " — |" * 13)
            continue
        lines.append(
            f"| {c['object']} | {c['set']} | {c['arm']} | {c['target_cells']} | {c['valid']}/{c['candidates']} | "
            f"{c['s_per_candidate']:.1f} | {s['fill_pct']:.1f} / {f(m['fill_pct'])} | "
            f"{s['largest_hole']} / {f(m['largest_hole'], '.0f')} | {s['surface_pct']:.1f} / {f(m['surface_pct'])} | "
            f"{'yes' if s['complete'] else 'no'}; {c['complete_valid']} | "
            f"{f(s['top_window_parts'], '.2f')} / {f(m['top_window_parts'], '.2f')} | "
            f"{f(s['side_window_parts'], '.2f')} / {f(m['side_window_parts'], '.2f')} | "
            f"{f(s['mirrored_pct'], '.0f')} / {f(m['mirrored_pct'], '.0f')} | {f(s['mirrorable_mirrored_pct'], '.0f')} | "
            f"{f(s['seams_raw_pct'], '.0f')} -> {f(s['seams_pct'], '.0f')} | {s['names']} / {f(m['names'], '.1f')} | "
            f"{s['new_parts']} / {s['new_on_skin']} | {f(s['new_skin_face_pct'])} / {f(m['new_skin_face_pct'])} | "
            f"{s['judge']:.4f} |")
    return "\n".join(lines)


DELTAS = (  # (label, value of a cell, higher is better, format)
    ("fill %", lambda c: c["selected"]["fill_pct"], True, ".1f"),
    ("largest hole", lambda c: c["selected"]["largest_hole"], False, ".0f"),
    ("surface %", lambda c: c["selected"]["surface_pct"], True, ".1f"),
    ("top parts / 4x4", lambda c: c["selected"]["top_window_parts"], False, ".2f"),
    ("side parts / 4x4", lambda c: c["selected"]["side_window_parts"], False, ".2f"),
    ("mirrored %", lambda c: c["selected"]["mirrored_pct"], True, ".0f"),
    ("seams % (recoloured)", lambda c: c["selected"]["seams_pct"], True, ".0f"),
    ("valid", lambda c: c["valid"], True, ".0f"),
)


def delta_table(cells: list[dict]) -> str:
    """Per pair: old -> new on the selected build, + where new is better, - worse, = equal; and the counts."""
    by_key = {(c["set"], c["object"], c["arm"]): c for c in cells}
    lines = ["| object | set | " + " | ".join(label for label, *_ in DELTAS) + " |",
             "|---|---|" + "---:|" * len(DELTAS)]
    totals = {label: Counter() for label, *_ in DELTAS}
    for set_number, obj in dict.fromkeys((c["set"], c["object"]) for c in cells):
        a, b = by_key.get((set_number, obj, "old")), by_key.get((set_number, obj, "new"))
        if a is None or b is None or "selected" not in a or "selected" not in b:
            continue
        row = []
        for label, value, higher, spec in DELTAS:
            x, y = value(a), value(b)
            mark = ("=" if math.isclose(x, y, abs_tol=1e-9) else "?" if math.isnan(x) or math.isnan(y)
                    else "+" if (y > x) == higher else "-")
            totals[label][mark] += 1
            row.append(f"{f(x, spec)} -> {f(y, spec)} {mark}")
        lines.append(f"| {obj} | {set_number} | " + " | ".join(row) + " |")
    lines.append("| | **new better / worse / equal** | " + " | ".join(
        f"{totals[label]['+']} / {totals[label]['-']} / {totals[label]['=']}" for label, *_ in DELTAS) + " |")
    return "\n".join(lines)


def kinds_table(cells: list[dict]) -> str:
    """The new arm's M12d parts in its selected builds, summed over the pairs, by kind: placed and on the skin."""
    placed, on_skin, names = Counter(), Counter(), {}
    for c in cells:
        if c["arm"] != "new" or "selected" not in c:
            continue
        for kind, row in c["selected"]["new_by_kind"].items():
            placed[kind] += row["placed"]
            on_skin[kind] += row["skin"]
        for name in c["selected"]["new_names_list"]:
            names.setdefault(new_kind(name), set()).add(name)
    lines = ["| kind | placed | on the skin | part names |", "|---|---:|---:|---|"]
    for kind in [k for k in KIND_ORDER if placed[k]] + sorted(k for k in placed if k not in KIND_ORDER):
        lines.append(f"| {kind} | {placed[kind]} | {on_skin[kind]} | {', '.join(sorted(names[kind]))} |")
    lines.append(f"| all | {sum(placed.values())} | {sum(on_skin.values())} | |")
    return "\n".join(lines)


def step_run(args: argparse.Namespace) -> None:
    """Every pair, old then new (so a partial run has both arms of the pairs it reached); resumable."""
    for set_number, obj in args.pairs:
        for arm in args.arms:
            out = run_dir(args.out, arm, set_number, obj)
            stats = out / "stats.json"
            if stats.exists() and json.loads(stats.read_text(encoding="utf-8"))["requested"] == args.n:
                continue
            argv = [set_number, "--shape", "brickgpt:" + STRUCTURES[obj], "--n", str(args.n), "--k", "1",
                    "--workers", str(args.workers), "--out", str(out), "--data", str(args.data), *arm_flags(arm)]
            print(f"{arm} {obj} {set_number}: python -m brickwfc.alt {' '.join(argv)}", flush=True)
            pipeline_main(argv)
            print(f"LOOKS_RUN_DONE {arm} {obj} {set_number}", flush=True)


def step_report(args: argparse.Namespace) -> None:
    sheet_dir = args.out / "sheet"
    sheet_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(args.out, arm, s, o, sheet_dir, args.data) for s, o in args.pairs for arm in args.arms]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        cells = [c for c in pool.map(look_cell, *zip(*jobs)) if c is not None]
    results = args.results
    results.parent.mkdir(parents=True, exist_ok=True)
    results.with_name(results.name + ".json").write_text(json.dumps(cells, indent=1), encoding="utf-8")
    sheet(cells, results.with_name(results.name + "_sheet.png"), sheet_dir)
    text = ("Per pair and arm (sel: the selected build; mean: over the valid candidates):\n\n" + report(cells)
            + "\n\nSelected builds, old -> new (+ new better, - worse):\n\n" + delta_table(cells)
            + "\n\nThe new arm's M12d parts in its selected builds, by kind:\n\n" + kinds_table(cells) + "\n")
    (args.out / "looks_tables.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote {results.name}.json, {results.name}_sheet.png and {args.out / 'looks_tables.md'}")


STEPS = {"run": step_run, "report": step_report}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m brickwfc.experiments.looks", description=__doc__.splitlines()[0])
    p.add_argument("--steps", nargs="+", choices=list(STEPS), default=["run", "report"])
    p.add_argument("--out", type=Path, default=Path("out/m12d_looks"))
    p.add_argument("--results", type=Path, default=Path("results/m12d_looks"),
                   help="writes <results>.json and <results>_sheet.png")
    p.add_argument("--n", type=int, default=50, help="candidates per pair and arm")
    p.add_argument("--workers", type=int, default=5)
    p.add_argument("--arms", nargs="+", choices=list(ARMS), default=list(ARMS))
    p.add_argument("--data", type=Path, default=DATA_DIR, help="OMR download cache (as the pipeline's --data)")
    p.add_argument("--pairs", type=Path, help="pairs file (complete.load_pairs; default the 9 sweep pairs)")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    args.pairs = load_pairs(args.pairs)
    for step in args.steps:
        STEPS[step](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
