"""Tests for models — Direction, AnimationDef, Palette."""

from pixel_magic.models.asset import (
    DEFAULT_ANIMATIONS,
    AnimationDef,
    Direction,
    DirectionMode,
)
from pixel_magic.models.palette import DitherConfig, DitherType, Palette


class TestDirection:
    def test_unique_4dir(self):
        dirs = Direction.unique_for_mode(DirectionMode.FOUR)
        assert len(dirs) == 2
        assert Direction.SE in dirs
        assert Direction.NE in dirs

    def test_unique_8dir(self):
        dirs = Direction.unique_for_mode(DirectionMode.EIGHT)
        assert len(dirs) == 5
        assert Direction.S in dirs
        assert Direction.N in dirs

    def test_all_4dir(self):
        dirs = Direction.all_for_mode(DirectionMode.FOUR)
        assert len(dirs) == 4
        assert set(dirs) == {Direction.SE, Direction.NE, Direction.SW, Direction.NW}

    def test_all_8dir(self):
        dirs = Direction.all_for_mode(DirectionMode.EIGHT)
        assert len(dirs) == 8

    def test_flip_pairs(self):
        pairs = Direction.flip_pairs()
        assert Direction.W in pairs
        assert pairs[Direction.W] == Direction.E
        assert Direction.SW in pairs
        assert pairs[Direction.SW] == Direction.SE
        assert Direction.NW in pairs
        assert pairs[Direction.NW] == Direction.NE


class TestDefaultAnimations:
    def test_has_required_anims(self):
        for name in ("idle", "walk", "run", "attack", "hurt", "death", "cast"):
            assert name in DEFAULT_ANIMATIONS

    def test_animation_def_fields(self):
        idle = DEFAULT_ANIMATIONS["idle"]
        assert isinstance(idle, AnimationDef)
        assert idle.frame_count > 0
        assert idle.is_looping is True


class TestPalette:
    def test_from_hex_list(self):
        p = Palette(name="test", colors=[(255, 0, 0, 255), (0, 255, 0, 255)])
        assert len(p.colors) == 2

    def test_to_hex_list(self):
        p = Palette(name="test", colors=[(255, 0, 0, 255), (0, 128, 0, 255)])
        hex_list = p.to_hex_list()
        assert "#ff0000" in hex_list
        assert "#008000" in hex_list

    def test_from_hex_file(self, tmp_path):
        hex_file = tmp_path / "test.hex"
        hex_file.write_text("ff0000\n00ff00\n0000ff\n")
        p = Palette.from_hex_file(hex_file)
        assert len(p.colors) == 3
        assert p.colors[0][:3] == (255, 0, 0)


class TestDitherConfig:
    def test_defaults(self):
        d = DitherConfig()
        assert d.type == DitherType.NONE
        assert d.strength == 0.3
