"""Core Wave Function Collapse solver for 2D and 3D grids (spec: CLAUDE.md, "Core WFC spec").

One *attempt* runs observe -> collapse -> propagate until every cell holds exactly one tile,
or a domain empties (contradiction). A *run* retries attempts with fresh seeds until one succeeds.

Beyond pairwise adjacency, optional ``Constraint`` objects can prune domains during propagation
(e.g. the part-support constraint in ``bricks/stability.py``).
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence

import numpy as np

from brickwfc.tileset import Tileset, neighbor_pairs

logger = logging.getLogger(__name__)

Cell = tuple[int, ...]
Shape = tuple[int, ...]

# Scale of the seeded noise added to entropies so ties are broken randomly, not by scan order.
TIE_BREAK_NOISE = 1e-6
DEFAULT_MAX_ATTEMPTS = 100


class Constraint(Protocol):
    """A non-pairwise constraint enforced during propagation."""

    def prune(self, wave: Wave, changed: set[Cell]) -> list[Cell] | None:
        """Remove tiles that the constraint rules out, given the cells whose domains just changed.

        Returns the cells it shrank (they are propagated further), or None on contradiction.
        """
        ...


class Wave:
    """Per-cell domains for one attempt: ``domain[*cell, t]`` is True while tile ``t`` is still possible.

    ``cell`` is ``(y, x)`` on a 2D grid and ``(y, z, x)`` on a 3D grid (see ``tileset.Topology``).
    """

    def __init__(self, tileset: Tileset, shape: Shape, constraints: Sequence[Constraint] = ()) -> None:
        if len(shape) != tileset.topology.ndim or min(shape) < 1:
            raise ValueError(f"shape {shape} does not fit a {tileset.topology.ndim}D tileset")
        self.tileset = tileset
        self.constraints = tuple(constraints)
        self.domain = np.ones((*shape, tileset.num_tiles), dtype=bool)
        # Cells on the grid boundary may only hold tiles allowed to face that boundary.
        for d, offset in enumerate(tileset.topology.offsets):
            axis = next(i for i, o in enumerate(offset) if o != 0)
            face = [slice(None)] * len(shape)
            face[axis] = -1 if offset[axis] > 0 else 0
            self.domain[tuple(face)] &= tileset.border[d]
        self._w = tileset.weights
        self._w_log_w = tileset.weights * np.log(tileset.weights)

    @property
    def shape(self) -> Shape:
        return self.domain.shape[:-1]

    def counts(self) -> np.ndarray:
        """Number of remaining tiles per cell."""
        return self.domain.sum(axis=-1)

    def has_contradiction(self) -> bool:
        return not self.domain.any(axis=-1).all()

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
        return tuple(int(i) for i in np.unravel_index(np.argmin(h), h.shape))

    def collapse(self, cell: Cell, rng: np.random.Generator) -> int:
        """Fix ``cell`` to one remaining tile, sampled with probability proportional to its weight."""
        p = self._w * self.domain[cell]
        tile = int(rng.choice(len(p), p=p / p.sum()))
        self.assign(cell, tile)
        return tile

    def assign(self, cell: Cell, tile: int) -> None:
        """Restrict ``cell`` to the single tile ``tile`` (does not propagate)."""
        self.domain[cell] = False
        self.domain[(*cell, tile)] = True

    def settle(self, start: Iterable[Cell]) -> bool:
        """Propagate adjacency from ``start``, then let each constraint prune, until nothing changes.

        Returns False on contradiction.
        """
        pending = list(start)
        while pending:
            changed = set(pending)
            if not self.propagate(pending, changed):
                return False
            pending = []
            for constraint in self.constraints:
                pruned = constraint.prune(self, changed)
                if pruned is None:
                    return False
                pending.extend(pruned)
        return True

    def propagate(self, start: Iterable[Cell], changed: set[Cell] | None = None) -> bool:
        """AC-3 style propagation outward from ``start``.

        Pop a cell; in each neighbor, remove tiles not supported by any tile remaining in the
        popped cell; if a neighbor's domain shrank, push it. Shrunk cells are added to
        ``changed`` when given. Returns False on contradiction.
        """
        shape = self.shape
        compat = self.tileset.compat
        offsets = self.tileset.topology.offsets
        queue = deque(start)
        while queue:
            cell = queue.popleft()
            here = self.domain[cell]
            for d, offset in enumerate(offsets):
                neighbor = tuple(c + o for c, o in zip(cell, offset))
                if not all(0 <= n < size for n, size in zip(neighbor, shape)):
                    continue
                supported = compat[d, here].any(axis=0)
                before = self.domain[neighbor]
                after = before & supported
                if np.array_equal(after, before):
                    continue
                self.domain[neighbor] = after
                if not after.any():
                    return False
                queue.append(neighbor)
                if changed is not None:
                    changed.add(neighbor)
        return True

    def to_grid(self) -> np.ndarray:
        """Tile id per cell, same shape as the grid. Only valid once every cell is collapsed."""
        if not self.is_done():
            raise RuntimeError("wave is not fully collapsed")
        return self.domain.argmax(axis=-1)


@dataclass(frozen=True)
class AttemptResult:
    grid: np.ndarray | None  # None on contradiction
    collapses: int  # observe+collapse steps taken before finishing or failing


def solve_attempt(
    tileset: Tileset, shape: Shape, rng: np.random.Generator, constraints: Sequence[Constraint] = ()
) -> AttemptResult:
    """Run a single WFC attempt with no backtracking."""
    wave = Wave(tileset, shape, constraints)
    # Initial pass prunes tiles that can never be supported (e.g. a tile with no allowed neighbor).
    if wave.has_contradiction() or not wave.settle(np.ndindex(*shape)):
        return AttemptResult(None, 0)
    collapses = 0
    while (cell := wave.observe(rng)) is not None:
        wave.collapse(cell, rng)
        collapses += 1
        if not wave.settle([cell]):
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
    shape: Shape,
    seed: int,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    constraints: Sequence[Constraint] = (),
) -> RunResult:
    """Generate one grid, restarting with the next attempt seed on contradiction."""
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")
    start = time.perf_counter()
    cells_collapsed = 0
    for attempt in range(max_attempts):
        result = solve_attempt(tileset, shape, attempt_rng(seed, attempt), constraints)
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

    Only forward directions are checked, so each pair is counted once; the opposite directions
    follow from the symmetry that ``Tileset`` validates.
    """
    violations = 0
    for d in tileset.topology.forward:
        src, dst = neighbor_pairs(grid, d, tileset.topology)
        violations += int((~tileset.compat[d, src, dst]).sum())
    return violations
