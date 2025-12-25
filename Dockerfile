# Multi-stage build for smaller image
FROM python:3.12-slim AS builder

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
FROM python:3.12-slim AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ugrep \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app
WORKDIR /home/app/app/src

# Copy virtual environment and source from builder
COPY --from=builder /app /home/app/app

# Set up environment
ENV PATH="/home/app/app/.venv/bin:$PATH"
ENV PYTHONPATH="/home/app/app/src"

# Default knowledge directory (read-only recommended)
VOLUME /knowledge
ENV CFS_KNOWLEDGE__ROOT=/knowledge

# Config mount point
VOLUME /config

# Entry point
ENTRYPOINT ["python", "-m", "contextfs"]
CMD ["--config", "/config/config.yaml"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import contextfs; print('OK')" || exit 1
