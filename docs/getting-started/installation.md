---
title: Installation
---

# Installation

## Prerequisites

**Python 3.12 or later** is required. Check your version:

```bash
python --version
```

**`uv` package manager** is required for dependency management and running the server. Install it if you don't have it:

```bash
curl -Lsf https://astral.sh/uv/install.sh | sh
```

**At least one provider API key:**

| Provider | Key | Used For |
|---|---|---|
| Gemini | `GOOGLE_API_KEY` | Image generation (default) |
| OpenAI | `OPENAI_API_KEY` | Image generation (alternative) + agent reasoning layer |

You can use Gemini alone, OpenAI alone, or both. If you use OpenAI as the image provider, `OPENAI_API_KEY` covers both image generation and agent orchestration. If you use Gemini for images, you still need `OPENAI_API_KEY` for the agent reasoning layer.

## Clone and Install

```bash
git clone https://github.com/BedirT/pixel-magic.git
cd pixel-magic
uv sync
```

`uv sync` installs all Python dependencies into an isolated virtual environment managed by `uv`. You do not need to activate it manually.

## Configure Environment

Copy the example environment file and edit it:

```bash
cp .env.example .env
```

Open `.env` and set your API keys at minimum:

```bash
GOOGLE_API_KEY=your-gemini-key-here
OPENAI_API_KEY=your-openai-key-here
```

See [Providers and Environment](../configuration/providers-and-env.md) for the full list of configuration options.

## Start the Server

### stdio transport (default — recommended for MCP clients)

```bash
uv run pixel-magic
```

The server starts and listens on stdin/stdout. This is the correct mode for Claude Desktop, Claude Code, VS Code, and Codex.

### Streamable HTTP transport (for remote/Docker deployments)

```bash
uv run pixel-magic --transport streamable-http --port 8000
```

The server listens on `http://localhost:8000/mcp`.

### Docker

```bash
docker compose up -d
```

The Docker setup uses the streamable-http transport on port 5363 by default. Adjust `docker-compose.yml` to pass your API keys.

## Verify the Installation

Run the test suite to confirm everything works:

```bash
uv run pytest -q
```

Check that all MCP tools are documented (required for CI):

```bash
uv run python scripts/check_mcp_docs_coverage.py
```

Once the server starts without errors, proceed to [MCP Setup](../mcp/setup.md) to connect your client.
