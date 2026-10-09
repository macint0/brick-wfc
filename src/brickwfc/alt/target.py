"""Target shapes for the pipeline (``--shape``), scaled to the inventory's volume.

- a primitive name (``bricks.shapes.SHAPES``), scaled by ``shapes.sized_for``;
- a top-down silhouette image (one pixel per stud, image rows along z; opaque or dark pixels are inside),
  extruded ``--shape-height`` plates and scaled in the footprint only; with a height map (same size, grey
  value = height in plates) the whole shape is scaled uniformly instead;
- an LDraw model (.ldr/.mpd file, or an OMR set number), voxelized (catalog parts on the stud grid only),
  each column filled from the ground to its top cell (or, with ``exact``, its own cells, which keeps
  overhangs and rooms but is a sparse view of the model), and scaled uniformly;
- a BrickGPT structure (``brickgpt:<structure id>`` from the StableText2Brick test split, or a local
  ``.txt`` file in its format; ``bricks.brickgpt``): a true 3D target, its exact cells scaled uniformly
  (with ``columns``, solid columns instead: the heightfield view of the same object);
- a triangle mesh (``.obj``/``.stl``/``.ply``/``.off``, watertight; ``bricks.mesh``), voxelized at ``voxels``
  cells along its longest side, filled, and scaled uniformly like a BrickGPT structure.

3D targets (models, BrickGPT structures, meshes) can be hollowed (``hollow`` > 0: a shell that many cells
thick plus internal pillars, ``shapes.hollow``); the hollowed shape is what is scaled to the volume, so the
same parts make a larger object. With ``supports``, columns are added under overhangs out of a part's reach
(``shapes.with_supports``), after scaling: the object keeps its size and gets extra cells outside it.

With ``symmetric`` (M12b step 3), the target carries the mirror plane of the object (``symmetry``; the best
vertical plane if it covers at least ``DECODE_MIN_SCORE`` of the object, else none) for symmetric decoding. If
the plane covers at least ``SYMMETRIZE_MIN_SCORE`` of it, the object is made exactly symmetric by adding the
mirror image of its cells: nearest-neighbor scaling breaks some symmetry (BrickGPT's car, 0.97 symmetric on its
20-unit grid, is 0.85 at 6378-1's scale). Adding cells keeps thin features (a resampling that is symmetric by
construction drops the chair's one-cell stem). Support columns are mirrored too (their placement is not symmetric
by itself). Off by default (targets as before).

With a silhouette, an optional color image of the same size gives each column a preferred color: the
inventory color nearest to its pixel (transparent pixels: no preference).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

from brickwfc.bricks import brickgpt
from brickwfc.bricks.mesh import MESH_SUFFIXES, mesh_mask
from brickwfc.bricks.colors import BrickColor
from brickwfc.bricks.shapes import (
    SHAPES,
    Mask,
    bounds,
    column_heights,
    from_heights,
    from_model,
    preferred_colors,
    resample,
    scaled_to,
    sized_for,
    with_supports,
)
from brickwfc.bricks.symmetry import DECODE_MIN_SCORE, SYMMETRIZE_MIN_SCORE, Plane, mirror_plane, reflected
from brickwfc.bricks.voxelize import voxelize
from brickwfc.ldraw.fetch import fetch_set
from brickwfc.ldraw.mpd import flatten

IMAGE_SUFFIXES = (".png", ".gif", ".bmp")
BRICKGPT_PREFIX = "brickgpt:"


@dataclass(frozen=True, eq=False)
class Target:
    mask: Mask
    preferred: np.ndarray | None  # (Z, X) color names, "" for no preference
    description: str
    plane: Plane | None = None  # with ``symmetric``: the object's mirror plane


def takes_supports(spec: str) -> bool:
    """Whether ``--shape spec`` can have support columns (and a hollow): a model, a BrickGPT structure or a mesh,
    not a primitive or a silhouette."""
    return Path(spec).suffix.lower() not in IMAGE_SUFFIXES and spec not in SHAPES


def load_target(spec: str, cells: float, colors: Sequence[BrickColor], height_map: Path | None = None,
                color_map: Path | None = None, height: int = 6, data_dir: Path = Path("data/omr"),
                exact: bool = False, columns: bool = False, brickgpt_dir: Path = brickgpt.DATA_DIR,
                voxels: int = 32, up: str = "y", hollow: int = 0, supports: bool = False,
                support_height: int = 0, symmetric: bool = False, keep_sections: bool = False) -> Target:
    """The target ``spec`` with a volume of about ``cells`` grid cells. ``exact``: a model keeps its own
    cells instead of solid columns; ``columns``: a 3D target becomes solid columns instead of its own cells;
    ``voxels``, ``up``: mesh resolution and up axis; ``hollow``: shell thickness of a 3D target (0: solid);
    ``supports``: add support columns under far overhangs of a 3D target; ``support_height`` > 0: only columns
    at most that many cells tall; ``symmetric``: find the mirror plane (see the module docstring); ``keep_sections``:
    a 3D target or model is scaled so its thin parts stay thick (``shapes.fit_scale``; the pipeline's fillable
    sizing)."""
    if symmetric and supports and not takes_supports(spec):
        raise ValueError("--hollow and --supports go with a 3D target (a model, a BrickGPT structure or a mesh)")
    target = _load(spec, cells, colors, height_map, color_map, height, data_dir, exact, columns, brickgpt_dir,
                   voxels, up, hollow, supports and not symmetric, support_height, keep_sections)
    if not symmetric:
        return target
    plane = mirror_plane(target.mask, DECODE_MIN_SCORE)
    obj = target.mask
    if plane is not None and plane.score >= SYMMETRIZE_MIN_SCORE:
        obj = obj | reflected(obj, plane)
        plane = Plane(plane.axis, plane.total, 1.0)
    mask = obj
    if supports:
        mask = with_supports(mask, max_height=support_height)
        if plane is not None:
            extra = mask & ~obj
            mask = mask | (reflected(extra, plane) & ~obj)
    hollowed = ", supports" + (f" up to {support_height} cells" if support_height else "") if supports else ""
    found = f", mirror plane {plane.name} ({plane.score:.2f})" if plane is not None else ", no mirror plane"
    return Target(mask, target.preferred, target.description[:-1] + hollowed + found + ")", plane)


def _load(spec: str, cells: float, colors: Sequence[BrickColor], height_map: Path | None, color_map: Path | None,
          height: int, data_dir: Path, exact: bool, columns: bool, brickgpt_dir: Path, voxels: int, up: str,
          hollow: int, supports: bool, support_height: int, keep_sections: bool = False) -> Target:
    """``load_target`` without the symmetric step."""
    path = Path(spec)
    suffix = path.suffix.lower()
    is_image = suffix in IMAGE_SUFFIXES
    is_mesh = suffix in MESH_SUFFIXES
    is_3d = spec.startswith(BRICKGPT_PREFIX) or suffix == ".txt" or is_mesh
    if (height_map or color_map) and not is_image:
        raise ValueError("--height-map and --color-map go with a silhouette image as --shape")
    if exact and (is_image or is_3d or spec in SHAPES):
        raise ValueError("--shape-exact goes with an LDraw model or set number as --shape")
    if columns and not is_3d:
        raise ValueError("--shape-columns goes with a 3D target (a BrickGPT structure or a mesh) as --shape")
    if (hollow or supports) and (is_image or spec in SHAPES):
        raise ValueError("--hollow and --supports go with a 3D target (a model, a BrickGPT structure or a mesh)")
    hollowed = (f", hollow {hollow}" if hollow else "") + (", supports" if supports else "")
    hollowed += f" up to {support_height} cells" if supports and support_height else ""
    finish = (lambda mask: with_supports(mask, max_height=support_height)) if supports else (lambda mask: mask)
    if is_3d:
        if is_mesh:
            occupied, name, kind = mesh_mask(path, voxels, up), path.name, f"mesh, {voxels} voxels"
        else:
            if spec.startswith(BRICKGPT_PREFIX):
                structure = brickgpt.find(spec[len(BRICKGPT_PREFIX):], brickgpt_dir)
                bricks, name = structure.bricks, f"{BRICKGPT_PREFIX}{structure.structure_id[:8]}"
            else:
                bricks, name = brickgpt.parse(path.read_text(encoding="utf-8")), path.name
            if not bricks:
                raise ValueError(f"{spec}: no bricks")
            occupied, kind = brickgpt.occupancy(bricks), "BrickGPT structure"
        kind += ", solid columns" if columns else ", exact cells"
        return Target(finish(scaled_to(occupied, cells, columns, hollow, keep_sections)), None,
                      f"{name} ({kind}{hollowed})")
    if spec in SHAPES:
        return Target(sized_for(spec, cells), None, f"{spec} (primitive)")
    if is_image:
        silhouette = Image.open(path)
        heights = column_heights(silhouette, Image.open(height_map) if height_map else None, height)
        if not heights.any():
            raise ValueError(f"{spec}: no pixel is inside the silhouette (dark or opaque)")
        mask, factor = from_heights(heights, cells, scale_height=height_map is not None)
        box = bounds(mask)
        preferred = None
        if color_map:
            image = Image.open(color_map)
            if image.size != silhouette.size:
                raise ValueError(f"color map is {image.size} pixels, silhouette {silhouette.size}")
            preferred = resample(preferred_colors(image, colors), (factor, factor))[box[1:]]
        return Target(mask[box], preferred, f"{path.name} (silhouette, scaled x{factor:.2f})")
    if path.suffix.lower() in (".ldr", ".mpd"):
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        text = fetch_set(spec, data_dir).read_text(encoding="utf-8", errors="replace")
    placed, _ = voxelize(flatten(text))
    if not placed:
        raise ValueError(f"{spec}: no catalog parts on the stud grid to take a shape from")
    kind = "model, exact cells" if exact else "model, solid columns"
    return Target(finish(from_model(placed, cells, solid_columns=not exact, shell=hollow, keep_sections=keep_sections)),
                  None,
                  f"{path.stem if path.suffix else spec} ({kind}{hollowed})")
