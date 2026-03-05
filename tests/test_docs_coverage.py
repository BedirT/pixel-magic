"""Checks for MCP docs coverage and legacy runtime import cleanup."""

from __future__ import annotations

import subprocess
import sys


def test_mcp_docs_coverage_script_passes():
    completed = subprocess.run(
        [sys.executable, "scripts/check_mcp_docs_coverage.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_no_legacy_runtime_imports_in_core_paths():
    checks = [
        ("src/pixel_magic/server.py", "pixel_magic.generation.orchestrator"),
        ("src/pixel_magic/server.py", "pixel_magic.generation.validation"),
        ("src/pixel_magic/server.py", "pixel_magic.agents"),
        ("src/pixel_magic/evaluation/runner.py", "pixel_magic.agents"),
        ("scripts/generate_game_demo.py", "pixel_magic.generation.orchestrator"),
    ]
    for path, forbidden in checks:
        text = open(path, encoding="utf-8").read()
        assert forbidden not in text
