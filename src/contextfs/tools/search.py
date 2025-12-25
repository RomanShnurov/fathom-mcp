"""Search tools: search_documents."""

import logging
from typing import Any

from mcp.types import TextContent, Tool

from ..config import Config
from ..errors import document_not_found, path_not_found
from ..search.ugrep import SearchResult, UgrepEngine
from ..security import FileAccessControl

logger = logging.getLogger(__name__)


def get_search_tools() -> list[Tool]:
    """Get search tool definitions."""
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
        Tool(
            name="search_multiple",
            description="""Search for multiple terms in parallel within a document.
More efficient than calling search_documents multiple times.
Useful for complex questions involving several concepts.

Each term can use boolean syntax (space=AND, |=OR, -=NOT).""",
            inputSchema={
                "type": "object",
                "properties": {
                    "document_path": {
                        "type": "string",
                        "description": "Path to document",
                    },
                    "terms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of search terms (max 10)",
                        "maxItems": 10,
                    },
                    "context_lines": {
                        "type": "integer",
                        "default": 5,
                    },
                    "fuzzy": {
                        "type": "boolean",
                        "default": False,
                    },
                },
                "required": ["document_path", "terms"],
            },
        ),
    ]


async def handle_search_tool(name: str, arguments: dict[str, Any], config: Config) -> list[TextContent]:
    """Handle search tool calls."""
    engine = UgrepEngine(config)

    if name == "search_documents":
        result = await _search_documents(config, engine, arguments)
        return [TextContent(type="text", text=format_result(result))]
    elif name == "search_multiple":
        result = await _search_multiple(config, engine, arguments)
        return [TextContent(type="text", text=format_result(result))]

    raise ValueError(f"Unknown tool: {name}")


async def _search_documents(config: Config, engine: UgrepEngine, args: dict[str, Any]) -> dict[str, Any]:
    """Execute document search."""
    query = args["query"]
    scope = args["scope"]
    scope_type = scope["type"]
    context_lines = args.get("context_lines", 5)
    max_results = args.get("max_results", 20)
    fuzzy = args.get("fuzzy", False)

    root = config.knowledge.root
    access_control = FileAccessControl(root, config)

    # Resolve path based on scope
    if scope_type == "global":
        search_path = root
        recursive = True
    elif scope_type == "collection":
        path = scope.get("path", "")
        search_path = access_control.validate_path(path) if path else root
        if not search_path.exists():
            raise path_not_found(path)
        recursive = True
    elif scope_type == "document":
        path = scope.get("path", "")
        search_path = access_control.validate_path(path)
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
        matches.append(
            {
                "document": match.file,
                "line": match.line_number,
                "text": match.text,
                "context_before": match.context_before,
                "context_after": match.context_after,
            }
        )

    return {
        "matches": matches,
        "total_matches": result.total_matches,
        "truncated": result.truncated,
    }


async def _search_multiple(
    config: Config,
    engine: UgrepEngine,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Search multiple terms in parallel."""
    import asyncio
    import time

    document_path = args["document_path"]
    terms = args["terms"]
    context_lines = args.get("context_lines", 5)
    fuzzy = args.get("fuzzy", False)

    if not terms:
        return {"error": "No search terms provided"}

    if len(terms) > 10:
        terms = terms[:10]

    # Validate path using FileAccessControl
    access_control = FileAccessControl(config.knowledge.root, config)
    full_path = access_control.validate_path(document_path)

    if not full_path.exists():
        raise document_not_found(document_path)

    start_time = time.monotonic()

    # Launch all searches in parallel
    tasks = [
        engine.search(
            query=term,
            path=full_path,
            recursive=False,
            context_lines=context_lines,
            max_results=10,  # Limit per-term
            fuzzy=fuzzy,
        )
        for term in terms
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Build result dictionary
    result_dict = {}
    for term, result in zip(terms, results, strict=True):
        if isinstance(result, Exception):
            result_dict[term] = {
                "found": False,
                "error": str(result),
            }
        elif isinstance(result, SearchResult):
            result_dict[term] = {
                "found": result.total_matches > 0,
                "match_count": result.total_matches,
                "excerpts": [
                    {
                        "text": m.text,
                        "line": m.line_number,
                    }
                    for m in result.matches[:5]  # Top 5 per term
                ],
            }

    duration_ms = int((time.monotonic() - start_time) * 1000)

    return {
        "results": result_dict,
        "search_duration_ms": duration_ms,
    }


def format_result(result: dict[str, Any]) -> str:
    import json

    return json.dumps(result, indent=2, ensure_ascii=False)
