"""MCP Tools registration."""

from mcp.server import Server
from mcp.types import TextContent, Tool

from ..config import Config
from .browse import get_browse_tools, handle_browse_tool
from .read import get_read_tools, handle_read_tool
from .search import get_search_tools, handle_search_tool


def register_all_tools(server: Server, config: Config) -> None:
    """Register all tools with the MCP server."""

    # Centralized list_tools handler
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return all available tools."""
        tools = []
        tools.extend(get_browse_tools())
        tools.extend(get_search_tools())
        tools.extend(get_read_tools())
        return tools

    # Centralized call_tool handler
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Route tool calls to appropriate handlers."""
        # Browse tools
        if name in ("list_collections", "find_document"):
            return await handle_browse_tool(name, arguments, config)

        # Search tools
        elif name in ("search_documents", "search_multiple"):
            return await handle_search_tool(name, arguments, config)

        # Read tools
        elif name in ("read_document", "get_document_info"):
            return await handle_read_tool(name, arguments, config)

        raise ValueError(f"Unknown tool: {name}")
