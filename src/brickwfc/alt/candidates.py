"""Generate and verify candidate builds (the funnel's first two stages), one seed per candidate.

Generators: ``d2`` (default), the bottom-up builder with any-offset placement, the learned style bias and
the tip-over check (``balance``; off with ``balanced=False``), cells of a layer visited in random or raster
order (``order``) and optionally a learned proposal model (``proposal``, see ``bricks.proposal``);
``wfc``, WFC with the support, inventory (and shape) constraints, backtracking, the same bias and a time
cap (a compared method, see CLAUDE.md). Both use the same styled tileset, and both put parts of a
column's preferred color (from a color image, ``target.py``) first.

Checks, in order: ``integrity`` (every part whole, nothing on a tile), ``inventory`` (no part overused),
``support`` (every part rests on a stud), ``shape`` (nothing outside the target shape), and, only for
builds that pass those, ``physics`` (finite required clutch per stud on a table, at most ``max_clutch``),
and ``disconnected`` (the build is more than one cluster of stud-connected parts, so it falls apart when
lifted; ``balance.clusters``).
A seed with no build fails ``generate``.

Candidates are generated in chunks of seeds, one chunk per worker job; each job builds its own tileset
(too large to send to every job), and every seed has its own ``Generator``, so results do not depend on
the chunking. Candidates serialize to JSON lines, so a killed run resumes where it stopped.
"""

from __future__ import annotations

import functools
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from brickwfc.bricks.balance import clusters
from brickwfc.bricks.bottomup import PREFERRED_BOOST, BottomUpBuilder
from brickwfc.bricks.colors import BrickColor, color_for_code
from brickwfc.bricks.inventory import Inventory, InventoryConstraint, overuse
from brickwfc.bricks.parts import CATALOG, PartSet, PlacedPart, Shape, extract_parts
from brickwfc.bricks.physics import table_clutch
from brickwfc.bricks.proposal import Proposal
from brickwfc.bricks.shapes import Mask, ShapeConstraint, outside
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.style import StyleBias, StyleStats, styled_tileset
from brickwfc.bricks.symmetry import Plane
from brickwfc.bricks.support import is_stable
from brickwfc.wfc import Bias, run

GENERATORS = ("d2", "wfc")
CHECKS = ("generate", "integrity", "inventory", "support", "shape", "physics", "disconnected")
VERIFY_VERSION = 3  # bump when the checks change, so cached candidates are not reused
WFC_MAX_ATTEMPTS, WFC_MAX_BACKTRACKS = 20, 1000


@dataclass(frozen=True)
class Context:
    """Everything a worker needs to generate candidates (picklable and small)."""

    inventory: Inventory
    colors: tuple[BrickColor, ...]
    stats: StyleStats
    grid: tuple[int, int, int]  # (Y, Z, X)
    mask: Mask | None  # target shape, grid-shaped
    preferred: np.ndarray | None  # (Z, X) preferred color names, "" for none
    empty_weight_per_part: float
    strength: float = 1.0
    generator: str = "d2"
    max_clutch: float = math.inf
    wfc_time_limit_s: float = 30.0
    balanced: bool = True  # d2: refuse parts that would tip their cluster over
    bridge: bool = True  # d2 (with balanced): prefer placements that join clusters
    connect: bool = True  # d2: repair pass that makes the build one piece (see bottomup)
    connect_rounds: int = 10
    open_tops: bool = False  # d2: studless top cells only under empty target cells (see bottomup)
    order: str = "random"  # d2: cells of a layer visited in "random" or "raster" order
    proposal: str = ""  # d2: a learned proposal model (.npz, vocab.json next to it); "" for none
    skin: bool = False  # d2: largest parts first on the target's skin (M12b step 3, see bottomup)
    plane: Plane | None = None  # d2: symmetric decoding across this mirror plane (M12b step 3)


@dataclass(frozen=True)
class Candidate:
    seed: int
    placed: tuple[PlacedPart, ...]
    failed: tuple[str, ...]  # names of the checks it failed (see CHECKS); empty = valid
    clutch: float  # required clutch per stud on a table; nan if physics was not checked
    seconds: float  # generation time
    physics_seconds: float
    clusters: int = 0  # clusters of stud-connected parts (1 = one liftable piece)

    @property
    def valid(self) -> bool:
        return not self.failed

    def to_json(self) -> dict:
        parts = [[p.shape.part.name, p.shape.turn, p.color.ldraw, p.layer, p.x, p.z] for p in self.placed]
        return {"seed": self.seed, "failed": list(self.failed), "clutch": self.clutch, "seconds": self.seconds,
                "physics_seconds": self.physics_seconds, "clusters": self.clusters, "placed": parts}

    @classmethod
    def from_json(cls, data: dict) -> "Candidate":
        placed = tuple(PlacedPart(Shape(CATALOG[name], turn), color_for_code(code), layer, x, z)
                       for name, turn, code, layer, x, z in data["placed"])
        count = data["clusters"] if "clusters" in data else len(clusters(placed))  # older caches lack it
        return cls(data["seed"], placed, tuple(data["failed"]), data["clutch"], data["seconds"], data["physics_seconds"],
                   count)


@functools.lru_cache(maxsize=2)
def load_proposal(path: str) -> Proposal:
    """The model at ``path``, loaded once per process."""
    return Proposal.load(Path(path))


def build(context: Context, parts: PartSet, bias: StyleBias, seed: int) -> np.ndarray | None:
    """One grid of tile ids for ``seed``, or None if the generator gave up."""
    if context.generator == "d2":
        builder = BottomUpBuilder(parts, any_offset=True, style=bias, balanced=context.balanced,
                                  bridge=context.bridge, connect=context.connect,
                                  connect_rounds=context.connect_rounds, open_tops=context.open_tops,
                                  order=context.order,
                                  proposal=load_proposal(context.proposal) if context.proposal else None,
                                  skin=context.skin)
        return builder.build(context.grid, np.random.default_rng(seed), context.inventory, context.mask,
                             context.preferred, context.plane)
    constraints = [SupportConstraint(parts), InventoryConstraint(parts, context.inventory)]
    if context.mask is not None:
        constraints.append(ShapeConstraint(parts, context.mask))
    result = run(parts.tileset, context.grid, seed, WFC_MAX_ATTEMPTS, constraints, WFC_MAX_BACKTRACKS,
                 context.wfc_time_limit_s, wfc_bias(parts, bias, context.preferred))
    return result.grid


def wfc_bias(parts: PartSet, bias: StyleBias, preferred: np.ndarray | None) -> Bias:
    """The style bias, times ``PREFERRED_BOOST`` for tiles of the cell's preferred color."""
    if preferred is None:
        return bias.for_tiles
    tile_colors = np.array([info.color.name if info.solid else "" for info in parts.infos])

    def weights(domain: np.ndarray, cell: tuple[int, int, int]) -> np.ndarray:
        w = bias.for_tiles(domain, cell)
        name = preferred[cell[1], cell[2]]
        return w * np.where(tile_colors == name, PREFERRED_BOOST, 1.0) if name else w

    return weights


def verify(context: Context, parts: PartSet, grid: np.ndarray) -> tuple[list[PlacedPart], list[str], float, float, int]:
    """(placed parts, failed checks, required clutch or nan, physics seconds, number of clusters)."""
    placed, errors = extract_parts(grid, parts)
    filled = parts.solid[grid]
    failed = []
    if errors:
        failed.append("integrity")
    if overuse(placed, context.inventory):
        failed.append("inventory")
    if not is_stable(placed, filled):
        failed.append("support")
    if context.mask is not None and outside(filled, context.mask):
        failed.append("shape")
    clutch, seconds = math.nan, 0.0
    if not failed:
        start = time.perf_counter()
        clutch = table_clutch(placed, grid.shape)
        seconds = time.perf_counter() - start
        if not (math.isfinite(clutch) and clutch <= context.max_clutch):
            failed.append("physics")
    count = len(clusters(placed))
    if count != 1:
        failed.append("disconnected")
    return placed, failed, clutch, seconds, count


def generate(context: Context, seeds: Sequence[int]) -> list[Candidate]:
    parts = styled_tileset(context.inventory, context.colors, context.empty_weight_per_part, context.stats)
    bias = StyleBias(context.stats, parts, context.strength)
    candidates = []
    for seed in seeds:
        start = time.perf_counter()
        grid = build(context, parts, bias, seed)
        seconds = time.perf_counter() - start
        if grid is None:
            candidates.append(Candidate(seed, (), ("generate",), math.nan, seconds, 0.0))
            continue
        placed, failed, clutch, physics_seconds, count = verify(context, parts, grid)
        candidates.append(Candidate(seed, tuple(placed), tuple(failed), clutch, seconds, physics_seconds, count))
    return candidates
