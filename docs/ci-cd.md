# CI/CD Documentation

## Overview

This project uses GitHub Actions for continuous integration and deployment with the following workflows:

## Workflows

### CI Pipeline (`.github/workflows/ci.yaml`)

Runs on every push to main/master and pull requests:

- **Testing**: Runs tests on Python 3.12 and 3.13
- **Linting**: Uses ruff for code quality checks
- **Type Checking**: Uses mypy for static type analysis
- **Coverage**: Generates coverage reports and uploads to Codecov
- **Docker**: Builds and tests Docker image with caching

**Performance Optimizations:**
- UV dependency caching saves ~30 seconds per run
- Docker layer caching via GitHub Actions cache
- Parallel job execution

### Release Pipeline (`.github/workflows/release.yaml`)

Triggered on version tags (v*):

- **PyPI**: Builds and publishes Python package using trusted publishing
- **Docker**: Builds multi-architecture images (AMD64/ARM64) and pushes to GHCR

## Docker Build Strategy

### Multi-stage Build
- **Builder stage**: Installs dependencies in virtual environment
- **Runtime stage**: Minimal image with only runtime dependencies
- **Security**: Runs as non-root user

### Optimizations
- Uses `uv.lock` for reproducible builds
- Layer caching for faster builds
- Health checks for container monitoring
- Multi-architecture support (AMD64/ARM64)

## Dependency Management

### Dependabot
Automated dependency updates for:
- Python packages (weekly)
- GitHub Actions (weekly)
- Docker base images (weekly)

### Security
- Action versions are pinned for security
- Trusted publishing for PyPI releases
- Non-root container execution

## Local Development

### Testing Docker Build
```bash
docker build -t contextfs .
docker run --rm contextfs --help
```

### Running Tests
```bash
uv sync --extra dev
uv run pytest --cov
```

## Monitoring

- **Coverage**: Tracked via Codecov
- **Container Health**: Built-in health checks
- **Build Performance**: GitHub Actions insights