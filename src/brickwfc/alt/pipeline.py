"""Alternate builds from a set or a parts list (M12): generate -> verify -> dedupe -> judge -> select.

    python -m brickwfc.alt 6372-1 --n 200 --k 8
    python -m brickwfc.alt my_parts.csv --shape pyramid --out out/alt/mine
    python -m brickwfc.alt 6372-1 --shape ship.png --color-map ship_colors.png

Input: an OMR set number, an .mpd/.ldr model or a .csv parts list (``inputs.py``). Style: the M10
statistics, from the fold that held the set out if it is one of the M10 sets, else from all of them.

  generate  ``--n`` candidates, seeds ``--seed`` .. ``--seed + n - 1``, with the bottom-up builder D2
            and the learned style bias (or ``--generator wfc``), in parallel (``candidates.py``); ``--order``
            and ``--proposal`` (a learned proposal model, M12b) change how D2 picks parts
  verify    integrity, inventory, support, shape, physics on a table (``candidates.py``), then a size
            floor: candidates with fewer contact events than the ``--min-size-quantile`` quantile of the
            verified ones fail "too_small", so one tiny build cannot shrink every judge sample; with a
            target shape, a fill floor: candidates filling less than ``--fill-floor`` x the 90th
            percentile of the verified ones' fill fail "low_fill" (M12b), and with ``--min-fill`` (M12c, off by
            default) less than that share of the target in absolute terms: a run where every candidate stalls
            (results/m12c_stall_6378_chair.md: 3.4% fill, all 50 "valid") then selects nothing
  dedupe    near-duplicates in feature space (``features.py``, ``funnel.dedupe``)
  judge     minus the divergence of the build's contact statistics from the learned ones (``style``),
            size-matched: every build subsampled to the smallest one's number of contact events
  select    top ``--k`` by judge + ``--diversity`` x distance to the builds already picked
            (``funnel.select``); judge scores are standardized and feature distances divided by their
            median, so the two terms are on comparable scales. With a target shape the score is
            z(judge) + ``--fill-weight`` x z(fill) (M12b; 0 restores judge only), and builds that meet the
            completeness bar (``features.Bar``: ``--bar volume`` fill >= 97%, largest hole <= 4, surface >= 98%;
            ``--bar surface`` surface >= 98%, largest surface hole <= 4) are picked before the rest (M12c,
            ``--no-complete-first`` restores score order); with complete-first, dedupe also keeps a complete
            build over an incomplete near-duplicate
  recolor   with ``--recolor`` (M12c, off by default), each selected build's colours are permuted among the parts
            of each part type to make its skin colour-coherent (``bricks.recolor``): every placement and every
            (part, colour) count stays, so every check above still holds. It runs after select, so the judge
            and the selection are those of the builds as generated (the stats.json ``judge`` is the original
            build's). The alternative, recolouring every candidate before the judge, would let the judge's colour
            term see the new colours and could change the selection

Without a target shape, the grid is a cube in millimetres (2.5 plates tall per stud of width) with
volume ``--room`` x the inventory's; ``--height`` fixes the height instead (M10's grid: ``--height 12``). With
``--shape`` (a primitive, a silhouette image with optional ``--height-map`` and ``--color-map``, a
model, a BrickGPT structure or a mesh; ``target.py``), the shape is scaled to the inventory's volume and the generators are told to fill
it. Writes, under ``--out``: build_NN.ldr (one
``0 STEP`` per layer, bottom to top), build_NN.png, sheet.png, stats.json, and candidates.jsonl (every
candidate as it is generated, so a killed run resumes: rerun the same command).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Sequence

import numpy as np

from brickwfc.alt.candidates import BUILDER_VERSION, GENERATORS, VERIFY_VERSION, Candidate, Context, generate
from brickwfc.alt.features import BARS, Bar, completeness, feature_vector, occupancy
from brickwfc.alt.inputs import (CATALOGS, DATA_DIR, SETS_FILE, STYLE_DIR, STYLE_FILES, STYLE_VERSION, Source,
                                 learned_style, load_source)
from brickwfc.alt.output import layer_steps, write_build, write_sheet
from brickwfc.bricks.accessories import fit
from brickwfc.alt.target import Target, load_target, takes_supports
from brickwfc.bricks.inventory import SIZINGS, inventory_cells, target_volume, unusable, utilization
from brickwfc.bricks.recolor import recolor
from brickwfc.bricks.shapes import SHAPES, fill, hollow, iou
from brickwfc.bricks.style import StyleStats, events, matched_divergence
from brickwfc.bricks.symmetry import SYMMETRIZE_MIN_SCORE
from brickwfc.bricks.voxelize import voxelize
from brickwfc.experiments.inventory import grid_for
from brickwfc.experiments.style import InlineExecutor
from brickwfc.funnel.dedupe import dedupe
from brickwfc.funnel.pipeline import StageStats, format_stages
from brickwfc.funnel.select import select
from brickwfc.ldraw.export import PLATE_LDU, STUD_LDU
from brickwfc.ldraw.mpd import flatten

SHAPE_EMPTY_WEIGHT = 0.05  # per part type: a solid share of ~95%, so the builders try to fill the shape
CHUNKS_PER_WORKER = 4
PLATES_PER_STUD = STUD_LDU / PLATE_LDU  # 2.5: plate layers per stud of width, for a cube in millimetres


@dataclass(frozen=True)
class AltConfig:
    n: int = 200
    k: int = 8
    seed: int = 0
    generator: str = "d2"
    height: int | None = None  # plates (no target shape); None: a cube, see cube_grid
    room: float = 1.5  # grid volume / inventory volume (no target shape)
    balanced: bool = True
    bridge: bool = True
    connect: bool = True
    connect_rounds: int = 10  # repair rounds (see bottomup); 1 reproduces the step-2b table
    shape: str | None = None  # see target.py
    height_map: str | None = None
    color_map: str | None = None
    shape_height: int = 6  # plates, for a silhouette without a height map
    shape_exact: bool = False  # a model shape keeps its exact cells (overhangs) instead of solid columns
    shape_columns: bool = False  # a 3D target (BrickGPT structure, mesh) becomes solid columns (its heightfield)
    voxels: int = 32  # mesh target: cells along its longest side before scaling
    mesh_up: str = "y"
    hollow: int = 0  # 3D target: shell thickness in cells, plus internal pillars (0: solid)
    hollow_scale: str = "shell"  # with hollow: shell (the shell is scaled to the volume, a larger object) or solid
    # (the solid target is sized as without hollow, then hollowed: the same object, the interior's parts left over)
    supports: bool = True  # 3D target: support columns under overhangs out of a part's reach (M12b 1d)
    support_height: int = 6  # with supports: only columns at most this many cells tall (0: any); 6 props the
    # chair's caster hub without towers under a table top (results/m12b_brickgpt.md)
    open_tops: bool = True  # with a target shape: studless top cells only under empty target cells
    order: str = "random"  # d2: cells of a layer visited in random or raster order
    sizing: str | None = None  # target volume; None: usable with a 3D target, fillable otherwise (``resolve``).
    # fillable: slopes count their stud cells x 1 layer, and the scale keeps thin parts thick; box: both as before
    # M12b sizing; usable: fillable without the parts that fit nowhere in the target (M12b completeness)
    fill_slack: float = 1.0  # target volume = this x the sizing's volume (1: as if every part were used)
    proposal: str | None = None  # d2: learned proposal model (.npz from training/, vocab.json next to it)
    skin: bool = False  # d2 with a target: largest parts first on the target's skin (M12b step 3)
    skin_power: float | None = None  # with skin: soft preference, choice weights x cells ** this (None: hard sort)
    symmetric: bool = False  # d2 with a target: mirror-preserving scale + symmetric decoding (M12b step 3)
    symmetrize_min_score: float = SYMMETRIZE_MIN_SCORE  # with symmetric: a plane this good symmetrizes the object
    holes: bool | None = None  # d2: hole-filling pass after the main pass and each connect round (M12b holes);
    # None: on with a 3D target (``resolve``)
    hang: bool | None = None  # d2 with holes: the hole pass may hang parts from parts above by their studs; None: as
    # holes with a 3D target
    reserve_small: bool = False  # d2: the main pass tries parts of <= 3 cells only where no larger part fits
    small_last: float | None = None  # d2: the main pass weighs parts of <= 3 cells down, by (cells / 4) ** this
    regrow: bool = False  # d2, connected order: on a stall (under half the target), grow again from the next ground
    # region (``bricks/bottomup.py``, M12c)
    strength: float = 1.0  # exponent on the learned style weights
    max_clutch: float = 1111.0  # physics: keep builds needing at most this clutch per stud, in plate-cell weights;
    # 1111 is a real stud (calibrated in results/m12b_overhangs_tables.md); inf: no limit
    wfc_time_limit_s: float = 30.0
    min_size_quantile: float = 0.1
    fill_floor: float = 0.5  # with a target: fail builds filling < this x the 90th-percentile fill (0: off)
    min_fill: float = 0.0  # with a target: also fail builds filling < this share of it (0: off; the floor above is
    # relative, so it passes a run in which every candidate stalls)
    fill_weight: float = 1.0  # with a target: selection score z(judge) + this x z(fill) (0: judge only)
    complete_first: bool = True  # with a target: builds that meet the bar are selected before the rest (M12c)
    bar: str = "volume"  # what complete means (``features.Bar``): volume (fill, largest hole, surface) or surface
    # (surface share and largest surface hole; interior cells are invisible)
    complete_fill: float = Bar.fill  # the bar's thresholds: fill share (volume bar only), ...
    complete_hole: int = Bar.largest_hole  # ... cells of the largest (surface) hole, ...
    complete_surface: float = Bar.surface  # ... and the filled share of the exposed cells
    judge_draws: int = 5
    dedupe_threshold: float = 0.05
    diversity: float = 0.5
    recolor: bool = False  # after select: colours permuted within part types for a coherent skin (``bricks.recolor``)


@dataclass(frozen=True)
class Selected:
    candidate: Candidate
    judge: float
    complete: bool | None = None  # meets the bar (None: no target shape)
    recolored: dict | None = None  # with --recolor: the skin's coherence before and after (``recolor_selected``)


@dataclass
class FunnelReport:
    requested: int
    stages: list[StageStats]
    check_failures: dict[str, int]
    size_floor: int  # contact events
    judge_size: int  # contact events every judged build was subsampled to
    selected: list[Selected]
    candidates: list[Candidate]
    complete: int | None = None  # unique builds that meet the bar (None: no target shape)


def bar_of(config: AltConfig) -> Bar:
    return Bar(config.complete_fill, config.complete_hole, config.complete_surface, config.bar)


def cube_grid(cells: float, room: float) -> tuple[int, int, int]:
    """(Y, Z, X) of a cube in millimetres (a plate is 0.4 studs tall, so 2.5 plates per stud of width)
    with volume about ``room`` x ``cells``."""
    volume = room * cells
    side = max(2, math.ceil((volume / PLATES_PER_STUD) ** (1 / 3)))
    return (max(1, math.ceil(volume / side**2)), side, side)


USABLE_ROUNDS = 5  # usable sizing: most rescaling rounds (a fixpoint is usually reached in 2 or 3)


def resolve(config: AltConfig) -> AltConfig:
    """``config`` with its target-dependent defaults filled in. With a 3D target (a model, BrickGPT structure or mesh:
    ``takes_supports``, as for support columns): usable sizing and, for d2, the hole pass with hanging support (cf,
    2026-10-10, from the M12b completeness sweep: hanging support raised fill on 9/9 pairs, usable sizing on the one
    pair where it leaves a part out and changed nothing on the other 8). Otherwise fillable sizing and no hole pass.
    Settings given explicitly stay as they are."""
    three_d = config.shape is not None and takes_supports(config.shape)
    on = three_d and config.generator == "d2"
    holes = on if config.holes is None else config.holes
    hang = holes and on if config.hang is None else config.hang
    sizing = ("usable" if three_d else "fillable") if config.sizing is None else config.sizing
    return replace(config, holes=holes, hang=hang, sizing=sizing)


def make_target(source: Source, config: AltConfig, data_dir: Path = DATA_DIR) -> Target | None:
    return sized_target(source, config, data_dir)[0]


HOLLOW_SCALES = ("shell", "solid")


def scaled_target(source: Source, config: AltConfig, volume: float, data_dir: Path) -> Target:
    """``config``'s target scaled to ``volume`` cells (``target.load_target``)."""
    return load_target(config.shape, volume, source.colors, Path(config.height_map) if config.height_map else None,
                       Path(config.color_map) if config.color_map else None, config.shape_height, data_dir,
                       config.shape_exact, config.shape_columns, voxels=config.voxels, up=config.mesh_up,
                       hollow=config.hollow, supports=config.supports and takes_supports(config.shape),
                       support_height=config.support_height, symmetric=config.symmetric,
                       keep_sections=config.sizing != "box", symmetrize_min_score=config.symmetrize_min_score)


def sized_target(source: Source, config: AltConfig, data_dir: Path = DATA_DIR) -> tuple[Target | None, dict]:
    """The target scaled to ``fill_slack`` x the inventory's volume under ``sizing``, and how it was sized.

    Usable sizing (M12b completeness) starts from the fillable volume, then leaves out every part that fits nowhere
    inside the scaled target (``inventory.unusable``: any orientation and position, every rule but the shape off),
    rescales, and repeats until the left-out parts no longer change: a smaller target can leave out more parts. The
    left-out parts stay in the inventory (they just cannot go in). The details: the volume the target was scaled to
    and, with usable sizing, the left-out parts (name -> count), their cells, the rounds and whether they settled.
    With ``hollow`` and ``hollow_scale="solid"``, see ``solid_scale_shell``."""
    if config.shape is None:
        return None, {}
    config = resolve(config)
    if not 0 < config.fill_slack <= 1:
        raise ValueError(f"fill_slack must be in (0, 1], not {config.fill_slack}")
    if config.hollow_scale not in HOLLOW_SCALES:
        raise ValueError(f"hollow_scale must be one of {HOLLOW_SCALES}, not {config.hollow_scale!r}")
    if config.hollow and config.hollow_scale == "solid":
        return solid_scale_shell(source, config, data_dir)
    left_out: dict[str, int] = {}  # the parts left out of the volume the target is scaled to
    settled = False
    for round_ in range(1, USABLE_ROUNDS + 1):
        kept = {k: n for k, n in source.inventory.items() if k[0] not in left_out}
        volume = config.fill_slack * target_volume(kept, config.sizing)
        target = scaled_target(source, config, volume, data_dir)
        if config.sizing != "usable":
            return target, {"volume": volume} | joined(target)
        now = unusable(source.inventory, target.mask)
        if now == left_out:
            settled = True
            break
        if round_ == USABLE_ROUNDS:  # not settled: keep this target, sized without ``left_out``
            break
        left_out = now
    dropped = {k: n for k, n in source.inventory.items() if k[0] in left_out}
    return target, {"volume": volume, "left_out": left_out, "left_out_cells": target_volume(dropped, "fillable"),
                    "rounds": round_, "settled": settled} | joined(target)


def joined(target: Target) -> dict:
    """The sizing detail of a target that resampling cut into pieces: the cells added to join it
    (``shapes.reconnect``); nothing for a target that came out one piece."""
    return {"reconnected": target.reconnected} if target.reconnected else {}


def solid_scale_shell(source: Source, config: AltConfig, data_dir: Path,
                      solid: tuple[Target, dict] | None = None) -> tuple[Target, dict]:
    """The solid target, sized as without ``hollow`` (with its usable fixpoint), then hollowed at that scale
    (``shapes.hollow``: a ``hollow``-cell shell plus internal pillars): the same object as the solid one, with the
    interior's share of the part budget left over for the surface (M12c). Support columns are the solid's (the
    outside is unchanged; the pillars hold the shell over the void). The scale is not refit: parts that fit in the
    solid but nowhere in the shell are counted (``fit_nowhere``), not taken out of the volume. The details add, under
    "hollow": the thickness, the solid's and the shell's cells, the part budget (fillable cells of the parts not left
    out) and the parts that fit nowhere in the shell with their cells. ``solid``: the solid target and its details,
    if already sized (``sized_target`` with ``hollow=0``)."""
    config = resolve(config)
    solid_config = replace(config, hollow=0)
    solid, details = solid or sized_target(source, solid_config, data_dir)
    obj = solid.mask
    if solid_config.supports and takes_supports(config.shape):  # the object without its support columns
        obj = scaled_target(source, replace(solid_config, supports=False), details["volume"], data_dir).mask
        if obj.shape != solid.mask.shape or (obj & ~solid.mask).any():
            raise RuntimeError("the solid target without supports is not inside the solid target with them")
    mask = hollow(obj, config.hollow) | (solid.mask & ~obj)
    left_out = details.get("left_out", {})
    kept = {k: n for k, n in source.inventory.items() if k[0] not in left_out}
    nowhere = {name: n for name, n in unusable(source.inventory, mask).items() if name not in left_out}
    nowhere_parts = {k: n for k, n in source.inventory.items() if k[0] in nowhere}
    details = details | {"hollow": {
        "thickness": config.hollow, "scale": "solid", "solid_cells": int(solid.mask.sum()), "cells": int(mask.sum()),
        "removed": int(solid.mask.sum() - mask.sum()), "budget_cells": target_volume(kept, config.sizing),
        "fit_nowhere": nowhere, "fit_nowhere_cells": target_volume(nowhere_parts, "fillable")}}
    description = solid.description[:-1] + f", hollow {config.hollow} at the solid's scale)"
    return Target(mask, solid.preferred, description, solid.plane, solid.reconnected), details


def make_context(source: Source, stats: StyleStats, config: AltConfig, target: Target | None = None) -> Context:
    config = resolve(config)
    if target is None:
        grid = (cube_grid(inventory_cells(source.inventory), config.room) if config.height is None
                else grid_for(source.inventory, config.height, config.room))
        mask = preferred = None
        empty = config.room - 1
    else:
        mask, preferred = target.mask, target.preferred
        grid, empty = mask.shape, SHAPE_EMPTY_WEIGHT
    return Context(source.inventory, source.colors, stats, grid, mask, preferred, empty, config.strength,
                   config.generator, config.max_clutch, config.wfc_time_limit_s, config.balanced,
                   config.bridge, config.connect, config.connect_rounds, config.open_tops and target is not None,
                   config.order, config.proposal or "", config.skin and target is not None,
                   target.plane if target is not None and config.symmetric else None, config.skin_power,
                   config.holes, config.hang, config.reserve_small, config.small_last, config.regrow)


# Generation, resumable ---------------------------------------------------------------------------


def cache_key(source: Source, style_label: str, context: Context) -> dict:
    """What a cached candidate depends on (besides its seed); normalized through JSON."""
    key = {
        "source": source.name, "inventory": sorted([*k, v] for k, v in source.inventory.items()), "style": style_label,
        "grid": list(context.grid), "mask": None if context.mask is None else np.argwhere(context.mask).tolist(),
        "preferred": None if context.preferred is None else context.preferred.tolist(),
        "empty_weight_per_part": context.empty_weight_per_part, "strength": context.strength,
        "generator": context.generator, "balanced": context.balanced, "bridge": context.bridge,
        "connect": context.connect, "connect_rounds": context.connect_rounds, "verify_version": VERIFY_VERSION,
        "max_clutch": context.max_clutch,
        "wfc_time_limit_s": context.wfc_time_limit_s,
    }
    if context.generator == "d2":  # candidates built before version 2 (no field) are not reused
        key["builder_version"] = BUILDER_VERSION
    if context.open_tops:  # only when on, so caches from before the rule stay valid
        key["open_tops"] = True
    if context.order != "random":  # likewise
        key["order"] = context.order
    if context.skin:  # likewise
        key["skin"] = True
        if context.skin_power is not None:
            key["skin_power"] = context.skin_power
    if context.plane is not None:  # likewise
        key["plane"] = [context.plane.axis, context.plane.total]
    if context.holes:  # likewise
        key["holes"] = True
    if context.hang:  # likewise
        key["hang"] = True
    if context.reserve_small:  # likewise
        key["reserve_small"] = True
    if context.small_last is not None:  # likewise
        key["small_last"] = context.small_last
    if context.regrow:  # likewise
        key["regrow"] = True
    if context.proposal:  # the model by content, so retrained weights are not mixed with old candidates
        key["proposal"] = hashlib.sha256(Path(context.proposal).read_bytes()).hexdigest()[:16]
    return json.loads(json.dumps(key))


def load_cache(path: Path, key: dict) -> dict[int, Candidate]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or json.loads(lines[0]).get("key") != key:
        raise SystemExit(f"{path} holds candidates of a different setup; pass --fresh or choose another --out")
    candidates = (Candidate.from_json(json.loads(line)) for line in lines[1:] if line.strip())
    return {c.seed: c for c in candidates}


def generate_all(context: Context, seeds: Sequence[int], cache: Path, key: dict, workers: int) -> list[Candidate]:
    """Candidates for ``seeds``, reusing and extending ``cache``; returned in seed order."""
    done = load_cache(cache, key)
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"key": key}) + "\n", encoding="utf-8")
    pending = [s for s in seeds if s not in done]
    size = max(1, math.ceil(len(pending) / (workers * CHUNKS_PER_WORKER)))
    chunks = [pending[i : i + size] for i in range(0, len(pending), size)]
    with ProcessPoolExecutor(workers) if workers > 1 else InlineExecutor() as pool:
        futures = [pool.submit(generate, context, chunk) for chunk in chunks]
        for i, future in enumerate(futures):  # collected in seed order: the cache is the same for any worker count
            batch = future.result()
            with cache.open("a", encoding="utf-8") as f:
                f.writelines(json.dumps(c.to_json()) + "\n" for c in batch)
            done.update((c.seed, c) for c in batch)
            if (i + 1) % workers == 0 or i + 1 == len(futures):
                print(f"  generated {sum(s in done for s in seeds)}/{len(seeds)}", flush=True)
    return [done[s] for s in seeds]


# The rest of the funnel ----------------------------------------------------------------------------


def standardized(values: np.ndarray) -> np.ndarray:
    """z-scores (0 everywhere when the values are all equal)."""
    return (values - values.mean()) / (values.std() or 1.0)


def run_funnel(candidates: list[Candidate], context: Context, stats: StyleStats, config: AltConfig,
               generate_seconds: float) -> FunnelReport:
    stages = [StageStats("generate", sum("generate" not in c.failed for c in candidates), generate_seconds)]
    failures = dict(Counter(name for c in candidates for name in c.failed))

    clock = time.perf_counter()
    valid = [c for c in candidates if c.valid]
    found = {c.seed: events(c.placed) for c in valid}
    # With a target shape: how much of it each valid build fills and whether it meets the completeness bar, before
    # any floor, so that a floor never removes a complete build (M12c: the complete 5891-1 chair uses the fewest
    # parts of its run and the contact-event floor below cut it).
    filled_share: dict[int, float] = {}
    complete: dict[int, bool] = {}
    if context.mask is not None:
        bar = bar_of(config)
        for c in valid:
            filled = occupancy(c.placed, context.grid)
            filled_share[c.seed] = fill(filled, context.mask)
            complete[c.seed] = bar.met(completeness(filled, context.mask), filled_share[c.seed])
    # The smallest builds by contact events fail "too_small" (one tiny build cannot shrink every judge sample) unless
    # they meet the bar.
    floor = int(np.quantile([found[c.seed].count for c in valid], config.min_size_quantile, method="lower")) if valid else 0
    verified = [c for c in valid if found[c.seed].count >= floor or complete.get(c.seed, False)]
    if len(verified) < len(valid):
        failures["too_small"] = len(valid) - len(verified)
    # With a target shape: a fill floor relative to the best builds (and the absolute --min-fill), so a stub that
    # happens to match the style statistics is not selected over builds that fill the shape.
    if context.mask is not None and verified:
        fill_floor = max(config.fill_floor * float(np.quantile([filled_share[c.seed] for c in verified], 0.9)),
                         config.min_fill)
        kept = [c for c in verified if filled_share[c.seed] >= fill_floor or complete[c.seed]]
        if len(kept) < len(verified):
            failures["low_fill"] = len(verified) - len(kept)
        verified = kept
    # With complete-first, complete builds go first into dedupe (so a complete build is kept over an incomplete
    # near-duplicate) and are selected before the rest.
    if context.mask is not None:
        filled_share = {c.seed: filled_share[c.seed] for c in verified}
        complete = {c.seed: complete[c.seed] for c in verified}
        if config.complete_first:
            verified = sorted(verified, key=lambda c: not complete[c.seed])  # stable: seed order within each group
    stages.append(StageStats("verify", len(verified), time.perf_counter() - clock))

    clock = time.perf_counter()
    colors = [color.name for color in context.colors]
    features = np.array([feature_vector(c.placed, context.grid, colors) for c in verified])
    features = features.reshape(len(verified), features.shape[1] if verified else 0)
    kept = dedupe(features, config.dedupe_threshold)
    unique, features = [verified[i] for i in kept], features[kept]
    stages.append(StageStats("dedupe", len(unique), time.perf_counter() - clock))

    clock = time.perf_counter()
    size = min((found[c.seed].count for c in unique), default=0)
    scores = np.array([-matched_divergence(found[c.seed], size, stats, np.random.default_rng([0, c.seed]),
                                           config.judge_draws) for c in unique])
    stages.append(StageStats("judge", len(unique), time.perf_counter() - clock))

    clock = time.perf_counter()
    picks: list[int] = []
    if unique:
        z = standardized(scores)
        if filled_share and config.fill_weight:  # with a target: judge and fill, both standardized
            z = z + config.fill_weight * standardized(np.array([filled_share[c.seed] for c in unique]))
        distances = np.linalg.norm(features[:, None] - features[None, :], axis=-1)[np.triu_indices(len(unique), 1)]
        scale = float(np.median(distances)) if distances.size and np.median(distances) > 0 else 1.0
        tiers = np.array([complete[c.seed] for c in unique]) if complete and config.complete_first else None
        picks = select(z, features / scale, config.k, config.diversity, tiers)
    stages.append(StageStats("select", len(picks), time.perf_counter() - clock))
    selected = [Selected(unique[i], float(scores[i]), complete.get(unique[i].seed)) for i in picks]
    return FunnelReport(len(candidates), stages, failures, floor, size, selected, candidates,
                        sum(complete[c.seed] for c in unique) if context.mask is not None else None)


def real_model_judge(source: Source, stats: StyleStats, size: int, draws: int) -> tuple[float, int] | None:
    """The real model's judge (its on-grid parts, voxelized) at the builds' judge size, or at its own size
    if it is smaller; None without a model or with no on-grid parts."""
    if source.model is None:
        return None
    placed, _ = voxelize(flatten(source.model))
    if not placed:
        return None
    found = events(placed)
    if found.count == 0:
        return None
    return -matched_divergence(found, size, stats, np.random.default_rng([1]), draws), min(size, found.count)


# Output -----------------------------------------------------------------------------------------------


RECOLOR_STREAM = 7  # the recolouring's Generator: [build seed, this]


def recolor_selected(report: FunnelReport, context: Context) -> FunnelReport:
    """``report`` with each selected build recoloured within part types (``bricks.recolor``); placements, counts, the
    judge and the order are kept."""
    selected = []
    for chosen in report.selected:
        c = chosen.candidate
        done = recolor(c.placed, context.grid, np.random.default_rng([c.seed, RECOLOR_STREAM]))
        selected.append(replace(chosen, candidate=replace(c, placed=tuple(done.placed)), recolored={
            "seams_pct_before": 100 * done.before.same_color, "seams_pct_after": 100 * done.after.same_color,
            "colors_per_window_before": done.before.colors_per_window,
            "colors_per_window_after": done.after.colors_per_window, "swaps": done.swaps,
            "fixed_skin_pct": 100 * done.fixed_skin_share, "seconds": done.seconds}))
    return replace(report, selected=selected)


def write_outputs(source: Source, context: Context, report: FunnelReport, out: Path) -> list[dict]:
    rows, previews = [], []
    for rank, chosen in enumerate(report.selected, 1):
        c = chosen.candidate
        ldr, png = write_build(c.placed, context.grid, out / f"build_{rank:02d}",
                               f"Alternate build {rank} from {source.name} (seed {c.seed})", source.accessories)
        previews.append(png)
        row = {"rank": rank, "seed": c.seed, "ldr": ldr.name, "png": png.name, "parts": len(c.placed),
               "clusters": c.clusters,
               "steps": len(layer_steps(c.placed)), "judge": chosen.judge, "clutch": c.clutch,
               "utilization_pct": 100 * utilization(list(c.placed), source.inventory),
               "accessories": len(fit(c.placed, source.accessories)),
               "seconds": c.seconds, "physics_seconds": c.physics_seconds}
        if context.mask is not None:
            filled = occupancy(c.placed, context.grid)
            done = completeness(filled, context.mask)
            row.update(fill_pct=100 * fill(filled, context.mask), iou=iou(filled, context.mask), holes=done.holes,
                       largest_hole=done.largest_hole, surface_pct=100 * done.surface,
                       largest_surface_hole=done.largest_surface_hole, complete=chosen.complete)
        if chosen.recolored is not None:
            row["recolor"] = chosen.recolored
        rows.append(row)
    if previews:
        write_sheet(previews, out / "sheet.png")
    return rows


def format_selected(rows: list[dict]) -> str:
    shaped = bool(rows) and "fill_pct" in rows[0]
    lines = ["rank  seed  parts  used%   judge   clutch  steps"
             + ("  fill%  holes  largest  surface%  surf.hole  complete" if shaped else "")]
    lines += [f"{r['rank']:4d} {r['seed']:5d} {r['parts']:6d} {r['utilization_pct']:6.1f} {r['judge']:7.3f} "
              f"{r['clutch']:8.1f} {r['steps']:6d}"
              + (f" {r['fill_pct']:6.1f} {r['holes']:6d} {r['largest_hole']:8d} {r['surface_pct']:9.1f} "
                 f"{r['largest_surface_hole']:10d} {'yes' if r['complete'] else 'no':>9}" if shaped else "")
              for r in rows]
    return "\n".join(lines)


def valid_completeness(candidates: Sequence[Candidate], context: Context) -> dict | None:
    """Means over the valid candidates of fill, holes, largest hole and surface completeness (with a target)."""
    valid = [c for c in candidates if c.valid]
    if context.mask is None or not valid:
        return None
    rows = []
    for c in valid:
        filled = occupancy(c.placed, context.grid)
        done = completeness(filled, context.mask)
        rows.append((100 * fill(filled, context.mask), done.holes, done.largest_hole, 100 * done.surface))
    means = np.mean(rows, axis=0)
    return {"valid": len(valid), "fill_pct": means[0], "holes": means[1], "largest_hole": means[2],
            "surface_pct": means[3]}


def main(argv: Sequence[str] | None = None) -> int:
    defaults = AltConfig()
    parser = argparse.ArgumentParser(prog="python -m brickwfc.alt", description=__doc__.splitlines()[0])
    parser.add_argument("input", help="OMR set number (e.g. 6372-1), .mpd/.ldr model, or .csv parts list")
    parser.add_argument("--shape", help=f"target shape, scaled to the inventory's volume: one of {sorted(SHAPES)}, "
                        "a silhouette image, an .ldr/.mpd model or a set number, a BrickGPT structure "
                        "(brickgpt:<structure id> or a .txt in its format), or a watertight .obj/.stl/.ply/.off mesh")
    parser.add_argument("--height-map", help="grey image, same size as the silhouette: height in plates")
    parser.add_argument("--color-map", help="color image, same size as the silhouette: preferred colors")
    parser.add_argument("--shape-height", type=int, default=defaults.shape_height,
                        help="plates, for a silhouette without a height map")
    parser.add_argument("--shape-exact", action="store_true",
                        help="model shape: keep its exact cells (overhangs, rooms) instead of solid columns")
    parser.add_argument("--shape-columns", action="store_true",
                        help="3D target (brickgpt:<id>, .txt or mesh): solid columns (its heightfield) instead of its cells")
    parser.add_argument("--voxels", type=int, default=defaults.voxels,
                        help="mesh target: cells along its longest side before scaling (detail kept)")
    parser.add_argument("--mesh-up", choices=("y", "z"), default=defaults.mesh_up, help="mesh target: up axis")
    parser.add_argument("--hollow-scale", choices=HOLLOW_SCALES, default=defaults.hollow_scale,
                        help="with --hollow: shell (the shell is scaled to the inventory's volume: a larger object) or "
                        "solid (the solid target is sized, then hollowed: the same object, the interior's parts free)")
    parser.add_argument("--hollow", type=int, default=defaults.hollow,
                        help="3D target: a shell this many cells thick plus internal pillars (0: solid)")
    parser.add_argument("--no-open-tops", action="store_true",
                        help="with a target shape: let studless tops (tiles) sit under target cells (as before M12b 1d)")
    parser.add_argument("--supports", action=argparse.BooleanOptionalAction, default=defaults.supports,
                        help="3D target (a model, BrickGPT structure or mesh; not a primitive or silhouette): add "
                        "support columns under overhangs out of a part's reach (extra cells); on by default")
    parser.add_argument("--support-height", type=int, default=defaults.support_height,
                        help="with supports: only columns at most this many cells (plates) tall; 0: any height "
                        f"(default {defaults.support_height})")
    parser.add_argument("--order", choices=("random", "raster", "connected"), default=defaults.order,
                        help="d2: order the cells of a layer are visited in; connected: grow one piece from a seed on "
                        "the ground (with --hang, down to the ground by hanging; see bricks/bottomup.py)")
    parser.add_argument("--sizing", choices=SIZINGS, default=defaults.sizing,
                        help="target sizing: fillable (a slope counts its stud cells x 1 layer toward the volume, and "
                        "the scale keeps thin parts thick), box (as before) or usable (fillable, without the parts "
                        "that fit nowhere inside the scaled target; rescaled until those settle); default usable "
                        "with a 3D target, fillable otherwise")
    parser.add_argument("--fill-slack", type=float, default=defaults.fill_slack,
                        help="with a target: scale it to this share of the sizing's volume (1: as if every part "
                        "were used)")
    parser.add_argument("--proposal", help="d2: learned proposal model (.npz, vocab.json next to it; see training/)")
    parser.add_argument("--skin", action="store_true",
                        help="d2 with a target shape: try the largest parts first on the target's outer surface")
    parser.add_argument("--skin-power", type=float,
                        help="with --skin: a soft preference instead of largest first, choice weights x cells ** this")
    parser.add_argument("--symmetric", action="store_true",
                        help="d2 with a target shape: find its mirror plane, scale a 3D target so the plane survives, "
                        "and place each part's mirror image with it where it fits")
    parser.add_argument("--symmetrize-min-score", type=float, default=defaults.symmetrize_min_score,
                        help="with --symmetric: a mirror plane covering at least this share of the target makes it "
                        "exactly symmetric (adds the mirror image of its cells)")
    parser.add_argument("--holes", action=argparse.BooleanOptionalAction, default=defaults.holes,
                        help="d2: a hole-filling pass after the main pass and each connect round (every free target "
                        "cell, every remaining part, largest first); on by default with a 3D target")
    parser.add_argument("--hang", action=argparse.BooleanOptionalAction, default=defaults.hang,
                        help="with --holes: the hole pass may also hang a part from a part above by its studs "
                        "(fills the lowest layer of overhangs); on by default with a 3D target")
    parser.add_argument("--reserve-small", action="store_true",
                        help="d2: the main pass tries parts of at most 3 cells (1 x 1 to 1 x 3 plates and tiles, 1 x 1 "
                        "bricks, corner plates) only where no larger part fits, keeping them for the hole pass")
    parser.add_argument("--small-last", type=float, metavar="A",
                        help="d2: the main pass weighs parts of at most 3 cells down by (cells / 4) ** A (a soft "
                        "--reserve-small)")
    parser.add_argument("--regrow", action="store_true",
                        help="d2 with --order connected: when the growth stalls (covers under half the target), grow "
                        "again from the next ground region; keep the best attempt")
    parser.add_argument("--k", type=int, default=defaults.k, help="builds to select")
    parser.add_argument("--n", type=int, default=defaults.n, help="candidates to generate")
    parser.add_argument("--seed", type=int, default=defaults.seed)
    parser.add_argument("--generator", choices=GENERATORS, default=defaults.generator)
    parser.add_argument("--height", type=int, default=defaults.height,
                        help="grid height in plates (no --shape; default: a cube)")
    parser.add_argument("--no-balance", action="store_true", help="d2 without the tip-over check (as in M9b-M11)")
    parser.add_argument("--no-bridge", action="store_true", help="d2 without the preference for joining clusters")
    parser.add_argument("--no-connect", action="store_true", help="d2 without the pass that makes builds one piece")
    parser.add_argument("--connect-rounds", type=int, default=defaults.connect_rounds,
                        help="repair rounds of the connect pass (1: as in step 2b)")
    parser.add_argument("--room", type=float, default=defaults.room, help="grid volume / inventory volume (no --shape)")
    parser.add_argument("--strength", type=float, default=defaults.strength, help="exponent on the style weights")
    parser.add_argument("--max-clutch", type=float, default=defaults.max_clutch,
                        help="physics: most clutch per stud a build may need, in plate-cell weights "
                        f"(default {defaults.max_clutch:.0f}: real bricks; inf: no limit)")
    parser.add_argument("--wfc-time-limit", type=float, default=defaults.wfc_time_limit_s, help="seconds per WFC build")
    parser.add_argument("--min-size-quantile", type=float, default=defaults.min_size_quantile)
    parser.add_argument("--fill-floor", type=float, default=defaults.fill_floor,
                        help="target shape: fail builds filling less than this x the 90th-percentile fill (0: off)")
    parser.add_argument("--min-fill", type=float, default=defaults.min_fill,
                        help="target shape: also fail builds filling less than this share of it (absolute; 0: off)")
    parser.add_argument("--fill-weight", type=float, default=defaults.fill_weight,
                        help="target shape: selection score z(judge) + this x z(fill) (0: judge only)")
    parser.add_argument("--no-complete-first", action="store_true",
                        help="target shape: select by score only, not builds that meet the completeness bar first")
    parser.add_argument("--bar", choices=BARS, default=defaults.bar,
                        help="target shape: what complete means; volume: fill, largest hole and surface share; "
                        "surface: surface share and largest surface hole only (interior cells are invisible)")
    parser.add_argument("--complete-fill", type=float, default=defaults.complete_fill,
                        help=f"volume bar: least fill share (default {defaults.complete_fill})")
    parser.add_argument("--complete-hole", type=int, default=defaults.complete_hole,
                        help=f"bar: most cells in the largest hole, or surface hole (default {defaults.complete_hole})")
    parser.add_argument("--complete-surface", type=float, default=defaults.complete_surface,
                        help=f"bar: least filled share of the exposed cells (default {defaults.complete_surface})")
    parser.add_argument("--dedupe-threshold", type=float, default=defaults.dedupe_threshold)
    parser.add_argument("--diversity", type=float, default=defaults.diversity, help="lambda in selection")
    parser.add_argument("--recolor", action="store_true",
                        help="after select: permute each selected build's colours within part types for a coherent "
                        "skin (placements and part counts kept; the judge is the original build's)")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 3) - 2))
    parser.add_argument("--wfc-workers", type=int, default=2, help="worker cap for --generator wfc (memory-heavy)")
    parser.add_argument("--data", type=Path, default=DATA_DIR, help="OMR download cache")
    parser.add_argument("--style-dir", type=Path, default=STYLE_DIR)
    parser.add_argument("--style-version", choices=sorted(STYLE_FILES), default=STYLE_VERSION,
                        help="M10 style statistics: v1 (M8 catalog, M10-M12 tables) or v2 (relearned with slopes)")
    parser.add_argument("--catalog", choices=sorted(CATALOGS), default="full",
                        help="parts the inventory is read with: full (corners, slopes) or m8 (before M12b)")
    parser.add_argument("--sets-file", type=Path, default=SETS_FILE)
    parser.add_argument("--out", type=Path, help="output directory (default out/alt/<input name>)")
    parser.add_argument("--fresh", action="store_true", help="discard cached candidates")
    args = parser.parse_args(argv)
    if args.generator != "d2" and (args.proposal or args.order != "random" or args.skin or args.symmetric
                                   or args.holes or args.hang or args.reserve_small or args.small_last is not None):
        parser.error("--order, --proposal, --skin, --symmetric, --holes, --hang, --reserve-small and --small-last "
                     "apply to --generator d2 only")
    if args.regrow and args.order != "connected":
        parser.error("--regrow goes with --order connected")
    if args.reserve_small and args.small_last is not None:
        parser.error("--reserve-small and --small-last are alternatives")
    if args.skin_power is not None and not args.skin:
        parser.error("--skin-power goes with --skin")

    start = time.perf_counter()
    config = resolve(AltConfig(
        n=args.n, k=args.k, seed=args.seed, generator=args.generator, height=args.height, room=args.room,
        balanced=not args.no_balance, bridge=not args.no_balance and not args.no_bridge,
        connect=not args.no_connect, connect_rounds=args.connect_rounds,
        shape=args.shape, height_map=args.height_map, color_map=args.color_map, shape_height=args.shape_height,
        shape_exact=args.shape_exact, shape_columns=args.shape_columns, voxels=args.voxels, mesh_up=args.mesh_up,
        hollow=args.hollow, hollow_scale=args.hollow_scale, supports=args.supports, support_height=args.support_height, open_tops=not args.no_open_tops,
        order=args.order, proposal=args.proposal, skin=args.skin, skin_power=args.skin_power,
        symmetric=args.symmetric, symmetrize_min_score=args.symmetrize_min_score, sizing=args.sizing,
        fill_slack=args.fill_slack,
        holes=args.holes, hang=args.hang, reserve_small=args.reserve_small, small_last=args.small_last,
        regrow=args.regrow,
        strength=args.strength, max_clutch=args.max_clutch, wfc_time_limit_s=args.wfc_time_limit,
        min_size_quantile=args.min_size_quantile, fill_floor=args.fill_floor, min_fill=args.min_fill, fill_weight=args.fill_weight,
        complete_first=not args.no_complete_first, bar=args.bar, complete_fill=args.complete_fill,
        complete_hole=args.complete_hole, complete_surface=args.complete_surface,
        dedupe_threshold=args.dedupe_threshold, diversity=args.diversity, recolor=args.recolor,
    ))
    if config.hang and not config.holes:
        parser.error("--hang goes with --holes")
    source = load_source(args.input, args.data, catalog=args.catalog)
    stats, style_label = learned_style(source.name, args.style_dir, args.sets_file, args.style_version)
    out = args.out or Path("out/alt") / source.name
    ignored_top = sorted(source.ignored.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    print(f"{source.name}: {source.recognized_parts} parts recognized, {source.ignored_parts} ignored"
          + (f" (most common: {', '.join(f'{p} x{n}' for p, n in ignored_top[:5])})" if ignored_top else ""))
    if source.accessories:
        print(f"{sum(source.accessories.values())} glass, panes and doors go into frames (no cells of their own)")
    print(f"style: {style_label}")

    target, sizing = sized_target(source, config, args.data)
    if target is not None:
        print(f"shape: {target.description}, {int(target.mask.sum())} cells, grid {target.mask.shape} (Y, Z, X)")
    if sizing.get("reconnected"):
        print(f"reconnected: {sizing['reconnected']} cells added to join the scaled target into one piece")
    if sizing.get("left_out"):
        print(f"usable sizing: left out {sizing['left_out_cells']} cells of parts that fit nowhere in the target "
              f"({', '.join(f'{name} x{n}' for name, n in sizing['left_out'].items())}), {sizing['rounds']} rounds")
    if shell := sizing.get("hollow"):
        nowhere = ", ".join(f"{name} x{n}" for name, n in shell["fit_nowhere"].items()) or "none"
        print(f"hollow {shell['thickness']} at the solid's scale: {shell['cells']} of {shell['solid_cells']} cells kept "
              f"({shell['removed']} removed); part budget {shell['budget_cells']} cells, "
              f"{shell['budget_cells'] - shell['cells']} more than the shell; fit nowhere in the shell: "
              f"{shell['fit_nowhere_cells']} cells ({nowhere})")
    context = make_context(source, stats, config, target)
    cache = out / "candidates.jsonl"
    if args.fresh and cache.exists():
        cache.unlink()
    workers = min(args.workers, args.wfc_workers) if config.generator == "wfc" else args.workers
    clock = time.perf_counter()
    seeds = range(config.seed, config.seed + config.n)
    candidates = generate_all(context, seeds, cache, cache_key(source, style_label, context), workers)
    report = run_funnel(candidates, context, stats, config, time.perf_counter() - clock)
    real = real_model_judge(source, stats, report.judge_size, config.judge_draws)
    if config.recolor:
        report = recolor_selected(report, context)
    rows = write_outputs(source, context, report, out)
    print(format_stages(report.requested, report.stages, report.check_failures))
    for row in rows:
        if "recolor" in row:
            r = row["recolor"]
            print(f"recolor build {row['rank']}: same-colour seams {r['seams_pct_before']:.0f}% -> "
                  f"{r['seams_pct_after']:.0f}%, colours per 4x4 window {r['colors_per_window_before']:.2f} -> "
                  f"{r['colors_per_window_after']:.2f} ({r['swaps']} swaps, {r['seconds']:.1f} s)")
    if report.complete is not None:
        print(f"select: {'complete first' if config.complete_first else 'score only (--no-complete-first)'}, "
              f"{bar_of(config).describe()}; {report.complete} of {report.stages[2].survivors} unique builds complete")
    print(format_selected(rows))
    complete = valid_completeness(candidates, context)
    if complete is not None:
        print(f"valid builds ({complete['valid']}), means: fill {complete['fill_pct']:.1f}%, holes {complete['holes']:.1f} "
              f"(largest {complete['largest_hole']:.0f} cells), surface {complete['surface_pct']:.1f}%")

    clutches = [c.clutch for c in candidates if not math.isnan(c.clutch)]
    stats_json = {
        "input": {"name": source.name, "recognized_parts": source.recognized_parts,
                  "accessories": sum(source.accessories.values()),
                  "ignored_parts": source.ignored_parts, "ignored_top": ignored_top,
                  "colors": [c.name for c in source.colors], "inventory_cells": inventory_cells(source.inventory)},
        "style": style_label, "config": asdict(config), "grid_YZX": list(context.grid),
        "shape": None if target is None else target.description,
        "shape_cells": None if context.mask is None else int(context.mask.sum()), "sizing": sizing,
        "requested": report.requested, "stages": [asdict(s) for s in report.stages],
        "check_failures": report.check_failures, "size_floor_events": report.size_floor,
        "judge_size_events": report.judge_size,
        "real_model_judge": None if real is None else {"judge": real[0], "events": real[1]},
        "generation_cpu_s": sum(c.seconds for c in candidates),
        "physics_cpu_s": sum(c.physics_seconds for c in candidates),
        "physics_checked": len(clutches), "physics_stable": sum(math.isfinite(v) for v in clutches),
        "clusters_per_build_median": float(np.median([c.clusters for c in candidates])),
        "connected": sum(c.clusters == 1 for c in candidates),
        "valid_completeness": complete,
        "complete_unique": report.complete,
        "wall_time_s": time.perf_counter() - start,
        "selected": rows,
    }
    (out / "stats.json").write_text(json.dumps(stats_json, indent=2), encoding="utf-8")
    print(f"wrote {len(rows)} builds, sheet.png and stats.json to {out}")
    return 0 if rows else 1
