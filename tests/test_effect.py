"""Tests for effect command validation and defaults."""

import sys
from pathlib import Path

import pytest
from PIL import Image

from pixel_magic.__main__ import main
from pixel_magic.effect import (
    EFFECT_PRESETS,
    enforce_loop_closure,
    infer_loop_default,
    resolve_effect_labels,
)


def test_effect_requires_name_or_preset(monkeypatch: pytest.MonkeyPatch):
    """Effect command must have --name or --preset."""
    monkeypatch.setattr(sys, "argv", ["pixel-magic", "effect"])

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 2


def test_effect_frames_must_be_positive(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    """--frames 0 should be rejected by the CLI."""
    monkeypatch.setattr(
        sys, "argv",
        ["pixel-magic", "effect", "--name", "explosion", "--frames", "0"],
    )

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 2
    assert "value must be >= 1" in capsys.readouterr().err


def test_effect_custom_preset_requires_names(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    """--preset custom without --names should surface as a CLI error."""
    monkeypatch.setattr(
        sys, "argv",
        ["pixel-magic", "effect", "--preset", "custom"],
    )

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 2
    assert "--names is required" in capsys.readouterr().err


def test_effect_unknown_preset():
    """Unknown preset should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown preset"):
        resolve_effect_labels(name=None, preset="nonexistent", custom_names="")


def test_resolve_effect_labels_name():
    """--name should return a single-item list."""
    set_name, labels = resolve_effect_labels(name="explosion", preset=None, custom_names="")
    assert set_name == "explosion"
    assert labels == ["explosion"]


def test_resolve_effect_labels_preset():
    """--preset should return all effects from that preset."""
    set_name, labels = resolve_effect_labels(name=None, preset="combat", custom_names="")
    assert set_name == "combat"
    assert labels == EFFECT_PRESETS["combat"]


def test_resolve_effect_labels_custom():
    """--preset custom with --names should parse comma-separated list."""
    set_name, labels = resolve_effect_labels(
        name=None, preset="custom", custom_names="fireball, ice_shard, lightning",
    )
    assert set_name == "custom"
    assert labels == ["fireball", "ice_shard", "lightning"]


def test_infer_loop_default():
    """One-shot effects should not loop, sustained effects should."""
    assert infer_loop_default("explosion") is False
    assert infer_loop_default("slash") is False
    assert infer_loop_default("fire") is True
    assert infer_loop_default("magic_circle") is True
    assert infer_loop_default("healing_aura") is True
    # Unknown effects default to non-looping
    assert infer_loop_default("custom_unknown") is False


def test_enforce_loop_closure_copies_first_frame_to_last():
    """Looped animations should end on an exact copy of the first frame."""
    first = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
    middle = Image.new("RGBA", (2, 2), (0, 255, 0, 255))
    last = Image.new("RGBA", (2, 2), (0, 0, 255, 255))

    closed = enforce_loop_closure([first, middle, last], loop=True)

    assert closed[0].tobytes() == closed[-1].tobytes()
    assert closed[-1] is not closed[0]
    assert closed[1].tobytes() == middle.tobytes()


def test_effect_uses_cleanup_pass_before_extracting_frames(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Effect generation should run a second Gemini pass to remove guide numbers."""
    from pixel_magic.providers.base import GenerationResult
    import pixel_magic.__main__ as cli
    import pixel_magic.providers.gemini as gemini_module

    class FakeProvider:
        instance = None

        def __init__(self, api_key: str, model: str):
            self.calls = 0
            FakeProvider.instance = self

        async def generate_with_images(self, prompt, images, **kwargs):
            self.calls += 1
            return GenerationResult(image=images[0].copy())

    monkeypatch.setattr(gemini_module, "GeminiProvider", FakeProvider)
    monkeypatch.setattr(cli, "_clean_sprite", lambda image, chromakey_color: image)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pixel-magic",
            "effect",
            "--name",
            "fire",
            "--frames",
            "4",
            "--output-dir",
            str(tmp_path),
        ],
    )

    main()

    effect_dir = tmp_path / "effects" / "fire"
    assert FakeProvider.instance is not None
    assert FakeProvider.instance.calls == 2
    assert (effect_dir / "sheet_cleaned.png").exists()
