"""Tiles, directional adjacency rules, and weights for WFC on 2D or 3D grids."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Topology:
    """A grid neighborhood: direction names, the index offset of each direction, and its opposite."""

    name: str
    directions: tuple[str, ...]
    offsets: tuple[tuple[int, ...], ...]
    opposite: tuple[int, ...]

    @property
    def ndim(self) -> int:
        return len(self.offsets[0])

    @property
    def forward(self) -> tuple[int, ...]:
        """One direction from each opposite pair (the one pointing along +axis); visiting
        neighbors only in these directions sees every neighboring pair exactly once."""
        return tuple(d for d, offset in enumerate(self.offsets) if sum(offset) > 0)


# 2D arrays are indexed (y, x): y is the row, growing southward.
GRID2D = Topology("grid2d", ("N", "E", "S", "W"), ((-1, 0), (0, 1), (1, 0), (0, -1)), (2, 3, 0, 1))

# 3D arrays are indexed (y, z, x): y is the layer (up = +y), z grows southward, x grows eastward.
GRID3D = Topology(
    "grid3d",
    ("U", "D", "N", "E", "S", "W"),
    ((1, 0, 0), (-1, 0, 0), (0, -1, 0), (0, 0, 1), (0, 1, 0), (0, 0, -1)),
    (1, 0, 4, 5, 2, 3),
)

TOPOLOGIES = {t.name: t for t in (GRID2D, GRID3D)}

# 2D shorthands, used by the 2D-only modules.
DIRECTIONS = GRID2D.directions
OFFSETS = GRID2D.offsets
OPPOSITE = GRID2D.opposite


@dataclass(frozen=True, eq=False)
class Tileset:
    """A set of tiles with weights, display colors, and directional adjacency rules.

    ``compat[d, a, b]`` is True when tile ``b`` may sit in direction ``d`` of tile ``a``,
    so ``compat[d, a]`` is the mask of tiles allowed next to ``a`` in direction ``d``.
    Rules must be symmetric: ``compat[d, a, b] == compat[opposite[d], b, a]``.

    ``border[d, t]`` is True when tile ``t`` may sit with the grid boundary in direction ``d``
    (default: always). Multi-cell parts use it so a part never sticks out of the grid.
    """

    names: tuple[str, ...]
    colors: tuple[RGB, ...]
    weights: np.ndarray  # (T,) float64, all > 0
    compat: np.ndarray  # (D, T, T) bool, D = number of topology directions
    topology: Topology = GRID2D
    border: np.ndarray | None = None  # (D, T) bool; None means all True

    def __post_init__(self) -> None:
        # Store read-only copies so a Tileset can't be mutated after validation.
        weights = np.array(self.weights, dtype=np.float64)
        compat = np.array(self.compat, dtype=bool)
        if self.border is None:
            border = np.ones((len(self.topology.directions), len(self.names)), dtype=bool)
        else:
            border = np.array(self.border, dtype=bool)
        for array in (weights, compat, border):
            array.setflags(write=False)
        object.__setattr__(self, "names", tuple(self.names))
        object.__setattr__(self, "colors", tuple(tuple(c) for c in self.colors))
        object.__setattr__(self, "weights", weights)
        object.__setattr__(self, "compat", compat)
        object.__setattr__(self, "border", border)
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
        directions, opposite = self.topology.directions, self.topology.opposite
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
        if self.compat.shape != (len(directions), n, n):
            raise ValueError(f"compat must have shape ({len(directions)}, {n}, {n}), got {self.compat.shape}")
        if self.border.shape != (len(directions), n):
            raise ValueError(f"border must have shape ({len(directions)}, {n}), got {self.border.shape}")
        for d in range(len(directions)):
            mismatch = self.compat[d] != self.compat[opposite[d]].T
            if mismatch.any():
                a, b = (int(i) for i in np.argwhere(mismatch)[0])
                raise ValueError(
                    f"asymmetric adjacency: {self.names[b]!r} {directions[d]} of {self.names[a]!r} "
                    f"is {bool(self.compat[d, a, b])}, but {self.names[a]!r} {directions[opposite[d]]} "
                    f"of {self.names[b]!r} is {bool(self.compat[opposite[d], b, a])}"
                )

    def rules(self) -> set[tuple[str, str, str]]:
        """All allowed placements as (a, b, direction) name triples: ``b`` may sit ``direction`` of ``a``.

        Name-based, so tilesets with different tile orders can be compared.
        """
        directions = self.topology.directions
        return {(self.names[a], self.names[b], directions[d]) for d, a, b in zip(*np.nonzero(self.compat))}

    @classmethod
    def from_pairs(
        cls,
        names: Sequence[str],
        colors: Sequence[RGB],
        weights: Sequence[float],
        pairs: Iterable[Sequence[str]],
        topology: Topology = GRID2D,
    ) -> Tileset:
        """Build a tileset from adjacency pairs.

        ``(a, b)`` lets a and b touch in every direction. ``(a, b, d)`` lets b sit in direction
        ``d`` (e.g. N/E/S/W) of a, which implies a sits in the opposite direction of b.
        Self-adjacency is not implied; list ``(a, a)`` to allow it.
        """
        directions, opposite = topology.directions, topology.opposite
        index = {name: i for i, name in enumerate(names)}
        compat = np.zeros((len(directions), len(names), len(names)), dtype=bool)
        for pair in pairs:
            if len(pair) not in (2, 3):
                raise ValueError(f"adjacency entry must be [a, b] or [a, b, dir], got {list(pair)}")
            a, b = pair[0], pair[1]
            for name in (a, b):
                if name not in index:
                    raise ValueError(f"adjacency entry {list(pair)} names unknown tile {name!r}")
            if len(pair) == 2:
                chosen: Iterable[int] = range(len(directions))
            elif pair[2] in directions:
                chosen = [directions.index(pair[2])]
            else:
                raise ValueError(f"adjacency entry {list(pair)}: direction must be one of {directions}")
            for d in chosen:
                compat[d, index[a], index[b]] = True
                compat[opposite[d], index[b], index[a]] = True
        return cls(tuple(names), tuple(colors), np.asarray(weights, dtype=np.float64), compat, topology)


def parse_hex_color(text: str) -> RGB:
    """Parse ``#RRGGBB`` into an (r, g, b) tuple."""
    digits = text.removeprefix("#")
    if len(digits) != 6:
        raise ValueError(f"expected a color like '#RRGGBB', got {text!r}")
    return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))


def to_hex_color(rgb: RGB) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def neighbor_pairs(grid: np.ndarray, d: int, topology: Topology = GRID2D) -> tuple[np.ndarray, np.ndarray]:
    """Aligned views ``(src, dst)`` where ``dst`` is the neighbor in direction ``d`` of ``src``."""
    offset = topology.offsets[d]
    src = grid[tuple(slice(max(0, -o), n - max(0, o)) for o, n in zip(offset, grid.shape))]
    dst = grid[tuple(slice(max(0, o), n - max(0, -o)) for o, n in zip(offset, grid.shape))]
    return src, dst


def adjacency_entries(tileset: Tileset) -> list[list[str]]:
    """Compact JSON adjacency list: ``[a, b]`` when a and b touch in every direction, else ``[a, b, dir]``."""
    names, compat, directions = tileset.names, tileset.compat, tileset.topology.directions
    entries: list[list[str]] = []
    for a in range(tileset.num_tiles):
        for b in range(a, tileset.num_tiles):
            allowed = compat[:, a, b]  # b in direction d of a; the reverse is implied by symmetry
            if allowed.all():
                entries.append([names[a], names[b]])
            else:
                entries.extend([names[a], names[b], directions[d]] for d in np.nonzero(allowed)[0])
    return entries


def tileset_to_json(tileset: Tileset) -> dict:
    data = {
        "topology": tileset.topology.name,
        "tiles": [
            {"name": name, "color": to_hex_color(color), "weight": float(weight)}
            for name, color, weight in zip(tileset.names, tileset.colors, tileset.weights)
        ],
        "adjacency": adjacency_entries(tileset),
    }
    forbidden = [[tileset.names[t], tileset.topology.directions[d]] for d, t in zip(*np.nonzero(~tileset.border))]
    if forbidden:
        data["border_forbidden"] = forbidden
    return data


def save_tileset(tileset: Tileset, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tileset_to_json(tileset), indent=2) + "\n", encoding="utf-8")


def load_tileset(path: str | Path) -> Tileset:
    """Load a tileset from JSON.

    Format::

        {
          "topology": "grid2d",   (optional; "grid2d" or "grid3d", default "grid2d")
          "tiles": [{"name": "water", "color": "#2f6fc4", "weight": 4.0}, ...],
          "adjacency": [["water", "water"], ["water", "sand"], ...],
          "border_forbidden": [["tile", "E"], ...]   (optional; tiles that may not face that grid edge)
        }

    Entries are ``[a, b]`` (undirected) or ``[a, b, dir]`` (directed); see ``Tileset.from_pairs``.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tiles = data["tiles"]
    tileset = Tileset.from_pairs(
        names=[t["name"] for t in tiles],
        colors=[parse_hex_color(t["color"]) for t in tiles],
        weights=[float(t.get("weight", 1.0)) for t in tiles],
        pairs=data["adjacency"],
        topology=TOPOLOGIES[data.get("topology", GRID2D.name)],
    )
    if "border_forbidden" not in data:
        return tileset
    border = np.ones_like(tileset.border)
    for name, direction in data["border_forbidden"]:
        border[tileset.topology.directions.index(direction), tileset.index(name)] = False
    return dataclasses.replace(tileset, border=border)
