# Pixel Magic

Workflow-native MCP toolkit for game-ready pixel art generation.

Pixel Magic provides a deterministic generation pipeline with agent orchestration:

- fixed stage transitions
- mandatory deterministic QA gate
- mandatory final validator agent gate
- one correction retry budget

## Features

- character, tileset, item, effect, UI, and custom generation tools
- character animation extension from a reference image via `extend_character_animation`
- provider support: Gemini and OpenAI
- deterministic post-processing and artifact exports
- offline LLM-as-a-Judge evaluation and regression reporting

## Quick Start

```bash
git clone https://github.com/BedirT/pixel-magic.git
cd pixel-magic
uv sync
cp .env.example .env
# set GOOGLE_API_KEY and/or OPENAI_API_KEY
uv run pixel-magic
```

## MCP Tools

Generation:

- `generate_character`
- `extend_character_animation`
- `generate_tileset`
- `generate_items`
- `generate_effect`
- `generate_ui_elements`
- `generate_custom`

Pipeline and QA:

- `convert_image`
- `process_sprite_sheet`
- `extract_frames_tool`
- `run_qa_check`

Utility and evaluation:

- `list_palettes`
- `list_animations`
- `list_prompt_templates`
- `set_provider`
- `set_style_defaults`
- `run_evaluation`
- `compare_evaluations`
- `list_eval_cases`

## Documentation

Project docs and MCP docs are under `docs/`, with a Docusaurus site under `website/`.

Run docs locally:

```bash
cd website
npm install
npm run start
```

Key docs:

- [Installation](docs/getting-started/installation.md)
- [MCP Setup](docs/mcp/setup.md)
- [MCP Tool Reference](docs/mcp/tool-reference.md)
- [Runtime Architecture](docs/architecture/runtime.md)

## Verification

Run tests:

```bash
uv run pytest -q
```

Check MCP docs coverage:

```bash
uv run python scripts/check_mcp_docs_coverage.py
```

## License

MIT
