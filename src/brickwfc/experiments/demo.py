"""M12 step 3: one target shape built from several real sets' parts.

    python -m brickwfc.experiments.demo --out out/m12_demo

The target is a top-down spaceship (``spaceship_images``: silhouette, height map in plates, color map),
written to ``examples/`` and scaled to each set's inventory volume. Each set runs the alternate-build
pipeline (``alt``) with the bottom-up builder D2 (``--n`` candidates; also without the connect pass, to
show what the one-piece rule costs) and, as the compared method, WFC
with the support, inventory and shape constraints (``--wfc-n`` candidates, ``--wfc-time-limit`` seconds
each; skipped on sets with more than ``--wfc-max-parts`` parts). Runs reuse the pipeline's candidate cache, so a killed run resumes.
Inventories are read with the M8 catalog and built in the v1 (M10) style by default, as in the M12 table;
``--catalog full --style-version v2`` uses the M12b catalog (corners, slopes) and style. Writes ``results.md``,
``summary.json``, ``target.png`` and ``sheet.png`` (the target, then the best D2 build per set, labeled)
under ``--out``.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from brickwfc.alt.candidates import Candidate
from brickwfc.alt.features import occupancy
from brickwfc.alt.inputs import SETS_FILE, load_source
from brickwfc.alt.pipeline import main as alt_main
from brickwfc.alt.target import Target, load_target
from brickwfc.bricks.colors import BrickColor
from brickwfc.bricks.inventory import inventory_cells, utilization
from brickwfc.bricks.shapes import fill, iou
from brickwfc.render3d import save_voxels_png

SETS = ("374-1", "6378-1", "7743-1", "5891-1", "4956-1", "10182-1")
EXAMPLES = Path("examples")
LIGHT_GRAY, WHITE, RED, BLUE, BLACK = (160, 165, 169), (244, 244, 244), (180, 0, 0), (30, 90, 168), (27, 42, 52)


def spaceship_images(width: int = 48, depth: int = 32) -> tuple[Image.Image, Image.Image, Image.Image]:
    """(silhouette, height map, color map) of a top-down spaceship pointing along +x: a fuselage, swept
    wings, tail fins and a cockpit. Heights in plates, whole bricks: wings 3, fuselage and fins 6, cockpit 9."""
    mid = depth // 2
    fuselage = [(2, mid - 4), (width - 10, mid - 4), (width - 1, mid), (width - 10, mid + 3), (2, mid + 3)]
    wings = [(12, mid - 4), (26, mid - 4), (18, 1), (12, 1)], [(12, mid + 3), (26, mid + 3), (18, depth - 2), (12, depth - 2)]
    fins = [(2, mid - 4), (8, mid - 4), (4, mid - 9), (1, mid - 9)], [(2, mid + 3), (8, mid + 3), (4, mid + 8), (1, mid + 8)]
    cockpit = [(width - 14, mid - 2), (width - 6, mid - 1), (width - 6, mid + 1), (width - 14, mid + 1)]
    stripes = [(15, 4), (17, 4), (20, mid - 5), (18, mid - 5)], [(15, depth - 5), (17, depth - 5), (20, mid + 4), (18, mid + 4)]

    silhouette = Image.new("L", (width, depth), 255)
    heights = Image.new("L", (width, depth), 0)
    colors = Image.new("RGBA", (width, depth), (0, 0, 0, 0))
    for polygons, height, color in ((wings, 3, BLUE), (fins, 6, RED), ((fuselage,), 6, LIGHT_GRAY),
                                    (stripes, 3, WHITE), ((cockpit,), 9, BLACK)):
        for polygon in polygons:
            ImageDraw.Draw(silhouette).polygon(polygon, fill=0)
            ImageDraw.Draw(heights).polygon(polygon, fill=height)
            ImageDraw.Draw(colors).polygon(polygon, fill=(*color, 255))
    return silhouette, heights, colors


def write_spaceship(directory: Path = EXAMPLES) -> tuple[Path, Path, Path]:
    paths = tuple(directory / f"spaceship_{kind}.png" for kind in ("silhouette", "heights", "colors"))
    for image, path in zip(spaceship_images(), paths):
        image.save(path)
    return paths


def load_run(directory: Path) -> tuple[list[Candidate], dict]:
    lines = (directory / "candidates.jsonl").read_text(encoding="utf-8").splitlines()[1:]
    stats = json.loads((directory / "stats.json").read_text(encoding="utf-8"))
    return [Candidate.from_json(json.loads(line)) for line in lines if line.strip()], stats


def summarize(set_number: str, generator: str, directory: Path, shape: tuple[Path, Path, Path],
              catalog: str = "m8") -> dict:
    candidates, stats = load_run(directory)
    source = load_source(set_number, catalog=catalog)
    target = load_target(str(shape[0]), inventory_cells(source.inventory), source.colors, shape[1], shape[2])
    built = [c for c in candidates if "generate" not in c.failed]
    valid = [c for c in candidates if c.valid]
    # Shape metrics over builds that pass every check but connectivity, so the rows without the
    # connect pass show what the one-piece rule costs (for the other rows these are the valid builds).
    sound = [c for c in candidates if set(c.failed) <= {"disconnected"}]
    fills = [fill(occupancy(c.placed, target.mask.shape), target.mask) for c in sound]
    ious = [iou(occupancy(c.placed, target.mask.shape), target.mask) for c in sound]
    n = len(candidates)
    mean = lambda values: statistics.mean(values) if values else math.nan  # noqa: E731
    best = stats["selected"][0] if stats["selected"] else {}
    return {
        "set": set_number, "generator": generator, "parts": source.recognized_parts, "candidates": n,
        "grid_YZX": stats["grid_YZX"], "shape_cells": stats["shape_cells"],
        "built_pct": 100 * len(built) / n, "valid_pct": 100 * len(valid) / n,
        "physics_pct": 100 * sum("physics" not in c.failed for c in built) / len(built) if built else math.nan,
        "connected_pct": 100 * sum(c.clusters == 1 for c in built) / len(built) if built else math.nan,
        "fill_pct": 100 * mean(fills), "iou": mean(ious),
        "utilization_pct": 100 * mean([utilization(list(c.placed), source.inventory) for c in sound]),
        "best_judge": best.get("judge", math.nan), "best_fill_pct": best.get("fill_pct", math.nan),
        "best_parts": best.get("parts", 0), "best_clutch": best.get("clutch", math.nan),
        "best_png": str(directory / best["png"]) if best else None,
        "seconds_per_candidate": mean([c.seconds + c.physics_seconds for c in candidates]),
        "check_failures": stats["check_failures"],
    }


def table(rows: list[dict]) -> str:
    lines = ["| set | generator | parts | grid (WxDxH) | candidates | built % | physics % | connected % | valid % "
             "| fill % | IoU | utilization % | best judge | s/candidate |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    f = lambda v, fmt: "—" if v is None or (isinstance(v, float) and math.isnan(v)) else fmt.format(v)  # noqa: E731
    for r in rows:
        if "status" in r:
            lines.append(f"| {r['set']} | {r['generator']} | {r['parts']} | {r['status']} |" + " — |" * 10)
            continue
        y, z, x = r["grid_YZX"]
        lines.append(f"| {r['set']} | {r['generator']} | {r['parts']} | {x}x{z}x{y} | {r['candidates']} | "
                     f"{r['built_pct']:.0f} | {f(r['physics_pct'], '{:.0f}')} | {f(r['connected_pct'], '{:.0f}')} | "
                     f"{r['valid_pct']:.0f} | {f(r['fill_pct'], '{:.1f}')} | {f(r['iou'], '{:.2f}')} | "
                     f"{f(r['utilization_pct'], '{:.1f}')} | {f(r['best_judge'], '{:.3f}')} | "
                     f"{r['seconds_per_candidate']:.2f} |")
    return "\n".join(lines)


def target_preview(target: Target, colors: Sequence[BrickColor], path: Path) -> None:
    """The target shape, each column in its preferred color (gray where it has none)."""
    rgb = {c.name: c.rgb for c in colors}
    column = np.array([[rgb.get(name, LIGHT_GRAY) for name in row] for row in target.preferred], dtype=np.uint8)
    save_voxels_png(target.mask, np.broadcast_to(column, (*target.mask.shape, 3)), path)


def labeled_sheet(images: Sequence[Path], labels: Sequence[str], path: Path, columns: int = 4, width: int = 900,
                  gap: int = 24) -> None:
    """Images in a grid, each scaled to ``width`` pixels and labeled above (builds of different sets are
    at different scales anyway: the target is sized to each inventory)."""
    pictures = []
    for image in images:
        picture = Image.open(image).convert("RGB")
        pictures.append(picture.resize((width, round(picture.height * width / picture.width)), Image.LANCZOS))
    font = ImageFont.load_default(size=30)
    text_h = 40 * max(label.count("\n") + 1 for label in labels)
    cell_h = max(p.height for p in pictures)
    rows = -(-len(pictures) // columns)
    sheet = Image.new("RGB", (columns * width + (columns - 1) * gap, rows * (cell_h + text_h + gap)), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for i, (picture, label) in enumerate(zip(pictures, labels)):
        row, col = divmod(i, columns)
        x, y = col * (width + gap), row * (cell_h + text_h + gap)
        draw.multiline_text((x + 8, y), label, fill=(0, 0, 0), font=font, spacing=8)
        sheet.paste(picture, (x, y + text_h + (cell_h - picture.height) // 2))
    sheet.save(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.demo", description=__doc__.splitlines()[0])
    parser.add_argument("--sets", nargs="+", default=list(SETS))
    parser.add_argument("--n", type=int, default=100, help="D2 candidates per set")
    parser.add_argument("--wfc-n", type=int, default=10, help="WFC candidates per set (0: skip WFC)")
    parser.add_argument("--wfc-time-limit", type=float, default=30.0)
    parser.add_argument("--wfc-max-parts", type=int, default=400,
                        help="skip WFC on larger sets (its backtracking history needs GBs of memory)")
    parser.add_argument("--workers", type=int, help="passed to the pipeline")
    parser.add_argument("--out", type=Path, default=Path("out/m12_demo"))
    parser.add_argument("--catalog", choices=("m8", "full"), default="m8", help="parts inventories are read with")
    parser.add_argument("--style-version", choices=("v1", "v2"), default="v1", help="M10 style statistics")
    args = parser.parse_args(argv)

    shape = write_spaceship()
    common = ["--shape", str(shape[0]), "--height-map", str(shape[1]), "--color-map", str(shape[2])]
    common += ["--catalog", args.catalog, "--style-version", args.style_version]
    common += ["--workers", str(args.workers)] if args.workers else []
    runs = [("d2", ["--n", str(args.n), "--k", "4"]),
            ("d2_no_connect", ["--n", str(args.n), "--k", "1", "--no-connect"])]
    if args.wfc_n:
        runs.append(("wfc", ["--generator", "wfc", "--n", str(args.wfc_n), "--k", "1",
                             "--wfc-time-limit", str(args.wfc_time_limit)]))
    rows = []
    for set_number in args.sets:
        for generator, extra in runs:
            parts = load_source(set_number, catalog=args.catalog).recognized_parts
            if generator == "wfc" and parts > args.wfc_max_parts:
                rows.append({"set": set_number, "generator": generator, "parts": parts, "status": "not run (memory)"})
                continue
            directory = args.out / set_number / generator
            alt_main([set_number, "--out", str(directory), *common, *extra])
            rows.append(summarize(set_number, generator, directory, shape, args.catalog))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    best = [r for r in rows if r["generator"] == "d2" and r.get("best_png")]
    if best:
        years = {c["set"]: c["year"] for c in json.loads(SETS_FILE.read_text(encoding="utf-8"))["candidates"]}
        source = load_source(best[0]["set"], catalog=args.catalog)
        target = load_target(str(shape[0]), inventory_cells(source.inventory), source.colors, shape[1], shape[2])
        colors = [c for r in best for c in load_source(r["set"], catalog=args.catalog).colors]
        target_preview(target, colors, args.out / "target.png")
        labels = ["target: spaceship\nsilhouette + heights + colors\n(scaled to each set)"]
        labels += [f"{r['set']} ({years.get(r['set'], '?')})\n{r['best_parts']} of {r['parts']} parts, "
                   f"fill {r['best_fill_pct']:.0f}%\nstands on a table: "
                   f"{'yes' if math.isfinite(r['best_clutch']) else 'no'}, one piece" for r in best]
        labeled_sheet([args.out / "target.png", *(Path(r["best_png"]) for r in best)], labels, args.out / "sheet.png")
    text = table(rows) + "\n"
    (args.out / "results.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
