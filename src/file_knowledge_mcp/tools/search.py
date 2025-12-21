"""Search tools: search_documents."""

import logging

from mcp.server import Server
from mcp.types import TextContent, Tool

from ..config import Config
from ..errors import document_not_found, path_not_found
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
