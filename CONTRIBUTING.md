# Contributing to contextfs

Thank you for your interest in contributing to contextfs! This document provides guidelines and instructions for contributing.

## Code of Conduct

This project follows a standard code of conduct. Please be respectful and professional in all interactions.

## Getting Started

### Prerequisites

- Python 3.12 or higher
- uv (recommended) or pip
- ugrep (system dependency)
- poppler-utils (system dependency)
- Git

### Development Setup

1. **Fork and clone the repository:**

```bash
git clone https://github.com/yourusername/contextfs.git
cd contextfs
```

2. **Install system dependencies:**

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y ugrep poppler-utils
```

**macOS:**
```bash
brew install ugrep poppler
```

**Windows:**
- Install ugrep from [releases](https://github.com/Genivia/ugrep/releases)
- Install poppler from [releases](https://github.com/oschwartz10612/poppler-windows/releases)

3. **Install Python dependencies:**

```bash
# Using uv (recommended)
uv sync --extra dev

# Or using pip
pip install -e ".[dev]"
```

4. **Verify installation:**

```bash
# Run tests
uv run pytest

# Check code quality
uv run ruff check src tests
uv run mypy src
```

## Development Workflow

### Project Structure

```
contextfs/
├── src/file_knowledge_mcp/     # Main package
│   ├── __init__.py
│   ├── __main__.py             # CLI entry point
│   ├── config.py               # Configuration system
│   ├── errors.py               # Error definitions
│   ├── security.py             # Security controls
│   ├── server.py               # MCP server
│   ├── tools/                  # MCP tools
│   │   ├── __init__.py
│   │   ├── browse.py           # list_collections, find_document
│   │   ├── search.py           # search_documents, search_multiple
│   │   └── read.py             # read_document, get_document_info
│   └── search/                 # Search engine
│       ├── __init__.py
│       └── ugrep.py            # ugrep wrapper
├── tests/                      # Test suite
│   ├── conftest.py             # Pytest fixtures
│   ├── test_config.py
│   ├── test_browse.py
│   ├── test_search.py
│   └── test_read.py
├── docs/                       # Documentation
├── specs/                      # Design specs
├── pyproject.toml              # Project config
├── config.example.yaml         # Example config
└── README.md
```

### Making Changes

1. **Create a feature branch:**

```bash
git checkout -b feature/your-feature-name
```

2. **Make your changes:**
   - Write clear, documented code
   - Follow existing code style
   - Add tests for new features
   - Update documentation as needed

3. **Test your changes:**

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_search.py

# Run with coverage
uv run pytest --cov

# Run specific test
uv run pytest tests/test_search.py::test_search_simple_query
```

4. **Check code quality:**

```bash
# Lint code
uv run ruff check src tests

# Auto-fix issues
uv run ruff check src tests --fix

# Format code
uv run ruff format src tests

# Type check
uv run mypy src
```

5. **Commit your changes:**

```bash
git add .
git commit -m "feat: add new feature"
```

Use conventional commit messages:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test changes
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `chore:` - Maintenance tasks

6. **Push and create a pull request:**

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Code Style

### Python Style

- Follow PEP 8
- Use type hints for all functions
- Maximum line length: 100 characters
- Use descriptive variable names
- Add docstrings to all public functions

### Example:

```python
from typing import List, Optional

async def search_documents(
    query: str,
    scope: SearchScope,
    max_results: int = 50,
    fuzzy: bool = False
) -> SearchResult:
    """
    Search for documents matching the query.

    Args:
        query: Search query with boolean operators
        scope: Search scope (global, collection, or document)
        max_results: Maximum number of results to return
        fuzzy: Enable fuzzy matching

    Returns:
        SearchResult with matches and metadata

    Raises:
        SearchError: If search fails
        TimeoutError: If search exceeds timeout
    """
    # Implementation here
    pass
```

### Ruff Configuration

The project uses ruff for linting and formatting. Configuration in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
ignore = ["E501"]
```

### Type Checking

The project uses mypy in strict mode:

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_ignores = true
```

## Testing

### Writing Tests

- Use pytest for all tests
- One test file per module
- Use descriptive test names
- Use fixtures from `conftest.py`
- Aim for >80% code coverage

### Test Structure

```python
import pytest
from file_knowledge_mcp.tools.search import search_documents

async def test_search_simple_query(config):
    """Test simple search query."""
    result = await search_documents(
        query="test",
        scope={"type": "global"},
        config=config
    )

    assert result.total_matches > 0
    assert len(result.matches) > 0

async def test_search_with_and_operator(config):
    """Test search with AND operator."""
    result = await search_documents(
        query="term1 term2",
        scope={"type": "global"},
        config=config
    )

    # Verify both terms appear in results
    for match in result.matches:
        assert "term1" in match.text.lower()
        assert "term2" in match.text.lower()
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test
uv run pytest tests/test_search.py::test_search_simple_query

# Run with coverage report
uv run pytest --cov --cov-report=html

# List all available tests
uv run pytest --co -q
```

### Test Coverage

Aim for at least 80% code coverage:

```bash
uv run pytest --cov --cov-report=term-missing
```

## Adding New Features

### Adding a New Tool

1. **Create tool handler in `src/file_knowledge_mcp/tools/`**

```python
from mcp.server import Server
from pydantic import BaseModel
from ..config import Config
from ..errors import McpError

class MyToolInput(BaseModel):
    """Input schema for my_tool."""
    param1: str
    param2: int = 10

def register_my_tools(server: Server, config: Config) -> None:
    """Register my custom tools."""

    @server.call_tool(
        "my_tool",
        "Description of what my_tool does",
        MyToolInput.model_json_schema()
    )
    async def my_tool(arguments: dict) -> dict:
        """Tool implementation."""
        args = MyToolInput(**arguments)

        # Validate paths if needed
        # Use FileAccessControl.validate_path()

        # Implementation
        result = do_something(args.param1, args.param2)

        return {
            "success": True,
            "result": result
        }
```

2. **Register tool in `src/file_knowledge_mcp/server.py`**

```python
from .tools.my_tools import register_my_tools

def register_all_tools(server: Server, config: Config) -> None:
    """Register all tools."""
    register_browse_tools(server, config)
    register_search_tools(server, config)
    register_read_tools(server, config)
    register_my_tools(server, config)  # Add this
```

3. **Add tests in `tests/test_my_tools.py`**

```python
import pytest

async def test_my_tool_basic(server, config):
    """Test basic my_tool functionality."""
    result = await server.call_tool(
        "my_tool",
        {"param1": "test", "param2": 20}
    )

    assert result["success"] is True
    assert "result" in result
```

4. **Update documentation:**
   - Add to `docs/tools.md`
   - Update README.md tools table
   - Update `specs/api-reference.md`

### Adding a New Document Format

1. **Add format to config defaults in `src/file_knowledge_mcp/config.py`**

```python
class Config(BaseSettings):
    formats: dict[str, FormatConfig] = {
        # Existing formats...
        "epub": FormatConfig(
            enabled=True,
            filter="pandoc -f epub -t plain",
            extensions=[".epub"]
        ),
    }
```

2. **Add filter command to security whitelist**

```python
class SecurityConfig(BaseModel):
    allowed_filter_commands: list[str] = [
        "pdftotext - -",
        "pandoc -f docx -t plain",
        "pandoc -f epub -t plain",  # Add this
    ]
```

3. **Add tests**

4. **Update documentation**

## Security Guidelines

### Path Validation

Always validate paths before file operations:

```python
from .security import FileAccessControl

access_control = FileAccessControl(knowledge_root)

# Validate path
validated_path = access_control.validate_path(user_provided_path)

# Now safe to use
with open(validated_path, 'r') as f:
    content = f.read()
```

### Filter Commands

Validate filter commands before execution:

```python
from .security import FilterSecurity

filter_security = FilterSecurity(config.security)

# Validate command
filter_security.validate_filter_command("pdftotext - -")

# Run securely
result = await filter_security.run_secure_filter(
    command="pdftotext - -",
    input_data=pdf_bytes,
    timeout=30
)
```

### Security Best Practices

- Never execute user-provided commands without validation
- Always use whitelist mode for filter commands
- Validate all file paths against knowledge root
- Use read-only operations only (no writes)
- Set appropriate timeouts for all operations
- Log security-related events
- Handle errors securely (don't leak paths in error messages)

## Documentation

### What to Document

- All public APIs (functions, classes)
- Configuration options
- Error codes
- Usage examples
- Integration guides

### Documentation Style

Use Google-style docstrings:

```python
def search_documents(query: str, scope: SearchScope) -> SearchResult:
    """
    Search for documents matching the query.

    This function performs a full-text search across documents using
    the configured search engine (ugrep by default).

    Args:
        query: Search query with boolean operators (AND, OR, NOT).
            Examples: "term1 term2" (AND), "term1|term2" (OR)
        scope: Search scope defining where to search (global,
            collection, or document)

    Returns:
        SearchResult containing matches, total count, and metadata

    Raises:
        SearchError: If search fails or query is malformed
        TimeoutError: If search exceeds configured timeout
        SecurityError: If scope path is invalid

    Examples:
        >>> result = search_documents("async", {"type": "global"})
        >>> print(f"Found {result.total_matches} matches")

        >>> result = search_documents(
        ...     "jwt token",
        ...     {"type": "collection", "path": "docs/api"}
        ... )
    """
```

## Pull Request Process

1. **Before submitting:**
   - All tests pass
   - Code is formatted (ruff)
   - No linting errors
   - Type checking passes (mypy)
   - Documentation updated
   - CHANGELOG.md updated (if applicable)

2. **PR description should include:**
   - What the PR does
   - Why the change is needed
   - How to test it
   - Screenshots (if UI changes)
   - Related issues

3. **PR review process:**
   - At least one maintainer approval required
   - All CI checks must pass
   - No unresolved comments
   - Up-to-date with main branch

4. **After approval:**
   - Squash commits if needed
   - Update commit message
   - Maintainer will merge

## Release Process

Releases are automated via GitHub Actions:

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Commit changes
4. Create and push tag: `git tag v0.1.0 && git push origin v0.1.0`
5. GitHub Actions will:
   - Run tests
   - Build package
   - Publish to PyPI
   - Build and push Docker image

## Getting Help

- Open an issue for bugs or feature requests
- Check existing issues and documentation first
- Be specific and provide examples
- Include error messages and logs

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Recognition

Contributors will be recognized in:
- GitHub contributors page
- Release notes
- CHANGELOG.md (for significant contributions)

Thank you for contributing to contextfs!
