"""Prompt template builder — loads Python-defined prompt templates."""

from __future__ import annotations

import logging
from pathlib import Path
from string import Template

logger = logging.getLogger(__name__)


class PromptTemplate:
    """A single prompt template."""

    def __init__(
        self,
        name: str,
        description: str,
        system_context: str,
        template: str,
        defaults: dict[str, str],
        reference_strategy: str = "",
    ):
        self.name = name
        self.description = description
        self.system_context = system_context
        self.template = template
        self.defaults = defaults
        self.reference_strategy = reference_strategy

    def render(self, **kwargs) -> str:
        """Render the template with given parameters, falling back to defaults."""
        params = {**self.defaults, **kwargs}

        # Build the full prompt: system context + template body
        parts = []
        if self.system_context:
            parts.append(self.system_context.strip())
        parts.append(self.template.strip())
        full = "\n\n".join(parts)

        # Use safe_substitute so missing keys don't raise
        return Template(full).safe_substitute(params)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.defaults,
            "reference_strategy": self.reference_strategy,
        }


class PromptBuilder:
    """Loads and manages prompt templates from the Python prompt library."""

    def __init__(self, prompts_dir: Path | None = None):
        self._templates: dict[str, PromptTemplate] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load templates from the Python prompt_library registry."""
        from pixel_magic.generation.prompt_library import REGISTRY
        self._templates.update(REGISTRY)

    def get(self, name: str) -> PromptTemplate | None:
        """Get a template by name."""
        return self._templates.get(name)

    def render(self, name: str, **kwargs) -> str:
        """Render a template by name with given parameters."""
        tpl = self._templates.get(name)
        if tpl is None:
            raise KeyError(f"Prompt template '{name}' not found")
        return tpl.render(**kwargs)

    def list_templates(self) -> list[dict]:
        """Return a summary of all available templates."""
        return [tpl.to_dict() for tpl in self._templates.values()]

    def list_names(self) -> list[str]:
        """Return sorted template names."""
        return sorted(self._templates.keys())
