# Pixel Magic

AI-powered pixel art sprite and terrain tile generation CLI built around a Gemini canvas pipeline. It generates isometric character sheets, animation sheets, terrain tilesets, world objects, and VFX effects, then cleans and extracts usable PNG assets.

## Quick Start

```bash
git clone https://github.com/BedirT/pixel-magic.git
cd pixel-magic
uv sync
cp .env.example .env
# set GOOGLE_API_KEY in .env
```

## Commands

| Command | Purpose |
|---------|---------|
| `generate` | Multi-view isometric character sheets |
| `animate` | Animation frames for existing characters |
| `animate-object` | Animation frames for existing objects |
| `tile` | Isometric terrain tilesets |
| `object` | World objects/props |
| `effect` | Subjectless VFX animations |

```bash
# Examples
pixel-magic generate --name knight --description "medieval knight with silver armor"
pixel-magic animate --name knight --animation walk --frames 6 --platform
pixel-magic tile --theme forest --sizes 32,64
pixel-magic object --preset forest
pixel-magic animate-object --set forest --name oak_tree --animation sway --frames 5
pixel-magic effect --name explosion --frames 5
pixel-magic effect --preset combat
```

See [`docs/cli.md`](docs/cli.md) for full argument reference and examples.

## How It Works

All commands follow a canvas-based pipeline: build a template canvas with guides (platforms, wireframes, labels), Gemini fills in content, a cleanup pass removes guides. Post-processing extracts individual sprites with background removal, mask cleanup, and outline normalization.

See [`docs/process.md`](docs/process.md) for the detailed technical walkthrough.

## Docs

- [CLI reference](docs/cli.md) — all commands, arguments, presets, and output structure
- [Process overview](docs/process.md) — detailed generation pipeline and post-processing stages
- [Project state](STATE.md) — what works, known limitations, architecture decisions

## License

MIT
