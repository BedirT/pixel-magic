---
title: Quickstart
---

# Quickstart

This guide gets you from zero to your first generated sprite in a few minutes. It assumes you have already completed [Installation](./installation.md).

## Step 1: Start the Server

```bash
uv run pixel-magic
```

The server starts in stdio mode. Leave this terminal open if you're testing directly; for MCP clients, the client will launch the server automatically.

## Step 2: Connect Your Client

See [MCP Setup](../mcp/setup.md) for full client configuration. The shortest path for Claude Code is:

```bash
claude mcp add pixel-magic -- uv --directory /absolute/path/to/pixel-magic run pixel-magic
```

Replace `/absolute/path/to/pixel-magic` with the actual path where you cloned the repo.

## Step 3: Generate Your First Asset

Once connected, ask your client to call a tool. Here are three common first calls:

### Generate a batch of item icons

```json
{
  "tool": "generate_items",
  "arguments": {
    "item_descriptions": ["rusty iron sword", "red health potion", "old skeleton key"],
    "resolution": "32x32",
    "style": "16-bit SNES RPG style",
    "max_colors": 16
  }
}
```

This produces three 32x32 PNG icons, one per item. Output files land in `output/items/` relative to the project root.

### Generate a character sprite set

```json
{
  "tool": "generate_character",
  "arguments": {
    "character_description": "A young female knight in silver plate armor with a red cape",
    "name": "knight",
    "style": "16-bit SNES RPG style",
    "direction_mode": 4,
    "resolution": "64x64",
    "max_colors": 16
  }
}
```

This produces idle and walk animations in 4 directions (south, east, north, west) — 8 PNGs by default. Output lands in `output/knight/`.

### Generate a tileset

```json
{
  "tool": "generate_tileset",
  "arguments": {
    "biome": "forest",
    "tile_types": ["grass", "dirt", "stone path", "water", "tree trunk base"],
    "name": "forest_tileset",
    "tile_width": 64,
    "tile_height": 32,
    "style": "16-bit isometric RPG"
  }
}
```

## Step 4: Read the Result

All generation tools return the same JSON envelope:

```json
{
  "status": "success",
  "job_id": "abc123",
  "stage": "finalize",
  "artifacts": {
    "output_dir": "output/knight",
    "atlas_path": "output/knight/atlas.png",
    "metadata_path": "output/knight/metadata.json",
    "frame_paths": {
      "idle_south": ["output/knight/idle_south_000.png", "..."],
      "walk_south": ["output/knight/walk_south_000.png", "..."]
    },
    "total_frames": 16
  },
  "output_paths": ["output/knight/idle_south_000.png", "..."],
  "deterministic_gate": { "passed": true },
  "final_validation": { "decision": "pass" }
}
```

The key fields you'll use in a pipeline:

- `status` — `"success"` or `"error"`
- `output_paths` — flat list of all generated PNG file paths
- `artifacts.output_dir` — directory containing all outputs
- `artifacts.atlas_path` — single sprite atlas combining all frames

If `status` is `"error"`, the response includes an `errors` array with a `code`, `stage`, and `details` field. See [Troubleshooting](../troubleshooting/common-issues.md).

## Step 5: Use the Output

The PNG files are standard RGBA sprites ready to import into any game engine or editor:

- **Godot** — import PNGs directly or use the atlas
- **Unity** — import as Sprite assets, use the atlas with Sprite Atlas
- **Tiled / LDtk** — use individual tile PNGs as tilesets
- **Aseprite** — open any frame PNG for further editing

The metadata JSON includes frame dimensions, animation names, loop settings, and frame durations.

## Next Steps

- See [MCP Tool Reference](../mcp/tool-reference.md) for the full parameter documentation and more examples for every tool
- See [Providers and Environment](../configuration/providers-and-env.md) to tune defaults
- See [Evaluation and Testing](../evaluation/testing-and-judge.md) if you want to run quality regression tests
