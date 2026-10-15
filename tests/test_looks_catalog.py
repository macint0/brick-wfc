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


def test_a_slack_replaces_the_looks_slack() -> None:
    flags = looks.arm_flags("matched", 0.7218534752661239)
    assert flags[flags.index("--fill-slack") + 1] == "0.7218534752661239"
    assert float(flags[flags.index("--fill-slack") + 1]) == 0.7218534752661239
    assert looks.arm_flags("matched") == looks.LOOKS and looks.LOOKS.count("--fill-slack") == 1


def test_matched_slack_iterates_until_the_volumes_match(monkeypatch) -> None:
    """A part is left out of the volume once the target is small enough, so the first guess misses; the next round
    matches."""
    monkeypatch.setattr(looks, "load_source", lambda spec, data, catalog: catalog)

    def sized(source, config, data):
        base = 1000.0 if source == "m12b" else 1200.0 - (100.0 if config.fill_slack < 0.75 else 0.0)
        return None, {"volume": config.fill_slack * base, "left_out": {}}

    monkeypatch.setattr(looks, "sized_target", sized)
    found = looks.matched_slack("5891-1", "chair")
    assert found["old_volume"] == 800.0 and abs(found["volume"] - 800.0) <= 1e-6 * 800
    assert len(found["tried"]) == 3 and abs(found["slack"] - 800 / 1100) < 1e-12


def test_accounting_counts_placed_unfittable_and_unused() -> None:
    window = "window1x2x2_60592"
    door = "doorframe1x4x6_60596"
    key = {"inventory": [[window, "white", 3], [door, "white", 1], ["plate1x1", "red", 5], ["jumper1x2_3794a", "red", 2]],
           "fit_nowhere": [door]}
    part = lambda name: PlacedPart(Shape(CATALOG[name]), RED, 0, 0, 0)
    selected = [part(window), part(window), part("plate1x1"), part("jumper1x2_3794a")]
    a = looks.accounting(key, selected, [selected, [part(window)]])
    assert a["frames"][window] == {"inventory": 3, "unfittable": 0, "placed": 2, "placed_mean": 1.5, "unused": 1}
    assert a["frames"][door] == {"inventory": 1, "unfittable": 1, "placed": 0, "placed_mean": 0.0, "unused": 0}
    assert a["kinds"]["jumper"]["placed"] == 1 and a["kinds"]["jumper"]["unused"] == 1
    assert a["all_new"]["inventory"] == 6 and a["all_new"]["unused"] == 2
    row = looks.accounting_table([{"object": "chair", "set": "5891-1", "arm": "matched", "accounting": a}])
    assert f"| 4 / 1 / 2 (1.5) / 1 | {door} x1 |" in row


def test_the_matched_arm_runs_on_its_sets_with_its_slack(tmp_path: Path, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(looks, "pipeline_main", lambda argv: calls.append(argv))
    for set_number in ("6378-1", "5891-1"):
        path = looks.run_dir(tmp_path, "matched", set_number, "car") / "slack.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"slack": 0.75}), encoding="utf-8")
    args = looks.parser().parse_args(["--out", str(tmp_path), "--arms", "matched"])
    args.pairs = (("6378-1", "car"), ("5891-1", "car"))
    looks.step_run(args)
    assert len(calls) == 1 and calls[0][0] == "5891-1"
    assert calls[0][calls[0].index("--fill-slack") + 1] == "0.75"
