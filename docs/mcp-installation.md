# MCP Installation Guide

Connect Pixel Magic as an MCP server to your AI coding assistant.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- A Gemini API key and/or OpenAI API key

## Setup

```bash
# Clone and install
git clone https://github.com/your-org/pixel-magic.git
cd pixel-magic
uv sync

# Configure API keys
cp .env.example .env
# Edit .env with your API keys
```

---

## VS Code / GitHub Copilot

### Option A: Native (uv)

Add to your workspace `.vscode/mcp.json`:

```json
{
  "servers": {
    "pixel-magic": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/pixel-magic", "run", "pixel-magic"],
      "env": {
        "GOOGLE_API_KEY": "${env:GOOGLE_API_KEY}",
        "OPENAI_API_KEY": "${env:OPENAI_API_KEY}"
      }
    }
  }
}
```

Or use the included `.mcp.json` in the project root (uses `${workspaceFolder}`).

### Option B: Docker (streamable-http)

```bash
docker compose up -d
```

Then in `.vscode/mcp.json`:

```json
{
  "servers": {
    "pixel-magic": {
      "type": "streamable-http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

---

## Claude Desktop

### Option A: Native (uv)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "pixel-magic": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/pixel-magic", "run", "pixel-magic"],
      "env": {
        "GOOGLE_API_KEY": "your-key-here",
        "OPENAI_API_KEY": "your-key-here"
      }
    }
  }
}
```

### Option B: Docker (streamable-http)

```bash
docker compose up -d
```

Then in the Claude Desktop config:

```json
{
  "mcpServers": {
    "pixel-magic": {
      "type": "streamable-http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

---

## Claude Code (CLI)

### Option A: Native (uv)

```bash
claude mcp add pixel-magic -- uv --directory /absolute/path/to/pixel-magic run pixel-magic
```

Set environment variables before launching:

```bash
export GOOGLE_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
claude
```

### Option B: Docker (streamable-http)

```bash
docker compose up -d
claude mcp add --transport streamable-http pixel-magic http://localhost:8000/mcp
```

---

## Codex (OpenAI)

### Option A: Native (uv)

In your project's `codex.json` or via the Codex CLI:

```bash
codex mcp add pixel-magic -- uv --directory /absolute/path/to/pixel-magic run pixel-magic
```

### Option B: Docker

```bash
docker compose up -d
codex mcp add --transport streamable-http pixel-magic http://localhost:8000/mcp
```

---

## Verifying the Connection

Once connected, ask your AI assistant to list available tools. You should see tools like:

- `generate_character` — Generate a full character sprite sheet
- `generate_tileset` — Generate tileset tiles
- `generate_items` — Generate item sprites
- `generate_effect` — Generate animated effects
- `list_palettes` — List available color palettes
- `list_prompt_templates` — List available prompt templates
- `run_qa_check` — Run quality checks on sprites
- `convert_image` — Convert any image to pixel art

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PIXEL_MAGIC_PROVIDER` | `gemini` | `gemini` or `openai` |
| `GOOGLE_API_KEY` | — | Gemini API key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `PIXEL_MAGIC_DIRECTION_MODE` | `4` | 4-dir or 8-dir |
| `PIXEL_MAGIC_PALETTE_SIZE` | `16` | Max colors |
| `PIXEL_MAGIC_QA_VISION_ENABLED` | `true` | Enable AI vision QA |
| `PIXEL_MAGIC_OUTPUT_DIR` | `output` | Output directory |

See `.env.example` for the full list.
