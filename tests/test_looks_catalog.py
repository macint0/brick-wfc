"""M12d looks driver (``experiments/looks.py``): arms, new-part kinds, skin vs interior, tables, resumable runs."""

import json
from pathlib import Path

import numpy as np
from PIL import Image

from brickwfc.bricks.parts import CATALOG, M12B_FILES, M12D_JUMPERS, PlacedPart, Shape
from brickwfc.bricks.symmetry import best_plane
from brickwfc.experiments import looks
from conftest import BLUE, RED


def test_the_arms_differ_only_in_catalog_and_style() -> None:
    old, new = looks.arm_flags("old"), looks.arm_flags("new")
    assert new == looks.LOOKS
    assert old[:len(new)] == new
    assert old[len(new):] == ["--catalog", "m12b", "--style-version", "v2"]
    assert looks.LOOKS[looks.LOOKS.index("--fill-slack") + 1] == str(looks.SLACK)


def test_every_part_after_m12b_has_a_kind() -> None:
    old = {p.name for p in M12B_FILES.values()}
    for name in CATALOG:
        kind = looks.new_kind(name)
        assert (kind is None) == (name in old), name
        assert kind != "other", name
    assert looks.new_kind("plate1x1") is None
    assert looks.new_kind(M12D_JUMPERS[0].name) == "jumper"
    assert set(looks.KINDS.values()) == set(looks.KIND_ORDER)


def block_with_jumpers() -> tuple[list[PlacedPart], tuple[int, int, int]]:
    """A 3-layer block of 1x1 plates, 3 deep and 4 wide, with a jumper buried in the middle layer and one in the top
    layer: the buried one has no skin face, the top one has."""
    jumper = Shape(CATALOG[M12D_JUMPERS[0].name])
    shape = (3, 3, 4)
    buried, top = PlacedPart(jumper, RED, 1, 1, 1), PlacedPart(jumper, BLUE, 2, 1, 1)
    taken = {cell for p in (buried, top) for cell in p.cells()}
    assert len(taken) == 4 and all(cell[1] == 1 and cell[2] in (1, 2) for cell in taken)
    plates = [PlacedPart(Shape(CATALOG["plate1x1"]), RED, y, x, z) for y in range(3) for z in range(3)
              for x in range(4) if (y, z, x) not in taken]
    return [buried, top, *plates], shape


def test_new_parts_on_the_skin_and_inside() -> None:
    placed, shape = block_with_jumpers()
    faces = looks.skin_faces_by_part(placed, shape)
    assert 0 not in faces and faces[1] == 2  # the buried jumper shows nothing, the top one its two top faces
    row = looks.parts_row(placed, shape)
    assert row["parts"] == len(placed) and row["names"] == 2 and row["new_names"] == 1
    assert row["new_parts"] == 2 and row["new_on_skin"] == 1
    assert row["new_by_kind"] == {"jumper": {"placed": 2, "skin": 1}}
    assert row["new_skin_face_pct"] == 100 * 2 / sum(faces.values())


def test_build_row_on_a_full_target() -> None:
    placed, shape = block_with_jumpers()
    mask = np.ones(shape, dtype=bool)
    row = looks.build_row(placed, mask, best_plane(mask))
    assert row["fill_pct"] == 100 and row["largest_hole"] == 0 and row["complete"]
    assert row["new_on_skin"] == 1


def cell(arm: str, obj: str, fill: float, seams: float, kinds: dict, names: list[str]) -> dict:
    selected = {"fill_pct": fill, "largest_hole": 3, "surface_pct": 99.0, "top_window_parts": 2.0,
                "side_window_parts": 2.0, "mirrored_pct": 50.0, "seams_pct": seams, "new_by_kind": kinds,
                "new_names_list": names}
    return {"arm": arm, "set": "6378-1", "object": obj, "valid": 40, "selected": selected}


def test_delta_and_kinds_tables() -> None:
    jumper = M12D_JUMPERS[0].name
    cells = [cell("old", "chair", 90.0, 50.0, {}, []),
             cell("new", "chair", 95.0, 40.0, {"jumper": {"placed": 3, "skin": 1}}, [jumper]),
             cell("old", "car", 80.0, 60.0, {}, []),
             cell("new", "car", 80.0, 60.0, {"jumper": {"placed": 1, "skin": 1}}, [jumper])]
    table = looks.delta_table(cells)
    assert "90.0 -> 95.0 +" in table and "50 -> 40 -" in table and "80.0 -> 80.0 =" in table
    assert table.splitlines()[-1].split(" | ")[2] == "1 / 0 / 1"  # fill: better on the chair, equal on the car
    kinds = looks.kinds_table(cells)
    assert f"| jumper | 4 | 2 | {jumper} |" in kinds and "| all | 4 | 2 | |" in kinds


def test_strip_puts_pictures_side_by_side(tmp_path: Path) -> None:
    paths = []
    for i, size in enumerate(((100, 50), (40, 40))):
        paths.append(tmp_path / f"{i}.png")
        Image.new("RGB", size, (i * 100, 0, 0)).save(paths[-1])
    out = looks.strip([str(p) for p in paths], tmp_path / "strip.png", height=20, gap=4)
    assert Image.open(out).size == (40 + 4 + 20, 20)


def test_run_skips_finished_runs_and_passes_the_flags(tmp_path: Path, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(looks, "pipeline_main", lambda argv: calls.append(argv))
    done = looks.run_dir(tmp_path, "old", "6378-1", "table")
    done.mkdir(parents=True)
    (done / "stats.json").write_text(json.dumps({"requested": 3}), encoding="utf-8")
    args = looks.parser().parse_args(["--out", str(tmp_path), "--n", "3", "--data", "omr"])
    args.pairs = (("6378-1", "table"),)
    looks.step_run(args)
    assert len(calls) == 1
    argv = calls[0]
    assert argv[0] == "6378-1" and argv[argv.index("--out") + 1] == str(looks.run_dir(tmp_path, "new", "6378-1", "table"))
    assert argv[argv.index("--data") + 1] == "omr" and argv[-len(looks.LOOKS):] == looks.LOOKS


def test_nanmean_skips_builds_without_a_window() -> None:
    assert looks.nanmean([2.0, float("nan"), 4.0]) == 3.0
    assert np.isnan(looks.nanmean([float("nan")]))
