"""M12 step 2: target shapes from silhouettes, height maps and models; preferred colors."""

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from brickwfc.alt.pipeline import cube_grid, main
from brickwfc.alt.target import load_target
from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.parts import PLATES, PlacedPart, extract_parts, part_tileset
from brickwfc.bricks.shapes import (
    bounds,
    column_heights,
    extrude,
    from_heights,
    from_model,
    inside_pixels,
    preferred_colors,
    resample,
)
from conftest import BLUE, RED, WHITE, tiny_model


def silhouette(width: int = 8, height: int = 6) -> Image.Image:
    """A dark plus sign on white: a cross through the middle."""
    image = Image.new("L", (width, height), 255)
    pixels = image.load()
    for x in range(width):
        pixels[x, height // 2] = 0
    for y in range(height):
        pixels[width // 2, y] = 0
    return image


def test_inside_pixels_dark_or_opaque() -> None:
    inside = inside_pixels(silhouette())
    assert inside.shape == (6, 8) and inside.sum() == 8 + 6 - 1
    rgba = Image.new("RGBA", (3, 2), (255, 255, 255, 0))
    rgba.putpixel((1, 1), (255, 255, 255, 255))  # opaque white pixel counts as inside
    assert inside_pixels(rgba).tolist() == [[False, False, False], [False, True, False]]


def test_column_heights_and_extrude() -> None:
    heights_image = Image.new("L", (8, 6), 3)
    heights = column_heights(silhouette(), heights_image)
    assert heights.max() == 3 and (heights[inside_pixels(silhouette())] == 3).all() and heights[0, 0] == 0
    mask = extrude(heights)
    assert mask.shape == (3, 6, 8) and mask.sum() == 3 * 13
    assert column_heights(silhouette(), None, height=5).max() == 5
    with pytest.raises(ValueError):
        column_heights(silhouette(), Image.new("L", (4, 4), 1))


def test_resample_and_bounds() -> None:
    array = np.arange(6).reshape(2, 3)
    assert resample(array, (2, 2)).shape == (4, 6) and resample(array, (2, 2))[3, 5] == 5
    assert resample(array, (0.1, 0.1)).shape == (1, 1)
    mask = np.zeros((4, 5, 5), dtype=bool)
    mask[:2, 1:3, 2] = True
    assert mask[bounds(mask)].shape == (2, 2, 1)


@pytest.mark.parametrize("cells", [300, 1500])
def test_from_heights_hits_the_volume(cells: int) -> None:
    flat = column_heights(silhouette(), None, height=6)
    mask, factor = from_heights(flat, cells, scale_height=False)
    assert abs(mask.sum() - cells) / cells < 0.15 and mask.shape[0] == 6  # height kept, footprint scaled
    tall = column_heights(silhouette(), Image.new("L", (8, 6), 4))
    mask, factor = from_heights(tall, cells, scale_height=True)
    assert abs(mask.sum() - cells) / cells < 0.15 and mask.shape[0] == round(4 * factor)


def test_from_model_scales_uniformly() -> None:
    for solid in (True, False):
        mask = from_model(tiny_model(), 1000, solid_columns=solid)
        assert abs(mask.sum() - 1000) / 1000 < 0.15
        assert mask[0].any() and mask[:, 0].any() and mask[:, :, 0].any()  # cut to its bounding box
    overhang = [tiny_model()[0], *tiny_model()[6:7]]  # a plate on the ground, a brick on layer 1 above part of it
    mask = from_model(overhang + [PlacedPart(overhang[0].shape, RED, 5, 0, 0)], 100, solid_columns=True)
    columns = mask.any(axis=0)
    assert (mask[0][columns]).all()  # every column stands on the ground


def test_preferred_colors_nearest() -> None:
    image = Image.new("RGBA", (2, 1), (250, 10, 10, 255))
    image.putpixel((1, 0), (0, 0, 0, 0))
    assert preferred_colors(image, [BLUE, RED, WHITE]).tolist() == [["red", ""]]


def test_load_target_silhouette_with_colors(tmp_path: Path) -> None:
    silhouette().save(tmp_path / "s.png")
    colors = Image.new("RGB", (8, 6), RED.rgb)
    for y in range(6):
        for x in range(4, 8):
            colors.putpixel((x, y), BLUE.rgb)
    colors.save(tmp_path / "c.png")
    target = load_target(str(tmp_path / "s.png"), 400, [RED, BLUE], color_map=tmp_path / "c.png", height=4)
    assert target.preferred.shape == target.mask.shape[1:]
    columns = target.mask.any(axis=0)
    left, right = target.preferred[:, 0], target.preferred[:, -1]
    assert set(left[columns[:, 0]]) == {"red"} and set(right[columns[:, -1]]) == {"blue"}
    with pytest.raises(ValueError):
        load_target("pyramid", 400, [RED], color_map=tmp_path / "c.png")
    assert load_target("pyramid", 400, [RED]).preferred is None


def test_load_target_from_model_file(tiny_ldr: Path) -> None:
    target = load_target(str(tiny_ldr), 500, [RED])
    assert abs(target.mask.sum() - 500) / 500 < 0.15


def test_builder_prefers_the_column_color() -> None:
    parts = part_tileset(list(PLATES.values()), [RED, BLUE], empty_weight=0.1)
    preferred = np.full((6, 8), "red", dtype=object)
    preferred[:, 4:] = "blue"
    builder = BottomUpBuilder(parts, any_offset=True)
    agree = total = 0
    for seed in range(5):
        grid = builder.build((3, 6, 8), np.random.default_rng(seed), preferred=preferred)
        placed, _ = extract_parts(grid, parts)
        for part in placed:
            for _, z, x in part.bottom_cells():
                agree += preferred[z, x] == part.color.name
                total += 1
    assert agree / total > 0.8


def test_cube_grid_is_a_cube_in_millimetres() -> None:
    y, z, x = cube_grid(1000, 1.5)
    assert z == x and abs(y / x - 2.5) < 0.5 and y * z * x >= 1500


def test_cli_with_silhouette_and_color_map(tiny_ldr: Path, style_dir: tuple[Path, Path], tmp_path: Path) -> None:
    silhouette().save(tmp_path / "s.png")
    Image.new("RGB", (8, 6), BLUE.rgb).save(tmp_path / "c.png")
    out = tmp_path / "out"
    args = [str(tiny_ldr), "--shape", str(tmp_path / "s.png"), "--color-map", str(tmp_path / "c.png"),
            "--shape-height", "3", "--n", "8", "--k", "2", "--workers", "1", "--out", str(out),
            "--style-dir", str(style_dir[0]), "--sets-file", str(style_dir[1])]
    assert main(args) == 0
    stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    assert "silhouette" in stats["shape"] and stats["grid_YZX"][0] == 3
    assert all(0 < row["fill_pct"] <= 100 for row in stats["selected"])


def test_shape_exact_keeps_the_model_cells(tiny_ldr: Path) -> None:
    solid = load_target(str(tiny_ldr), 500, [RED])
    exact = load_target(str(tiny_ldr), 500, [RED], exact=True)
    assert "solid columns" in solid.description and "exact cells" in exact.description
    assert exact.mask.sum() > 0 and not np.array_equal(exact.mask, solid.mask)
    assert not (solid.mask[1:] & ~solid.mask[:-1]).any()  # solid columns: nothing above an empty cell
    with pytest.raises(ValueError):
        load_target("pyramid", 500, [RED], exact=True)


def test_spaceship_target_images(tmp_path: Path) -> None:
    from brickwfc.experiments.demo import labeled_sheet, spaceship_images, write_spaceship

    silhouette_image, heights, colors = spaceship_images()
    inside = inside_pixels(silhouette_image)
    grey = np.asarray(heights)
    assert inside.any() and (grey[inside] > 0).all() and (grey[~inside] == 0).all()
    assert (np.asarray(colors)[..., 3][inside] == 255).all()
    paths = write_spaceship(tmp_path)
    target = load_target(str(paths[0]), 2000, [RED, BLUE, WHITE], paths[1], paths[2])
    assert abs(target.mask.sum() - 2000) / 2000 < 0.15 and set(np.unique(target.preferred)) <= {"", "red", "blue", "white"}
    labeled_sheet([paths[0], paths[2]], ["a", "b"], tmp_path / "sheet.png", columns=2)
    assert (tmp_path / "sheet.png").exists()
