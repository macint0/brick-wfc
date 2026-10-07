"""Core 2D Wave Function Collapse solver (spec: CLAUDE.md, "Core WFC spec").

One *attempt* runs observe -> collapse -> propagate until every cell holds exactly one tile,
or a domain empties (contradiction). A *run* retries attempts with fresh seeds until one succeeds.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from brickwfc.tileset import OFFSETS, Tileset

logger = logging.getLogger(__name__)

Cell = tuple[int, int]

# Scale of the seeded noise added to entropies so ties are broken randomly, not by scan order.
TIE_BREAK_NOISE = 1e-6
DEFAULT_MAX_ATTEMPTS = 100


class Wave:
    """Per-cell domains for one attempt: ``domain[y, x, t]`` is True while tile ``t`` is still possible."""

    def __init__(self, tileset: Tileset, height: int, width: int) -> None:
        if height < 1 or width < 1:
            raise ValueError(f"grid must be at least 1x1, got {width}x{height}")
        self.tileset = tileset
        self.domain = np.ones((height, width, tileset.num_tiles), dtype=bool)
        self._w = tileset.weights
        self._w_log_w = tileset.weights * np.log(tileset.weights)

    @property
    def shape(self) -> tuple[int, int]:
        return self.domain.shape[0], self.domain.shape[1]

    def counts(self) -> np.ndarray:
        """Number of remaining tiles per cell, shape (H, W)."""
        return self.domain.sum(axis=2)

    def is_done(self) -> bool:
        return bool(np.all(self.counts() == 1))

    def entropy(self) -> np.ndarray:
        """Weighted Shannon entropy per cell: H = log(sum w) - sum(w log w) / sum(w)."""
        sum_w = self.domain @ self._w
        sum_w_log_w = self.domain @ self._w_log_w
        return np.log(sum_w) - sum_w_log_w / sum_w

    def observe(self, rng: np.random.Generator) -> Cell | None:
        """Return the uncollapsed cell with the lowest entropy, or None if every cell is collapsed."""
        uncollapsed = self.counts() > 1
        if not uncollapsed.any():
            return None
        h = self.entropy() + TIE_BREAK_NOISE * rng.random(self.shape)
        h[~uncollapsed] = np.inf
        y, x = np.unravel_index(np.argmin(h), h.shape)
        return int(y), int(x)

    def collapse(self, cell: Cell, rng: np.random.Generator) -> int:
        """Fix ``cell`` to one remaining tile, sampled with probability proportional to its weight."""
        p = self._w * self.domain[cell]
        tile = int(rng.choice(len(p), p=p / p.sum()))
        self.assign(cell, tile)
        return tile

    def assign(self, cell: Cell, tile: int) -> None:
        """Restrict ``cell`` to the single tile ``tile`` (does not propagate)."""
        self.domain[cell] = False
        self.domain[cell + (tile,)] = True

    def propagate(self, start: Iterable[Cell]) -> bool:
        """AC-3 style propagation outward from ``start``.

        Pop a cell; in each neighbor, remove tiles not supported by any tile remaining in the
        popped cell; if a neighbor's domain shrank, push it. Returns False on contradiction.
        """
        height, width = self.shape
        compat = self.tileset.compat
        queue = deque(start)
        while queue:
            y, x = queue.popleft()
            here = self.domain[y, x]
            for d, (dy, dx) in enumerate(OFFSETS):
                ny, nx = y + dy, x + dx
                if not (0 <= ny < height and 0 <= nx < width):
                    continue
                supported = compat[d, here].any(axis=0)
                before = self.domain[ny, nx]
                after = before & supported
                if np.array_equal(after, before):
                    continue
                self.domain[ny, nx] = after
                if not after.any():
                    return False
                queue.append((ny, nx))
        return True

    def to_grid(self) -> np.ndarray:
        """Tile id per cell, shape (H, W). Only valid once every cell is collapsed."""
        if not self.is_done():
            raise RuntimeError("wave is not fully collapsed")
        return self.domain.argmax(axis=2)


@dataclass(frozen=True)
class AttemptResult:
    grid: np.ndarray | None  # None on contradiction
    collapses: int  # observe+collapse steps taken before finishing or failing


def solve_attempt(tileset: Tileset, height: int, width: int, rng: np.random.Generator) -> AttemptResult:
    """Run a single WFC attempt with no backtracking."""
    wave = Wave(tileset, height, width)
    # Initial pass prunes tiles that can never be supported (e.g. a tile with no allowed neighbor).
    all_cells = [(y, x) for y in range(height) for x in range(width)]
    if not wave.propagate(all_cells):
        return AttemptResult(None, 0)
    collapses = 0
    while (cell := wave.observe(rng)) is not None:
        wave.collapse(cell, rng)
        collapses += 1
        if not wave.propagate([cell]):
            return AttemptResult(None, collapses)
    return AttemptResult(wave.to_grid(), collapses)


@dataclass(frozen=True)
class RunStats:
    """Per-run metrics (later reported in the paper)."""

    seed: int
    success: bool
    attempts: int
    contradictions: int
    cells_collapsed: int  # observe+collapse steps summed over all attempts
    wall_time_s: float


@dataclass(frozen=True)
class RunResult:
    grid: np.ndarray | None  # None if every attempt hit a contradiction
    stats: RunStats


def attempt_rng(seed: int, attempt: int) -> np.random.Generator:
    """RNG for attempt ``attempt`` of the run with base seed ``seed``.

    Keyed on the pair (seed, attempt) rather than ``seed + attempt`` so that a restart in run
    ``s`` never replays the first attempt of run ``s + 1``; runs with different seeds stay independent.
    """
    return np.random.default_rng([seed, attempt])


def run(
    tileset: Tileset,
    height: int,
    width: int,
    seed: int,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> RunResult:
    """Generate one grid, restarting with the next attempt seed on contradiction."""
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")
    start = time.perf_counter()
    cells_collapsed = 0
    for attempt in range(max_attempts):
        result = solve_attempt(tileset, height, width, attempt_rng(seed, attempt))
        cells_collapsed += result.collapses
        if result.grid is not None:
            stats = RunStats(seed, True, attempt + 1, attempt, cells_collapsed, time.perf_counter() - start)
            logger.info("run %s", stats)
            return RunResult(result.grid, stats)
        logger.debug("seed %d attempt %d: contradiction after %d collapses", seed, attempt, result.collapses)
    stats = RunStats(seed, False, max_attempts, max_attempts, cells_collapsed, time.perf_counter() - start)
    logger.info("run %s", stats)
    return RunResult(None, stats)


def adjacency_violations(grid: np.ndarray, tileset: Tileset) -> int:
    """Count neighboring cell pairs whose tiles are not allowed to touch.

    Only east and south neighbors are checked, so each pair is counted once; north/west follow
    from the symmetry that ``Tileset`` validates.
    """
    compat = tileset.compat
    east_ok = compat[1, grid[:, :-1], grid[:, 1:]]
    south_ok = compat[2, grid[:-1, :], grid[1:, :]]
    return int((~east_ok).sum() + (~south_ok).sum())
