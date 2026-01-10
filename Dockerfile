# Multi-stage build for smaller image
FROM python:3.14-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
RUN pip install uv

WORKDIR /app

# Copy dependency files and README (required by pyproject.toml)
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# Create virtual environment and install dependencies with frozen lock file
RUN uv venv /app/.venv
RUN . /app/.venv/bin/activate && uv sync --frozen

# --- Runtime stage ---
FROM python:3.14-slim AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ugrep \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash app

# Copy healthcheck script (as root)
COPY docker/healthcheck.py /usr/local/bin/healthcheck.py
RUN chmod +x /usr/local/bin/healthcheck.py

# Copy virtual environment and source from builder
COPY --from=builder /app /home/app/app
RUN chown -R app:app /home/app/app

# Switch to non-root user
USER app
WORKDIR /home/app/app/src

# Set up environment
ENV PATH="/home/app/app/.venv/bin:$PATH"
ENV PYTHONPATH="/home/app/app/src"

# Default knowledge directory (read-only recommended)
VOLUME /knowledge
ENV FMCP_KNOWLEDGE__ROOT=/knowledge

# Config mount point
VOLUME /config

# Expose default HTTP port (can be overridden via FMCP_TRANSPORT__PORT)
# Declarative - actual port configured via environment
EXPOSE 8765

# Entry point
ENTRYPOINT ["python", "-m", "fathom_mcp"]
CMD ["--config", "/config/config.yaml"]

# Healthcheck using Python script
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python /usr/local/bin/healthcheck.py || exit 1
