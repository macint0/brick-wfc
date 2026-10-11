"""M12c overnight queue (experiments/overnight.py, scripts/overnight_m12c.sh): every scripted command line parses with
its driver's own parser, the pair files are the bench's, and the order puts the 9 sweep pairs last."""

import shlex
from pathlib import Path

import pytest

from brickwfc.experiments import coherence, complete, select
from brickwfc.experiments.complete import ARMS, PAIRS, load_pairs
from brickwfc.experiments.overnight import BENCH_ALL, BENCH_NEW, CHAIR_PAIRS, estimates, steps

ROOT = Path(__file__).resolve().parents[1]
PARSERS = {"brickwfc.experiments.complete": complete.parser, "brickwfc.experiments.select": select.parser,
           "brickwfc.experiments.coherence": coherence.parser}


@pytest.mark.parametrize("slacks", [[0.8, 1.0], [0.7], [0.9, 0.6]])
def test_every_command_parses_with_its_driver(slacks) -> None:
    names = []
    for name, argv in steps(slacks):
        names.append(name)
        assert argv[:2] == ["python", "-m"] and shlex.split(shlex.join(argv)) == argv  # what the script evals
        args = PARSERS[argv[2]]().parse_args(argv[3:])  # argparse exits on an unknown option or choice
        assert all(arm in ARMS for arm in getattr(args, "arms", None) or [])
        if getattr(args, "pairs", None) is not None:
            load_pairs(ROOT / args.pairs)
    assert len(set(names)) == len(names)


def test_the_order_runs_new_pairs_first_and_the_sweep_pairs_last() -> None:
    names = [name for name, _ in steps([0.8, 1.0])]
    assert names[:4] == ["hollow-sweep", "hollow-report", "chair-sweep", "chair-size-report"]
    assert names.index("bench-sweep-0.8") < names.index("bench-sweep-1.0") < names.index("bench-sweep9-0.8")
    assert names[-1] == "bench-coherence-1.0-final"
    sweep9 = dict(steps([0.8]))["bench-sweep9-0.8"]
    assert "--pairs" not in sweep9 and "bench80" in sweep9  # the driver's default: the 9 sweep pairs
    with pytest.raises(ValueError):
        steps([0.85])


def test_pair_files() -> None:
    new, everything = load_pairs(ROOT / BENCH_NEW), load_pairs(ROOT / BENCH_ALL)
    assert len(new) == 45 and not set(new) & set(PAIRS) and set(new) | set(PAIRS) == set(everything)
    sets = [s for s, _ in new]
    order = [s for s in dict.fromkeys(s for s, _ in everything)]  # the bench file lists sets smallest first
    assert sorted(sets, key=order.index) == sets  # small sets first
    assert load_pairs(ROOT / CHAIR_PAIRS) == (("6378-1", "chair"),)


def test_estimates_cover_the_heavy_steps(monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    rows = dict(estimates([0.8, 1.0]))
    assert rows["bench-sweep-1.0"] > rows["bench-sweep-0.8"] > rows["bench-sweep9-0.8"] > 0
    assert rows["hollow-sweep"] > 0 and rows["chair-sweep"] > 0 and rows["hollow-report"] is None


def test_the_script_runs_the_steps_with_markers() -> None:
    text = (ROOT / "scripts" / "overnight_m12c.sh").read_text(encoding="utf-8")
    for needle in ("python -m brickwfc.experiments.overnight steps", "--dry-run", "STEP_DONE $name",
                   "STEP_FAILED $name", 'echo "ALL_DONE"', "out/m12b_complete/overnight.log"):
        assert needle in text
