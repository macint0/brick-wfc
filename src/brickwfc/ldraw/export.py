"""Write LDraw .ldr files.

Units: 1 stud = 20 LDU, 1 plate = 8 LDU, 1 brick = 24 LDU. LDraw's -Y is up, and a standard
part's origin is the center of its top face (the body extends toward +Y), so a plate whose
bottom sits on layer ``y`` has its origin at LDraw y = -(y + 1) * 8.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

STUD_LDU = 20
PLATE_LDU = 8
BRICK_LDU = 24

IDENTITY = (1, 0, 0, 0, 1, 0, 0, 0, 1)


@dataclass(frozen=True)
class Placement:
    """One LDraw type-1 line: a part at a position with a 3x3 rotation (row-major)."""

    color: int
    position: tuple[float, float, float]  # LDU
    rotation: tuple[float, ...]  # 9 entries
    part: str

    def to_line(self) -> str:
        numbers = " ".join(fmt(v) for v in (*self.position, *self.rotation))
        return f"1 {self.color} {numbers} {self.part}"


def fmt(value: float) -> str:
    """Integers without a decimal point, other values with up to 4 decimals."""
    return str(int(value)) if float(value).is_integer() else f"{value:.4f}".rstrip("0")


def stud_position(x: float, z: float, layer_top: float) -> tuple[float, float, float]:
    """LDU position of a part origin centered on stud cell (x, z) whose top face is at plate height ``layer_top``."""
    return (x * STUD_LDU, -layer_top * PLATE_LDU, z * STUD_LDU)


STEP = "0 STEP"


def _header(path: Path, title: str) -> list[str]:
    return [f"0 {title}", f"0 Name: {path.name}", "0 Author: brickwfc", ""]


def write_ldr(placements: Iterable[Placement], path: str | Path, title: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = _header(path, title) + [p.to_line() for p in placements]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_steps(steps: Iterable[Iterable[Placement]], path: str | Path, title: str) -> None:
    """An .ldr with building instructions: each group of placements is one step, closed by ``0 STEP``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = _header(path, title)
    for step in steps:
        lines += [p.to_line() for p in step] + [STEP]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_ldr(text: str) -> list[Placement]:
    """Read the type-1 (part placement) lines of a single-file .ldr; everything else is ignored."""
    placements = []
    for line in text.splitlines():
        tokens = line.split()
        if len(tokens) < 15 or tokens[0] != "1":
            continue
        numbers = [float(t) for t in tokens[2:14]]
        placements.append(
            Placement(int(tokens[1]), tuple(numbers[:3]), tuple(numbers[3:]), " ".join(tokens[14:]))
        )
    return placements


def parse_steps(text: str) -> list[list[Placement]]:
    """The placements of a single-file .ldr grouped by ``0 STEP`` lines (parts after the last STEP form
    a final step); empty steps are dropped."""
    steps: list[list[Placement]] = [[]]
    for line in text.splitlines():
        if line.split() == STEP.split():
            steps.append([])
        else:
            steps[-1] += parse_ldr(line)
    return [step for step in steps if step]
