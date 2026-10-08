"""Generate and verify candidate builds (the funnel's first two stages), one seed per candidate.

Generators: ``d2`` (default), the bottom-up builder with any-offset placement and the learned style bias;
``wfc``, WFC with the support, inventory (and shape) constraints, backtracking, the same bias and a time
cap (a compared method, see CLAUDE.md). Both use the same styled tileset.

Checks, in order: ``integrity`` (every part whole, nothing on a tile), ``inventory`` (no part overused),
``support`` (every part rests on a stud), ``shape`` (nothing outside the target shape), and, only for
builds that pass those, ``physics`` (finite required clutch per stud on a table, at most ``max_clutch``).
A seed with no build fails ``generate``.

Candidates are generated in chunks of seeds, one chunk per worker job; each job builds its own tileset
(too large to send to every job), and every seed has its own ``Generator``, so results do not depend on
the chunking. Candidates serialize to JSON lines, so a killed run resumes where it stopped.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.colors import BrickColor, color_for_code
from brickwfc.bricks.inventory import Inventory, InventoryConstraint, overuse
from brickwfc.bricks.parts import CATALOG, PartSet, PlacedPart, Shape, extract_parts
from brickwfc.bricks.physics import required_clutch
from brickwfc.bricks.shapes import Mask, ShapeConstraint, outside
from brickwfc.bricks.stability import SupportConstraint
from brickwfc.bricks.style import StyleBias, StyleStats, styled_tileset
from brickwfc.bricks.support import is_stable
from brickwfc.wfc import run

GENERATORS = ("d2", "wfc")
CHECKS = ("generate", "integrity", "inventory", "support", "shape", "physics")
WFC_MAX_ATTEMPTS, WFC_MAX_BACKTRACKS = 20, 1000


@dataclass(frozen=True)
class Context:
    """Everything a worker needs to generate candidates (picklable and small)."""

    inventory: Inventory
    colors: tuple[BrickColor, ...]
    stats: StyleStats
    grid: tuple[int, int, int]  # (Y, Z, X)
    mask: Mask | None  # target shape, grid-shaped
    empty_weight_per_part: float
    strength: float = 1.0
    generator: str = "d2"
    max_clutch: float = math.inf
    wfc_time_limit_s: float = 30.0


@dataclass(frozen=True)
class Candidate:
    seed: int
    placed: tuple[PlacedPart, ...]
    failed: tuple[str, ...]  # names of the checks it failed (see CHECKS); empty = valid
    clutch: float  # required clutch per stud on a table; nan if physics was not checked
    seconds: float  # generation time
    physics_seconds: float

    @property
    def valid(self) -> bool:
        return not self.failed

    def to_json(self) -> dict:
        parts = [[p.shape.part.name, int(p.shape.rotated), p.color.ldraw, p.layer, p.x, p.z] for p in self.placed]
        return {"seed": self.seed, "failed": list(self.failed), "clutch": self.clutch, "seconds": self.seconds,
                "physics_seconds": self.physics_seconds, "placed": parts}

    @classmethod
    def from_json(cls, data: dict) -> "Candidate":
        placed = tuple(PlacedPart(Shape(CATALOG[name], bool(rotated)), color_for_code(code), layer, x, z)
                       for name, rotated, code, layer, x, z in data["placed"])
        return cls(data["seed"], placed, tuple(data["failed"]), data["clutch"], data["seconds"], data["physics_seconds"])


def build(context: Context, parts: PartSet, bias: StyleBias, seed: int) -> np.ndarray | None:
    """One grid of tile ids for ``seed``, or None if the generator gave up."""
    if context.generator == "d2":
        builder = BottomUpBuilder(parts, any_offset=True, style=bias)
        return builder.build(context.grid, np.random.default_rng(seed), context.inventory, allowed=context.mask)
    constraints = [SupportConstraint(parts), InventoryConstraint(parts, context.inventory)]
    if context.mask is not None:
        constraints.append(ShapeConstraint(parts, context.mask))
    result = run(parts.tileset, context.grid, seed, WFC_MAX_ATTEMPTS, constraints, WFC_MAX_BACKTRACKS,
                 context.wfc_time_limit_s, bias.for_tiles)
    return result.grid


def verify(context: Context, parts: PartSet, grid: np.ndarray) -> tuple[list[PlacedPart], list[str], float, float]:
    """(placed parts, failed checks, required clutch or nan, physics seconds)."""
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
        clutch = required_clutch(placed, grid.shape)
        seconds = time.perf_counter() - start
        if not (math.isfinite(clutch) and clutch <= context.max_clutch):
            failed.append("physics")
    return placed, failed, clutch, seconds


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
        placed, failed, clutch, physics_seconds = verify(context, parts, grid)
        candidates.append(Candidate(seed, tuple(placed), tuple(failed), clutch, seconds, physics_seconds))
    return candidates
