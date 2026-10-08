"""Write selected builds: .ldr with building steps, isometric previews, a contact sheet."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PIL import Image

from brickwfc.bricks.build import save_preview
from brickwfc.bricks.parts import PlacedPart
from brickwfc.ldraw.export import write_steps
from brickwfc.render2d import contact_sheet


def layer_steps(placed: Sequence[PlacedPart]) -> list[list[PlacedPart]]:
    """Building steps bottom to top: one step per layer that some part starts on (a brick belongs to its
    bottom layer's step), parts in each step ordered by (z, x)."""
    layers = sorted({p.layer for p in placed})
    return [sorted((p for p in placed if p.layer == layer), key=lambda p: (p.z, p.x)) for layer in layers]


def write_build(placed: Sequence[PlacedPart], shape: tuple[int, int, int], stem: Path, title: str) -> tuple[Path, Path]:
    """``stem``.ldr (one ``0 STEP`` per layer) and ``stem``.png; returns both paths."""
    ldr, png = stem.with_suffix(".ldr"), stem.with_suffix(".png")
    write_steps(([p.placement() for p in step] for step in layer_steps(placed)), ldr, title)
    save_preview(list(placed), shape, png)
    return ldr, png


def write_sheet(previews: Sequence[Path], path: Path, columns: int = 4) -> None:
    images = [Image.open(p).convert("RGB") for p in previews]
    contact_sheet(images, min(columns, len(images))).save(path)
