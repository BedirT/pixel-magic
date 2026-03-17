"""Prompt library — Python-defined prompt templates.

Each sub-module defines PromptTemplate instances and registers them
in the REGISTRY dict.  PromptBuilder loads from here instead of YAML.
"""

from __future__ import annotations

from pixel_magic.generation.prompts import PromptTemplate

# Global registry: template_name → PromptTemplate
REGISTRY: dict[str, PromptTemplate] = {}


def register(tpl: PromptTemplate) -> PromptTemplate:
    """Register a template in the global registry. Returns it for convenience."""
    REGISTRY[tpl.name] = tpl
    return tpl


def _load_all() -> None:
    """Import all sub-modules so their register() calls execute."""
    from pixel_magic.generation.prompt_library import (  # noqa: F401
        characters,
        custom,
        effects,
        items,
        tilesets,
        ui,
    )


_load_all()
