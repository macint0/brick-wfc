"""A small subset of the LDraw color table (codes and RGB values from LDConfig.ldr)."""

from __future__ import annotations

from dataclasses import dataclass

from brickwfc.tileset import RGB


@dataclass(frozen=True)
class BrickColor:
    name: str
    ldraw: int  # LDraw color code
    rgb: RGB


PALETTE: dict[str, BrickColor] = {
    c.name: c
    for c in [
        BrickColor("black", 0, (0x1B, 0x2A, 0x34)),
        BrickColor("blue", 1, (0x1E, 0x5A, 0xA8)),
        BrickColor("green", 2, (0x00, 0x85, 0x2B)),
        BrickColor("red", 4, (0xB4, 0x00, 0x00)),
        BrickColor("yellow", 14, (0xFA, 0xC8, 0x0A)),
        BrickColor("white", 15, (0xF4, 0xF4, 0xF4)),
        BrickColor("tan", 19, (0xE4, 0xCD, 0x9E)),
        BrickColor("orange", 25, (0xD6, 0x79, 0x23)),
        BrickColor("light_gray", 71, (0xA0, 0xA5, 0xA9)),
        BrickColor("dark_gray", 72, (0x6C, 0x6E, 0x68)),
    ]
}


def colors_by_name(names: list[str]) -> list[BrickColor]:
    unknown = [n for n in names if n not in PALETTE]
    if unknown:
        raise ValueError(f"unknown colors {unknown}; choose from {sorted(PALETTE)}")
    return [PALETTE[n] for n in names]
