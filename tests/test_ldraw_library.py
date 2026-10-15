"""M12d: the LDraw library reader that measures catalog facts (offline: a fake library in a dict)."""

from pathlib import Path

import pytest

from brickwfc.ldraw.library import cached_loader, facts, library_paths

# A 1 x 2 "plate" with one stud on its +x cell, a side stud facing -z, a bottom face under its -x cell only,
# and a subpart that holds its body's far corner.
FILES = {
    "parts/test.dat": """0 Test Plate 1 x 2
1 16 10 0 0 1 0 0 0 1 0 0 0 1 stud.dat
1 16 -10 4 -10 1 0 0 0 0 -1 0 1 0 stud.dat
1 16 0 0 0 1 0 0 0 1 0 0 0 1 s\\tests01.dat
4 16 -20 8 -10 0 8 -10 0 8 10 -20 8 10
3 16 -20 0 -10 20 0 -10 20 0 10
""",
    "parts/s/tests01.dat": "0 Subpart\n2 24 20 8 10 20 0 10\n",
}


def load(name: str) -> str:
    return next((FILES[path] for path in library_paths(name) if path in FILES), "")


def test_library_paths() -> None:
    assert library_paths("s\\3001s01.dat") == ["parts/s/3001s01.dat"]
    assert library_paths("48\\4-4cyli.dat") == ["p/48/4-4cyli.dat"]
    assert library_paths("Stud.dat") == ["parts/stud.dat", "p/stud.dat"]


def test_facts_of_a_resolved_part() -> None:
    f = facts("test", load)
    assert f.title == "Test Plate 1 x 2" and f.missing == ()
    assert f.top_studs == [(10.0, 0.0)] and f.top_stud_y == [0.0]
    assert [direction for _, direction in f.side_studs] == [(0.0, 0.0, -1.0)]
    assert (f.x, f.z, f.y) == ((-20.0, 20.0), (-10.0, 10.0), (0.0, 8.0))  # the subpart's line reaches x = 20
    assert f.bottom_cover == {(-10.0, 0.0): 1.0, (10.0, 0.0): 0.0}


def test_cache_is_read_without_fetching(tmp_path: Path) -> None:
    for path, text in FILES.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(text, encoding="utf-8")
    offline = cached_loader(tmp_path, fetch=False)
    assert facts("test", offline).top_studs == [(10.0, 0.0)]
    assert offline("missing.dat") == ""
    with pytest.raises(ValueError):
        facts("missing", offline)  # nothing to measure
