from pathlib import Path
import sys

import pytest

from pixel_magic.__main__ import (
    _build_parser,
    _canonical_direction,
    main,
    _resolve_view_path,
    _view_labels,
)


def test_view_labels_use_compass_names() -> None:
    assert _view_labels(4) == ["south_west", "north_east"]
    assert _view_labels(8) == ["north", "north_east", "east", "south_east", "south"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("north", "north"),
        ("north-east", "north_east"),
        ("south_east", "south_east"),
        ("front", "south"),
        ("back", "north"),
        ("right", "east"),
        ("left", "west"),
        ("front_right", "south_east"),
        ("front_left", "south_west"),
        ("back_right", "north_east"),
        ("back_left", "north_west"),
    ],
)
def test_canonical_direction_supports_compass_and_legacy_aliases(raw: str, expected: str) -> None:
    assert _canonical_direction(raw) == expected


def test_animate_parser_defaults_to_south_east() -> None:
    parser = _build_parser()
    args = parser.parse_args(["animate", "--name", "hero"])
    assert args.direction == "south_east"


def test_animate_rejects_unknown_direction(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["pixel-magic", "animate", "--name", "hero", "--direction", "upsideways"],
    )

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 2
    assert "Unknown direction" in capsys.readouterr().out


def test_resolve_view_path_falls_back_to_legacy_filename(tmp_path: Path) -> None:
    legacy = tmp_path / "front_right.png"
    legacy.write_bytes(b"legacy")

    resolved = _resolve_view_path(tmp_path, "south_east")

    assert resolved == legacy


def test_resolve_view_path_prefers_canonical_filename(tmp_path: Path) -> None:
    canonical = tmp_path / "south_east.png"
    legacy = tmp_path / "front_right.png"
    canonical.write_bytes(b"canonical")
    legacy.write_bytes(b"legacy")

    resolved = _resolve_view_path(tmp_path, "front_right")

    assert resolved == canonical
