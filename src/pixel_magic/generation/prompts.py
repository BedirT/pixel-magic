"""Prompt template builder — loads YAML templates and fills parameters."""

from __future__ import annotations

import logging
from pathlib import Path
from string import Template

import yaml

logger = logging.getLogger(__name__)


class PromptTemplate:
    """A single prompt template loaded from YAML."""

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
    """Loads and manages prompt templates from YAML files."""

    def __init__(self, prompts_dir: Path):
        self._templates: dict[str, PromptTemplate] = {}
        self._prompts_dir = prompts_dir
        self._load_all()

    def _load_all(self) -> None:
        """Load all YAML template files from the prompts directory."""
        if not self._prompts_dir.exists():
            logger.warning("Prompts directory not found: %s", self._prompts_dir)
            return

        for yaml_file in sorted(self._prompts_dir.glob("*.yaml")):
            self._load_file(yaml_file)

    def _load_file(self, path: Path) -> None:
        """Load templates from a single YAML file.

        Supports two formats:
        - Dict-keyed: top-level keys are template names, values are template fields
        - List format: list of dicts each with a 'name' field
        """
        with open(path) as f:
            data = yaml.safe_load(f)

        if isinstance(data, dict):
            entries = [
                (name, entry) for name, entry in data.items() if isinstance(entry, dict)
            ]
        elif isinstance(data, list):
            entries = [(entry.get("name", ""), entry) for entry in data if isinstance(entry, dict)]
        else:
            logger.warning("Unexpected format in %s: %s", path, type(data).__name__)
            return

        for name, entry in entries:
            if not name:
                continue

            tpl = PromptTemplate(
                name=name,
                description=entry.get("description", ""),
                system_context=entry.get("system_context", ""),
                template=entry.get("template", ""),
                defaults=entry.get("defaults", entry.get("parameters", {})),
                reference_strategy=entry.get("reference_strategy", ""),
            )
            self._templates[name] = tpl

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
        """Return template names grouped by category."""
        return sorted(self._templates.keys())
