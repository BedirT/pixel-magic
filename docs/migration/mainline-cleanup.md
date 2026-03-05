---
title: Mainline Cleanup Migration
---

## Breaking Changes

- Removed MCP tool: `add_character_animation`
- Added MCP tool: `extend_character_animation`
- Removed legacy generation architecture modules:
  - `src/pixel_magic/generation/orchestrator.py`
  - `src/pixel_magic/generation/validation.py`
  - `src/pixel_magic/agents/` package
- Generation tools no longer expose `validate` / `max_retries` arguments.

## Why

- Single workflow-native runtime
- deterministic transition ownership by executor
- mandatory hard gates with explicit retry budget
- simpler maintenance and clearer operational behavior

## Migration Mapping

- `add_character_animation` -> `extend_character_animation`
- old multi-agent package imports -> workflow runtime imports:
  - `WorkflowExecutor`
  - `GenerationRequest`
  - `AgentRuntime`
  - `ProviderAdapter`

## Extension Workflow Notes

`extend_character_animation` keeps the prior user goal:

- add a new animation for an existing character design
- provide one reference image path
- generate requested animation across configured directions
