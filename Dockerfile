FROM python:3.12-slim AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml ./

# Install dependencies (no dev deps in production)
RUN uv pip install --system --no-cache .

# Copy source code
COPY src/ src/
COPY prompts/ prompts/
COPY palettes/ palettes/

# Create output directory
RUN mkdir -p output

# Default: stdio transport (for MCP clients like Claude Desktop)
# Override with --transport streamable-http for network access
ENV PIXEL_MAGIC_OUTPUT_DIR=/app/output
ENV PIXEL_MAGIC_PROMPTS_DIR=/app/prompts
ENV PIXEL_MAGIC_PALETTES_DIR=/app/palettes

EXPOSE 8000

ENTRYPOINT ["pixel-magic"]
CMD ["--transport", "stdio"]
