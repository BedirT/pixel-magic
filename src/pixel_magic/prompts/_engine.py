"""Jinja2 template rendering engine for prompt templates."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_TEMPLATES = Path(__file__).parent / "templates"


def _json_escape(value: object) -> str:
    """Escape a value for safe embedding inside a JSON double-quoted string.

    Handles double quotes, backslashes, newlines, tabs, and other JSON
    special characters. Use as ``{{ description | je }}`` in templates
    where the surrounding quotes are already in the template text.
    """
    serialized = json.dumps(str(value))
    # json.dumps wraps in quotes — strip them since the template provides its own
    return serialized[1:-1]


_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES)),
    keep_trailing_newline=True,
    lstrip_blocks=True,
    trim_blocks=True,
)
_env.filters["je"] = _json_escape


def render(template_name: str, **kwargs: object) -> str:
    """Render a Jinja2 template with the given variables."""
    return _env.get_template(template_name).render(**kwargs)
