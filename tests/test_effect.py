"""Tests for effect command validation and defaults."""

import sys
from pathlib import Path

import pytest
from PIL import Image

from pixel_magic.__main__ import main
from pixel_magic.effect import enforce_loop_closure


def test_effect_requires_name_and_description(monkeypatch: pytest.MonkeyPatch):
    """Effect command must have --name and --animation-description."""
    monkeypatch.setattr(sys, "argv", ["pixel-magic", "effect"])

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 2


def test_effect_frames_must_be_positive(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    """--frames 0 should be rejected by the CLI."""
    monkeypatch.setattr(
        sys, "argv",
        [
            "pixel-magic", "effect",
            "--name", "explosion",
            "--animation-description", "an explosion",
            "--frames", "0",
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 2
    assert "value must be >= 1" in capsys.readouterr().err


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
            "--animation-description",
            "flames dancing and flickering",
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
