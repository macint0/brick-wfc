"""What the alternate-build pipeline builds from: a parts inventory, and the learned style to build it in.

The input is an OMR set number (downloaded to ``data/omr`` once), an LDraw model file (.mpd/.ldr), or a
parts list (.csv: part file, LDraw color code, count). A set number without an OMR model falls back to its
Rebrickable inventory (``bricks.rebrickable``; ``rebrickable:6372-1`` forces that source), which has no model. The inventory is every part in ``parts.CATALOG``,
in any position; other parts are reported as ignored (LDraw primitives, which only appear inside custom
parts defined in a model file, are not parts and are left out of that report).
"""

from __future__ import annotations

import json
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from brickwfc.bricks.colors import BrickColor
from brickwfc.bricks import rebrickable
from brickwfc.bricks.inventory import Inventory, inventory_from_csv, inventory_from_mpd
from brickwfc.bricks.style import StyleStats, merged
from brickwfc.experiments.coverage import PRIMITIVE
from brickwfc.experiments.style import folds
from brickwfc.ldraw.fetch import fetch_set

DATA_DIR = Path("data/omr")
STYLE_DIR = Path("results/m10_style_stats")  # style_fold{i}.json from the M10 run
SETS_FILE = Path("results/sets_selection.json")
FOLDS, FOLD_SEED = 4, 0  # the M10 run's cross-validation (experiments.style defaults)
REBRICKABLE_PREFIX = "rebrickable:"


@dataclass(frozen=True)
class Source:
    name: str
    inventory: Inventory
    colors: tuple[BrickColor, ...]
    ignored: dict[str, int]  # LDraw file -> number of parts not in the catalog
    model: str | None  # LDraw text of the real model; None for a parts list

    @property
    def recognized_parts(self) -> int:
        return sum(self.inventory.values())

    @property
    def ignored_parts(self) -> int:
        return sum(self.ignored.values())


def rebrickable_source(set_num: str, data_dir: Path = rebrickable.DATA_DIR) -> Source:
    """A set's Rebrickable inventory (latest version, no spares); ignored parts by Rebrickable part number."""
    inventory, ignored, colors, _ = rebrickable.Rebrickable(data_dir).inventory(set_num)
    if not inventory:
        raise ValueError(f"{set_num}: none of its Rebrickable parts are in the part catalog")
    return Source(set_num, inventory, tuple(colors), dict(ignored), None)


def load_source(spec: str, data_dir: Path = DATA_DIR, rebrickable_dir: Path = rebrickable.DATA_DIR) -> Source:
    if spec.startswith(REBRICKABLE_PREFIX):
        return rebrickable_source(spec.removeprefix(REBRICKABLE_PREFIX), rebrickable_dir)
    path = Path(spec)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        text, model = path.read_text(encoding="utf-8"), None
        inventory, ignored, colors = inventory_from_csv(text)
    else:
        if suffix in (".mpd", ".ldr"):
            model = path.read_text(encoding="utf-8", errors="replace")
        else:
            try:
                model = fetch_set(spec, data_dir).read_text(encoding="utf-8", errors="replace")
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise
                return rebrickable_source(spec, rebrickable_dir)  # no OMR model for this set
        inventory, ignored, colors = inventory_from_mpd(model)
    if not inventory:
        raise ValueError(f"{spec}: none of its parts are in the part catalog")
    name = path.stem if suffix in (".csv", ".mpd", ".ldr") else spec
    ignored = {file: count for file, count in ignored.items() if not PRIMITIVE.search(file)}
    return Source(name, inventory, tuple(colors), ignored, model)


def all_from_folds(fold_stats: Sequence[StyleStats]) -> StyleStats:
    """Statistics of every set from the k cross-validation folds' training statistics. The fold files
    hold raw counts (``StyleStats.to_json``) and each set is in the training sets of exactly k - 1
    folds, so the sum of the folds over k - 1 equals ``style.merged`` over the sets' own counts."""
    return merged(fold_stats).scaled(1 / (len(fold_stats) - 1))


def learned_style(name: str, style_dir: Path = STYLE_DIR, sets_file: Path = SETS_FILE) -> tuple[StyleStats, str]:
    """The M10 statistics to build ``name`` in, and where they come from: if ``name`` is one of the
    M10 sets, the fold that held it out (the style never saw the set it rebuilds); else all M10 sets."""
    sets = json.loads(sets_file.read_text(encoding="utf-8"))["selected"]
    paths = [style_dir / f"style_fold{i}.json" for i in range(FOLDS)]
    for i, held_out in enumerate(folds(sets, FOLDS, FOLD_SEED)):
        if name in held_out:
            return StyleStats.load(paths[i]), f"M10 fold {i} (learned without {name})"
    return all_from_folds([StyleStats.load(p) for p in paths]), f"all {len(sets)} M10 sets"
