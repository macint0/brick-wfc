"""Stability-aware propagation (M6): part-level support enforced inside WFC propagation.

Rule: every part above layer 0 must rest on at least one stud (the top of a plate or brick, not of
a tile) directly below its bottom layer. Unlike M4's per-cell rule this is non-local (a 2x4 plate may be held up by any one of
its 8 studs), so it cannot be written as pairwise adjacency. ``SupportConstraint`` plugs into
``Wave.settle`` and does two things, one layer at a time:

- **Prune:** remove a bottom-layer tile from a cell when no cell below its part's footprint can
  still hold a stud.
- **Force:** when a cell is fixed to a bottom-layer tile and exactly one cell below its footprint
  can still hold a stud, that cell must hold one, so its other tiles are removed.

Tiles above a part's bottom layer need no check: adjacency ties them to the bottom tile below.

Both are sound (they only remove tiles that cannot appear in a stable completion), so every
finished grid satisfies ``support.is_stable``.
"""

from __future__ import annotations

import numpy as np

from brickwfc.bricks.parts import PartSet
from brickwfc.wfc import Cell, Wave


class SupportConstraint:
    def __init__(self, parts: PartSet) -> None:
        self.stud_top = parts.stud_top
        # Bottom-layer tiles grouped by footprint (offsets from the cell to every seated cell of its part's
        # layer); tiles of different colors share a footprint, so each group is checked once per layer.
        groups: dict[tuple[tuple[int, int], ...], list[int]] = {}
        for tile, info in enumerate(parts.infos):
            if info.bottom:
                groups.setdefault(tuple(sorted(info.seats())), []).append(tile)
        self.groups = [(footprint, np.array(tiles)) for footprint, tiles in groups.items()]
        self.pad = max(abs(v) for footprint, _ in self.groups for offset in footprint for v in offset)

    def prune(self, wave: Wave, changed: set[Cell]) -> list[Cell] | None:
        # A cell's support depends on the layer below it, so a change at layer y affects layer y + 1;
        # forcing depends on the cell's own layer, so layer y is rechecked too.
        num_layers = wave.shape[0]
        layers = sorted({cell[0] + k for cell in changed for k in (0, 1) if 1 <= cell[0] + k < num_layers})
        pruned: list[Cell] = []
        for y in layers:
            layer_pruned = self._prune_layer(wave, y)
            if layer_pruned is None:
                return None
            pruned.extend(layer_pruned)
        return pruned

    def _prune_layer(self, wave: Wave, y: int) -> list[Cell] | None:
        layer, below = wave.domain[y], wave.domain[y - 1]
        nz, nx = layer.shape[:2]
        pad = self.pad
        below_has_stud = np.pad((below & self.stud_top).any(axis=-1), pad)
        fixed = layer.sum(axis=-1) == 1
        shrunk = np.zeros((nz, nx), dtype=bool)
        must_have_stud = np.zeros((nz + 2 * pad, nx + 2 * pad), dtype=bool)  # padded like the supporters

        for footprint, tiles in self.groups:
            present = layer[:, :, tiles].any(axis=-1)
            if not present.any():
                continue
            # supporters[i][z, x]: can the cell below footprint offset i of a part at (z, x) be solid?
            supporters = [below_has_stud[pad + dz : pad + dz + nz, pad + dx : pad + dx + nx] for dz, dx in footprint]
            count = np.sum(supporters, axis=0)

            unsupported = present & (count == 0)
            if unsupported.any():
                group = layer[:, :, tiles]
                group[unsupported] = False
                layer[:, :, tiles] = group
                shrunk |= unsupported

            last_support = present & fixed & (count == 1)
            if last_support.any():
                for (dz, dx), can_support in zip(footprint, supporters):
                    must_have_stud[pad + dz : pad + dz + nz, pad + dx : pad + dx + nx] |= last_support & can_support

        forced = must_have_stud[pad : pad + nz, pad : pad + nx] & (below & ~self.stud_top).any(axis=-1)
        below[forced] &= self.stud_top

        if not layer[shrunk].any(axis=-1).all():
            return None
        return [(y, int(z), int(x)) for z, x in np.argwhere(shrunk)] + [
            (y - 1, int(z), int(x)) for z, x in np.argwhere(forced)
        ]
