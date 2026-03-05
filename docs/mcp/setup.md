---
title: MCP Setup
---

# MCP Setup

This page covers how to connect Pixel Magic to various MCP-capable clients. The server supports two transport modes:

- **stdio** — the client spawns the server as a subprocess (recommended for local use)
- **streamable-http** — the client connects to a running HTTP server (useful for Docker/remote)

---

## Claude Desktop

Edit `claude_desktop_config.json` (located in `~/Library/Application Support/Claude/` on macOS):

```json
{
  "mcpServers": {
    "pixel-magic": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/pixel-magic", "run", "pixel-magic"],
      "env": {
        "GOOGLE_API_KEY": "your-gemini-key",
        "OPENAI_API_KEY": "your-openai-key"
      }
    }
  }
}
```

Restart Claude Desktop after saving. The Pixel Magic tools will appear in the tool picker.

---

## Claude Code

### stdio (recommended)

```bash
claude mcp add pixel-magic -- uv --directory /absolute/path/to/pixel-magic run pixel-magic
```

### Streamable HTTP (if running via Docker or a remote server)

```bash
claude mcp add --transport streamable-http pixel-magic http://localhost:5363/mcp
```

---

## VS Code / GitHub Copilot

Create or edit `.vscode/mcp.json` at your workspace root:

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

The `${env:VAR}` syntax reads from your shell environment, so you don't have to hardcode keys in the workspace file.

### HTTP transport

```json
{
  "servers": {
    "pixel-magic": {
      "type": "streamable-http",
      "url": "http://localhost:5363/mcp"
    }
  }
}
```

---

## Codex

### stdio

```bash
codex mcp add pixel-magic -- uv --directory /absolute/path/to/pixel-magic run pixel-magic
```

### HTTP

```bash
codex mcp add --url http://localhost:5363/mcp pixel-magic
```

---

## Docker / Remote HTTP

Start the server with HTTP transport:

```bash
docker compose up -d
# or manually:
uv run pixel-magic --transport streamable-http --port 5363
```

Then configure your client to use `http://your-host:5363/mcp`.

---

## Verifying the Connection

After connecting, run any tool discovery command in your client and confirm these tools appear:

- `generate_character`
- `extend_character_animation`
- `generate_tileset`
- `generate_items`
- `generate_effect`
- `generate_ui_elements`
- `generate_custom`
- `convert_image`
- `process_sprite_sheet`
- `extract_frames_tool`
- `run_qa_check`
- `list_palettes`
- `list_animations`
- `list_prompt_templates`
- `set_provider`
- `set_style_defaults`
- `run_evaluation`
- `compare_evaluations`
- `list_eval_cases`

If any tools are missing, check that the server started without errors and that your API keys are set correctly.
