"""README.md and docs/*.md: every relative link points at a file or folder in the repository, and every
results/ file named in docs/reproduce.md headings exists."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_relative_links_exist(doc: Path) -> None:
    missing = []
    for target in LINK.findall(doc.read_text(encoding="utf-8")):
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue  # a URL or an anchor
        if not (doc.parent / target.split("#")[0]).exists():
            missing.append(target)
    assert not missing, f"{doc.name}: broken links {missing}"


def test_reproduce_covers_every_results_write_up() -> None:
    text = (ROOT / "docs" / "reproduce.md").read_text(encoding="utf-8")
    named = set(re.findall(r"^### `(results/[^`]+\.md)`", text, flags=re.MULTILINE))
    present = {f"results/{p.name}" for p in (ROOT / "results").glob("*.md")}
    assert named <= present, f"named but missing: {sorted(named - present)}"
    # A results file must have its own section, or at least appear in the "not on main yet" list.
    unmentioned = {p for p in present - named if p not in text}
    assert not unmentioned, f"results files without a command: {sorted(unmentioned)}"
