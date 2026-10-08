"""M12b step 1a: BrickGPT structures as 3D targets (no network: fetching is faked)."""

import json
from pathlib import Path

import numpy as np
import pytest

from brickwfc.alt.pipeline import main
from brickwfc.alt.target import load_target
from brickwfc.bricks import brickgpt
from brickwfc.bricks.brickgpt import Brick, find, occupancy, overlaps, parse, to_placed
from brickwfc.bricks.physics import table_clutch
from brickwfc.experiments.brickgpt import pick_objects
from conftest import RED

# A small table: four 1x1 legs two bricks tall, a 2x6 + 2x6 top (h along x, w along y).
TABLE = """1x1 (0,0,0)
1x1 (3,0,0)
1x1 (0,5,0)
1x1 (3,5,0)
1x1 (0,0,1)
1x1 (3,0,1)
1x1 (0,5,1)
1x1 (3,5,1)

2x6 (0,0,2)
2x6 (2,0,2)
"""


def row(structure_id: str, category: str, bricks: str) -> dict:
    """A dataset row as the API returns it: scores per unit, indexed [x][y][z], 1 where empty."""
    scores = np.ones((brickgpt.GRID,) * 3)
    for b in parse(bricks):
        for x, y, z in b.units():
            scores[x, y, z] = 0.5 + 0.1 * z
    return {"structure_id": structure_id, "object_id": "o" + structure_id, "category_id": category,
            "captions": [f"a {category}"], "bricks": bricks, "stability_scores": scores.tolist()}


def test_parse_and_bad_lines() -> None:
    bricks = parse(TABLE)
    assert len(bricks) == 10 and bricks[-1] == Brick(2, 6, 2, 0, 2)
    with pytest.raises(ValueError, match="line 2"):
        parse("1x1 (0,0,0)\n2x2 0,0,1\n")


def test_h_runs_along_x() -> None:
    # Along x, the two 2x6 tops sit side by side; along y they would overlap.
    assert overlaps(parse(TABLE)) == 0
    swapped = [Brick(b.w, b.h, b.x, b.y, b.z) for b in parse(TABLE)]
    assert overlaps(swapped) > 0


def test_occupancy_in_cells() -> None:
    mask = occupancy(parse(TABLE))
    assert mask.shape == (60, 20, 20)  # (Y, Z, X): 20 units, 3 plates per brick
    assert mask.sum() == 3 * (8 + 24) and mask[6:9, :6, :4].all() and not mask[9:].any()
    assert mask[0:6, 5, 3].all() and not mask[0:6, 2, 2].any()  # a leg at x=3, y=5; under the top: empty


def test_to_placed_is_exact() -> None:
    bricks = parse(TABLE)
    placed = to_placed(bricks, RED)
    assert {p.shape.part.name for p in placed} == {"brick1x1", "brick2x6"}
    cells = {c for p in placed for c in p.cells()}
    assert cells == {tuple(int(i) for i in c) for c in np.argwhere(occupancy(bricks))}
    assert np.isfinite(table_clutch(placed, occupancy(bricks).shape))
    with pytest.raises(ValueError):
        to_placed([Brick(3, 5, 0, 0, 0)], RED)


def fake_api(monkeypatch: pytest.MonkeyPatch, rows: list[dict]) -> list[str]:
    calls = []

    def get_json(url: str) -> dict:
        calls.append(url)
        query = dict(part.split("=") for part in url.split("?")[1].split("&"))
        offset, length = int(query["offset"]), int(query["length"])
        page = [{"row_idx": i, "row": rows[i]} for i in range(offset, min(offset + length, len(rows)))]
        return {"rows": page, "num_rows_total": len(rows)}

    monkeypatch.setattr(brickgpt, "_get_json", get_json)
    return calls


def test_fetch_caches_and_resumes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rows = [row(f"id{i:02d}", "chair" if i % 2 else "table", TABLE) for i in range(5)]
    calls = fake_api(monkeypatch, rows)
    path = brickgpt.fetch_rows("test", tmp_path, page=2)
    assert len(calls) == 3 and len(path.read_text(encoding="utf-8").splitlines()) == 5
    cached = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert "stability_scores" not in cached and cached["scores"] == [0.5] * 4 + [0.6] * 4 + [0.7, 0.7]
    brickgpt.fetch_rows("test", tmp_path, page=2)  # complete: one call to learn the total, nothing appended
    assert len(calls) == 4 and len(path.read_text(encoding="utf-8").splitlines()) == 5
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:3]) + "\n", encoding="utf-8")  # a killed fetch: resumes at row 3
    brickgpt.fetch_rows("test", tmp_path, page=2)
    assert calls[-1].endswith("offset=3&length=2") and path.read_text(encoding="utf-8").splitlines() == lines


def test_find_by_prefix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_api(monkeypatch, [row("abc1", "chair", TABLE), row("abd2", "table", TABLE), row("xyz", "car", "1x1 (0,0,0)")])
    assert find("abc", tmp_path).structure_id == "abc1"
    with pytest.raises(ValueError, match="matches 2"):
        find("ab", tmp_path)
    with pytest.raises(ValueError, match="no such structure"):
        find("nope", tmp_path)


def test_load_target_brickgpt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_api(monkeypatch, [row("abc1", "chair", TABLE)])
    exact = load_target("brickgpt:abc1", 2000, [RED], brickgpt_dir=tmp_path)
    columns = load_target("brickgpt:abc1", 2000, [RED], columns=True, brickgpt_dir=tmp_path)
    assert "exact cells" in exact.description and "solid columns" in columns.description
    for target in (exact, columns):
        assert abs(target.mask.sum() - 2000) / 2000 < 0.15
    assert (exact.mask[0] & ~exact.mask[-1]).sum() < exact.mask[0].sum()  # exact: open under the table top
    assert not (columns.mask[1:] & ~columns.mask[:-1]).any()  # columns: nothing above an empty cell
    (tmp_path / "table.txt").write_text(TABLE, encoding="utf-8")
    local = load_target(str(tmp_path / "table.txt"), 2000, [RED])
    assert np.array_equal(local.mask, exact.mask)
    with pytest.raises(ValueError):
        load_target(str(tmp_path / "table.txt"), 2000, [RED], exact=True)
    with pytest.raises(ValueError):
        load_target("pyramid", 2000, [RED], columns=True)


def test_pick_objects_median_per_category() -> None:
    def structure(sid: str, cat: str, n: int) -> brickgpt.Structure:
        return brickgpt.Structure(sid, sid, cat, (), tuple(Brick(1, 1, i, 0, 0) for i in range(n)), ())

    pool = [structure(f"c{i}", "chair", n) for i, n in enumerate((5, 1, 9))]
    pool += [structure(f"t{i}", "table", n) for i, n in enumerate((3, 3, 7, 2))] + [structure("x", "car", 4)]
    picked = pick_objects(pool, categories=2)
    assert [s.structure_id for s in picked] == ["t1", "c0"]  # tables first (4 of them); medians by size, then id


def test_cli_with_brickgpt_txt(tiny_ldr: Path, style_dir: tuple[Path, Path], tmp_path: Path) -> None:
    (tmp_path / "table.txt").write_text(TABLE, encoding="utf-8")
    out = tmp_path / "out"
    args = [str(tiny_ldr), "--shape", str(tmp_path / "table.txt"), "--n", "6", "--k", "1", "--workers", "1",
            "--out", str(out), "--style-dir", str(style_dir[0]), "--sets-file", str(style_dir[1])]
    main(args)
    stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    assert "BrickGPT structure, exact cells" in stats["shape"] and stats["config"]["shape_columns"] is False
