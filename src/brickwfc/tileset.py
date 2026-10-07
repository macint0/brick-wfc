"""Tiles, directional adjacency rules, and weights for 2D WFC."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

# Directions are indexed N=0, E=1, S=2, W=3. Offsets are (dy, dx); y is the row index, growing southward.
DIRECTIONS: tuple[str, ...] = ("N", "E", "S", "W")
OFFSETS: tuple[tuple[int, int], ...] = ((-1, 0), (0, 1), (1, 0), (0, -1))
OPPOSITE: tuple[int, ...] = (2, 3, 0, 1)

RGB = tuple[int, int, int]


@dataclass(frozen=True, eq=False)
class Tileset:
    """A set of tiles with weights, display colors, and directional adjacency rules.

    ``compat[d, a, b]`` is True when tile ``b`` may sit in direction ``d`` of tile ``a``,
    so ``compat[d, a]`` is the mask of tiles allowed next to ``a`` in direction ``d``.
    Rules must be symmetric: ``compat[d, a, b] == compat[OPPOSITE[d], b, a]``.
    """

    names: tuple[str, ...]
    colors: tuple[RGB, ...]
    weights: np.ndarray  # (T,) float64, all > 0
    compat: np.ndarray  # (4, T, T) bool

    def __post_init__(self) -> None:
        # Store read-only copies so a Tileset can't be mutated after validation.
        weights = np.array(self.weights, dtype=np.float64)
        compat = np.array(self.compat, dtype=bool)
        weights.setflags(write=False)
        compat.setflags(write=False)
        object.__setattr__(self, "names", tuple(self.names))
        object.__setattr__(self, "colors", tuple(tuple(c) for c in self.colors))
        object.__setattr__(self, "weights", weights)
        object.__setattr__(self, "compat", compat)
        self._validate()

    @property
    def num_tiles(self) -> int:
        return len(self.names)

    def index(self, name: str) -> int:
        try:
            return self.names.index(name)
        except ValueError:
            raise ValueError(f"unknown tile {name!r}; known tiles: {list(self.names)}") from None

    def _validate(self) -> None:
        n = len(self.names)
        if n == 0:
            raise ValueError("tileset has no tiles")
        if len(set(self.names)) != n:
            raise ValueError(f"duplicate tile names: {list(self.names)}")
        if len(self.colors) != n:
            raise ValueError(f"expected {n} colors, got {len(self.colors)}")
        for name, color in zip(self.names, self.colors):
            if len(color) != 3 or not all(0 <= c <= 255 for c in color):
                raise ValueError(f"tile {name!r}: color must be 3 ints in 0..255, got {color}")
        if self.weights.shape != (n,):
            raise ValueError(f"weights must have shape ({n},), got {self.weights.shape}")
        if not np.all(self.weights > 0):
            raise ValueError(f"weights must be positive, got {self.weights.tolist()}")
        if self.compat.shape != (4, n, n):
            raise ValueError(f"compat must have shape (4, {n}, {n}), got {self.compat.shape}")
        for d in range(4):
            mismatch = self.compat[d] != self.compat[OPPOSITE[d]].T
            if mismatch.any():
                a, b = (int(i) for i in np.argwhere(mismatch)[0])
                raise ValueError(
                    f"asymmetric adjacency: {self.names[b]!r} {DIRECTIONS[d]} of {self.names[a]!r} "
                    f"is {bool(self.compat[d, a, b])}, but {self.names[a]!r} {DIRECTIONS[OPPOSITE[d]]} "
                    f"of {self.names[b]!r} is {bool(self.compat[OPPOSITE[d], b, a])}"
                )

    def rules(self) -> set[tuple[str, str, str]]:
        """All allowed placements as (a, b, direction) name triples: ``b`` may sit ``direction`` of ``a``.

        Name-based, so tilesets with different tile orders can be compared.
        """
        return {
            (self.names[a], self.names[b], DIRECTIONS[d]) for d, a, b in zip(*np.nonzero(self.compat))
        }

    @classmethod
    def from_pairs(
        cls,
        names: Sequence[str],
        colors: Sequence[RGB],
        weights: Sequence[float],
        pairs: Iterable[Sequence[str]],
    ) -> Tileset:
        """Build a tileset from adjacency pairs.

        ``(a, b)`` lets a and b touch in every direction. ``(a, b, d)`` lets b sit in direction
        ``d`` (one of N/E/S/W) of a, which implies a sits in the opposite direction of b.
        Self-adjacency is not implied; list ``(a, a)`` to allow it.
        """
        index = {name: i for i, name in enumerate(names)}
        compat = np.zeros((4, len(names), len(names)), dtype=bool)
        for pair in pairs:
            if len(pair) not in (2, 3):
                raise ValueError(f"adjacency entry must be [a, b] or [a, b, dir], got {list(pair)}")
            a, b = pair[0], pair[1]
            for name in (a, b):
                if name not in index:
                    raise ValueError(f"adjacency entry {list(pair)} names unknown tile {name!r}")
            if len(pair) == 2:
                directions = range(4)
            elif pair[2] in DIRECTIONS:
                directions = [DIRECTIONS.index(pair[2])]
            else:
                raise ValueError(f"adjacency entry {list(pair)}: direction must be one of {DIRECTIONS}")
            for d in directions:
                compat[d, index[a], index[b]] = True
                compat[OPPOSITE[d], index[b], index[a]] = True
        return cls(tuple(names), tuple(colors), np.asarray(weights, dtype=np.float64), compat)


def parse_hex_color(text: str) -> RGB:
    """Parse ``#RRGGBB`` into an (r, g, b) tuple."""
    digits = text.removeprefix("#")
    if len(digits) != 6:
        raise ValueError(f"expected a color like '#RRGGBB', got {text!r}")
    return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))


def to_hex_color(rgb: RGB) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def neighbor_pairs(grid: np.ndarray, d: int) -> tuple[np.ndarray, np.ndarray]:
    """Aligned views ``(src, dst)`` where ``dst`` is the neighbor in direction ``d`` of ``src``."""
    height, width = grid.shape
    dy, dx = OFFSETS[d]
    src = grid[max(0, -dy) : height - max(0, dy), max(0, -dx) : width - max(0, dx)]
    dst = grid[max(0, dy) : height - max(0, -dy), max(0, dx) : width - max(0, -dx)]
    return src, dst


def adjacency_entries(tileset: Tileset) -> list[list[str]]:
    """Compact JSON adjacency list: ``[a, b]`` when a and b touch in every direction, else ``[a, b, dir]``."""
    names, compat = tileset.names, tileset.compat
    entries: list[list[str]] = []
    for a in range(tileset.num_tiles):
        for b in range(a, tileset.num_tiles):
            allowed = compat[:, a, b]  # b in direction d of a; the reverse is implied by symmetry
            if allowed.all():
                entries.append([names[a], names[b]])
            else:
                entries.extend([names[a], names[b], DIRECTIONS[d]] for d in np.nonzero(allowed)[0])
    return entries


def tileset_to_json(tileset: Tileset) -> dict:
    return {
        "tiles": [
            {"name": name, "color": to_hex_color(color), "weight": float(weight)}
            for name, color, weight in zip(tileset.names, tileset.colors, tileset.weights)
        ],
        "adjacency": adjacency_entries(tileset),
    }


def save_tileset(tileset: Tileset, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tileset_to_json(tileset), indent=2) + "\n", encoding="utf-8")


def load_tileset(path: str | Path) -> Tileset:
    """Load a tileset from JSON.

    Format::

        {
          "tiles": [{"name": "water", "color": "#2f6fc4", "weight": 4.0}, ...],
          "adjacency": [["water", "water"], ["water", "sand"], ...]
        }

    Entries are ``[a, b]`` (undirected) or ``[a, b, dir]`` (directed); see ``Tileset.from_pairs``.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tiles = data["tiles"]
    return Tileset.from_pairs(
        names=[t["name"] for t in tiles],
        colors=[parse_hex_color(t["color"]) for t in tiles],
        weights=[float(t.get("weight", 1.0)) for t in tiles],
        pairs=data["adjacency"],
    )
