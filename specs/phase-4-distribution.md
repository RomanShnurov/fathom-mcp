# Phase 4: Distribution

## Prerequisites

- Phases 1-3 completed
- All tests passing
- Core features stable

## Goals

1. **Docker image** - easy deployment
2. **PyPI package** - pip install
3. **Documentation** - comprehensive README and examples
4. **CI/CD** - automated testing and publishing

---

## Task 4.1: Docker Image

### Dockerfile

```dockerfile
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

# Optional: Install rclone for sync support
ARG WITH_SYNC=false
RUN if [ "$WITH_SYNC" = "true" ]; then \
    apt-get update && apt-get install -y --no-install-recommends curl unzip && \
    curl -O https://downloads.rclone.org/rclone-current-linux-amd64.zip && \
    unzip rclone-current-linux-amd64.zip && \
    cp rclone-*-linux-amd64/rclone /usr/local/bin/ && \
    rm -rf rclone-* && \
    apt-get remove -y curl unzip && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*; \
    fi

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

# Default knowledge directory
VOLUME /knowledge
ENV FKM_KNOWLEDGE__ROOT=/knowledge

# Config mount point
VOLUME /config

# Entry point
ENTRYPOINT ["python", "-m", "file_knowledge_mcp"]
CMD ["--config", "/config/config.yaml"]
```

### docker-compose.yaml

```yaml
version: "3.8"

services:
  file-knowledge-mcp:
    build:
      context: .
      args:
        WITH_SYNC: "false"
    image: file-knowledge-mcp:latest
    volumes:
      - ./documents:/knowledge:ro
      - ./config.yaml:/config/config.yaml:ro
    # For Claude Desktop integration via stdio
    stdin_open: true
    tty: true

  # With sync support
  file-knowledge-mcp-sync:
    build:
      context: .
      args:
        WITH_SYNC: "true"
    image: file-knowledge-mcp:sync
    volumes:
      - ./documents:/knowledge
      - ./config.yaml:/config/config.yaml:ro
      - ~/.config/rclone:/home/app/.config/rclone:ro  # rclone config
    stdin_open: true
    tty: true
```

### .dockerignore

```
.git
.gitignore
__pycache__
*.pyc
*.pyo
.pytest_cache
.ruff_cache
.mypy_cache
*.egg-info
dist
build
.env
.venv
venv
tests
docs
specs
*.md
!README.md
Makefile
justfile
docker-compose*.yaml
```

### Checklist

- [ ] Create Dockerfile with multi-stage build
- [ ] Create docker-compose.yaml
- [ ] Create .dockerignore
- [ ] Test build: `docker build -t file-knowledge-mcp .`
- [ ] Test run: `docker run -v ./docs:/knowledge file-knowledge-mcp`
- [ ] Test with sync: `docker build --build-arg WITH_SYNC=true`
- [ ] Document Docker usage in README

---

## Task 4.2: PyPI Package

### pyproject.toml (final)

```toml
[project]
name = "file-knowledge-mcp"
version = "0.1.0"
description = "File-first knowledge base MCP server with ugrep search"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.12"
authors = [
    { name = "Your Name", email = "your@email.com" }
]
keywords = [
    "mcp",
    "model-context-protocol",
    "knowledge-base",
    "search",
    "pdf",
    "ai",
    "llm",
    "claude",
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
    "Topic :: Text Processing :: Indexing",
]

dependencies = [
    "mcp>=1.0.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "pypdf>=4.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
sync = [
    "watchfiles>=0.20",
]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.0",
    "ruff>=0.1.0",
    "mypy>=1.0",
]
all = [
    "file-knowledge-mcp[sync,dev]",
]

[project.scripts]
file-knowledge-mcp = "file_knowledge_mcp.__main__:main"

[project.urls]
Homepage = "https://github.com/yourusername/file-knowledge-mcp"
Documentation = "https://github.com/yourusername/file-knowledge-mcp#readme"
Repository = "https://github.com/yourusername/file-knowledge-mcp"
Issues = "https://github.com/yourusername/file-knowledge-mcp/issues"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/file_knowledge_mcp"]

[tool.hatch.build.targets.sdist]
include = [
    "/src",
    "/tests",
    "/README.md",
    "/LICENSE",
    "/config.example.yaml",
]

[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
ignore = ["E501"]  # Line length handled by formatter

[tool.ruff.lint.isort]
known-first-party = ["file_knowledge_mcp"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --cov=file_knowledge_mcp --cov-report=term-missing"

[tool.coverage.run]
source = ["src/file_knowledge_mcp"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

### Publishing to PyPI

```bash
# Build
uv build

# Test on TestPyPI first
uv publish --repository testpypi

# Publish to PyPI
uv publish
```

### Checklist

- [ ] Finalize pyproject.toml
- [ ] Create LICENSE file (MIT)
- [ ] Test local install: `pip install -e .`
- [ ] Test build: `uv build`
- [ ] Register on PyPI
- [ ] Test publish to TestPyPI
- [ ] Publish to PyPI
- [ ] Verify install: `pip install file-knowledge-mcp`

---

## Task 4.3: README Documentation

### README.md

```markdown
# file-knowledge-mcp

[![PyPI version](https://badge.fury.io/py/file-knowledge-mcp.svg)](https://pypi.org/project/file-knowledge-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

File-first knowledge base MCP server. Search your documents with AI using the Model Context Protocol.

## Features

- **File-first approach** - Search directly in files using ugrep (not RAG)
- **Boolean search** - AND, OR, NOT operators for precise queries
- **Hierarchical collections** - Organize documents in folders
- **Multiple formats** - PDF, Markdown, plain text
- **Cloud sync** - Optional sync from Google Drive, Dropbox, S3 via rclone

## Quick Start

### Installation

```bash
# Install from PyPI
pip install file-knowledge-mcp

# With cloud sync support
pip install file-knowledge-mcp[sync]
```

### System Dependencies

```bash
# Ubuntu/Debian
sudo apt install ugrep poppler-utils

# macOS
brew install ugrep poppler

# Optional: rclone for cloud sync
# https://rclone.org/install/
```

### Usage

```bash
# Start with a documents folder
file-knowledge-mcp --root ./my-documents

# Or with a config file
file-knowledge-mcp --config config.yaml
```

### Claude Desktop Integration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "file-knowledge-mcp",
      "args": ["--root", "/path/to/documents"]
    }
  }
}
```

## Configuration

Create a `config.yaml`:

```yaml
knowledge:
  root: "./documents"

search:
  context_lines: 5
  max_results: 50

# Optional: cloud sync
sync:
  enabled: true
  remotes:
    gdrive:
      rclone_remote: "gdrive:MyDocuments"
```

See [config.example.yaml](config.example.yaml) for all options.

## Tools

| Tool | Description |
|------|-------------|
| `list_collections` | Browse document folders |
| `find_document` | Find documents by name |
| `search_documents` | Search inside documents |
| `search_multiple` | Parallel search for multiple terms |
| `read_document` | Read document content |
| `get_document_info` | Get metadata and TOC |
| `sync_remote` | Sync from cloud storage |

### Search Syntax

```
"attack armor"     - Find both terms (AND)
"move|teleport"    - Find either term (OR)
"attack -ranged"   - Exclude term (NOT)
'"end of turn"'    - Exact phrase
```

## Docker

```bash
# Build
docker build -t file-knowledge-mcp .

# Run
docker run -v ./docs:/knowledge file-knowledge-mcp

# With sync support
docker build --build-arg WITH_SYNC=true -t file-knowledge-mcp:sync .
```

## Development

```bash
# Clone
git clone https://github.com/yourusername/file-knowledge-mcp
cd file-knowledge-mcp

# Install with dev dependencies
uv sync --all-extras

# Run tests
pytest

# Lint
ruff check src tests
```

## License

MIT License - see [LICENSE](LICENSE) for details.
```

### Checklist

- [ ] Write comprehensive README
- [ ] Add badges (PyPI, license)
- [ ] Include all tools documentation
- [ ] Add search syntax examples
- [ ] Add Claude Desktop config example
- [ ] Add Docker instructions
- [ ] Add development setup

---

## Task 4.4: CI/CD with GitHub Actions

### .github/workflows/ci.yaml

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y ugrep poppler-utils

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: uv sync --all-extras

      - name: Lint with ruff
        run: uv run ruff check src tests

      - name: Type check with mypy
        run: uv run mypy src

      - name: Run tests
        run: uv run pytest --cov --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: coverage.xml

  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t file-knowledge-mcp .

      - name: Test Docker image
        run: |
          docker run --rm file-knowledge-mcp --help
```

### .github/workflows/release.yaml

```yaml
name: Release

on:
  push:
    tags:
      - "v*"

jobs:
  pypi:
    runs-on: ubuntu-latest
    environment: release
    permissions:
      id-token: write  # For trusted publishing

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install uv
        run: pip install uv

      - name: Build package
        run: uv build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1

  docker:
    runs-on: ubuntu-latest
    permissions:
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract version
        id: version
        run: echo "VERSION=${GITHUB_REF#refs/tags/v}" >> $GITHUB_OUTPUT

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:${{ steps.version.outputs.VERSION }}
            ghcr.io/${{ github.repository }}:latest

      - name: Build and push (with sync)
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          build-args: WITH_SYNC=true
          tags: |
            ghcr.io/${{ github.repository }}:${{ steps.version.outputs.VERSION }}-sync
            ghcr.io/${{ github.repository }}:sync
```

### Checklist

- [ ] Create .github/workflows/ci.yaml
- [ ] Create .github/workflows/release.yaml
- [ ] Test CI on push
- [ ] Configure PyPI trusted publishing
- [ ] Configure GHCR permissions
- [ ] Test release workflow with tag

---

## Task 4.5: Additional Documentation

### docs/configuration.md

Full configuration reference with all options.

### docs/tools.md

Detailed documentation for each tool with examples.

### docs/integration.md

Integration guides:
- Claude Desktop
- Claude Code
- Custom Python client
- REST API wrapper (optional)

### CHANGELOG.md

```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2024-XX-XX

### Added
- Initial release
- Core tools: list_collections, find_document, search_documents, read_document
- Parallel search with search_multiple
- Document metadata with get_document_info
- Cloud sync via rclone
- MCP Resources and Prompts
- Docker support
- PyPI package
```

### Checklist

- [ ] Create docs/ folder
- [ ] Write configuration.md
- [ ] Write tools.md
- [ ] Write integration.md
- [ ] Create CHANGELOG.md
- [ ] Add CONTRIBUTING.md
- [ ] Add CODE_OF_CONDUCT.md

---

## Completion Criteria

Phase 4 is complete when:

- [ ] Docker image builds and runs
- [ ] Package published to PyPI
- [ ] `pip install file-knowledge-mcp` works
- [ ] README is comprehensive
- [ ] CI runs on every PR
- [ ] Releases auto-publish to PyPI and GHCR
- [ ] Documentation covers all features
- [ ] At least 80% test coverage
