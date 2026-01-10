#!/usr/bin/env python3
"""CLI tool for testing search_documents MCP tool.

Usage:
    python search_cli.py "your search query"
    python search_cli.py "attack armor" --scope collection --path "game"
    python search_cli.py "move|teleport" --fuzzy
    python search_cli.py '"exact phrase"' --max-results 10
"""

import argparse
import asyncio
import json
import sys
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Search documents via Fathom MCP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Global search
  python search_cli.py "python async"

  # Search in specific collection
  python search_cli.py "docker" --scope collection --path "docs"

  # Search in specific document
  python search_cli.py "test" --scope document --path "README.md"

  # Boolean operators
  python search_cli.py "attack armor"     # AND
  python search_cli.py "move|teleport"    # OR
  python search_cli.py "attack -ranged"   # NOT
  python search_cli.py '"end of turn"'    # Exact phrase

  # With options
  python search_cli.py "error" --context 10 --max-results 5 --fuzzy
        """,
    )

    parser.add_argument("query", help="Search query (supports boolean operators)")

    parser.add_argument(
        "--url",
        default="http://localhost:8765/mcp",
        help="MCP server URL (default: http://localhost:8765/mcp)",
    )

    parser.add_argument(
        "--scope",
        choices=["global", "collection", "document"],
        default="global",
        help="Search scope (default: global)",
    )

    parser.add_argument(
        "--path",
        help="Path for collection/document scope (required for non-global)",
    )

    parser.add_argument(
        "--context",
        type=int,
        default=5,
        help="Lines of context around matches (default: 5)",
    )

    parser.add_argument(
        "--max-results",
        type=int,
        default=20,
        help="Maximum number of matches (default: 20)",
    )

    parser.add_argument(
        "--fuzzy",
        action="store_true",
        help="Enable fuzzy matching",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON response",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args()


async def search_documents(url: str, query: str, **kwargs: Any) -> dict[str, Any]:
    """Call search_documents tool via MCP.

    Args:
        url: MCP server URL
        query: Search query
        **kwargs: Additional search parameters (scope, path, context_lines, etc.)

    Returns:
        Tool result
    """
    # Build scope object
    scope = {"type": kwargs.get("scope", "global")}
    if kwargs.get("path"):
        scope["path"] = kwargs["path"]

    # Build tool arguments
    arguments = {
        "query": query,
        "scope": scope,
        "context_lines": kwargs.get("context", 5),
        "max_results": kwargs.get("max_results", 20),
        "fuzzy": kwargs.get("fuzzy", False),
    }

    # Connect to MCP server
    async with streamable_http_client(url) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Call tool
            result = await session.call_tool("search_documents", arguments)

            return result


def format_result(result: Any, verbose: bool = False) -> str:
    """Format search result for display.

    Args:
        result: MCP tool result
        verbose: Include verbose output

    Returns:
        Formatted string
    """
    if not result.content:
        return "No results found."

    # Extract text content
    text_content = None
    for content in result.content:
        if hasattr(content, "text"):
            text_content = content.text
            break

    if not text_content:
        return "No text content in result."

    if verbose:
        return f"=== Search Result ===\n{text_content}\n=== End Result ==="

    return text_content


async def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Validate arguments
    if args.scope in ("collection", "document") and not args.path:
        print(
            f"Error: --path is required when --scope is '{args.scope}'",
            file=sys.stderr,
        )
        return 1

    # Display search parameters
    if args.verbose:
        print("=== Search Parameters ===", file=sys.stderr)
        print(f"URL: {args.url}", file=sys.stderr)
        print(f"Query: {args.query}", file=sys.stderr)
        print(f"Scope: {args.scope}", file=sys.stderr)
        if args.path:
            print(f"Path: {args.path}", file=sys.stderr)
        print(f"Context lines: {args.context}", file=sys.stderr)
        print(f"Max results: {args.max_results}", file=sys.stderr)
        print(f"Fuzzy: {args.fuzzy}", file=sys.stderr)
        print(file=sys.stderr)

    try:
        # Execute search
        result = await search_documents(
            args.url,
            args.query,
            scope=args.scope,
            path=args.path,
            context=args.context,
            max_results=args.max_results,
            fuzzy=args.fuzzy,
        )

        # Output result
        if args.json:
            # Output raw JSON
            output = {
                "content": [
                    {"type": c.type, "text": c.text if hasattr(c, "text") else None}
                    for c in result.content
                ],
                "isError": result.isError if hasattr(result, "isError") else False,
            }
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            # Format and print
            print(format_result(result, verbose=args.verbose))

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
