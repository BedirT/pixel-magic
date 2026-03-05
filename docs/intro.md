---
id: intro
title: Pixel Magic
slug: /
---

# Pixel Magic

Pixel Magic is an MCP server that generates game-ready pixel art assets using AI. You connect it to any MCP-capable client (Claude Desktop, Claude Code, VS Code Copilot, Codex, etc.) and call tools to generate characters, tilesets, items, effects, UI elements, and more — all as production-quality PNG sprite files on your local disk.

## How It Works

Every generation request passes through a fixed pipeline:

1. **Input validation** — parameters are checked before any API call is made
2. **Planning** — an agent produces a structured generation plan (prompts, frame counts, layout)
3. **Generation** — the active AI provider (Gemini or OpenAI) renders the images
4. **Post-processing** — frames are extracted, palette-quantized, and cleaned up deterministically
5. **QA gate** — alpha compliance, palette drift, and frame count are checked; failures trigger one correction retry
6. **Validator agent** — a second agent reviews the output and either passes, requests a correction, or fails the job
7. **Export** — approved frames are written to disk as individual PNGs plus an atlas sheet

This means you get consistent, QA-checked output every time — not raw model output that might have the wrong frame count or a broken alpha channel.

## What You Can Generate

| Tool | Output |
|---|---|
| `generate_character` | Full character sprite set with all directions and animations |
| `extend_character_animation` | New animation for an existing character from a reference image |
| `generate_tileset` | Isometric tile variants for a biome |
| `generate_items` | Batch item icon sprites |
| `generate_effect` | Animated visual effects (explosions, magic, etc.) |
| `generate_ui_elements` | Batch UI sprite elements |
| `generate_custom` | Anything — freeform prompt with frame extraction |

Pipeline and utility tools are also available for converting images, processing existing sprite sheets, running QA checks, and managing palettes.

## Providers

Pixel Magic supports two AI providers:

- **Gemini** (`GOOGLE_API_KEY`) — default for image generation
- **OpenAI** (`OPENAI_API_KEY`) — alternative image generation plus the agent reasoning layer

You can switch providers at runtime using `set_provider` without restarting the server.

## Recommended Reading Order

1. [Installation](./getting-started/installation.md) — clone, configure keys, start the server
2. [Quickstart](./getting-started/quickstart.md) — your first generation in under 5 minutes
3. [MCP Setup](./mcp/setup.md) — connect your client (Claude Desktop, VS Code, Codex, etc.)
4. [MCP Tool Reference](./mcp/tool-reference.md) — complete reference for all tools with examples
5. [Providers and Environment](./configuration/providers-and-env.md) — all environment variables
6. [Runtime Architecture](./architecture/runtime.md) — pipeline internals
7. [Evaluation and Testing](./evaluation/testing-and-judge.md) — offline regression testing
