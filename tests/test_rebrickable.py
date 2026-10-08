"""M12c: set inventories from Rebrickable's bulk CSVs (a tiny synthetic bundle; no network)."""

import csv
import gzip
import io
import urllib.error
from collections import Counter
from pathlib import Path

import pytest

from brickwfc.alt import inputs
from brickwfc.bricks import rebrickable
from brickwfc.bricks.rebrickable import RBColor, Rebrickable, map_color, map_part
from brickwfc.experiments.rebrickable_check import compare, differences, jaccard, largest_differences, report

TABLES = {
    "sets": [["set_num", "name", "year", "theme_id", "num_parts", "img_url"],
             ["9999-1", "Test House", "2001", "1", "20", ""], ["8888-1", "Other", "1999", "1", "1", ""]],
    "inventories": [["id", "version", "set_num"], ["10", "1", "9999-1"], ["11", "2", "9999-1"], ["12", "1", "8888-1"]],
    "inventory_parts": [
        ["inventory_id", "part_num", "color_id", "quantity", "is_spare", "img_url"],
        ["10", "3001", "4", "99", "False", ""],  # an older version: not used
        ["11", "3001", "4", "6", "False", ""],  # brick 2x4, red
        ["11", "3001", "4", "1", "True", ""],  # spare: skipped
        ["11", "3069bpr0099", "15", "2", "False", ""],  # printed tile 1x2 -> 3069b
        ["11", "3003a", "71", "3", "False", ""],  # mold variant of 2x2 brick -> 3003
        ["11", "3626c", "14", "4", "False", ""],  # a minifig head: not in the catalog
        ["11", "3024", "326", "2", "False", ""],  # olive green: LDraw 330
        ["11", "3024", "182", "1", "False", ""],  # trans-orange: LDraw 57
        ["11", "3023", "999", "2", "False", ""],  # unknown color: nearest RGB, flagged
        ["12", "3001", "0", "1", "False", ""],
    ],
    "colors": [["id", "name", "rgb", "is_trans", "num_parts", "num_sets", "y1", "y2"],
               ["0", "Black", "05131D", "False", "1", "1", "", ""], ["4", "Red", "C91A09", "False", "1", "1", "", ""],
               ["14", "Yellow", "F2CD37", "False", "1", "1", "", ""], ["15", "White", "FFFFFF", "False", "1", "1", "", ""],
               ["71", "Light Bluish Gray", "A0A5A9", "False", "1", "1", "", ""],
               ["182", "Trans-Orange", "F08F1C", "True", "1", "1", "", ""],
               ["326", "Olive Green", "9B9A5A", "False", "1", "1", "", ""],
               ["999", "Weird Blue", "1F5BA9", "False", "1", "1", "", ""]],
    "part_relationships": [["rel_type", "child_part_num", "parent_part_num"], ["P", "3069bpr0099", "3069b"],
                           ["M", "3003a", "3003"], ["A", "3001", "3001old"]],
}


def write_bundle(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for name, table in TABLES.items():
        with gzip.open(directory / f"{name}.csv.gz", "wt", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(table)
    return directory


def test_inventory_from_the_bundle(tmp_path: Path) -> None:
    db = Rebrickable(write_bundle(tmp_path / "rb"), download=False)
    inventory, ignored, colors, info = db.inventory("9999-1")
    assert info.inventory_version == 2 and info.name == "Test House" and info.year == 2001
    assert inventory == {("brick2x4", "red"): 6, ("tile1x2", "white"): 2, ("brick2x2", "light_gray"): 3,
                         ("plate1x1", "ldraw330"): 2, ("plate1x1", "ldraw57"): 1, ("plate1x2", "blue"): 2}
    assert ignored == Counter({"3626c": 4}) and info.parts == 20 and info.recognized == 16
    assert info.via_parent == Counter({"3069bpr0099 -> 3069b": 2, "3003a -> 3003": 3})
    assert info.guessed_colors == Counter({"Weird Blue -> blue": 2})
    assert {c.name for c in colors} == {"red", "white", "light_gray", "ldraw330", "ldraw57", "blue"}
    assert (tmp_path / "rb" / "sets" / "9999-1.json").exists()  # cached: the big file is not read again
    (tmp_path / "rb" / "inventory_parts.csv.gz").unlink()
    assert db.inventory("9999-1")[0] == inventory
    with pytest.raises(KeyError):
        db.inventory("1234-1")


def test_part_and_color_mapping() -> None:
    parents = {"a": "b", "b": "3001", "loop1": "loop2", "loop2": "loop1"}
    assert map_part("a", parents)[0].name == "brick2x4" and map_part("a", parents)[1] == "3001"
    assert map_part("loop1", parents) == (None, None) and map_part("3062B", {})[0].name == "brick1x1_3062b"
    color, guessed = map_color(RBColor(484, "Dark Orange", (169, 85, 0)))
    assert (color.ldraw, guessed) == (484, False)
    color, guessed = map_color(RBColor(5000, "New", (250, 200, 10)))
    assert color.name == "yellow" and guessed


def test_fetch_downloads_once_and_reports_http_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(request, timeout):
        calls.append(request.full_url)
        if "colors" in request.full_url:
            raise urllib.error.HTTPError(request.full_url, 503, "Unavailable", {}, None)
        return Response(b"data")

    monkeypatch.setattr(rebrickable.urllib.request, "urlopen", urlopen)
    paths = rebrickable.fetch(tmp_path, names=("sets", "inventories"))
    assert [p.read_bytes() for p in paths] == [b"data", b"data"] and len(calls) == 2
    rebrickable.fetch(tmp_path, names=("sets",))
    assert len(calls) == 2  # already there
    with pytest.raises(RuntimeError, match="HTTP 503"):
        rebrickable.fetch(tmp_path, names=("colors",))
    assert not (tmp_path / "colors.csv.gz").exists() and not list(tmp_path.glob("*.part"))


def test_alt_input_prefix_and_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rb = write_bundle(tmp_path / "rb")
    monkeypatch.setattr(rebrickable, "fetch", lambda *a, **k: [])  # never download in tests
    forced = inputs.load_source("rebrickable:9999-1", tmp_path / "omr", rb)
    assert forced.name == "9999-1" and forced.model is None and forced.recognized_parts == 16 and forced.ignored == {"3626c": 4}

    def missing(set_number, out_dir):
        raise urllib.error.HTTPError(f"https://omr/{set_number}.mpd", 404, "Not Found", {}, None)

    monkeypatch.setattr(inputs, "fetch_set", missing)
    fallback = inputs.load_source("9999-1", tmp_path / "omr", rb)
    assert fallback.inventory == forced.inventory

    def broken(set_number, out_dir):
        raise urllib.error.HTTPError(f"https://omr/{set_number}.mpd", 500, "Server Error", {}, None)

    monkeypatch.setattr(inputs, "fetch_set", broken)
    with pytest.raises(urllib.error.HTTPError):  # only a missing model falls back
        inputs.load_source("9999-1", tmp_path / "omr", rb)


def test_check_metrics_and_report() -> None:
    omr = {("brick2x4", "red"): 4, ("plate1x1", "ldraw84"): 3}
    rb = {("brick2x4", "red"): 4, ("plate1x1", "ldraw484"): 3, ("tile1x2", "white"): 1}
    assert jaccard(omr, omr) == 1 and jaccard(omr, rb) == pytest.approx(4 / 11)
    row = compare(omr, rb)
    assert row["agreement_parts"] == pytest.approx(7 / 8) and row["agreement_colors"] == pytest.approx(4 / 11)
    assert largest_differences(omr, rb)[0][2] in (3, -3)
    colors = differences([(omr, rb)], 1)
    assert ("ldraw484", 3, 1, 0) in colors and ("ldraw84", -3, 0, 1) in colors
    rows = [{"set": "x", "name": "n", "year": 1, "inventory_version": 1, **row,
             "largest_differences": largest_differences(omr, rb)}]
    text = report(rows, differences([(omr, rb)], 0), colors, Counter(), Counter(), Counter({"3626c": 4}))
    assert "Sets below 0.9 agreement" in text and "- x (0.364)" in text and "3626c: 4" in text
