#!/usr/bin/env python3
"""Check that MCP tools in server.py are documented in docs/mcp/tool-reference.md."""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_PATH = REPO_ROOT / "src/pixel_magic/server.py"
DOC_PATH = REPO_ROOT / "docs/mcp/tool-reference.md"
TOOL_HEADING_RE = re.compile(r"^###\s+`([a-zA-Z0-9_]+)`\s*$")


def _is_mcp_tool(node: ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            if isinstance(dec.func.value, ast.Name) and dec.func.value.id == "mcp":
                if dec.func.attr == "tool":
                    return True
    return False


def get_server_tool_names(path: Path) -> set[str]:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in module.body:
        if isinstance(node, ast.AsyncFunctionDef) and _is_mcp_tool(node):
            names.add(node.name)
    return names


def get_documented_tool_names(path: Path) -> set[str]:
    names: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = TOOL_HEADING_RE.match(raw.strip())
        if match:
            names.add(match.group(1))
    return names


def main() -> int:
    if not SERVER_PATH.exists():
        print(f"ERROR: missing server file: {SERVER_PATH}")
        return 1
    if not DOC_PATH.exists():
        print(f"ERROR: missing docs file: {DOC_PATH}")
        return 1

    server_tools = get_server_tool_names(SERVER_PATH)
    doc_tools = get_documented_tool_names(DOC_PATH)

    missing_in_docs = sorted(server_tools - doc_tools)
    stale_in_docs = sorted(doc_tools - server_tools)

    if missing_in_docs:
        print("ERROR: tools missing from docs:")
        for name in missing_in_docs:
            print(f"  - {name}")
    if stale_in_docs:
        print("ERROR: tools documented but missing from server:")
        for name in stale_in_docs:
            print(f"  - {name}")

    if missing_in_docs or stale_in_docs:
        return 1

    print(f"OK: {len(server_tools)} MCP tools are documented.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
