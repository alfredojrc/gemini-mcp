# Gemini MCP Server Dockerfile
# Multi-stage build for minimal production image

FROM python:3.12-slim as builder

WORKDIR /build

# Install build dependencies
RUN pip install --no-cache-dir build

# Copy source
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Build wheel
RUN python -m build --wheel

# =============================================================================
# Production Image
# =============================================================================
FROM python:3.12-slim

# Create non-root user
RUN useradd -m -s /bin/bash app

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheel from builder and install
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Create directories
RUN mkdir -p /app/plugins /app/personas /home/app/.gemini-mcp \
    && chown -R app:app /app /home/app

# Copy default personas
COPY --chown=app:app personas/ /app/personas/

# Switch to non-root user
USER app

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV GEMINI_MCP_TRANSPORT=sse
ENV GEMINI_MCP_SERVER_PORT=8765
ENV PLUGIN_DIR=/app/plugins
ENV PERSONA_DIR=/app/personas

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

# Expose port
EXPOSE 8765

# Run server
CMD ["gemini-mcp"]
