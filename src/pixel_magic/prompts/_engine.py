"""Jinja2 template rendering engine for prompt templates."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES)),
    keep_trailing_newline=True,
    lstrip_blocks=True,
    trim_blocks=True,
)


def render(template_name: str, **kwargs: object) -> str:
    """Render a Jinja2 template with the given variables."""
    return _env.get_template(template_name).render(**kwargs)
