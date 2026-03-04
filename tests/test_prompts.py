"""Tests for generation.prompts — YAML template loading and rendering."""

from pathlib import Path

from pixel_magic.generation.prompts import PromptBuilder


class TestPromptBuilder:
    def test_loads_yaml_templates(self):
        builder = PromptBuilder(Path("prompts"))
        names = builder.list_names()
        assert "character_directions_4dir" in names
        assert "character_animation" in names
        assert "tileset_ground" in names
        assert "item_icons_batch" in names
        assert "effect_animation" in names
        assert "ui_elements_batch" in names

    def test_get_template(self):
        builder = PromptBuilder(Path("prompts"))
        tpl = builder.get("character_directions_4dir")
        assert tpl is not None
        assert tpl.name == "character_directions_4dir"
        assert tpl.system_context != ""

    def test_render_with_defaults(self):
        builder = PromptBuilder(Path("prompts"))
        rendered = builder.render(
            "character_directions_4dir",
            character_description="a warrior with sword and shield",
        )
        assert "warrior" in rendered
        assert "south" in rendered.lower()

    def test_render_with_overrides(self):
        builder = PromptBuilder(Path("prompts"))
        rendered = builder.render(
            "character_directions_4dir",
            character_description="an elf mage",
            resolution="32x32",
            max_colors="8",
        )
        assert "elf mage" in rendered
        assert "32x32" in rendered

    def test_list_templates_has_descriptions(self):
        builder = PromptBuilder(Path("prompts"))
        templates = builder.list_templates()
        for tpl in templates:
            assert tpl["description"] != ""

    def test_unknown_template_returns_none(self):
        builder = PromptBuilder(Path("prompts"))
        assert builder.get("nonexistent_template") is None
