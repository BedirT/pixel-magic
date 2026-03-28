"""Tests for tile command validation and defaults."""

import sys

import pytest

from pixel_magic.__main__ import main


def test_tile_defaults_to_blue_chromakey():
    """Tile generation should default to blue to preserve green terrain."""
    from pixel_magic.__main__ import _resolve_tile_chromakey

    assert _resolve_tile_chromakey(args_chromakey=None, settings_chromakey="green") == "blue"
    assert _resolve_tile_chromakey(args_chromakey=None, settings_chromakey="blue") == "blue"
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
