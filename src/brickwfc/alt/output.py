"""Write selected builds: .ldr with building steps, isometric previews, a contact sheet."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from PIL import Image

from brickwfc.bricks.build import save_preview
from brickwfc.bricks.accessories import fit
from brickwfc.bricks.parts import PlacedPart, export_drop, lowered
from brickwfc.ldraw.export import Placement
from brickwfc.ldraw.export import write_steps
from brickwfc.render2d import contact_sheet


def layer_steps(placed: Sequence[PlacedPart]) -> list[list[PlacedPart]]:
    """Building steps bottom to top: one step per layer that some part starts on (a brick belongs to its
    bottom layer's step), parts in each step ordered by (z, x)."""
    layers = sorted({p.layer for p in placed})
    return [sorted((p for p in placed if p.layer == layer), key=lambda p: (p.z, p.x)) for layer in layers]


def write_build(placed: Sequence[PlacedPart], shape: tuple[int, int, int], stem: Path, title: str,
                accessories: Mapping[tuple[str, int], int] | None = None) -> tuple[Path, Path]:
    """``stem``.ldr (one ``0 STEP`` per layer) and ``stem``.png; returns both paths. With ``accessories`` (M12d: the
    inventory's glass, panes and doors), each frame's are fitted (``accessories.fit``) and written in its step."""
    ldr, png = stem.with_suffix(".ldr"), stem.with_suffix(".png")
    write_steps(step_placements(placed, accessories), ldr, title)
    save_preview(list(placed), shape, png)
    return ldr, png


def step_placements(placed: Sequence[PlacedPart], accessories: Mapping[tuple[str, int], int] | None = None
                    ) -> list[list[Placement]]:
    """The placements of each building step (``layer_steps``), every frame followed by its fitted accessories."""
    drop = export_drop(placed)
    held: dict[int, list[Placement]] = {}
    for i, placement in fit(placed, accessories or {}):
        held.setdefault(i, []).append(lowered(placement, drop))
    index = {id(p): i for i, p in enumerate(placed)}
    steps = []
    for step in layer_steps(placed):
        steps.append([q for p in step for q in [lowered(p.placement(), drop), *held.get(index[id(p)], [])]])
    return steps


def write_sheet(previews: Sequence[Path], path: Path, columns: int = 4) -> None:
    images = [Image.open(p).convert("RGB") for p in previews]
    contact_sheet(images, min(columns, len(images))).save(path)
