"""Shape features of 2D designs shared by verify, dedupe, and judge."""

from __future__ import annotations

from collections import deque

import numpy as np

from brickwfc.tileset import OFFSETS


def label_regions(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """4-connected components of ``mask`` via BFS.

    Returns ``(labels, count)``: ``labels`` is 0 outside the mask and 1..count inside.
    """
    height, width = mask.shape
    labels = np.zeros(mask.shape, dtype=np.int64)
    count = 0
    for start in zip(*np.nonzero(mask)):
        if labels[start]:
            continue
        count += 1
        labels[start] = count
        queue = deque([start])
        while queue:
            y, x = queue.popleft()
            for dy, dx in OFFSETS:
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not labels[ny, nx]:
                    labels[ny, nx] = count
                    queue.append((ny, nx))
    return labels, count


def region_sizes(mask: np.ndarray) -> np.ndarray:
    """Sizes of the 4-connected regions of ``mask`` (empty array if the mask is empty)."""
    labels, count = label_regions(mask)
    return np.bincount(labels.ravel(), minlength=count + 1)[1:]


def perimeter(mask: np.ndarray) -> int:
    """Number of 4-neighbor cell pairs with one cell inside ``mask`` and one outside (grid border excluded)."""
    return int((mask[:, 1:] != mask[:, :-1]).sum() + (mask[1:] != mask[:-1]).sum())


def feature_vector(grid: np.ndarray, land: np.ndarray, num_tiles: int) -> np.ndarray:
    """Dedupe/selection features: [tile histogram..., land regions per 100 cells, land perimeter per cell].

    Every entry is a per-cell rate, so all features are on comparable (roughly 0..1) scales and
    grids of different sizes can be compared.
    """
    cells = grid.size
    histogram = np.bincount(grid.ravel(), minlength=num_tiles) / cells
    _, regions = label_regions(land)
    return np.concatenate([histogram, [100 * regions / cells, perimeter(land) / cells]])
