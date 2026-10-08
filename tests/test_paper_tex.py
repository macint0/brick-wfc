"""paper/tables.py: markdown tables of results/m13_tables.md -> LaTeX booktabs (standard library only)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "paper"))
import tables  # noqa: E402

MD = """# M13: paper tables

intro text

## Main table (one row per generator)

| generator | valid % | s per accepted design | timeout % |
|---|---|---|---|
| WFC + constraints (B) | 2.5 [m9b] | 1.19e+03 [m9b] | 98 [m9b] |
| D2 + learned proposal | pending [proposal] | — | — |

| a second | table |
|---|---|
| is | ignored |

## Ablation (each constraint or component off)

| component | metric | with | without | note |
|---|---|---|---|---|
| learned style | judge | -0.3281 [m10] | -0.3721 [m10] | off = uniform_weights & 50% |

## Sources

| tag | file |
|---|---|
| m9b | `x.json` |
"""


def test_cells() -> None:
    assert tables.cell(" 2.5 [m9b] ") == r"2.5\textsuperscript{\,m9b}"
    assert tables.cell("pending [proposal]") == r"\textit{pending}\textsuperscript{\,pr}"  # short tag for print
    assert tables.cell("—") == "--" and tables.cell("**100**") == "100"
    assert tables.cell("-0.3281 [m10]") == r"$-$0.3281\textsuperscript{\,m10}"
    assert tables.cell("1.19e+03") == r"1.19$\times 10^{3}$"
    assert tables.cell("a_b & 5% #1") == r"a\_b \& 5\% \#1"


def test_tables_are_found_per_section(tmp_path: Path) -> None:
    found = tables.md_tables(MD)
    assert list(found) == ["Main table (one row per generator)", "Ablation (each constraint or component off)", "Sources"]
    assert len(found["Main table (one row per generator)"]) == 3  # header + 2 rows; the second table is ignored
    source = tmp_path / "m13_tables.md"
    source.write_text(MD, encoding="utf-8")
    written = tables.convert(source, tmp_path / "generated")
    assert [p.name for p in written] == ["main_table.tex", "ablation_table.tex"]  # no table for Sources
    main = written[0].read_text(encoding="utf-8")
    assert r"\begin{tabular}{lrrr}" in main and r"\rotatebox{70}{valid \%}" in main and r"\bottomrule" in main
    ablation = written[1].read_text(encoding="utf-8")
    assert r"\begin{tabular}{llrrl}" in ablation and r"\textbf{metric}" in ablation and "rotatebox" not in ablation
    assert r"uniform\_weights \& 50\%" in ablation


def test_the_real_tables_convert(tmp_path: Path) -> None:
    written = tables.convert(ROOT / "results" / "m13_tables.md", tmp_path)
    assert len(written) == 2 and all(p.read_text(encoding="utf-8").count(r"\\") > 5 for p in written)
