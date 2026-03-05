# Pixel Magic

AI-powered pixel art sprite generation and conversion pipeline, exposed as an MCP server.

Generate game-ready character sheets, tilesets, items, effects, and UI elements — all in consistent pixel art style with deterministic post-processing and quality assurance.

## Features

- **AI Generation** — Gemini (primary) or OpenAI image generation with crafted prompt templates
- **Full Pipeline** — Background removal → grid inference → downscale → palette quantization → cleanup → consistency → export
- **Separator Framing** — Magenta (#FF00FF) divider lines in prompts enable deterministic frame extraction; graceful fallback to heuristic detection when absent
- **Multi-direction Characters** — 4-dir (SE + NE unique, SW + NW via flips) or 8-dir (5 unique + flips) with proper isometric convention
- **Animation Support** — Walk, run, idle, attack, death, hit, cast — or define custom animations
- **Quality Assurance** — Deterministic checks (palette, grid, islands, flicker) + AI vision evaluation
- **Export Formats** — PNG atlas + JSON metadata, individual PNGs, Godot SpriteFrames `.tres`, Godot TileSet `.tres`
- **MCP Server** — 16 tools accessible from Copilot, Claude Desktop, Claude Code, Codex, or any MCP client
- **Palette System** — Bundled palettes (default_16, survival_earth, fantasy_rpg) or bring your own `.hex` files

## Quick Start

```bash
# Install
git clone https://github.com/your-org/pixel-magic.git
cd pixel-magic
uv sync

# Configure
cp .env.example .env
# Add your GOOGLE_API_KEY and/or OPENAI_API_KEY to .env

# Run as MCP server (stdio)
uv run pixel-magic

# Run as HTTP server
uv run pixel-magic --transport streamable-http --port 8000

# Run with Docker
docker compose up -d
```

## MCP Tools

### Generation

| Tool | Description |
|---|---|
| `generate_character` | Full character sheet: idle directions + animations |
| `add_character_animation` | Add animation to existing character using reference |
| `generate_tileset` | Ground, object, or wall tiles |
| `generate_items` | Batch item icons or world-drop sprites |
| `generate_effect` | Animated VFX (explosions, magic, etc.) |
| `generate_ui_elements` | UI components (bars, slots, buttons) |
| `generate_custom` | Free-form prompt with full pipeline |

### Pipeline

| Tool | Description |
|---|---|
| `convert_image` | Convert any image to pixel art |
| `process_sprite_sheet` | Process an existing sprite sheet through the pipeline |
| `extract_frames_tool` | Extract individual frames from a sprite sheet |

### Quality

| Tool | Description |
|---|---|
| `run_qa_check` | Run deterministic + vision QA on sprites |

### Utility

| Tool | Description |
|---|---|
| `list_palettes` | Show available color palettes |
| `list_animations` | Show built-in animation presets |
| `list_prompt_templates` | Show available prompt templates |
| `set_provider` | Switch between gemini/openai |
| `set_style_defaults` | Update default resolution, palette, style |

## Project Structure

```
pixel-magic/
├── src/pixel_magic/
│   ├── __main__.py          # CLI entry point
│   ├── server.py            # MCP server (16 tools)
│   ├── config.py            # Pydantic settings
│   ├── models/              # Data models
│   │   ├── asset.py         # Sprite, animation, spec types
│   │   ├── palette.py       # Palette & dither config
│   │   └── metadata.py      # QA reports, atlas metadata
│   ├── providers/           # AI image providers
│   │   ├── base.py          # Abstract interface
│   │   ├── gemini.py        # Google Gemini
│   │   └── openai.py        # OpenAI Images API
│   ├── generation/          # Prompt & orchestration
│   │   ├── prompts.py       # Template loader
│   │   ├── extractor.py     # Frame extraction (separator + heuristic)
│   │   ├── orchestrator.py  # Multi-step generation coordinator
│   │   └── prompt_library/  # Python template modules
│   ├── pipeline/            # Deterministic post-processing
│   │   ├── ingest.py        # Load, normalize, bg removal
│   │   ├── grid.py          # Grid inference
│   │   ├── projection.py    # Downsample to target resolution
│   │   ├── palette.py       # OKLab quantization & dithering
│   │   ├── cleanup.py       # AA removal, islands, outlines
│   │   ├── consistency.py   # Palette lock, pivot, jitter
│   │   └── export.py        # Atlas, JSON, Godot .tres
│   └── qa/                  # Quality assurance
│       ├── deterministic.py # 8 automated checks
│       └── vision.py        # AI vision evaluation
├── prompts/                 # YAML prompt templates
├── palettes/                # .hex palette files
├── docs/
│   └── mcp-installation.md  # Setup for all MCP clients
├── Dockerfile
├── docker-compose.yaml
└── pyproject.toml
```

## Configuration

All settings can be set via environment variables with `PIXEL_MAGIC_` prefix. See `.env.example` for the full list.

## MCP Client Setup

See [docs/mcp-installation.md](docs/mcp-installation.md) for setup instructions for:
- VS Code / GitHub Copilot
- Claude Desktop
- Claude Code
- Codex

## License

MIT
