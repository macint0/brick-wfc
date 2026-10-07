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
        BrickColor("brown", 6, (0x58, 0x39, 0x27)),
        BrickColor("old_light_gray", 7, (0x9B, 0xA1, 0x9D)),
        BrickColor("old_dark_gray", 8, (0x6D, 0x6E, 0x5C)),
        BrickColor("bright_green", 10, (0x4B, 0x9F, 0x4A)),
        BrickColor("lime", 27, (0xBB, 0xE9, 0x0B)),
        BrickColor("dark_tan", 28, (0x95, 0x8A, 0x73)),
        BrickColor("reddish_brown", 70, (0x58, 0x2A, 0x12)),
        BrickColor("dark_blue", 272, (0x0A, 0x34, 0x63)),
        BrickColor("dark_green", 288, (0x18, 0x46, 0x32)),
        BrickColor("dark_red", 320, (0x72, 0x0E, 0x0F)),
    ]
}
BY_CODE: dict[int, BrickColor] = {c.ldraw: c for c in PALETTE.values()}
UNKNOWN_RGB = (0x80, 0x80, 0x80)


def color_for_code(code: int) -> BrickColor:
    """The palette color for an LDraw code, or a gray stand-in named after the code."""
    return BY_CODE.get(code) or BrickColor(f"ldraw{code}", code, UNKNOWN_RGB)


def colors_by_name(names: list[str]) -> list[BrickColor]:
    unknown = [n for n in names if n not in PALETTE]
    if unknown:
        raise ValueError(f"unknown colors {unknown}; choose from {sorted(PALETTE)}")
    return [PALETTE[n] for n in names]
