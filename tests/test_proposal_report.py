"""The M12b comparison report: per-set summaries, paired comparisons, and the determinism spot check."""

from pathlib import Path

from brickwfc.bricks.style import StyleStats
from brickwfc.experiments import proposal, proposal_report

from test_proposal_driver import model

FIXTURE_WEIGHTS = Path(__file__).parent / "fixtures" / "proposal" / "proposal.npz"


def row(s: str, condition: str, seed: int, judge: float) -> dict:
    return {"set_number": s, "condition": condition, "seed": seed, "fold": 0, "valid": True, "parts": 10,
            "utilization": 1.0, "matched_judge": judge, "matched_ceiling": -0.3, "distance": 0.2, "outside_vocab": 2,
            "wall_time_s": 1.0}


def test_summaries_compare_only_sets_with_every_condition() -> None:
    rows = [row("a", c, seed, j + 0.01 * seed) for c, j in (("stats_random", -0.5), ("stats_raster", -0.4),
                                                            ("proposal_raster", -0.3)) for seed in range(2)]
    rows += [row("b", "stats_random", 0, -0.9)]  # b is partial: no raster conditions yet
    summaries = proposal_report.per_set(rows, ["a", "b"])
    assert [(r["set"], r["condition"]) for r in summaries] == [("a", "stats_random"), ("a", "stats_raster"),
                                                               ("a", "proposal_raster"), ("b", "stats_random")]
    assert abs(summaries[0]["matched_judge"] - -0.495) < 1e-12 and summaries[0]["matched_judge_sd"] > 0
    pairs = proposal_report.comparisons(summaries, ["a", "b"])
    assert pairs[0] == {"a": "proposal_raster", "b": "stats_raster", "sets": 1, "a_higher": 1,
                        "mean_difference": pairs[0]["mean_difference"]}
    assert abs(pairs[0]["mean_difference"] - 0.1) < 1e-12
    text = proposal_report.markdown(summaries, pairs, {"a": {"parts": 10, "outside_vocab": 2}})
    assert "Means over the 1 sets with every condition" in text
    assert "| stats_random | 1 | 2 |" in text  # b's lone build is left out of the means


def test_spot_check_rebuilds_logged_builds_exactly() -> None:
    real = model()
    stats = StyleStats().add(real)
    rows = [{**proposal.run_job(proposal.Job("s0", 0, c, 1, tuple(real), stats, str(FIXTURE_WEIGHTS),
                                             proposal_report.HEIGHT, proposal_report.ROOM, 1.0, 1.0)), "set_number": "s0"}
            for c in ("stats_random", "stats_raster")]
    keys = [("s0", "stats_random", 1), ("s0", "stats_raster", 1)]
    assert proposal_report.spot_check(rows, keys, {"s0": real}, stats, FIXTURE_WEIGHTS) == []
    rows[1]["placed"] = rows[1]["placed"][1:]
    assert proposal_report.spot_check(rows, keys, {"s0": real}, stats, FIXTURE_WEIGHTS) == ["s0 stats_raster seed 1"]
