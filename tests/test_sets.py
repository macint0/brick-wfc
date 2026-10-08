from pathlib import Path

import pytest

from brickwfc.experiments import sets
from brickwfc.experiments.sets import CANDIDATES, evaluate, markdown, select

HOUSE = """0 FILE main.ldr
1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat
1 4 0 -32 0 1 0 0 0 1 0 0 0 1 3020.dat
1 4 0 -40 0 1 0 0 0 1 0 0 0 1 3794b.dat
0 NOFILE
"""


def test_candidates_are_unique_and_oldest_first() -> None:
    numbers = [c[0] for c in CANDIDATES]
    assert len(numbers) == len(set(numbers))
    years = [c[3] for c in CANDIDATES]
    assert years == sorted(years)


def test_evaluate_marks_rereleases_and_missing_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sets, "CANDIDATES", [("1-1", "House", "Town", 1980), ("2-1", "House again", "Town", 1990),
                                              ("3-1", "Gone", "Town", 1995)])
    for number in ("1-1", "2-1"):
        (tmp_path / f"{number}.mpd").write_text(HOUSE)

    def fetch(number: str, data: Path) -> Path:
        path = data / f"{number}.mpd"
        if not path.exists():
            raise sets.urllib.error.HTTPError("url", 404, "Not Found", None, None)
        return path

    monkeypatch.setattr(sets, "fetch_set", fetch)
    rows = evaluate(tmp_path)
    assert [r["note"] for r in rows] == ["", "re-release of 1-1", "unavailable (HTTP 404)"]
    assert rows[0]["parts"] == 3 and rows[0]["catalog_pct"] == pytest.approx(200 / 3)
    assert [r["set"] for r in select(rows, min_share=50, min_parts=3)] == ["1-1"]
    assert select(rows, min_share=70, min_parts=3) == [] and select(rows, min_share=50, min_parts=4) == []
    assert rows[0]["on_grid"] == 2 and rows[0]["catalog"] == 2  # the jumper plate (3794b) is not a catalog part
    assert "| 1-1 | House | Town | 1980 | 3 | 66.7 | 2 | 100 | 0 | 0 | 0 | yes |" in markdown(rows, 50, 3, 50)
    assert "| 2-1 | House again | Town | 1990 | 3 | 66.7 | 2 | 100 | 0 | 0 | 0 | re-release of 1-1 |" in markdown(rows, 50, 3)
    rows[0]["on_grid"] = 0  # nothing on the grid
    assert select(rows, 50, 3, min_on_grid=50) == [] and "< 50% on grid" in markdown(rows, 50, 3, 50)
