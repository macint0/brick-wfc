"""Two driver details found by the overnight queue: the select driver's output name keeps a dot inside it, and the
colour driver skips a finished run that selected nothing (every candidate under the fill floor)."""
import json
from pathlib import Path

from brickwfc.experiments.coherence import has_selection, results_path
from brickwfc.experiments.select import output_path


def test_select_output_keeps_a_dot_inside_the_name() -> None:
    assert output_path(Path("out/x/select_0.6")) == Path("out/x/select_0.6.json")
    assert output_path(Path("out/x/select")) == Path("out/x/select.json")
    assert output_path(Path("out/x/select.json")) == Path("out/x/select.json")


def test_coherence_skips_a_run_without_a_selection(tmp_path: Path) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"selected": []}), encoding="utf-8")
    some = tmp_path / "some.json"
    some.write_text(json.dumps({"selected": [{"seed": 3}]}), encoding="utf-8")
    assert not has_selection(empty)
    assert has_selection(some)


def test_coherence_results_keep_a_dot_inside_the_name() -> None:
    assert results_path(Path("out/x/coherence_0.6"), ".json") == Path("out/x/coherence_0.6.json")
    assert results_path(Path("out/x/coherence_0.6"), ".png") == Path("out/x/coherence_0.6.png")
