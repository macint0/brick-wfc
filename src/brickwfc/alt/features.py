"""Feature vectors of 3D builds for dedupe and diversity-aware selection.

Builds of one inventory that use (nearly) all of it have nearly the same part and color histograms, so
those alone barely tell builds apart; the per-layer fill and a coarse top-view height map describe the
overall form. Every entry is in [0, 1].
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from brickwfc.bricks.parts import PlacedPart
from brickwfc.bricks.style import TYPE_INDEX, TYPES

HEIGHT_MAP_BLOCKS = 4  # the top view is pooled into at most 4 x 4 blocks


def occupancy(placed: Sequence[PlacedPart], shape: tuple[int, int, int]) -> np.ndarray:
    filled = np.zeros(shape, dtype=bool)
    for part in placed:
        for cell in part.cells():
            filled[cell] = True
    return filled


def height_map(filled: np.ndarray) -> np.ndarray:
    """(Z, X) height of each column's top filled cell (0 = empty column), as a share of the grid height."""
    ny = filled.shape[0]
    top = np.where(filled.any(axis=0), ny - np.argmax(filled[::-1], axis=0), 0)
    return top / ny


def pooled(values: np.ndarray, blocks: int) -> np.ndarray:
    """Mean of ``values`` (Z, X) over a grid of at most ``blocks`` x ``blocks`` blocks, flattened."""
    rows = np.array_split(values, min(blocks, values.shape[0]), axis=0)
    return np.array([block.mean() for row in rows for block in np.array_split(row, min(blocks, row.shape[1]), axis=1)])


def feature_vector(placed: Sequence[PlacedPart], shape: tuple[int, int, int], colors: Sequence[str]) -> np.ndarray:
    """[per-layer fill (Y), part-type shares (len(TYPES)), color shares (len(colors)), pooled height map]."""
    filled = occupancy(placed, shape)
    layer_fill = filled.mean(axis=(1, 2))
    count = max(len(placed), 1)
    types = np.bincount([TYPE_INDEX[p.shape.part.name] for p in placed], minlength=len(TYPES)) / count
    color_index = {name: i for i, name in enumerate(colors)}
    color_shares = np.bincount([color_index[p.color.name] for p in placed], minlength=len(colors)) / count
    return np.concatenate([layer_fill, types, color_shares, pooled(height_map(filled), HEIGHT_MAP_BLOCKS)])
