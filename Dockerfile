FROM python:3.12-slim AS base

# Install uv
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml README.md ./

# Install third-party dependencies only (not the local package)
RUN uv pip install --system --no-cache \
    "google-genai>=1.0.0" \
    "openai>=1.60.0" \
    "mcp[cli]>=1.20.0" \
    "opencv-python-headless>=4.9.0" \
    "Pillow>=10.0.0" \
    "scikit-image>=0.22.0" \
    "numpy>=1.26.0" \
    "pydantic>=2.6.0" \
    "pydantic-settings>=2.2.0" \
    "pyyaml>=6.0"

# Copy source code
COPY src/ src/
COPY prompts/ prompts/
COPY palettes/ palettes/

# Install the local package (no-deps since already installed above)
RUN uv pip install --system --no-cache --no-deps .

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
