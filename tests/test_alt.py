"""M12: the alternate-build pipeline (inputs, candidates, steps, CLI, resume)."""

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from brickwfc.alt.candidates import Candidate, generate
from brickwfc.alt.features import feature_vector, height_map
from brickwfc.alt.inputs import all_from_folds, learned_style, load_source
from brickwfc.alt.output import layer_steps
from brickwfc.alt.pipeline import AltConfig, cache_key, generate_all, main, make_context, resolve
from brickwfc.bricks.inventory import inventory_from_csv
from brickwfc.bricks.parts import BY_FILE
from brickwfc.bricks.style import StyleStats, merged
from brickwfc.experiments.style import folds
from brickwfc.ldraw.export import PLATE_LDU, parse_steps, write_steps

from conftest import BLUE, RED, piece, tiny_model


def bottom_layer(placement) -> int:
    """Bottom layer of an exported part: its origin is the top face, at LDraw y = -top * PLATE_LDU."""
    return round(-placement.position[1] / PLATE_LDU) - BY_FILE[placement.part].height


# Inputs ---------------------------------------------------------------------------------------------


def test_inventory_from_csv() -> None:
    text = "part,color,count\n3001.dat,4,3\n3001,4,2  # same part without .dat\n3020,1,0\n\n9999.dat,4,5\n"
    inventory, ignored, colors = inventory_from_csv(text)
    assert inventory == {("brick2x4", "red"): 5}
    assert ignored == {"9999.dat": 5}
    assert [c.name for c in colors] == ["red"]  # blue only with count 0
    with pytest.raises(ValueError):
        inventory_from_csv("3001.dat,4\n")


def test_load_source_from_model(tiny_ldr: Path) -> None:
    source = load_source(str(tiny_ldr))
    assert source.name == "tiny"
    assert source.recognized_parts == len(tiny_model())
    assert source.ignored == {"3626b.dat": 1}
    assert source.inventory[("plate2x4", "blue")] == 6
    assert source.model is not None


def test_all_from_folds_equals_merged_counts() -> None:
    models = {f"s{i}": [piece("plate2x4", 0, 0, 0, RED)] + [piece("plate1x2", y, 0, 0, BLUE) for y in range(1, i + 2)]
              for i in range(8)}
    per_set = {s: StyleStats().add(m) for s, m in models.items()}
    fold_stats = [merged([per_set[s] for s in per_set if s not in held]) for held in folds(list(models), 4, 0)]
    expected, got = merged(list(per_set.values())), all_from_folds(fold_stats)
    assert np.allclose(got.vertical, expected.vertical) and np.allclose(got.parts, expected.parts)
    assert np.allclose(got.same_color, expected.same_color) and np.allclose(got.supports, expected.supports)
    assert got.colors == pytest.approx(expected.colors) and got.models == expected.models


def test_learned_style_uses_the_held_out_fold(tmp_path: Path) -> None:
    sets = [f"s{i}" for i in range(8)]
    for i in range(4):
        for version, tag in (("", 10), ("_v2", 20), ("_v3", 30)):
            stats = StyleStats().add([piece("plate1x1", 0)])
            stats.models = tag + i  # tag each fold and version
            stats.save(tmp_path / f"style_fold{i}{version}.json")
    sets_file = tmp_path / "sets.json"
    sets_file.write_text(json.dumps({"selected": sets}), encoding="utf-8")
    for i, held in enumerate(folds(sets, 4, 0)):
        stats, label = learned_style(held[0], tmp_path, sets_file, "v1")
        assert stats.models == 10 + i and label == f"M10 fold {i} (learned without {held[0]})"  # as in M12 caches
        stats, label = learned_style(held[0], tmp_path, sets_file, "v2")
        assert stats.models == 20 + i and label.endswith("style v2")
        stats, label = learned_style(held[0], tmp_path, sets_file)  # v3 by default (M12d)
        assert stats.models == 30 + i and label.endswith("style v3")
    stats, label = learned_style("other", tmp_path, sets_file, "v1")
    assert stats.models == round((10 + 11 + 12 + 13) / 3) and label == "all 8 M10 sets"


# Steps and features ---------------------------------------------------------------------------------


def test_layer_steps_put_bricks_in_their_bottom_layer() -> None:
    steps = layer_steps(tiny_model())
    assert [{p.layer for p in step} for step in steps] == [{0}, {1}, {4}, {5}]
    assert any(p.shape.part.kind == "brick" for p in steps[1])


def test_write_and_parse_steps(tmp_path: Path) -> None:
    steps = layer_steps(tiny_model())
    path = tmp_path / "steps.ldr"
    write_steps(([p.placement() for p in step] for step in steps), path, "steps")
    assert path.read_text(encoding="utf-8").count("0 STEP") == len(steps)
    parsed = parse_steps(path.read_text(encoding="utf-8"))
    assert [len(s) for s in parsed] == [len(s) for s in steps]
    assert [{bottom_layer(p) for p in step} for step in parsed] == [{0}, {1}, {4}, {5}]


def test_features_are_bounded() -> None:
    placed = tiny_model()
    shape = (8, 6, 8)
    f = feature_vector(placed, shape, ["blue", "red", "white", "yellow"])
    assert np.all((f >= 0) & (f <= 1))
    filled = np.zeros(shape, dtype=bool)
    filled[:3, 0, 0] = True
    assert height_map(filled)[0, 0] == pytest.approx(3 / 8) and height_map(filled)[1, 1] == 0


# Generation, resume, CLI ----------------------------------------------------------------------------


def tiny_context(tiny_ldr: Path, style_dir: tuple[Path, Path], **config) -> tuple:
    source = load_source(str(tiny_ldr))
    stats, label = learned_style(source.name, *style_dir)
    context = make_context(source, stats, AltConfig(**config))
    return source, label, context


def test_candidates_verify_and_roundtrip(tiny_ldr: Path, style_dir: tuple[Path, Path]) -> None:
    source, _, context = tiny_context(tiny_ldr, style_dir)
    candidates = generate(context, range(6))
    assert [c.seed for c in candidates] == list(range(6))
    for c in candidates:
        assert not set(c.failed) & {"generate", "integrity", "inventory", "support"}  # D2 guarantees these
        assert not Counter((p.shape.part.name, p.color.name) for p in c.placed) - Counter(source.inventory)
        back = Candidate.from_json(json.loads(json.dumps(c.to_json())))
        assert (back.seed, back.placed, back.failed) == (c.seed, c.placed, c.failed)
        assert back.clutch == c.clutch or (np.isnan(back.clutch) and np.isnan(c.clutch))


def test_resume_and_workers_give_the_same_candidates(tiny_ldr: Path, style_dir: tuple[Path, Path], tmp_path: Path) -> None:
    source, label, context = tiny_context(tiny_ldr, style_dir)
    key = cache_key(source, label, context)
    serial = generate_all(context, range(8), tmp_path / "a.jsonl", key, workers=1)
    parallel = generate_all(context, range(8), tmp_path / "b.jsonl", key, workers=2)
    assert [c.placed for c in serial] == [c.placed for c in parallel]

    cache = tmp_path / "a.jsonl"
    lines = cache.read_text(encoding="utf-8").splitlines()
    cache.write_text("\n".join(lines[:4]) + "\n", encoding="utf-8")  # header + 3 candidates: a killed run
    resumed = generate_all(context, range(8), cache, key, workers=1)
    assert [c.placed for c in resumed] == [c.placed for c in serial]
    assert len(cache.read_text(encoding="utf-8").splitlines()) == 9
    with pytest.raises(SystemExit):
        generate_all(context, range(8), cache, {**key, "strength": 2.0}, workers=1)


def test_cli_writes_k_builds_with_steps(tiny_ldr: Path, style_dir: tuple[Path, Path], tmp_path: Path,
                                       capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out"
    args = [str(tiny_ldr), "--n", "12", "--k", "3", "--workers", "1", "--out", str(out),
            "--style-dir", str(style_dir[0]), "--sets-file", str(style_dir[1])]
    assert main(args) == 0
    printed = capsys.readouterr().out
    assert f"{len(tiny_model())} parts recognized, 1 ignored" in printed and "requested:    12" in printed

    stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    assert [s["stage"] for s in stats["stages"]] == ["generate", "verify", "dedupe", "judge", "select"]
    survivors = [stats["requested"]] + [s["survivors"] for s in stats["stages"]]
    assert survivors == sorted(survivors, reverse=True) and survivors[-1] == 3
    assert stats["style"] == "all 8 M10 sets, style v3" and stats["real_model_judge"] is not None

    inventory = load_source(str(tiny_ldr)).inventory
    for row in stats["selected"]:
        assert (out / row["png"]).exists()
        steps = parse_steps((out / row["ldr"]).read_text(encoding="utf-8"))
        assert len(steps) == row["steps"] and sum(len(s) for s in steps) == row["parts"]
        layers = [{bottom_layer(p) for p in step} for step in steps]
        assert all(len(layer) == 1 for layer in layers)
        bottoms = [layer.pop() for layer in layers]
        assert bottoms == sorted(set(bottoms))  # one step per layer, bottom to top
        used = Counter((BY_FILE[p.part].name, p.color) for step in steps for p in step)
        codes = {c.name: c.ldraw for c in load_source(str(tiny_ldr)).colors}
        assert all(used[(name, codes[color])] <= count for (name, color), count in inventory.items())
        assert row["clutch"] < float("inf")
    assert (out / "sheet.png").exists()


def test_cli_with_target_shape(tiny_ldr: Path, style_dir: tuple[Path, Path], tmp_path: Path) -> None:
    out = tmp_path / "shaped"
    args = [str(tiny_ldr), "--shape", "pyramid", "--n", "8", "--k", "2", "--workers", "1", "--out", str(out),
            "--style-dir", str(style_dir[0]), "--sets-file", str(style_dir[1])]
    assert main(args) == 0
    stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    assert stats["shape_cells"] > 0
    assert all(0 < row["fill_pct"] <= 100 for row in stats["selected"])


def test_disconnected_builds_fail_verify(tiny_ldr: Path, style_dir: tuple[Path, Path]) -> None:
    source, _, context = tiny_context(tiny_ldr, style_dir)
    import dataclasses

    loose = generate(dataclasses.replace(context, connect=False, bridge=False), range(20))
    joined = generate(context, range(20))
    assert any("disconnected" in c.failed for c in loose)
    assert all(c.clusters == 1 and "disconnected" not in c.failed for c in joined)


def test_order_and_proposal_reach_the_builder_and_the_cache_key(tiny_ldr: Path, style_dir: tuple[Path, Path],
                                                                tmp_path: Path) -> None:
    weights = Path(__file__).parent / "fixtures" / "proposal" / "proposal.npz"
    source, label, plain = tiny_context(tiny_ldr, style_dir)
    _, _, raster = tiny_context(tiny_ldr, style_dir, order="raster")
    _, _, model = tiny_context(tiny_ldr, style_dir, order="raster", proposal=str(weights))
    keys = [cache_key(source, label, c) for c in (plain, raster, model)]
    assert "order" not in keys[0] and "proposal" not in keys[0]  # caches from before the options stay valid
    assert keys[1]["order"] == "raster" and len(keys[2]["proposal"]) == 16
    assert keys[0] != keys[1] != keys[2]
    generate_all(raster, range(2), tmp_path / "c.jsonl", keys[1], workers=1)
    with pytest.raises(SystemExit):  # a statistics cache is not reused for the model
        generate_all(model, range(2), tmp_path / "c.jsonl", keys[2], workers=1)

    seeds = range(6)
    by_order = generate(raster, seeds)
    with_model = generate(model, seeds)
    assert [c.placed for c in with_model] == [c.placed for c in generate(model, seeds)]  # seeded
    assert [c.placed for c in with_model] != [c.placed for c in by_order]  # the model steers the choices
    assert [c.placed for c in by_order] != [c.placed for c in generate(plain, seeds)]  # so does the order
    for c in with_model:
        assert not set(c.failed) & {"generate", "integrity", "inventory", "support"}  # guarantees hold
    with pytest.raises(SystemExit):
        main([str(tiny_ldr), "--generator", "wfc", "--order", "raster", "--out", str(tmp_path / "w"),
              "--style-dir", str(style_dir[0]), "--sets-file", str(style_dir[1])])


def test_3d_target_defaults() -> None:
    """With a 3D target (a model, BrickGPT structure or mesh), d2 builds with the hole pass, hanging support and usable
    sizing by default (cf, 2026-10-10); with a 2D target or none, without them and with fillable sizing. Settings
    given explicitly stay."""
    for shape in ("brickgpt:a712684f", "chair.stl", "model.ldr"):
        config = resolve(AltConfig(shape=shape))
        assert config.holes and config.hang and config.sizing == "usable", shape
        assert resolve(config) == config
    for shape in (None, "pyramid", "silhouette.png"):
        config = resolve(AltConfig(shape=shape))
        assert not config.holes and not config.hang and config.sizing == "fillable", shape
    wfc = resolve(AltConfig(shape="brickgpt:a712684f", generator="wfc"))
    assert not wfc.holes and not wfc.hang and wfc.sizing == "usable"
    plain = resolve(AltConfig(shape="brickgpt:a712684f", holes=False, sizing="fillable"))
    assert not plain.holes and not plain.hang and plain.sizing == "fillable"
    no_hang = resolve(AltConfig(shape="brickgpt:a712684f", hang=False))
    assert no_hang.holes and not no_hang.hang
    flat = resolve(AltConfig(shape="pyramid", holes=True))
    assert flat.holes and not flat.hang  # the hole pass on a 2D target when asked; hanging stays a 3D default


def test_small_part_options_reach_the_builder_and_the_cache_key(tiny_ldr: Path, style_dir: tuple[Path, Path]) -> None:
    source, label, plain = tiny_context(tiny_ldr, style_dir)
    assert "reserve_small" not in cache_key(source, label, plain) and "small_last" not in cache_key(source, label, plain)
    _, _, reserve = tiny_context(tiny_ldr, style_dir, reserve_small=True)
    _, _, soft = tiny_context(tiny_ldr, style_dir, small_last=1.0)
    assert cache_key(source, label, reserve)["reserve_small"] is True
    assert cache_key(source, label, soft)["small_last"] == 1.0
    for context in (reserve, soft):
        candidates = generate(context, range(2))
        assert all(not set(c.failed) & {"generate", "integrity", "inventory", "support"} for c in candidates)
