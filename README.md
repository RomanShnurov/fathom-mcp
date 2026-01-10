# Fathom MCP

[![PyPI version](https://badge.fury.io/py/fathom-mcp.svg)](https://badge.fury.io/py/fathom-mcp)
[![Python versions](https://img.shields.io/pypi/pyversions/fathom-mcp.svg)](https://pypi.org/project/fathom-mcp/)
[![Tests and Quality](https://github.com/RomanShnurov/fathom-mcp/actions/workflows/tests-and-quality.yaml/badge.svg)](https://github.com/RomanShnurov/fathom-mcp/actions/workflows/tests-and-quality.yaml)
[![Integration - Document Formats](https://github.com/RomanShnurov/fathom-mcp/actions/workflows/integration-formats.yaml/badge.svg)](https://github.com/RomanShnurov/fathom-mcp/actions/workflows/integration-formats.yaml)
[![codecov](https://codecov.io/gh/RomanShnurov/fathom-mcp/branch/master/graph/badge.svg)](https://codecov.io/gh/RomanShnurov/fathom-mcp)

A Model Context Protocol server that provides AI assistants with direct access to local document collections through file-first search capabilities.

## Features

### Search Capabilities
- **Full-text search** with boolean operators (AND, OR, NOT) and exact phrase matching
- **Parallel search** across multiple queries for faster results
- **Fuzzy matching** and context-aware result highlighting
- **Powered by ugrep** - No database or RAG infrastructure required

### Organization
- **Hierarchical collections** - Organize knowledge using folder structures
- **Scope control** - Search globally, within collections, or in specific documents
- **Smart discovery** - Find documents by name or path patterns

### Format Support
- **Multiple document formats** - PDF, DOCX, HTML, JSON, XML, and more
- **Automatic format detection** - No manual configuration required
- **Smart filter integration** - Uses pandoc, jq, and other tools
- **Graceful degradation** - Formats auto-disabled if tools unavailable
- See [docs/supported-formats.md](docs/supported-formats.md) for full details

### Security
- **Read-only access** - Server never modifies your documents
- **Path validation** - Prevents directory traversal attacks
- **Command sandboxing** - Filter commands run in restricted mode
- **Whitelist enforcement** - Shell filters validated before execution

## Installation

### From PyPI (Recommended)

Install Fathom MCP directly from PyPI:

```bash
pip install fathom-mcp
```

Or with uv:

```bash
uv pip install fathom-mcp
```

### System Dependencies

This server requires the following system utilities:

```bash
# Ubuntu/Debian
sudo apt install ugrep poppler-utils

# macOS
brew install ugrep poppler
```

## Supported Formats

Fathom MCP supports searching and reading multiple document formats:

### Default Formats (No Additional Tools Required)
- **Markdown** (.md, .markdown)
- **Plain Text** (.txt, .rst)
- **CSV** (.csv)
- **PDF** (.pdf) - requires pdftotext (from poppler-utils)

### Optional Formats (Requires External Tools)
- **Microsoft Word** (.doc, .docx) - requires pandoc or antiword
- **OpenDocument** (.odt) - requires pandoc
- **EPUB** (.epub) - requires pandoc
- **HTML** (.html, .htm) - requires pandoc
- **RTF** (.rtf) - requires pandoc
- **JSON** (.json) - requires jq
- **XML** (.xml) - requires pandoc

### Quick Setup for Optional Formats

To enable all optional formats:

```bash
# macOS
brew install pandoc jq

# Linux (Ubuntu/Debian)
sudo apt install pandoc jq

# Windows (Chocolatey)
choco install pandoc jq
```

See [docs/supported-formats.md](docs/supported-formats.md) for detailed installation instructions, configuration options, and troubleshooting.

## Collections and Scope

The File Knowledge server organizes documents using a **collection-based hierarchy** that maps directly to your filesystem structure.

### Understanding Collections

- A **collection** is simply a folder within your knowledge base root
- Collections can be nested to any depth
- Each document belongs to exactly one collection (its containing folder)
- The root directory itself is the top-level collection

### Configuring the Knowledge Root

The knowledge root can be specified via:

**Command-line argument** (recommended for static setups):
```bash
fathom-mcp --root /path/to/documents
```

**Configuration file**:
```yaml
knowledge:
  root: "/path/to/documents"
```

**Environment variable**:
```bash
export FMCP_KNOWLEDGE__ROOT=/path/to/documents
```

### Search Scopes

All search operations support three scope levels:

- **Global scope** - Search across all documents in the knowledge base
- **Collection scope** - Limit search to a specific folder and its subfolders
- **Document scope** - Search within a single document only

This hierarchical approach enables efficient knowledge organization without requiring database infrastructure.

## Configuration

### Basic Configuration

Create a `config.yaml` with your settings:

```yaml
knowledge:
  root: "./documents"

search:
  context_lines: 5        # Lines of context around matches
  max_results: 50         # Maximum results per search
  timeout: 30             # Search timeout in seconds

security:
  enable_shell_filters: true
  filter_mode: whitelist  # Recommended for production

exclude:
  patterns:
    - ".git/*"
    - "*.draft.*"
    - "*.tmp"
```

See [config.example.yaml](config.example.yaml) for all available options.

### Environment Variables

All configuration options can be overridden using environment variables with the `FMCP_` prefix:

```bash
export FMCP_KNOWLEDGE__ROOT=/path/to/documents
export FMCP_SEARCH__MAX_RESULTS=100
export FMCP_SECURITY__FILTER_MODE=whitelist
```

Use double underscores (`__`) to denote nested configuration levels.

## API

### Tools

The server implements six MCP tools organized into three categories:

#### Browse Operations
- **`list_collections`** - List folders and documents in a collection
- **`find_document`** - Find documents by name or path pattern

#### Search Operations
- **`search_documents`** - Full-text search with boolean operators
- **`search_multiple`** - Execute multiple searches in parallel

#### Read Operations
- **`read_document`** - Read document content with optional page selection
- **`get_document_info`** - Get document metadata and table of contents

### list_collections

Browse the hierarchical structure of your knowledge base.

**Arguments:**
- `path` (string, optional): Collection path relative to root. Defaults to root level.

**Returns:**
- List of subcollections (folders)
- List of documents with their paths and formats

**Example:**
```json
{
  "path": "programming/python"
}
```

### find_document

Locate documents by filename or path pattern using fuzzy matching.

**Arguments:**
- `query` (string, required): Search term for document names
- `limit` (number, optional): Maximum results to return (default: 20)

**Returns:**
- List of matching documents with paths and relevance scores

**Example:**
```json
{
  "query": "async patterns",
  "limit": 10
}
```

### search_documents

Execute full-text searches across your knowledge base with powerful boolean operators.

**Arguments:**
- `query` (string, required): Search query with optional operators
- `scope` (object, required): Defines search boundaries
  - `type` (string): One of `"global"`, `"collection"`, or `"document"`
  - `path` (string, conditional): Required for `collection` and `document` scopes

**Search Operators:**
- `term1 term2` - AND: Find documents containing both terms
- `term1|term2` - OR: Find documents containing either term
- `term1 -term2` - NOT: Exclude documents with term2
- `"exact phrase"` - Match exact phrase with quotes

**Returns:**
- List of matches with document path, line numbers, and context
- Truncation indicator if results exceed maximum

**Examples:**

Global search:
```json
{
  "query": "authentication jwt",
  "scope": {
    "type": "global"
  }
}
```

Collection-scoped search:
```json
{
  "query": "async|await -deprecated",
  "scope": {
    "type": "collection",
    "path": "programming/python"
  }
}
```

Document-specific search:
```json
{
  "query": "\"error handling\"",
  "scope": {
    "type": "document",
    "path": "guides/best-practices.md"
  }
}
```

### search_multiple

Execute multiple search queries concurrently for improved performance.

**Arguments:**
- `queries` (array of strings, required): List of search queries
- `scope` (object, required): Same scope structure as `search_documents`

**Returns:**
- Object mapping each query to its search results
- Each result includes matches and truncation status

**Example:**
```json
{
  "queries": ["authentication", "authorization", "session management"],
  "scope": {
    "type": "collection",
    "path": "security/docs"
  }
}
```

**Note:** Concurrent searches are limited by the `limits.max_concurrent_searches` configuration setting.

### read_document

Read the complete contents of a document with optional page selection for PDFs.

**Arguments:**
- `path` (string, required): Document path relative to knowledge root
- `pages` (array of numbers, optional): Specific pages to read (PDF only)

**Returns:**
- Document content as text
- Format metadata

**Examples:**

Read entire document:
```json
{
  "path": "guides/user-manual.pdf"
}
```

Read specific pages:
```json
{
  "path": "guides/user-manual.pdf",
  "pages": [1, 5, 10]
}
```

**Note:** Content length is limited by the `limits.max_read_chars` configuration setting.

### get_document_info

Retrieve metadata and structural information about a document.

**Arguments:**
- `path` (string, required): Document path relative to knowledge root

**Returns:**
- File size and format
- Page count (for PDFs)
- Table of contents with page numbers (when available)
- Last modified timestamp

**Example:**
```json
{
  "path": "reference/api-documentation.pdf"
}
```

## Usage with Claude Desktop

### Using Command-Line Arguments

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "fathom-mcp": {
      "command": "fathom-mcp",
      "args": ["--root", "/path/to/your/documents"]
    }
  }
}
```

### Using Configuration File

For more complex setups, use a configuration file:

```json
{
  "mcpServers": {
    "fathom-mcp": {
      "command": "fathom-mcp",
      "args": ["--config", "/path/to/config.yaml"]
    }
  }
}
```

### Using uv (Development)

When developing or running from source:

```json
{
  "mcpServers": {
    "fathom-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/fathom-mcp",
        "run",
        "fathom-mcp",
        "--root",
        "/path/to/documents"
      ]
    }
  }
}
```

### Configuration File Location

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

**Important:** Restart Claude Desktop after modifying the configuration file.

## HTTP Transport Support

Fathom MCP supports two transport protocols for different deployment scenarios:

### 1. Stdio Transport (Default)

For Claude Desktop integration - the server communicates over standard input/output:

```json
{
  "mcpServers": {
    "fathom-mcp": {
      "command": "fathom-mcp",
      "args": ["--root", "/path/to/your/documents"]
    }
  }
}
```

**Docker (optional):**
```bash
# Run stdio transport in Docker
docker compose --profile stdio up
```

### 2. HTTP Transport (Docker)

For remote deployment and web clients - the server runs as an HTTP service.

#### Streamable HTTP:

```bash
# Start server
docker compose --profile http up fathom-mcp-http

# Test connectivity
fathom-mcp-test -t streamable-http -u http://localhost:8765/mcp -l basic
```

### Configuration

HTTP transport configured via environment variables or config file:

**Environment variables:**
```bash
export FMCP_TRANSPORT__TYPE=streamable-http
export FMCP_TRANSPORT__HOST=0.0.0.0
export FMCP_TRANSPORT__PORT=8765
export FMCP_TRANSPORT__ENABLE_CORS=true
export FMCP_TRANSPORT__ALLOWED_ORIGINS='["https://app.example.com"]'
```

**Configuration file:**
```yaml
transport:
  type: "streamable-http"
  host: "0.0.0.0"
  port: 8765
  enable_cors: true
  allowed_origins:
    - "https://app.example.com"
  structured_logging: true
```

### Security

⚠️ **IMPORTANT: No Built-In Authentication**

**Fathom MCP does NOT include authentication for HTTP transport.** This is intentional - authentication should be handled by dedicated tools.

**For HTTP deployments:**
- ✅ **Use reverse proxy** (Nginx, Caddy, Traefik) with authentication
- ✅ **Use VPN** (Tailscale, WireGuard) for network isolation
- ✅ **Use HTTPS** in production (never HTTP)
- ❌ **Never expose** HTTP transport directly to the internet
- ❌ **Never use** wildcard CORS (`*`) in production

**For local use:** Use the default `stdio` transport - no network access, no authentication needed.

**See [docs/security.md](docs/security.md) for detailed security setup with examples for reverse proxy, VPN, and OAuth.**

### Testing

Test client available for all transports:

```bash
# Connectivity test
fathom-mcp-test -t streamable-http -u http://localhost:8765/mcp -l connectivity

# Basic test suite
fathom-mcp-test -t streamable-http -u http://localhost:8765/mcp -l basic

# Full test suite with verbose output
fathom-mcp-test -t streamable-http -u http://localhost:8765/mcp -l full -v
```

**Exit codes:**
- 0: All tests passed
- 1: Some tests failed
- 2: Fatal error (cannot connect)
- 3: Configuration error
- 4: Timeout error
- 6: Partial success (connectivity OK, tools failed)

## Docker Deployment

### Using docker-compose (Recommended)

```bash
# Start the server
docker-compose up

# Build and start
docker-compose up --build

# Run in detached mode
docker-compose up -d
```

The included `docker-compose.yaml` provides:
- Read-only document mounting for security
- Resource limits (512MB memory, 1 CPU)
- Proper stdio configuration for MCP protocol

### Manual Docker Build

```bash
# Build image
docker build -t fathom-mcp .

# Run with read-only mount
docker run -v /path/to/docs:/knowledge:ro fathom-mcp

# Run with custom configuration
docker run \
  -v /path/to/docs:/knowledge:ro \
  -v /path/to/config.yaml:/config/config.yaml:ro \
  fathom-mcp
```

## Cloud Storage Integration

The File Knowledge server operates on **local documents only**. Cloud synchronization is intentionally handled outside the MCP server for security and architectural clarity.

### Recommended Approaches

**Option 1: Cloud Desktop Clients**
- Google Drive Desktop, Dropbox, OneDrive, iCloud Drive
- Automatic background sync to local folder
- Point server to synced directory

**Option 2: rclone mount**
```bash
# Mount cloud storage as read-only local directory
rclone mount gdrive:Knowledge /data/knowledge --read-only --vfs-cache-mode full --daemon
```

**Option 3: Scheduled sync**
```bash
# Periodic sync via cron
*/30 * * * * rclone sync gdrive:Knowledge /data/knowledge
```

See [`docs/cloud-sync-guide.md`](docs/cloud-sync-guide.md) for detailed setup instructions.


## Development

### Project Setup

```bash
# Clone repository
git clone https://github.com/RomanShnurov/fathom-mcp
cd fathom-mcp

# Install with development dependencies (recommended)
uv sync --extra dev

# Alternative: pip
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov

# Run specific test file
uv run pytest tests/test_search.py

# Run with verbose output
uv run pytest -v
```

### Code Quality Tools

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Auto-fix linting issues
uv run ruff check . --fix

# Type checking
uv run mypy src
```

## Security

The File Knowledge server implements defense-in-depth security.

### Transport Security

⚠️ **HTTP Transport Security:** When using HTTP transport (`streamable-http`), the server does NOT include built-in authentication. This is intentional - use external tools:

- **Reverse proxy** (Nginx, Caddy, Traefik) with basic auth or OAuth
- **VPN** (Tailscale, WireGuard) for network isolation
- **localhost only** (`host: 127.0.0.1`) for same-machine access
- **stdio transport** (default) for local AI agents like Claude Desktop

**📖 See [docs/security.md](docs/security.md) for complete setup guides with configuration examples.**

### Path Security
- **Path validation**: All file paths validated against knowledge root
- **Traversal prevention**: Blocks `../` and absolute path attacks
- **Symlink policy**: Configurable symlink following (default: disabled)

### Command Security
- **Whitelist enforcement**: Filter commands validated before execution
- **Sandboxed execution**: Shell commands run with timeout limits
- **Read-only design**: Server never modifies document collection
- **No credential access**: Server never touches cloud storage APIs

### Configuration
```yaml
security:
  enable_shell_filters: true
  filter_mode: whitelist          # Recommended for production
  allowed_filter_commands:
    - "pdftotext % -"
  symlink_policy: disallow        # Prevent symlink attacks
```

**For production HTTP deployments, always use reverse proxy or VPN. See [docs/security.md](docs/security.md).**

## Debugging

Since MCP servers run over stdio, debugging can be challenging. Fathom MCP provides two options for interactive testing.

### Built-in MCP Inspector (Recommended)

Fathom MCP includes a Streamlit-based inspector UI for testing server tools, resources, and prompts:

```bash
# Install inspector dependencies
uv sync --extra inspector

# Run the inspector
streamlit run inspector/app.py
```

The built-in Inspector provides:
- Interactive tool testing with dynamic forms
- Resource browsing and content reading
- Prompt listing and inspection
- Real-time server logs with filtering
- No external dependencies (Node.js not required)

### External MCP Inspector

Alternatively, use the official [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector fathom-mcp --root /path/to/documents
```

You can also use it with configuration files:

```bash
npx @modelcontextprotocol/inspector fathom-mcp --config config.yaml
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run code quality checks (`ruff format`, `ruff check`, `mypy`)
5. Submit a pull request

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for detailed guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Resources

### Documentation
- [Security Guide](docs/security.md) - Reverse proxy, VPN, and OAuth setup
- [Supported Formats](docs/supported-formats.md) - Document format configuration
- [Cloud Sync Guide](docs/cloud-sync-guide.md) - Cloud storage integration
- [Integration Guide](docs/integration.md) - Client setup and deployment
- [Configuration Reference](docs/configuration.md) - All configuration options
- [Tools Reference](docs/tools.md) - Complete MCP tools documentation

### External Resources
- [Model Context Protocol](https://modelcontextprotocol.io/) - Official MCP documentation
- [MCP Specification](https://spec.modelcontextprotocol.io/) - Protocol specification
- [ugrep](https://github.com/Genivia/ugrep) - Ultra-fast grep with boolean search
- [poppler-utils](https://poppler.freedesktop.org/) - PDF rendering utilities
