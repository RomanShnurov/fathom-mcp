# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-01-11

### Added
- **HTTP Streamable Transport** - New transport option for remote deployment and web clients
  - Supports both `stdio` (default, for Claude Desktop) and `streamable-http` transports
  - Configurable via environment variables (`FMCP_TRANSPORT__*`) or config file
  - CORS support with origin validation (no wildcards in production)
  - Transport factory pattern for easy extension
- **Server Lifecycle Management** (`lifecycle.py`)
  - Startup/shutdown event handlers
  - Graceful resource cleanup with timeout protection
  - Proper async context manager patterns
- **HTTP Middleware System** (`middleware.py`)
  - Security headers middleware (HSTS, X-Content-Type-Options, etc.)
  - Request ID tracking for correlation
  - Structured error handling with HTTP status codes
- **Structured Logging** (`logging_config.py`)
  - JSON formatter for production use
  - Human-readable formatter for development
  - Request ID correlation in logs
  - Log level configuration per environment
- **Test Client CLI** (`fathom-mcp-test`)
  - Multi-transport testing support (stdio, http, sse)
  - Test levels: connectivity, basic, full
  - Retry logic with exponential backoff
  - Comprehensive test suite for all MCP tools
- **Filter Builder System** (`filter_builder.py`)
  - Flexible ugrep filter construction
  - Better format handling and validation
  - Improved error messages
- **Docker Enhancements**
  - HTTP healthcheck endpoint (`/health`, `/healthz`)
  - Docker profiles: `stdio`, `http`
  - Updated docker-compose with HTTP service configuration
  - Health monitoring with configurable retries
- **CLI Search Tool** (`scripts/search_cli.py`, `search.bat`, `search.sh`)
  - Standalone search interface for testing
  - Cross-platform support (Windows/Unix)
- **Documentation**
  - New `docs/security.md` - Comprehensive security guide with reverse proxy, VPN, OAuth examples
  - New `docs/filter-architecture.md` - Filter system architecture documentation
  - Updated README with HTTP transport usage examples
  - Configuration examples for HTTP transport (`config.http.example.yaml`)

### Changed
- **Dependencies** - Moved `tenacity` from dev to main dependencies for retry logic in HTTP client
- **Configuration Schema** - Extended with transport-specific settings (host, port, CORS, logging)
- **Error System** - Enhanced with HTTP status code mapping for better client error handling
- **Server Initialization** - Refactored to support transport selection and factory pattern
- **Docker Base Image** - Updated Dockerfile with multi-stage build for HTTP support

### Removed
- Obsolete test scripts (`test_dependencies.py`, `test_docker.py`, `test_local_setup.py`, `test_mcp_server.py`, `validate_ci.py`, `quick_check.py`)
- `docs/integration.md` - Replaced by comprehensive `docs/security.md`

### Security
- ⚠️ **Important:** HTTP transport does NOT include built-in authentication by design
- Recommend using reverse proxy (Nginx/Caddy/Traefik) with auth for HTTP deployments
- VPN-based access (Tailscale/WireGuard) recommended for remote access
- CORS wildcard (`*`) blocked in production mode
- Origin format validation for CORS
- See `docs/security.md` for deployment security best practices

### Testing
- New integration tests for HTTP transport (`test_integration_http.py`)
- Middleware tests (`test_middleware.py`)
- Transport factory tests (`test_transports.py`)
- Filter builder tests (`test_filter_builder.py`, `test_filter_integration.py`)
- Test client tests (`test_test_client.py`)

### CI/CD
- Updated GitHub Actions workflows for dependency bumping
- Pre-commit hooks updated with new dependencies

## [0.1.0] - 2025-01-XX

### Added
- Initial release of Fathom MCP
- File-first knowledge base with hierarchical collections
- Full-text search powered by ugrep with boolean operators (AND, OR, NOT)
- Support for multiple document formats (PDF, Markdown, Text, CSV)
- Optional format support (DOCX, ODT, EPUB, HTML, JSON, XML) via external tools
- MCP server implementation with 6 tools:
  - `list_collections` - Browse folder hierarchy
  - `find_document` - Find documents by name
  - `search_documents` - Full-text search with scope control
  - `search_multiple` - Parallel search execution
  - `read_document` - Read document content with page selection
  - `get_document_info` - Get document metadata and TOC
- Security features:
  - Path validation and traversal prevention
  - Shell command sandboxing with whitelist/blacklist modes
  - Read-only design
- Configuration system with YAML and environment variable support
- Docker deployment support with docker-compose
- Claude Desktop integration
- Comprehensive test suite with pytest
- Documentation and examples

### Security
- Implemented defense-in-depth security model
- Path traversal attack prevention
- Command sandboxing with timeout enforcement
- Whitelist-based filter command validation

[Unreleased]: https://github.com/RomanShnurov/fathom-mcp/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/RomanShnurov/fathom-mcp/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/RomanShnurov/fathom-mcp/releases/tag/v0.1.0
