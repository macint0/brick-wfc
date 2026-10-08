"""Target shapes from triangle meshes (M12b step 1b): ``.obj``, ``.stl``, ``.ply``, ``.off`` via ``trimesh``.

A mesh must be watertight (a closed surface), so its inside is defined. It is voxelized so a voxel is one
grid cell, 1 stud x 1 stud x 1 plate: the mesh's up axis is stretched by 2.5 (a plate is 0.4 studs tall)
and the voxel pitch is its longest side / ``voxels``, so the result is ``voxels`` cells along its longest
side in studs. The surface voxels are filled to a solid. The caller rescales the mask to an inventory's
volume (``shapes.scaled_to``), so ``voxels`` sets the detail kept, not the final size.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage

from brickwfc.bricks.shapes import Mask, bounds

MESH_SUFFIXES = (".obj", ".stl", ".ply", ".off")
PLATES_PER_STUD = 2.5
UP_AXES = ("y", "z")


def load_mesh(path: Path) -> trimesh.Trimesh:
    """The mesh in ``path`` (several bodies are concatenated); ValueError if it is not watertight."""
    mesh = trimesh.load(path, force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError(f"{path}: no triangles")
    if not mesh.is_watertight:
        raise ValueError(f"{path}: the mesh is not watertight (it has holes), so its inside is undefined; "
                         "close it first (e.g. in Blender: 3D Print Toolbox > Make Manifold)")
    return mesh


def voxelize_mesh(mesh: trimesh.Trimesh, voxels: int = 32, up: str = "y") -> Mask:
    """(Y, Z, X) solid cells of ``mesh``, ``voxels`` cells along its longest side (in studs)."""
    if up not in UP_AXES:
        raise ValueError(f"up axis must be one of {UP_AXES}")
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    if up == "z":  # turn z-up into y-up, keeping handedness: (x, y, z) -> (x, z, -y)
        vertices = np.column_stack([vertices[:, 0], vertices[:, 2], -vertices[:, 1]])
    pitch = float((vertices.max(axis=0) - vertices.min(axis=0)).max()) / voxels
    vertices = (vertices - vertices.min(axis=0)) * np.array([1.0, PLATES_PER_STUD, 1.0])
    stretched = trimesh.Trimesh(vertices, mesh.faces, process=False)
    grid = stretched.voxelized(pitch).matrix  # (x, y, z) surface voxels
    solid = ndimage.binary_fill_holes(grid)
    mask = np.transpose(solid, (1, 2, 0))  # (y, z, x)
    if not mask.any():
        raise ValueError("the mesh voxelized to nothing; raise --voxels")
    return mask[bounds(mask)]


def mesh_mask(path: Path, voxels: int = 32, up: str = "y") -> Mask:
    return voxelize_mesh(load_mesh(path), voxels, up)
