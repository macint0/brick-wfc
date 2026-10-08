"""The M12b comparison driver: which style statistics it reads."""

import json
from pathlib import Path

import pytest

from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import CATALOG, PlacedPart, Shape
from brickwfc.bricks.style import StyleStats
from brickwfc.experiments import proposal

RED, BLUE = colors_by_name(["red", "blue"])


def piece(name: str, layer: int, x: int, z: int, color=RED) -> PlacedPart:
    return PlacedPart(Shape(CATALOG[name], 0), color, layer, x, z)


def model() -> list[PlacedPart]:
    """Plates on the floor, two bricks and two slopes on them."""
    floor = [piece("plate2x4", 0, x, z, BLUE) for x in (0, 4) for z in (0, 2)]
    return floor + [piece("brick2x4", 1, 0, 0), piece("brick2x4", 1, 4, 0), piece("slope45_2x1", 1, 0, 2),
                    piece("slope45_2x2", 1, 4, 2)]


def test_style_version_defaults_to_v2_and_the_pipelines_file(tmp_path: Path) -> None:
    from brickwfc.alt.inputs import STYLE_FILES, STYLE_VERSION

    assert STYLE_VERSION == "v2"
    assert proposal.style_file(tmp_path, 0, "v2") == tmp_path / STYLE_FILES["v2"].format(i=0)
    sets_file = tmp_path / "sets.json"
    sets_file.write_text(json.dumps({"selected": [f"s{i}" for i in range(8)]}), encoding="utf-8")
    StyleStats().add(model()).save(tmp_path / "style" / "style_fold0_v2.json")  # only v2 exists
    args = ["--random-weights", "--sets-file", str(sets_file), "--style-dir", str(tmp_path / "style"),
            "--sets", "none", "--out", str(tmp_path / "out")]
    assert proposal.main(args) == 0
    with pytest.raises(FileNotFoundError):
        proposal.main(args + ["--style-version", "v1"])


def test_resume_refuses_builds_with_other_statistics(tmp_path: Path) -> None:
    sets_file = tmp_path / "sets.json"
    sets_file.write_text(json.dumps({"selected": [f"s{i}" for i in range(8)]}), encoding="utf-8")
    StyleStats().add(model()).save(tmp_path / "style" / "style_fold0_v2.json")
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "runs.jsonl").write_text(json.dumps({"set_number": "s0", "condition": "stats_raster",
                                                             "seed": 0}) + "\n", encoding="utf-8")  # no version: v1
    with pytest.raises(SystemExit):
        proposal.main(["--random-weights", "--sets-file", str(sets_file), "--style-dir", str(tmp_path / "style"),
                       "--sets", "none", "--out", str(tmp_path / "out")])

