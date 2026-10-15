"""The M12d ranking of parts the catalog cannot place: primitives are not parts, counts and names are right."""
from collections import Counter
from pathlib import Path

from brickwfc.experiments.missing_parts import PRIMITIVE, kind_of, main, markdown, model_parts, name_of, rank

MODEL = "\n".join([
    "0 FILE test.mpd",
    "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3024.dat",  # plate 1x1: in the catalog
    "1 4 20 0 0 1 0 0 0 1 0 0 0 1 4599a.dat",  # tap: missing (jumpers are catalog parts since M12d batch 4)
    "1 4 40 0 0 1 0 0 0 1 0 0 0 1 4599a.dat",
    "1 4 60 0 0 1 0 0 0 1 0 0 0 1 3820.dat",  # minifig hand: missing
    "1 4 80 0 0 1 0 0 0 1 0 0 0 1 rect3.dat",  # primitives: not parts
    "1 4 80 0 0 1 0 0 0 1 0 0 0 1 4-4cyli.dat",
    "1 4 80 0 0 1 0 0 0 1 0 0 0 1 stud.dat",
    "1 4 80 0 0 1 0 0 0 1 0 0 0 1 s\\3001s01.dat",
])


def test_primitives_are_not_parts() -> None:
    assert all(PRIMITIVE.search(n) for n in ("rect3.dat", "box2-5.dat", "tri3a1.dat", "t01i3333.dat", "4-4cyli.dat",
                                              "stud.dat", "stud4.dat", "s\\3001s01.dat", "48/4-4cyli.dat"))
    assert not any(PRIMITIVE.search(n) for n in ("3024.dat", "3794a.dat", "60593c01.dat", "3626bp01.dat"))
    assert model_parts(MODEL) == ["3024.dat", "4599a.dat", "4599a.dat", "3820.dat"]


def test_rank_counts_missing_instances_and_models() -> None:
    ranking = rank([MODEL, MODEL.replace("3820", "3024")])
    assert (ranking.total, ranking.recognized) == (8, 3)
    assert ranking.missing == Counter({"4599a.dat": 4, "3820.dat": 1})
    assert ranking.sets_with == Counter({"4599a.dat": 2, "3820.dat": 1})
    assert ranking.recognized_pct == 37.5


def test_names_and_kinds() -> None:
    names = {"3794": "Plate Special 1 x 2 with 1 Stud (Jumper)", "3820": "Minifig Hand"}
    assert name_of("3794a.dat", names).startswith("Plate Special")
    assert name_of("3820.dat", names) == "Minifig Hand"
    assert name_of("99999.dat", names) == "?"
    assert kind_of("Plate Special 1 x 2 with 1 Stud (Jumper)") == "jumper"
    assert kind_of("Minifig Hand") == "minifig"
    assert kind_of("Something else") == "other"


def test_markdown_table_cumulates_to_all_parts() -> None:
    text = markdown("one model", rank([MODEL]), {}, top=10)
    assert "4 parts, recognized 1 (25.0%), missing 3 in 2 distinct files" in text
    assert "| 2 | 3820 | 1 | 1 | 100.0 | other | ? |" in text


def test_driver_writes_the_table(tmp_path: Path) -> None:
    data = tmp_path / "omr"
    data.mkdir()
    (data / "1-1.mpd").write_text(MODEL, encoding="utf-8")
    out = tmp_path / "ranking.md"
    assert main(["--all", "--data", str(data), "--rebrickable", str(tmp_path / "none.csv.gz"), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Parts the catalog cannot place")
    assert "## all 1 local OMR models: 4 parts" in text
