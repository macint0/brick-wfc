"""M13 user study: blinded pair images with a hidden key, and Bradley-Terry fits on synthetic votes."""

import csv
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from brickwfc.experiments import user_study
from brickwfc.experiments.user_study import Comparison, fit, fit_bradley_terry, read_key, read_votes


def run_folder(root: Path, name: str, count: int, color: tuple[int, int, int]) -> Path:
    folder = root / name
    folder.mkdir()
    for k in range(count):
        Image.new("RGB", (40 + k, 30), color).save(folder / f"build_{k + 1:02d}.png")
    Image.new("RGB", (10, 10)).save(folder / "sheet.png")  # not a build
    return folder


def synthetic_comparisons(strengths: np.ndarray, per_pair: int, rng: np.random.Generator, ties: float = 0.0) -> list[Comparison]:
    found = []
    for i in range(len(strengths)):
        for j in range(i + 1, len(strengths)):
            p = 1 / (1 + np.exp(strengths[j] - strengths[i]))
            for _ in range(per_pair):
                if rng.random() < ties:
                    found.append(Comparison(i, j, 0.5))
                else:
                    found.append(Comparison(i, j, float(rng.random() < p)) if rng.random() < 0.5
                                 else Comparison(j, i, float(rng.random() >= p)))
    return found


def test_bradley_terry_recovers_known_strengths() -> None:
    truth = np.array([0.0, 0.5, 1.0, -1.0])
    truth = truth - truth.mean()
    s, se = fit_bradley_terry(synthetic_comparisons(truth, 400, np.random.default_rng(0)), 4)
    assert np.abs(s - truth).max() < 0.15 and list(np.argsort(s)) == list(np.argsort(truth))
    assert (np.abs(s - truth) < 3 * se).all() and abs(s.mean()) < 1e-9


def test_bradley_terry_stays_finite_when_one_side_always_wins() -> None:
    s, se = fit_bradley_terry([Comparison(0, 1, 1.0)] * 20, 2)
    assert np.isfinite(s).all() and s[0] > s[1] + 2 and np.isfinite(se).all()


def test_ties_pull_strengths_together() -> None:
    s, _ = fit_bradley_terry([Comparison(0, 1, 0.5)] * 50, 2)
    assert abs(s[0] - s[1]) < 1e-6


def test_pairs_are_blinded_and_keyed(tmp_path: Path) -> None:
    a = run_folder(tmp_path, "d2", 4, (200, 0, 0))
    b = run_folder(tmp_path, "wfc", 3, (0, 0, 200))
    out = tmp_path / "study"
    assert user_study.main(["pairs", str(a), str(b), "--n", "10", "--seed", "1", "--out", str(out)]) == 0
    key = read_key(out / "key.csv")
    assert len(key) == 10 and sorted(key) == [f"pair_{k:03d}" for k in range(1, 11)]
    assert all({row["left_generator"], row["right_generator"]} == {"d2", "wfc"} for row in key.values())
    lefts = [row["left_generator"] for row in key.values()]
    assert 0 < lefts.count("d2") < 10  # sides are randomized
    assert len({(row["left_file"], row["right_file"]) for row in key.values()}) == 10  # no repeats
    assert not any("sheet" in row["left_file"] + row["right_file"] for row in key.values())
    image = Image.open(out / "pair_001.png")
    width = max(Image.open(key["pair_001"][f"{side}_file"]).width for side in ("left", "right"))
    assert image.size == (2 * width + user_study.GAP, 30 + user_study.LABEL_H)
    with (out / "votes_template.csv").open(newline="", encoding="utf-8") as f:
        assert [r["pair"] for r in csv.DictReader(f)] == list(key)
    # Same seed, same study; the pool is exhausted at 12 pairs.
    again = user_study.plan_pairs([a, b], ["d2", "wfc"], 10, np.random.default_rng(1))
    assert [(p["pair"], str(p["left_file"])) for p in again] == [(k, row["left_file"]) for k, row in key.items()]
    assert len(user_study.plan_pairs([a, b], ["d2", "wfc"], 50, np.random.default_rng(1))) == 12


def test_fit_from_votes_through_the_key(tmp_path: Path) -> None:
    a = run_folder(tmp_path, "good", 5, (200, 0, 0))
    b = run_folder(tmp_path, "bad", 5, (0, 0, 200))
    out = tmp_path / "study"
    user_study.main(["pairs", str(a), str(b), "--n", "25", "--seed", "0", "--out", str(out)])
    key = read_key(out / "key.csv")
    rng = np.random.default_rng(2)
    rows = []
    for rater in ("r1", "r2", "r3"):
        for pair, row in key.items():
            good_left = row["left_generator"] == "good"
            good_wins = rng.random() < 0.8
            rows.append([pair, "1" if good_wins == good_left else "2", rater])
    rows.append([next(iter(key)), "tie", "r4"])
    votes = tmp_path / "votes.csv"
    with votes.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([["pair", "winner", "rater"], *rows, ["pair_002", "", "r5"]])  # blank: skipped
    result = fit(read_votes([votes]), key)
    assert result.items == ["bad", "good"] and result.comparisons == 76
    assert 0.7 < result.p_beats(1, 0) < 0.9
    assert user_study.main(["fit", "--key", str(out / "key.csv"), "--votes", str(votes), "--out", str(out)]) == 0
    assert "| good |" in (out / "bt_generator.md").read_text(encoding="utf-8")
    build_level = fit(read_votes([votes]), key, level="build")
    assert len(build_level.items) == 10
    with pytest.raises(ValueError):
        fit([{"pair": next(iter(key)), "winner": "left-ish"}], key)
