"""M12b step 1d: support columns under far overhangs, the overhang loss, clutch calibration."""

import json

import numpy as np
import pytest

from brickwfc.alt.inputs import load_source
from brickwfc.alt.pipeline import AltConfig, main, make_target
from brickwfc.alt.target import load_target
from brickwfc.bricks.shapes import mushroom, unsupported_empty, with_supports
from brickwfc.experiments.brickgpt import REAL_CLUTCH, cantilever_clutch, variant_args
from conftest import RED

TABLE_TOP = """1x1 (0,0,0)
2x6 (0,0,1)
2x6 (2,0,1)
2x6 (4,0,1)
2x6 (6,0,1)
"""


def test_supports_only_under_far_overhangs() -> None:
    mask = mushroom(6, 14, 14, stem=2, cap_layers=1)  # a 2x2 stem under a 14x14 cap
    supported = with_supports(mask, reach=3)
    extra = supported & ~mask
    assert (supported >= mask).all() and extra.any()
    assert not extra[-1].any()  # nothing added beside the cap, only under it
    cap = mask.shape[0] - 1
    columns = extra[:cap].any(axis=0)
    assert columns[0, 0] and not columns[6, 6]  # under the far corner, not next to the stem
    assert extra[:cap, 0, 0].all()  # each column runs down to the ground
    assert np.array_equal(with_supports(mask, reach=20), mask)  # everything within reach: nothing added


def test_support_height_keeps_only_short_columns() -> None:
    low = mushroom(4, 14, 14, stem=2, cap_layers=1)  # the cap 3 cells above the ground
    high = mushroom(12, 14, 14, stem=2, cap_layers=1)  # 11 cells above
    assert np.array_equal(with_supports(low, max_height=3), with_supports(low))  # every column is 3 tall
    assert np.array_equal(with_supports(high, max_height=3), high)  # too tall: none
    short = mushroom(4, 14, 14, stem=2, cap_layers=1)
    short[0, :2, :2] = True  # a foot under one corner: that column now stops on it, 2 cells tall
    assert (with_supports(short, max_height=2) & ~short).sum() == 2 * 2 * 2


def test_unsupported_empty() -> None:
    mask = np.ones((3, 1, 3), dtype=bool)
    filled = np.zeros_like(mask)
    filled[0, 0, 0] = filled[1, 0, 0] = True
    loss = unsupported_empty(filled, mask)
    assert not loss[0].any()  # the ground supports everything
    assert loss[1, 0].tolist() == [False, True, True] and loss[2, 0].tolist() == [False, True, True]


def test_cantilever_calibration() -> None:
    lengths = (3, 4, 6, 8)
    plates = [cantilever_clutch(n) for n in lengths]
    bricks = [cantilever_clutch(n, "brick") for n in lengths]
    assert all(a < b for a, b in zip(plates, plates[1:]))  # longer arms need more grip
    assert all(b == pytest.approx(3 * p) for p, b in zip(plates, bricks))  # a brick weighs 3 plates
    assert 1000 < REAL_CLUTCH < 1250 and max(bricks) < REAL_CLUTCH


def test_supports_target(tmp_path) -> None:
    (tmp_path / "table.txt").write_text(TABLE_TOP, encoding="utf-8")
    plain = load_target(str(tmp_path / "table.txt"), 900, [RED])
    supported = load_target(str(tmp_path / "table.txt"), 900, [RED], supports=True)
    assert supported.mask.shape == plain.mask.shape and (supported.mask >= plain.mask).all()
    assert supported.mask.sum() > plain.mask.sum() and "supports" in supported.description
    assert variant_args("supports") == ["--supports", "--support-height", "0"] and variant_args("default") == []
    assert "--no-supports" in variant_args("exact") and "--no-supports" in variant_args("opentops")
    with pytest.raises(ValueError):
        load_target("pyramid", 500, [RED], supports=True)


def test_pipeline_defaults_real_clutch_and_short_supports(tiny_ldr, style_dir, tmp_path) -> None:
    defaults = AltConfig()
    assert defaults.max_clutch == pytest.approx(REAL_CLUTCH, abs=1)
    assert defaults.supports and defaults.support_height == 6
    table = tmp_path / "table.txt"
    table.write_text(TABLE_TOP, encoding="utf-8")
    source = load_source(str(tiny_ldr))
    assert "supports up to 6 cells" in make_target(source, AltConfig(shape=str(table))).description
    assert "supports" not in make_target(source, AltConfig(shape=str(table), supports=False)).description
    assert "supports" not in make_target(source, AltConfig(shape="pyramid")).description  # 2D targets: skipped
    out = tmp_path / "off"
    main([str(tiny_ldr), "--shape", str(table), "--no-supports", "--max-clutch", "inf", "--n", "2", "--k", "1",
          "--workers", "1", "--out", str(out), "--style-dir", str(style_dir[0]), "--sets-file", str(style_dir[1])])
    config = json.loads((out / "stats.json").read_text(encoding="utf-8"))["config"]
    assert config["supports"] is False and config["max_clutch"] == float("inf")
