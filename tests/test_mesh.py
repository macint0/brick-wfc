"""M12b steps 1b and 1c: mesh targets and hollow shells."""

import json
from pathlib import Path

import numpy as np
import pytest
import trimesh
from scipy import ndimage

from brickwfc.alt.pipeline import main
from brickwfc.alt.target import load_target
from brickwfc.bricks.mesh import load_mesh, voxelize_mesh
from brickwfc.bricks.shapes import block, hollow, scaled_to, surface
from conftest import RED


def test_box_voxelizes_to_a_full_box_in_plates() -> None:
    mask = voxelize_mesh(trimesh.creation.box(extents=(4, 2, 8)), voxels=16)  # x 4, y (up) 2, z 8
    y, z, x = mask.shape
    assert mask.all()
    assert abs(z - 16) <= 1 and abs(x - 8) <= 1  # longest side: 16 cells; pitch 0.5
    assert abs(y - 2 * 2.5 / 0.5) <= 1  # a plate is 0.4 studs: 2 units up are 10 plates


def test_sphere_is_filled_and_round() -> None:
    mask = voxelize_mesh(trimesh.creation.icosphere(subdivisions=3), voxels=16)
    assert abs(mask.sum() / mask.size - np.pi / 6) < 0.05  # a ball fills ~52% of its box
    assert not ndimage.binary_fill_holes(mask)[~mask].any()  # solid: no enclosed empty cells
    assert mask[mask.shape[0] // 2, 8, 8] and not mask[0, 0, 0]


def test_up_axis_z() -> None:
    tall = trimesh.creation.box(extents=(2, 2, 8))  # long along z
    assert voxelize_mesh(tall, 8, up="z").shape[0] > voxelize_mesh(tall, 8, up="y").shape[0]


def test_open_mesh_is_refused(tmp_path: Path) -> None:
    box = trimesh.creation.box()
    open_box = trimesh.Trimesh(box.vertices, box.faces[:-2])
    open_box.export(tmp_path / "open.stl")
    with pytest.raises(ValueError, match="watertight"):
        load_mesh(tmp_path / "open.stl")


def test_load_target_from_mesh_files(tmp_path: Path) -> None:
    trimesh.creation.icosphere(subdivisions=2).export(tmp_path / "ball.obj")
    trimesh.creation.box(extents=(3, 1, 2)).export(tmp_path / "box.stl")
    for name in ("ball.obj", "box.stl"):
        target = load_target(str(tmp_path / name), 1500, [RED], voxels=12)
        assert abs(target.mask.sum() - 1500) / 1500 < 0.15 and "mesh, 12 voxels" in target.description
    columns = load_target(str(tmp_path / "ball.obj"), 1500, [RED], voxels=12, columns=True)
    assert not (columns.mask[1:] & ~columns.mask[:-1]).any()


def test_hollow_shell_and_pillars() -> None:
    mask = block(12, 12, 12)
    shell = hollow(mask, 2)
    assert (shell <= mask).all() and shell.sum() < mask.sum()
    assert shell[:2].all() and shell[-2:].all() and shell[:, :2].all() and shell[:, :, :2].all()  # 2 cells thick
    inside = ndimage.binary_erosion(mask, iterations=2)
    pillars = shell & inside
    assert pillars.any() and pillars.sum() < inside.sum() / 2  # sparse supports, mostly hollow
    # Every pillar cell stands on a filled cell (down to the floor shell), and every hollow cell under the
    # roof is next to a pillar or a wall (the roof spans period - width = 2 studs between them).
    ys, zs, xs = np.nonzero(pillars)
    assert shell[ys - 1, zs, xs].all()
    under_roof = shell[-3]
    assert (~under_roof).any() and ndimage.binary_dilation(under_roof, structure=np.ones((3, 3))).all()
    assert np.array_equal(hollow(mask, 0), mask)


def test_hollow_keeps_the_volume_with_a_larger_object() -> None:
    ball = voxelize_mesh(trimesh.creation.icosphere(subdivisions=3), voxels=16)
    solid = scaled_to(ball, 3000)
    hollowed = scaled_to(ball, 3000, shell=2)
    assert abs(hollowed.sum() - 3000) / 3000 < 0.15
    assert hollowed.shape[2] > solid.shape[2]  # the same cells make a wider object


def test_surface_ignores_the_hollow_inside() -> None:
    mask = block(6, 6, 6)
    outer = surface(mask)
    assert outer.sum() == 6**3 - 4**3 and not outer[1:-1, 1:-1, 1:-1].any()
    assert np.array_equal(surface(hollow(mask, 1, period=100)), outer)  # the enclosed void is not outside


def test_variant_args() -> None:
    from brickwfc.experiments.brickgpt import variant_args

    assert variant_args("exact") == ["--no-open-tops"] and variant_args("opentops") == []
    assert variant_args("columns") == ["--no-open-tops", "--shape-columns"]
    assert variant_args("hollow2") == ["--hollow", "2"]
    with pytest.raises(ValueError):
        variant_args("solid")


def test_hollow_target_errors(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_target("pyramid", 500, [RED], hollow=2)


def test_cli_with_hollow_mesh(tiny_ldr: Path, style_dir: tuple[Path, Path], tmp_path: Path) -> None:
    trimesh.creation.box(extents=(3, 2, 3)).export(tmp_path / "box.stl")
    out = tmp_path / "out"
    args = [str(tiny_ldr), "--shape", str(tmp_path / "box.stl"), "--voxels", "8", "--hollow", "1", "--n", "6",
            "--k", "1", "--workers", "1", "--out", str(out), "--style-dir", str(style_dir[0]),
            "--sets-file", str(style_dir[1])]
    main(args)
    stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    assert "mesh, 8 voxels, exact cells, hollow 1" in stats["shape"] and stats["config"]["hollow"] == 1
