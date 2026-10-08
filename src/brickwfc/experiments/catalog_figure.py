"""M12b step 4: the spaceship demo before and after corners and slopes, side by side.

    python -m brickwfc.experiments.demo --sets 6378-1 5891-1 --wfc-n 0 --n 100 --out out/m12b_catalog_fig/before
    python -m brickwfc.experiments.demo --sets 6378-1 5891-1 --wfc-n 0 --n 100 --catalog full --style-version v2 \\
        --out out/m12b_catalog_fig/after
    python -m brickwfc.experiments.catalog_figure --dir out/m12b_catalog_fig --out results/m12b_catalog_before_after.png

"Before" reads each set with the M8 catalog and builds in the v1 style; "after" with the M12b catalog
(corners, slopes) and the v2 style; same seeds, same target. One row per set: the best D2 build of each
(the pipeline's top selection), labeled with its parts, how many are slopes and corners, and its fill.
Each build is drawn again from its cached candidate with the current preview (``build.save_preview``, which
draws slopes with their sloped faces), so changing the preview needs no new builds.
Prints a table of both runs' means (the judge is not compared: the two runs judge with different style
statistics).
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Sequence

from brickwfc.bricks.build import save_preview
from brickwfc.experiments.demo import labeled_sheet, load_run

RUNS = (("before", "M8 catalog, v1 style"), ("after", "+ corners and slopes, v2 style"))


def kinds(directory: Path, seed: int) -> Counter[str]:
    """Part kinds of the candidate with ``seed`` (corners counted apart from plates and bricks)."""
    candidates, _ = load_run(directory)
    placed = next(c for c in candidates if c.seed == seed).placed
    return Counter("corner" if "corner" in p.shape.part.name else p.shape.part.kind for p in placed)


def preview(directory: Path, seed: int) -> Path:
    """The candidate with ``seed`` drawn with the current preview, as ``best_preview.png`` in ``directory``."""
    candidates, stats = load_run(directory)
    placed = next(c for c in candidates if c.seed == seed).placed
    path = directory / "best_preview.png"
    save_preview(list(placed), tuple(stats["grid_YZX"]), path)
    return path


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.catalog_figure",
                                     description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=Path("out/m12b_catalog_fig"))
    parser.add_argument("--out", type=Path, default=Path("results/m12b_catalog_before_after.png"))
    args = parser.parse_args(argv)

    summaries = {run: {r["set"]: r for r in json.loads((args.dir / run / "summary.json").read_text(encoding="utf-8"))
                       if r["generator"] == "d2"} for run, _ in RUNS}
    images, labels, lines = [], [], [
        "| set | run | parts in inventory | valid % | fill % | IoU | utilization % | best: parts, slopes, corners, fill % "
        "| s/candidate |", "|---|---|---|---|---|---|---|---|---|"]
    for set_number in summaries["before"]:
        for run, title in RUNS:
            row = summaries[run][set_number]
            best = json.loads((args.dir / run / set_number / "d2" / "stats.json").read_text(encoding="utf-8"))["selected"][0]
            used = kinds(args.dir / run / set_number / "d2", best["seed"])
            images.append(preview(args.dir / run / set_number / "d2", best["seed"]))
            labels.append(f"{set_number}: {title}\n{best['parts']} of {row['parts']} parts "
                          f"({plural(used['slope'], 'slope')}, {plural(used['corner'], 'corner')})\n"
                          f"fill {best['fill_pct']:.0f}%, stands: "
                          f"{'yes' if math.isfinite(best['clutch']) else 'no'}, one piece")
            lines.append(f"| {set_number} | {run} | {row['parts']} | {row['valid_pct']:.0f} | {row['fill_pct']:.1f} | "
                         f"{row['iou']:.2f} | {row['utilization_pct']:.1f} | {best['parts']}, {used['slope']}, "
                         f"{used['corner']}, {best['fill_pct']:.0f} | {row['seconds_per_candidate']:.1f} |")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    labeled_sheet(images, labels, args.out, columns=2)
    print("\n".join(lines))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
