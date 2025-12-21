# Phase 1: Foundation (MVP)

## Goal

Создать минимально работающий MCP сервер, который можно подключить к Claude Desktop и искать по локальным документам.

## Prerequisites

- Python 3.12+
- ugrep installed (`apt install ugrep` / `brew install ugrep`)
- poppler-utils for PDF (`apt install poppler-utils` / `brew install poppler`)

## Project Structure

```
file-knowledge-mcp/
├── pyproject.toml
├── README.md
├── config.example.yaml
│
├── src/
│   └── file_knowledge_mcp/
│       ├── __init__.py
│       ├── __main__.py          # Entry point
│       ├── server.py            # MCP server setup
│       ├── config.py            # Pydantic settings
│       ├── errors.py            # Error hierarchy
│       │
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── browse.py        # list_collections, find_document
│       │   ├── search.py        # search_documents
│       │   └── read.py          # read_document
│       │
│       └── search/
│           ├── __init__.py
│           └── ugrep.py         # Ugrep wrapper
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_config.py
    ├── test_browse.py
    ├── test_search.py
    └── fixtures/
        └── sample_docs/
            ├── test.pdf
            └── test.md
```

---

## Task 1.1: Project Setup

### pyproject.toml

```toml
[project]
name = "file-knowledge-mcp"
version = "0.1.0"
description = "File-first knowledge base MCP server"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.12"
authors = [
    { name = "Your Name", email = "your@email.com" }
]
keywords = ["mcp", "knowledge-base", "search", "pdf", "ai"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
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
    "ruff>=0.1.0",
]

[project.scripts]
file-knowledge-mcp = "file_knowledge_mcp.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### Checklist

- [ ] Create project directory
- [ ] Initialize with `uv init` or manually create pyproject.toml
- [ ] Create src/file_knowledge_mcp/ structure
- [ ] Create tests/ structure
- [ ] Add .gitignore
- [ ] Install dependencies: `uv sync`

---

## Task 1.2: Configuration

### src/file_knowledge_mcp/config.py

```python
"""Configuration management with Pydantic."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class FormatConfig(BaseModel):
    """Document format configuration."""

    enabled: bool = True
    filter: str | None = None  # None = read directly, str = shell command
    extensions: list[str]


class SearchConfig(BaseModel):
    """Search engine settings."""

    engine: Literal["ugrep"] = "ugrep"
    context_lines: int = Field(default=5, ge=0, le=50)
    max_results: int = Field(default=50, ge=1, le=500)
    max_file_size_mb: int = Field(default=100, ge=1)
    timeout_seconds: int = Field(default=30, ge=5, le=300)


class ExcludeConfig(BaseModel):
    """File exclusion settings."""

    patterns: list[str] = Field(default_factory=lambda: [
        ".git/*",
        "__pycache__/*",
        "*.draft.*",
        "_archive/*",
    ])
    hidden_files: bool = True


class LimitsConfig(BaseModel):
    """Performance limits."""

    max_concurrent_searches: int = Field(default=4, ge=1, le=16)
    max_document_read_chars: int = Field(default=100_000, ge=1000)


class ServerConfig(BaseModel):
    """Server metadata."""

    name: str = "file-knowledge-mcp"
    version: str = "0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


class KnowledgeConfig(BaseModel):
    """Knowledge base root configuration."""

    root: Path

    @field_validator("root")
    @classmethod
    def validate_root_exists(cls, v: Path) -> Path:
        path = Path(v).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"Knowledge root does not exist: {path}")
        if not path.is_dir():
            raise ValueError(f"Knowledge root is not a directory: {path}")
        return path


class Config(BaseSettings):
    """Main configuration."""

    model_config = SettingsConfigDict(
        env_prefix="FKM_",
        env_nested_delimiter="__",
    )

    knowledge: KnowledgeConfig
    server: ServerConfig = Field(default_factory=ServerConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    exclude: ExcludeConfig = Field(default_factory=ExcludeConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    formats: dict[str, FormatConfig] = Field(default_factory=lambda: {
        "pdf": FormatConfig(
            extensions=[".pdf"],
            filter="pdftotext - -",
        ),
        "markdown": FormatConfig(
            extensions=[".md", ".markdown"],
            filter=None,
        ),
        "text": FormatConfig(
            extensions=[".txt", ".rst"],
            filter=None,
        ),
    })

    @property
    def supported_extensions(self) -> set[str]:
        """Get all enabled file extensions."""
        exts = set()
        for fmt in self.formats.values():
            if fmt.enabled:
                exts.update(fmt.extensions)
        return exts

    def get_filter_for_extension(self, ext: str) -> str | None:
        """Get filter command for file extension."""
        for fmt in self.formats.values():
            if fmt.enabled and ext.lower() in fmt.extensions:
                return fmt.filter
        return None


class ConfigError(Exception):
    """Configuration loading error."""
    pass


def load_config(config_path: str | Path | None = None) -> Config:
    """Load configuration from YAML file or defaults.

    Args:
        config_path: Path to config.yaml. If None, tries ./config.yaml

    Returns:
        Validated Config instance

    Raises:
        ConfigError: If configuration is invalid
    """
    config_data: dict = {}

    if config_path:
        path = Path(config_path)
        if not path.exists():
            raise ConfigError(f"Config file not found: {path}")
        config_data = yaml.safe_load(path.read_text()) or {}
    else:
        # Try default locations
        for default in [Path("./config.yaml"), Path("./config.yml")]:
            if default.exists():
                config_data = yaml.safe_load(default.read_text()) or {}
                break

    try:
        return Config(**config_data)
    except Exception as e:
        raise ConfigError(f"Invalid configuration: {e}") from e
```

### config.example.yaml

```yaml
# file-knowledge-mcp configuration

# Required: path to documents
knowledge:
  root: "./documents"

# Optional: server settings
server:
  name: "file-knowledge-mcp"
  log_level: "INFO"  # DEBUG | INFO | WARNING | ERROR

# Optional: search settings
search:
  context_lines: 5
  max_results: 50
  timeout_seconds: 30

# Optional: exclude patterns
exclude:
  patterns:
    - ".git/*"
    - "__pycache__/*"
    - "*.draft.*"
  hidden_files: true

# Optional: format settings
formats:
  pdf:
    enabled: true
    filter: "pdftotext - -"
    extensions: [".pdf"]
  markdown:
    enabled: true
    filter: null
    extensions: [".md", ".markdown"]
  text:
    enabled: true
    filter: null
    extensions: [".txt", ".rst"]

# Optional: limits
limits:
  max_concurrent_searches: 4
  max_document_read_chars: 100000
```

### Checklist

- [ ] Create config.py with all models
- [ ] Create config.example.yaml
- [ ] Write tests for config loading
- [ ] Test environment variable override (FKM_KNOWLEDGE__ROOT)

---

## Task 1.3: Error Handling

### src/file_knowledge_mcp/errors.py

```python
"""Error definitions for MCP server."""

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """Error codes following JSON-RPC conventions."""

    # JSON-RPC standard errors
    INVALID_PARAMS = "-32602"
    INTERNAL_ERROR = "-32603"

    # Knowledge base errors (1xxx)
    PATH_NOT_FOUND = "1001"
    DOCUMENT_NOT_FOUND = "1002"
    COLLECTION_NOT_FOUND = "1003"
    FORMAT_NOT_SUPPORTED = "1004"

    # Search errors (2xxx)
    SEARCH_TIMEOUT = "2001"
    SEARCH_ENGINE_ERROR = "2002"
    INVALID_QUERY = "2003"

    # Limit errors (4xxx)
    FILE_TOO_LARGE = "4001"
    RESULT_TRUNCATED = "4002"


class McpError(Exception):
    """Base error with MCP-compatible response."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        data: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.data = data or {}
        super().__init__(message)

    def to_response(self) -> dict[str, Any]:
        """Convert to MCP error response format."""
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "data": self.data,
            }
        }


# Convenience factory functions
def path_not_found(path: str) -> McpError:
    return McpError(
        code=ErrorCode.PATH_NOT_FOUND,
        message=f"Path not found: {path}",
        data={"path": path},
    )


def document_not_found(path: str, suggestions: list[str] | None = None) -> McpError:
    return McpError(
        code=ErrorCode.DOCUMENT_NOT_FOUND,
        message=f"Document not found: {path}",
        data={"path": path, "suggestions": suggestions or []},
    )


def search_timeout(query: str, timeout_sec: int) -> McpError:
    return McpError(
        code=ErrorCode.SEARCH_TIMEOUT,
        message=f"Search timed out after {timeout_sec}s",
        data={"query": query, "timeout_seconds": timeout_sec},
    )


def search_engine_error(message: str, details: str | None = None) -> McpError:
    return McpError(
        code=ErrorCode.SEARCH_ENGINE_ERROR,
        message=f"Search engine error: {message}",
        data={"details": details} if details else {},
    )


def file_too_large(path: str, size_mb: float, max_mb: int) -> McpError:
    return McpError(
        code=ErrorCode.FILE_TOO_LARGE,
        message=f"File too large: {size_mb:.1f}MB (max: {max_mb}MB)",
        data={"path": path, "size_mb": size_mb, "max_mb": max_mb},
    )
```

### Checklist

- [ ] Create errors.py
- [ ] Test error serialization
- [ ] Add logging for errors

---

## Task 1.4: Search Engine (ugrep wrapper)

### src/file_knowledge_mcp/search/ugrep.py

```python
"""Ugrep search engine wrapper."""

import asyncio
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import Config
from ..errors import search_timeout, search_engine_error

logger = logging.getLogger(__name__)


@dataclass
class SearchMatch:
    """Single search match."""

    file: str
    line_number: int
    text: str
    context_before: list[str]
    context_after: list[str]


@dataclass
class SearchResult:
    """Search operation result."""

    matches: list[SearchMatch]
    total_matches: int
    truncated: bool
    query: str
    searched_path: str


class UgrepEngine:
    """Ugrep-based search engine."""

    def __init__(self, config: Config):
        self.config = config
        self._semaphore = asyncio.Semaphore(config.limits.max_concurrent_searches)

    async def search(
        self,
        query: str,
        path: Path,
        recursive: bool = True,
        context_lines: int | None = None,
        max_results: int | None = None,
        fuzzy: bool = False,
    ) -> SearchResult:
        """Execute search using ugrep.

        Args:
            query: Boolean search query (space=AND, |=OR, -=NOT)
            path: File or directory to search
            recursive: Search subdirectories
            context_lines: Lines of context (default from config)
            max_results: Max matches (default from config)
            fuzzy: Enable fuzzy matching

        Returns:
            SearchResult with matches

        Raises:
            McpError: On timeout or engine error
        """
        context = context_lines or self.config.search.context_lines
        max_res = max_results or self.config.search.max_results

        # Build command
        cmd = self._build_command(query, path, recursive, context, fuzzy)
        logger.debug(f"Executing: {' '.join(cmd)}")

        async with self._semaphore:
            try:
                result = await asyncio.wait_for(
                    self._run_ugrep(cmd),
                    timeout=self.config.search.timeout_seconds,
                )
            except asyncio.TimeoutError:
                raise search_timeout(query, self.config.search.timeout_seconds)

        matches = self._parse_output(result.stdout, path)
        truncated = len(matches) > max_res

        return SearchResult(
            matches=matches[:max_res],
            total_matches=len(matches),
            truncated=truncated,
            query=query,
            searched_path=str(path),
        )

    def _build_command(
        self,
        query: str,
        path: Path,
        recursive: bool,
        context_lines: int,
        fuzzy: bool,
    ) -> list[str]:
        """Build ugrep command."""
        cmd = [
            "ugrep",
            "-%",  # Boolean query mode
            "-i",  # Case insensitive
            f"-C{context_lines}",
            "--line-number",
        ]

        if fuzzy:
            cmd.append("-Z")

        if recursive and path.is_dir():
            cmd.append("-r")
            # Add filters for supported formats
            for ext in self.config.supported_extensions:
                cmd.extend(["--include", f"*{ext}"])
            # PDF filter
            if ".pdf" in self.config.supported_extensions:
                pdf_filter = self.config.get_filter_for_extension(".pdf")
                if pdf_filter:
                    cmd.append(f"--filter=pdf:{pdf_filter}")
        elif path.is_file() and path.suffix.lower() == ".pdf":
            pdf_filter = self.config.get_filter_for_extension(".pdf")
            if pdf_filter:
                cmd.append(f"--filter=pdf:{pdf_filter}")

        cmd.append(query)
        cmd.append(str(path))

        return cmd

    async def _run_ugrep(self, cmd: list[str]) -> subprocess.CompletedProcess:
        """Run ugrep in thread pool."""
        return await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
        )

    def _parse_output(self, stdout: str, base_path: Path) -> list[SearchMatch]:
        """Parse ugrep output into SearchMatch objects."""
        if not stdout.strip():
            return []

        matches = []
        current_match = None
        context_before = []

        for line in stdout.split("\n"):
            if not line:
                if current_match:
                    matches.append(current_match)
                    current_match = None
                    context_before = []
                continue

            # Parse line format: filename:line_number:text
            # or filename-line_number-text for context
            if ":" in line:
                parts = line.split(":", 2)
                if len(parts) >= 3 and parts[1].isdigit():
                    if current_match:
                        matches.append(current_match)

                    file_path = parts[0]
                    # Make relative to base
                    try:
                        rel_path = Path(file_path).relative_to(base_path)
                        file_path = str(rel_path)
                    except ValueError:
                        pass

                    current_match = SearchMatch(
                        file=file_path,
                        line_number=int(parts[1]),
                        text=parts[2],
                        context_before=context_before.copy(),
                        context_after=[],
                    )
                    context_before = []
                elif current_match:
                    current_match.context_after.append(line)
                else:
                    context_before.append(line)

        if current_match:
            matches.append(current_match)

        return matches


def check_ugrep_installed() -> bool:
    """Check if ugrep is available."""
    try:
        result = subprocess.run(
            ["ugrep", "--version"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
```

### Checklist

- [ ] Create search/ugrep.py
- [ ] Test with sample PDF
- [ ] Test with sample markdown
- [ ] Test Boolean queries (AND, OR, NOT)
- [ ] Test fuzzy search
- [ ] Test timeout handling
- [ ] Test concurrent search limiting

---

## Task 1.5: Tools Implementation

### src/file_knowledge_mcp/tools/__init__.py

```python
"""MCP Tools registration."""

from mcp.server import Server

from ..config import Config
from .browse import register_browse_tools
from .search import register_search_tools
from .read import register_read_tools


def register_all_tools(server: Server, config: Config) -> None:
    """Register all tools with the MCP server."""
    register_browse_tools(server, config)
    register_search_tools(server, config)
    register_read_tools(server, config)
```

### src/file_knowledge_mcp/tools/browse.py

```python
"""Browse tools: list_collections, find_document."""

import fnmatch
import logging
from datetime import datetime
from pathlib import Path

from mcp.server import Server
from mcp.types import Tool, TextContent

from ..config import Config
from ..errors import path_not_found

logger = logging.getLogger(__name__)


def register_browse_tools(server: Server, config: Config) -> None:
    """Register browse-related tools."""

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="list_collections",
                description="""List document collections (folders) at the specified path.
Use this to explore the knowledge base structure.
Call with empty path to see root collections.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path relative to knowledge root. Empty for root.",
                            "default": "",
                        },
                    },
                },
            ),
            Tool(
                name="find_document",
                description="""Find documents by name across all collections.
Useful when you know the document name but not its location.
Supports partial matching.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Document name or part of it",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "list_collections":
            result = await _list_collections(config, arguments.get("path", ""))
            return [TextContent(type="text", text=format_result(result))]

        elif name == "find_document":
            result = await _find_document(
                config,
                arguments["query"],
                arguments.get("limit", 10),
            )
            return [TextContent(type="text", text=format_result(result))]

        raise ValueError(f"Unknown tool: {name}")


async def _list_collections(config: Config, path: str) -> dict:
    """List collections at path."""
    root = config.knowledge.root
    target = root / path if path else root

    if not target.exists():
        raise path_not_found(path)

    if not target.is_dir():
        raise path_not_found(f"{path} is not a directory")

    collections = []
    documents = []

    for item in sorted(target.iterdir()):
        # Skip excluded
        if _should_exclude(item, config):
            continue

        if item.is_dir():
            doc_count = _count_documents(item, config)
            subcoll_count = sum(1 for x in item.iterdir() if x.is_dir())
            collections.append({
                "name": item.name,
                "path": str(item.relative_to(root)),
                "document_count": doc_count,
                "subcollection_count": subcoll_count,
            })
        elif item.suffix.lower() in config.supported_extensions:
            stat = item.stat()
            documents.append({
                "name": item.name,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

    return {
        "current_path": path,
        "collections": collections,
        "documents": documents,
    }


async def _find_document(config: Config, query: str, limit: int) -> dict:
    """Find documents matching query."""
    root = config.knowledge.root
    query_lower = query.lower()
    matches = []

    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in config.supported_extensions:
            continue
        if _should_exclude(file_path, config):
            continue

        name_lower = file_path.stem.lower()

        # Calculate relevance score
        if query_lower == name_lower:
            score = 1.0
        elif query_lower in name_lower:
            score = 0.8
        elif any(part in name_lower for part in query_lower.split()):
            score = 0.5
        else:
            continue

        rel_path = file_path.relative_to(root)
        matches.append({
            "name": file_path.name,
            "path": str(rel_path),
            "collection": str(rel_path.parent) if rel_path.parent != Path(".") else "",
            "size_bytes": file_path.stat().st_size,
            "score": score,
        })

    # Sort by score descending
    matches.sort(key=lambda x: x["score"], reverse=True)

    return {
        "matches": matches[:limit],
        "total_found": len(matches),
    }


def _should_exclude(path: Path, config: Config) -> bool:
    """Check if path should be excluded."""
    name = path.name

    # Hidden files
    if config.exclude.hidden_files and name.startswith("."):
        return True

    # Patterns
    rel_path = str(path)
    for pattern in config.exclude.patterns:
        if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(name, pattern):
            return True

    return False


def _count_documents(directory: Path, config: Config) -> int:
    """Count documents in directory (non-recursive)."""
    count = 0
    for item in directory.iterdir():
        if item.is_file() and item.suffix.lower() in config.supported_extensions:
            if not _should_exclude(item, config):
                count += 1
    return count


def format_result(result: dict) -> str:
    """Format result as readable string."""
    import json
    return json.dumps(result, indent=2, ensure_ascii=False)
```

### src/file_knowledge_mcp/tools/search.py

```python
"""Search tools: search_documents."""

import logging
from pathlib import Path

from mcp.server import Server
from mcp.types import Tool, TextContent

from ..config import Config
from ..errors import path_not_found, document_not_found
from ..search.ugrep import UgrepEngine

logger = logging.getLogger(__name__)


def register_search_tools(server: Server, config: Config) -> None:
    """Register search-related tools."""

    engine = UgrepEngine(config)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="search_documents",
                description="""Search for text inside documents using boolean patterns.

Query syntax:
- Space between words = AND: "attack armor" finds both terms
- Pipe | = OR: "move|teleport" finds either term
- Dash - = NOT: "attack -ranged" excludes "ranged"
- Quotes for exact phrase: '"end of turn"'

Scope controls where to search:
- "global": search everywhere
- "collection": search in specific collection (recursive)
- "document": search in specific document""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query with boolean operators",
                        },
                        "scope": {
                            "type": "object",
                            "description": "Where to search",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["global", "collection", "document"],
                                },
                                "path": {
                                    "type": "string",
                                    "description": "Path for collection/document scope",
                                },
                            },
                            "required": ["type"],
                        },
                        "context_lines": {
                            "type": "integer",
                            "description": "Lines of context around matches",
                            "default": 5,
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum matches to return",
                            "default": 20,
                        },
                        "fuzzy": {
                            "type": "boolean",
                            "description": "Enable fuzzy matching",
                            "default": False,
                        },
                    },
                    "required": ["query", "scope"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "search_documents":
            result = await _search_documents(config, engine, arguments)
            return [TextContent(type="text", text=format_result(result))]

        raise ValueError(f"Unknown tool: {name}")


async def _search_documents(config: Config, engine: UgrepEngine, args: dict) -> dict:
    """Execute document search."""
    query = args["query"]
    scope = args["scope"]
    scope_type = scope["type"]
    context_lines = args.get("context_lines", 5)
    max_results = args.get("max_results", 20)
    fuzzy = args.get("fuzzy", False)

    root = config.knowledge.root

    # Resolve path based on scope
    if scope_type == "global":
        search_path = root
        recursive = True
    elif scope_type == "collection":
        path = scope.get("path", "")
        search_path = root / path
        if not search_path.exists():
            raise path_not_found(path)
        recursive = True
    elif scope_type == "document":
        path = scope.get("path", "")
        search_path = root / path
        if not search_path.exists():
            raise document_not_found(path)
        recursive = False
    else:
        raise ValueError(f"Invalid scope type: {scope_type}")

    # Execute search
    result = await engine.search(
        query=query,
        path=search_path,
        recursive=recursive,
        context_lines=context_lines,
        max_results=max_results,
        fuzzy=fuzzy,
    )

    # Format for response
    matches = []
    for match in result.matches:
        matches.append({
            "document": match.file,
            "line": match.line_number,
            "text": match.text,
            "context_before": match.context_before,
            "context_after": match.context_after,
        })

    return {
        "matches": matches,
        "total_matches": result.total_matches,
        "truncated": result.truncated,
    }


def format_result(result: dict) -> str:
    import json
    return json.dumps(result, indent=2, ensure_ascii=False)
```

### src/file_knowledge_mcp/tools/read.py

```python
"""Read tools: read_document."""

import logging
from pathlib import Path

from mcp.server import Server
from mcp.types import Tool, TextContent
from pypdf import PdfReader

from ..config import Config
from ..errors import document_not_found, file_too_large

logger = logging.getLogger(__name__)


def register_read_tools(server: Server, config: Config) -> None:
    """Register read-related tools."""

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="read_document",
                description="""Read full document content or specific pages.
Use as fallback when search doesn't find what you need.
WARNING: Can return large amounts of text, prefer search when possible.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to document (relative to knowledge root)",
                        },
                        "pages": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Specific pages to read (1-indexed). Empty = all.",
                            "default": [],
                        },
                    },
                    "required": ["path"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "read_document":
            result = await _read_document(config, arguments)
            return [TextContent(type="text", text=format_result(result))]

        raise ValueError(f"Unknown tool: {name}")


async def _read_document(config: Config, args: dict) -> dict:
    """Read document content."""
    import asyncio

    path = args["path"]
    pages = args.get("pages", [])

    full_path = config.knowledge.root / path

    if not full_path.exists():
        raise document_not_found(path)

    # Check file size
    size_mb = full_path.stat().st_size / (1024 * 1024)
    max_mb = config.search.max_file_size_mb
    if size_mb > max_mb:
        raise file_too_large(path, size_mb, max_mb)

    # Read based on format
    ext = full_path.suffix.lower()

    if ext == ".pdf":
        content, total_pages, pages_read = await asyncio.to_thread(
            _read_pdf, full_path, pages
        )
    else:
        content = await asyncio.to_thread(full_path.read_text, encoding="utf-8")
        total_pages = 1
        pages_read = [1]

    # Truncate if needed
    max_chars = config.limits.max_document_read_chars
    truncated = len(content) > max_chars
    if truncated:
        content = content[:max_chars] + "\n...(truncated)"

    return {
        "content": content,
        "pages_read": pages_read,
        "total_pages": total_pages,
        "truncated": truncated,
    }


def _read_pdf(path: Path, pages: list[int]) -> tuple[str, int, list[int]]:
    """Read PDF content."""
    reader = PdfReader(path)
    total_pages = len(reader.pages)

    # Determine which pages to read
    if pages:
        # Convert to 0-indexed, filter valid
        page_indices = [p - 1 for p in pages if 0 < p <= total_pages]
    else:
        page_indices = list(range(total_pages))

    text_parts = []
    for idx in page_indices:
        page_num = idx + 1
        text_parts.append(f"--- Page {page_num} ---")
        text_parts.append(reader.pages[idx].extract_text() or "")

    return "\n".join(text_parts), total_pages, [i + 1 for i in page_indices]


def format_result(result: dict) -> str:
    import json
    return json.dumps(result, indent=2, ensure_ascii=False)
```

### Checklist

- [ ] Create tools/__init__.py
- [ ] Create tools/browse.py with list_collections, find_document
- [ ] Create tools/search.py with search_documents
- [ ] Create tools/read.py with read_document
- [ ] Test each tool manually
- [ ] Test tool registration

---

## Task 1.6: Server Entry Point

### src/file_knowledge_mcp/__main__.py

```python
"""CLI entry point."""

import argparse
import asyncio
import logging
import sys

from .server import create_server, run_server
from .config import load_config, ConfigError
from .search.ugrep import check_ugrep_installed


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="File-first knowledge base MCP server"
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to config.yaml",
        default=None,
    )
    parser.add_argument(
        "--root", "-r",
        help="Knowledge base root directory (overrides config)",
        default=None,
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Log level (overrides config)",
    )

    args = parser.parse_args()

    # Check ugrep
    if not check_ugrep_installed():
        print("ERROR: ugrep is not installed.", file=sys.stderr)
        print("Install with: apt install ugrep (Linux) or brew install ugrep (macOS)", file=sys.stderr)
        sys.exit(1)

    # Load config
    try:
        # If --root provided without config, create minimal config
        if args.root and not args.config:
            from .config import Config, KnowledgeConfig
            config = Config(knowledge=KnowledgeConfig(root=args.root))
        else:
            config = load_config(args.config)
            # Override root if provided
            if args.root:
                config.knowledge.root = args.root
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    # Override log level if provided
    log_level = args.log_level or config.server.log_level
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run server
    try:
        asyncio.run(run_server(config))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
```

### src/file_knowledge_mcp/server.py

```python
"""MCP Server setup and lifecycle."""

import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .config import Config
from .tools import register_all_tools

logger = logging.getLogger(__name__)


def create_server(config: Config) -> Server:
    """Create and configure MCP server.

    Args:
        config: Server configuration

    Returns:
        Configured Server instance
    """
    server = Server(config.server.name)

    # Register server info
    @server.list_resources()
    async def list_resources():
        return []  # Phase 2

    @server.list_prompts()
    async def list_prompts():
        return []  # Phase 2

    # Register tools
    register_all_tools(server, config)

    logger.info(f"Server '{config.server.name}' created")
    logger.info(f"Knowledge root: {config.knowledge.root}")

    return server


async def run_server(config: Config) -> None:
    """Run server with stdio transport.

    Args:
        config: Server configuration
    """
    server = create_server(config)

    logger.info("Starting MCP server on stdio...")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
```

### Checklist

- [ ] Create __main__.py with CLI
- [ ] Create server.py with MCP setup
- [ ] Test CLI: `python -m file_knowledge_mcp --help`
- [ ] Test with --root flag
- [ ] Test with config file
- [ ] Test connection from Claude Desktop

---

## Task 1.7: Testing

### tests/conftest.py

```python
"""Shared pytest fixtures."""

import tempfile
from pathlib import Path

import pytest

from file_knowledge_mcp.config import Config, KnowledgeConfig


@pytest.fixture
def temp_knowledge_dir():
    """Create temporary knowledge directory with sample files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create structure
        (root / "games").mkdir()
        (root / "games" / "coop").mkdir()
        (root / "sport").mkdir()

        # Create sample files
        (root / "games" / "Guide.md").write_text("# Game Guide\n\nWelcome to games!")
        (root / "games" / "coop" / "Gloomhaven.md").write_text(
            "# Gloomhaven\n\n## Movement\n\nYou can move up to your speed.\n\n## Attack\n\nRoll dice to attack."
        )
        (root / "sport" / "Football.md").write_text(
            "# Football Rules\n\n## Offside\n\nA player is offside if..."
        )

        yield root


@pytest.fixture
def config(temp_knowledge_dir):
    """Create config with temp directory."""
    return Config(knowledge=KnowledgeConfig(root=temp_knowledge_dir))
```

### tests/test_browse.py

```python
"""Tests for browse tools."""

import pytest
from file_knowledge_mcp.tools.browse import _list_collections, _find_document


@pytest.mark.asyncio
async def test_list_collections_root(config):
    result = await _list_collections(config, "")

    assert result["current_path"] == ""
    assert len(result["collections"]) == 2

    names = [c["name"] for c in result["collections"]]
    assert "games" in names
    assert "sport" in names


@pytest.mark.asyncio
async def test_list_collections_nested(config):
    result = await _list_collections(config, "games")

    assert result["current_path"] == "games"
    assert len(result["collections"]) == 1
    assert result["collections"][0]["name"] == "coop"
    assert len(result["documents"]) == 1
    assert result["documents"][0]["name"] == "Guide.md"


@pytest.mark.asyncio
async def test_find_document(config):
    result = await _find_document(config, "gloom", 10)

    assert result["total_found"] == 1
    assert result["matches"][0]["name"] == "Gloomhaven.md"
    assert result["matches"][0]["collection"] == "games/coop"
```

### Checklist

- [ ] Create conftest.py with fixtures
- [ ] Create test_config.py
- [ ] Create test_browse.py
- [ ] Create test_search.py (with mock or integration)
- [ ] Create test_read.py
- [ ] Run all tests: `pytest -v`
- [ ] Check coverage: `pytest --cov`

---

## Completion Criteria

Phase 1 is complete when:

- [ ] `file-knowledge-mcp --root ./docs` starts without errors
- [ ] Claude Desktop can connect and list tools
- [ ] `list_collections` returns folder structure
- [ ] `find_document` finds documents by name
- [ ] `search_documents` finds text in PDF/MD files
- [ ] `read_document` returns file content
- [ ] All tests pass
- [ ] README has quick start instructions
