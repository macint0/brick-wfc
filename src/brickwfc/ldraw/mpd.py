"""Parse LDraw .ldr / .mpd models into a flat list of library parts in world coordinates.

An .mpd bundles several files ("0 FILE name" ... "0 NOFILE"); the first is the main model and
type-1 lines that reference another file of the bundle are submodels. Submodels are expanded
recursively, composing transforms; anything not in the bundle is a library part.
Color 16 means "inherit the color of the referencing line".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

INHERIT_COLOR = 16
MAX_DEPTH = 32


@dataclass(frozen=True, eq=False)
class PartInstance:
    part: str  # normalized library file name, e.g. "3020.dat"
    color: int
    position: np.ndarray  # (3,) LDU, LDraw axes (-Y up)
    rotation: np.ndarray  # (3, 3)


def normalize_name(name: str) -> str:
    return name.strip().replace("\\", "/").lower()


def parse_color(token: str) -> int:
    """LDraw color code; direct colors ("0x2RRGGBB") are kept as their integer value."""
    return int(token, 16) if token.lower().startswith("0x") else int(token)


def split_files(text: str) -> tuple[str, dict[str, list[str]]]:
    """Split an .mpd into ``(main file name, {name: lines})``. A plain .ldr is one file named "main"."""
    files: dict[str, list[str]] = {}
    current: list[str] | None = None
    main = ""
    for line in text.splitlines():
        tokens = line.split(maxsplit=2)
        if len(tokens) >= 3 and tokens[0] == "0" and tokens[1] == "FILE":
            name = normalize_name(tokens[2])
            current = files.setdefault(name, [])
            main = main or name
        elif len(tokens) >= 2 and tokens[0] == "0" and tokens[1] == "NOFILE":
            current = None
        elif current is not None:
            current.append(line)
    if not files:
        return "main", {"main": text.splitlines()}
    return main, files


def flatten(text: str) -> list[PartInstance]:
    """All library parts of the main model, in world coordinates."""
    main, files = split_files(text)
    parts: list[PartInstance] = []

    def expand(name: str, color: int, position: np.ndarray, rotation: np.ndarray, depth: int) -> None:
        if depth > MAX_DEPTH:
            raise ValueError(f"submodel nesting deeper than {MAX_DEPTH} at {name!r} (cycle?)")
        for line in files[name]:
            tokens = line.split()
            if len(tokens) < 15 or tokens[0] != "1":
                continue
            line_color = parse_color(tokens[1])
            line_color = color if line_color == INHERIT_COLOR else line_color
            numbers = np.array([float(t) for t in tokens[2:14]])
            world_position = position + rotation @ numbers[:3]
            world_rotation = rotation @ numbers[3:].reshape(3, 3)
            reference = normalize_name(" ".join(tokens[14:]))
            if reference in files:
                expand(reference, line_color, world_position, world_rotation, depth + 1)
            else:
                parts.append(PartInstance(reference, line_color, world_position, world_rotation))

    expand(main, INHERIT_COLOR, np.zeros(3), np.eye(3), 0)
    return parts
