"""Browse tools: list_collections, find_document."""

import fnmatch
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.types import TextContent, Tool

from ..config import Config
from ..errors import path_not_found
from ..security import FileAccessControl

logger = logging.getLogger(__name__)


def get_browse_tools() -> list[Tool]:
    """Get browse tool definitions."""
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


async def handle_browse_tool(name: str, arguments: dict[str, Any], config: Config) -> list[TextContent]:
    """Handle browse tool calls."""
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


async def _list_collections(config: Config, path: str) -> dict[str, Any]:
    """List collections at path."""
    root = config.knowledge.root

    # Validate path using FileAccessControl
    access_control = FileAccessControl(root, config)
    target = access_control.validate_path(path) if path else root

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
            collections.append(
                {
                    "name": item.name,
                    "path": str(item.relative_to(root)),
                    "document_count": doc_count,
                    "subcollection_count": subcoll_count,
                }
            )
        elif item.suffix.lower() in config.supported_extensions:
            stat = item.stat()
            documents.append(
                {
                    "name": item.name,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

    return {
        "current_path": path,
        "collections": collections,
        "documents": documents,
    }


async def _find_document(config: Config, query: str, limit: int) -> dict[str, Any]:
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
        matches.append(
            {
                "name": file_path.name,
                "path": str(rel_path),
                "collection": str(rel_path.parent) if rel_path.parent != Path(".") else "",
                "size_bytes": file_path.stat().st_size,
                "score": score,
            }
        )

    # Sort by score descending
    from typing import cast
    matches.sort(key=lambda x: cast(float, x["score"]), reverse=True)

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
        if item.is_file() and item.suffix.lower() in config.supported_extensions and not _should_exclude(item, config):
            count += 1
    return count


def format_result(result: dict[str, Any]) -> str:
    """Format result as readable string."""
    import json

    return json.dumps(result, indent=2, ensure_ascii=False)
