# Multi-stage build for smaller image
FROM python:3.12-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
RUN pip install uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Create virtual environment and install dependencies
RUN uv venv /app/.venv
RUN . /app/.venv/bin/activate && uv pip install --no-cache .

# --- Runtime stage ---
FROM python:3.12-slim as runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ugrep \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app
WORKDIR /home/app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /home/app/.venv

# Copy application code
COPY --chown=app:app src/ /home/app/src/

# Set up environment
ENV PATH="/home/app/.venv/bin:$PATH"
ENV PYTHONPATH="/home/app"

# Default knowledge directory (read-only recommended)
VOLUME /knowledge
ENV CFS_KNOWLEDGE__ROOT=/knowledge

# Config mount point
VOLUME /config

# Entry point
ENTRYPOINT ["python", "-m", "contextfs"]
CMD ["--config", "/config/config.yaml"]
