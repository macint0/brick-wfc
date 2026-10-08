"""Brick builds as token sequences for a learned proposal model (M12b step 2).

A build is a sequence of parts in bottom-up raster order (by layer, then z, then x), each written as five
tokens ``Y Z X SHAPE COLOR``: the part's min-corner cell (Y in plates, Z and X in studs), its shape (a
catalog part in one orientation, as ``parts.Shape.name``: ``brick2x4`` or ``brick2x4_r90``, so the rotation
is part of the shape) and its color (``NONE`` for BrickGPT's colorless structures, ``OTHER`` for a color not
in the vocabulary).

A sequence starts with a four-token header and a target block:

    START SRC SCALE MASKFLAG  [64 mask patches]  part tokens ...  EOS

- ``START`` is ``BOS`` when the sequence starts at the build's first part, ``CONT`` for a window that starts
  later (long builds are trained and decoded in windows);
- ``SRC`` is the data source (``SRC_brickgpt`` or ``SRC_set``), so decoding can ask for real-set style;
- ``SCALE_s`` and the mask: the build's (or target's) occupancy, downsampled to a ``MASK_GRID``^3 grid of
  coarse voxels of s x s studs x 3s plates (s = 1 for BrickGPT's 20^3-brick grid, larger for bigger
  models; see ``coarse_mask``). The mask enters the model as ``MASK_PATCHES`` patch vectors of
  ``PATCH``^3 bits each (``patches``), not as tokens. ``MASKFLAG`` is ``MASK``, or ``NOMASK`` when there is
  no target (the patches are then all zero).

Token ids are fixed by a ``Vocab`` saved as JSON next to the data and the model weights, so a model keeps
working if the catalog grows: shapes it has no token for simply get no proposal.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

from brickwfc.bricks.colors import PALETTE, BrickColor
from brickwfc.bricks.parts import CATALOG, PlacedPart, Shape, shapes_of

MAX_XZ = 64  # studs per horizontal axis
MAX_Y = 192  # plate layers
MAX_SCALE = 8
MASK_GRID = 20  # coarse voxels per axis
PATCH = 5  # coarse voxels per patch side
MASK_PATCHES = (MASK_GRID // PATCH) ** 3  # 64
PATCH_BITS = PATCH**3  # 125
PLATES_PER_UNIT = 3  # a coarse voxel is 3 plates tall per stud of width (one brick)
HEADER = 4  # START SRC SCALE MASKFLAG
PREFIX = HEADER + MASK_PATCHES  # sequence positions before the first part token
PART_TOKENS = 5  # Y Z X SHAPE COLOR
SOURCES = ("brickgpt", "set")
SPECIALS = ("PAD", "BOS", "CONT", "EOS", "MASK", "NOMASK", *(f"SRC_{s}" for s in SOURCES))
NONE_COLOR, OTHER_COLOR = "NONE", "OTHER"


@dataclass(frozen=True)
class Vocab:
    """Token names; a token's id is its index."""

    tokens: tuple[str, ...]
    index: dict[str, int] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "index", {t: i for i, t in enumerate(self.tokens)})
        if len(self.index) != len(self.tokens):
            raise ValueError("duplicate tokens in vocabulary")

    def __len__(self) -> int:
        return len(self.tokens)

    def id(self, token: str) -> int:
        return self.index[token]

    def ids(self, prefix: str) -> np.ndarray:
        """Ids of every token starting with ``prefix`` (in vocabulary order)."""
        return np.array([i for t, i in self.index.items() if t.startswith(prefix)], dtype=np.int64)

    def y(self, layer: int) -> int:
        return self.index[f"Y{layer}"]

    def z(self, z: int) -> int:
        return self.index[f"Z{z}"]

    def x(self, x: int) -> int:
        return self.index[f"X{x}"]

    def shape(self, shape: Shape) -> int | None:
        """The shape's token id, or None if the vocabulary has no token for it."""
        return self.index.get(f"S:{shape.name}")

    def color(self, color: BrickColor | None) -> int:
        if color is None:
            return self.index[f"C:{NONE_COLOR}"]
        return self.index.get(f"C:{color.name}", self.index[f"C:{OTHER_COLOR}"])

    def shape_ids(self) -> np.ndarray:
        return self.ids("S:")

    def color_ids(self) -> np.ndarray:
        return self.ids("C:")

    def to_json(self) -> dict:
        return {"tokens": list(self.tokens), "prefix": PREFIX, "header": HEADER, "mask_patches": MASK_PATCHES,
                "patch_bits": PATCH_BITS, "part_tokens": PART_TOKENS, "mask_grid": MASK_GRID, "patch": PATCH}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Vocab":
        return cls(tuple(json.loads(Path(path).read_text(encoding="utf-8"))["tokens"]))


def build_vocab(colors: Iterable[str] = ()) -> Vocab:
    """Specials, scales, coordinates, every catalog shape, and the palette's colors plus ``colors``."""
    shapes = [s.name for s in shapes_of(list(CATALOG.values()))]
    color_names = list(PALETTE) + sorted(set(colors) - set(PALETTE) - {NONE_COLOR, OTHER_COLOR})
    tokens = (
        list(SPECIALS)
        + [f"SCALE_{s}" for s in range(1, MAX_SCALE + 1)]
        + [f"Y{i}" for i in range(MAX_Y)]
        + [f"Z{i}" for i in range(MAX_XZ)]
        + [f"X{i}" for i in range(MAX_XZ)]
        + [f"S:{name}" for name in shapes]
        + [f"C:{name}" for name in [*color_names, NONE_COLOR, OTHER_COLOR]]
    )
    return Vocab(tuple(tokens))


# Ordering and symmetries ------------------------------------------------------------------------------


def raster_key(part: PlacedPart) -> tuple[int, int, int, str]:
    """Sort key of the token order: layer, then z, then x (then shape name, for a total order)."""
    return part.layer, part.z, part.x, part.shape.name


def ordered(placed: Sequence[PlacedPart]) -> list[PlacedPart]:
    return sorted(placed, key=raster_key)


def extent(placed: Sequence[PlacedPart]) -> tuple[int, int, int]:
    """(Y, Z, X) cells spanned from the origin (0 for an empty build)."""
    if not placed:
        return 0, 0, 0
    return (max(p.top + 1 for p in placed), max(p.z + p.shape.size_z for p in placed),
            max(p.x + p.shape.size_x for p in placed))


def _turned(shape: Shape) -> Shape:
    return Shape(shape.part, not shape.rotated) if shape.part.width != shape.part.depth else shape


def rotate90(placed: Sequence[PlacedPart]) -> list[PlacedPart]:
    """The build turned a quarter about the vertical axis: (x, z) -> (Z - z - depth, x), shapes turned."""
    _, nz, _ = extent(placed)
    return [PlacedPart(_turned(p.shape), p.color, p.layer, nz - p.z - p.shape.size_z, p.x) for p in placed]


def mirror_x(placed: Sequence[PlacedPart]) -> list[PlacedPart]:
    """The build mirrored along x (every catalog part is a symmetric box, so shapes are unchanged)."""
    _, _, nx = extent(placed)
    return [PlacedPart(p.shape, p.color, p.layer, nx - p.x - p.shape.size_x, p.z) for p in placed]


def symmetries(placed: Sequence[PlacedPart], count: int = 8) -> list[list[PlacedPart]]:
    """The first ``count`` of the build's 8 horizontal symmetries (4 turns, then the 4 turns mirrored);
    the first is the build itself."""
    variants, current = [], list(placed)
    for mirrored in (current, mirror_x(current)):
        turn = mirrored
        for _ in range(4):
            variants.append(turn)
            turn = rotate90(turn)
    return variants[:count]


# Target mask ---------------------------------------------------------------------------------------------


def occupancy(placed: Sequence[PlacedPart]) -> np.ndarray:
    """(Y, Z, X) bool cells covered by the build."""
    mask = np.zeros(extent(placed), dtype=bool)
    for p in placed:
        mask[p.layer : p.top + 1, p.z : p.z + p.shape.size_z, p.x : p.x + p.shape.size_x] = True
    return mask


def mask_scale(shape: tuple[int, int, int]) -> int:
    """The coarse voxel size s (s x s studs x 3s plates) that fits a (Y, Z, X) grid into MASK_GRID^3."""
    ny, nz, nx = shape
    s = max(1, math.ceil(nz / MASK_GRID), math.ceil(nx / MASK_GRID), math.ceil(ny / (PLATES_PER_UNIT * MASK_GRID)))
    if s > MAX_SCALE:
        raise ValueError(f"grid {shape} needs coarse scale {s} > {MAX_SCALE}")
    return s


def coarse_mask(cells: np.ndarray) -> tuple[int, np.ndarray]:
    """(scale, (MASK_GRID,)*3 bool): a coarse voxel is set where any of its cells is (max-pooling); the grid is
    anchored at the origin, (y, z, x) like the cells."""
    s = mask_scale(cells.shape)
    ny, nz, nx = cells.shape
    sy, sz, sx = PLATES_PER_UNIT * s, s, s
    padded = np.zeros((MASK_GRID * sy, MASK_GRID * sz, MASK_GRID * sx), dtype=bool)
    padded[:ny, :nz, :nx] = cells
    pooled = padded.reshape(MASK_GRID, sy, MASK_GRID, sz, MASK_GRID, sx).any(axis=(1, 3, 5))
    return s, pooled


def patches(mask: np.ndarray | None) -> np.ndarray:
    """(MASK_PATCHES, PATCH_BITS) float32 patch vectors of a coarse mask, patches in (y, z, x) order and bits
    in (y, z, x) order inside a patch; all zero for no mask."""
    if mask is None:
        return np.zeros((MASK_PATCHES, PATCH_BITS), dtype=np.float32)
    n = MASK_GRID // PATCH
    blocks = mask.reshape(n, PATCH, n, PATCH, n, PATCH).transpose(0, 2, 4, 1, 3, 5)
    return blocks.reshape(MASK_PATCHES, PATCH_BITS).astype(np.float32)


# Tokens ---------------------------------------------------------------------------------------------


def part_tokens(part: PlacedPart, vocab: Vocab, colorless: bool = False) -> list[int]:
    """The part's five tokens. Raises for a shape the vocabulary lacks or a position outside it."""
    shape = vocab.shape(part.shape)
    if shape is None:
        raise ValueError(f"no token for shape {part.shape.name}")
    if not (0 <= part.layer < MAX_Y and 0 <= part.z < MAX_XZ and 0 <= part.x < MAX_XZ):
        raise ValueError(f"{part.shape.name} at {(part.layer, part.z, part.x)} is outside the token grid")
    return [vocab.y(part.layer), vocab.z(part.z), vocab.x(part.x), shape, vocab.color(None if colorless else part.color)]


def header(vocab: Vocab, source: str, scale: int, has_mask: bool, start: bool = True) -> list[int]:
    return [vocab.id("BOS" if start else "CONT"), vocab.id(f"SRC_{source}"), vocab.id(f"SCALE_{scale}"),
            vocab.id("MASK" if has_mask else "NOMASK")]


@dataclass(frozen=True)
class Encoded:
    """One build as model input: the header, the coarse mask (None for no target) and the part tokens."""

    header: np.ndarray  # (HEADER,) int
    mask: np.ndarray | None  # (MASK_GRID,)*3 bool
    parts: np.ndarray  # (n, PART_TOKENS) int, raster order

    def tokens(self, vocab: Vocab) -> list[int]:
        """The flat token sequence with the mask block written as one PAD per patch slot, then EOS (for
        inspection; the model reads the mask block through ``patches``)."""
        return [*self.header.tolist(), *([vocab.id("PAD")] * MASK_PATCHES), *self.parts.ravel().tolist(), vocab.id("EOS")]


def encode(placed: Sequence[PlacedPart], vocab: Vocab, source: str, colorless: bool = False,
           with_mask: bool = True) -> Encoded:
    """A build as tokens, its own occupancy as the target mask (what BrickGPT's objects and real sets give)."""
    parts = ordered(placed)
    scale, mask = coarse_mask(occupancy(parts))
    rows = np.array([part_tokens(p, vocab, colorless) for p in parts], dtype=np.int64).reshape(-1, PART_TOKENS)
    return Encoded(np.array(header(vocab, source, scale, with_mask), dtype=np.int64), mask if with_mask else None, rows)


def decode_part(row: Sequence[int], vocab: Vocab) -> PlacedPart:
    """A part from its five tokens (``NONE`` and ``OTHER`` decode to a gray stand-in color)."""
    y, z, x, s, c = (vocab.tokens[int(t)] for t in row)
    name = s[2:]
    rotated = name.endswith("_r90")
    shape = Shape(CATALOG[name.removesuffix("_r90")], rotated)
    color_name = c[2:]
    color = PALETTE.get(color_name) or BrickColor(color_name, 71, (0xA0, 0xA5, 0xA9))
    return PlacedPart(shape, color, int(y[1:]), int(x[1:]), int(z[1:]))
