"""Tests for generation.prompts — Python-based template loading and rendering."""

import pytest

from pixel_magic.generation.prompts import PromptBuilder, PromptTemplate


class TestPromptBuilder:
    def test_loads_all_templates(self):
        builder = PromptBuilder()
        names = builder.list_names()
        assert "character_directions_4dir" in names
        assert "character_animation" in names
        assert "tileset_ground" in names
        assert "item_icons_batch" in names
        assert "effect_animation" in names
        assert "ui_elements_batch" in names

    def test_get_template(self):
        builder = PromptBuilder()
        tpl = builder.get("character_directions_4dir")
        assert tpl is not None
        assert isinstance(tpl, PromptTemplate)
        assert tpl.name == "character_directions_4dir"
        assert tpl.system_context != ""

    def test_render_with_defaults(self):
        builder = PromptBuilder()
        rendered = builder.render(
            "character_directions_4dir",
            character_description="a warrior with sword and shield",
        )
        assert "warrior" in rendered
        assert "south_east" in rendered.lower()

    def test_render_with_overrides(self):
        builder = PromptBuilder()
        rendered = builder.render(
            "character_directions_4dir",
            character_description="an elf mage",
            resolution="32x32",
            max_colors="8",
        )
        assert "elf mage" in rendered
        assert "32x32" in rendered

    def test_list_templates_has_descriptions(self):
        builder = PromptBuilder()
        templates = builder.list_templates()
        assert len(templates) > 0
        for tpl in templates:
            assert tpl["description"] != ""

    def test_unknown_template_returns_none(self):
        builder = PromptBuilder()
        assert builder.get("nonexistent_template") is None

    def test_unknown_template_render_raises(self):
        builder = PromptBuilder()
        with pytest.raises(KeyError):
            builder.render("nonexistent_template")

    def test_all_templates_renderable(self):
        """Every registered template should render without error using defaults."""
        builder = PromptBuilder()
        for name in builder.list_names():
            rendered = builder.render(name)
            assert len(rendered) > 50  # non-trivial output
