"""The M12b shape-arm report: summaries of pipeline runs with a target shape, per arm."""

from pathlib import Path

from brickwfc.alt.pipeline import main as alt_main
from brickwfc.bricks.tokens import Vocab, build_vocab
from brickwfc.experiments import proposal_shape

WEIGHTS = Path(__file__).parent / "fixtures" / "proposal" / "proposal.npz"
ARMS = {"stats_random": [], "stats_raster": ["--order", "raster"],
        "proposal_raster": ["--order", "raster", "--proposal", str(WEIGHTS)]}


def test_summaries_and_sheet_of_three_arms(tiny_ldr: Path, style_dir: tuple[Path, Path], tmp_path: Path) -> None:
    for arm, extra in ARMS.items():
        assert alt_main([str(tiny_ldr), "--shape", "pyramid", "--n", "4", "--k", "1", "--workers", "1",
                         "--out", str(tmp_path / "runs" / "tiny" / arm), "--style-dir", str(style_dir[0]),
                         "--sets-file", str(style_dir[1]), *extra]) == 0
    full = build_vocab()
    vocab = Vocab(tuple(t for t in full.tokens if t != "S:plate2x4"))  # one shape the model lacks
    rows = [proposal_shape.summarize(str(tiny_ldr), arm, tmp_path / "runs" / "tiny" / arm, vocab, *style_dir)
            for arm in ARMS]
    for r in rows:
        assert r["candidates"] == 4 and 0 < r["valid_pct"] <= 100 and r["target_cells"] > 0
        assert 0 < r["fill_pct"] <= 100 and 0 < r["iou"] <= 1 and r["matched_judge"] < 0
        assert 0 < r["outside_vocab"] <= r["parts"]  # the tiny model's floor is 2x4 plates
    text = proposal_shape.table(rows)
    assert "proposal_raster vs stats_raster, object fill: higher on" in text
    seed = proposal_shape.sheet(rows, tmp_path / "runs" / "tiny", str(tiny_ldr), tmp_path / "sheet.png")
    assert (tmp_path / "sheet.png").exists() and all(seed in r["valid_seeds"] for r in rows)
