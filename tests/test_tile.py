"""Tests for tile command validation and defaults."""

import sys

import pytest

from pixel_magic.__main__ import main
from pixel_magic.prompts import build_tile_canvas_prompt
from pixel_magic.tile import build_tile_canvas


def test_tile_defaults_to_pink_chromakey():
    """Tile generation should default to pink to preserve green and blue terrain."""
    from pixel_magic.__main__ import _resolve_tile_chromakey

    assert _resolve_tile_chromakey(args_chromakey=None, settings_chromakey="green") == "pink"
    assert _resolve_tile_chromakey(args_chromakey=None, settings_chromakey="blue") == "pink"
    assert _resolve_tile_chromakey(args_chromakey="green", settings_chromakey="blue") == "green"


def test_tile_custom_theme_requires_types(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    """Missing custom types should surface as a normal CLI error."""
    monkeypatch.setattr(sys, "argv", ["pixel-magic", "tile", "--theme", "custom"])

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 2
    assert "--types is required when using --theme custom" in capsys.readouterr().err


def test_tile_variants_must_be_positive(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    """Non-positive variant counts should be rejected by the CLI."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["pixel-magic", "tile", "--type", "grass", "--variants", "0"],
    )

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 2
    assert "--variants must be >= 1" in capsys.readouterr().err


def test_three_tile_canvas_avoids_empty_grid_cells():
    """Three custom tiles should use a single-row layout with no unused cell."""
    canvas, cols, slot_size, aspect_ratio, image_size = build_tile_canvas(
        ["mud", "brick", "poison swamp"],
        chromakey_color="pink",
    )

    assert cols == 3
    assert slot_size[0] > 0
    assert canvas.width > canvas.height
    assert aspect_ratio in {"3:2", "16:9", "4:3"}
    assert image_size in {"512", "1K", "2K", "4K"}


def test_tile_prompt_forbids_extra_unlabeled_tiles():
    """Prompt should explicitly forbid generating tiles outside labeled slots."""
    prompt = build_tile_canvas_prompt(
        ["mud", "brick", "poison swamp"],
        chromakey_color="pink",
        grid_cols=3,
        grid_rows=1,
    )

    assert "exactly 3 labeled isometric diamond outlines" in prompt
    assert "Do not invent extra tiles" in prompt
    assert "Any unlabeled or outline-free area must remain solid pink" in prompt
